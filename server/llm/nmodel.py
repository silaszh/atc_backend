import os

import openai
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from dotenv import load_dotenv
from ..pg_helper import get_helper

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
        print(messages)
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

        with ctx:
            ctx.append(msg)
            res = self._chat_api(ctx.messages, using_tools)

            # while res.choices[0].message.tool_calls:
            #     ctx.append(res.choices[0].message)
            #     # print("工具调用：" + ",".join(tc.function.name for tc in res.choices[0].message.tool_calls))
            #     for tool_call in res.choices[0].message.tool_calls:
            #         result = tc.handle_tool_calls(tool_call)
            #         ctx.append(
            #             {
            #                 "role": "tool",
            #                 "tool_call_id": tool_call.id,
            #                 "content": result,
            #             }
            #         )
            #     res = self._chat_api(ctx.messages, using_tools)

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

        with ctx:
            ctx.append(msg)
            stream = self._chat_api(ctx.messages, using_tools, stream=True)
            content = ""
            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason is None:
                    content += delta.content
                    yield delta.content
                else:
                    print("")
                    print(choice.finish_reason)
                    print(delta)
            # while res.choices[0].message.tool_calls:
            #     ctx.append(res.choices[0].message)
            #     # print("工具调用：" + ",".join(tc.function.name for tc in res.choices[0].message.tool_calls))
            #     for tool_call in res.choices[0].message.tool_calls:
            #         result = tc.handle_tool_calls(tool_call)
            #         ctx.append(
            #             {
            #                 "role": "tool",
            #                 "tool_call_id": tool_call.id,
            #                 "content": result,
            #             }
            #         )
            #     res = self._chat_api(ctx.messages, using_tools)
            msg = format_assistant_message(
                ChatCompletionMessage(role="assistant", content=content)
            )
            ctx.append(msg)
        return

    def chat_on(self, chat_id, message, img_url=None, video_url=None, using_tools=None):
        ctx = self.contexts.get(chat_id)
        if ctx is None:
            ctx = self._load_chat(chat_id)
        return self._chat(ctx, message, img_url, video_url, using_tools)

    def chat(self, message, img_url=None, video_url=None, using_tools=None):
        ctx = Context(-1, sync_with_db=False)
        return self._chat(ctx, message, img_url, video_url, using_tools)

    def stream_chat_on(
        self, chat_id, message, img_url=None, video_url=None, using_tools=None
    ):
        ctx = self.contexts.get(chat_id)
        if ctx is None:
            ctx = self._load_chat(chat_id)
        return self._stream_chat(ctx, message, img_url, video_url, using_tools)

    def stream_chat(self, message, img_url=None, video_url=None, using_tools=None):
        ctx = Context(-1, sync_with_db=False)
        return self._stream_chat(ctx, message, img_url, video_url, using_tools)


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
