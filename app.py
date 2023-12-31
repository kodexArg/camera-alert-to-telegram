#!.venv/bin/python
import asyncio
import argparse
import cv2
import os
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes



load_dotenv()
SECS_LAST_MOVEMENT = 2
SECS_LAST_ALERT = 20
SECS_SAVED_VIDEO = 4
DEFAULT_MASK = [120, 255, 700, 500]


class VideoSaverSingleton:
    """Singleton class to handle and allow one video saving at a time."""

    _instance = None
    saving_video = False

    def __init__(self, rtsp_url):
        self.rtsp_url=rtsp_url

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def save_video(self, rtsp_url):
        if VideoSaverSingleton.saving_video:
            print("Video is already being saved. Exiting...")
            return

        VideoSaverSingleton.saving_video = True
        self._save_video_process(rtsp_url)
        VideoSaverSingleton.saving_video = False

    def _save_video_process(self, rtsp_url):
        video_capture = cv2.VideoCapture(rtsp_url)
        if not video_capture.isOpened():
            print("Failed to open video stream")
            return

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = 10.0
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(
            "output.mp4",
            fourcc,
            fps,
            (frame_width, frame_height),
        )

        end_time = datetime.now() + timedelta(seconds=SECS_SAVED_VIDEO)
        while datetime.now() < end_time:
            ret, frame = video_capture.read()
            if ret:
                out.write(frame)
            else:
                print("Failed to capture frame")
                break

        video_capture.release()
        out.release()
        print(f"\033[91m VIDEO SAVED {datetime.now()}\033[0m")

        self._send_video_telegram("output.mp4")


class StatefulTimer:
    """Manage state for actions, implementing a lock mechanism with a delay-based unlock."""

    def __init__(self):
        self.last_access = datetime.now()
        self.locked = False

    def unlock(self):
        self.locked = False
        print("\033[92mTimer unlocked\033[0m")

    def check(self):
        now = datetime.now()
        if not self.locked and self.last_access + timedelta(seconds=SECS_LAST_MOVEMENT) < now:
            self.locked = True
            threading.Timer(5, self.unlock).start()
            return True
        return False


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


def process_frames(video_capture, threshold_area, mask_rect, rtsp_url):
    stateful_timer = StatefulTimer()
    has_frame, _, reference_frame = read_frame(video_capture)

    while has_frame:
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
            if stateful_timer.check():
                print(f"\033[91mAlert recorded at {datetime.now()}\033[0m")
                threading.Thread(target=alert_triggered, args=(rtsp_url,)).start()

        reference_frame = gray_frame.copy()
        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    def _send_video_telegram(self, video_path):
        try:
            token = os.getenv("TOKEN")
            bot = Bot(token)
            chat_id = os.getenv("CHAT_ID")
            bot.send_video(chat_id, video=open(video_path, "rb"))
            print("Video sent successfully")
        except TelegramError as e:
            print(f"Error sending video: {e}")


def alert_triggered(rtsp_url):
    VideoSaverSingleton.get_instance().save_video(rtsp_url)


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=f"Your chat ID is: {chat_id}")


def initialize_telegram_bot():
    async def run_bot():
        token = os.getenv("TOKEN")
        application = Application.builder().token(token).build()
        chat_id_handler = CommandHandler("chatid", chat_id_command)
        application.add_handler(chat_id_handler)
        await application.run_polling()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot())


def main():
    parser = argparse.ArgumentParser(description="Motion Detection in Video Streams")
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        default=os.getenv("RTSP"),
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
        default=DEFAULT_MASK,
        help="Mask coordinates (x1 y1 x2 y2)",
    )
    args = parser.parse_args()

    mask_rect = tuple(args.mask)
    rtsp_url = args.url if args.url else os.getenv("RTSP")
    if not rtsp_url:
        raise ValueError("RTSP URL not found. Ensure your .env file has a valid RTSP variable.")

    cap = cv2.VideoCapture(rtsp_url)
    process_frames(cap, args.threshold, mask_rect, rtsp_url=rtsp_url)
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    bot_thread = threading.Thread(target=initialize_telegram_bot)
    bot_thread.start()
    main()
