from openai import OpenAI

from context import Context

ctx = Context('http://localhost:11434/v1/', '1')

ctx.addMessage({"role": "system",
                "content": "你是一个员工工作状态管理系统的管理员，能够对员工工作时反映出的情绪识别并分析。"})


# client1 = OpenAI(
#     base_url='https://chat.zju.edu.cn/api/ai/v1/',
#     api_key='sk-GyXE0EDASwuCCQlb5490E8D095404a6eAdC4BbD1E9909eD1',
# )

# client = client2

# chat_completion = client.chat.completions.create(
#     messages=[
#         {
#             'role': 'user',
#             'content': '1.3和1.15谁大？',
#         }
#     ],
#     model='deepseek-r1-distill-qwen',
#     store=True
# )

# chat_completion

# l = client.chat.completions.list()

# print(l)

# print(chat_completion.choices[0].message.content)


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "根据员工名获取近五次参考效价唤醒模型的情绪数据，其中包括具体的arousal值，区间(0, 1)；valence值，区间(-1, 1)和系统推断的主要情绪。当员工不存在时，success字段为false",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "员工姓名"}},
                "required": ["employee_name"]}}}]

ctx.addMessage({"role": "user", "content": "员工小明最近的情绪状态如何？"})

response = ctx.client.chat.completions.create(
    model="1",
    messages=ctx.messages,
    tools=tools,
    tool_choice="auto"
)

ctx.addMessage("assistant", response.choices[0].message.content)

# 4. 解析模型响应：若需要调用工具，则执行函数
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    print(tool_call.function.name)
    print(tool_call.function.arguments)
    # if tool_call.function.name == "get_weather":
    #     # 提取参数（城市名）
    #     city = eval(tool_call.function.arguments)["city"]
    #     # 模拟调用天气接口（实际中替换为真实 API）
    #     weather_result = f"北京今天天气：晴，20-28℃，微风"

    #     # 5. 将工具结果返回给模型，获取最终回答
    #     messages.append(response.choices[0].message)  # 追加模型的工具调用指令
    #     messages.append({
    #         "role": "tool",
    #         "tool_call_id": tool_call.id,
    #         "content": weather_result
    #     })

    #     # 6. 再次调用模型，生成自然语言回答
    #     final_response = client.chat.completions.create(
    #         model="1",
    #         messages=messages
    #     )
    #     print("最终回答：", final_response.choices[0].message.content)

ctx.printMessage()
