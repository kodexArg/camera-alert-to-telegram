# Camera Alert to Telegram

A Python-based surveillance system that detects motion in a video stream (e.g., from an IP camera) and sends alerts with video clips via Telegram. This project has been tested and runs effectively on a Raspberry Pi 3.

## Key Features

*   Real-time motion detection within a user-defined mask.
*   Automatic video recording of motion events, with optional slow-motion effect.
*   Instant Telegram alerts with captured video clips.
*   Interactive Telegram bot commands for on-demand photos and video clips.
*   Highly configurable via a `.env` file.
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
    Create a `.env` file in the project root (see example below) and populate it with your settings.
4.  **Run:**
    ```bash
    python app.py
    ```
    For Raspberry Pi, you might use `python3 app.py`.

## Configuration (`.env` file)

Create a `.env` file in the root directory to configure the application.

```env
# Camera Stream
RTSP="rtsp://your_camera_ip/stream_path"

# Telegram Bot (Required if USE_TELEGRAM=True)
TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID="YOUR_TELEGRAM_CHAT_ID"

# Core Features
USE_TELEGRAM=True
SHOW_VIDEO=False         # False for headless (e.g., Raspberry Pi)
LOGGER_LEVEL="INFO"      # Logging verbosity

# Video & Motion Settings
FPS=5                    # Camera processing frames per second (adjust for RPi performance)
SLOW_MOTION=1.0          # Saved video playback speed (0.5 = half speed, 1.0 = normal)
VIDEO_LENGTH_SECS=15     # Duration of recorded clips
SECS_BETWEEN_ALERTS=16   # Cooldown period between alerts
SENSITIVITY=5000         # Motion detection sensitivity (higher = less sensitive)
MIN_MOTION_FRAMES=3      # Consecutive motion frames to trigger alert
MASK="100,100,500,400"   # Detection area: x1,y1,x2,y2 (adjust to your camera view)
MAX_VIDEO_FILES=10       # Max video files to store
```

**Key `.env` parameters:**

*   `RTSP`: Your camera's RTSP URL.
*   `TOKEN`: Your Telegram Bot's API token.
*   `CHAT_ID`: The Telegram chat ID to send alerts to.
*   `FPS`: How many frames per second the application processes from the camera. Crucial for performance, especially on devices like Raspberry Pi.
*   `SLOW_MOTION`: Factor to control playback speed of saved videos.
*   `MASK`: Defines the rectangular area (x1, y1, x2, y2) for motion detection.
*   Other parameters like `VIDEO_LENGTH_SECS`, `SECS_BETWEEN_ALERTS`, `SENSITIVITY`, `MIN_MOTION_FRAMES` allow fine-tuning of the detection and recording behavior.

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


