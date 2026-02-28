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

# @ olmadan yaz (örn: @MissRose_bot -> "MissRose_bot")
ALLOWED_ADMIN_MENTIONS = {
    # "MissRose_bot",
}

FIRST_MUTE_MIN = 5
SECOND_MUTE_MIN = 30
RESET_AFTER_HOURS = 24

OFFENSES = {}  # key=(chat_id,user_id) -> {"count": int, "last": epoch}

# =====================
# KOMUTLAR
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif. !site yazarak siteleri görebilirsin.")

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
# HOŞ GELDİN (KESİN YÖNTEM)
# =====================
def _is_join(update: ChatMemberUpdated) -> bool:
    # Üye katıldı mı?
    old = update.old_chat_member.status
    new = update.new_chat_member.status
    # left/kicked -> member gibi geçişler JOIN sayılır
    return old in ("left", "kicked") and new in ("member", "restricted")

async def welcome_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmu: ChatMemberUpdated = update.chat_member
    if not cmu:
        return

    # sadece gruplar
    if cmu.chat.type not in ("group", "supergroup"):
        return

    if not _is_join(cmu):
        return

    user = cmu.new_chat_member.user
    name = user.full_name or user.first_name or "Üye"

    await context.bot.send_message(
        chat_id=cmu.chat.id,
        text=f"Casino Zayko grubumuza hoş geldin {name}"
    )

# =====================
# YARDIMCI FONKSİYONLAR
# =====================
def contains_bad_word(text: str) -> bool:
    lower = (text or "").lower()
    return any(w in lower for w in BAD_WORDS)

def extract_mentions(text: str):
    return {m[1:] for m in MENTION_RE.findall(text or "")}

def inc_offense(chat_id: int, user_id: int) -> int:
    now = time.time()
    key = (chat_id, user_id)
    rec = OFFENSES.get(key)

    if rec and (now - rec["last"] > RESET_AFTER_HOURS * 3600):
        rec = {"count": 0, "last": now}
    if not rec:
        rec = {"count": 0, "last": now}

    rec["count"] += 1
    rec["last"] = now
    OFFENSES[key] = rec
    return rec["count"]

async def punish(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, strike: int):
    if strike == 1:
        until = datetime.now(timezone.utc) + timedelta(minutes=FIRST_MUTE_MIN)
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
    elif strike == 2:
        until = datetime.now(timezone.utc) + timedelta(minutes=SECOND_MUTE_MIN)
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
    else:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)

# =====================
# ANA MODERASYON
# =====================
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user:
        return

    # servis mesajlarını karıştırma
    if msg.new_chat_members or msg.left_chat_member:
        return

    text = msg.text or msg.caption or ""

    # Komutlar / !site vs dokunma
    lower = text.strip().lower()
    if lower.startswith("/start") or lower.startswith("/site") or lower.startswith("!site"):
        return

    # Admin/kurucu asla cezalanmasın
    try:
        sender_member = await context.bot.get_chat_member(chat.id, user.id)
        if sender_member.status in ("administrator", "creator"):
            return
    except:
        pass

    entities = list(msg.entities or []) + list(msg.caption_entities or [])
    has_entity_link = any(e.type in ("url", "text_link") for e in entities)
    has_regex_link = bool(LINK_RE.search(text))

    has_entity_mention = any(e.type in ("mention", "text_mention") for e in entities)
    has_regex_mention = bool(MENTION_RE.search(text))
    has_mention = has_entity_mention or has_regex_mention

    has_bad_word = contains_bad_word(text)

    if not (has_entity_link or has_regex_link or has_mention or has_bad_word):
        return

    # İzinli admin mention varsa affet
    mentioned_usernames = extract_mentions(text)
    if mentioned_usernames.intersection(ALLOWED_ADMIN_MENTIONS):
        return

    # Mesajı sil
    try:
        await msg.delete()
    except:
        pass

    # Ceza: 1=5dk, 2=30dk, 3=ban
    strike = inc_offense(chat.id, user.id)
    try:
        await punish(chat.id, user.id, context, strike)
    except Exception as e:
        print("Punish error:", e)

# =====================
# MAIN
# =====================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Komutlar / !site
    app.add_handler(CommandHandler("start", start), group=0)
    app.add_handler(CommandHandler("site", site), group=0)
    app.add_handler(MessageHandler(filters.Regex(r"^!site(\s|$)"), site), group=0)

    # HOŞ GELDİN (ChatMemberHandler)
    app.add_handler(
        ChatMemberHandler(welcome_chat_member, ChatMemberHandler.CHAT_MEMBER),
        group=0
    )

    # Moderasyon
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, moderate), group=1)

    app.run_polling()

if __name__ == "__main__":
    main()
