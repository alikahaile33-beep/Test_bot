import telebot
import json
import os
import threading
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== قراءة المتغيرات البيئية من Render =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))

# التحقق من وجود المتغيرات
if not BOT_TOKEN or not CHANNEL_USERNAME or not ADMIN_ID:
    raise ValueError("❌ المتغيرات البيئية غير مكتملة! تأكد من تعيين BOT_TOKEN, CHANNEL_USERNAME, ADMIN_ID")

bot = telebot.TeleBot(BOT_TOKEN)

# ===== التعامل مع ملف البيانات =====
DATA_FILE = "data.json"
data_lock = threading.Lock()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "withdraw_requests": []}

def save_data(data):
    try:
        with data_lock:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ فشل حفظ البيانات: {e}")

data = load_data()

# ===== دوال مساعدة =====
def get_user(user_id):
    user_id = str(user_id)
    if user_id not in data["users"]:
        data["users"][user_id] = {"balance": 0, "referrals": [], "referred_by": None}
        save_data(data)
    return data["users"][user_id]

def update_user(user_id, field, value):
    user_id = str(user_id)
    data["users"][user_id][field] = value
    save_data(data)

# ===== التحقق من الاشتراك بالقناة =====
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"⚠️ خطأ في التحقق من الاشتراك للمستخدم {user_id}: {e}")
        return False

