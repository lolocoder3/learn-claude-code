import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

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
    return "your location is shanghai"


def conversation(history):
    messageFromLLM = client.messages.create(
        model=model,
        max_tokens=8000,
        system="You are a helpful assistant.",
        messages=history,
        tools=TOOLS,
    )

     # 添加整个assistant响应（包括tool_use块）
    history.append({"role": "assistant", "content": messageFromLLM.content})
    if(messageFromLLM.stop_reason != "tool_use"):
        return
    results = []
    for block in messageFromLLM.content:
        if block.type == "tool_use":
            print(f"\033[33m$ show_location\033[0m")
            output = show_location()
            print(output)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output})
    history.append({"role": "user", "content": results})
while True:
    try:
        query = input("\033[36ms01 >> \033[0m")
    except (EOFError, KeyboardInterrupt):
        break

    if query.strip().lower() in ("q", "exit",""):
        break

    history.append({"role": "user", "content": query})
    conversation(history)
    response_content = history[-1]["content"]
    if isinstance(response_content, list):
        for block in response_content:
            if hasattr(block, "text"):
                print(block.text)
    print()
