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

from telegram import Bot
from telegram.ext import Application, CommandHandler

class TelegramBot:
    def __init__(self, token):
        self.app = Application.builder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        start_handler = CommandHandler("start", self.start_cmd)
        echo_handler = CommandHandler("echo", self.echo_cmd)
        self.app.add_handler(start_handler)
        self.app.add_handler(echo_handler)

    async def start_cmd(self, update, context):
        logger.debug(f"started: {context}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot started!")

    async def echo_cmd(self, update, context):
        logger.debug(f"Echo: {context}")
        user_message = update.message.text
        await update.message.reply_text(user_message)

    async def run(self):
        logger.info("Bot initialized")
        await self.app.initialize()
        logger.info("Bot start!")
        await self.app.start()

    def stop(self):
        self.app.stop()




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

    async def save_video(self, rtsp_url):
        if VideoSaverSingleton.saving_video:
            logger.warning("Video is already being saved. Exiting...")
            return

        VideoSaverSingleton.saving_video = True
        try:
            await asyncio.to_thread(self._save_video_process, rtsp_url)
        except Exception as e:
            logger.error(f"Error saving video: {e}")
        finally:
            VideoSaverSingleton.saving_video = False
            logger.info("Resetting saving_video flag to False")

    def _save_video_process(self, rtsp_url):
        # TODO: cv2.VideoCapture can be asynced? otherwise _save_video_process to sync.
        video_capture = cv2.VideoCapture(rtsp_url)
        if not video_capture.isOpened():
            logger.error("Failed to open video stream")
            raise Exception("Failed to open video stream")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = 10.0
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(
            f"output_{datetime.now().strftime('%H:%M:%S')}.mp4",
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


def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return False, None, None
    return (
        ret,
        frame,
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
    )


def is_motion_detected(frame1, frame2, threshold_area, mask_rect):
    x1, y1, x2, y2 = mask_rect
    frame1_masked = frame1[y1:y2, x1:x2]
    frame2_masked = frame2[y1:y2, x1:x2]

    diff = cv2.absdiff(frame1_masked, frame2_masked)
    blur = cv2.GaussianBlur(diff, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
    dilated = cv2.dilate(thresh, None, iterations=3)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    bounding_boxes = []
    for contour in contours:
        if cv2.contourArea(contour) > threshold_area:
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


async def process_frames(video_capture, threshold_area, mask_rect, rtsp_url):
    last_motion_time = None
    last_alert_time = None
    secs_last_movement = config["SECS_LAST_MOVEMENT"]
    secs_last_alert = config["SECS_LAST_ALERT"]

    has_frame, _, reference_frame = read_frame(video_capture)

    logger.debug("Main loop initialized...")

    while has_frame:
        now = datetime.now()
        has_frame, frame, gray_frame = read_frame(video_capture)

        if not has_frame:
            break

        motion_detected, bounding_boxes = is_motion_detected(
            reference_frame,
            gray_frame,
            threshold_area,
            mask_rect,
        )

        cv2.rectangle(
            frame,
            (mask_rect[0], mask_rect[1]),
            (mask_rect[2], mask_rect[3]),
            (255, 255, 255),
            1,
        )

        if motion_detected:
            draw_motion_boxes(frame, bounding_boxes, mask_rect)
            is_new_motion = last_motion_time is None or now - last_motion_time > timedelta(seconds=secs_last_movement)
            is_time_for_alert = last_alert_time is None or now - last_alert_time > timedelta(seconds=secs_last_alert)

            if is_new_motion:
                last_motion_time = now
                logger.info("Motion detected")

            if is_time_for_alert and is_new_motion:
                last_alert_time = now
                logger.info("Alert detected")

                await alert_triggered(rtsp_url)

        reference_frame = gray_frame.copy()  # used in the next comparisson

        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Clean up
    video_capture.release()
    cv2.destroyAllWindows()


async def alert_triggered(rtsp_url):
    # await VideoSaverSingleton.get_instance(rtsp_url).save_video(rtsp_url)
    pass


def parse_arguments():
    parser = argparse.ArgumentParser(description="Motion Detection in Video Streams")
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
        default=1000,
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


async def video_processing_task(args):
    mask_rect = tuple(args.mask)
    rtsp_url = args.url
    cap = cv2.VideoCapture(rtsp_url)
    await process_frames(cap, args.threshold, mask_rect, rtsp_url)
    cap.release()
    cv2.destroyAllWindows()


async def telegram_bot_task():
    logger.debug("TELEGRAM BOT TASK INIT")
    bot = TelegramBot(config["TOKEN"])
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")


async def start_cmd(context, update):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot started!")


async def main(args):
    mask_rect = tuple(args.mask)
    rtsp_url = args.url
    # VideoSaverSingleton.get_instance(rtsp_url)
    # video_task = asyncio.create_task(video_processing_task(args))

    try:
        telegram_task = asyncio.create_task(telegram_bot_task())
        await asyncio.gather(telegram_task)
    finally:
        if not telegram_task.done():
            telegram_task.cancel()
            await telegram_task


    # await asyncio.gather(telegram_task, video_task)


config = config_loader()
args = parse_arguments()

if __name__ == "__main__":
    loglevel = config["LOGGER_LEVEL"]
    logger.level(loglevel)
    logger.info(f"Initializing with logger level {loglevel}")
    asyncio.run(main(args))
