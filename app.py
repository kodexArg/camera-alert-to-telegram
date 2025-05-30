#!.venv/bin/python
import asyncio
import cv2
import os
import glob
import sys
import traceback
from datetime import datetime, timedelta
from collections import deque
from loguru import logger
from telegram import Update, Bot, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from io import BytesIO
import signal
from config import Config


def ensure_directories_exist():
    directories = [Config.video_directory, Config.motion_pictures_directory]
    
    for directory in directories:
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            
            test_file = os.path.join(directory, ".permissions_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logger.critical(f"Cannot create or write to directory {directory}: {e}")
            raise


def initialize_processing():
    background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=100, detectShadows=True)
    last_motion = last_alert = first_motion_time = last_motion_picture_time = None
    frame_interval = 1.0 / Config.fps
    return background_subtractor, last_motion, last_alert, first_motion_time, last_motion_picture_time, frame_interval


def read_frame(video_capture):
    ret, frame = video_capture.read()
    if not ret:
        return False, None, None
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return ret, frame, gray_frame


def draw_mask_and_status(frame, motion_detected, on_alert):
    mask_rect = Config.mask
    cv2.rectangle(frame, (mask_rect[0], mask_rect[1]), (mask_rect[2], mask_rect[3]), (255, 255, 255), 1)
    if motion_detected:
        cv2.circle(frame, (15, 20), 7, (255, 255, 255), -1)
    if on_alert:
        cv2.circle(frame, (45, 20), 7, (0, 0, 255), -1)


def display_frame(frame):
    cv2.imshow("Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        raise InterruptedError("Manual exit requested.")


def draw_motion_rectangles(frame, bounding_boxes):
    offset_x, offset_y = Config.mask[0], Config.mask[1]
    for x, y, w, h in bounding_boxes:
        cv2.rectangle(
            frame,
            (x + offset_x, y + offset_y),
            (x + w + offset_x, y + h + offset_y),
            (0, 255, 0),
            2,
        )


def save_video(video_buffer, duration_seconds=None, prefix="motion", first_motion_time=None):
    save_duration = duration_seconds if duration_seconds is not None else Config.video_length_secs
    out = None
    
    try:
        if not os.path.exists(Config.video_directory):
            os.makedirs(Config.video_directory)
        
        if not video_buffer:
            logger.error("Video buffer is empty. Cannot save video.")
            return None
        
        try:
            height, width, _ = video_buffer[-1][1].shape
        except IndexError:
            logger.error("Error accessing last frame from buffer (unexpectedly empty?).")
            return None
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Config.video_directory}/{prefix}_{timestamp_str}_{save_duration}s.mp4"
        output_fps = max(1, Config.fps * Config.slow_motion) if Config.slow_motion > 0 else Config.fps
        
        codecs_to_try = ["mp4v", "avc1", "H264", "XVID"]
        out = None
        
        for codec in codecs_to_try:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                test_out = cv2.VideoWriter(filename, fourcc, output_fps, (width, height))
                
                if test_out.isOpened():
                    out = test_out
                    logger.debug(f"Using codec: {codec}")
                    break
                else:
                    test_out.release()
            except Exception as codec_error:
                logger.debug(f"Codec {codec} failed: {codec_error}")
        
        if out is None:
            logger.error("Could not find a suitable codec for video encoding.")
            return None
        
        buffer_copy = list(video_buffer)
        if not buffer_copy:
            logger.error("Buffer became empty during video creation.")
            return None
        
        if first_motion_time and prefix == "motion":
            half_duration = save_duration / 2
            save_start_time = first_motion_time - timedelta(seconds=half_duration)
            save_end_time = first_motion_time + timedelta(seconds=half_duration)
            logger.info(f"Video centered on motion at {first_motion_time.strftime('%H:%M:%S')}")
        else:
            save_start_time = datetime.now() - timedelta(seconds=save_duration)
            save_end_time = datetime.now()
        
        frames_written = 0
        earliest_frame_time = buffer_copy[0][0] if buffer_copy else None
        latest_frame_time = buffer_copy[-1][0] if buffer_copy else None
        
        if earliest_frame_time and latest_frame_time:
            buffer_span = (latest_frame_time - earliest_frame_time).total_seconds()
            logger.debug(f"Buffer spans {buffer_span:.1f}s: {earliest_frame_time.strftime('%H:%M:%S')} - {latest_frame_time.strftime('%H:%M:%S')}")
        
        if earliest_frame_time and save_start_time < earliest_frame_time:
            logger.warning(f"Requested frame time {save_start_time.strftime('%H:%M:%S')} earlier than buffer start {earliest_frame_time.strftime('%H:%M:%S')}")
        
        for timestamp, frame in buffer_copy:
            if save_start_time <= timestamp <= save_end_time:
                out.write(frame)
                frames_written += 1
        
        if frames_written == 0:
            logger.warning(f"No frames written for {filename}.")
            return None
        
        logger.info(f"Saved video with {frames_written} frames.")
        
        try:
            existing_videos = glob.glob(f"{Config.video_directory}/*.mp4")
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
    
    except Exception as e:
        logger.error(f"Error in save_video: {e}", exc_info=True)
        return None
    
    finally:
        if out is not None:
            try:
                out.release()
            except Exception as e:
                logger.error(f"Error releasing VideoWriter: {e}")


