import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from llm.context import Context
import llm.tc as tc


class Model:
    def __init__(self, base_url: str, api_key: str):
        self.models = {
            "ds-v3": "deepseek-v3",
            "ds-r1": "deepseek-r1-671b",
            "qw2.5": "qwen2.5-instruct",
            "qwq": "QwQ-32B",
            "qw3": "qwen3",
            "qw3:8b": "Qwen3-8B",
            "mimo": "mimo-v2-flash",
            "GLM": "GLM-4.1V-Thinking-Flash",
        }
        self.using_model = self.models["mimo"]
        self.base_url = base_url
        self.api_key = api_key
        self.contexts: list[Context] = []

    def newContext(self, sys_prompt: str = None):
        chat_id = len(self.contexts)
        ctx = Context(self.base_url, self.api_key)
        if sys_prompt:
            ctx.addMessage({"role": "system", "content": sys_prompt})
        self.contexts.append(ctx)
        return chat_id

    def chat(self, chat_id: int, msg: str):
        ctx = self.contexts[chat_id]
        ctx.addMessage({"role": "user", "content": msg})
        res = ctx.client.chat.completions.create(
            model=self.using_model,
            messages=ctx.messages,
            tools=tc.tools,
            tool_choice="auto",
        )
        while res.choices[0].message.tool_calls:
            ctx.addMessage(res.choices[0].message)
            print("工具调用：" + ",".join(res.choices[0].message.tool_calls))
            tool_call = res.choices[0].message.tool_calls[0]
            result = tc.handle_tool_calls(tool_call)
            ctx.addMessage(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result}
            )
            res = ctx.client.chat.completions.create(
                model=self.using_model, messages=ctx.messages
            )
        ctx.addMessage(res.choices[0].message)
        return res.choices[0].message.content

    def chatWithImg(self, chat_id: str, msg: str, img: str):
        ctx = self.contexts[chat_id]
        ctx.addMessage(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": msg},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"},
                    },
                ],
            }
        )
        res = ctx.client.chat.completions.create(
            model=self.using_model,
            messages=ctx.messages,
            tools=tc.tools,
            tool_choice="auto",
        )
        while res.choices[0].message.tool_calls:
            ctx.addMessage(res.choices[0].message)
            print("工具调用：" + ",".join(res.choices[0].message.tool_calls))
            tool_call = res.choices[0].message.tool_calls[0]
            result = tc.handle_tool_calls(tool_call)
            ctx.addMessage(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result}
            )
            res = ctx.client.chat.completions.create(
                model=self.using_model, messages=ctx.messages
            )
        ctx.addMessage(res.choices[0].message)
        return res.choices[0].message.content

    def deleteContext(self, chat_id: int):
        if 0 <= chat_id < len(self.contexts):
            del self.contexts[chat_id]
