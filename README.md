# Camera Alert to Telegram

A Python-based surveillance system that detects motion in a video stream (e.g., from an IP camera) and sends alerts with video clips via Telegram. This project has been tested and runs effectively on a Raspberry Pi 3.

## Key Features

*   Real-time motion detection within a user-defined mask.
*   Automatic video recording of motion events, with optional slow-motion effect.
*   Instant Telegram alerts with captured video clips.
*   Interactive Telegram bot commands for on-demand photos and video clips.
*   Simple configuration: only sensitive parameters in `.env`, defaults in code.
*   Configuration flexibility via command-line arguments.
*   Manages video storage by deleting older files.

## Quick Start

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd camera-alert-to-telegram
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure:**
    Create a minimal `.env` file in the project root with your sensitive parameters (see example below).
4.  **Run:**
    ```bash
    python app.py
    ```
    For Raspberry Pi, you might use `python3 app.py`.

## Configuration

The application uses a minimal `.env` file for sensitive information and has reasonable defaults for all other parameters.

### Sensitive Parameters (`.env` file)

Create a `.env` file in the root directory with only the following sensitive parameters:

```env
# Camera Stream
RTSP=rtsp://your_camera_ip/stream_path

# Telegram Bot (Required if use_telegram=True)
TOKEN=YOUR_TELEGRAM_BOT_TOKEN
CHAT_ID=YOUR_TELEGRAM_CHAT_ID
```

### Configuration Parameters

All other parameters have default values defined in `config.py` and can be overridden via command-line arguments:

Parameter | Default Value | Command-line Override | Description
--------- | ------------- | --------------------- | -----------
`use_telegram` | `False` | `--use-telegram` | Enable Telegram integration
`max_video_files` | `20` | N/A | Maximum video files to store
`video_length_secs` | `8` | `--video-seconds` | Duration of recorded clips
`detection_seconds` | `2` | `--detection-seconds` | Time threshold for motion detection
`secs_between_alerts` | `8` | `--secs-between-alerts` | Cooldown period between alerts
`sensitivity` | `4000` | `--sensitivity` | Motion detection sensitivity (higher = less sensitive)
`show_video` | `False` | `--show-video` | Display video window
`log_level` | `"INFO"` | `--log-level` | Logging verbosity
`mask` | `[0, 0, 0, 0]` | `--mask` | Detection area: x1 y1 x2 y2
`fps` | `5` | `--fps` | Camera processing frames per second
`min_motion_frames` | `2` | `--min-motion-frames` | Consecutive motion frames to trigger alert
`slow_motion` | `1.0` | `--slow-motion` | Saved video playback speed (1.0 = normal)

Example command with arguments:
```bash
python app.py --use-telegram --video-seconds 15 --sensitivity 5000 --mask 100 100 500 400 --fps 5 --slow-motion 0.5
```

**Important parameters:**

*   `RTSP`: Your camera's RTSP URL (required in `.env` or via `--rtsp`).
*   `fps`: How many frames per second the application processes from the camera. Crucial for performance, especially on devices like Raspberry Pi.
*   `slow_motion`: Factor to control playback speed of saved videos.
*   `mask`: Defines the rectangular area (x1, y1, x2, y2) for motion detection.
*   Other parameters like `video_length_secs`, `secs_between_alerts`, `sensitivity`, `min_motion_frames` allow fine-tuning of the detection and recording behavior.

## Telegram Bot Commands

*   `/start`: Displays a welcome message and chat ID.
*   `/photo`: Captures and sends an instant photo from the camera.
*   `/clip5`: Records and sends a 5-second video clip.
*   `/clip20`: Records and sends a 20-second video clip.

## Dependencies

*   Python 3.x
*   OpenCV (`opencv-python`)
*   python-telegram-bot
*   Loguru
*   python-dotenv


