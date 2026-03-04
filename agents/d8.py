#!/usr/bin/env python3
"""极简版Claude Agent - 最小化实现"""

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"
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
    return "your location is 313"


def conversation(history):
    while True:
        messageFromLLM = client.messages.create(
            model=MODEL,
            system=f"You are a helpful assistant..",
            messages=history,
            tools=TOOLS,
            max_tokens=8000,
        )
        # 添加助手响应到历史
        history.append({"role": "assistant", "content": messageFromLLM.content})
        # 如果模型没有调用工具，结束对话
        if messageFromLLM.stop_reason != "tool_use":
            return
        # 执行每个工具调用，收集结果
        results = []
        for block in messageFromLLM.content:
            if block.type == "tool_use":
                print(f"\033[33m$ show_location\033[0m")
                output = show_location()
                print(output[:200])
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output})
        history.append({"role": "user", "content": results})


while True:
    try:
        query = input("\033[36ms01 >> \033[0m")
    except (EOFError, KeyboardInterrupt):
        break

    if not query or query.strip().lower() in ("q", "exit"):
        break

    history.append({"role": "user", "content": query})
    conversation(history)
    # 显示助手回复
    response_content = history[-1]["content"]
    if isinstance(response_content, list):
        for block in response_content:
            if hasattr(block, "text"):
                print(block.text)
    print()
