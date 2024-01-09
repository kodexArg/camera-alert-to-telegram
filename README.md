## Required Environment Variables
Some of these can be sent as arguments. Use '-h' to get information about how to use them. As soon as you get a good configuration, write it in a **.env** file. 

### Example .env file:

```
# Required
RTSP=rtsp://your_camera_connection_string

# Required if USE_TELEGRAM = True
TOKEN=your_telegram_token
CHAT_ID=your_chat_id #TODO: or a [list, of, chats, ids]

# Features
USE_TELEGRAM=False
SHOW_VIDEO=True
LOGGER_LEVEL="DEBUG"

# Video and detection settings
MAX_VIDEO_FILES=20
VIDEO_LENGTH_SECS=8
DETECTION_SECONDS=3
SECS_BETWEEN_ALERTS=10
SENSITIVITY=3000
FPS=5
MASK=130, 360, 683, 450

```

### Running app.py with arguments:
```
./app.py --rtsp rtsp://your_camera_url --log-level DEBUG --mask 130 360 683 450

```

### About these values:
RTSP: The RTSP URL for your camera. This is essential for accessing the video stream.
TOKEN: Your Telegram bot token. Required if you enable Telegram notifications.
CHAT_ID: Your Telegram chat ID (or a list of IDs) for receiving notifications. Required if Telegram notifications are enabled.

**Optional Parameters**
*These parameters can be set in the .env file or passed as command-line arguments when running app.py.*

USE_TELEGRAM: Enable or disable Telegram integration. Accepts True or False. Can be set as --use-telegram in the command line.
SHOW_VIDEO: Show the video feed in a window when the script is running. Accepts True or False. Can be set as --show-video in the command line.
LOGGER_LEVEL: Control the level of logging output. Common values are DEBUG and INFO. Can be set as --log-level in the command line.
VIDEO_LENGTH_SECS: Duration of the video saved when motion is detected. Defaults to 5 seconds. Minimum value is 4 seconds. Can be set as --video-seconds.
DETECTION_SECONDS: Time in seconds before considering motion as ceased. Defaults to 2 seconds. Can only be positive. Can be set as --detection-seconds.
SECS_BETWEEN_ALERTS: Minimum time between two alerts. Defaults to 8 seconds. Must be greater than VIDEO_LENGTH_SECS. Can be set as --secs-between-alerts.
SENSITIVITY: Sensitivity for motion detection. Defaults to 3000. Can be set as --sensitivity.
FPS: Frames per second of the video. Defaults to 5. Can be set as --fps.
MASK: Defines the area for motion detection in the format x1, y1, x2, y2. All values must be positive integers, with x1 < x2 and y1 < y2. Can be set as --mask.


## Video Capture and Alert Logic 

The logic behind video capture and alert triggering is designed to ensure that significant motion events are captured effectively. To understand this, let's consider a scenario with specific parameter values:

- `VIDEO_LENGTH_SECS`: 6 seconds (the total length of the video to be saved)
- `DETECTION_SECONDS`: 2 seconds (the time required to confirm actual motion)
- An additional 1-second pre-motion buffer is used for context (an arbitrary constant for better user understanding)

**How the Logic Works:**
1. **Motion Detection and Alert Triggering**:
   - When motion is detected, the system starts a countdown of `DETECTION_SECONDS` (2 seconds in our example).
   - If sustained motion is confirmed after these 2 seconds, an alert is triggered.

2. **Video Capture Process**:
   - Normally, one would expect the video capture to start immediately after the alert is triggered. However, this approach would miss the initial 2 seconds of motion that led to the alert.
   - To capture these crucial initial moments, the system utilizes a 6-second buffer (`video_buffer`) which continuously records video.
   - Upon triggering an alert, instead of immediately saving the video, the system waits for an additional 4 seconds (6 seconds total length - 2 seconds motion detection period). This ensures that the video buffer contains the initial 2 seconds of motion.

3. **Enhanced Contextual Capture**:
   - To provide an even better context, we subtract another second from the capture period. This means that the system will now wait for only 3 seconds post-alert before saving the video.
   - This adjustment ensures that the final video starts with 1 second of 'no motion' footage, followed by the 2 seconds of initial motion and then 3 seconds after the motion, totaling 6 seconds. 

**Example Breakdown of the Final Video**:
- The first 1 second shows the scene before the motion started, providing context.
- The next 2 seconds capture the initial motion that triggered the alert.
- The final 3 seconds show the continued motion post-alert, completing the story.


## Extras
I've included a `find-camera.py` script which you might find useful to locate your camera on the LAN.


## TODO
- [x] keep a permanent cache of X seconds (prolly 1 second) so the user can see the movement trigger
- [x] normalize parameters and virtual environment
- [ ] multiple chat_id and chat_id registration using a bot command
- [x] video rotation to save space
- [x] video_buffer to Tuple[frame, timestamp]

## COULD HAVE
- [ ] Sensitivity as bot parameter
- [ ] Send Video to Telegram as bot parameter
- [ ] Send Text to Telegram option
- [ ] .env variable to disable the telegram
- [ ] Mask as bot parameter + draw the mask


