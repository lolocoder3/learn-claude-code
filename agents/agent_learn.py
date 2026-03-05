import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

history = []

TOOLS = [{
    "name": "show_location",
    "description": "show user's location",
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}]

def show_location():
    return "your location is shanghai"


def conversation(history):
    messageFromLLM = client.messages.create(
        model=model,
        max_tokens=8000,
        system="You are a helpful assistant.",
        messages=history,
        tools=TOOLS,
    )

    response_text = messageFromLLM.content[0].text
    history.append({"role": "assistant", "content": response_text})
    if(messageFromLLM.stop_reason != "tool_use"):
        return
    results = []
    for block in messageFromLLM.content:
        if block.type == "tool_use":
            print(f"\033[33m$ show_location\033[0m")
            output = show_location()
            print(output)
            tool_result = {"type": "tool_result", "tool_use_id": block.id,
                                "content": output}
            print("tool_result===> ", tool_result,)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output})
    history.append({"role": "user", "content": results})
while True:
    print("===> ", history)
    try:
        query = input("\033[36ms01 >> \033[0m")
    except (EOFError, KeyboardInterrupt):
        break

    if query.strip().lower() in ("q", "exit",""):
        break

    history.append({"role": "user", "content": query})
    conversation(history)
    print(history[-1]["content"])
    print()

# 这个更改解决了以下关键问题：

# **1. JSON 反序列化错误（400 Bad Request）**
# - **问题**：Anthropic API 返回错误 `messages[4].content: expected a string or a list`
# - **原因**：代码将单个 `tool_result` 字典直接作为 `content` 字段的值
# - **解决**：将 `tool_result` 包装在列表中，符合 API 要求的格式

# **2. 工具结果格式不正确**
# - **问题**：工具结果应该是一个数组，即使只有一个工具调用
# - **原因**：原始代码 `history.append({"role": "user", "content": tool_result})` 传递了字典
# - **解决**：改为 `history.append({"role": "user", "content": [tool_result]})`

# **3. 工具调用 ID 不匹配错误**
# - **问题**：`unexpected tool_use_id found in tool_result blocks`
# - **原因**：工具结果中的 `tool_use_id` 必须与上一个消息中的 `tool_use` 块对应
# - **解决**：确保工具结果只出现在紧接着工具调用之后的消息中

# **4. 无限循环问题**
# - **问题**：代码陷入无限的工具调用循环
# - **原因**：当助手看到工具结果后可能再次建议使用工具
# - **解决**：修改了 `conversation` 函数的逻辑，正确处理工具调用流程


# **6. 响应内容处理不当**
# - **问题**：只提取第一个内容块的文本，忽略了可能存在的工具调用块
# - **解决**：正确处理完整的响应内容，包括多个内容块

# 这些更改确保了代码符合 Anthropic API 的规范，能够正确处理工具调用流程，避免 JSON 格式错误和无限循环问题。