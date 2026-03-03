#!/usr/bin/env python3
"""极简版Claude Agent - 最小化实现"""

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"

if __name__ == "__main__":
    history = []
    while True:
        q = input("User>> ")
        
        history.append({"role": "user", "content": q})
        r = client.messages.create(
            model=MODEL,
            system=f"You are a helpful assistant..",
            messages=history,
            max_tokens=8000,
        )
        history.append({"role": "assistant", "content": r.content})
        content = r.content
        
        for block in history[-1]["content"]:
        # 只打印文本类型的块
            if hasattr(block, "text"):
                print(block.text)

        print()
