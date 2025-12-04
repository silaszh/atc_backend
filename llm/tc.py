import json
import sys
import os
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
    "根据员工名获取近五次参考效价唤醒模型的情绪数据，其中包括具体的arousal值，区间(0, 1)；valence值，区间(-1, 1)和系统推断的主要情绪。当员工不存在时，success字段为false",
    ("employee_name", "员工姓名"),
)
def get_state(employee_name):
    helper = get_default_helper()
    person = helper.get_person_by_name(employee_name)
    if person:
        log = helper.get_latest_state_log(person["id"])
        helper.close()
        return {
            "success": True,
            "data": {
                "id": person["id"],
                "name": person.get("name"),
                "age": person.get("age"),
                "ear": log.get("ear", 0),
                "mar": log.get("mar", 0),
                "emoRet": log.get("emoRet", []),
            },
        }
    else:
        return {"success": False}


def extract_emo(emoRet):
    """从状态日志中提取 dominant_emotion 列表"""
    return [ret.get("domEmo", "") for ret in emoRet]


@Tool("获取所有员工的情绪状态")
def get_all_states():
    helper = get_default_helper()
    persons = helper.get_all_persons()
    data = []
    for person in persons:
        person_id = person["id"]
        log = helper.get_latest_state_log(person_id)
        if not log:
            data.append({"name": person.get("name"), "ear": 0, "mar": 0, "emo": []})
            continue
        ear = log.get("ear", 0)
        mar = log.get("mar", 0)
        emo = extract_emo(log.get("emoRet", []))
        data.append({"name": person.get("name"), "ear": ear, "mar": mar, "emo": emo})
    helper.close()
    return {"success": True, "data": data}


@Tool(
    "获取最近10条特定员工的情绪日志",
    ("employ_name", "员工姓名"),
)
def get_state_trend(employ_name):
    helper = get_default_helper()
    person = helper.get_person_by_name(employ_name)
    if not person:
        helper.close()
        return {"success": False}
    
    logs = helper.get_state_logs_by_person_id(person["id"], limit=10)
    helper.close()
    
    data = []
    for log in logs:
        ear = log.get("ear", 0)
        mar = log.get("mar", 0)
        emo = extract_emo(log.get("emoRet", []))
        data.append({"ear": ear, "mar": mar, "emo": emo})
    
    return {"success": True, "data": data}
