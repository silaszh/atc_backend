import cv2
import numpy as np
import time


class Camera:
    """摄像头基类"""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id

    def get_frame(self) -> bytes:
        """获取最新帧的JPEG数据"""
        raise NotImplementedError("子类必须实现get_frame方法")

    def release(self):
        pass


class PhyCam(Camera):
    """真实物理摄像头"""

    def __init__(self, camera_id: str, device_id: int = 0):
        super().__init__(camera_id)
        self.cap = cv2.VideoCapture(device_id)
        if not self.cap.isOpened():
            raise ValueError(f"无法打开摄像头设备 {device_id}")

    def get_frame(self) -> bytes:
        ret, frame = self.cap.read()
        if ret:
            ret, buffer = cv2.imencode(".jpg", frame)
            if ret:
                return buffer.tobytes()
        return b""

    def release(self):
        self.cap.release()


class VidCam(Camera):
    """视频文件摄像头"""

    def __init__(self, camera_id: str, video_path: str):
        super().__init__(camera_id)
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频文件 {video_path}")

    def get_frame(self) -> bytes:
        ret, frame = self.cap.read()
        if ret:
            ret, buffer = cv2.imencode(".jpg", frame)
            if ret:
                return buffer.tobytes()
        else:
            # 循环播放
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret:
                ret, buffer = cv2.imencode(".jpg", frame)
                if ret:
                    return buffer.tobytes()
        return b""

    def release(self):
        self.cap.release()


class ImgCam(Camera):
    """固定图片摄像头"""

    def __init__(self, camera_id: str, image_path: str):
        super().__init__(camera_id)
        self.frame = cv2.imread(image_path)
        if self.frame is None:
            raise ValueError(f"无法加载图片 {image_path}")
        # 编码一次
        ret, buffer = cv2.imencode(".jpg", self.frame)
        if ret:
            self.frame_bytes = buffer.tobytes()
        else:
            raise ValueError("图片编码失败")

    def get_frame(self) -> bytes:
        return self.frame_bytes


class AniCam(Camera):
    """动画摄像头 - 生成动态帧"""

    def __init__(self, camera_id: str, width: int = 640, height: int = 480):
        super().__init__(camera_id)
        self.width = width
        self.height = height
        self.frame_count = 0

    def get_frame(self) -> bytes:
        # 生成动态帧
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # 移动的圆
        center_x = (self.frame_count * 10) % self.width
        cv2.circle(frame, (center_x, self.height // 2), 50, (0, 255, 0), -1)
        # 帧计数
        cv2.putText(
            frame,
            f"AniCam Frame: {self.frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )
        # 其他动画元素，比如颜色变化
        color = (self.frame_count * 5 % 256, 100, 200)
        cv2.rectangle(frame, (50, 50), (150, 150), color, -1)

        ret, buffer = cv2.imencode(".jpg", frame)
        if ret:
            self.frame_count += 1
            return buffer.tobytes()
        return b""
