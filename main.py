import os
import telebot
import random
import string
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)

users = {}
stock = {10: [], 20: [], 50: []}
redeem_codes = {}
pending_payments = {}

def main_menu(uid):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 Buy Code", callback_data="buy"))
    markup.add(InlineKeyboardButton("💰 My Points", callback_data="points"))
    markup.add(InlineKeyboardButton("💳 Buy Points", callback_data="buy_points"))
    markup.add(InlineKeyboardButton("🎁 Redeem Code", callback_data="redeem"))

    if uid == ADMIN_ID:
        markup.add(InlineKeyboardButton("⚙ Admin Panel", callback_data="admin"))

    return markup

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    if uid not in users:
        users[uid] = {"points": 0}
    bot.send_message(uid,
                     "🎉 Welcome To Google Play Code Store\n\nSelect an option 👇",
                     reply_markup=main_menu(uid))

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id

    if call.data == "buy":
        markup = InlineKeyboardMarkup()
        for amount in stock:
            markup.add(
                InlineKeyboardButton(
                    f"₹{amount} (Stock {len(stock[amount])})",
                    callback_data=f"buy_{amount}"
                )
            )
        bot.edit_message_text("Select Amount:", uid, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("buy_"):
        amount = int(call.data.split("_")[1])

        if users[uid]["points"] < amount:
            bot.answer_callback_query(call.id, "❌ Not enough points")
            return

        if len(stock[amount]) == 0:
            bot.answer_callback_query(call.id, "❌ Out of stock")
            return

        code = stock[amount].pop(0)
        users[uid]["points"] -= amount
        bot.send_message(uid, f"✅ Your Code:\n{code}")

    elif call.data == "points":
        bot.answer_callback_query(call.id)
        bot.send_message(uid, f"💰 Your Points: {users[uid]['points']}")

    elif call.data == "buy_points":
        bot.send_message(uid,
                         "📸 Send Payment Screenshot After Paying\n\n(Your QR Here)")
        pending_payments[uid] = True

    elif call.data == "redeem":
        msg = bot.send_message(uid, "Enter redeem code:")
        bot.register_next_step_handler(msg, process_redeem)

    elif call.data == "admin" and uid == ADMIN_ID:
        bot.send_message(uid,
                         "Admin Commands:\n"
                         "/addcode 10 CODE\n"
                         "/stock\n"
                         "/genredeem 400\n"
                         "/approve USER_ID AMOUNT")

def process_redeem(message):
    uid = message.chat.id
    code = message.text.strip()

    if code in redeem_codes:
        amount = redeem_codes.pop(code)
        users[uid]["points"] += amount
        bot.send_message(uid, f"✅ {amount} Points Added")
    else:
        bot.send_message(uid, "❌ Invalid Code")

@bot.message_handler(content_types=['photo'])
def handle_payment(message):
    uid = message.chat.id

    if uid in pending_payments:
        bot.send_message(ADMIN_ID,
                         f"💳 Payment Screenshot from {uid}\n\nApprove using:\n/approve {uid} AMOUNT")
        bot.send_message(uid, "⏳ Waiting for admin approval")
        del pending_payments[uid]

@bot.message_handler(commands=['approve'])
def approve_payment(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = int(amount)

        if user_id not in users:
            users[user_id] = {"points": 0}

        users[user_id]["points"] += amount

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
        stock[amount].append(code)
        bot.send_message(message.chat.id, "✅ Code Added")
    except:
        bot.send_message(message.chat.id, "Use:\n/addcode 10 ABCD-1234")

@bot.message_handler(commands=['stock'])
def stock_check(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = "📦 Stock:\n"
    for amount in stock:
        msg += f"₹{amount} = {len(stock[amount])}\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=['genredeem'])
def generate_redeem(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, amount = message.text.split()
        amount = int(amount)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        redeem_codes[code] = amount
        bot.send_message(message.chat.id,
                         f"🎁 Redeem Code:\n{code}\nAmount: {amount}")
    except:
        bot.send_message(message.chat.id, "Use:\n/genredeem 400")

bot.infinity_polling()
