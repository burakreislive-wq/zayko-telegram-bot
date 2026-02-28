import os
import re
from datetime import datetime, timedelta, timezone

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN eksik! Railway Variables'a ekle.")

LINK_RE = re.compile(r"(https?://|t\.me/|www\.)", re.IGNORECASE)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif. !site yazarak siteleri görebilirsin.")


async def site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = (
        "✅ Güvenilir sitelerimiz için aşağıdaki linklere tıklayabilirsiniz.\n\n"
        "⚠️ Özelden para isteyen, bonus eklemek isteyenleri dikkate almayın.\n"
        "📩 !mod yazarak bize ulaşabilirsiniz.\n\n"
        "🔽 Önerdiğimiz Siteler 🔽"
    )

    keyboard = [[
        InlineKeyboardButton("Superbetin", url="https://cutt.ly/CtEwy6Xa"),
        InlineKeyboardButton("Ritzbet", url="https://cutt.ly/ritzzayko"),
    ]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    with open("site_banner.jpg", "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup
        )


async def mute_on_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user:
        return

    text = msg.text or msg.caption or ""
    entities = list(msg.entities or []) + list(msg.caption_entities or [])

    has_entity_link = any(e.type in ("url", "text_link") for e in entities)
    has_regex_link = bool(LINK_RE.search(text))

    if not (has_entity_link or has_regex_link):
        return

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except:
        pass

    try:
        await msg.delete()
    except:
        pass

    until = datetime.now(timezone.utc) + timedelta(minutes=5)

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
    except Exception as e:
        print("Mute error:", e)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("site", site))
    app.add_handler(MessageHandler(filters.Regex(r"^!site"), site))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, mute_on_link))

    app.run_polling()


if __name__ == "__main__":
    main()
