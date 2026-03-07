import os
import subprocess

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
    print("path :" + path)
    return "hello world"


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

# 已成功修复UnicodeDecodeError: 'gbk' codec can't decode byte 0xad in position 97错误。

# __问题分析：__

# 1. 错误发生在`agents/agent_learn.py`文件的`run_bash`函数中
# 2. 当执行`head -c 200 agent_learn.py`命令时，输出包含UTF-8编码的中文字符
# 3. `subprocess.run`使用`text=True`参数时，默认使用系统编码（Windows上是GBK）解码输出
# 4. 当`head -c 200`在UTF-8多字节序列中间截断时，会产生无效的GBK字节序列

# __修复方案：__ 在`subprocess.run`调用中明确指定编码参数：

# - `encoding='utf-8'`：使用UTF-8编码解码命令输出
# - `errors='replace'`：遇到无法解码的字符时用替换字符（�）代替，避免崩溃

# __测试结果：__ 修复后的程序可以正常运行，不再出现编码错误。测试命令`head -c 200 agent_learn.py`现在可以正确输出文件内容的前200个字符。

# $ python agent_learn.py 
# s01 >> what content in agent_learn.py
# $ read_file tools is excuted
# path :agent_learn.py
# The file `agent_learn.py` contains the text "hello world".

# s01 >> show me the content of agent_learn.py
# $ read_file tools is excuted
# path :agent_learn.py
# The file `agent_learn.py` contains the text "hello world".

# s01 >> I want to know see this current file
# $ read_file tools is excuted
# path :agent_learn.py
# The current content of `agent_learn.py` is "hello world".