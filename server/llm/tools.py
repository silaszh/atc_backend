from enum import Enum

from langchain.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

import json

from ..pg_helper import get_helper
from ..data_store import online_seat


class SeatState:
    def __init__(self, seat_id, employee_name):
        self.seat_id = seat_id
        self.employee_name = employee_name
        self.states = []

    def add_state(self, state_data):
        state_data.pop("seat_id", None)
        self.states.append(state_data)

    def to_dict(self):
        return {
            "seat_id": self.seat_id,
            "employee_name": self.employee_name,
            "states": self.states,
        }


@tool
def get_all_seat_states():
    """获取所有席位的状态数据，返回格式为列表，每个元素包含工位ID、员工名称和状态数据列表
    其中，状态数据包括以下字段：

    - timestamp: 系统时间（ISO格式字符串）
    - heart_rate: 心率
    - emo_v: 效价唤醒模型中的效价值，范围为-1到1，从非常消极到非常积极
    - emo_a: 效价唤醒模型中的唤醒值，范围为-1到1，从困倦到兴奋
    - pose_0: 头部姿态角（俯仰角）
    - pose_1: 头部姿态角（偏航角）
    - pose_2: 头部姿态角（翻滚角）
    - ear: 眼睛纵横比
    - mar: 嘴巴纵横比
    - label: 通过效价唤醒模型得到的情绪标签
    - eye_close_freq: 眼睛闭合频率
    - iris_ratio_x: 虹膜位置水平比（从左至右为0到1）
    - iris_ratio_y: 虹膜位置垂直比（从下到上为0到1）

    """
    helper = get_helper()
    seats = helper.get_all_seats()
    states = helper.get_all_states()
    helper.close()
    seat_states = {}
    for seat in seats:
        seat_id = seat[0]
        name = seat[1]
        seat_states[seat_id] = SeatState(seat_id, name)
    for state in states:
        seat_id = state["seat_id"]
        if seat_id in seat_states:
            seat_states[seat_id].add_state(state)
    return json.dumps([s.to_dict() for s in seat_states.values()])


class SpanType(str, Enum):
    LATEST = "latest"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"


class GetSeatStatesInput(BaseModel):
    """get_seat_states工具的输入参数"""

    seat_id: int = Field(description="席位ID")
    time_span: SpanType = Field(
        description="""\
需要获取状态数据的时间范围，可选值：latest（最新状态）、hour（最近1小时）、day（最近24小时）、month（最近30天），分别表示

- 获取最近10条数据
- 一小时均匀分出10份后各取区间内首条数据
- 一天均匀分出10份后各取区间内首条数据
- 一月均匀分出10份后各取区间内首条数据"""
    )


@tool(args_schema=GetSeatStatesInput)
def get_seat_states(seat_id: int, time_span: SpanType):
    """获取指定席位指定时间跨度的状态数据列表
    其中，状态数据包括以下字段：

    - timestamp: 系统时间（ISO格式字符串）
    - heart_rate: 心率
    - emo_v: 效价唤醒模型中的效价值，范围为-1到1，从非常消极到非常积极
    - emo_a: 效价唤醒模型中的唤醒值，范围为-1到1，从困倦到兴奋
    - pose_0: 头部姿态角（俯仰角）
    - pose_1: 头部姿态角（偏航角）
    - pose_2: 头部姿态角（翻滚角）
    - ear: 眼睛纵横比
    - mar: 嘴巴纵横比
    - label: 通过效价唤醒模型得到的情绪标签
    - eye_close_freq: 眼睛闭合频率
    - iris_ratio_x: 虹膜位置水平比（从左至右为0到1）
    - iris_ratio_y: 虹膜位置垂直比（从下到上为0到1）
    """

    helper = get_helper()
    match time_span:
        case SpanType.LATEST:
            states = helper.get_recent_states_by_seat_id(seat_id)
        case SpanType.HOUR:
            states = helper.get_states_by_seat_id_and_time_span(seat_id, "hour")
        case SpanType.DAY:
            states = helper.get_states_by_seat_id_and_time_span(seat_id, "day")
        case SpanType.MONTH:
            states = helper.get_states_by_seat_id_and_time_span(seat_id, "month")
    helper.close()
    return json.dumps(states)


@tool
def get_seat_id_by_name(employee_name: str):
    """根据员工名称获取对应的席位ID，未找到时返回Not found"""
    helper = get_helper()
    seat = helper.get_seat_by_name(employee_name)
    helper.close()
    if seat:
        return json.dumps(
            {
                "seat_id": seat[0],
                "name": seat[1],
            }
        )
    else:
        return "Not found"


@tool
def get_seat_info(seat_id: int):
    """根据席位ID获取员工名称等信息，含当前在线状态与上一次登录时间，未找到时返回Not found"""
    helper = get_helper()
    seat = helper.get_seat_by_id(seat_id)
    helper.close()
    if seat:
        return json.dumps(
            {
                "seat_id": seat[0],
                "name": seat[1],
                "online": online_seat.get(seat[0]) is not None,
                # ? datetime对象JSON序列化时直接转字符串
                "last_login_time": str(seat[2]),
            }
        )
    else:
        return "Not found"


@tool
def get_seat_alert(seat_id: int):
    """根据席位ID获取员工最近20条异常状态警报历史"""
    helper = get_helper()
    alerts = helper.get_alerts_by_seat_id(seat_id)
    helper.close()
    return json.dumps(alerts)


class ActionType(str, Enum):
    EYE_CLOSING = "eye_closing"
    YAWNING = "yawning"
    HEAD_DROOPING = "head_drooping"
    STARING = "staring"
    SLOW_RESPONSE = "slow_response"
    OTHER = "other"


class AbnormalSegment(BaseModel):
    start_second: float = Field(ge=0, le=15, description="异常开始时间（秒，0~15）")
    end_second: Optional[float] = Field(
        None,
        ge=0,
        le=15,
        description="异常结束时间（秒，若为瞬时事件可不填或等于 start_second）",
    )
    action_type: ActionType = Field(description="异常动作类型")
    description: Optional[str] = Field(None, description="简要描述现象（可选）")


class VerifySystemJudgmentInput(BaseModel):
    """verify_system_judgment工具的输入参数"""

    is_system_correct: bool = Field(description="系统判断是否正确")
    corrected_analysis: str = Field(description="判定原因，基于视频内容详细解释")
    recommendation: str = Field(description="针对当前情况的专业建议")
    abnormal_segments: List[AbnormalSegment] = Field(
        default_factory=list,
        description="视频中所有异常行为片段的时间标记列表，若无异常则为空列表",
    )


@tool(args_schema=VerifySystemJudgmentInput)
def verify_system_judgment(
    is_system_correct: bool,
    corrected_analysis: str,
    recommendation: str,
    abnormal_segments: List[AbnormalSegment],
):
    """验证系统判断的正确性，并提供纠正分析、建议和异常行为片段"""
    return json.dumps(
        {
            "is_system_correct": is_system_correct,
            "corrected_analysis": corrected_analysis,
            "recommendation": recommendation,
            # FIXME 性能可能有问题
            "abnormal_segments": [
                json.loads(s.model_dump_json()) for s in abnormal_segments
            ],
        }
    )


def tool_scheme(tool_func):
    return convert_to_openai_tool(tool_func)
