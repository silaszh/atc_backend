import time
import numpy as np
import cv2

from webrtc_server import WebRTCServer

FPS = 60

server = WebRTCServer(fps=FPS)
server.start()


def run_ani():
    width, height = 1920, 1080
    frame_count = 60
    while True:
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        center_x = (frame_count * 10) % width
        cv2.circle(frame, (center_x, height // 2), 50, (0, 255, 0), -1)
        cv2.putText(
            frame,
            f"AniCam Frame: {frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )
        color = (frame_count * 5 % 256, 100, 200)
        cv2.rectangle(frame, (50, 50), (150, 150), color, -1)
        server.provide_frame(frame)
        frame_count += 1
        time.sleep(1 / FPS)


def run_cam(device_id):
    cap = cv2.VideoCapture(device_id)
    while True:
        ret, frame = cap.read()
        if ret:
            server.provide_frame(frame)
        time.sleep(1 / FPS)


if __name__ == "__main__":
    run_cam(1)