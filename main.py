import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)

users = {}
stock = {10: [], 20: [], 50: []}

def menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 Buy Code", callback_data="buy"))
    markup.add(InlineKeyboardButton("💰 My Points", callback_data="points"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.chat.id
    if uid not in users:
        users[uid] = {"points": 0}
    bot.send_message(uid, "🎉 Welcome To Google Play Code Selling Bot", reply_markup=menu())

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id

    if call.data == "buy":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("₹10", callback_data="buy_10"))
        markup.add(InlineKeyboardButton("₹20", callback_data="buy_20"))
        markup.add(InlineKeyboardButton("₹50", callback_data="buy_50"))
        bot.edit_message_text("Select Code Amount:", uid, call.message.message_id, reply_markup=markup)

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
        bot.send_message(uid, f"✅ Your Google Play Code:\n{code}")

    elif call.data == "points":
        bot.answer_callback_query(call.id)
        bot.send_message(uid, f"💰 Your Points: {users[uid]['points']}")

@bot.message_handler(commands=['addcode'])
def addcode(message):
    if message.chat.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()
        amount = int(parts[1])
        code = parts[2]

        if amount not in stock:
            stock[amount] = []

        stock[amount].append(code)
        bot.send_message(message.chat.id, "✅ Code Added Successfully")
    except:
        bot.send_message(message.chat.id, "Use format:\n/addcode 10 ABCD-1234")

@bot.message_handler(commands=['addpoints'])
def addpoints(message):
    if message.chat.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])

        if user_id not in users:
            users[user_id] = {"points": 0}

        users[user_id]["points"] += amount
        bot.send_message(message.chat.id, "✅ Points Added")
    except:
        bot.send_message(message.chat.id, "Use format:\n/addpoints userID amount")

bot.infinity_polling()
