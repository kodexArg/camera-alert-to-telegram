from telegram import Bot
from telegram.ext import Application, CommandHandler

class TelegramBot:
    def __init__(self):
        self.token = config["TOKEN"]
        self.app = Application.builder().token(self.token).build()
        self.setup_handlers()

    def setup_handlers(self):
        start_handler = CommandHandler("start", self.start_cmd)
        self.app.add_handler(start_handler)

    async def start_cmd(self, update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your bot.")

    async def run(self):
        await self.app.start_polling()

    def stop(self):
        self.app.stop()


# then call it with:
#     telegram_task = asyncio.create_task(telegram_bot_task())
#     await asyncio.gather(..., telegram_task)