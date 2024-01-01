
# def initialize_telegram_bot():
#     async def run_bot():
#         token = config["TOKEN"]
#         application = Application.builder().token(token).build()
#         chat_id_handler = CommandHandler("chatid", chat_id_command)
#         application.add_handler(chat_id_handler)
#         await application.run_polling()

#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(run_bot())


# async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     chat_id = update.effective_chat.id
#     await context.bot.send_message(chat_id=chat_id, text=f"Your chat ID is: {chat_id}")


    def _send_video_telegram(self, video_path):

        try:
            token = os.getenv("TOKEN")
            bot = Bot(token)
            chat_id = os.getenv("CHAT_ID")
            bot.send_video(chat_id, video=open(video_path, "rb"))
            logger.success("Video sent successfully")
        except TelegramError as e:
            logger.error(f"Error sending video: {e}")