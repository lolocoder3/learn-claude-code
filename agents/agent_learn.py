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

    response_text = messageFromLLM.content[0].text
    history.append({"role": "assistant", "content": response_text})
    if(messageFromLLM.stop_reason != "tool_use"):
        return
        print("messageFromLLM.content===>",messageFromLLM.content)
    for block in messageFromLLM.content:
        if block.type == "tool_use":
            print(f"\033[33m$ show_location\033[0m")
            output = show_location()
            print(output)
            tool_result = {"type": "tool_result", "tool_use_id": block.id,
                                "content": output}
            print("tool_result===> ", tool_result,)
    history.append({"role": "user", "content": tool_result})

while True:
    print("===> ", history)
    try:
        query = input("\033[36ms01 >> \033[0m")
    except (EOFError, KeyboardInterrupt):
        break

    if query.strip().lower() in ("q", "exit",""):
        break

    history.append({"role": "user", "content": query})
    conversation(history)
    print(history[-1]["content"])
    print()