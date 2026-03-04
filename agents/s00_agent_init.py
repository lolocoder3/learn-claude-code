#!/usr/bin/env python3
"""精简版Claude Agent初始化示例
最简单的Agent实现，展示核心交互循环。
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 初始化客户端
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = "deepseek-chat"
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

def agent_loop(messages: list):
    """单次Agent循环"""
    response = client.messages.create(
        model=MODEL, system=SYSTEM, messages=messages, max_tokens=8000,
    )
    messages.append({"role": "assistant", "content": response.content})

if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        
        # 合并退出条件
        if not query or query.strip().lower() in ("q", "exit"):
            break
        
        history.append({"role": "user", "content": query})
        agent_loop(history)
        
        # 打印助手回复
        # 方法1：直接打印整个content对象（包含元数据）
        # print(history[-1]["content"])
        
        # 方法2：只打印文本内容（更简洁）
        for block in history[-1]["content"]:
            if hasattr(block, "text"):
                print(block.text)

        print()
