#!.venv/bin/python
import argparse
import numpy as np
import cv2
import os
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import deque
from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes


rstp: str = ""  # rtsp url in .env
load_dotenv()

SECS_LAST_MOVEMENT = 2  # seconds since the first capture considered an Alert
SECS_LAST_ALERT = 20  # seconds since the last Alert.
SECS_SAVED_VIDEO = 4  # video length
DEFAULT_MASK = [120, 255, 700, 500]


class StatefulTimer:
    def __init__(self):
        self.last_access = datetime.now()
        self.locked = False

    def unlock(self):
        self.locked = False
        print("\033[92mTimer unlocked\033[0m")

    def check(self):
        now = datetime.now()

        if not self.locked and self.last_access + timedelta(seconds=SECS_LAST_MOVEMENT) < now:
            # It's an ALERT!
            self.locked = True
            # Start a timer to set 'locked' to False after 5 seconds
            timer = threading.Timer(5, self.unlock)
            timer.start()
            return True

        return False


def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return False, None, None
    else:
        return ret, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def is_motion_detected(frame1, frame2, threshold_area, mask_rect):
    # detection mask
    x1, y1, x2, y2 = mask_rect
    frame1_masked = frame1[y1:y2, x1:x2]
    frame2_masked = frame2[y1:y2, x1:x2]

    # diff between frames
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

#!.venv/bin/python
import argparse
import numpy as np
import cv2
import os
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import deque
from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes


rstp: str = ""  # rtsp url in .env
load_dotenv()

SECS_LAST_MOVEMENT = 2  # seconds since the first capture considered an Alert
SECS_LAST_ALERT = 20  # seconds since the last Alert.
SECS_SAVED_VIDEO = 4  # video length
DEFAULT_MASK = [120, 255, 700, 500]


class StatefulTimer:
    def __init__(self):
        self.last_access = datetime.now()
        self.locked = False

    def unlock(self):
        self.locked = False
        print("\033[92mTimer unlocked\033[0m")

    def check(self):
        now = datetime.now()

        if not self.locked and self.last_access + timedelta(seconds=SECS_LAST_MOVEMENT) < now:
            # It's an ALERT!
            self.locked = True
            # Start a timer to set 'locked' to False after 5 seconds
            timer = threading.Timer(5, self.unlock)
            timer.start()
            return True

        return False


def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return False, None, None
    else:
        return ret, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def is_motion_detected(frame1, frame2, threshold_area, mask_rect):
    # detection mask
    x1, y1, x2, y2 = mask_rect
    frame1_masked = frame1[y1:y2, x1:x2]
    frame2_masked = frame2[y1:y2, x1:x2]

    # diff between frames
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

        motion_detected, bounding_boxes = is_motion_detected(reference_frame, gray_frame, threshold_area, mask_rect)

        # Draw a white rectangle to visualize the mask area
        cv2.rectangle(
            frame,
            (mask_rect[0], mask_rect[1]),
            (mask_rect[2], mask_rect[3]),
            (255, 255, 255),
            1,
        )

        if motion_detected:
            # print(f"detection: {datetime.now()}")
            draw_motion_boxes(frame, bounding_boxes, mask_rect)

            is_alert = stateful_timer.check()

            if is_alert:
                print(f"\033[91mAlert recorded at {datetime.now()}\033[0m")
                threading.Thread(target=alert_triggered,args=(rtsp_url,),).start()

        reference_frame = gray_frame.copy()

        # Frame display
        cv2.imshow("Frame", frame)

        # Exit pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


class VideoSaverSingleton:
    """
        Ensure only one instance is saving the video
    """
    _instance = None
    saving_video = False

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

        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4 format
        fps = 10.0  # Assuming 20 FPS, adjust as needed
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # video
        out = cv2.VideoWriter('output.mp4', fourcc, fps, (frame_width, frame_height))

        end_time = datetime.now() + timedelta(seconds=SECS_SAVED_VIDEO)

        while datetime.now() < end_time:
            ret, frame = video_capture.read()
            if ret:
                out.write(frame)
            else:
                print("Failed to capture frame")
                break

        # Clear on exit
        video_capture.release()
        out.release()
        print(f"\033[91m VIDEO SAVED {datetime.now()}\033[0m")

        # Telegram
        # self._send_video_telegram('output.mp4')
    
    def _send_video_telegram(self, video_path):
        try:
            token = os.getenv("TOKEN")
            bot = Bot(token)
            chat_id = "YOUR_CHAT_ID"
            bot.send_video(chat_id, video=open(video_path, 'rb'))
            print("Video sent successfully")
        except TelegramError as e:
            print(f"Error sending video: {e}")


def alert_triggered(rtsp_url):
    VideoSaverSingleton.get_instance().save_video(rtsp_url)



