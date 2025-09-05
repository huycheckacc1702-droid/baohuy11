import os
import json
import asyncio
from random import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters
)

# Nếu có keep_alive.py (dùng Replit/Heroku), import:
try:
    from keep_alive import keep_alive
except ImportError:
    def keep_alive():
        pass  # Nếu không có thì bỏ qua

# Lấy token từ biến môi trường
BOT_TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "data.json"
ADMINS_FILE = "admins.json"
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "5736655322"))  # sửa thành ID admin thật

# --------- Helper ---------
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}, "accounts": [], "sold": [], "requests": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def is_admin(user_id):
    try:
        with open(ADMINS_FILE, "r") as f:
            admins = json.load(f)
        return str(user_id) in admins
    except:
        return False

def add_admin(uid: str):
    try:
        with open(ADMINS_FILE, "r") as f:
            admins = json.load(f)
    except:
        admins = []
    if uid not in admins:
        admins.append(uid)
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f, indent=4)

def format_currency(n):
    return f"{n:,}".replace(",", ".")

# --------- USER ---------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 Chào mừng đến với shop acc!\n\n"
        "🛒 Lệnh người dùng:\n"
        "/random - Mua acc random (2.000đ)\n"
        "/myacc - Xem acc đã mua\n"
        "/sodu - Kiểm tra số dư\n"
        "/nap <sotien> - Nạp tiền\n"
        "/top - Xem top người dùng\n"
        "/dice - Game tung xúc xắc\n\n"
        "💳 Sau khi dùng /nap, vui lòng gửi ảnh chuyển khoản."
    )

async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user = data["users"].setdefault(user_id, {"balance": 0, "myacc": []})
    if user["balance"] < 2000:
        await update.message.reply_text("⚠️ Bạn cần ít nhất 2.000đ để mua acc.")
        return
    if not data["accounts"]:
        await update.message.reply_text("⛔ Hiện không còn acc nào.")
        return
    acc = data["accounts"].pop(0)
    user["balance"] -= 2000
    user["myacc"].append(acc)
    data["sold"].append(acc)
    save_data(data)
    await update.message.reply_text(f"✅ Bạn đã mua acc:\n`{acc}`", parse_mode="Markdown")

async def myacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    accs = data["users"].get(user_id, {}).get("myacc", [])
    if not accs:
        await update.message.reply_text("📭 Bạn chưa mua acc nào.")
    else:
        msg = "\n".join([f"{i+1}. `{acc}`" for i, acc in enumerate(accs)])
        await update.message.reply_text(f"📦 Acc đã mua:\n{msg}", parse_mode="Markdown")

async def sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    balance = data["users"].get(user_id, {}).get("balance", 0)
    await update.message.reply_text(f"💰 Số dư của bạn: {format_currency(balance)}đ")

async def nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Dùng đúng cú pháp: /nap <sotien>")
        return
    amount = int(context.args[0])
    if amount < 2000:
        await update.message.reply_text("❌ Số tiền tối thiểu là 2.000đ.")
        return
    context.user_data["pending_nap"] = {
        "amount": amount,
        "timestamp": datetime.now()
    }
    await update.message.reply_text(
        f"💳 Vui lòng chuyển khoản:\n"
        f"- STK: 0971487462\n"
        f"- Ngân hàng: MB Bank\n"
        f"- Nội dung: {user_id}\n"
        f"- Số tiền: {format_currency(amount)}đ\n\n"
        "📸 Sau đó gửi ảnh chuyển khoản. Yêu cầu có hiệu lực trong 20 phút."
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if "pending_nap" not in context.user_data:
        await update.message.reply_text("❌ Bạn cần dùng /nap trước khi gửi ảnh.")
        return
    nap_request = context.user_data["pending_nap"]
    if datetime.now() > nap_request["timestamp"] + timedelta(minutes=20):
        del context.user_data["pending_nap"]
        await update.message.reply_text("❌ Yêu cầu nạp đã hết hạn.")
        return
    amount = nap_request["amount"]
    photo_file_id = update.message.photo[-1].file_id
    request_id = len(data["requests"])
    data["requests"].append({
        "user_id": user_id,
        "amount": amount,
        "photo_file_id": photo_file_id,
        "status": "pending"
    })
    save_data(data)
    del context.user_data["pending_nap"]
    await update.message.reply_text("✅ Đã nhận ảnh. Chờ admin duyệt.")
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton("❌ Hủy", callback_data=f"reject_{request_id}")
        ]
    ])
    caption = f"📥 Yêu cầu nạp từ UID {user_id}\nSố tiền: {format_currency(amount)}đ"
    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo_file_id,
        caption=caption,
        reply_markup=keyboard
    )

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    users = sorted(data["users"].items(), key=lambda x: x[1].get("balance", 0), reverse=True)
    msg = "🏆 TOP người dùng:\n"
    for i, (uid, info) in enumerate(users[:5]):
        msg += f"{i+1}. UID {uid[-5:]} - {format_currency(info['balance'])}đ\n"
    await update.message.reply_text(msg)

