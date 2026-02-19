import requests


class HookMocker:
    def __init__(self, alert, web_hook_url):
        self.alert = alert
        self.web_hook_url = web_hook_url

    def start(self, width=1920, height=1080, fps=30):
        print(f"Mocker started with {width}x{height} at {fps} FPS")
        self.alert.start(width=width, height=height, fps=fps)

    def provide_frame(self, frame):
        self.alert.provide_frame(frame)

    def end(self):
        print("Mocker ending")
        self.alert.end()
        self.frame_count = self.alert.frame_count
        self.dropped_frames = self.alert.dropped_frames
        requests.post(
            self.web_hook_url,
            json={
                "EventName": "s3:ObjectCreated:Put",
                "Key": f"atc/{self.alert.name}",
                "Records": [],
            },
        )
