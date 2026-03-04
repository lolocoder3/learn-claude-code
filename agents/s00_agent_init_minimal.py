#!/usr/bin/env python3
"""极简版Claude Agent - 最小化实现"""

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"

if __name__ == "__main__":
    message = []
    q = input("User>> ")

    message.append({"role": "user", "content": q})
    messageFromLLM = client.messages.create(
        model=MODEL,
        system=f"You are a helpful assistant..",
        messages=message,
        max_tokens=8000,
    )

    print(messageFromLLM.content[0].text)
