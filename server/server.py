import base64
import json
import sys
import os
import re
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from flask import Flask, request, jsonify, Response, redirect
from flask_socketio import SocketIO

# from llm.model import Model as OldModel
from .llm.nmodel import Model
from llm import prompts
from mongo_helper import get_default_helper

# 设置静态文件目录
app = Flask(__name__, static_folder="../static", static_url_path="/")
socketio = SocketIO(app, cors_allowed_origins="*")

# model = Model(os.getenv("API_BASE_URL"), os.getenv("API_KEY"))
model = Model("mimo-v2-flash")

# v_model = OldModel(os.getenv("API_BASE_URL"), os.getenv("API_KEY"))
# v_model.using_model = v_model.models["GLM"]

# 全局状态存储
current_warnings = set()
current_dangers = set()


@socketio.on("connect")
def handle_connect():
    if current_warnings:
        socketio.emit("warning_update", list(current_warnings), to=request.sid)
    if current_dangers:
        socketio.emit("danger_update", list(current_dangers), to=request.sid)


# 大模型相关请求


def parse_analysis_result(msg):
    # 清理可能的代码块标记
    clean_msg = re.sub(r"^```\w*\s*|\s*```$", "", msg.strip(), flags=re.MULTILINE)

    result = {
        "level_code": 0,
        "level_name": "未知",
        "json_analysis": "",
        "image_analysis": "",
        "conclusion": "",
        "raw_message": msg,
    }

    # 匹配至少3个连续的 - 或 _ 或 *，且前后可能有空白字符
    parts = re.split(r"\s*(?:---|___|\*\*\*)\s*", clean_msg)

    # 过滤空字符串
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) >= 4:
        # 解析第一部分：[等级序号]等级名称
        header = parts[0]
        # 尝试提取 [数字] 和 名称
        match = re.match(r"\[(\d+)\]\s*(.*)", header)
        if match:
            result["level_code"] = int(match.group(1))
            result["level_name"] = match.group(2)
        else:
            # 备用匹配：查找任何 [数字]
            match = re.search(r"\[(\d+)\]", header)
            if match:
                result["level_code"] = int(match.group(1))
                # 假设剩下的就是名称
                result["level_name"] = header.replace(match.group(0), "").strip()
            else:
                result["level_name"] = header

        result["json_analysis"] = parts[1]
        result["image_analysis"] = parts[2]
        result["conclusion"] = parts[3]

    return result


# @app.route("/api/analysis/<person_id>", methods=["POST"])
# def create_analysis(person_id):
#     if person_id not in latest_frames:
#         return jsonify({"online": False})

#     helper = get_default_helper()
#     recent_logs = helper.get_state_logs_by_person_id(person_id, limit=10)
#     helper.close()

#     log_data_list = []
#     for log in recent_logs:
#         if "_id" in log:
#             del log["_id"]
#         if "timestamp" in log:
#             log["timestamp"] = str(log["timestamp"])
#         log_data_list.append(log)

#     frame_data = latest_frames[person_id]
#     img = base64.b64encode(frame_data).decode("utf-8")
#     data = json.dumps(log_data_list)

#     chat_id = v_model.newContext(prompts.analyse_prompt)
#     print(data)
#     msg = v_model.chatWithImg(chat_id, data, img)
#     v_model.deleteContext(chat_id)

#     analysis_result = parse_analysis_result(msg)
#     print(analysis_result)
#     return jsonify({"online": True, "analysis": analysis_result})


@app.route("/", methods=["GET"])
def index():
    return app.send_static_file("index.html")


@app.errorhandler(404)
def page_not_found(e):
    return app.send_static_file("index.html")


def emotion_update_task():
    """Background task to push emotion updates to frontend."""
    global current_warnings, current_dangers
    while True:
        online_ids = list(latest_frames.keys())
        if online_ids:
            try:
                helper = get_default_helper()
                employees_data = helper.get_recent_logs_for_employees(online_ids)
                helper.close()

                new_warnings = []
                new_dangers = []
                for emp in employees_data:
                    logs = emp.get("logs", [])

                    # 统计空数据（离岗）的数量
                    empty_count = sum(
                        1
                        for log in logs
                        if not any(
                            log.get(k) not in ["", None]
                            for k in ["emo_label", "ear", "mar", "pose"]
                        )
                    )

                    if empty_count > 3:
                        new_dangers.append(emp["id"])

                    # 统计 sleepy 的数量
                    negative_count = sum(
                        1 for log in logs if log.get("emo_label") in ["sleepy", "bored"]
                    )

                    # 统计 ear < 0.2 的数量
                    low_ear_count = sum(
                        1
                        for log in logs
                        if isinstance(log.get("ear"), (int, float))
                        and log.get("ear") < 0.2
                    )

                    # 统计 mar > 0.5 的数量
                    high_mar_count = sum(
                        1
                        for log in logs
                        if isinstance(log.get("mar"), (int, float))
                        and log.get("mar") > 0.5
                    )

                    # 统计 pose[0] abs > 30 的数量
                    abnormal_pose_count = sum(
                        1
                        for log in logs
                        if log.get("pose")
                        and isinstance(log["pose"], list)
                        and len(log["pose"]) > 0
                        and abs(log["pose"][0]) > 30
                    )

                    if (
                        negative_count > 3
                        or low_ear_count > 3
                        or high_mar_count > 3
                        or abnormal_pose_count > 3
                    ):
                        new_warnings.append(emp["id"])

                # 比较状态变化
                new_warnings_set = set(new_warnings)
                new_dangers_set = set(new_dangers)

                added_warnings = list(new_warnings_set - current_warnings)
                lifted_warnings = list(current_warnings - new_warnings_set)

                added_dangers = list(new_dangers_set - current_dangers)
                lifted_dangers = list(current_dangers - new_dangers_set)

                current_warnings = new_warnings_set
                current_dangers = new_dangers_set

                if added_warnings:
                    socketio.emit("warning_update", added_warnings)
                if lifted_warnings:
                    socketio.emit("warning_lift", lifted_warnings)

                if added_dangers:
                    socketio.emit("danger_update", added_dangers)
                if lifted_dangers:
                    socketio.emit("danger_lift", lifted_dangers)

            except Exception as e:
                print(f"Error in emotion update task: {e}")
            socketio.sleep(5)
        else:
            socketio.sleep(1)


from .routes.model import bp as model_bp
from .routes.seat import bp as seat_bp
from .routes.state import bp as state_bp
from .ws_service import socketio as wss

wss.init_app(app)

app.register_blueprint(model_bp)
app.register_blueprint(seat_bp)
app.register_blueprint(state_bp)

if os.environ.get("WERKZEUG_RUN_MAIN"):
    socketio.start_background_task(emotion_update_task)
