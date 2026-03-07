import os
import subprocess

from pathlib import Path
import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use Tools to solve tasks. Act, don't explain."


TOOLS = [
    {
        "name": "run_bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
]


def read_file(path: str) -> str:
    print(f"\033[33m$ read_file tools is excuted\033[0m")
    text = (Path.cwd() / path).resolve().read_text()
    lines = text.splitlines()
    return "\n".join(lines)[:50000]


def write_file(command: str) -> None:
    print(f"\033[33m$ write_file tools is excuted\033[0m")


def edit_file(command: str) -> None:
    print(f"\033[33m$ edit_file tools is excuted\033[0m")


def run_bash(command: str) -> str:
    print(f"\033[33m$ run_bash tools is excuted\033[0m")
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def agent_loop(history):
    while True:
        messageFromLLM = client.messages.create(
            model=model,
            max_tokens=8000,
            system="You are a helpful assistant.",
            messages=history,
            tools=TOOLS,
        )

        # 添加整个assistant响应（包括tool_use块）
        history.append({"role": "assistant", "content": messageFromLLM.content})
        if messageFromLLM.stop_reason != "tool_use":
            return
        results = []
        for block in messageFromLLM.content:
            if block.type == "tool_use":
                if block.name == "run_bash":
                    print(f"\033[33m$ {block.input['command']}\033[0m")
                    output = run_bash(block.input["command"])
                    print(output[:200])
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        }
                    )
                elif block.name == "read_file":
                    output = read_file(block.input["path"])
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        }
                    )
        # print(history)
        history.append({"role": "user", "content": results})


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()

#meet issue gbk
# $ python agent_learn.py
# s01 >> show me the content of agent_learn.py
# $ read_file tools is excuted
# Traceback (most recent call last):
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 152, in <module>
#     agent_loop(history)
#     ~~~~~~~~~~^^^^^^^^^
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 128, in agent_loop
#     output = read_file(block.input["path"])
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 64, in read_file
#     text = (Path.cwd() / path).resolve().read_text()
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\pathlib\__init__.py", line 788, in read_text
#     return f.read()
#            ~~~~~~^^
# UnicodeDecodeError: 'gbk' codec can't decode byte 0xad in position 123: illegal multibyte sequence