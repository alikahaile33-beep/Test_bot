from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! البوت يعمل الآن.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل /start")

def main():
    TOKEN = "8523151879:AAHfkCf-WBthGgGeihW10RjD1YX58l9pkLc"

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    print("✅ البوت يعمل الآن")
    application.run_polling()

if __name__ == "__main__":
    main()