def main():
    # Parameters
    parser = argparse.ArgumentParser(description="Motion Detection in Video Streams")
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        default=os.getenv("rstp"),
        help="RTSP URL of the camera including user:password if required",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=int,
        default=1000,
        help="Threshold area for motion detection. Defines the minimum pixel area that changes between frames must cover to be considered motion. Lower value = more sensitive detection.",
    )
    parser.add_argument(
        "-m",
        "--mask",
        nargs=4,
        type=int,
        default=DEFAULT_MASK,
        help="Mask coordinates (x1 y1 x2 y2) for focusing motion detection on a specific area of the frame. Default is '0 400 720 720'.",
    )
    args = parser.parse_args()

    # White square mask where the movement is detected
    mask_rect = tuple(args.mask)

    # Main loop
    cap = cv2.VideoCapture(args.url)
    process_frames(cap, args.threshold, mask_rect, rtsp_url=args.url)

    # End
    cap.release()
    cv2.destroyAllWindows()


    token = os.getenv("TOKEN")
    application = Application.builder().token(token).build()

    # Add a command handler for the /chatid command
    chat_id_handler = CommandHandler("chatid", chat_id_command)
    application.add_handler(chat_id_handler)

    # Existing code to start the bot
    application.run_polling()


def telegram_bot_init():
    token = os.getenv("TOKEN")
    bot = Bot(token)
    return bot
    


if __name__ == "__main__":
    print("Initializing telegram_bot_init thread...")
    telegram_bot_init()
    print("done.")


    print("Initializing main app...")
    main()

def process_frames(video_capture, threshold_area, mask_rect, rtsp_url):
    stateful_timer = StatefulTimer()
    has_frame, _, reference_frame = read_frame(video_capture)

    while has_frame:
        has_frame, frame, gray_frame = read_frame(video_capture)

        if not has_frame:
            break

        motion_detected, bounding_boxes = is_motion_detected(reference_frame, gray_frame, threshold_area, mask_rect)

        # Draw a white rectangle to visualize the mask area
        cv2.rectangle(
            frame,
            (mask_rect[0], mask_rect[1]),
            (mask_rect[2], mask_rect[3]),
            (255, 255, 255),
            1,
        )

        if motion_detected:
            # print(f"detection: {datetime.now()}")
            draw_motion_boxes(frame, bounding_boxes, mask_rect)

            is_alert = stateful_timer.check()

            if is_alert:
                print(f"\033[91mAlert recorded at {datetime.now()}\033[0m")
                threading.Thread(target=alert_triggered,args=(rtsp_url,),).start()

        reference_frame = gray_frame.copy()

        # Frame display
        cv2.imshow("Frame", frame)

        # Exit pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


class VideoSaverSingleton:
    """
        Ensure only one instance is saving the video
    """
    _instance = None
    saving_video = False

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

        # Define the codec and create VideoWriter object
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4 format
        fps = 10.0  # Assuming 20 FPS, adjust as needed
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # video
        out = cv2.VideoWriter('output.mp4', fourcc, fps, (frame_width, frame_height))

        end_time = datetime.now() + timedelta(seconds=SECS_SAVED_VIDEO)

        while datetime.now() < end_time:
            ret, frame = video_capture.read()
            if ret:
                out.write(frame)
            else:
                print("Failed to capture frame")
                break

        # Clear on exit
        video_capture.release()
        out.release()
        print(f"\033[91m VIDEO SAVED {datetime.now()}\033[0m")

        # Telegram
        # self._send_video_telegram('output.mp4')
    
    def _send_video_telegram(self, video_path):
        try:
            token = os.getenv("TOKEN")
            bot = Bot(token)
            chat_id = "YOUR_CHAT_ID"
            bot.send_video(chat_id, video=open(video_path, 'rb'))
            print("Video sent successfully")
        except TelegramError as e:
            print(f"Error sending video: {e}")


def alert_triggered(rtsp_url):
    VideoSaverSingleton.get_instance().save_video(rtsp_url)



def main():
    # Parameters
    parser = argparse.ArgumentParser(description="Motion Detection in Video Streams")
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        default=os.getenv("rstp"),
        help="RTSP URL of the camera including user:password if required",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=int,
        default=1000,
        help="Threshold area for motion detection. Defines the minimum pixel area that changes between frames must cover to be considered motion. Lower value = more sensitive detection.",
    )
    parser.add_argument(
        "-m",
        "--mask",
        nargs=4,
        type=int,
        default=DEFAULT_MASK,
        help="Mask coordinates (x1 y1 x2 y2) for focusing motion detection on a specific area of the frame. Default is '0 400 720 720'.",
    )
    args = parser.parse_args()

    # White square mask where the movement is detected
    mask_rect = tuple(args.mask)

    # Main loop
    cap = cv2.VideoCapture(args.url)
    process_frames(cap, args.threshold, mask_rect, rtsp_url=args.url)

    # End
    cap.release()
    cv2.destroyAllWindows()


    token = os.getenv("TOKEN")
    application = Application.builder().token(token).build()

    # Add a command handler for the /chatid command
    chat_id_handler = CommandHandler("chatid", chat_id_command)
    application.add_handler(chat_id_handler)

    # Existing code to start the bot
    application.run_polling()


def telegram_bot_init():
    token = os.getenv("TOKEN")
    bot = Bot(token)
    return bot
    


if __name__ == "__main__":
    print("Initializing telegram_bot_init thread...")
    telegram_bot_init()
    print("done.")


    print("Initializing main app...")
    main()
