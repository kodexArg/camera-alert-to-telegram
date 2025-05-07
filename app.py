#!.venv/bin/python
import asyncio
import cv2
import os
import glob
from datetime import datetime, timedelta
from collections import deque
from loguru import logger
from telegram import Update, Bot, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from io import BytesIO
import signal

from config import Config

VIDEO_DIRECTORY = "./videos"

def initialize_processing():
    """Initialize background subtractor and temporal variables."""
    background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=100, detectShadows=True)
    last_motion = last_alert = None
    frame_interval = 1.0 / Config.fps
    return background_subtractor, last_motion, last_alert, frame_interval

def read_frame(video_capture):
    """Read and convert a frame from the video stream."""
    ret, frame = video_capture.read()
    if not ret:
        return False, None, None
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return ret, frame, gray_frame

def draw_mask_and_status(frame, motion_detected, on_alert):
    """Draw mask rectangle and status indicators on the frame."""
    mask_rect = Config.mask
    cv2.rectangle(frame, (mask_rect[0], mask_rect[1]), (mask_rect[2], mask_rect[3]), (255, 255, 255), 1)
    if motion_detected:
        cv2.circle(frame, (15, 20), 7, (255, 255, 255), -1)
    if on_alert:
        cv2.circle(frame, (45, 20), 7, (0, 0, 255), -1)

def display_frame(frame):
    """Display frame in OpenCV window."""
    cv2.imshow("Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        raise InterruptedError("Manual exit requested.")

def draw_motion_rectangles(frame, bounding_boxes):
    """Draw green rectangles on detected motion areas."""
    offset_x, offset_y = Config.mask[0], Config.mask[1]
    for x, y, w, h in bounding_boxes:
        cv2.rectangle(
            frame,
            (x + offset_x, y + offset_y),
            (x + w + offset_x, y + h + offset_y),
            (0, 255, 0),
            2,
        )

def save_video(video_buffer, duration_seconds=None, prefix="motion"):
    """Save video from buffer to disk and manage old files."""
    save_duration = duration_seconds if duration_seconds is not None else Config.video_length_secs

    if not os.path.exists(VIDEO_DIRECTORY):
        os.makedirs(VIDEO_DIRECTORY)

    if not video_buffer:
         logger.error("Video buffer is empty. Cannot save video.")
         return None

    try:
        height, width, _ = video_buffer[-1][1].shape
    except IndexError:
         logger.error("Error accessing last frame from buffer (unexpectedly empty?).")
         return None

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{VIDEO_DIRECTORY}/{prefix}_{timestamp_str}_{save_duration}s.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(filename, fourcc, Config.fps, (width, height))

    save_start_time = datetime.now() - timedelta(seconds=save_duration)
    frames_written = 0
    buffer_copy = list(video_buffer)

    for timestamp, frame in buffer_copy:
        if timestamp >= save_start_time:
            out.write(frame)
            frames_written += 1

    out.release()

    if frames_written == 0:
        logger.warning(f"No frames written for {filename}.")
        try:
            os.remove(filename)
        except OSError:
            pass
        return None

    try:
        existing_videos = glob.glob(f"{VIDEO_DIRECTORY}/*.mp4")
        existing_videos.sort(key=os.path.getctime)
        while len(existing_videos) > Config.max_video_files:
            old_file = existing_videos.pop(0)
            logger.info(f"Video limit ({Config.max_video_files}) reached. Deleting: {old_file}")
            try:
                os.remove(old_file)
            except OSError as e:
                 logger.error(f"Could not delete old video {old_file}: {e}")
    except Exception as e:
        logger.error(f"Error managing old video files: {e}")

    return filename

async def send_video_to_telegram(video_path: str, bot: Bot):
    """Send video to Telegram."""
    if not Config.use_telegram:
        return

    if not video_path or not os.path.exists(video_path):
        logger.error(f"Attempt to send invalid or non-existent video: {video_path}")
        return

    try:
        with open(video_path, "rb") as video_file:
            await bot.send_video(Config.chat_id, video=video_file)
    except Exception as e:
        logger.error(f"Failed to send video {video_path} to Telegram: {e}")

async def send_bot_initialization_message(bot: Bot):
    """Send confirmation message when bot starts."""
    if not Config.use_telegram:
        return
    try:
        await bot.send_message(Config.chat_id, "✅ Surveillance system started and connected.")
    except Exception as e:
        logger.error(f"Could not send initialization message to Telegram: {e}")

async def send_error_alert(bot: Bot, message: str):
    """Send critical error message to Telegram."""
    if not Config.use_telegram:
        return
    try:
        await bot.send_message(Config.chat_id, f"⚠️ CRITICAL ERROR: {message}. System may restart.")
    except Exception as e:
        logger.error(f"Failed to send error alert to Telegram: {e}")

def detect_motion_in_mask(fg_mask):
    """Detect significant contours in mask area."""
    x1, y1, x2, y2 = Config.mask
    cropped_mask = fg_mask[y1:y2, x1:x2]
    dilated = cv2.dilate(cropped_mask, None, iterations=3)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    detected_rectangles = []
    for contour in contours:
        if cv2.contourArea(contour) > Config.sensitivity:
            x, y, w, h = cv2.boundingRect(contour)
            detected_rectangles.append((x, y, w, h))
            motion_detected = True
    return motion_detected, detected_rectangles

def update_motion_frame_count(current_motion_detected, current_count):
    """Update motion frame counter."""
    if current_motion_detected:
        current_count += 1
    else:
        current_count = 0
    is_sustained_motion = current_count >= Config.min_motion_frames
    return current_count, is_sustained_motion

async def process_frame(frame, gray_frame, background_subtractor):
    """Process frame and detect motion."""
    fg_mask = background_subtractor.apply(gray_frame)
    _, binary_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)
    motion_detected, rectangles = detect_motion_in_mask(binary_mask)

    if motion_detected:
        draw_motion_rectangles(frame, rectangles)
        return True
    return False

