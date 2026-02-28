import os
import re
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

LINK_RE = re.compile(r"(https?://|t\.me/|www\.)", re.IGNORECASE)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif. Link atan 5 dakika susturulur.")


async def mute_on_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or not user:
        return

    text = msg.text or msg.caption or ""
    entities = (msg.entities or []) + (msg.caption_entities or [])

    has_entity_link = any(e.type in ("url", "text_link") for e in entities)
    has_regex_link = bool(LINK_RE.search(text))

    if not (has_entity_link or has_regex_link):
        return

    # Adminlara dokunma
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except:
        pass

    # Mesajı sil
    try:
        await msg.delete()
    except:
        pass

    # 5 dakika sustur
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
    app.add_handler(MessageHandler(filters.ALL, mute_on_link))

    app.run_polling()


if __name__ == "__main__":
    main()
