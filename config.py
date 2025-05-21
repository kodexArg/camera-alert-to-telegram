import os
import argparse
from dotenv import load_dotenv


class Config:
    # Sensibles - se cargan desde .env o argumentos de línea de comandos
    rtsp = None
    token = None
    chat_id = None

    # No sensibles - valores por defecto directos (basados en los defaults originales de os.getenv)
    use_telegram = False
    max_video_files = 20
    video_length_secs = 8
    detection_seconds = 2
    secs_between_alerts = 8
    sensitivity = 4000
    show_video = False
    log_level = "INFO"
    mask = [0, 0, 0, 0]  # Máscara por defecto
    fps = 5
    min_motion_frames = 2
    slow_motion = 1.0
    # video_seconds es un alias para video_length_secs en argparse, se maneja en parse_arguments

    @classmethod
    def load(cls):
        load_dotenv()  # Carga .env para variables sensibles

        # Carga variables sensibles desde el entorno si están presentes
        # Éstas servirán como default para argparse si no se sobrescriben por argumentos
        env_rtsp = os.getenv("RTSP")
        if env_rtsp is not None:
            cls.rtsp = env_rtsp

        env_token = os.getenv("TOKEN")
        if env_token is not None:
            cls.token = env_token

        env_chat_id = os.getenv("CHAT_ID")
        if env_chat_id is not None:
            cls.chat_id = env_chat_id
        
        # Las variables no sensibles ya tienen sus defaults a nivel de clase.
        # argparse usará estos defaults si no se provee un argumento en línea de comandos.

        cls.parse_arguments()  # Aplica argumentos de línea de comandos

        # Valida el factor slow_motion (ya sea el default o el de argparse)
        if cls.slow_motion <= 0:
            raise ValueError("SLOW_MOTION must be a positive value.")

        cls.validate_mask(cls)  # Valida formato y valores de la máscara
        cls.validate_telegram_settings()  # Valida configuración de Telegram si use_telegram es True

    @classmethod
    def parse_arguments(cls):
        parser = argparse.ArgumentParser(description="Motion Detection in Video Streams. RTSP URL is required as an argument or environment variable.")
        
        # Los argumentos usan los atributos de clase actuales como sus valores por defecto
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
        # MAX_VIDEO_FILES no es un argumento, usará el default de la clase.
        # TOKEN y CHAT_ID no son argumentos de línea de comandos (por seguridad), se cargan de .env.

        args = parser.parse_args()

        # Actualiza los atributos de clase con los valores de los argumentos parseados
        # args contiene los valores de la línea de comandos, o los defaults especificados en add_argument
        # (que a su vez provinieron de los atributos de clase actuales).
        
        # Asignaciones directas para claridad y manejo de alias como video_seconds
        if args.rtsp is not None: # Puede ser None si no se dio en arg ni en env
            cls.rtsp = args.rtsp
        
        cls.use_telegram = args.use_telegram
        cls.video_length_secs = args.video_seconds # Mapeo de --video-seconds a cls.video_length_secs
        cls.detection_seconds = args.detection_seconds
        cls.secs_between_alerts = args.secs_between_alerts
        cls.sensitivity = args.sensitivity
        cls.show_video = args.show_video
        cls.log_level = args.log_level
        cls.mask = args.mask
        cls.fps = args.fps
        cls.min_motion_frames = args.min_motion_frames
        cls.slow_motion = args.slow_motion
        
        # Los atributos que no son argumentos de argparse (ej. max_video_files, token, chat_id si no están en .env)
        # retienen sus valores (default de clase o de .env). Token y chat_id se cargaron antes.

        # Asegura valores mínimos para ciertos parámetros de configuración
        cls.video_length_secs = max(cls.video_length_secs, 4)
        cls.detection_seconds = max(cls.detection_seconds, 0)
        cls.secs_between_alerts = max(cls.secs_between_alerts, cls.video_length_secs + 1)

        # Asegura que la URL RTSP esté provista (ya sea desde .env o --rtsp)
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

