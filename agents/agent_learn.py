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

# what tools you have
# I have access to one tool:

# **show_location** - This tool allows me to show your current location. When you ask about location-related information, I can use this tool to provide you with details about where you are.

# I can also help with a wide variety of other tasks like answering questions, explaining concepts, helping with writing, analysis, problem-solving, and more - though for those I rely on my general knowledge and reasoning abilities rather than specific tools.

# What would you like help with today?

# 我现在在哪里
# 我来帮你查看当前位置。