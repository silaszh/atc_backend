import time
from flask import Blueprint, Response, request, jsonify

from ..llm.nmodel import Model
from ..llm import prompts

from ..pg_helper import get_helper

bp = Blueprint("model", __name__)

model = Model("ZhipuAI/GLM-4.7-Flash")


def sse_event(data, event="message"):
    return f"event: {event}\ndata: {data}\n\n"


def sse_wrapper(chat_id, message, new_chat=False):
    if new_chat:
        yield sse_event(chat_id, "chat_id")
    start = time.time()
    stream = model.stream_chat_on(chat_id, message)
    for text in stream:
        yield sse_event(text)
    if new_chat:
        yield sse_event(model.summarize_chat(chat_id), "summary")
    yield sse_event(time.time() - start, "close")


@bp.route("/api/chats", methods=["GET"])
def get_chats():
    helper = get_helper()
    chats = helper.get_chats()
    helper.close()
    return jsonify(chats)


@bp.route("/api/chats", methods=["POST"])
def create_chat():
    chat_id = model.new_chat(system_prompt=prompts.chat_prompt)
    if request.is_json:
        data = request.get_json()
        if isinstance(data["prompt"], str):
            return Response(
                sse_wrapper(chat_id, data["prompt"], new_chat=True),
                mimetype="text/event-stream",
            )
    return jsonify({"chat_id": chat_id})


@bp.route("/api/chats/<chat_id>/messages", methods=["GET"])
def get_messages(chat_id):
    helper = get_helper()
    messages = helper.get_msg_of_chat(chat_id)
    helper.close()
    return jsonify(messages)


@bp.route("/api/chats/<chat_id>/messages", methods=["POST"])
def send_message(chat_id):
    if request.is_json:
        data = request.get_json()
        if isinstance(data["prompt"], str):
            return Response(
                sse_wrapper(int(chat_id), data["prompt"]),
                mimetype="text/event-stream",
            )
    return jsonify({"error": "Invalid input"}), 400