async def handle_motion_detection(
    motion_detected, video_buffer, last_motion, last_alert, on_alert, motion_frame_count, bot
):
    """Handle alert state based on motion detection."""
    now = datetime.now()
    motion_frame_count, is_sustained_motion = update_motion_frame_count(
        motion_detected, motion_frame_count
    )

    if on_alert:
        time_since_alert_start = now - last_alert
        final_video_duration = timedelta(seconds=Config.video_length_secs)

        if time_since_alert_start >= final_video_duration:
            saved_video_path = save_video(video_buffer, Config.video_length_secs, prefix="motion")
            if saved_video_path:
                await send_video_to_telegram(saved_video_path, bot)
            else:
                logger.error("Failed to save alert video.")
            on_alert = False
            motion_frame_count = 0
            last_alert = now

    if is_sustained_motion and not on_alert:
        min_time_between_alerts = timedelta(seconds=Config.secs_between_alerts)
        can_alert = last_alert is None or (now - last_alert) > min_time_between_alerts

        if can_alert:
            logger.info(f"Sustained motion detected ({motion_frame_count} frames). Starting ALERT.")
            last_alert = now
            on_alert = True

    if motion_detected:
        last_motion = now

    return last_motion, last_alert, on_alert, motion_frame_count

async def process_frames(video_capture, video_buffer, bot):
    """Process frames from video stream."""
    on_alert = False
    current_frame_motion_detected = False
    motion_frame_count = 0
    background_subtractor, last_motion, last_alert, frame_interval = initialize_processing()

    while True:
        try:
            has_frame, frame, gray_frame = read_frame(video_capture)
            if not has_frame:
                logger.warning("Video stream appears to have ended or failed. Exiting loop.")
                break

            now = datetime.now()
            video_buffer.append((now, frame.copy()))

            current_frame_motion_detected = await process_frame(
                frame, gray_frame, background_subtractor
            )

            last_motion, last_alert, on_alert, motion_frame_count = await handle_motion_detection(
                current_frame_motion_detected,
                video_buffer,
                last_motion,
                last_alert,
                on_alert,
                motion_frame_count,
                bot
            )

            if Config.show_video:
                display_frame_copy = frame.copy()
                draw_mask_and_status(display_frame_copy, current_frame_motion_detected, on_alert)
                display_frame(display_frame_copy)

            await asyncio.sleep(frame_interval)

        except InterruptedError:
            logger.info("Manual exit detected from video window.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in processing loop: {e}", exc_info=True)
            await send_error_alert(bot, f"Processing error: {e}")
            break

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with chat info."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    await update.message.reply_html(
        f"Hello {user.mention_html()}!\n"
        f"I am the surveillance bot.\n"
        f"Your chat ID: <code>{chat_id}</code>\n"
        f"Commands: /photo, /clip5, /clip20"
    )

