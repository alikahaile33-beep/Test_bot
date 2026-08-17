import telebot
import json
import os
import threading
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== الإعدادات =====
BOT_TOKEN = "توكن البوت هنا"
CHANNEL_USERNAME = "@قناة_البوت"   # ضع معرف القناة العام (مثل @mychannel)
ADMIN_ID = 123456789               # ضع معرف التلغرام الخاص بك (لإدارة الطلبات)

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
    with data_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

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
    except:
        return False

# ===== أمر /start =====
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    # تحقق من الإحالة (إن وجدت)
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = args[1].replace("ref_", "")
        if referrer_id.isdigit():
            referrer_id = int(referrer_id)
            if referrer_id == user_id:
                referrer_id = None  # لا يحيل نفسه

    # تحقق من الاشتراك
    if not is_subscribed(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 اشترك بالقناة", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
        markup.add(InlineKeyboardButton("✅ تأكد من الاشتراك", callback_data="check_sub"))
        bot.send_message(user_id, "⚠️ يجب الاشتراك بالقناة أولاً:", reply_markup=markup)
        return

    # سجل المستخدم
    user = get_user(user_id)
    if referrer_id and not user.get("referred_by"):
        # تسجيل الإحالة (بشرط أن المُحيل موجود وليس نفسه)
        if str(referrer_id) in data["users"] and referrer_id != user_id:
            # أضف الإحالة للمُحيل
            data["users"][str(referrer_id)]["referrals"].append(user_id)
            # أضف نجمة للمُحيل
            data["users"][str(referrer_id)]["balance"] += 1
            # سجل أن هذا المستخدم تمت إحالته
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

# ===== زر تأكيد الاشتراك =====
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    user_id = call.from_user.id
    if is_subscribed(user_id):
        bot.delete_message(user_id, call.message.message_id)
        start(call.message)  # إعادة تشغيل البوت مع بداية جديدة
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك بعد، اشترك ثم اضغط تأكد", show_alert=True)

# ===== أمر الإحالة =====
@bot.message_handler(commands=['refer'])
def refer(message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
        return
    user = get_user(user_id)
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    bot.send_message(user_id, f"🔗 رابط إحالتك:\n{ref_link}\n\n"
                              f"شاركه مع أصدقائك، كل مشترك عبره يكسبك نجمة ⭐.")

# ===== قائمة المحالين =====
@bot.message_handler(commands=['myreferrals'])
def my_referrals(message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
        return
    user = get_user(user_id)
    refs = user.get("referrals", [])
    if not refs:
        bot.send_message(user_id, "📭 لا يوجد إحالات حتى الآن.")
        return
    # جلب أسماء المحالين
    names = []
    for uid in refs[:20]:  # حد أقصى 20 للعرض
        try:
            u = bot.get_chat(uid)
            names.append(f"- {u.first_name}")
        except:
            names.append(f"- مستخدم {uid}")
    bot.send_message(user_id, "📋 قائمة المحالين:\n" + "\n".join(names))

# ===== طلب السحب =====
@bot.message_handler(commands=['withdraw'])
def withdraw(message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
        return
    user = get_user(user_id)
    balance = user["balance"]
    if balance < 5:
        bot.send_message(user_id, f"❌ رصيدك {balance} ⭐، تحتاج 5 نجوم على الأقل للسحب.")
        return
    # تسجيل طلب السحب
    request = {
        "user_id": user_id,
        "username": message.from_user.username or message.from_user.first_name,
        "balance": balance,
        "stars": balance,  # يمكن تحويلها إلى عملة أخرى حسب رغبتك
        "date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    data["withdraw_requests"].append(request)
    save_data(data)
    # إشعار للمشرف
    bot.send_message(ADMIN_ID, f"💰 طلب سحب جديد:\n"
                               f"المستخدم: {request['username']} (ID: {user_id})\n"
                               f"النجوم: {balance}\n"
                               f"التاريخ: {request['date']}\n"
                               f"للرد استخدم /approve_withdraw {len(data['withdraw_requests'])-1}")
    bot.send_message(user_id, "✅ تم تقديم طلب السحب، سيتم معالجته يدوياً قريباً.")

# ===== (للمشرف) الموافقة على السحب =====
@bot.message_handler(commands=['approve_withdraw'])
def approve_withdraw(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        idx = int(message.text.split()[1])
        request = data["withdraw_requests"][idx]
        user_id = request["user_id"]
        # خصم الرصيد بعد الدفع
        data["users"][str(user_id)]["balance"] = 0
        # حذف الطلب
        data["withdraw_requests"].pop(idx)
        save_data(data)
        bot.send_message(user_id, "✅ تم صرف رصيدك بنجاح! شكراً لاستخدامك البوت.")
        bot.send_message(ADMIN_ID, f"✅ تمت الموافقة على طلب {request['username']}")
    except:
        bot.send_message(ADMIN_ID, "❌ حدث خطأ، تأكد من كتابة الأمر مع رقم الطلب الصحيح.")

# ===== أوامر مساعدة إضافية =====
@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        bot.send_message(user_id, "⚠️ اشترك بالقناة أولاً.")
        return
    user = get_user(user_id)
    bot.send_message(user_id, f"💰 رصيدك الحالي: {user['balance']} ⭐")

# ===== تشغيل البوت =====
if __name__ == "__main__":
    print("🤖 البوت يعمل...")
    bot.infinity_polling()
