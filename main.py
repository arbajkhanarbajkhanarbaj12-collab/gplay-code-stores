import os
import telebot
import random
import string
import sqlite3
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ----------------- ENV -----------------
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)

# ----------------- DATABASE -----------------
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0
)''')

# Stock table
c.execute('''CREATE TABLE IF NOT EXISTS stock (
    amount INTEGER,
    code TEXT
)''')

# Redeem codes table
c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes (
    code TEXT,
    amount INTEGER
)''')

# Payments table
c.execute('''CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    amount INTEGER,
    screenshot TEXT,
    utr TEXT,
    status TEXT DEFAULT 'pending',
    request_id TEXT
)''')

# Transactions table
c.execute('''CREATE TABLE IF NOT EXISTS transactions (
    user_id INTEGER,
    type TEXT,
    amount INTEGER,
    code TEXT
)''')

# Referral table
c.execute('''CREATE TABLE IF NOT EXISTS referrals (
    referrer_id INTEGER,
    referred_id INTEGER
)''')

# Daily claims
c.execute('''CREATE TABLE IF NOT EXISTS daily_claims (
    user_id INTEGER,
    last_claim INTEGER
)''')

conn.commit()

# ----------------- MAIN MENU -----------------
def main_menu(uid):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 Buy Code", callback_data="buy"))
    markup.add(InlineKeyboardButton("💳 Buy Points", callback_data="buy_points"))
    markup.add(InlineKeyboardButton("💰 My Points", callback_data="points"))
    markup.add(InlineKeyboardButton("🎁 Redeem Code", callback_data="redeem"))
    markup.add(InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"))
    markup.add(InlineKeyboardButton("🎯 Referral", callback_data="referral"))
    markup.add(InlineKeyboardButton("📅 Daily Bonus", callback_data="daily"))
    if uid == ADMIN_ID:
        markup.add(InlineKeyboardButton("⚙ Admin Panel", callback_data="admin"))
    return markup

# ----------------- UTILS -----------------
def get_points(uid):
    c.execute("SELECT points FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    if row:
        return row[0]
    else:
        c.execute("INSERT INTO users(id, points) VALUES(?,0)", (uid,))
        conn.commit()
        return 0

def add_transaction(uid, t_type, amount, code=None):
    c.execute("INSERT INTO transactions(user_id,type,amount,code) VALUES(?,?,?,?)", (uid,t_type,amount,code))
    conn.commit()

# ----------------- PENDING PAYMENTS -----------------
pending_payments = {}  # uid: {"amount": None, "screenshot": None, "utr": None, "request_id": None}

def generate_request_id():
    return "R" + ''.join(random.choices(string.digits, k=20))

# ----------------- START -----------------
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    get_points(uid)
    bot.send_message(uid, f"🎉 Welcome To World-Class GPlay Code Store (@Buyredeem_bot)\n\nSelect an option 👇",
                     reply_markup=main_menu(uid))

# ----------------- CALLBACK HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id

    if call.data == "buy_points":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Deposited ✅", callback_data="deposit_button"))
        bot.send_message(uid, "💰 UPI Payment Details\n\nAmount: ₹700\nUPI ID: redeemcode@ybl\n\nInstructions:\n1️⃣ Scan QR code OR send ₹700 to above UPI\n2️⃣ After payment, click Deposited ✅ button\n3️⃣ Follow the steps to submit proof",
                         reply_markup=markup)
    elif call.data == "deposit_button":
        amount = 700
        req_id = generate_request_id()
        pending_payments[uid] = {"amount": amount, "screenshot": None, "utr": None, "request_id": req_id}
        bot.send_message(uid, "Step 1️⃣: Enter UTR / Transaction ID:")
    elif call.data == "referral":
        link = f"https://t.me/@Buyredeem_bot?start={uid}"
        bot.send_message(uid,f"🎯 Invite friends using this link:\n{link}\nEarn bonus points when they join!")

# ----------------- HANDLE UTR -----------------
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    uid = message.chat.id
    if uid in pending_payments and pending_payments[uid]["utr"] is None:
        pending_payments[uid]["utr"] = message.text.strip()
        bot.send_message(uid, "✅ UTR Received!\n\nStep 2️⃣: Send Screenshot of Payment (make sure it shows amount, date, UTR)")
    elif uid in pending_payments and pending_payments[uid]["utr"] and pending_payments[uid]["screenshot"] is None:
        bot.send_message(uid, "📸 Please send payment screenshot from your bank app.")
    else:
        pass

# ----------------- PHOTO HANDLER -----------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.chat.id
    if uid in pending_payments and pending_payments[uid]["utr"] and pending_payments[uid]["screenshot"] is None:
        pending_payments[uid]["screenshot"] = message.photo[-1].file_id
        info = pending_payments[uid]
        c.execute("INSERT INTO payments(user_id,amount,screenshot,utr,request_id) VALUES(?,?,?,?,?)",
                  (uid, info["amount"], info["screenshot"], info["utr"], info["request_id"]))
        conn.commit()
        bot.send_message(uid, f"✅ Payment Proof Submitted Successfully!\n\n💰 Amount: ₹{info['amount']}\n🔢 UTR: {info['utr']}\n📸 Screenshot: ✅ Received\n⏳ Status: Admin verification pending\n🆔 Request ID: `{info['request_id']}`", parse_mode="Markdown")
        bot.send_photo(ADMIN_ID, info["screenshot"],
                       caption=f"💳 Payment from {uid}\nAmount: ₹{info['amount']}\nUTR: {info['utr']}\nRequest ID: {info['request_id']}\nApprove: /approve {uid} {info['amount']}\nReject: /reject {uid}")
        del pending_payments[uid]

# ----------------- ADMIN COMMANDS -----------------
@bot.message_handler(commands=['approve'])
def approve_payment(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = int(amount)
        c.execute("UPDATE users SET points=points+? WHERE id=?", (amount, user_id))
        c.execute("UPDATE payments SET status='approved' WHERE user_id=? AND amount=? AND status='pending'", (user_id, amount))
        add_transaction(user_id, "buy_points", amount)
        conn.commit()
        bot.send_message(user_id, f"✅ {amount} Points Approved & Added")
        bot.send_message(message.chat.id, "✅ Payment Approved")
    except:
        bot.send_message(message.chat.id, "Use: /approve USER_ID AMOUNT")

@bot.message_handler(commands=['reject'])
def reject_payment(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, user_id = message.text.split()
        user_id = int(user_id)
        c.execute("UPDATE payments SET status='rejected' WHERE user_id=? AND status='pending'", (user_id,))
        conn.commit()
        bot.send_message(user_id,"❌ Your payment was rejected by admin.")
        bot.send_message(message.chat.id,"✅ Payment Rejected")
    except:
        bot.send_message(message.chat.id, "Use: /reject USER_ID")

# ----------------- RUN BOT -----------------
bot.infinity_polling()
