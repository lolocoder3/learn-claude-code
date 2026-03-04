#!/usr/bin/env python3
"""极简版Claude Agent - 最小化实现"""

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"
history = []


def conversation(history):
    while True:
        messageFromLLM = client.messages.create(
            model=MODEL,
            system=f"You are a helpful assistant..",
            messages=history,
            max_tokens=8000,
        )
        # 获取LLM的响应文本
        response_text = messageFromLLM.content[0].text
        history.append({"role": "assistant", "content": response_text})
        if messageFromLLM.stop_reason == "end_turn":
            return


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
    print(history[-1]["content"])
    print()
