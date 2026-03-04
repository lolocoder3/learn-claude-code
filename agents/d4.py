#!/usr/bin/env python3
"""极简版Claude Agent - 最小化实现"""

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"
history = []
while True:
    query = input("User>> ")
    # print(history)
    history.append({"role": "user", "content": query})
    messageFromLLM = client.messages.create(
        model=MODEL,
        system=f"You are a helpful assistant..",
        messages=history,
        max_tokens=8000,
    )
    history.append({"role": "assistant", "content": messageFromLLM.content[0].text})
    print(messageFromLLM.content[0].text)
