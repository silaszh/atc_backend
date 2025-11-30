import json
import sys
import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))
from flask import Flask, request, jsonify, Response

from llm.model import Model
from llm import prompts
from socket_server import latest_frames, init_socket_server
from mongo_helper import get_default_helper

# 将静态文件目录保持为原设置（views 路由已可配置）；不影响 /webrtc 页面
app = Flask(__name__, static_folder="../static", static_url_path="/")

model = Model(os.getenv("API_BASE_URL"), os.getenv("API_KEY"))

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
            time.sleep(0.1)  # 控制帧率

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
        msg = model.chat(chat_id, data["message"])
        return jsonify({"message": msg})
    else:
        return jsonify({"error": "Invalid input"}), 400


@app.route("/api/inferences", methods=["POST"])
def create_inference():
    if request.is_json:
        data = request.get_json()
        chat_id = model.newContext(prompts.infer_prompt)
        msg = model.chat(chat_id, json.dumps(data))
        model.deleteContext(chat_id)
        return jsonify({"status": msg})
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


if os.environ.get("WERKZEUG_RUN_MAIN"):
    init_socket_server()
