import json
import sys
import os
from datetime import datetime
from openai.types.chat import ChatCompletionMessageFunctionToolCall

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from mongo_helper import get_default_helper

tools = []
toolsMap = {}


def handle_tool_calls(tc: ChatCompletionMessageFunctionToolCall):
    print(tc.function.name, tc.function.arguments)
    result = toolsMap[tc.function.name](**json.loads(tc.function.arguments))
    import pprint

    pprint.pprint(result)
    return json.dumps(result, ensure_ascii=False)


class Tool:
    def __init__(self, desc, *params):
        self.desc = desc
        self.parameters = []
        for p in params:
            self.param(*p)

    def param(self, name: str, description: str, type="string", required=True):
        self.parameters.append(
            {
                "name": name,
                "type": type,
                "description": description,
                "required": required,
            }
        )
        return self

    def __call__(self, tool_func):
        params = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        for p in self.parameters:
            params["properties"][p.get("name")] = {
                "type": p.get("type"),
                "description": p.get("description"),
            }
            if p.get("required"):
                params["required"].append(p.get("name"))
        tool_config = {
            "type": "function",
            "function": {
                "name": tool_func.__name__,
                "description": self.desc,
                "parameters": params,
            },
        }
        tools.append(tool_config)
        toolsMap[tool_func.__name__] = tool_func
        return tool_func


@Tool(
    """
    根据员工名获取最近一次记录的连续五次参考效价唤醒模型的情绪数据，其中：
    - emo_va包括valence值，区间(-1, 1)和arousal值，区间(-1, 1)的平均值
    - emo_label为系统推断的主要情绪，非常具有参考价值但并非总是正确
    - pose为画面中员工所在的位置信息
    - ear和mar为面部表情相关的指标，连续五次分析中眼睛和嘴巴开合度的平均值。你可以通过开合度预测是否处于临近睡眠状态（眯眼、打哈欠等行为）
    - time为此次记录的系统时间，你可以与当前时间进行比较，如果时间差异大则说明员工暂未上线，数据参考价值有限
    当员工不存在时，success字段为false，
    若员工存在但所有数据为空，则说明最近一次记录时员工离岗
""",
    ("employee_name", "员工姓名"),
)
def get_state(employee_name):
    helper = get_default_helper()
    person = helper.get_person_by_name(employee_name)
    if person:
        # log = helper.get_latest_state_log(person["id"])
        logs = helper.get_state_logs_by_person_id(person["id"], limit=5)
        helper.close()

        data = []
        for log in logs:
            data.append(
                {
                    "id": person["id"],
                    "name": person.get("name"),
                    "age": person.get("age"),
                    "ear": log.get("ear", 0),
                    "mar": log.get("mar", 0),
                    "emo_label": log.get("emo_label", ""),
                    "emo_va": log.get("emo_va", []),
                    "pose": log.get("pose", []),
                    "time": log.get("timestamp", ""),
                }
            )
        return {
            "success": True,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data,
        }
    else:
        return {"success": False}


@Tool(
    """
获取所有员工最近一次的情绪状态数据，包括ear、mar、emo，
ear和mar为面部表情相关的指标，连续五次分析中眼睛和嘴巴开合度的平均值，
emo_label为系统初步推断的主要情绪。
如果一位员工数据异常，均为空。
"""
)
def get_all_states():
    helper = get_default_helper()
    persons = helper.get_all_persons()
    data = []
    for person in persons:
        person_id = person["id"]
        log = helper.get_latest_state_log(person_id)
        if not log:
            data.append(
                {"name": person.get("name"), "ear": 0, "mar": 0, "emo_label": ""}
            )
            continue
        ear = log.get("ear", 0)
        mar = log.get("mar", 0)
        emo_label = log.get("emo_label", "")
        data.append(
            {"name": person.get("name"), "ear": ear, "mar": mar, "emo_label": emo_label}
        )
    helper.close()
    return {"success": True, "data": data}


@Tool(
    """
获取特定员工最近10次记录的情绪数据，其中：
- emo_va包括valence值，区间(-1, 1)和arousal值，区间(-1, 1)的平均值
- emo_label为系统推断的主要情绪，非常具有参考价值但并非总是正确
- pose为画面中员工所在的位置信息
- ear和mar为面部表情相关的指标，连续五次分析中眼睛和嘴巴开合度的平均值。你可以通过开合度预测是否处于临近睡眠状态（眯眼、打哈欠等行为）
当员工不存在时，success字段为false，
若员工存在但所有数据为空，则说明最近一次记录时员工离岗
""",
    ("employee_name", "员工姓名"),
)
def get_state_trend(employee_name):
    helper = get_default_helper()
    person = helper.get_person_by_name(employee_name)
    if person:
        logs = helper.get_state_logs_by_person_id(person["id"], limit=50)
        helper.close()

        data = []
        for log in logs:
            data.append(
                {
                    "id": person["id"],
                    "name": person.get("name"),
                    "age": person.get("age"),
                    "ear": log.get("ear", 0),
                    "mar": log.get("mar", 0),
                    "emo_label": log.get("emo_label", ""),
                    "emo_va": log.get("emo_va", []),
                    "pose": log.get("pose", []),
                    "time": log.get("timestamp", ""),
                }
            )
        return {
            "success": True,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data,
        }
    else:
        return {"success": False}
