import os
from datetime import datetime, timezone
import json
from flask import Blueprint, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

from ..data_store import alert_map
from ..pg_helper import get_helper
from ..minio_service import get_video_url
from ..alert_stream import ALERT_STREAM
from ..llm.model import Model
from ..llm import prompts
from ..llm.tools import verify_system_judgment

load_dotenv()

bp = Blueprint("state", __name__)

model = Model(os.getenv("VISION_MODEL"))
using_tools = [verify_system_judgment]


@bp.route("/api/states", methods=["POST"])
def create_state():
    if request.is_json:
        data = request.get_json()
        seat_id = data.get("seat_id")
        if seat_id is None:
            return jsonify({"error": "Missing seat_id"}), 400

        timestamp = data.get("timestamp")
        if timestamp is None:
            return jsonify({"error": "Missing timestamp"}), 400

        # 支持 10位/13位 数字时间戳
        if isinstance(timestamp, (int, float)):
            if timestamp > 10_000_000_000:  # 认为是毫秒
                timestamp = timestamp / 1000.0
            timestamp = datetime.fromtimestamp(timestamp, timezone.utc)
        else:
            return jsonify({"error": "Invalid timestamp type"}), 400

        print(timestamp)
        # 剔除已处理字段
        state_data = {
            k: v for k, v in data.items() if k not in ["seat_id", "timestamp"]
        }

        helper = get_helper()
        helper.insert_state(seat_id, timestamp, state_data)
        helper.close()

        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"error": "Invalid input"}), 400


@bp.route("/api/osshook", methods=["POST"])
def handle_webhook():
    data = request.get_json()
    print(data["Key"])
    video_path = data["Key"]
    print(get_video_url(video_path))
    alert_key = data["Key"].split("/")[-1].replace(".mp4", "")
    alert_id = alert_map.get(alert_key)
    if not alert_id:
        print(f"Alert ID not found for video {video_path} with key {alert_key}")
        return "OK", 200
    video_url = get_video_url(video_path)
    ALERT_STREAM.ingest(alert_id, "alert-video", {"video_url": video_url})
    state = ALERT_STREAM.get_state(alert_id, "alert")
    msg, tool_res = model.chat(
        state["summary"],
        video_url=video_url,
        using_tools=using_tools,
        system_prompt=prompts.video_analysis_prompt,
        tool_loop=False,
    )
    tool_res = json.loads(tool_res)
    print(msg)

    reason = tool_res.get("corrected_analysis", "无")
    suggestion = tool_res.get("recommendation", "无")
    tag = tool_res.get("abnormal_segments")

    print(reason)
    print(suggestion)
    print(tag)

    ALERT_STREAM.ingest(
        alert_id,
        "alert-llm",
        {
            "reason": reason,
            "suggestion": suggestion,
            "tag": tag,
            "cancel": not tool_res["is_system_correct"],
        },
    )
    with ALERT_STREAM.persisting(alert_id):
        helper = get_helper()
        if tool_res["is_system_correct"]:
            helper.update_alert(alert_id, reason, suggestion, video_url, tag)
        else:
            helper.remove_alert(alert_id)
        helper.close()
        alert_map.pop(alert_key, None)
    return "OK", 200


@bp.route("/api/alerts", methods=["GET"])
def get_alerts():
    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=20, type=int)
    helper = get_helper()
    if "seat_id" in request.args:
        seat_id = request.args.get("seat_id", type=int)
        alerts = helper.get_alerts_by_seat_id(seat_id, page=page, page_size=page_size)
    else:
        alerts = helper.get_all_alerts(page=page, page_size=page_size)
    helper.close()
    return jsonify(alerts)


@bp.route("/api/alerts/<alert_id>", methods=["GET"])
def get_alerts_by_alert_id(alert_id):
    helper = get_helper()
    alert = helper.get_alert_by_alert_id(alert_id)
    helper.close()
    return jsonify(alert)


@bp.route("/api/alerts/<alert_id>/settle", methods=["POST"])
def settle_alert(alert_id):
    helper = get_helper()
    helper.settle_alert(alert_id)
    helper.close()
    return jsonify({"status": "success"}), 200


def _format_sse(event_name, payload, event_id=None):
    message = ""
    if event_id is not None:
        message += f"id: {event_id}\n"
    message += f"event: {event_name}\n"
    message += f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"
    return message


@bp.route("/api/alerts/now", methods=["GET"])
def stream_alert_now():
    def generate():
        snapshot_events, cursor = ALERT_STREAM.open_stream_snapshot()
        for event in snapshot_events:
            yield _format_sse(
                event_name=event["event_name"],
                payload=event["payload"],
                event_id=f"snapshot-{event['alert_id']}-{event['event_name']}",
            )

        while True:
            events, latest_seq = ALERT_STREAM.wait_for_events(
                cursor, timeout_seconds=25
            )
            if not events:
                yield ": keepalive\n\n"
                cursor = latest_seq
                continue

            for event in events:
                yield _format_sse(
                    event_name=event["event_name"],
                    payload=event["payload"],
                    event_id=event["seq"],
                )
            cursor = latest_seq

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(
        stream_with_context(generate()), headers=headers, mimetype="text/event-stream"
    )
