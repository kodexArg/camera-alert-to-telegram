#!.venv/bin/python
import asyncio
import cv2
import os
import glob
from datetime import datetime, timedelta
from collections import deque
from loguru import logger
from telegram import Update, ForceReply, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import Config


async def process_frames(first_video_capture):
    bot = Bot(Config.token)  # Inicializa el bot al inicio para uso en caso de alertas
    on_alert = False
    motion_detected = False
    motion_frame_count = 0
    mog2_subtractor, last_motion, last_alert, frame_interval, video_buffer = initialize_processing()
    logger.debug("Main loop initialized. Starting...")

    while True:
        try:
            has_frame, frame, gray_frame = read_frame(first_video_capture)
            if not has_frame:
                logger.warning("No more frames to read, exiting...")
                break

            current_time = datetime.now()
            video_buffer.append((current_time, frame))

            draw_white_box_and_status_dots(frame, motion_detected, on_alert)

            if Config.show_video:
                display_frame(frame)

            motion_detected = await handle_frame_processing(frame, gray_frame, mog2_subtractor)

            last_motion, last_alert, on_alert, motion_frame_count = await handle_motion_detection(
                motion_detected, video_buffer, last_motion, last_alert, on_alert, motion_frame_count
            )

            await asyncio.sleep(frame_interval)

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            await send_error_alert(bot, f"Error irrecuperable detectado: {e}. Por favor, reinicie el dispositivo.")
            break  # Salir



def initialize_processing():
    mog2_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=100, detectShadows=True)  # TODO: un-hardcode
    last_motion = last_alert = None
    frame_interval = 1.0 / Config.fps  # fraction of second
    frames_in_cache = Config.fps * Config.video_length_secs + 2  # Arbitrary 10 more frames
    video_buffer = deque(maxlen=frames_in_cache)
    return mog2_subtractor, last_motion, last_alert, frame_interval, video_buffer


def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return False, None, None
    return (ret, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))


def draw_white_box_and_status_dots(frame, motion_detected, on_alert):
    mask_rect = Config.mask
    cv2.rectangle(frame, (mask_rect[0], mask_rect[1]), (mask_rect[2], mask_rect[3]), (255, 255, 255), 1)
    if motion_detected:
        cv2.circle(frame, (10, 10), 5, (255, 255, 255), -1)
    if on_alert:
        cv2.circle(frame, (30, 10), 5, (0, 0, 255), -1)


async def handle_frame_processing(frame, gray_frame, mog2_subtractor):
    fg_mask = mog2_subtractor.apply(gray_frame)
    _, fg_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)

    motion_detected, bounding_boxes = is_motion_detected_with_mask(fg_mask)

    if motion_detected:
        draw_motion_boxes(frame, bounding_boxes)
        return True

    return False


def is_motion_detected_with_mask(fg_mask):
    x1, y1, x2, y2 = Config.mask
    fg_mask_cropped = fg_mask[y1:y2, x1:x2]

    dilated = cv2.dilate(fg_mask_cropped, None, iterations=3)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    bounding_boxes = []
    for contour in contours:
        if cv2.contourArea(contour) > Config.sensitivity:
            x, y, w, h = cv2.boundingRect(contour)
            bounding_boxes.append((x, y, w, h))
            motion_detected = True

    return motion_detected, bounding_boxes


def draw_motion_boxes(frame, bounding_boxes):
    offset_x, offset_y = Config.mask[0], Config.mask[1]
    for x, y, w, h in bounding_boxes:
        cv2.rectangle(
            frame,
            (x + offset_x, y + offset_y),
            (x + w + offset_x, y + h + offset_y),
            (0, 255, 0),
            2,
        )


