import threading
import socketserver

# 全局变量存储最新帧，按摄像头ID索引
latest_frames = {}

# Socket服务器配置
STREAM_PORT = 65432

class FrameHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global latest_frames
        print(f"新的摄像头连接: {self.client_address}")
        current_camera_id = None
        try:
            while True:
                try:
                    # 接收id长度(4字节)
                    id_length_data = self.request.recv(4)
                    if not id_length_data:
                        break
                    id_length = int.from_bytes(id_length_data, "big")

                    # 接收id字符串
                    id_data = self.request.recv(id_length)
                    if not id_data:
                        break
                    camera_id = id_data.decode("utf-8")
                    current_camera_id = camera_id

                    # 接收帧长度(4字节)
                    frame_length_data = self.request.recv(4)
                    if not frame_length_data:
                        break
                    frame_length = int.from_bytes(frame_length_data, "big")

                    # 接收帧数据
                    frame_data = b""
                    while len(frame_data) < frame_length:
                        chunk = self.request.recv(frame_length - len(frame_data))
                        if not chunk:
                            break
                        frame_data += chunk

                    if len(frame_data) == frame_length:
                        latest_frames[camera_id] = frame_data
                        # print(f"收到摄像头 {camera_id} 的帧数据")

                except Exception as e:
                    print(f"接收帧错误: {e}")
                    break
        finally:
            # 连接断开时，删除对应的摄像头记录
            if current_camera_id and current_camera_id in latest_frames:
                del latest_frames[current_camera_id]
                print(f"删除断开摄像头 {current_camera_id} 的记录")
            print(f"摄像头连接断开: {self.client_address}")

def start_stream_server():
    try:
        server = socketserver.ThreadingTCPServer(("0.0.0.0", STREAM_PORT), FrameHandler)
        print(f"视频流服务器启动在端口 {STREAM_PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"启动流服务器失败: {e}")

def init_socket_server():
    global stream_thread
    stream_thread = threading.Thread(target=start_stream_server, daemon=True)
    stream_thread.start()

if __name__ == "__main__":
    # 作为独立进程运行
    start_stream_server()