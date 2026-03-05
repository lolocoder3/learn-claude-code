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

     # 添加整个assistant响应（包括tool_use块）
    history.append({"role": "assistant", "content": messageFromLLM.content})
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
            results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output})
    history.append({"role": "user", "content": results})
while True:
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

# __问题分析：__ 错误信息显示：`unexpected tool_use_id found in tool_result blocks. Each tool_result block must have a corresponding tool_use block in the previous message.`

# __根本原因：__ 在 `agent_learn.py` 的 `conversation` 函数中，代码只将模型的文本响应添加到历史记录中，而没有包含 `tool_use` 块。具体来说：

# 1. 原始代码：`history.append({"role": "assistant", "content": response_text})` - 只添加了文本
# 2. 当模型调用工具时，会生成 `tool_use` 块，但这些块没有被添加到历史记录中
# 3. 后续发送 `tool_result` 时，API找不到对应的 `tool_use` 块，导致400错误

# __解决方案：__ 将代码修改为：`history.append({"role": "assistant", "content": messageFromLLM.content})` 这样会将整个响应内容（包括 `tool_use` 块）添加到历史记录中，确保 `tool_result` 有对应的 `tool_use` 块。

# __测试结果：__ 修复后程序运行正常，可以正确处理工具调用：

# - 输入"我在哪" → 调用 `show_location` 工具 → 返回"your location is shanghai"
# - 后续对话正常进行，没有出现错误
