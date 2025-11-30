from typing import List
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionMessage


class Context:
    def __init__(self, base_url: str, api_key: str):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.messages: List[ChatCompletionMessageParam] = []

    def addMessage(self, message: ChatCompletionMessageParam |
                   ChatCompletionMessage) -> None:
        self.messages.append(message)

    def clear(self):
        self.messages = []

    def printMessage(self) -> None:
        for message in self.messages:
            Context.print_msg(message)

    @staticmethod
    def print_msg(message):
        if isinstance(message, ChatCompletionMessage):
            role = message.role
            content = message.content
            tool_calls = message.tool_calls
            Context._show_content(role, content)
            if tool_calls:
                for idx, tc in enumerate(tool_calls, start=1):
                    if tc.type == "function":
                        name, argument = tc.function.name, tc.function.arguments
                        print(f"  -> tool_call #{idx}: {name}({argument})")
                    else:
                        print(f"  -> tool_call #{idx}: type={tc.type}")
        else:
            role = message.get("role", "unknown")
            content = message.get("content")
            tool_calls = message.get("tool_calls") or []
            tcid = message.get("tool_call_id")
            Context._show_content(role, content)
            if role == "assistant":
                if isinstance(tool_calls, list) and tool_calls:
                    for idx, tc in enumerate(tool_calls, start=1):
                        tc_type = tc.get("type")
                        if tc_type == "function":
                            fn = tc.get("function", {})
                            name = fn.get("name", "")
                            args = fn.get("arguments", "")
                            print(f"  -> tool_call #{idx}: {name}({args})")
                        else:
                            print(f"  -> tool_call #{idx}: type={tc_type}")
            elif role == "tool":
                if tcid:
                    print(f"  <- tool_result for {tcid}")

    @staticmethod
    def _show_content(role, content):
        rendered_content = ""
        if isinstance(content, str):
            rendered_content = content
        elif isinstance(content, list):
            parts = []
            for part in content:
                ptype = part.get("type")
                if ptype == "text":
                    parts.append(part.get("text", ""))
                elif ptype == "image_url":
                    parts.append("[image]")
                elif ptype == "input_audio":
                    parts.append("[audio]")
                else:
                    parts.append(f"[{ptype or 'part'}]")
            rendered_content = " ".join([p for p in parts if p])
        else:
            rendered_content = "" if content is None else str(content)

        header = f"[{role}]"
        if rendered_content:
            print(f"{header} {rendered_content}")
        else:
            print(header)
