import cv2
import numpy as np
import av
import asyncio
from aiortc import VideoStreamTrack


class CapTrack(VideoStreamTrack):
    """Video track that uses a pre-configured cv2.VideoCapture."""
    def __init__(self, cap: cv2.VideoCapture, is_loop: bool = False):
        super().__init__()
        self.cap = cap
        self.is_loop = is_loop
        if self.is_loop:
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            self.frame_delay = 1 / self.fps
        else:
            self.frame_delay = 0  # No delay for camera

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        if not ret and self.is_loop:
            # Loop back to beginning for video files
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        if not ret:
            # return black frame if no frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        if self.frame_delay > 0:
            await asyncio.sleep(self.frame_delay)
        return video_frame


class CameraVideoTrack(CapTrack):
    def __init__(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Could not open camera")
        # Try to set camera properties for better exposure
        try:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # manual exposure
        except Exception:
            pass
        try:
            cap.set(cv2.CAP_PROP_EXPOSURE, -4)  # lower exposure
        except Exception:
            pass
        try:
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # disable autofocus
        except Exception:
            pass
        # Warm up the camera by reading a few frames to ensure it's ready
        for _ in range(10):
            ret, _ = cap.read()
            if ret:
                break
        super().__init__(cap, is_loop=False)


class VideoFileTrack(CapTrack):
    def __init__(self, video_path: str):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")
        super().__init__(cap, is_loop=True)