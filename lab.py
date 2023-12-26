import os, io
import asyncio
import httpx
from dotenv import load_dotenv
from loguru import logger
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import whisper

load_dotenv()

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    logger.debug(f"Echo message: '{update.message.text}' received from user: {update.effective_user.id} in chat: {update.effective_chat.id}")


async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle received audio."""
    logger.debug(f"Audio message received from user: {update.effective_user.id} in chat: {update.effective_chat.id}")

    audio_file = update.message.audio or update.message.voice  # Get audio from the message

    if audio_file:
        retry = 0
        max_retry = 5
        while retry < max_retry:
            try:
                file = await context.bot.get_file(audio_file.file_id)
                break
            except httpx.ReadTimeout:
                retry += 1
                await asyncio.sleep(5)  # wait for 5 seconds before retrying
        else:  # if it still fails after max_retry attempts, give up
            logger.error("Failed to download file after multiple attempts")
            return

        filepath = os.path.join("audios", f"{audio_file.file_id}.ogg")
        await file.download_to_drive(filepath)  # Using download method here instead of download_to_drive
        logger.debug(f"File {filepath} downloaded")

        model = whisper.load_model("base")

        audio = whisper.load_audio(filepath)
        audio = whisper.pad_or_trim(audio)
        logger.debug("Audio loaded")

        # make log-Mel spectrogram and move to the same device as the model
        mel = whisper.log_mel_spectrogram(audio).to(model.device)

        # decode the audio
        options = whisper.DecodingOptions(fp16=False, language="es")
        result = whisper.decode(model, mel, options)

        await update.message.reply_text(result.text)


def main() -> None:
    application = Application.builder().token(os.getenv("TOKEN")).build()

    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, audio_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.AUDIO & ~filters.VOICE, audio_handler))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
