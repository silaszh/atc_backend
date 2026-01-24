from threading import Event
import time
import uuid
from flask import Blueprint, request, jsonify

from ..data_store import online_seat, pending_answers
from ..pg_helper import get_helper
from ..ws_service import socketio

bp = Blueprint("seat", __name__)


@bp.route("/api/seats", methods=["GET"])
def get_seats():
    helper = get_helper()
    seats = helper.get_all_seats()
    seats_info = []
    for seat in seats:
        online = online_seat.get(seat[0]) is not None
        seats_info.append(
            {
                "seat_id": seat[0],
                "name": seat[1],
                "online": online,
                "last_login_time": seat[2],
            }
        )
    helper.close()
    return jsonify(seats_info)


@bp.route("/api/offer", methods=["POST"])
def offer():
    print(time.time(), "Received offer")
    if not request.is_json:
        return jsonify({"error": "expected json"}), 400

    offer_data = request.get_json()
    target_seat_id = offer_data.get("seat_id", 0)

    seat_sid = online_seat.get(target_seat_id)
    if not seat_sid:
        return jsonify({"error": f"Seat {target_seat_id} not online"}), 404
    # 生成唯一请求ID 与 Event 等待 seat 回应
    request_id = str(uuid.uuid4())
    completion_event = Event()

    pending_answers[request_id] = {"event": completion_event, "data": None}

    try:
        # offer 转发
        socketio.emit(
            "offer",
            {
                "sdp": offer_data["sdp"],
                "type": offer_data.get("type", "offer"),
                "sid": request_id,
            },
            to=seat_sid,
        )

        # 阻塞等待 Answer
        if completion_event.wait(timeout=10):
            answer_data = pending_answers[request_id]["data"]
            if answer_data:
                return jsonify({"sdp": answer_data["sdp"], "type": answer_data["type"]})
            else:
                return jsonify({"error": "Empty answer received"}), 500
        else:
            return jsonify({"error": "Timeout waiting for device answer"}), 504

    finally:
        # 清理
        if request_id in pending_answers:
            del pending_answers[request_id]


# @bp.route("/api/states", methods=["POST"])
# def create_state():
#     if request.is_json:
#         data = request.get_json()
#         if "id" not in data:
#             return jsonify({"error": "Missing id"}), 400

#         helper = get_default_helper()
#         person_id = data["id"]
#         person = helper.get_person_by_id(person_id)

#         log_data = {k: v for k, v in data.items() if k not in ["name", "age", "id"]}
#         if "time" in log_data:
#             log_data["timestamp"] = log_data.pop("time")
#         log_data["person_id"] = person_id

#         if not person:
#             person_data = {
#                 "id": person_id,
#                 "name": data.get("name"),
#                 "age": data.get("age"),
#             }
#             helper.create_person(person_data)
#         helper.insert_state_log(log_data)

#         helper.close()
#         return jsonify({"status": "success"}), 200
#     else:
#         return jsonify({"error": "Invalid input"}), 400
