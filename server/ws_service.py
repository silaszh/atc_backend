from flask import request
from flask_socketio import SocketIO

from .data_store import online_seat, pending_answers
from .pg_helper import get_helper

# 初始化不绑定 app 的 SocketIO
socketio = SocketIO(cors_allowed_origins="*")

# current_warnings = set()
# current_dangers = set()
# @socketio.on("connect")
# def handle_connect():
#     if current_warnings:
#         socketio.emit("warning_update", list(current_warnings), to=request.sid)
#     if current_dangers:
#         socketio.emit("danger_update", list(current_dangers), to=request.sid)


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
