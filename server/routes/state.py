from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from ..pg_helper import get_helper

bp = Blueprint("state", __name__)


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
    # TODO
    print("Received webhook request")
    print(request.json)     
    data = request.get_json()
    print(data["Key"])
    return "OK", 200
