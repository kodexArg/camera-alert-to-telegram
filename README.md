# Camera Alert to Telegram

A Python-based surveillance system that detects motion in a video stream and sends alerts via Telegram. The system uses OpenCV for video processing and motion detection, and the python-telegram-bot library for Telegram integration.

## Features

- Real-time motion detection in a configurable area of the video stream
- Automatic video recording when motion is detected
- Telegram integration for instant alerts and video sharing
- Configurable sensitivity and detection parameters
- Video buffer management with automatic cleanup
- Command-line interface for instant photos and video clips
- Robust error handling and logging system

## Required Environment Variables

The system can be configured through environment variables in a `.env` file or command-line arguments. Here's an example configuration:

```env
# Required
RTSP="rtsp://your_camera_url"

# Required if USE_TELEGRAM = True
TOKEN="your_telegram_bot_token"
CHAT_ID="your_chat_id"

# Features
USE_TELEGRAM=True
SHOW_VIDEO=False
LOGGER_LEVEL="INFO"

# Video and detection settings
MAX_VIDEO_FILES=6
VIDEO_LENGTH_SECS=20
DETECTION_SECONDS=3
SECS_BETWEEN_ALERTS=21
SENSITIVITY=4500
FPS=6
MIN_MOTION_FRAMES=3
MASK=150, 290, 683, 523
```

### Configuration Parameters

#### Required Parameters
- `RTSP`: The RTSP URL for your camera stream
- `TOKEN`: Your Telegram bot token (required if `USE_TELEGRAM=True`)
- `CHAT_ID`: Your Telegram chat ID (required if `USE_TELEGRAM=True`)

#### Optional Parameters
- `USE_TELEGRAM`: Enable/disable Telegram integration (default: `True`)
- `SHOW_VIDEO`: Show video feed in a window (default: `False`)
- `LOGGER_LEVEL`: Logging level (default: `"INFO"`)

#### Video and Detection Settings
- `MAX_VIDEO_FILES`: Maximum number of video files to keep (default: `6`)
- `VIDEO_LENGTH_SECS`: Duration of recorded videos in seconds (default: `20`)
- `DETECTION_SECONDS`: Time to confirm motion (default: `3`)
- `SECS_BETWEEN_ALERTS`: Minimum time between alerts (default: `21`)
- `SENSITIVITY`: Motion detection sensitivity (default: `4500`)
- `FPS`: Frames per second (default: `6`)
- `MIN_MOTION_FRAMES`: Minimum frames with motion to trigger alert (default: `3`)
- `MASK`: Detection area coordinates (x1, y1, x2, y2)

## Running the Application

### Basic Usage
```bash
python app.py
```

### Command-line Arguments
```bash
python app.py --rtsp rtsp://your_camera_url --log-level INFO --mask 150 290 683 523
```

## Telegram Bot Commands

The system provides several commands for interacting with the surveillance system:

- `/start`: Display welcome message and available commands
- `/photo`: Take and send an instant photo from the camera
- `/clip5`: Generate and send a 5-second video clip
- `/clip20`: Generate and send a 20-second video clip

## Video Processing and Alert Logic

The system uses a sophisticated buffer-based approach to ensure comprehensive motion capture:

1. **Continuous Buffer**
   - Maintains a circular buffer of video frames
   - Buffer size = `VIDEO_LENGTH_SECS + SECS_BETWEEN_ALERTS + 5` seconds
   - Each frame is timestamped for precise event tracking

2. **Motion Detection**
   - Uses OpenCV's MOG2 background subtractor
   - Processes frames at configured `FPS`
   - Detects motion in the specified `MASK` area
   - Requires `MIN_MOTION_FRAMES` consecutive frames with motion

3. **Alert Triggering**
   - When motion is detected, waits `DETECTION_SECONDS` to confirm
   - Ensures `SECS_BETWEEN_ALERTS` between consecutive alerts
   - Saves video from buffer when alert is triggered
   - Automatically manages video file storage

4. **Video Management**
   - Saves videos in MP4 format
   - Maintains maximum of `MAX_VIDEO_FILES` videos
   - Automatically removes oldest videos when limit is reached
   - Videos are named with timestamp and duration

## Error Handling and Logging

- Comprehensive error handling for video capture and processing
- Automatic reconnection attempts for lost video streams
- Detailed logging with configurable levels
- Telegram notifications for critical errors
- Clean shutdown handling for system signals

## Development Status

### Completed Features
- [x] Configurable video buffer with timestamp tracking
- [x] Normalized parameters and virtual environment
- [x] Video rotation and cleanup
- [x] Robust error handling and logging
- [x] Telegram integration with multiple commands

### Planned Features
- [ ] Multiple chat_id support and registration via bot commands
- [ ] Configurable sensitivity through bot commands
- [ ] Optional text-only alerts
- [ ] Dynamic mask configuration through bot commands
- [ ] Mask visualization in video feed

## Dependencies

- Python 3.11+
- OpenCV
- python-telegram-bot
- loguru
- python-dotenv

## Installation

### Standard Installation
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your configuration
4. Run the application:
   ```bash
   python app.py
   ```

### Raspberry Pi Installation
1. Clone the repository
2. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```
3. Create a `.env` file with your configuration
4. Run the application:
   ```bash
   python3 app.py
   ```

### Running as a Service (Linux)
For production environments, it's recommended to run the application as a systemd service. This ensures:
- Automatic startup on boot
- Automatic restart on failure
- Proper logging and monitoring
- System resource management

Create a service file at `/etc/systemd/system/camera-alert.service` with appropriate permissions and configuration. The service should run as a non-root user with necessary permissions for camera access.

Example service configuration:
```ini
[Unit]
Description=Camera Alert to Telegram Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/camera-alert-to-telegram
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl enable camera-alert
sudo systemctl start camera-alert
```

Monitor the service:
```bash
sudo systemctl status camera-alert
```


