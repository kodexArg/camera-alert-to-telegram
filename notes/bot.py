import argparse
import asyncio
import os
from dotenv import load_dotenv
from loguru import logger
from telegram import Update, ForceReply, Bot
from telegram.ext import ContextTypes, Application, CommandHandler, Updater


class Config:
    @staticmethod
    def load():
        load_dotenv()  # .env file required

        return {
            "TOKEN": os.getenv("TOKEN"),
        }

def config_loader():
    return Config.load()


def initialize_bot():
    app = Application.builder().token(config["TOKEN"]).build()
    app.add_handler(CommandHandler("start", start, block=False))
    return app


async def telegram_task():
    bot = Bot(config["TOKEN"])
    que = asyncio.Queue()
    updater = Updater(bot,que)

    await updater.initialize()
    await updater.start_polling()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(f"I see you, {user.mention_html()}.", reply_markup=ForceReply(selective=True))


config = config_loader()

if __name__ == "__main__":
    asyncio.run(telegram_task())
