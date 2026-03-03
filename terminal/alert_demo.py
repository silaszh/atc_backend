import time
import cv2

from .webrtc_server import WebRTCServer
from .hook_mocker import HookMocker

SEAT_ID = 4
FPS = 30

alert_at = 2
total_frames = 15 * FPS

server = WebRTCServer(FPS, SEAT_ID)
server.start()

# 初始化摄像头
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Cannot open camera")
    exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
actual_fps = cap.get(cv2.CAP_PROP_FPS)
print(f"Camera resolution: {actual_width}x{actual_height}, FPS: {actual_fps}")

frame_buffer = []
alert_frame = alert_at * FPS
frame_count = 0
alert = None
start_time = time.time()
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to read frame")
            break
        frame_buffer.append(frame)
        frame_count += 1
        if frame_count >= alert_frame and alert is None:
            elapsed = time.time() - start_time
            print(
                f"Alert triggered at frame: {frame_count}, buffer size: {len(frame_buffer)}, elapsed: {elapsed:.1f}s"
            )
            alert = server.alert(
                timestamp=int(time.time()),
                # summary=f"Alert at frame {frame_count}",
                summary=f"频繁打哈欠，存在疲劳可能性",
                level="严重",
            )
            # * 模拟 WebHook
            alert = HookMocker(alert, "http://localhost:5000/api/osshook")
            # 使用实际摄像头分辨率初始化
            alert.start(width=actual_width, height=actual_height)
            start_idx = max(len(frame_buffer) - total_frames // 2, 0)
            buffered_frames = frame_buffer[start_idx:]
            print(
                f"Providing {len(buffered_frames)} buffered frames (from index {start_idx}), expecting {total_frames // 2}"
            )
            for f in buffered_frames:
                alert.provide_frame(f)
            frame_buffer.clear()
            print(f"Buffered frames queued")

        if frame_count >= alert_frame and alert is not None:
            alert.provide_frame(frame)
            if frame_count >= alert_frame + total_frames // 2:
                print(
                    f"Reached total frames limit at frame {frame_count}, expected to stop at {alert_frame + total_frames // 2}"
                )
                break
        time.sleep(1 / FPS)
finally:
    cap.release()
    if alert is not None:
        elapsed_total = time.time() - start_time
        expected_frames = total_frames
        print(f"Total runtime: {elapsed_total:.1f}s, frame_count: {frame_count}")
        alert.end()
        print(
            f"Encoded {alert.frame_count} frames (expected {expected_frames}), dropped {alert.dropped_frames}"
        )
        print(
            f"Video duration: {alert.frame_count / FPS:.1f}s at {FPS}fps (expected {expected_frames / FPS:.1f}s)"
        )
    print("Camera released")
