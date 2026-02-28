import os
import re
import time
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberUpdated,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    filters,
)

# =====================
# AYARLAR
# =====================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN eksik! Railway Variables'a ekle.")

LINK_RE = re.compile(r"(https?://|t\.me/|www\.)", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+", re.IGNORECASE)

BAD_WORDS = [
    "porno", "porn", "sex", "nsfw",
    "sik", "siktir", "amk", "aq",
    "orospu", "orospuçocuğu", "piç", "ibne",
    "yarrak", "göt", "fuck",
]

ALLOWED_ADMIN_MENTIONS = {
    # Örnek: "MissRose_bot",
}

FIRST_MUTE_MIN = 5
SECOND_MUTE_MIN = 30
RESET_AFTER_HOURS = 24

OFFENSES = {}

# =====================
# KOMUTLAR
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot aktif.\n\n"
        "!site yazarak siteleri görebilirsin."
    )

async def site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = (
        "✅ Güvenilir sitelerimiz için aşağıdaki linklere tıklayabilirsiniz.\n\n"
        "⚠️ Özelden para isteyenleri dikkate almayın.\n\n"
        "🔽 Önerdiğimiz Siteler 🔽"
    )

    keyboard = [[
        InlineKeyboardButton("Superbetin", url="https://cutt.ly/CtEwy6Xa"),
        InlineKeyboardButton("Ritzbet", url="https://cutt.ly/ritzzayko"),
    ]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with open("site_banner.jpg", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=reply_markup
            )
    except FileNotFoundError:
        await update.message.reply_text(caption, reply_markup=reply_markup)

# =====================
# HOŞ GELDİN (KESİN ÇALIŞAN)
# =====================
def is_user_join(update: ChatMemberUpdated) -> bool:
    old = update.old_chat_member.status
    new = update.new_chat_member.status
    return old in ("left", "kicked") and new in ("member", "restricted")

async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmu = update.chat_member
    if not cmu:
        return

    if cmu.chat.type not in ("group", "supergroup"):
        return

    if not is_user_join(cmu):
        return

    user = cmu.new_chat_member.user
    name = user.full_name or user.first_name or "Üye"

    await context.bot.send_message(
        chat_id=cmu.chat.id,
        text=f"Casino Zayko'ya hoş geldin {name} 👋\nNasılsın? ☺️"
    )

# =====================
# YARDIMCI
# =====================
def contains_bad_word(text: str) -> bool:
    lower = (text or "").lower()
    return any(word in lower for word in BAD_WORDS)

def extract_mentions(text: str):
    return {m[1:] for m in MENTION_RE.findall(text or "")}

def increase_strike(chat_id: int, user_id: int) -> int:
    now = time.time()
    key = (chat_id, user_id)
    record = OFFENSES.get(key)

    if record and (now - record["last"] > RESET_AFTER_HOURS * 3600):
        record = {"count": 0, "last": now}

    if not record:
        record = {"count": 0, "last": now}

    record["count"] += 1
    record["last"] = now
    OFFENSES[key] = record

    return record["count"]

async def punish(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, strike: int):
    if strike == 1:
        until = datetime.now(timezone.utc) + timedelta(minutes=FIRST_MUTE_MIN)
        await context.bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
    elif strike == 2:
        until = datetime.now(timezone.utc) + timedelta(minutes=SECOND_MUTE_MIN)
        await context.bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
    else:
        await context.bot.ban_chat_member(chat_id, user_id)

# =====================
# MODERASYON
# =====================
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user:
        return

    if msg.new_chat_members or msg.left_chat_member:
        return

    text = msg.text or msg.caption or ""

    # Komutları elleme
    lower = text.strip().lower()
    if lower.startswith("/start") or lower.startswith("/site") or lower.startswith("!site"):
        return

    # Adminleri elleme
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except:
        pass

    entities = list(msg.entities or []) + list(msg.caption_entities or [])

    has_link = any(e.type in ("url", "text_link") for e in entities) or bool(LINK_RE.search(text))
    has_mention = any(e.type in ("mention", "text_mention") for e in entities) or bool(MENTION_RE.search(text))
    has_bad = contains_bad_word(text)

    if not (has_link or has_mention or has_bad):
        return

    mentioned = extract_mentions(text)
    if mentioned.intersection(ALLOWED_ADMIN_MENTIONS):
        return

    try:
        await msg.delete()
    except:
        pass

    strike = increase_strike(chat.id, user.id)

    try:
        await punish(chat.id, user.id, context, strike)
    except Exception as e:
        print("Punish error:", e)

# =====================
# MAIN
# =====================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("site", site))
    app.add_handler(MessageHandler(filters.Regex(r"^!site(\s|$)"), site))

    app.add_handler(ChatMemberHandler(welcome_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, moderate))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
