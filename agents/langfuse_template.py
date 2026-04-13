#!/usr/bin/env python3
"""极简版Claude Agent - 最小化实现 + Langfuse集成"""
# https://langfuse.com/guides/cookbook/integration_anthropic

from anthropic import Anthropic
from dotenv import load_dotenv
from langfuse import get_client, observe

load_dotenv(override=True)

# 初始化 Langfuse 客户端
langfuse = get_client()

# 验证连接
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"

q = input("User>> ")

# 创建 trace 并记录对话
@observe(name="chat", as_type="generation")
def chat_span(input_text: str) -> str:
    message = [{"role": "user", "content": input_text}]
    messageFromLLM = client.messages.create(
        model=MODEL,
        system=[{"type": "text", "text": "You are a helpful assistant."}],
        messages=message,  # type: ignore
        max_tokens=8000,
    )
    # 获取文本响应
    response_text = ""
    for block in messageFromLLM.content:
        if block.type == "text":
            response_text = block.text
            break
    
    # 记录响应到 Langfuse
    if response_text:
        print(f"Assistant>> {response_text}")
    
    return response_text

# 调用函数
response = chat_span(q)

# 确保所有数据都发送到 Langfuse
langfuse.flush()
langfuse.shutdown()
