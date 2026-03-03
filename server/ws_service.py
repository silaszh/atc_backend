from datetime import datetime, timezone

from flask import request
from flask_socketio import SocketIO

from .data_store import online_seat, pending_answers, alert_map
from .pg_helper import get_helper
from .alert_stream import ALERT_STREAM

# 初始化不绑定 app 的 SocketIO
socketio = SocketIO(cors_allowed_origins="*")


@socketio.on("checkin")
def checkin(data):
    """
    边缘计算设备签到，更新login_time
    """
    print(f"Device checkin: {data}")
    seat_id = data.get("seat_id")
    if seat_id:
        online_seat[seat_id] = request.sid
        helper = get_helper()
        helper.update_login_time(seat_id)
        helper.close()
        print(f"Device {seat_id} registered with sid {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    disconnect_sid = request.sid
    print(f"Client disconnected: {disconnect_sid}")

    for seat_id, sid in list(online_seat.items()):
        if sid == disconnect_sid:
            # 双重检查：确保当前内存中的 sid 仍然是断开连接的那个 sid
            if online_seat.get(seat_id) == disconnect_sid:
                del online_seat[seat_id]
                print(f"Device {seat_id} disconnected and removed from online_seat")
            break


@socketio.on("answer")
def handle_answer_from_device(data):
    """
    边缘计算设备发回 answer，data 结构: { "sdp": ..., "type": ..., "sid": "user_request_uuid" }
    """
    request_id = data.get("sid")
    if request_id in pending_answers:
        pending_answers[request_id]["data"] = data
        pending_answers[request_id]["event"].set()


@socketio.on("alert")
def handle_alert(data):
    # * { "seat_id": ..., "timestamp": ..., "summary": ..., "level": ... }
    helper = get_helper()
    alert_id = helper.insert_alert(
        seat_id=data.get("seat_id"),
        timestamp=datetime.fromtimestamp(data.get("timestamp"), timezone.utc),
        summary=data.get("summary"),
        level=data.get("level"),
    )
    helper.close()
    alert_map[f"seat{data.get('seat_id')}_{data.get('timestamp')}"] = alert_id
    ALERT_STREAM.ingest(alert_id, "alert", data)
    print(f"Received alert from device: {data}")
