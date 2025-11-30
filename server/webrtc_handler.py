import asyncio
import logging
import threading
from typing import Set

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import BYE

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from camera.video_tracks import CameraVideoTrack, VideoFileTrack


class WebRTCHandler:
    """封装WebRTC相关功能"""

    def __init__(self):
        self.pcs: Set[RTCPeerConnection] = set()
        self.background_loop = asyncio.new_event_loop()
        self.working = False

        # 启动后台asyncio loop
        self._t = threading.Thread(
            target=self._start_background_loop,
            args=(self.background_loop,),
            daemon=True
        )

    def start(self):
        self.working = True
        self._t.start()

    def _start_background_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def _handle_offer(self, offer: dict) -> RTCSessionDescription:
        """在后台事件循环中处理SDP offer并返回answer"""
        pc = RTCPeerConnection()
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_state_change():
            logging.info("Connection state: %s", pc.connectionState)
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                await pc.close()
                self.pcs.discard(pc)

        # 设置远端offer
        await pc.setRemoteDescription(RTCSessionDescription(offer["sdp"], offer.get("type", "offer")))

        # 添加视频track（可根据需要切换）
        # pc.addTrack(CameraVideoTrack())
        pc.addTrack(VideoFileTrack("F:\\海绵宝宝.第1-9季.SpongeBob.SquarePants.中配版.S01-S09.1999.720p.WEB-DL.H.264.AAC.2.0-CSWEB\\海绵宝宝.第1-9季.SpongeBob.SquarePants.中配版.S01-S09E003.1999.720p.WEB-DL.H.264.AAC.2.0-CSWEB.mp4"))

        # 创建answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        return pc.localDescription

    def handle_offer(self, offer: dict) -> dict:
        """处理WebRTC offer请求，返回SDP answer或错误"""
        fut = asyncio.run_coroutine_threadsafe(
            self._handle_offer(offer), self.background_loop)
        try:
            desc = fut.result(timeout=1500)
            return {'sdp': desc.sdp, 'type': desc.type}
        except Exception as e:
            logging.exception('Failed to create answer')
            return {'error': str(e)}