import socket
import cv2
import time
import sys
import numpy as np

# 服务器配置
SERVER_HOST = '127.0.0.1'  # 本地测试用，实际部署时改为服务器IP
SERVER_PORT = 65432

# 摄像头唯一标识
CAMERA_ID = "23373334"

def main():
    print("启动虚拟摄像头模拟设备...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((SERVER_HOST, SERVER_PORT))
            print(f"已连接到服务器 {SERVER_HOST}:{SERVER_PORT}")

            # 虚拟摄像头：生成假视频帧
            print("开始发送虚拟视频流...")
            camera_id_bytes = CAMERA_ID.encode('utf-8')
            frame_count = 0
            while True:
                # 生成一个640x480的彩色帧
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                # 添加一些动态元素，比如一个移动的圆
                center_x = (frame_count * 10) % 640
                cv2.circle(frame, (center_x, 240), 50, (0, 255, 0), -1)
                cv2.putText(frame, f"Virtual Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                # 编码为JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    # 发送：id长度(4字节) + id + 帧长度(4字节) + 帧数据
                    try:
                        s.sendall(len(camera_id_bytes).to_bytes(4, 'big') + camera_id_bytes + len(frame_bytes).to_bytes(4, 'big') + frame_bytes)
                    except BrokenPipeError:
                        print("连接断开")
                        break
                    except Exception as e:
                        print(f"发送错误: {e}")
                        break
                else:
                    print("编码帧失败")
                    break

                frame_count += 1
                # 控制帧率，大约10 FPS
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("用户中断")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()