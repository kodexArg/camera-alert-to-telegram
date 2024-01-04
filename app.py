#!.venv/bin/python

import asyncio
import argparse
import cv2
import os
import sys
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from loguru import logger
from telegram import Update, ForceReply, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


class Config:
    @staticmethod
    def load():
        load_dotenv()  # .env file required

        return {
            "TOKEN": os.getenv("TOKEN"),
            "CHAT_ID": os.getenv("CHAT_ID"),
            "RTSP": os.getenv("RTSP"),
            "SECS_LAST_MOVEMENT": int(os.getenv("SECS_LAST_MOVEMENT", "0")),
            "SECS_LAST_ALERT": int(os.getenv("SECS_LAST_ALERT", "20")),
            "SECS_SAVED_VIDEO": int(os.getenv("SECS_SAVED_VIDEO", "4")),
            "SECS_UNLOCK_AFTER_ALERT": int(os.getenv("SECS_UNLOCK_AFTER_ALERT", "5")),
            "DEFAULT_MASK": [
                int(os.getenv("DEFAULT_MASK_X1", "120")),
                int(os.getenv("DEFAULT_MASK_Y1", "255")),
                int(os.getenv("DEFAULT_MASK_X2", "700")),
                int(os.getenv("DEFAULT_MASK_Y2", "500")),
            ],
            "LOGGER_LEVEL": os.getenv("LOGGER_LEVEL", "DEBUG"),
            "FPS": int(os.getenv("FPS", 24)),
            "SENSITIVITY": int(os.getenv("SENSITIVITY", 1000)),
        }


class VideoSaverSingleton:
    """Singleton class to handle and allow one video saving at a time."""

    _instance = None
    _lock = threading.Lock()
    saving_video = False

    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url

    @classmethod
    def get_instance(cls, rtsp_url=None):
        with cls._lock:
            """n00b tip: _lock is valid for all instances of this class, ensuring thtat
            only one instance of this code snippet is being evaulated"""
            if cls._instance is None:
                if rtsp_url is None:
                    raise ValueError("RTSP URL is required for the first initialization.")
                cls._instance = cls(rtsp_url)
        return cls._instance

    async def save_video(self, rtsp_url) -> str:
        """Get (then return) the video filename from the private method _save_video_process"""
        if VideoSaverSingleton.saving_video:
            logger.warning("Video is already being saved. Exiting...")
            return

        VideoSaverSingleton.saving_video = True
        try:
            video_filename = await asyncio.to_thread(self._save_video_process, rtsp_url)
        except Exception as e:
            logger.error(f"Error saving video: {e}")
        finally:
            VideoSaverSingleton.saving_video = False
            logger.info("Resetting saving_video flag to False")

        return video_filename

    def _save_video_process(self, rtsp_url) -> str:
        """Returns the video filename"""
        # TODO: cv2.VideoCapture can be asynced? otherwise _save_video_process to sync.
        video_capture = cv2.VideoCapture(rtsp_url)
        if not video_capture.isOpened():
            logger.error("Failed to open video stream")
            raise Exception("Failed to open video stream")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = 10.0
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        video_filename = f"cap_{datetime.now().strftime('%H:%M:%S')}.mp4"
        out = cv2.VideoWriter(
            video_filename,
            fourcc,
            fps,
            (frame_width, frame_height),
        )

        end_time = datetime.now() + timedelta(seconds=config["SECS_SAVED_VIDEO"])
        while datetime.now() < end_time:
            ret, frame = video_capture.read()
            if ret:
                # TODO:
                out.write(frame)
            else:
                logger.error("Failed to capture frame")
                break

        video_capture.release()
        out.release()
        logger.success(f"VIDEO SAVED")

        return video_filename


def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return False, None, None
    return (
        ret,
        frame,
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
    )


def is_motion_detected_with_mask(fg_mask, threshold, mask_rect):
    x1, y1, x2, y2 = mask_rect
    fg_mask_cropped = fg_mask[y1:y2, x1:x2]

    dilated = cv2.dilate(fg_mask_cropped, None, iterations=3)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    bounding_boxes = []
    for contour in contours:
        if cv2.contourArea(contour) > threshold:
            x, y, w, h = cv2.boundingRect(contour)
            bounding_boxes.append((x, y, w, h))
            motion_detected = True

    return motion_detected, bounding_boxes


def draw_motion_boxes(frame, bounding_boxes, mask_rect):
    offset_x, offset_y = mask_rect[0], mask_rect[1]
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
    if cv2.waitKey(1) & 0xFF == ord('q'):
        raise Exception("Quit")