async def handle_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send instant camera photo."""
    video_buffer = context.bot_data.get('video_buffer')

    if not video_buffer:
        logger.warning("Photo request, but video buffer not available.")
        await update.message.reply_text("⚠️ Video buffer not ready yet.")
        return

    try:
        timestamp, recent_frame = video_buffer[-1]
        success, image_buffer = cv2.imencode(".jpg", recent_frame)
        if not success:
            logger.error("Failed to encode image to JPG for /photo.")
            await update.message.reply_text("⚠️ Internal error generating image.")
            return

        image_file = BytesIO(image_buffer)
        filename = f"photo_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        image_file.name = filename

        await update.message.reply_photo(
            photo=InputFile(image_file, filename=filename),
            caption=f"📸 Photo ({timestamp.strftime('%H:%M:%S')})"
        )

    except IndexError:
        logger.warning("Photo request, but buffer appears empty (IndexError).")
        await update.message.reply_text("⚠️ Video buffer is empty.")
    except Exception as e:
        logger.error(f"Error processing /photo command: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Unexpected error generating photo: {e}")

async def send_requested_clip(update: Update, context: ContextTypes.DEFAULT_TYPE, duration_seconds: int):
    """Generate and send video clip of specific duration."""
    video_buffer = context.bot_data.get('video_buffer')

    if not video_buffer:
        logger.warning(f"Clip{duration_seconds} request, but buffer not available.")
        await update.message.reply_text("⚠️ Video buffer not ready.")
        return

    min_frames = Config.fps * duration_seconds
    if len(video_buffer) < min_frames:
         logger.warning(f"Clip{duration_seconds} request, but buffer too short ({len(video_buffer)}/{min_frames} frames).")
         await update.message.reply_text(f"⚠️ Not enough data for a {duration_seconds}s clip.")
         return

    wait_msg = await update.message.reply_text(f"⏳ Generating {duration_seconds} second clip...")

    try:
        video_path = save_video(video_buffer, duration_seconds=duration_seconds, prefix="clip")

        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as video_file:
                height, width, _ = video_buffer[-1][1].shape
                await update.message.reply_video(
                    video=InputFile(video_file, filename=os.path.basename(video_path)),
                    duration=duration_seconds,
                    width=width,
                    height=height
                )
            await wait_msg.delete()
        elif video_path is None:
             logger.warning(f"Failed to save {duration_seconds}s clip (save_video returned None).")
             await wait_msg.edit_text(f"⚠️ Could not save frames for {duration_seconds}s clip.")
        else:
            logger.error(f"Failed to save {duration_seconds}s clip (file not found: {video_path}).")
            await wait_msg.edit_text("⚠️ Internal error saving clip.")

    except Exception as e:
        logger.error(f"Error processing /clip{duration_seconds}: {e}", exc_info=True)
        await wait_msg.edit_text(f"⚠️ Unexpected error generating clip: {e}")

async def handle_clip5_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /clip5 command."""
    await send_requested_clip(update, context, duration_seconds=5)

