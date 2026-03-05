import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

history = []

def conversation(history):
    messageFromLLM = client.messages.create(
        model=model,
        max_tokens=8000,
        system="You are a helpful assistant.",
        messages=history,
    )

    response_text = messageFromLLM.content[0].text
    history.append({"role": "assistant", "content": response_text})

while True:
    print("===> ", history)
    query = input("User>> ")

    history.append({"role": "user", "content": query})
    conversation(history)
    print(history[-1]["content"])
    print()
