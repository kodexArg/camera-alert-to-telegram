import os
import argparse
from dotenv import load_dotenv
from loguru import logger


class Config:
    rtsp = None
    token = None
    chat_id = None

    use_telegram = True
    max_video_files = 20
    video_length_secs = 20
    detection_seconds = 2
    secs_between_alerts = 21
    sensitivity = 3000
    show_video = False
    log_level = "DEBUG"
    mask = [150, 290, 683, 523]
    fps = 5
    min_motion_frames = 2
    slow_motion = 0.75
    motion_picture = True
    motion_picture_cooldown_secs = 5
    video_directory = "./videos"
    motion_pictures_directory = "./motion_pictures"

    @classmethod
    def load(cls):
        load_dotenv()

        env_rtsp = os.getenv("RTSP")
        if env_rtsp is not None:
            cls.rtsp = env_rtsp

        env_token = os.getenv("TOKEN")
        if env_token is not None:
            cls.token = env_token

        env_chat_id = os.getenv("CHAT_ID")
        if env_chat_id is not None:
            cls.chat_id = env_chat_id

        cls.parse_arguments()

        if cls.slow_motion <= 0:
            cls.slow_motion = 1.0
            logger.warning(f"SLOW_MOTION must be a positive value. Reset to {cls.slow_motion}.")

        cls.validate_mask(cls)
        cls.validate_telegram_settings()

    @classmethod
    def parse_arguments(cls):
        parser = argparse.ArgumentParser(description="Motion Detection in Video Streams. RTSP URL is required as an argument or environment variable.")
        
        parser.add_argument("--rtsp", type=str, default=cls.rtsp, help="RTSP URL of the camera (required if not set in environment or via --rtsp)")
        parser.add_argument("--use-telegram", action="store_true", default=cls.use_telegram, help="Use Telegram integration (requires TOKEN and CHAT_ID in .env or arguments)")
        parser.add_argument("--video-seconds", type=int, default=cls.video_length_secs, help="Number of seconds for saved video (minimum 4)")
        parser.add_argument("--detection-seconds", type=int, default=cls.detection_seconds, help="Seconds before triggering an alert (positive values only)")
        parser.add_argument(
            "--secs-between-alerts",
            type=int,
            default=cls.secs_between_alerts,
            help="How many seconds must wait before listening for alerts again. Minimum is --video-seconds + 1 secs.",
        )
        parser.add_argument("--sensitivity", type=int, default=cls.sensitivity, help="Sensitivity for motion detection")
        parser.add_argument("--show-video", action="store_true", default=cls.show_video, help="Display video window if set")
        parser.add_argument("--log-level", type=str, default=cls.log_level, help="Log level (e.g., info, debug)")
        parser.add_argument("--mask", nargs=4, type=int, default=cls.mask, help="Mask coordinates (x1 y1 x2 y2)")
        parser.add_argument("--fps", type=int, default=cls.fps, help="Frames per Second")
        parser.add_argument("--min-motion-frames", type=int, default=cls.min_motion_frames, help="How many motion detection should occur before considering it a motion")
        parser.add_argument("--slow-motion", type=float, default=cls.slow_motion, help="Slow motion factor (e.g., 0.75 for 75% speed, 1.0 for normal speed)")
        parser.add_argument("--motion-picture", action="store_true", default=cls.motion_picture, help="Enable motion picture mode")
        parser.add_argument("--motion-picture-cooldown-secs", type=int, default=cls.motion_picture_cooldown_secs, help="Cooldown time in seconds between motion picture alerts")
        parser.add_argument("--video-directory", type=str, default=cls.video_directory, help="Directory to store recorded videos")
        parser.add_argument("--motion-pictures-directory", type=str, default=cls.motion_pictures_directory, help="Directory to store motion pictures")

        args = parser.parse_args()

        if args.rtsp is not None:
            cls.rtsp = args.rtsp
        
        cls.use_telegram = args.use_telegram
        cls.video_length_secs = args.video_seconds
        cls.detection_seconds = args.detection_seconds
        cls.secs_between_alerts = args.secs_between_alerts
        cls.sensitivity = args.sensitivity
        cls.show_video = args.show_video
        cls.log_level = args.log_level
        cls.mask = args.mask
        cls.fps = args.fps
        cls.min_motion_frames = args.min_motion_frames
        cls.slow_motion = args.slow_motion
        cls.motion_picture = args.motion_picture
        cls.motion_picture_cooldown_secs = args.motion_picture_cooldown_secs
        cls.video_directory = args.video_directory
        cls.motion_pictures_directory = args.motion_pictures_directory

        cls.video_length_secs = max(cls.video_length_secs, 4)
        cls.detection_seconds = max(cls.detection_seconds, 0)
        cls.secs_between_alerts = max(cls.secs_between_alerts, cls.video_length_secs + 1)
        if not cls.rtsp:
            parser.error("RTSP URL is required. Set it as an argument (--rtsp) or as an environment variable (RTSP).")

    def validate_mask(cls):
        if cls.mask is not None:
            if len(cls.mask) != 4:
                raise ValueError(f"Mask must have four coordinates: x1, y1, x2, y2. \nCurrent value: {cls.mask}")

            x1, y1, x2, y2 = cls.mask
            if not all(isinstance(coord, int) for coord in [x1, y1, x2, y2]):
                raise ValueError(f"Mask coordinates must be integers. \nCurrent value: {cls.mask}")

            if x1 >= x2 or y1 >= y2:
                raise ValueError(f"Mask coordinates must satisfy x1 < x2 and y1 < y2. \nCurrent value: {cls.mask}")

            if any(coord < 0 for coord in [x1, y1, x2, y2]):
                raise ValueError(f"Mask coordinates must be positive integers. \nCurrent value: {cls.mask}")

    @classmethod
    def validate_telegram_settings(cls):
        if cls.use_telegram:
            if not cls.token or not cls.chat_id:
                raise ValueError("TOKEN and CHAT_ID must be set when USE_TELEGRAM is True.")