async def handle_clip20_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /clip20 command."""
    await send_requested_clip(update, context, duration_seconds=20)

async def main():
    """Initialize and run bot and video processing."""
    global app_bot

    buffer_seconds = Config.video_length_secs + Config.secs_between_alerts + 5
    buffer_size = int(Config.fps * buffer_seconds)
    video_buffer = deque(maxlen=buffer_size)

    app_bot = None
    video_capture = None
    active_tasks = []

    while True:
        try:
            video_capture = cv2.VideoCapture(Config.rtsp)
            if not video_capture.isOpened():
                 logger.error("Failed to open RTSP stream. Retrying in 15 seconds...")
                 await asyncio.sleep(15)
                 continue

            logger.info("Camera connection established.")

            bot_instance = None
            if Config.use_telegram:
                logger.info("Initializing Telegram bot...")
                bot_instance = Bot(Config.token)
                app_bot = ApplicationBuilder().token(Config.token).build()
                app_bot.bot_data['video_buffer'] = video_buffer
                app_bot.add_handler(CommandHandler("start", handle_start_command))
                app_bot.add_handler(CommandHandler("photo", handle_photo_command))
                app_bot.add_handler(CommandHandler("clip5", handle_clip5_command))
                app_bot.add_handler(CommandHandler("clip20", handle_clip20_command))

                await app_bot.initialize()
                await app_bot.start()
                polling_task = asyncio.create_task(app_bot.updater.start_polling())
                active_tasks.append(polling_task)
                await send_bot_initialization_message(bot_instance)
            else:
                logger.warning("Telegram integration is disabled.")
                app_bot = None
                bot_instance = None

            processing_task = asyncio.create_task(
                process_frames(video_capture, video_buffer, bot_instance)
            )
            active_tasks.append(processing_task)

            await processing_task
            break

        except Exception as e:
            logger.critical(f"Critical error in main function: {e}. Restarting...", exc_info=True)
            if Config.use_telegram and bot_instance:
                 await send_error_alert(bot_instance, f"Critical error: {e}. Attempting restart.")
            await asyncio.sleep(20)

        finally:
            logger.info("Starting resource cleanup...")
            for task in active_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as task_error:
                         logger.error(f"Error waiting for task {task.get_name()} cancellation: {task_error}")
            active_tasks.clear()

            if video_capture and video_capture.isOpened():
                video_capture.release()
            cv2.destroyAllWindows()

            if app_bot:
                try:
                    if app_bot.updater and app_bot.updater.is_running:
                        await app_bot.updater.stop()
                    await app_bot.stop()
                    await app_bot.shutdown()
                except Exception as bot_shutdown_error:
                    logger.error(f"Error during bot shutdown: {bot_shutdown_error}")
                app_bot = None

            logger.info("Cleanup completed.")

async def signal_handler(sig, frame):
    """Handler for clean shutdown with Ctrl+C."""
    global app_bot
    logger.warning(f"Signal {sig} received. Starting clean shutdown...")
    if app_bot:
        try:
            if app_bot.updater and app_bot.updater.is_running:
                await app_bot.updater.stop()
            await app_bot.shutdown()
        except Exception as e:
            logger.error(f"Error stopping bot in signal_handler: {e}")
    cv2.destroyAllWindows()
    exit(0)

if __name__ == "__main__":
    try:
        Config.load()
        logger.remove()
        log_level = Config.log_level.upper()
        logger.add(lambda msg: print(msg, end=""), level=log_level, format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
        logger.add("surveillance_{time:YYYY-MM-DD}.log", rotation="1 day", retention="7 days", level="INFO", format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}")
        logger.info("--- Script Start ---")
        logger.info(f"Log level configured: {log_level}")
        logger.info(f"Use Telegram: {Config.use_telegram}")
        logger.info(f"Show Video: {Config.show_video}")

        asyncio.run(main())

    except FileNotFoundError:
         print("CRITICAL ERROR: .env or config.py file not found.")
         logger.critical("File .env or config.py not found.")
    except ValueError as ve:
        print(f"CRITICAL ERROR in configuration: {ve}")
        logger.critical(f"Configuration error: {ve}")
    except KeyboardInterrupt:
        logger.info("Script interrupted by user (Ctrl+C).")
    except Exception as e_global:
        print(f"UNEXPECTED CRITICAL ERROR: {e_global}")
        logger.critical(f"Unhandled critical error at entry point: {e_global}", exc_info=True)

    logger.info("--- Script End ---")
