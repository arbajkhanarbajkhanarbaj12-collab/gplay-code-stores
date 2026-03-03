import os
import telebot
import random
import string
import sqlite3
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
    approved INTEGER DEFAULT 0
)''')

# Transactions table
c.execute('''CREATE TABLE IF NOT EXISTS transactions (
    user_id INTEGER,
    type TEXT,
    amount INTEGER,
    code TEXT
)''')

conn.commit()

# ----------------- MAIN MENU -----------------
def main_menu(uid):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 Buy Code", callback_data="buy"))
    markup.add(InlineKeyboardButton("💳 Buy Points", callback_data="buy_points"))
    markup.add(InlineKeyboardButton("💰 My Points", callback_data="points"))
    markup.add(InlineKeyboardButton("🎁 Redeem Code", callback_data="redeem"))
    if uid == ADMIN_ID:
        markup.add(InlineKeyboardButton("⚙ Admin Panel", callback_data="admin"))
    return markup

# ----------------- UTIL FUNCTIONS -----------------
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

# ----------------- HANDLERS -----------------
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    get_points(uid)  # ensure user exists
    bot.send_message(uid, "🎉 Welcome To World-Class GPlay Code Store\n\nSelect an option 👇",
                     reply_markup=main_menu(uid))

# ----------------- CALLBACK HANDLER -----------------
pending_payments = {}

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id

    if call.data == "buy":
        markup = InlineKeyboardMarkup()
        for amount in range(10, 301, 5):  # ₹10 to ₹300 step 5
            c.execute("SELECT COUNT(*) FROM stock WHERE amount=?", (amount,))
            stock_count = c.fetchone()[0]
            markup.add(InlineKeyboardButton(f"₹{amount} (Stock {stock_count})", callback_data=f"buy_{amount}"))
        bot.edit_message_text("Select Amount:", uid, call.message.message_id, reply_markup=markup)

    elif call.data == "buy_points":
        bot.send_message(uid, "📸 Send Payment Screenshot After Paying\n\n(Your QR or UPI ID Here)")
        pending_payments[uid] = True

    elif call.data.startswith("buy_"):
        amount = int(call.data.split("_")[1])
        points = get_points(uid)
        c.execute("SELECT code FROM stock WHERE amount=? LIMIT 1", (amount,))
        row = c.fetchone()
        if points < amount:
            bot.answer_callback_query(call.id, "❌ Not enough points")
            return
        if not row:
            bot.answer_callback_query(call.id, "❌ Out of stock")
            return
        code = row[0]
        # Deduct stock and points
        c.execute("DELETE FROM stock WHERE code=? AND amount=?", (code, amount))
        c.execute("UPDATE users SET points=points-? WHERE id=?", (amount, uid))
        conn.commit()
        bot.send_message(uid, f"✅ Your Code:\n{code}")
        add_transaction(uid, "buy", amount, code)

    elif call.data == "points":
        bot.answer_callback_query(call.id)
        pts = get_points(uid)
        bot.send_message(uid, f"💰 Your Points: {pts}")

    elif call.data == "redeem":
        msg = bot.send_message(uid, "Enter redeem code:")
        bot.register_next_step_handler(msg, process_redeem)

    elif call.data == "admin" and uid == ADMIN_ID:
        bot.send_message(uid,
            "Admin Commands:\n"
            "/addcode 10 CODE\n"
            "/stock\n"
            "/genredeem 400\n"
            "/approve USER_ID AMOUNT\n"
            "/transactions")

# ----------------- REDEEM -----------------
def process_redeem(message):
    uid = message.chat.id
    code = message.text.strip()
    c.execute("SELECT amount FROM redeem_codes WHERE code=?", (code,))
    row = c.fetchone()
    if row:
        amount = row[0]
        c.execute("DELETE FROM redeem_codes WHERE code=?", (code,))
        c.execute("UPDATE users SET points=points+? WHERE id=?", (amount, uid))
        conn.commit()
        bot.send_message(uid, f"✅ {amount} Points Added via Redeem")
        add_transaction(uid, "redeem", amount, code)
    else:
        bot.send_message(uid, "❌ Invalid Redeem Code")

# ----------------- PHOTO HANDLER -----------------
@bot.message_handler(content_types=['photo'])
def handle_payment(message):
    uid = message.chat.id
    if uid in pending_payments:
        bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=f"💳 Payment Screenshot from {uid}\nApprove using:\n/approve {uid} AMOUNT"
        )
        bot.send_message(uid, "⏳ Waiting for admin approval")
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
        c.execute("SELECT points FROM users WHERE id=?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users(id, points) VALUES(?,0)", (user_id,))
        c.execute("UPDATE users SET points=points+? WHERE id=?", (amount, user_id))
        c.execute("INSERT INTO transactions(user_id,type,amount,code) VALUES(?,?,?,?)", (user_id,"buy_points",amount,None))
        conn.commit()
        bot.send_message(user_id, f"✅ {amount} Points Approved & Added")
        bot.send_message(message.chat.id, "✅ Payment Approved")
    except:
        bot.send_message(message.chat.id, "Use:\n/approve USER_ID AMOUNT")

@bot.message_handler(commands=['addcode'])
def addcode(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, amount, code = message.text.split()
        amount = int(amount)
        c.execute("INSERT INTO stock(amount,code) VALUES(?,?)",(amount,code))
        conn.commit()
        bot.send_message(message.chat.id, "✅ Code Added")
    except:
        bot.send_message(message.chat.id, "Use:\n/addcode 10 ABCD-1234")

@bot.message_handler(commands=['stock'])
def stock_check(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = "📦 Stock Status:\n"
    for amount in range(10, 301, 5):
        c.execute("SELECT COUNT(*) FROM stock WHERE amount=?", (amount,))
        count = c.fetchone()[0]
        msg += f"₹{amount} = {count}\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['genredeem'])
def generate_redeem(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, amount = message.text.split()
        amount = int(amount)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c.execute("INSERT INTO redeem_codes(code,amount) VALUES(?,?)",(code,amount))
        conn.commit()
        bot.send_message(message.chat.id,f"🎁 Redeem Code:\n{code}\nAmount: {amount}")
    except:
        bot.send_message(message.chat.id, "Use:\n/genredeem 400")

@bot.message_handler(commands=['transactions'])
def transactions(message):
    if message.chat.id != ADMIN_ID:
        return
    c.execute("SELECT user_id,type,amount,code FROM transactions ORDER BY rowid DESC LIMIT 20")
    rows = c.fetchall()
    msg = "📜 Last 20 Transactions:\n"
    for r in rows:
        msg += f"User:{r[0]} | {r[1]} | {r[2]} | {r[3]}\n"
    bot.send_message(message.chat.id,msg)

# ----------------- RUN BOT -----------------
bot.infinity_polling()