def display_frame(frame):
    cv2.imshow("Frame", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        raise Exception("Quit")


async def handle_motion_detection(motion_detected, video_buffer, last_motion, last_alert, on_alert, motion_frame_count):
    """Note: detailed and easy to understand explanation can be found in the README.md,
    under the title `Video Capture and Alert Logic`."""

    now = datetime.now()
    motion_frame_count, is_sustained_motion = update_motion_frame_count(motion_detected, motion_frame_count)

    if on_alert:
        secs_in_motion_required = Config.video_length_secs - Config.detection_seconds
        if now - last_alert >= timedelta(seconds=secs_in_motion_required):
            logger.warning("Video Saved")
            await send_video_to_telegram(save_video(video_buffer))
            on_alert = False
            motion_frame_count = 0

    if is_sustained_motion and not on_alert:
        is_time_for_alert = last_alert is None or now - last_alert > timedelta(seconds=Config.secs_between_alerts)
        if is_time_for_alert:
            last_alert = now
            on_alert = True
            motion_frame_count = 0
            logger.info("Alert detected")

    if motion_detected:
        last_motion = now

    return last_motion, last_alert, on_alert, motion_frame_count


def update_motion_frame_count(motion_detected, motion_frame_count):
    if motion_detected:
        motion_frame_count += 1
        logger.debug("Motion detected")
    else:
        motion_frame_count = 0

    is_sustained_motion = motion_frame_count >= Config.min_motion_frames

    return motion_frame_count, is_sustained_motion


def save_video(video_buffer):
    """
    Saves the last 'Config.video_length_secs' seconds of the video buffer to a file on disk and
    deletes the oldest video if the number of video files exceeds the maximum limit in MAX_VIDEO_FILES (default=20).
    """

    if not os.path.exists("./videos"):
        os.makedirs("./videos")

    # Define the codec
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    if video_buffer:
        frame_width = video_buffer[0][1].shape[1]
        frame_height = video_buffer[0][1].shape[0]
    else:
        raise ValueError("Video buffer is empty.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"./videos/cap_{timestamp}.mp4"
    out = cv2.VideoWriter(video_filename, fourcc, Config.fps, (frame_width, frame_height))

    # Saving only `Config.video_length_secs` from video_buffer to disk
    start_time = datetime.now() - timedelta(seconds=Config.video_length_secs)
    for timestamp, frame in video_buffer:
        if timestamp >= start_time:
            out.write(frame)

    out.release()

    # Check and delete the oldest video file if necessary
    video_files = glob.glob("./videos/*.mp4")
    if len(video_files) > Config.max_video_files:
        oldest_file = min(video_files, key=os.path.getctime)
        logger.info(f"Deleting oldest video file: {oldest_file}")
        os.remove(oldest_file)

    return video_filename


async def send_video_to_telegram(video_filename):
    if Config.use_telegram:
        bot = Bot(Config.token)
        with open(video_filename, "rb") as video_file:
            await bot.send_video(Config.chat_id, video=video_file)
    else:
        logger.warning("Telegram bot disabled")


async def send_bot_initialized_message():
    try:
        bot = Bot(Config.token)
        await bot.send_message(Config.chat_id, "Bot successfully initialized and running.")
    except Exception as e:
        logger.error(f"Failed to send initialization message: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    await update.message.reply_html(
        f"I see you, {user.mention_html()}.\nYour chat id is {chat_id}.",
    )


async def main():
    cap = cv2.VideoCapture(Config.rtsp)

    if Config.use_telegram:
        logger.debug("Building Telegram Bot...")
        bot_app = ApplicationBuilder().token(Config.token).build()
        bot_app.add_handler(CommandHandler("start", start))

        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()  # Bot loop
        await send_bot_initialized_message()

    # Main video loop
    logger.debug("Processing frames...")
    await process_frames(cap)

    # Clean up for video processing
    logger.debug("releasing and destroying all windows...")
    cap.release()
    cv2.destroyAllWindows()

    if Config.use_telegram:
        logger.debug("Stopping the bot polling...")
        await bot_app.updater.stop()

        logger.debug("Shutting down the bot...")
        await bot_app.shutdown()
        logger.debug("Bot gracefully shut down.")


async def send_error_alert(bot, message):
    try:
        await bot.send_message(Config.chat_id, message)
    except Exception as e:
        logger.error(f"Failed to send error alert to Telegram: {e}")




Config.load()

if __name__ == "__main__":
    logger.level(Config.log_level)
    logger.info(f"Initializing with logger level {Config.log_level}")
    logger.debug(f"Bot: {Config.use_telegram}")
    asyncio.run(main())
