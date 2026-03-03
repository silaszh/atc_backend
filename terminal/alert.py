import os
import queue
import threading

import av

ALERT_QUEUE_MAXSIZE = 2000


class Alert:
    def __init__(self, name, client):
        self.name = name
        self.client = client
        self.frame_count = 0
        self.frame_queue = queue.Queue(maxsize=ALERT_QUEUE_MAXSIZE)
        self.encode_thread = None
        self.upload_thread = None
        self.stop_event = threading.Event()
        self.dropped_frames = 0

    def start(self, width=1920, height=1080, fps=30):
        print(f"Starting alert with {width}x{height}")
        read_fd, write_fd = os.pipe()
        self.read_pipe = os.fdopen(read_fd, "rb", buffering=0)
        self.write_pipe = os.fdopen(write_fd, "wb", buffering=0)

        def _upload() -> None:
            try:
                print(f"Upload thread starting for {self.name}")
                self.client.put_object(
                    "atc",
                    self.name,
                    self.read_pipe,
                    length=-1,
                    part_size=10 * 1024 * 1024,
                    content_type="video/mp4",
                )
                print(f"Upload completed for {self.name}")
            except Exception as e:
                print(f"Upload error: {e}")

        self.upload_thread = threading.Thread(target=_upload, daemon=False)
        self.upload_thread.start()

        self.container = av.open(
            self.write_pipe,
            mode="w",
            format="mp4",
            options={"movflags": "frag_keyframe+empty_moov+default_base_moof"},
        )
        self.stream = self.container.add_stream("libx264", rate=fps)
        self.stream.width = width
        self.stream.height = height
        self.stream.pix_fmt = "yuv420p"
        # 使用更快的编码预设
        # self.stream.options = {"preset": "ultrafast", "crf": "23"}
        print("AV container and stream initialized")

        # 启动编码线程
        def _encode() -> None:
            try:
                print("Encode thread starting")
                while not self.stop_event.is_set() or not self.frame_queue.empty():
                    try:
                        frame = self.frame_queue.get(timeout=0.1)
                        if frame is None:
                            break
                        av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
                        for packet in self.stream.encode(av_frame):
                            self.container.mux(packet)
                        self.frame_count += 1
                    except queue.Empty:
                        continue
                    except Exception as e:
                        print(f"Error encoding frame {self.frame_count}: {e}")
                print(f"Encode thread finished, encoded {self.frame_count} frames")
            except Exception as e:
                print(f"Encode thread error: {e}")

        self.encode_thread = threading.Thread(target=_encode, daemon=False)
        self.encode_thread.start()

    def provide_frame(self, frame):
        try:
            self.frame_queue.put(frame, block=True, timeout=0.05)
        except queue.Full:
            self.dropped_frames += 1
            # 每50帧打印一次
            if self.dropped_frames % 50 == 1:
                print(
                    f"Warning: Frame queue full, dropped {self.dropped_frames} frames so far"
                )

    def end(self):
        print(
            f"Stopping alert, queued frames: {self.frame_queue.qsize()}, dropped frames: {self.dropped_frames}"
        )
        self.frame_queue.put(None)
        self.stop_event.set()

        # 等待编码线程完成
        if self.encode_thread:
            self.encode_thread.join(timeout=30)
            if self.encode_thread.is_alive():
                print("Warning: Encode thread still running after timeout")
            else:
                print(f"Encode thread completed with {self.frame_count} frames")

        # 完成编码，flush所有待处理的数据
        try:
            for packet in self.stream.encode():
                self.container.mux(packet)
        except Exception as e:
            print(f"Error flushing encoder: {e}")

        # 关闭容器，确保所有数据已写入pipe
        try:
            self.container.close()
            print("Container closed successfully")
        except Exception as e:
            print(f"Error closing container: {e}")

        # 关闭写端，通知上传线程EOF
        self.write_pipe.close()
        print("Write pipe closed, waiting for upload thread...")

        # 等待上传线程完成（最多30秒）
        if self.upload_thread:
            self.upload_thread.join(timeout=30)
            if self.upload_thread.is_alive():
                print("Warning: Upload thread still running after timeout")
            else:
                print("Upload thread completed")

        # 关闭读端
        self.read_pipe.close()