async def send_video_to_telegram(video_path: str, bot: Bot):
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
    if not Config.use_telegram:
        return
    
    try:
        await bot.send_message(Config.chat_id, "✅ Surveillance system started and connected.")
    except Exception as e:
        logger.error(f"Could not send initialization message to Telegram: {e}")


async def send_error_alert(bot: Bot, message: str):
    if not Config.use_telegram:
        return
    
    try:
        await bot.send_message(Config.chat_id, f"⚠️ CRITICAL ERROR: {message}. System may restart.")
    except Exception as e:
        logger.error(f"Failed to send error alert to Telegram: {e}")


def detect_motion_in_mask(fg_mask):
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
    if current_motion_detected:
        current_count += 1
    else:
        current_count = 0
    
    is_sustained_motion = current_count >= Config.min_motion_frames
    return current_count, is_sustained_motion


async def process_frame(frame, gray_frame, background_subtractor):
    fg_mask = background_subtractor.apply(gray_frame)
    _, binary_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)
    motion_detected, rectangles = detect_motion_in_mask(binary_mask)
    
    if motion_detected:
        draw_motion_rectangles(frame, rectangles)
        return True
    
    return False


async def handle_motion_detection(
    motion_detected, current_frame, video_buffer, last_motion, last_alert, on_alert, 
    motion_frame_count, bot, last_motion_picture_time=None, first_motion_time=None
):
    now = datetime.now()
    motion_frame_count, is_sustained_motion = update_motion_frame_count(
        motion_detected, motion_frame_count
    )
    
    if motion_detected and not last_motion:
        first_motion_time = now
        logger.debug(f"First motion detected at {first_motion_time.strftime('%H:%M:%S')}")
        
        # Handle motion picture if enabled and cooldown period passed
        if Config.motion_picture and Config.use_telegram:
            can_send_picture = last_motion_picture_time is None or (now - last_motion_picture_time) > timedelta(seconds=Config.motion_picture_cooldown_secs)
            
            if can_send_picture:
                logger.info(f"Motion detected. Sending picture...")
                last_motion_picture_time = now
                
                # Save motion picture
                picture_path = save_motion_picture(current_frame)
                
                # Send motion picture to Telegram
                await send_motion_picture_to_telegram(current_frame, bot)
    
    if on_alert:
        half_duration = Config.video_length_secs / 2
        time_since_first_motion = now - first_motion_time if first_motion_time else timedelta(seconds=0)
        
        if time_since_first_motion >= timedelta(seconds=half_duration):
            saved_video_path = save_video(
                video_buffer,
                Config.video_length_secs,
                prefix="motion",
                first_motion_time=first_motion_time
            )
            
            if saved_video_path:
                await send_video_to_telegram(saved_video_path, bot)
                # Clean up motion pictures after sending video
                cleanup_motion_pictures()
            else:
                logger.error("Failed to save alert video.")
            
            on_alert = False
            motion_frame_count = 0
            last_alert = now
            first_motion_time = None
    
    if is_sustained_motion and not on_alert:
        min_time_between_alerts = timedelta(seconds=Config.secs_between_alerts)
        can_alert = last_alert is None or (now - last_alert) > min_time_between_alerts
        
        if can_alert:
            logger.info(f"Sustained motion detected ({motion_frame_count} frames). Starting ALERT.")
            last_alert = now
            on_alert = True
    
    if motion_detected:
        last_motion = now
    elif last_motion and (now - last_motion) > timedelta(seconds=2):
        last_motion = None
    
    return last_motion, last_alert, on_alert, motion_frame_count, last_motion_picture_time, first_motion_time