# ===== أمر /start =====
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        # التحقق من الإحالة (إن وجدت)
        args = message.text.split()
        referrer_id = None
        if len(args) > 1 and args[1].startswith("ref_"):
            referrer_id = args[1].replace("ref_", "")
            if referrer_id.isdigit():
                referrer_id = int(referrer_id)
                if referrer_id == user_id:
                    referrer_id = None  # لا يحيل نفسه

        # التحقق من الاشتراك
        if not is_subscribed(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📢 اشترك بالقناة", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
            markup.add(InlineKeyboardButton("✅ تأكد من الاشتراك", callback_data="check_sub"))
            bot.send_message(user_id, "⚠️ يجب الاشتراك بالقناة أولاً:", reply_markup=markup)
            return

        # سجل المستخدم
        user = get_user(user_id)
        if referrer_id and not user.get("referred_by"):
            if str(referrer_id) in data["users"] and referrer_id != user_id:
                # أضف الإحالة للمُحيل
                data["users"][str(referrer_id)]["referrals"].append(user_id)
                data["users"][str(referrer_id)]["balance"] += 1
                user["referred_by"] = referrer_id
                save_data(data)
                bot.send_message(referrer_id, f"🎉 تمت إحالة جديدة! رصيدك الآن {data['users'][str(referrer_id)]['balance']} ⭐")

        bot.send_message(user_id, f"مرحباً {message.from_user.first_name}!\n"
                                  f"رصيدك: {user['balance']} ⭐\n"
                                  f"عدد الإحالات: {len(user['referrals'])}\n\n"
                                  "📌 استخدم الأوامر التالية:\n"
                                  "/refer - رابط الإحالة الخاص بك\n"
                                  "/myreferrals - قائمة المحالين\n"
                                  "/withdraw - طلب سحب (يلزم 5 نجوم)")
    except Exception as e:
        print(f"⚠️ خطأ في start: {e}")
        bot.send_message(message.chat.id, "حدث خطأ، حاول مجدداً.")

# ===== زر تأكيد الاشتراك =====
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    try:
        user_id = call.from_user.id
        if is_subscribed(user_id):
            bot.delete_message(user_id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك بعد، اشترك ثم اضغط تأكد", show_alert=True)
    except Exception as e:
        print(f"⚠️ خطأ في callback: {e}")

# ===== أمر الإحالة =====
@bot.message_handler(commands=['refer'])
def refer(message):
    try:
        user_id = message.from_user.id
        if not is_subscribed(user_id):
            bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
            return
        user = get_user(user_id)
        ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
        bot.send_message(user_id, f"🔗 رابط إحالتك:\n{ref_link}\n\nشاركه مع أصدقائك، كل مشترك عبره يكسبك نجمة ⭐.")
    except Exception as e:
        print(f"⚠️ خطأ في refer: {e}")

# ===== قائمة المحالين =====
@bot.message_handler(commands=['myreferrals'])
def my_referrals(message):
    try:
        user_id = message.from_user.id
        if not is_subscribed(user_id):
            bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
            return
        user = get_user(user_id)
        refs = user.get("referrals", [])
        if not refs:
            bot.send_message(user_id, "📭 لا يوجد إحالات حتى الآن.")
            return
        names = []
        for uid in refs[:20]:
            try:
                u = bot.get_chat(uid)
                names.append(f"- {u.first_name}")
            except:
                names.append(f"- مستخدم {uid}")
        bot.send_message(user_id, "📋 قائمة المحالين:\n" + "\n".join(names))
    except Exception as e:
        print(f"⚠️ خطأ في myreferrals: {e}")

# ===== طلب السحب =====
@bot.message_handler(commands=['withdraw'])
def withdraw(message):
    try:
        user_id = message.from_user.id
        if not is_subscribed(user_id):
            bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
            return
        user = get_user(user_id)
        balance = user["balance"]
        if balance < 5:
            bot.send_message(user_id, f"❌ رصيدك {balance} ⭐، تحتاج 5 نجوم على الأقل للسحب.")
            return
        request = {
            "user_id": user_id,
            "username": message.from_user.username or message.from_user.first_name,
            "balance": balance,
            "stars": balance,
            "date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        data["withdraw_requests"].append(request)
        save_data(data)
        bot.send_message(ADMIN_ID, f"💰 طلب سحب جديد:\nالمستخدم: {request['username']} (ID: {user_id})\nالنجوم: {balance}\nالتاريخ: {request['date']}\nللرد استخدم /approve_withdraw {len(data['withdraw_requests'])-1}")
        bot.send_message(user_id, "✅ تم تقديم طلب السحب، سيتم معالجته يدوياً قريباً.")
    except Exception as e:
        print(f"⚠️ خطأ في withdraw: {e}")

# ===== (للمشرف) الموافقة على السحب =====
@bot.message_handler(commands=['approve_withdraw'])
def approve_withdraw(message):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(ADMIN_ID, "❌ يرجى كتابة رقم الطلب: /approve_withdraw [رقم]")
            return
        idx = int(parts[1])
        if idx < 0 or idx >= len(data["withdraw_requests"]):
            bot.send_message(ADMIN_ID, "❌ رقم الطلب غير صحيح.")
            return
        request = data["withdraw_requests"][idx]
        user_id = request["user_id"]
        data["users"][str(user_id)]["balance"] = 0
        data["withdraw_requests"].pop(idx)
        save_data(data)
        bot.send_message(user_id, "✅ تم صرف رصيدك بنجاح! شكراً لاستخدامك البوت.")
        bot.send_message(ADMIN_ID, f"✅ تمت الموافقة على طلب {request['username']}")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ حدث خطأ: {e}")

# ===== أمر معرفة الرصيد =====
@bot.message_handler(commands=['balance'])
def balance(message):
    try:
        user_id = message.from_user.id
        if not is_subscribed(user_id):
            bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
            return
        user = get_user(user_id)
        bot.send_message(user_id, f"💰 رصيدك الحالي: {user['balance']} ⭐")
    except Exception as e:
        print(f"⚠️ خطأ في balance: {e}")

# ===== تشغيل البوت مع إعادة تشغيل تلقائي =====
if __name__ == "__main__":
    while True:
        try:
            print("🚀 بدء البوت...")
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ حدث خطأ في polling: {e}")
            print("🔄 إعادة التشغيل بعد 5 ثوانٍ...")
            time.sleep(5)
