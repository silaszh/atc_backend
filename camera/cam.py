import socket
import cv2
import time
import sys
import threading
from .camera_classes import *

# 服务器配置
SERVER_HOST = "127.0.0.1"  # 本地测试用，实际部署时改为服务器IP
SERVER_PORT = 65432


def push_stream(fps: float, camera: Camera):
    """将Camera提供的帧推送到服务器"""
    print(f"启动摄像头 {camera.camera_id} 推流...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((SERVER_HOST, SERVER_PORT))
            print(
                f"摄像头 {camera.camera_id} 已连接到服务器 {SERVER_HOST}:{SERVER_PORT}"
            )

            camera_id_bytes = camera.camera_id.encode("utf-8")
            while True:
                frame_bytes = camera.get_frame()
                if frame_bytes:
                    # 发送：id长度(4字节) + id + 帧长度(4字节) + 帧数据
                    try:
                        s.sendall(
                            len(camera_id_bytes).to_bytes(4, "big")
                            + camera_id_bytes
                            + len(frame_bytes).to_bytes(4, "big")
                            + frame_bytes
                        )
                    except BrokenPipeError:
                        print(f"摄像头 {camera.camera_id} 连接断开")
                        break
                    except Exception as e:
                        print(f"摄像头 {camera.camera_id} 发送错误: {e}")
                        break
                else:
                    print(f"摄像头 {camera.camera_id} 无法获取帧")
                    break

                # 控制帧率
                time.sleep(1 / fps)

    except KeyboardInterrupt:
        print(f"摄像头 {camera.camera_id} 用户中断")
    except Exception as e:
        print(f"摄像头 {camera.camera_id} 错误: {e}")


def main():
    # 声明Camera类的数组
    cameras = [
        VidCam("23373329", "E:/Desktop/vid/1.mp4"),
        VidCam("23373330", "E:/Desktop/vid/2.mp4"),
        VidCam("23373331", "E:/Desktop/vid/3.mp4"),
        PhyCam("23373332", device_id=0),
        # 可以添加更多：VidCam("vid_001", "path.mp4"), ImgCam("img_001", "path.jpg")
    ]

    # 使用多线程同时推流多个摄像头
    fps = 10.0  # 10 FPS
    threads = []

    for camera in cameras:
        t = threading.Thread(target=push_stream, args=(fps, camera), daemon=True)
        t.start()
        threads.append(t)

    # 保持主线程运行，等待用户中断
    try:
        while True:
            time.sleep(1)  # 主线程循环
    except KeyboardInterrupt:
        print("收到中断信号，正在停止所有摄像头...")

    # 清理资源
    for camera in cameras:
        camera.release()
    print("所有摄像头已停止")


if __name__ == "__main__":
    main()
