import json
from openai.types.chat import ChatCompletionMessageFunctionToolCall

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "根据员工名获取近五次参考效价唤醒模型的情绪数据，其中包括具体的arousal值，区间(0, 1)；valence值，区间(-1, 1)和系统推断的主要情绪。当员工不存在时，success字段为false",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_name": {"type": "string", "description": "员工姓名"}
                },
                "required": ["employee_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_status",
            "description": "获取所有员工的情绪状态",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def handle_tool_calls(tc: ChatCompletionMessageFunctionToolCall):
    if tc.function.name == "get_status":
        print(tc.function.arguments)
        try:
            args = json.loads(tc.function.arguments)
        except Exception:
            args = eval(tc.function.arguments)
        employee_name = args["employee_name"]
        result = {
            "success": True,
            "data": {
                "name": employee_name,
                "id": "23370000",
                "status": [
                    {
                        "valence": -0.0569193272846249,
                        "arousal": 0.0426297431765363,
                        "dominant_emotion": "sleepy",
                        "probabilities": {
                            "angry": 0.7424741052091122,
                            "disgust": 1.4385372537617513e-05,
                            "fear": 3.133590519428253,
                            "happy": 0.272903754375875,
                            "sad": 6.222175061702728,
                            "surprise": 0.014641349844168872,
                            "neutral": 89.61420059204102,
                        },
                    },
                    {
                        "valence": -0.6284678809794514,
                        "arousal": 0.6511502143768666,
                        "dominant_emotion": "nervous",
                        "probabilities": {
                            "angry": 6.514935195446014,
                            "disgust": 0.0012231746040924918,
                            "fear": 76.23038291931152,
                            "happy": 0.03507450164761394,
                            "sad": 15.921491384506226,
                            "surprise": 0.19239415414631367,
                            "neutral": 1.1044963262975216,
                        },
                    },
                ],
            },
        }
        return json.dumps(result, ensure_ascii=False)
    elif tc.function.name == "get_all_status":
        return json.dumps(
            {
                "success": True,
                "data": [
                    {
                        "name": "小明",
                        "id": "23370000",
                        "status": [
                            {
                                "valence": -0.0569193272846249,
                                "arousal": 0.0426297431765363,
                                "dominant_emotion": "sleepy",
                                "probabilities": {
                                    "angry": 0.7424741052091122,
                                    "disgust": 1.4385372537617513e-05,
                                    "fear": 3.133590519428253,
                                    "happy": 0.272903754375875,
                                    "sad": 6.222175061702728,
                                    "surprise": 0.014641349844168872,
                                    "neutral": 89.61420059204102,
                                },
                            }
                        ],
                    },
                    {
                        "name": "小帅",
                        "id": "23370001",
                        "status": [
                            {
                                "valence": -0.2519051893370252,
                                "arousal": 0.17188670209759896,
                                "dominant_emotion": "bored",
                                "probabilities": {
                                    "angry": 3.04515975982903,
                                    "disgust": 5.6837300212363796e-05,
                                    "fear": 12.135964610336101,
                                    "happy": 0.47922095346277677,
                                    "sad": 28.512720973057807,
                                    "surprise": 0.024968474496139557,
                                    "neutral": 55.801907527560445,
                                },
                            }
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        )
