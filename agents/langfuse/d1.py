from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(override=True)

client = Anthropic(base_url="https://api.deepseek.com/anthropic")
MODEL = "deepseek-chat"

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