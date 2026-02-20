import json
import os

import openai
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_message_function_tool_call import Function

from dotenv import load_dotenv
from ..pg_helper import get_helper
from . import prompts
from .tools import tool_scheme

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")


class Context:
    def __init__(self, chat_id, sync_with_db=True):
        self.chat_id = chat_id
        self.sync_with_db = sync_with_db
        self.messages = []
        self.helper = None

    def append(self, message):
        if self.helper:
            self.helper.append_msg_to_chat(self.chat_id, message)
        self.messages.append(message)

    def __enter__(self):
        if self.sync_with_db:
            self.helper = get_helper()
        return self.messages

    def __exit__(self, type, value, trace):
        if self.helper:
            self.helper.update_chat(self.chat_id)
            self.helper.close()


class Model:
    def __init__(self, model_name, base_url=API_BASE_URL, api_key=API_KEY):
        self.base_url = base_url
        self.api_key = api_key
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
        )

        self.model_name = model_name
        self.contexts = {}
        self.multi = False

    def new_chat(self, system_prompt=None):
        helper = get_helper()
        chat_id = helper.create_chat()
        self.contexts[chat_id] = Context(chat_id)
        if system_prompt:
            msg = {"role": "system", "content": system_prompt}
            self.contexts[chat_id].append(msg)
            helper.append_msg_to_chat(chat_id, msg)
        helper.close()
        return chat_id

    def _load_chat(self, chat_id):
        helper = get_helper()
        messages = helper.get_msg_of_chat(chat_id)
        ctx = Context(chat_id)
        ctx.messages = messages
        # print(messages)
        return ctx

    def _chat_api(self, messages, using_tools=None, stream=False):
        return self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=using_tools,
            tool_choice="auto" if using_tools else None,
            stream=stream,
        )

    def _chat(
        self, ctx: Context, message, img_url=None, video_url=None, using_tools=None
    ):
        if self.multi:
            content = [{"type": "text", "text": message}]
            if img_url:
                content.append({"type": "image_url", "image_url": {"url": img_url}})
            if video_url:
                content.append({"type": "video_url", "video_url": {"url": video_url}})
                # content.append(
                #     {
                #         "type": "file",
                #         "file": {
                #             "file_id": video_url,
                #             "format": "video/mp4",
                #         },
                #     }
                # )
            msg = {"role": "user", "content": content}
        else:
            # 忽略 img_url, video_url
            msg = {"role": "user", "content": message}

        tool_map = {}
        tool_list = []
        for t in using_tools or []:
            scheme = tool_scheme(t)
            tool_map[scheme["function"]["name"]] = t
            tool_list.append(scheme)

        with ctx:
            ctx.append(msg)
            res = self._chat_api(ctx.messages, tool_list)
            print(res.choices[0].message)
            while res.choices[0].message.tool_calls:
                ctx.append(format_assistant_message(res.choices[0].message))
                print(
                    "工具调用："
                    + ",".join(
                        tc.function.name for tc in res.choices[0].message.tool_calls
                    )
                )
                for tool_call in res.choices[0].message.tool_calls:
                    result = tool_map[tool_call.function.name].invoke(
                        json.loads(tool_call.function.arguments)
                    )
                    ctx.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )
                res = self._chat_api(ctx.messages, tool_list)

            msg = format_assistant_message(res.choices[0].message)
            ctx.append(msg)
        return msg["content"]

    def _stream_chat(
        self, ctx: Context, message, img_url=None, video_url=None, using_tools=None
    ):
        if self.multi:
            content = [{"type": "text", "text": message}]
            if img_url:
                content.append({"type": "image_url", "image_url": {"url": img_url}})
            if video_url:
                content.append({"type": "video_url", "video_url": {"url": video_url}})
                # content.append(
                #     {
                #         "type": "file",
                #         "file": {
                #             "file_id": video_url,
                #             "format": "video/mp4",
                #         },
                #     }
                # )
            msg = {"role": "user", "content": content}
        else:
            # 忽略 img_url, video_url
            msg = {"role": "user", "content": message}

        tool_map = {}
        tool_list = []
        for t in using_tools or []:
            scheme = tool_scheme(t)
            tool_map[scheme["function"]["name"]] = t
            tool_list.append(scheme)

        with ctx:
            ctx.append(msg)
            while True:
                stream = self._chat_api(ctx.messages, tool_list, stream=True)
                content = ""
                calling_tools = []
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if delta and delta.content:
                        content += delta.content
                        yield ("message", delta.content)
                    if choice.finish_reason:
                        print(choice.finish_reason)
                    if delta and delta.tool_calls:
                        for tc in delta.tool_calls:
                            if tc.index >= len(calling_tools):
                                calling_tools.append(
                                    {
                                        "function": {
                                            "name": tc.function.name,
                                            "arguments": tc.function.arguments or "",
                                        },
                                        "id": tc.id,
                                        "type": tc.type,
                                    }
                                )
                                print("工具调用：" + str(tc.index))
                            else:
                                calling_tools[tc.index]["function"][
                                    "arguments"
                                ] += tc.function.arguments
                for tc in calling_tools:
                    print(tc)
                # 构建消息
                msg = format_assistant_message(
                    ChatCompletionMessage(
                        role="assistant",
                        content=content,
                        tool_calls=[
                            ChatCompletionMessageFunctionToolCall(
                                function=Function(
                                    name=tc["function"]["name"],
                                    arguments=tc["function"]["arguments"],
                                ),
                                id=tc["id"],
                                type=tc["type"],
                            )
                            for tc in calling_tools
                        ],
                    )
                )
                ctx.append(msg)
                # 处理工具调用
                for tool_call in calling_tools:
                    result = tool_map[tool_call["function"]["name"]].invoke(
                        json.loads(tool_call["function"]["arguments"])
                    )
                    yield ("tool", result)
                    ctx.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result,
                        }
                    )
                if not calling_tools:
                    print("没有工具调用，结束对话")
                    break
                yield ("sep", None)
        return msg["content"]

    def chat_on(self, chat_id, message, img_url=None, video_url=None, using_tools=None):
        ctx = self.contexts.get(chat_id)
        if ctx is None:
            ctx = self._load_chat(chat_id)
        return self._chat(ctx, message, img_url, video_url, using_tools)

    def chat(
        self,
        message,
        img_url=None,
        video_url=None,
        using_tools=None,
        system_prompt=None,
    ):
        ctx = Context(-1, sync_with_db=False)
        if system_prompt:
            ctx.messages.append({"role": "system", "content": system_prompt})
        return self._chat(ctx, message, img_url, video_url, using_tools)

    def stream_chat_on(
        self, chat_id, message, img_url=None, video_url=None, using_tools=None
    ):
        ctx = self.contexts.get(chat_id)
        if ctx is None:
            ctx = self._load_chat(chat_id)
        return self._stream_chat(ctx, message, img_url, video_url, using_tools)

    def stream_chat(
        self,
        message,
        img_url=None,
        video_url=None,
        using_tools=None,
        system_prompt=None,
    ):
        ctx = Context(-1, sync_with_db=False)
        if system_prompt:
            ctx.messages.append({"role": "system", "content": system_prompt})
        return self._stream_chat(ctx, message, img_url, video_url, using_tools)

    def summarize_chat(self, chat_id):
        ctx = self.contexts.get(chat_id)
        if ctx is None:
            ctx = self._load_chat(chat_id)
        content = json.dumps(ctx.messages)
        summary = self.chat(content, system_prompt=prompts.summarize_chat_prompt)
        pg_helper = get_helper()
        pg_helper.update_chat(chat_id, title=summary)
        pg_helper.close()
        return summary


def format_assistant_message(msg: ChatCompletionMessage):
    ret = {}
    ret["role"] = "assistant"
    ret["content"] = msg.content
    ret["tool_calls"] = []
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            ret["tool_calls"].append(
                {
                    "function": {
                        "arguments": tool_call.function.arguments,
                        "name": tool_call.function.name,
                    },
                    "id": tool_call.id,
                    "type": tool_call.type,
                }
            )
    return ret
