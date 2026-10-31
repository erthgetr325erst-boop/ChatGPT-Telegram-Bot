import requests
import json
import uuid
import telebot
import time
import sqlite3
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
from typing import Dict, List, Optional, Tuple

BOT_TOKEN = "توكن"
CHANNEL_USERNAME = "@hackeronions"
CHANNEL_ID = "@hackeronions"

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect('chatbot_data.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    conv_id TEXT,
    model TEXT,
    created_at TEXT,
    messages_count INTEGER DEFAULT 0,
    last_activity TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS messages_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    conv_id TEXT,
    user_message TEXT,
    bot_response TEXT,
    model TEXT,
    timestamp TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    model TEXT DEFAULT 'auto',
    streaming_enabled INTEGER DEFAULT 1
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS saved_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    prompt_name TEXT,
    prompt_text TEXT,
    created_at TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_subscription (
    user_id INTEGER PRIMARY KEY,
    is_verified INTEGER DEFAULT 0,
    last_check TEXT
)
''')

conn.commit()

SUPPORTED_MODELS = {
    'auto': '🤖 تلقائي (موصى به)',
    'gpt-4': '🚀 GPT-4 (متقدم)',
    'gpt-4o': '🦾 GPT-4o (أحدث إصدار)',
    'gpt-4-turbo': '🧠 GPT-4 Turbo (سريع وقوي)',
    'gpt-4-turbo-preview': '⚡ GPT-4 Turbo Preview',
    'gpt-3.5-turbo': '💨 GPT-3.5 Turbo (أسرع نموذج)',
    'gpt-4o-mini': '📱 GPT-4o Mini (خفيف وسريع)',
    'gpt-4-32k': '📚 GPT-4 32K (سياقات طويلة)',
    'gpt-3.5-turbo-16k': '📖 GPT-3.5 16K (سياقات متوسطة)'
}

class ConversationData:
    def __init__(self, conv_id, model="auto"):
        self.conv_id = conv_id
        self.conversation_id = None
        self.parent_message_id = None
        self.headers = {}
        self.model = model
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.messages_count = 0
        self.last_activity = datetime.now()

user_conversations: Dict[int, Dict[str, ConversationData]] = {}
user_current_conv: Dict[int, str] = {}

HEADERS = {
    'User-Agent': "ChatGPT/1.2027.000 (Android 15; RMX3834; build 2700000)",
    'Accept': "application/json",
    'Accept-Encoding': "gzip",
    'Content-Type': "application/json",
    'oai-package-name': "com.Modderme",
    'oai-client-type': "android",
    'oai-device-id': "84329164059103383964",
    'accept-language': "en-US,en;q=0.9,ar-EG;q=0.8,ar;q=0.7",
    'x-device-tier': "lower_mid",
    'chatgpt-account-id': "84329164059103383964",
    'chatgpt-residency-region': "no_constraint",
    'Cookie': "__cflb=04dTod5Jcx9DYJeMeKbyj32ve2B3i9pLVRxJxEAaKD; _cfuvid=PXu6q36jhfgxnsdFkDmqwLzCfHOSgG588liApL0856A-1777834828.2542033-1.0.1.1-JFC10kaoqt9_IXzxrixI6zZuAm.TzRPF14QfJiD43MQ; oai-ll=; oai-sc=0gAAAAABp959mEmk6Qr5JsnqYMpWx1-15EJhCVV2EV6SQpet7Z7SjNuAT0x2cVScJu_g_TE9_NXidYfi68DtZfl4ImOQIRkr8PF-R-v9PUl7IPGtYiF1rwqdVm0NjapKV1lROdrmNGkiuNgcVMGYXMrP45hfmmQKiCQ5MBQLjfI7XI2tKSLvHT3WkjFEnmDZIRtVz85lyV9pxK181GJRARSxM53m06IfD3jEDjVbSR5QDQbL6Nxl4l7c; __cf_bm=y_lpbPz3viZYHSAd8nCLtIlm2JBCYWvEwOz8xvvwFow-1777835878.3854406-1.0.1.1-Muu0UxZKqufJhSVDELNGz2fO12Xcqc.oJ3hINoXkGIc2tGinJqVnmBTM7EAKDRfqdl1WdKtZ06fuCJ3y5DddxeMPVlBNX_r7daQReYa59qkFBwXOF3p4W3lwU.tdPN9A"
}

def check_subscription(user_id: int) -> bool:
    try:
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            cursor.execute('UPDATE user_subscription SET is_verified = 1, last_check = ? WHERE user_id = ?', 
                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
            conn.commit()
            return True
        else:
            cursor.execute('UPDATE user_subscription SET is_verified = 0, last_check = ? WHERE user_id = ?',
                          (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
            conn.commit()
            return False
    except:
        return False

def subscription_required(func):
    def wrapper(message: Message, *args, **kwargs):
        user_id = message.from_user.id
        
        cursor.execute('SELECT is_verified FROM user_subscription WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            if check_subscription(user_id):
                return func(message, *args, **kwargs)
        
        if check_subscription(user_id):
            return func(message, *args, **kwargs)
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        keyboard.add(InlineKeyboardButton("✅ تأكد من الاشتراك", callback_data="check_subscription"))
        keyboard.add(InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="check_subscription"))
        
        bot.reply_to(
            message, 
            f"⚠️ **عذراً! يجب عليك الاشتراك في قناتنا أولاً** ⚠️\n\n"
            f"🔴 **القناة:** {CHANNEL_USERNAME}\n\n"
            f"✨ **لماذا الاشتراك؟**\n"
            f"• 🤖 تحديثات مستمرة للبوت\n"
            f"• 🚀 مميزات حصرية\n"
            f"• 💡 نصائح واستخدامات متقدمة\n"
            f"• 🆕 إعلانات عن الإصدارات الجديدة\n\n"
            f"✅ **بعد الاشتراك، اضغط على زر التأكيد**",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return None
    return wrapper

def split_long_message(text: str, max_length: int = 4000) -> List[str]:
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    lines = text.split('\n')
    current_chunk = ""
    
    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
            if len(current_chunk) > max_length:
                for i in range(0, len(current_chunk), max_length):
                    chunks.append(current_chunk[i:i+max_length])
                current_chunk = ""
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def get_conduit_token() -> Optional[str]:
    url_prepare = "https://android.chat.openai.com/backend-api/f/conversation/prepare"
    
    payload = {
        "action": "next",
        "messages": [],
        "model": "auto",
        "history_and_training_disabled": False,
        "fork_from_shared_post": False,
        "enable_message_followups": False,
        "force_use_sse": False,
        "force_use_search": None,
        "force_paragen": False,
        "supports_buffering": False,
        "timezone": "Africa/Cairo",
        "timezone_offset_min": -180,
        "system_hints": [],
        "is_onboarding_conversation": False
    }
    
    try:
        response = requests.post(url_prepare, json=payload, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            return response.json().get("conduit_token", "")
    except:
        pass
    return None

def create_conversation(user_id: int, model: str = "auto") -> Optional[str]:
    token = get_conduit_token()
    if not token:
        return None
    
    conv_headers = HEADERS.copy()
    conv_headers['Conduit-Token'] = token
    conv_headers['x-oai-convo-session-id'] = str(uuid.uuid4())
    conv_headers['x-oai-turn-trace-id'] = str(uuid.uuid4())
    conv_headers['x-openai-target-path'] = "/backend-api/f/conversation"
    
    conv_id = str(uuid.uuid4())[:8]
    conv_data = ConversationData(conv_id, model)
    conv_data.headers = conv_headers
    
    if user_id not in user_conversations:
        user_conversations[user_id] = {}
    
    user_conversations[user_id][conv_id] = conv_data
    user_current_conv[user_id] = conv_id
    
    cursor.execute('''
        INSERT INTO conversations (user_id, conv_id, model, created_at, messages_count, last_activity)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, conv_id, model, conv_data.created_at, 0, conv_data.last_activity.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    return conv_id

def send_ai_response(chat_id: int, user_id: int, conv_id: str, message_text: str) -> bool:
    if user_id not in user_conversations or conv_id not in user_conversations[user_id]:
        return False
    
    conv = user_conversations[user_id][conv_id]
    
    cursor.execute('SELECT model, streaming_enabled FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    model = settings[0] if settings else 'auto'
    streaming = settings[1] if settings else 1
    
    message_id = str(uuid.uuid4())
    new_parent_id = str(uuid.uuid4())
    
    payload = {
        "action": "next",
        "messages": [{
            "id": message_id,
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": [message_text]},
            "status": "finished_successfully"
        }],
        "model": model,
        "parent_message_id": conv.parent_message_id if conv.parent_message_id else new_parent_id,
        "stream": bool(streaming),
        "timezone": "Africa/Cairo",
        "timezone_offset_min": -180
    }
    
    if conv.conversation_id:
        payload["conversation_id"] = conv.conversation_id
    
    try:
        bot.send_chat_action(chat_id, 'typing')
        
        response = requests.post(
            'https://android.chat.openai.com/backend-api/f/conversation',
            headers=conv.headers,
            json=payload,
            stream=bool(streaming),
            timeout=60
        )
        
        if response.status_code == 200:
            full_response = ""
            last_message_id = None
            sent_message = None
            
            for line in response.iter_lines(decode_unicode=True):
                if line and line.strip().startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    
                    try:
                        event = json.loads(data)
                        
                        if 'conversation_id' in event and not conv.conversation_id:
                            conv.conversation_id = event['conversation_id']
                        
                        if 'message' in event and 'content' in event['message']:
                            parts = event['message']['content'].get('parts', [])
                            if parts and parts[0] and parts[0] != full_response:
                                full_response = parts[0]
                                
                                if sent_message is None:
                                    sent_message = bot.send_message(chat_id, full_response[:4000], parse_mode='Markdown')
                                else:
                                    try:
                                        if len(full_response) <= 4000:
                                            bot.edit_message_text(full_response, chat_id, sent_message.message_id, parse_mode='Markdown')
                                    except:
                                        pass
                            
                            if 'id' in event['message']:
                                last_message_id = event['message']['id']
                    except:
                        pass
            
            if last_message_id:
                conv.parent_message_id = last_message_id
                conv.messages_count += 1
                
                cursor.execute('''
                    INSERT INTO messages_history (user_id, conv_id, user_message, bot_response, model, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, conv_id, message_text, full_response, model, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                
                cursor.execute('UPDATE conversations SET messages_count = ?, last_activity = ? WHERE conv_id = ?',
                              (conv.messages_count, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), conv_id))
                conn.commit()
                
                if len(full_response) > 4000:
                    chunks = split_long_message(full_response)
                    for chunk in chunks[1:]:
                        time.sleep(0.5)
                        bot.send_message(chat_id, chunk, parse_mode='Markdown')
            
            return True
        else:
            bot.send_message(chat_id, f"❌ خطأ: {response.status_code}")
            return False
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ: {str(e)[:100]}")
        return False

def get_main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("💬 محادثة جديدة", callback_data="new_conv"),
        InlineKeyboardButton("🗑️ حذف المحادثة", callback_data="del_conv"),
        InlineKeyboardButton("📋 قائمة المحادثات", callback_data="list_convs"),
        InlineKeyboardButton("🔄 تبديل المحادثة", callback_data="switch_conv"),
        InlineKeyboardButton("🤖 تغيير النموذج", callback_data="change_model"),
        InlineKeyboardButton("⭐ حفظ سؤال", callback_data="save_prompt"),
        InlineKeyboardButton("📜 محفوظاتي", callback_data="my_prompts"),
        InlineKeyboardButton("📊 الإحصائيات", callback_data="my_stats"),
        InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings"),
        InlineKeyboardButton("ℹ️ معلومات", callback_data="info"),
        InlineKeyboardButton("🗑️ مسح الكل", callback_data="clear_all"),
        InlineKeyboardButton("📢 قناتنا", callback_data="channel_info")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_conversations_list(user_id: int, page: int = 0) -> Tuple[Optional[InlineKeyboardMarkup], int]:
    if user_id not in user_conversations or not user_conversations[user_id]:
        return None, 0
    
    convs = list(user_conversations[user_id].keys())
    items_per_page = 6
    total_pages = (len(convs) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for conv_id in convs[start:end]:
        conv = user_conversations[user_id][conv_id]
        is_current = "✓ " if user_current_conv.get(user_id) == conv_id else ""
        keyboard.add(InlineKeyboardButton(
            f"{is_current}💬 {conv_id[:6]} ({conv.messages_count} رسائل)",
            callback_data=f"select_conv_{conv_id}"
        ))
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"conv_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"conv_page_{page+1}"))
    if nav:
        keyboard.row(*nav)
    
    keyboard.add(InlineKeyboardButton("➕ محادثة جديدة", callback_data="new_conv"))
    keyboard.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    
    return keyboard, total_pages

def get_settings_menu(user_id: int):
    cursor.execute('SELECT model, streaming_enabled FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    
    if not settings:
        cursor.execute('INSERT INTO user_settings (user_id, model, streaming_enabled) VALUES (?, ?, ?)', (user_id, 'auto', 1))
        conn.commit()
        model, streaming = 'auto', 1
    else:
        model, streaming = settings
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"🤖 النموذج: {SUPPORTED_MODELS.get(model, model.upper())}", callback_data="change_model"),
        InlineKeyboardButton(f"📡 وضع التدفق: {'✅ مفعل' if streaming else '❌ معطل'}", callback_data="toggle_stream"),
        InlineKeyboardButton("🔄 إعادة تعيين", callback_data="reset_settings"),
        InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return keyboard

def get_models_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    models_list = list(SUPPORTED_MODELS.items())
    for i in range(0, len(models_list), 2):
        row_buttons = []
        model_code, model_name = models_list[i]
        row_buttons.append(InlineKeyboardButton(model_name, callback_data=f"set_model_{model_code}"))
        if i + 1 < len(models_list):
            model_code2, model_name2 = models_list[i + 1]
            row_buttons.append(InlineKeyboardButton(model_name2, callback_data=f"set_model_{model_code2}"))
        keyboard.row(*row_buttons)
    
    keyboard.add(InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
    return keyboard

def get_prompts_menu(user_id: int, page: int = 0):
    cursor.execute('SELECT id, prompt_name, prompt_text FROM saved_prompts WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    prompts = cursor.fetchall()
    
    if not prompts:
        return None, 0
    
    items_per_page = 5
    total_pages = (len(prompts) + items_per_page - 1) // items_per_page
    start = page * items_per_page
    end = start + items_per_page
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for pid, name, text in prompts[start:end]:
        display_name = name[:25] + "..." if len(name) > 25 else name
        keyboard.add(InlineKeyboardButton(f"📌 {display_name}", callback_data=f"use_prompt_{pid}"))
        keyboard.add(InlineKeyboardButton(f"🗑️ حذف", callback_data=f"del_prompt_{pid}"))
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"prompt_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"prompt_page_{page+1}"))
    if nav:
        keyboard.row(*nav)
    
    keyboard.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    return keyboard, total_pages

@bot.message_handler(commands=['start', 'help'])
def start_command(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or ""
    
    cursor.execute('SELECT is_verified FROM user_subscription WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] == 0:
        if check_subscription(user_id):
            pass
        else:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
            keyboard.add(InlineKeyboardButton("✅ تأكد من الاشتراك", callback_data="check_subscription"))
            
            bot.send_message(
                message.chat.id,
                f"⚠️ **مرحباً {first_name}!** ⚠️\n\n"
                f"🔴 **للوصول إلى البوت، يجب عليك الاشتراك في قناتنا أولاً**\n\n"
                f"📢 **قناتنا:** {CHANNEL_USERNAME}\n\n"
                f"✨ **مميزات الاشتراك:**\n"
                f"• 🤖 تحديثات مستمرة للبوت\n"
                f"• 🚀 مميزات حصرية جديدة\n"
                f"• 💡 نصائح واستخدامات متقدمة\n"
                f"• 🆕 إعلانات عن الإصدارات الجديدة\n\n"
                f"✅ **بعد الاشتراك، اضغط على زر التأكيد**",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            return
    
    if user_id not in user_conversations or not user_conversations[user_id]:
        create_conversation(user_id)
    
    cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO user_settings (user_id, model, streaming_enabled) VALUES (?, ?, ?)', (user_id, 'auto', 1))
        conn.commit()
    
    welcome_text = f"""
✨ **مرحباً بك {first_name} في بوت ChatGPT المتطور!** ✨

🤖 **المميزات:**
• ✅ ردود متدفقة (Streaming)
• ✅ تقسيم تلقائي للرسائل الطويلة
• ✅ محادثات متعددة غير محدودة
• ✅ حفظ الأسئلة المفضلة
• ✅ **{len(SUPPORTED_MODELS)} نموذج ذكاء اصطناعي**
• ✅ واجهة أزرار تفاعلية
• ✅ حفظ تاريخ المحادثات

⚡ **النماذج المتوفرة:**
{chr(10).join([f'• {name}' for name in SUPPORTED_MODELS.values()])}

💬 **طريقة الاستخدام:**
فقط أرسل سؤالك وستحصل على إجابة فورية!

👨‍💻 **المطور:** محمود عادل
📢 **قناتنا:** {CHANNEL_USERNAME}
    """
    
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=get_main_menu())

@bot.message_handler(commands=['menu'])
@subscription_required
def menu_command(message: Message):
    bot.send_message(message.chat.id, "📋 **القائمة الرئيسية:**", parse_mode='Markdown', reply_markup=get_main_menu())

@bot.message_handler(commands=['models'])
@subscription_required
def models_command(message: Message):
    models_text = "🤖 **النماذج المتوفرة في البوت:**\n\n"
    for code, name in SUPPORTED_MODELS.items():
        models_text += f"• **{name}**\n  `{code}`\n\n"
    models_text += "\n💡 استخدم 'تغيير النموذج' من القائمة لاختيار نموذج مختلف"
    bot.reply_to(message, models_text, parse_mode='Markdown')

@bot.message_handler(commands=['new'])
@subscription_required
def new_conv_command(message: Message):
    user_id = message.from_user.id
    cursor.execute('SELECT model FROM user_settings WHERE user_id = ?', (user_id,))
    model = cursor.fetchone()
    model = model[0] if model else 'auto'
    
    conv_id = create_conversation(user_id, model)
    if conv_id:
        model_name = SUPPORTED_MODELS.get(model, model.upper())
        bot.reply_to(message, f"✅ **تم إنشاء محادثة جديدة!**\nالمعرف: `{conv_id}`\nالنموذج: {model_name}", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ فشل إنشاء المحادثة. حاول مرة أخرى.")

@bot.message_handler(commands=['delete'])
@subscription_required
def delete_conv_command(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_conversations or not user_conversations[user_id]:
        bot.reply_to(message, "⚠️ لا توجد محادثات للحذف!")
        return
    
    conv_id = user_current_conv.get(user_id, list(user_conversations[user_id].keys())[-1])
    del user_conversations[user_id][conv_id]
    
    if user_conversations[user_id]:
        user_current_conv[user_id] = list(user_conversations[user_id].keys())[-1]
        bot.reply_to(message, f"🗑️ **تم حذف المحادثة** `{conv_id}`")
    else:
        del user_conversations[user_id]
        if user_id in user_current_conv:
            del user_current_conv[user_id]
        bot.reply_to(message, "🗑️ **تم حذف جميع المحادثات!**\nاستخدم /new لإنشاء محادثة جديدة.")

@bot.message_handler(commands=['save'])
@subscription_required
def save_prompt_command(message: Message):
    bot.reply_to(message, "📝 **لحفظ سؤال:**\nأرسل السؤال بالصيغة:\n`/save اسم_السؤال: نص السؤال`\n\nمثال:\n`/save الرياضيات: ما هي المعادلة التربيعية؟`", parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
@subscription_required
def stats_command(message: Message):
    user_id = message.from_user.id
    cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
    convs_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM messages_history WHERE user_id = ?', (user_id,))
    msgs_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT model FROM user_settings WHERE user_id = ?', (user_id,))
    model = cursor.fetchone()
    current_model = SUPPORTED_MODELS.get(model[0], model[0].upper()) if model else 'تلقائي'
    
    stats_text = f"""
📊 **إحصائياتك الشخصية** 📊

💬 **إجمالي الرسائل:** {msgs_count}
🗂️ **المحادثات المنشأة:** {convs_count}
🤖 **النموذج الحالي:** {current_model}
📅 **تاريخ اليوم:** {datetime.now().strftime("%Y-%m-%d")}

💡 **نصيحة:** استخدم /new لإنشاء محادثة جديدة!
    """
    bot.reply_to(message, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['list'])
@subscription_required
def list_convs_command(message: Message):
    user_id = message.from_user.id
    if user_id not in user_conversations or not user_conversations[user_id]:
        bot.reply_to(message, "⚠️ لا توجد محادثات! استخدم /new لإنشاء محادثة جديدة.")
        return
    
    convs = list(user_conversations[user_id].keys())
    text = "📋 **قائمة المحادثات:**\n\n"
    for i, conv_id in enumerate(convs, 1):
        conv = user_conversations[user_id][conv_id]
        current = "✓ " if user_current_conv.get(user_id) == conv_id else ""
        text += f"{i}. {current}`{conv_id}` ({conv.messages_count} رسائل)\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['switch'])
@subscription_required
def switch_conv_command(message: Message):
    user_id = message.from_user.id
    result = get_conversations_list(user_id)
    if result[0]:
        markup, pages = result
        bot.reply_to(message, f"🔄 **اختر المحادثة للتبديل إليها:**", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.reply_to(message, "⚠️ لا توجد محادثات! استخدم /new لإنشاء محادثة جديدة.")

@bot.message_handler(func=lambda message: True)
@subscription_required
def handle_message(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if message.text.startswith('/save'):
        try:
            content = message.text[6:].strip()
            if ':' not in content:
                bot.reply_to(message, "❌ صيغة خاطئة!\nاستخدم: `/save الاسم: السؤال`", parse_mode='Markdown')
                return
            
            name, text = content.split(':', 1)
            name = name.strip()
            text = text.strip()
            
            cursor.execute('''
                INSERT INTO saved_prompts (user_id, prompt_name, prompt_text, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            
            bot.reply_to(message, f"✅ **تم حفظ السؤال:** {name}\nيمكنك استخدامه لاحقاً من القائمة", parse_mode='Markdown')
        except:
            bot.reply_to(message, "❌ حدث خطأ في حفظ السؤال")
        return
    
    if user_id not in user_conversations or not user_conversations[user_id]:
        create_conversation(user_id)
    
    conv_id = user_current_conv.get(user_id, list(user_conversations[user_id].keys())[-1])
    
    status = bot.reply_to(message, "⏳ **جاري التفكير...**", parse_mode='Markdown')
    bot.delete_message(chat_id, status.message_id)
    
    send_ai_response(chat_id, user_id, conv_id, message.text)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: CallbackQuery):
    user_id = call.from_user.id
    data = call.data
    
    if data == "check_subscription":
        if check_subscription(user_id):
            bot.answer_callback_query(call.id, "✅ تم التحقق! يمكنك استخدام البوت الآن")
            
            if user_id not in user_conversations or not user_conversations[user_id]:
                create_conversation(user_id)
            
            cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO user_settings (user_id, model, streaming_enabled) VALUES (?, ?, ?)', (user_id, 'auto', 1))
                conn.commit()
            
            welcome_text = f"""
✨ **مرحباً بك في بوت ChatGPT المتطور!** ✨

🤖 **المميزات:**
• ✅ ردود متدفقة (Streaming)
• ✅ تقسيم تلقائي للرسائل الطويلة
• ✅ محادثات متعددة غير محدودة
• ✅ حفظ الأسئلة المفضلة
• ✅ **{len(SUPPORTED_MODELS)} نموذج ذكاء اصطناعي**
• ✅ واجهة أزرار تفاعلية

💬 **فقط أرسل سؤالك وستحصل على إجابة فورية!**

👨‍💻 **المطور:** محمود عادل
📢 **قناتنا:** {CHANNEL_USERNAME}
            """
            bot.edit_message_text(
                welcome_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=get_main_menu()
            )
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك بعد! اشترك في القناة ثم حاول مرة أخرى", show_alert=True)
    
    elif data == "channel_info":
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📢 اضغط للاشتراك", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        keyboard.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
        
        bot.edit_message_text(
            f"📢 **قناتنا الرسمية** 📢\n\n"
            f"🔴 **القناة:** {CHANNEL_USERNAME}\n\n"
            f"✨ **مميزات الاشتراك:**\n"
            f"• 🤖 تحديثات مستمرة للبوت\n"
            f"• 🚀 مميزات حصرية جديدة\n"
            f"• 💡 نصائح واستخدامات متقدمة\n"
            f"• 🆕 إعلانات عن الإصدارات الجديدة\n"
            f"• 🎁 عروض ومسابقات حصرية\n\n"
            f"✅ **اشترك الآن لتصبح من المستخدمين المميزين!**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    elif data == "list_convs" or data == "switch_conv":
        result = get_conversations_list(user_id)
        if result[0]:
            markup, pages = result
            bot.edit_message_text(
                f"📋 **قائمة المحادثات** (الصفحة 1 من {pages})\n✓ = المحادثة الحالية",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "⚠️ لا توجد محادثات!", show_alert=True)
    
    elif data.startswith("conv_page_"):
        page = int(data.split("_")[2])
        result = get_conversations_list(user_id, page)
        if result[0]:
            markup, pages = result
            bot.edit_message_text(
                f"📋 **قائمة المحادثات** (الصفحة {page+1} من {pages})",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
    
    elif data.startswith("select_conv_"):
        conv_id = data.replace("select_conv_", "")
        if conv_id in user_conversations.get(user_id, {}):
            user_current_conv[user_id] = conv_id
            bot.answer_callback_query(call.id, f"✅ تم التبديل إلى {conv_id}")
            bot.edit_message_text(
                f"✅ **تم التبديل إلى المحادثة** `{conv_id}`",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=get_main_menu()
            )
    
    elif data == "new_conv":
        cursor.execute('SELECT model FROM user_settings WHERE user_id = ?', (user_id,))
        model = cursor.fetchone()
        model = model[0] if model else 'auto'
        
        conv_id = create_conversation(user_id, model)
        if conv_id:
            model_name = SUPPORTED_MODELS.get(model, model.upper())
            bot.edit_message_text(
                f"✅ **محادثة جديدة!**\nالمعرف: `{conv_id}`\nالنموذج: {model_name}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=get_main_menu()
            )
        else:
            bot.answer_callback_query(call.id, "❌ فشل الإنشاء", show_alert=True)
    
    elif data == "del_conv":
        if user_id not in user_conversations or not user_conversations[user_id]:
            bot.answer_callback_query(call.id, "⚠️ لا توجد محادثات!", show_alert=True)
            return
        
        conv_id = user_current_conv.get(user_id, list(user_conversations[user_id].keys())[0])
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("✅ نعم", callback_data=f"confirm_del_{conv_id}"),
            InlineKeyboardButton("❌ لا", callback_data="back_main")
        )
        bot.edit_message_text(
            f"⚠️ **تأكيد حذف المحادثة** `{conv_id}`؟",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    elif data.startswith("confirm_del_"):
        conv_id = data.replace("confirm_del_", "")
        if conv_id in user_conversations.get(user_id, {}):
            del user_conversations[user_id][conv_id]
            
            if user_conversations[user_id]:
                user_current_conv[user_id] = list(user_conversations[user_id].keys())[0]
            else:
                del user_conversations[user_id]
                if user_id in user_current_conv:
                    del user_current_conv[user_id]
            
            bot.edit_message_text(
                "🗑️ **تم حذف المحادثة بنجاح!**",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=get_main_menu()
            )
    
    elif data == "settings":
        bot.edit_message_text(
            "⚙️ **الإعدادات:**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_settings_menu(user_id)
        )
    
    elif data == "change_model":
        bot.edit_message_text(
            "🤖 **اختر النموذج المناسب:**\n\n" + 
            "\n".join([f"• **{name}**" for name in SUPPORTED_MODELS.values()]),
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_models_menu()
        )
    
    elif data.startswith("set_model_"):
        model = data.replace("set_model_", "")
        if model in SUPPORTED_MODELS:
            cursor.execute('UPDATE user_settings SET model = ? WHERE user_id = ?', (model, user_id))
            conn.commit()
            model_name = SUPPORTED_MODELS[model]
            bot.answer_callback_query(call.id, f"✅ تم تغيير النموذج إلى {model_name}")
            bot.edit_message_text(
                f"✅ **النموذج الحالي:** {model_name}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=get_settings_menu(user_id)
            )
        else:
            bot.answer_callback_query(call.id, "❌ نموذج غير مدعوم", show_alert=True)
    
    elif data == "toggle_stream":
        cursor.execute('SELECT streaming_enabled FROM user_settings WHERE user_id = ?', (user_id,))
        current = cursor.fetchone()
        current_val = current[0] if current else 1
        new_val = 0 if current_val else 1
        cursor.execute('UPDATE user_settings SET streaming_enabled = ? WHERE user_id = ?', (new_val, user_id))
        conn.commit()
        status = "مفعل" if new_val else "معطل"
        bot.answer_callback_query(call.id, f"✅ تم {status} وضع التدفق")
        bot.edit_message_text(
            "⚙️ **الإعدادات:**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_settings_menu(user_id)
        )
    
    elif data == "reset_settings":
        cursor.execute('UPDATE user_settings SET model = "auto", streaming_enabled = 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تم إعادة تعيين الإعدادات")
        bot.edit_message_text(
            "⚙️ **الإعدادات:**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_settings_menu(user_id)
        )
    
    elif data == "save_prompt":
        bot.edit_message_text(
            "📝 **لحفظ سؤال:**\nأرسل الأمر:\n`/save الاسم: السؤال`\n\nمثال:\n`/save الرياضيات: ما هو قانون الجذب؟`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
    
    elif data == "my_prompts":
        result = get_prompts_menu(user_id)
        if result[0]:
            markup, pages = result
            bot.edit_message_text(
                f"📌 **أسئلتك المحفوظة** (الصفحة 1 من {pages})\n\nاضغط على السؤال لاستخدامه، أو على حذف لإزالته",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "📭 لا توجد أسئلة محفوظة!", show_alert=True)
    
    elif data.startswith("prompt_page_"):
        page = int(data.split("_")[2])
        result = get_prompts_menu(user_id, page)
        if result[0]:
            markup, pages = result
            bot.edit_message_text(
                f"📌 **أسئلتك المحفوظة** (الصفحة {page+1} من {pages})",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
    
    elif data.startswith("use_prompt_"):
        pid = int(data.replace("use_prompt_", ""))
        cursor.execute('SELECT prompt_text FROM saved_prompts WHERE id = ? AND user_id = ?', (pid, user_id))
        result = cursor.fetchone()
        if result:
            bot.send_message(call.message.chat.id, f"📌 **سؤال من محفوظاتي:**\n{result[0]}\n\n⏳ جاري الإجابة...", parse_mode='Markdown')
            fake_message = type('obj', (object,), {
                'chat': call.message.chat,
                'text': result[0],
                'reply_to_message': None
            })()
            handle_message(fake_message)
    
    elif data.startswith("del_prompt_"):
        pid = int(data.replace("del_prompt_", ""))
        cursor.execute('DELETE FROM saved_prompts WHERE id = ? AND user_id = ?', (pid, user_id))
        conn.commit()
        bot.answer_callback_query(call.id, "🗑️ تم حذف السؤال المحفوظ")
        result = get_prompts_menu(user_id)
        if result[0]:
            markup, pages = result
            bot.edit_message_text(
                f"📌 **أسئلتك المحفوظة** (تم التحديث)",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=markup
            )
        else:
            bot.edit_message_text(
                "📭 **لا توجد أسئلة محفوظة!**\nاستخدم /save لحفظ سؤال جديد",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=get_main_menu()
            )
    
    elif data == "my_stats":
        cursor.execute('SELECT COUNT(*) FROM conversations WHERE user_id = ?', (user_id,))
        convs_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM messages_history WHERE user_id = ?', (user_id,))
        msgs_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT model FROM user_settings WHERE user_id = ?', (user_id,))
        model = cursor.fetchone()
        current_model = SUPPORTED_MODELS.get(model[0], model[0].upper()) if model else 'تلقائي'
        
        cursor.execute('SELECT streaming_enabled FROM user_settings WHERE user_id = ?', (user_id,))
        stream = cursor.fetchone()
        stream_status = "مفعل" if (stream[0] if stream else 1) else "معطل"
        
        cursor.execute('SELECT COUNT(*) FROM saved_prompts WHERE user_id = ?', (user_id,))
        saved_count = cursor.fetchone()[0]
        
        stats_text = f"""
📊 **إحصائياتك الشخصية** 📊

💬 **إجمالي الرسائل:** {msgs_count}
🗂️ **المحادثات المنشأة:** {convs_count}
🤖 **النموذج الحالي:** {current_model}
📡 **وضع التدفق:** {stream_status}
⭐ **الأسئلة المحفوظة:** {saved_count}
📅 **تاريخ اليوم:** {datetime.now().strftime("%Y-%m-%d")}

💡 **نصيحة:** استخدم /new لإنشاء محادثة جديدة!
        """
        bot.edit_message_text(
            stats_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
    
    elif data == "info":
        info_text = f"""
ℹ️ **معلومات البوت**

**📌 الإسم:** ChatGPT TeleBot
**📌 الإصدار:** 4.0.0
**📌 المطور:** محمود عادل
**📌 القناة:** {CHANNEL_USERNAME}

**✨ المميزات:**
• ✅ ردود متدفقة (Streaming)
• ✅ تقسيم تلقائي للرسائل الطويلة
• ✅ محادثات متعددة غير محدودة
• ✅ حفظ الأسئلة المفضلة
• ✅ **{len(SUPPORTED_MODELS)} نموذج ذكاء اصطناعي**
• ✅ واجهة أزرار تفاعلية
• ✅ حفظ تاريخ المحادثات
• ✅ اشتراك إجباري للقناة

**🤖 النماذج المتوفرة:**
{chr(10).join([f'• {name}' for name in SUPPORTED_MODELS.values()])}

**🔧 التقنيات:**
• Python 3.9+
• pyTelegramBotAPI
• SQLite Database
• ChatGPT API

🤖 **استمتع بالتجربة!**
        """
        bot.edit_message_text(info_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=get_main_menu())
    
    elif data == "clear_all":
        if user_id in user_conversations:
            user_conversations[user_id] = {}
        if user_id in user_current_conv:
            del user_current_conv[user_id]
        
        bot.answer_callback_query(call.id, "✅ تم مسح كل المحادثات!")
        bot.edit_message_text(
            "🧹 **تم مسح جميع المحادثات!**\n\nاستخدم 'محادثة جديدة' للبدء.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
    
    elif data == "back_main":
        bot.edit_message_text(
            "📋 **القائمة الرئيسية:**",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )

if __name__ == "__main__":
    print("="*60)
    print("🚀 **تشغيل بوت تيليجرام - الإصدار 4.0**")
    print(f"📡 التوكن: {BOT_TOKEN[:20]}...")
    print(f"📢 القناة: {CHANNEL_USERNAME}")
    print("="*60)
    print("\n✅ **المميزات النشطة:**")
    print("✅ ردود متدفقة (Streaming)")
    print("✅ تقسيم تلقائي للرسائل الطويلة")
    print("✅ محادثات متعددة غير محدودة")
    print("✅ حفظ واسترجاع الأسئلة المفضلة")
    print(f"✅ {len(SUPPORTED_MODELS)} نموذج ذكاء اصطناعي")
    print("✅ واجهة أزرار تفاعلية كاملة")
    print("✅ قاعدة بيانات SQLite للحفظ")
    print("✅ إحصائيات شخصية")
    print("✅ اشتراك إجباري للقناة")
    print("="*60)
    print("\n🤖 **النماذج المدعومة:**")
    for name in SUPPORTED_MODELS.values():
        print(f"   • {name}")
    print("="*60)
    print("\n🤖 **البوت جاهز للعمل!**")
    print("💬 افتح تيليجرام وابدأ المحادثة")
    print("⚠️ يجب الاشتراك في القناة أولاً")
    print("="*60 + "\n")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, interval=1)
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(5)
            print("🔄 إعادة التشغيل...")