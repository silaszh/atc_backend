import time
import numpy as np
import cv2
import threading

from .webrtc_server import WebRTCServer

FPS = 30
stop_event = threading.Event()


def run_ani(server):
    width, height = 1920, 1080
    frame_count = 60
    while not stop_event.is_set():
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


def run_cam(server, device_id):
    cap = cv2.VideoCapture(device_id)
    while not stop_event.is_set():
        ret, frame = cap.read()
        if ret:
            server.provide_frame(frame)
        time.sleep(1 / FPS)
    cap.release()
    print("Camera released")


def run_img(server, image_path):
    frame = cv2.imread(image_path)
    while not stop_event.is_set():
        if frame is not None:
            server.provide_frame(frame)
        time.sleep(1 / FPS)


def run_vid(server, video_path):
    cap = cv2.VideoCapture(video_path)
    while not stop_event.is_set():
        ret, frame = cap.read()
        if ret:
            server.provide_frame(frame)
        else:
            # 循环播放
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if ret:
                server.provide_frame(frame)
        time.sleep(1 / FPS)

    cap.release()
    print("Video released")


def mock_monitoring_data(server):
    count = 0
    while not stop_event.is_set():
        data = f"Simulated monitoring data {count}"
        server.send_data(data)
        count += 1
        time.sleep(1)


def simu_device(seat, run_fn, *args):
    server = WebRTCServer(fps=FPS, seat=seat)
    server.start()
    t = threading.Thread(target=run_fn, args=(server, *args))
    t_monitor = threading.Thread(target=mock_monitoring_data, args=(server,))
    t.start()
    t_monitor.start()
    return t, t_monitor


if __name__ == "__main__":
    device_pool = [
        simu_device(4, run_cam, 0),
        simu_device(7, run_ani),
        # simu_device(8, run_vid, "E:/Desktop/vid/1.mp4"),
        # simu_device(9, run_vid, "E:/Desktop/vid/2.mp4"),
        # simu_device(10, run_img, "E:/Desktop/vid/i1.png"),
    ]
    try:
        print("Running... Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        stop_event.set()
        for t, t_monitor in device_pool:
            if t:
                t.join()
            if t_monitor:
                t_monitor.join()
        print("Exiting...")
