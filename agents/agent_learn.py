import os
import subprocess

from pathlib import Path
import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)
WORKDIR = Path.cwd()
client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


# -- The dispatch map: {tool_name: handler} --
TOOL_HANDLERS = {
    "run_bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: read_file(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: write_file(kw["path"], kw["content"]),
    "edit_file": lambda **kw: edit_file(kw["path"], kw["old_text"], kw["new_text"]),
    "todo": lambda **kw: TODO.update(kw["items"]),
}

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
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": ["integer", "null"]},
            },
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
    {
        "name": "todo",
        "description": "Update task list. Track progress on multi-step tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "item": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["id", "text", "status"],
                    },
                }
            },
            "required": ["items"],
        },
    },
]

# example 创建一个hello.py,然后增加一个2 sum函数
# 空白表示 pending，x表示 completed，>表示in_progress

# > todo: [x] #1: 创建hello.py文件
# [x] #2: 添加基本的hello world功能
# [x] #3: 实现2 sum函数
# [>] #4: 测试代码功能

# (3/4 completed)


# 创建一个hello.py,然后增加一个2 sum函数
# 观察todo 的items的数据

# [{'id': '1', 'text': '创建hello.py文件', 'status': 'in_progress'}, {'id': '2', 'text': '添加2 sum函数', 'status': 'pending'}]

class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        print(items)
        return ""

TODO = TodoManager()

def read_file(path: str, limit: int = None) -> str:
    print(f"\033[33m$ read_file tools is excuted\033[0m")
    try:
        # 使用 errors='replace' 自动处理编码问题，替换无法解码的字符
        text = safe_path(path).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    print(f"\033[33m$ write_file tools is excuted\033[0m")
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    print(f"\033[33m$ edit_file tools is excuted\033[0m")
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


def run_bash(command: str) -> str:
    print(f"\033[33m$ run_bash tools is excuted\033[0m")
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
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
                handler = TOOL_HANDLERS.get(block.name)
                if handler is not None:
                    output = handler(**block.input)
                else:
                    output = f"Unknown tool: {block.name}"
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    }
                )
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
