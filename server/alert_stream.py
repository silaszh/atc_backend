import time
import threading
from collections import deque
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

EVENT_ALERT = "alert"
EVENT_ALERT_VIDEO = "alert-video"
EVENT_ALERT_LLM = "alert-llm"
EVENT_NAMES = (EVENT_ALERT, EVENT_ALERT_VIDEO, EVENT_ALERT_LLM)
REQUIRED_EVENT_NAMES = set(EVENT_NAMES)


class AlertStreamStore:
    def __init__(self, max_events: int = 5000, ttl_seconds: int = 600):
        self._events = deque(maxlen=max_events)
        self._inflight: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)

    def ingest(
        self, alert_id: int, event_name: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if event_name not in REQUIRED_EVENT_NAMES:
            raise ValueError(f"Unsupported event name: {event_name}")
        if not isinstance(payload, dict):
            raise ValueError("payload must be dict")

        if alert_id is None:
            raise ValueError("Missing alert_id in payload")

        normalized_payload = deepcopy(payload)
        normalized_payload["alert_id"] = alert_id

        merged_to_persist = None
        with self._cond:
            now = time.time()
            self._cleanup_expired_locked(now)

            state = self._inflight.get(alert_id)
            if state is None:
                state = {
                    "parts": {},
                    "updated_at": now,
                    "expire_at": now + self._ttl_seconds,
                    "persisting": False,
                }
                self._inflight[alert_id] = state

            state["parts"][event_name] = normalized_payload
            state["updated_at"] = now
            state["expire_at"] = now + self._ttl_seconds

            seq = self._append_event_locked(
                event_name=event_name,
                alert_id=alert_id,
                payload=normalized_payload,
            )

        return {
            "status": "ok",
            "alert_id": alert_id,
            "event_name": event_name,
            "seq": seq,
            "completed": merged_to_persist is not None,
        }

    def open_stream_snapshot(self) -> Tuple[List[Dict[str, Any]], int]:
        with self._cond:
            now = time.time()
            self._cleanup_expired_locked(now)
            snapshot_events: List[Dict[str, Any]] = []

            alert_ids = sorted(
                self._inflight.keys(),
                key=lambda item: self._inflight[item]["updated_at"],
            )
            for alert_id in alert_ids:
                state = self._inflight[alert_id]
                for event_name in EVENT_NAMES:
                    part = state["parts"].get(event_name)
                    if part is None:
                        continue
                    snapshot_events.append(
                        {
                            "seq": 0,
                            "event_name": event_name,
                            "alert_id": alert_id,
                            "payload": deepcopy(part),
                        }
                    )

            return snapshot_events, self._seq

    def wait_for_events(
        self, last_seq: int, timeout_seconds: int = 25
    ) -> Tuple[List[Dict[str, Any]], int]:
        with self._cond:
            now = time.time()
            self._cleanup_expired_locked(now)

            if self._seq <= last_seq:
                self._cond.wait(timeout=timeout_seconds)

            event_list = [event for event in self._events if event["seq"] > last_seq]
            return event_list, self._seq

    def get_state(self, alert_id: str, event: str) -> Optional[Dict[str, Any]]:
        with self._cond:
            state = self._inflight.get(alert_id)
            if state is None:
                return None
            return deepcopy(state["parts"].get(event))

    def persisting(self, alert_id):
        class PersistContext:
            def __enter__(inner_self):
                with self._cond:
                    state = self._inflight.get(alert_id)
                    if state is not None:
                        state["persisting"] = True

            def __exit__(inner_self, exc_type, exc_val, exc_tb):
                with self._cond:
                    current_state = self._inflight.get(alert_id)
                    if current_state is not None:
                        del self._inflight[alert_id]

        return PersistContext()

    def _append_event_locked(
        self, event_name: str, alert_id: str, payload: Dict[str, Any]
    ) -> int:
        self._seq += 1
        event = {
            "seq": self._seq,
            "event_name": event_name,
            "alert_id": alert_id,
            "payload": deepcopy(payload),
        }
        self._events.append(event)
        self._cond.notify_all()
        return self._seq

    def _cleanup_expired_locked(self, now: float) -> None:
        expired_ids = [
            alert_id
            for alert_id, state in self._inflight.items()
            if state["expire_at"] <= now and not state["persisting"]
        ]
        for alert_id in expired_ids:
            del self._inflight[alert_id]

    def _is_completed_state(self, state: Dict[str, Any]) -> bool:
        return REQUIRED_EVENT_NAMES.issubset(state["parts"].keys())


ALERT_STREAM = AlertStreamStore()
