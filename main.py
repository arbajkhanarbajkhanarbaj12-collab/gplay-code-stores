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

# Payments table
c.execute('''CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    points INTEGER,
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
    points INTEGER,
    code TEXT
)''')

# Daily claims
c.execute('''CREATE TABLE IF NOT EXISTS daily_claims (
    user_id INTEGER,
    last_claim INTEGER
)''')

conn.commit()

# ----------------- UTILS -----------------
def get_points(uid):
    c.execute("SELECT points FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    if row:
        return row[0]
    else:
        with conn:
            c.execute("INSERT INTO users(id, points) VALUES(?,0)", (uid,))
        return 0

def add_transaction(uid, t_type, points, code=None):
    with conn:
        c.execute("INSERT INTO transactions(user_id,type,points,code) VALUES(?,?,?,?)", (uid,t_type,points,code))

def generate_request_id():
    return "R" + ''.join(random.choices(string.digits, k=20))

# ----------------- MAIN MENU -----------------
def main_menu(uid):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💳 Buy Points", callback_data="buy_points"))
    markup.add(InlineKeyboardButton("💰 My Points", callback_data="points"))
    markup.add(InlineKeyboardButton("📅 Daily Bonus", callback_data="daily"))
    if uid == ADMIN_ID:
        markup.add(InlineKeyboardButton("⚙ Admin Panel", callback_data="admin"))
    return markup

# ----------------- PENDING PAYMENTS -----------------
pending_payments = {}  # uid: {"points":None,"amount":None,"screenshot":None,"utr":None,"request_id":None}

# ----------------- START -----------------
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    get_points(uid)
    bot.send_message(uid, f"🎉 Welcome To Ultimate Redeem Bot (@Buyredeem_bot)\nSelect an option 👇",
                     reply_markup=main_menu(uid))

# ----------------- CALLBACK HANDLER -----------------
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id

    if call.data == "buy_points":
        msg = bot.send_message(uid, "💰 Enter how many points you want to buy (1 point = ₹1):")
        bot.register_next_step_handler(msg, process_points_amount)

    elif call.data == "points":
        pts = get_points(uid)
        bot.send_message(uid, f"💰 Your Points: {pts}")

    elif call.data == "daily":
        now = int(time.time())
        c.execute("SELECT last_claim FROM daily_claims WHERE user_id=?", (uid,))
        row = c.fetchone()
        if row and now - row[0] < 86400:
            bot.send_message(uid,"❌ You already claimed daily bonus today.")
        else:
            bonus = 50
            with conn:
                c.execute("UPDATE users SET points=points+? WHERE id=?", (bonus,uid))
                if row:
                    c.execute("UPDATE daily_claims SET last_claim=? WHERE user_id=?", (now,uid))
                else:
                    c.execute("INSERT INTO daily_claims(user_id,last_claim) VALUES(?,?)",(uid,now))
            bot.send_message(uid,f"✅ Daily bonus {bonus} points added!")

    elif call.data == "admin" and uid == ADMIN_ID:
        bot.send_message(uid,"Admin commands:\n/approve USER_ID REQUEST_ID\n/reject USER_ID REQUEST_ID\n/transactions")

    elif call.data == "deposit_button":
        if uid in pending_payments:
            bot.send_message(uid,"Step 1️⃣: Enter UTR / Transaction ID:")
        else:
            bot.send_message(uid,"❌ No pending payment. Please enter points first.")

# ----------------- PROCESS POINTS -----------------
def process_points_amount(message):
    uid = message.chat.id
    try:
        points = int(message.text.strip())
        if points <= 0:
            bot.send_message(uid,"❌ Enter a valid number of points")
            return
        amount = points
        req_id = generate_request_id()
        pending_payments[uid] = {"points": points, "amount": amount, "screenshot": None, "utr": None, "request_id": req_id}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Deposited ✅", callback_data="deposit_button"))
        bot.send_message(uid,
                         f"💰 Payment Details\nAmount: ₹{amount}\nUPI ID: redeemcode@ybl\n\nInstructions:\n1️⃣ Scan QR or pay ₹{amount} to above UPI\n2️⃣ Click Deposited ✅ button\n3️⃣ Send UTR & Screenshot",
                         reply_markup=markup)
    except:
        bot.send_message(uid,"❌ Enter a valid number")

# ----------------- HANDLE UTR -----------------
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    uid = message.chat.id
    if uid in pending_payments:
        if pending_payments[uid]["utr"] is None:
            pending_payments[uid]["utr"] = message.text.strip()
            bot.send_message(uid,"✅ UTR Received!\nStep 2️⃣: Send Screenshot of Payment (show amount, date, UTR)")
        elif pending_payments[uid]["screenshot"] is None:
            bot.send_message(uid,"📸 Please send your payment screenshot")

# ----------------- HANDLE SCREENSHOT -----------------
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.chat.id
    if uid in pending_payments and pending_payments[uid]["screenshot"] is None and pending_payments[uid]["utr"]:
        pending_payments[uid]["screenshot"] = message.photo[-1].file_id
        info = pending_payments[uid]
        with conn:
            c.execute("INSERT INTO payments(user_id,points,amount,screenshot,utr,request_id) VALUES(?,?,?,?,?,?)",
                      (uid, info["points"], info["amount"], info["screenshot"], info["utr"], info["request_id"]))
        bot.send_message(uid,
                         f"✅ Payment Proof Submitted!\n💰 Amount: ₹{info['amount']}\nPoints: {info['points']}\n🔢 UTR: {info['utr']}\n📸 Screenshot: ✅ Received\n⏳ Status: Admin verification pending\n🆔 Request ID: `{info['request_id']}`",
                         parse_mode="Markdown")
        bot.send_photo(ADMIN_ID, info["screenshot"],
                       caption=f"💳 Payment from {uid}\nAmount: ₹{info['amount']}\nPoints: {info['points']}\nUTR: {info['utr']}\nRequest ID: {info['request_id']}\nApprove: /approve {uid} {info['request_id']}\nReject: /reject {uid} {info['request_id']}")
        del pending_payments[uid]

# ----------------- ADMIN APPROVE -----------------
@bot.message_handler(commands=['approve'])
def approve_payment(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, user_id, request_id = message.text.split()
        user_id = int(user_id)
        with conn:
            c.execute("SELECT points FROM payments WHERE user_id=? AND request_id=? AND status='pending'", (user_id, request_id))
            row = c.fetchone()
            if not row:
                bot.send_message(message.chat.id,"❌ No pending payment found with this Request ID.")
                return
            points = row[0]
            c.execute("UPDATE users SET points=points+? WHERE id=?", (points, user_id))
            c.execute("UPDATE payments SET status='approved' WHERE user_id=? AND request_id=?", (user_id, request_id))
            add_transaction(user_id,"buy_points",points)
        bot.send_message(user_id,f"✅ {points} Points Approved & Added")
        bot.send_message(message.chat.id,"✅ Payment Approved Successfully")
    except:
        bot.send_message(message.chat.id,"❌ Use: /approve USER_ID REQUEST_ID")

# ----------------- ADMIN REJECT -----------------
@bot.message_handler(commands=['reject'])
def reject_payment(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, user_id, request_id = message.text.split()
        user_id = int(user_id)
        with conn:
            c.execute("UPDATE payments SET status='rejected' WHERE user_id=? AND request_id=? AND status='pending'", (user_id, request_id))
        bot.send_message(user_id,"❌ Your payment was rejected by admin.")
        bot.send_message(message.chat.id,"✅ Payment Rejected")
    except:
        bot.send_message(message.chat.id,"❌ Use: /reject USER_ID REQUEST_ID")

# ----------------- ADMIN TRANSACTIONS -----------------
@bot.message_handler(commands=['transactions'])
def transactions(message):
    if message.chat.id != ADMIN_ID:
        return
    c.execute("SELECT user_id,type,points,code FROM transactions ORDER BY rowid DESC LIMIT 20")
    rows = c.fetchall()
    msg = "📜 Last 20 Transactions:\n"
    for r in rows:
        msg += f"User:{r[0]} | {r[1]} | {r[2]} | {r[3]}\n"
    bot.send_message(message.chat.id,msg)

# ----------------- RUN BOT -----------------
bot.infinity_polling(timeout=60, long_polling_timeout=90, skip_pending=True)