async def process_frames(video_capture, video_buffer, bot):
    on_alert = False
    current_frame_motion_detected = False
    motion_frame_count = 0
    background_subtractor, last_motion, last_alert, first_motion_time, last_motion_picture_time, frame_interval = initialize_processing()
    
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
            
            last_motion, last_alert, on_alert, motion_frame_count, last_motion_picture_time, first_motion_time = await handle_motion_detection(
                current_frame_motion_detected,
                frame,
                video_buffer,
                last_motion,
                last_alert,
                on_alert,
                motion_frame_count,
                bot,
                last_motion_picture_time,
                first_motion_time
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
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    await update.message.reply_html(
        f"Hello {user.mention_html()}!\n"
        f"I am the surveillance bot.\n"
        f"Your chat ID: <code>{chat_id}</code>\n"
        f"Commands: /photo, /clip5, /clip20"
    )


async def handle_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            photo=InputFile(image_file, filename=filename)
        )
    except IndexError:
        logger.warning("Photo request, but buffer appears empty (IndexError).")
        await update.message.reply_text("⚠️ Video buffer is empty.")
    except Exception as e:
        logger.error(f"Error processing /photo command: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Unexpected error generating photo: {e}")


async def send_requested_clip(update: Update, context: ContextTypes.DEFAULT_TYPE, duration_seconds: int):
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
                actual_playback_duration = duration_seconds / Config.slow_motion if Config.slow_motion > 0 else duration_seconds
                
                await update.message.reply_video(
                    video=InputFile(video_file, filename=os.path.basename(video_path)),
                    duration=int(round(actual_playback_duration)),
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
    await send_requested_clip(update, context, duration_seconds=5)


async def handle_clip20_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_requested_clip(update, context, duration_seconds=20)


async def send_motion_picture_to_telegram(frame, bot: Bot):
    if not Config.use_telegram or not Config.motion_picture:
        return
    
    try:
        success, image_buffer = cv2.imencode(".jpg", frame)
        
        if not success:
            logger.error("Failed to encode motion image to JPG")
            return
        
        image_file = BytesIO(image_buffer)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"motion_{timestamp_str}.jpg"
        image_file.name = filename
        
        await bot.send_photo(
            chat_id=Config.chat_id,
            photo=InputFile(image_file, filename=filename),
            caption="🚨 Motion detected!"
        )
        logger.info(f"Motion picture sent to Telegram")
    except Exception as e:
        logger.error(f"Failed to send motion picture to Telegram: {e}")


def save_motion_picture(frame):
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{Config.motion_pictures_directory}/motion_{timestamp_str}.jpg"
    
    try:
        if not os.path.exists(Config.motion_pictures_directory):
            os.makedirs(Config.motion_pictures_directory, exist_ok=True)
        
        cv2.imwrite(filename, frame)
        logger.debug(f"Saved motion picture: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving motion picture: {e}")
        return None


def cleanup_motion_pictures():
    try:
        if not os.path.exists(Config.motion_pictures_directory):
            return
        
        motion_pictures = glob.glob(f"{Config.motion_pictures_directory}/*.jpg")
        for picture in motion_pictures:
            try:
                os.remove(picture)
                logger.debug(f"Deleted motion picture: {picture}")
            except OSError as e:
                logger.error(f"Could not delete motion picture {picture}: {e}")
    except Exception as e:
        logger.error(f"Error cleaning up motion pictures: {e}")


async def main():
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
        logger.remove()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(script_dir, "logs")
        
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        console_handler = logger.add(
            lambda msg: print(msg, end=""), 
            level="INFO", 
            format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        file_handler = logger.add(
            os.path.join(logs_dir, "app_{time:YYYY-MM-DD}.log"), 
            rotation="1 day", 
            retention="7 days", 
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            backtrace=True,
            diagnose=True
        )
        
        logger.info("--- Script Start ---")
        
        try:
            Config.load()
            log_level = Config.log_level.upper()
            logger.configure(handlers=[{"sink": lambda msg: print(msg, end=""), "level": log_level}])
            logger.info(f"Console log level configured: {log_level}")
            logger.info(f"File log level: DEBUG")
        except Exception as config_error:
            logger.critical(f"Configuration error: {config_error}", exc_info=True)
            raise
        
        logger.info(f"Use Telegram: {Config.use_telegram}")
        logger.info(f"Show Video: {Config.show_video}")
        
        ensure_directories_exist()
        
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(signal_handler(s, None)))
        
        asyncio.run(main())
        
    except FileNotFoundError as fnf:
        error_msg = f"CRITICAL ERROR: .env or config.py file not found: {fnf}"
        print(error_msg)
        logger.critical(error_msg, exc_info=True)
    except ValueError as ve:
        error_msg = f"CRITICAL ERROR in configuration: {ve}"
        print(error_msg)
        logger.critical(error_msg, exc_info=True)
    except KeyboardInterrupt:
        logger.info("Script interrupted by user (Ctrl+C).")
    except Exception as e_global:
        error_msg = f"UNEXPECTED CRITICAL ERROR: {e_global}"
        print(error_msg)
        logger.critical(error_msg, exc_info=True)
        traceback_str = "".join(traceback.format_exception(type(e_global), e_global, e_global.__traceback__))
        logger.critical(f"Traceback:\n{traceback_str}")
    
    logger.info("--- Script End ---")
