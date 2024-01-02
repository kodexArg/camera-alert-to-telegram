## Required Environment Variables
At this time, to start **app.py**, the following environment variables must be available:
*.env file or exported variables:*
```
TOKEN=your_telegram_token
CHAT_ID=your_chat_id #TODO: or a [list, of, chats, ids]
RTSP=rtsp://your_camera_connection_string
```
(I've included a `find-camera.py` script which you might find useful to locate your camera on the LAN)

Additionally, there's a list of optional parameters available. They are in the **Config** class of **app.py**.

The bottom part of my .env looks like this:
```
SECS_LAST_MOVEMENT=0
SECS_LAST_ALERT=20
SECS_SAVED_VIDEO=4
SECS_UNLOCK_AFTER_ALERT=5
DEFAULT_MASK_X1=120
DEFAULT_MASK_Y1=255
DEFAULT_MASK_X2=700
DEFAULT_MASK_Y2=500
LOGGER_LEVEL=DEBUG
FPS=24
```