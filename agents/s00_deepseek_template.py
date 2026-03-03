import anthropic

from dotenv import load_dotenv

load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

message = client.messages.create(
    model="deepseek-chat",
    max_tokens=1000,
    system="You are a helpful assistant.",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Hi, how are you?"
                }
            ]
        }
    ]
)

print(message.content)
