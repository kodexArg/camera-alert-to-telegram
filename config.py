import os
import argparse
from dotenv import load_dotenv


class Config:
    # Class-level attributes
    rtsp = None
    token = None
    chat_id = None
    use_telegram = None
    max_video_files = None
    video_length_secs = None
    detection_seconds = None
    secs_between_alerts = None
    sensitivity = None
    show_video = None
    log_level = None
    mask = None
    fps = None
    min_motion_frames = None

    @classmethod
    def load(cls):
        load_dotenv()

        # Load from environment variables
        cls.rtsp = os.getenv("RTSP")
        cls.token = os.getenv("TOKEN")
        cls.chat_id = os.getenv("CHAT_ID")
        cls.use_telegram = True if os.getenv("USE_TELEGRAM").lower() == "true" else False
        cls.max_video_files = int(os.getenv("MAX_VIDEO_FILES", 20))
        cls.video_length_secs = int(os.getenv("VIDEO_LENGTH_SECS", 8))
        cls.detection_seconds = int(os.getenv("DETECTION_SECONDS", 2))
        cls.secs_between_alerts = int(os.getenv("SECS_BETWEEN_ALERTS", 8))
        cls.sensitivity = int(os.getenv("SENSITIVITY", 4000))
        cls.show_video =  True if os.getenv("SHOW_VIDEO").lower() == "true" else False
        cls.log_level = os.getenv("LOGGER_LEVEL", "INFO")
        cls.mask = [int(coord.strip()) for coord in os.getenv("MASK", "0, 0, 0, 0").split(",")]
        cls.fps = int(os.getenv("FPS", 5))
        cls.min_motion_frames = int(os.getenv("MIN_MOTION_FRAMES", 2))

        cls.parse_arguments()
        cls.validate_mask(cls)
        cls.validate_telegram_settings()

    @classmethod
    def parse_arguments(cls):
        parser = argparse.ArgumentParser(description="Motion Detection in Video Streams. RTSP URL is required as an argument or environment variable.")
        parser.add_argument("--rtsp", type=str, help="RTSP URL of the camera (required if not set in environment)")
        parser.add_argument("--use-telegram", action="store_true", default=cls.use_telegram, help="Use Telegram integration (requires TOKEN and CHAT_ID in .env)")
        parser.add_argument("--video-seconds", type=int, default=cls.video_length_secs, help="Number of seconds for saved video (minimum 4)")
        parser.add_argument("--detection-seconds", type=int, default=cls.detection_seconds, help="Seconds before triggering an alert (positive values only)")
        parser.add_argument(
            "--secs-between-alerts",
            type=int,
            default=cls.secs_between_alerts,
            help="How many seconds must wait before listening for alerts again. Minimun is --video-seconds + 1 secs.",
        )
        parser.add_argument("--sensitivity", type=int, default=cls.sensitivity, help="Sensitivity for motion detection")
        parser.add_argument("--show-video", action="store_true", help="Display video window if set")
        parser.add_argument("--log-level", type=str, default=cls.log_level, help="Log level (e.g., info, debug)")
        parser.add_argument("--mask", nargs=4, type=int, help="Mask coordinates (x1 y1 x2 y2)")
        parser.add_argument("--fps", type=int, default=cls.fps, help="Frames per Second")
        parser.add_argument("--min-motion-frames", type=int, default=cls.min_motion_frames, help="How many motion detection should occur before considering it a motion")

        args = parser.parse_args()

        # Update class attributes with arguments if provided
        for key, value in vars(args).items():
            if value is not None:
                setattr(cls, key, value)

        # Ensure minimum values for certain config parameters
        cls.video_length_secs = max(cls.video_seconds, 4)
        cls.detection_seconds = max(cls.detection_seconds, 0)
        cls.secs_between_alerts = max(cls.secs_between_alerts, cls.video_length_secs + 1)

        # Ensure RTSP URL is provided
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