def initialize_processing(args):
    # MOG2
    mog2_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=100, detectShadows=True)
    last_motion_time = last_alert_time = None
    frame_interval = 1.0 / args.FPS
    return mog2_subtractor, last_motion_time, last_alert_time, frame_interval


async def handle_frame_processing(frame, gray_frame, mog2_subtractor, args, mask_rect):
    fg_mask = mog2_subtractor.apply(gray_frame)
    _, fg_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)
    motion_detected, bounding_boxes = is_motion_detected_with_mask(fg_mask, args.threshold, mask_rect)
    if motion_detected:
        draw_motion_boxes(frame, bounding_boxes, mask_rect)
        return True
    return False


async def handle_motion_detection(motion_detected, last_motion_time, last_alert_time, rtsp_url):
    if motion_detected:
        now = datetime.now()
        is_new_motion = last_motion_time is None or now - last_motion_time > timedelta(seconds=config["SECS_LAST_MOVEMENT"])
        is_time_for_alert = last_alert_time is None or now - last_alert_time > timedelta(seconds=config["SECS_LAST_ALERT"])

        if is_new_motion:
            last_motion_time = now
            logger.info("Motion detected")

        if is_time_for_alert and is_new_motion:
            last_alert_time = now
            logger.info("Alert detected")
            await alert_triggered(rtsp_url)

        return last_motion_time, last_alert_time
    return last_motion_time, last_alert_time


async def process_frames(video_capture, args, mask_rect, rtsp_url):
    mog2_subtractor, last_motion_time, last_alert_time, frame_interval = initialize_processing(args)
    logger.debug("Main loop initialized...")

    while True:
        has_frame, frame, gray_frame = read_frame(video_capture)
        if not has_frame:
            break

        try:
            motion_detected = await handle_frame_processing(frame, gray_frame, mog2_subtractor, args, mask_rect)
            last_motion_time, last_alert_time = await handle_motion_detection(motion_detected, last_motion_time, last_alert_time, rtsp_url)

            if args.vid:
                display_frame(frame)

            await asyncio.sleep(frame_interval)
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            break

    video_capture.release()
    cv2.destroyAllWindows()


async def alert_triggered(rtsp_url):
    saved_file_path = await VideoSaverSingleton.get_instance(rtsp_url).save_video(rtsp_url)
    if saved_file_path:
        await send_video_to_telegram(saved_file_path)


async def send_video_to_telegram(video_filename):
    bot = Bot(config["TOKEN"])
    with open(video_filename, "rb") as video_file:
        await bot.send_video(config["CHAT_ID"], video=video_file)


def parse_arguments():
    # TODO: arguments should resemble virtual envs
    parser = argparse.ArgumentParser(description="Motion Detection in Video Streams")
    parser.add_argument(
        "--vid",
        action="store_true",
        help="Display video window if set",
    )
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        default=config["RTSP"],
        help="RTSP URL of the camera",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=int,
        default=config["SENSITIVITY"],
        help="Threshold area for motion detection",
    )
    parser.add_argument(
        "-m",
        "--mask",
        nargs=4,
        type=int,
        default=config["DEFAULT_MASK"],
        help="Mask coordinates (x1 y1 x2 y2)",
    )
    return parser.parse_args()


def config_loader():
    return Config.load()


async def main(args):
    mask_rect = tuple(args.mask)
    rtsp_url = args.url

    VideoSaverSingleton.get_instance(rtsp_url)
    cap = cv2.VideoCapture(rtsp_url)

    logger.debug("Building Bot...")
    bot_app = ApplicationBuilder().token(config["TOKEN"]).build()
    bot_app.add_handler(CommandHandler("start", start))

    await bot_app.initialize()
    await bot_app.start()

    logger.debug("Starting polling...")
    await bot_app.updater.start_polling()

    logger.debug("Processing frames...")
    await process_frames(cap, args, mask_rect, rtsp_url)

    # Clean up for video processing + telegram bot
    logger.debug("releasing and destroying all windows...")
    cap.release()
    cv2.destroyAllWindows()
    await bot_app.updater.stop()
    await bot_app.shutdown()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = update.effective_user
    await update.message.reply_html(f"I see you, {user.mention_html()}.\nYour chat id is {chat_id}.", reply_markup=ForceReply(selective=True))


config = config_loader()
args = parse_arguments()


if __name__ == "__main__":
    logger_level = config["LOGGER_LEVEL"]
    logger.level(logger_level)
    logger.info(f"Initializing with logger level {logger_level}")
    asyncio.run(main(args))
