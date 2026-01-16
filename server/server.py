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

from llm.model import Model
from llm import prompts
from socket_server import latest_frames, init_socket_server
from mongo_helper import get_default_helper

# 设置静态文件目录
app = Flask(__name__, static_folder="../static", static_url_path="/")
socketio = SocketIO(app, cors_allowed_origins="*")

model = Model(os.getenv("API_BASE_URL"), os.getenv("API_KEY"))

v_model = Model(os.getenv("API_BASE_URL"), os.getenv("API_KEY"))
v_model.using_model = v_model.models["GLM"]

# 全局状态存储
current_warnings = set()
current_dangers = set()


@socketio.on("connect")
def handle_connect():
    if current_warnings:
        socketio.emit("warning_update", list(current_warnings), to=request.sid)
    if current_dangers:
        socketio.emit("danger_update", list(current_dangers), to=request.sid)


# 摄像头相关请求


@app.route("/api/streams/<camera_id>")
def get_stream(camera_id):
    if not camera_id:
        return Response("", mimetype="multipart/x-mixed-replace; boundary=frame")

    def generate():
        global latest_frames
        import time

        while True:
            frame_data = latest_frames.get(camera_id)
            if frame_data:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n"
                )
            time.sleep(0.001)  # 控制帧率

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


# 大模型相关请求


@app.route("/api/chats", methods=["POST"])
def create_chat():
    chat_id = model.newContext(prompts.chat_prompt)
    return jsonify({"chat_id": chat_id})


@app.route("/api/chats/<chat_id>/messages", methods=["POST"])
def send_message(chat_id):
    if request.is_json:
        data = request.get_json()
        print(data)
        msg = model.chat(int(chat_id), data["message"])
        return jsonify({"message": msg})
    else:
        return jsonify({"error": "Invalid input"}), 400


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


@app.route("/api/analysis/<person_id>", methods=["POST"])
def create_analysis(person_id):
    if person_id not in latest_frames:
        return jsonify({"online": False})

    helper = get_default_helper()
    recent_logs = helper.get_state_logs_by_person_id(person_id, limit=10)
    helper.close()

    log_data_list = []
    for log in recent_logs:
        if "_id" in log:
            del log["_id"]
        if "timestamp" in log:
            log["timestamp"] = str(log["timestamp"])
        log_data_list.append(log)

    frame_data = latest_frames[person_id]
    img = base64.b64encode(frame_data).decode("utf-8")
    data = json.dumps(log_data_list)

    chat_id = v_model.newContext(prompts.analyse_prompt)
    print(data)
    msg = v_model.chatWithImg(chat_id, data, img)
    v_model.deleteContext(chat_id)

    analysis_result = parse_analysis_result(msg)
    print(analysis_result)
    return jsonify({"online": True, "analysis": analysis_result})


@app.route("/api/inferences", methods=["POST"])
def create_inference():
    if request.is_json:
        data = request.get_json()
        chat_id = model.newContext(prompts.infer_prompt)
        msg = model.chat(chat_id, json.dumps(data))
        model.deleteContext(chat_id)
        return jsonify({"state": msg})
    else:
        return jsonify({"error": "Invalid input"}), 400


# 数据库相关请求


@app.route("/api/employees", methods=["GET"])
def get_employees():
    helper = get_default_helper()
    persons = helper.get_all_persons()
    employees = []
    for person in persons:
        online = latest_frames.get(person["id"]) is not None
        employees.append(
            {
                "id": person["id"],
                "name": person.get("name"),
                "online": online,
                "last_login_time": person.get("last_login_time"),
            }
        )
    helper.close()
    return jsonify(employees)


@app.route("/api/employees/<person_id>", methods=["GET"])
def get_employee(person_id):
    helper = get_default_helper()
    person = helper.get_person_by_id(person_id)
    helper.close()

    if person:
        return jsonify(
            {
                "id": person["id"],
                "name": person.get("name"),
                "age": person.get("age"),
                "avatar": person.get("avatar", "/logo.png"),
                "last_login_time": person.get("last_login_time"),
            }
        )
    else:
        return jsonify({"error": "Person not found"}), 404


@app.route("/api/states", methods=["POST"])
def create_state():
    if request.is_json:
        data = request.get_json()
        if "id" not in data:
            return jsonify({"error": "Missing id"}), 400

        helper = get_default_helper()
        person_id = data["id"]
        person = helper.get_person_by_id(person_id)

        # 准备日志数据：删除 name、age 和 id，并将 time 改为 timestamp，添加 person_id
        log_data = {k: v for k, v in data.items() if k not in ["name", "age", "id"]}
        if "time" in log_data:
            log_data["timestamp"] = log_data.pop("time")
        log_data["person_id"] = person_id

        if not person:
            # 不存在，创建 person，并插入 state_logs
            person_data = {
                "id": person_id,
                "name": data.get("name"),
                "age": data.get("age"),
            }
            helper.create_person(person_data)
        helper.insert_state_log(log_data)

        helper.close()
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"error": "Invalid input"}), 400


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


if os.environ.get("WERKZEUG_RUN_MAIN"):
    init_socket_server()
    socketio.start_background_task(emotion_update_task)
