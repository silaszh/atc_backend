import threading
import time
import asyncio
from minio import Minio
import socketio
import numpy as np
import cv2
import av
import os

from collections import deque
from aiortc import (
    MediaStreamError,
    RTCConfiguration,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.mediastreams import VIDEO_CLOCK_RATE, VIDEO_TIME_BASE
from dotenv import load_dotenv

from .alert import Alert

load_dotenv()

WEBRTC_SERVER_URL = os.getenv("WEBRTC_SERVER_URL", "ws://localhost:5000")
WEBRTC_DATA_HISTORY_MAXLEN = int(os.getenv("WEBRTC_DATA_HISTORY_MAXLEN", 200))

minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False,
)


class RingBuffer:
    def __init__(self, maxlen):
        self._buf = deque(maxlen=maxlen)

    def append(self, item):
        self._buf.append(item)

    def snapshot(self):
        return list(self._buf)


class MonitoringHub:
    def __init__(self, max_history=WEBRTC_DATA_HISTORY_MAXLEN):
        self._history = RingBuffer(maxlen=max_history)
        self._channels = set()
        self._queue = asyncio.Queue()
        self._task = None

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self):
        while True:
            data = await self._queue.get()
            dead = []
            for ch in list(self._channels):
                if ch.readyState != "open":
                    dead.append(ch)
                    continue
                try:
                    ch.send(data)
                except Exception:
                    dead.append(ch)
            for ch in dead:
                self._channels.discard(ch)

    def register_channel(self, channel):
        # 初次建立时补发历史
        print(f"Channel {channel.label} opened, sending history")
        self._channels.add(channel)
        for item in self._history.snapshot():
            try:
                channel.send(item)
            except Exception:
                self._channels.discard(channel)
                break

    def send_data(self, data):
        str_data = str(data)
        self._history.append(str_data)
        self._queue.put_nowait(str_data)


class WebRTCServer:
    def __init__(self, fps, seat, server=WEBRTC_SERVER_URL):
        self.pcs = set()
        self.fps = fps
        self.frameContainer = [None]
        self.hub = MonitoringHub()
        self.sio = None

        self.background_loop = asyncio.new_event_loop()

        self._rtc_thread = threading.Thread(
            target=self._start_background_loop,
            args=(self.background_loop,),
            daemon=True,
        )
        self._rtc_thread.start()

        self.server = server
        self.seat = seat

    def _start_background_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def _websocket_start(self):
        await self.hub.start()
        sio = socketio.AsyncClient()
        self.sio = sio

        @sio.event
        async def connect():
            print("已连接到中心信令服务器")
            await sio.emit("checkin", {"seat_id": self.seat})

        @sio.event
        async def offer(data):
            # data 包含: { sdp: "...", type: "offer", "sid": "..." }
            print("收到 WebRTC Offer")

            localDescription = await self._handle_offer(data)

            await sio.emit(
                "answer",
                {
                    "sdp": localDescription.sdp,
                    "type": localDescription.type,
                    "sid": data["sid"],
                },
            )

        await sio.connect(self.server)
        print(self.server, "connected")
        await sio.wait()

    async def _handle_offer(self, offer):
        pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.pcs.add(pc)
        start = time.time()

        @pc.on("connectionstatechange")
        async def on_state_change():
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                await pc.close()
                print("Connection closed")
                self.pcs.discard(pc)

        @pc.on("datachannel")
        def on_data_channel(channel):
            route_channel(channel)

        await pc.setRemoteDescription(
            RTCSessionDescription(offer["sdp"], offer.get("type", "offer"))
        )
        pc.addTrack(VideoFrameTrack(self.fps, self.frameContainer))

        dc = pc.createDataChannel("monitoring")

        @dc.on("open")
        def on_open():
            print("Monitoring data channel opened")
            self.hub.register_channel(dc)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        print(f"Handle offer in {(time.time() - start)*1000:.2f}ms")
        return pc.localDescription

    def start(self):
        asyncio.run_coroutine_threadsafe(self._websocket_start(), self.background_loop)

    def provide_frame(self, frame):
        self.frameContainer[0] = frame

    def send_data(self, data):
        self.hub.send_data(data)

    def alert(self, timestamp, summary, level):
        payload = {
            "seat_id": self.seat,
            "timestamp": timestamp,
            "summary": summary,
            "level": level,
        }
        if self.sio is not None and self.sio.connected:
            asyncio.run_coroutine_threadsafe(
                self.sio.emit("alert", payload), self.background_loop
            )
        else:
            print("Warning: sio is not connected, skip signaling alert emit")
        return Alert(name=f"seat{self.seat}_{timestamp}.mp4", client=minio_client)

    def stop(self):
        if self.background_loop.is_running():
            self.background_loop.call_soon_threadsafe(self.background_loop.stop)
        if self._rtc_thread.is_alive():
            self._rtc_thread.join(timeout=2)


class VideoFrameTrack(VideoStreamTrack):
    def __init__(self, fps, fc):
        super().__init__()
        self.fps = fps
        self.frameContainer = fc

    async def next_timestamp(self):
        """
        重写父类方法，去除帧率限制
        """
        if self.readyState != "live":
            raise MediaStreamError

        if hasattr(self, "_timestamp"):
            self._timestamp += int(1 / self.fps * VIDEO_CLOCK_RATE)
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            await asyncio.sleep(wait)
        else:
            self._start = time.time()
            self._timestamp = 0
        return self._timestamp, VIDEO_TIME_BASE

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.frameContainer[0]
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            frame = self.frameContainer[0]
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


def route_channel(channel):
    match channel.label:
        case "latency":

            @channel.on("message")
            def on_message(message):
                now = int(time.time() * 1000 + 0.5)
                channel.send(str(now))

                pre = int(message)
                print(f"Latency: {now - pre}ms")

        case _:
            print(f"Unknown Channel {channel.label}")
