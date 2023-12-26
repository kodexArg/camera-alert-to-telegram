import argparse
import numpy as np
import cv2
from datetime import datetime, timedelta
from collections import deque

MOTIONS_DETECTED = 3  # require n number of captures to consider it an Alert
SECS_LAST_MOVEMENT = 2  # seconds since the first capture considered an Alert
SECS_LAST_ALERT = 5  # seconds since the last Alert.
lastpic = None  # GLOBAL


class TimestampIterator:
    """
    Stores the last three values received and returns True if there has been movement in
    all the records the past 2 seconds (or SECS_DETECT_DELAY).
    """

    def __init__(self):
        self.timestamps = deque(maxlen=3)

    def call(self):
        current_time = datetime.now()
        self.timestamps.append(current_time)

        has_x_motions = len(self.timestamps) == MOTIONS_DETECTED
        is_on_time = current_time - self.timestamps[0] <= timedelta(SECS_LAST_MOVEMENT)

        if has_x_motions and is_on_time:
            return True

        return False


def read_frame(cap):
    ret, frame = cap.read()
    if not ret:
        return False, None, None
    else:
        return ret, frame, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


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


def process_frames(cap, t, mask_rect):
    global lastpic
    timestamp_iterator = TimestampIterator()  # to record last three detections

    ret, _, reference_frame = read_frame(cap)

    while ret:
        ret, frame, gray_frame = read_frame(cap)
        if not ret:
            break

        motion_detected, bounding_boxes = is_motion_detected(
            reference_frame, gray_frame, t, mask_rect
        )

        # Draw a white rectangle to visualize the mask area
        cv2.rectangle(
            frame,
            (mask_rect[0], mask_rect[1]),
            (mask_rect[2], mask_rect[3]),
            (255, 255, 255),
            2,
        )

        if motion_detected:
            print(f"detection: {datetime.now()}")
            draw_motion_boxes(frame, bounding_boxes, mask_rect)

            is_alert = timestamp_iterator.call()
            has_lastpic = lastpic is not None and (
                datetime.now() - lastpic
            ) < timedelta(SECS_LAST_MOVEMENT)

            if is_alert and not has_lastpic:
                lastpic = datetime.now()
                print(
                    f"\033[91mAlert recorded at {datetime.now()}\033[0m"
                )  # print red: \033[91m.....[0m

        reference_frame = gray_frame.copy()
        cv2.imshow("Frame", frame)

        # Exit pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


def main():
    # Parameters
    parser = argparse.ArgumentParser(description="Motion Detection in Video Streams")
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        default="rtsp://admin:Ip1921681108@192.168.10.38:554/cam/realmonitor?channel=1&subtype=1",
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
        default=[0, 275, 720, 720],
        help="Mask coordinates (x1 y1 x2 y2) for focusing motion detection on a specific area of the frame. Default is '0 400 720 720'.",
    )
    args = parser.parse_args()

    # White square mask where the movement is detected
    mask_rect = tuple(args.mask)

    # Main loop
    cap = cv2.VideoCapture(args.url)
    process_frames(cap, args.threshold, mask_rect)

    # End
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
