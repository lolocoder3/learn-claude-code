import os
import subprocess

import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

history = []

TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


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
            print(f"\033[33m$ {block.input['command']}\033[0m")
            output = run_bash(block.input["command"])
            print(output[:200])
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

# 运行generate hello.py for me，发现没有生成对应的文件。
# $ python agent_learn.py
# s01 >> generate hello.py for me
# $ cat > hello.py << 'EOF'
# #!/usr/bin/env python3
# # hello.py - A simple Python script

# def main():
#     """Main function that prints a greeting."""
#     print("Hello, World!")
#     print("Welcome to Python programming!")

#     # You can add more functionality here
#     name = input("What's your name? ")
#     print(f"Nice to meet you, {name}!")

# if __name__ == "__main__":
#     main()
# EOF
# 此时不应有 <<。

# s01 >>