# --------- GAME ---------
async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user = data["users"].setdefault(user_id, {"balance": 0, "myacc": []})
    cost = 2000
    if user["balance"] < cost:
        await update.message.reply_text("❌ Bạn cần ít nhất 2.000đ để chơi.")
        return
    user["balance"] -= cost
    save_data(data)
    msg = await update.message.reply_dice(emoji="🎲")
    result = msg.dice.value
    await asyncio.sleep(4)
    reward, text = 0, f"😢 Bạn ra số {result}. Không nhận được gì."
    if result == 6:
        if random() < 0.6:
            reward = 2000
            text = f"🎉 Bạn ra số 6 và nhận {format_currency(reward)}đ!"
        else:
            reward = cost
            text = f"✅ Bạn ra số 6! Hoàn lại {format_currency(reward)}đ."
    elif result == 5:
        reward = 4000
        text = f"🪙 Bạn ra số 5! Nhận {format_currency(reward)}đ."
    elif result == 3:
        reward = 6000
        text = f"🎁 Bạn ra số 3! Nhận {format_currency(reward)}đ (x2)!"
    user["balance"] += reward
    save_data(data)
    await update.message.reply_text(text)

# --------- ADMIN ---------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_caption("❌ Bạn không có quyền.")
        return
    data = load_data()
    action, idx_str = query.data.split("_")
    idx = int(idx_str)
    if idx >= len(data["requests"]):
        await query.edit_message_caption("❌ Yêu cầu không tồn tại.")
        return
    req = data["requests"][idx]
    if req["status"] != "pending":
        await query.edit_message_caption("❌ Yêu cầu đã xử lý.")
        return
    uid, amount = req["user_id"], req["amount"]
    user = data["users"].setdefault(uid, {"balance": 0, "myacc": []})
    if action == "approve":
        user["balance"] += amount
        req["status"] = "approved"
        await query.edit_message_caption(f"✅ Đã duyệt nạp {format_currency(amount)}đ cho UID {uid}.")
        try:
            await context.bot.send_message(chat_id=int(uid),
                text=f"✅ Admin đã duyệt nạp {format_currency(amount)}đ vào tài khoản bạn.")
        except:
            pass
    else:
        req["status"] = "rejected"
        await query.edit_message_caption("❌ Đã từ chối yêu cầu.")
    save_data(data)

async def addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ Dùng: /addacc <tài khoản>")
        return
    acc = " ".join(context.args)
    data = load_data()
    if acc in data["accounts"]:
        await update.message.reply_text("⚠️ Tài khoản đã tồn tại.")
        return
    data["accounts"].append(acc)
    save_data(data)
    await update.message.reply_text(f"✅ Đã thêm acc:\n`{acc}`", parse_mode="Markdown")

async def delacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ Dùng: /delacc <tài khoản>")
        return
    acc = " ".join(context.args)
    data = load_data()
    if acc not in data["accounts"]:
        await update.message.reply_text("⚠️ Tài khoản không tồn tại.")
        return
    data["accounts"].remove(acc)
    save_data(data)
    await update.message.reply_text(f"✅ Đã xoá acc:\n`{acc}`", parse_mode="Markdown")

async def addadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền.")
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Dùng: /addadmin <uid>")
        return
    uid = context.args[0]
    add_admin(uid)
    await update.message.reply_text(f"✅ Đã thêm admin UID {uid}")

# --------- MAIN ---------
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("random", random))
    app.add_handler(CommandHandler("myacc", myacc))
    app.add_handler(CommandHandler("sodu", sodu))
    app.add_handler(CommandHandler("nap", nap))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("dice", dice))

    # Admin commands
    app.add_handler(CommandHandler("addacc", addacc))
    app.add_handler(CommandHandler("delacc", delacc))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Photo handler for nạp tiền
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    app.run_polling()
