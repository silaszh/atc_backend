from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Literal

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
    """获取所有席位的状态数据，返回格式为列表，每个元素包含工位ID、员工名称和状态列表"""
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


@tool
def get_seat_states(seat_id: int, time_span: str):
    """获取指定席位的状态数据"""
    return "[]"  # TODO


@tool
def get_seat_id_by_name(employee_name: str):
    """根据员工名称获取对应的席位ID"""
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
    """根据席位ID获取员工名称"""
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
    """根据席位ID获取员工异常状态警报历史"""
    # TODO
    return json.dumps([])


def tool_scheme(tool_func):
    schema = tool_func.args_schema.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": schema.get("title", ""),
            "description": schema.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
        },
    }
