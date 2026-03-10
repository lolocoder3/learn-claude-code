import os
import subprocess

from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
WORKDIR = Path.cwd()
client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"You are a coding agent at {WORKDIR}. Use the task tool to delegate exploration or subtasks."
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."


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
}

# Child gets all base tools except task (no recursive spawning)
CHILD_TOOLS = [
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
]

# -- Parent tools: base tools + task dispatcher --
PARENT_TOOLS = CHILD_TOOLS + [
    {
        "name": "task",
        "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "description": {
                    "type": "string",
                    "description": "Short description of the task",
                },
            },
            "required": ["prompt"],
        },
    },
]


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


# -- Subagent: fresh context, filtered tools, summary-only return --
def run_subagent(prompt: str) -> str:
    # see line 243, and know history in sub agent should start from user
    sub_messages = [{"role": "user", "content": prompt}]
    for _ in range(30):  # safety limit
        messageFromLLM = client.messages.create(
            model=model,
            max_tokens=8000,
            system=SUBAGENT_SYSTEM,
            messages=sub_messages,
            tools=CHILD_TOOLS,
        )

        sub_messages.append({"role": "assistant", "content": messageFromLLM.content})
        if messageFromLLM.stop_reason != "tool_use":
            break
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
        sub_messages.append({"role": "user", "content": results})
    # Only the final text returns to the parent -- child context is discarded
    tmp = []
    summary = "(no summary)"
    for b in messageFromLLM.content:
        if hasattr(b, "text") and b.text != "":
            tmp.append(b.text)
    if len(tmp) > 0:
        summary = "".join(tmp)
    print(summary)
    return summary


def agent_loop(history):
    print(history)
    while True:
        messageFromLLM = client.messages.create(
            model=model,
            max_tokens=8000,
            system=SYSTEM,
            messages=history,
            tools=PARENT_TOOLS,
        )

        history.append({"role": "assistant", "content": messageFromLLM.content})
        if messageFromLLM.stop_reason != "tool_use":
            return
        results = []
        for block in messageFromLLM.content:
            if block.type == "tool_use":
                if block.name == "task":
                    print(block)
                    output = run_subagent(block.input["prompt"])
                else:
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

# python agent_learn.py 

# error
# Failed to deserialize the JSON body into the target type: messages: invalid type: string 


# s01 >> Use a subtask to find what testing framework this project uses
# [{'role': 'user', 'content': 'Use a subtask to find what testing framework this project uses'}]
# ToolUseBlock(id='call_00_sfiNEluvGbTI89YHtmDuaGFQ', caller=None, input={'description': 'Explore project structure to identify testing framework', 'prompt': "Please explore this project's structure to identify what testing framework it uses. Look for:\n1. Package.json or similar dependency files\n2. Test files (e.g., *.spec.js, *.test.js, *.test.ts, etc.)\n3. Configuration files for testing (jest.config.js, vitest.config.js, etc.)\n4. Any test scripts in package.json\n5. Common testing framework files and directories\n\nStart by examining the current directory structure and then look for specific testing-related files."}, name='task', type='tool_use')
# Traceback (most recent call last):
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 250, in <module>
#     agent_loop(history)
#     ~~~~~~~~~~^^^^^^^^^
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 221, in agent_loop
#     output = run_subagent(block.input["prompt"])
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 163, in run_subagent
#     messageFromLLM = client.messages.create(
#         model=model,
#     ...<3 lines>...
#         tools=CHILD_TOOLS,
#     )
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\_utils\_utils.py", line 282, in wrapper
#     return func(*args, **kwargs)
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\resources\messages\messages.py", line 996, in create
#     return self._post(
#            ~~~~~~~~~~^
#         "/v1/messages",
#         ^^^^^^^^^^^^^^^
#     ...<30 lines>...
#         stream_cls=Stream[RawMessageStreamEvent],
#         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#     )
#     ^
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\_base_client.py", line 1364, in post
#     return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
#                            ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\_base_client.py", line 1137, in request
#     raise self._make_status_error_from_response(err.response) from None
# anthropic.BadRequestError: Error code: 400 - {'error': {'message': 'Failed to deserialize the JSON body into the target type: messages: invalid type: string "Please explore this project\'s structure to identify what testing framework it uses. Look for:\\n1. Package.json or similar dependency files\\n2. Test files (e.g., *.spec.js, *.test.js, *.test.ts, etc.)\\n3. Configuration files for testing (jest.config.js, vitest.config.js, etc.)\\n4. Any test scripts in package.json\\n5. Common testing framework files and directories\\n\\nStart by examining the current directory structure and then look for specific testing-related files.", expected a sequence at line 1 column 500', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}}

# lolom@WIN-96NTVQFEJNB MINGW64 ~/repo/learn-claude-code/agents (main)
# $ python agent_learn.py 
# s01 >> Use a subtask to find what testing framework this project uses
# [{'role': 'user', 'content': 'Use a subtask to find what testing framework this project uses'}]
# ToolUseBlock(id='call_00_YkToXiSMy6ccvH0kKmhvofyp', caller=None, input={'prompt': 'Explore the project structure to identify what testing framework is being used. Look for:\n1. Package.json or similar dependency files\n2. Test files and their extensions\n3. Test configuration files\n4. Any test runner scripts\n5. Common test framework indicators like Jest, Mocha, Jasmine, Vitest, etc.\n\nPlease provide a detailed analysis of the testing framework found.', 'description': 'Identify testing framework used in project'}, name='task', type='tool_use')
# Traceback (most recent call last):
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 250, in <module>
#     agent_loop(history)
#     ~~~~~~~~~~^^^^^^^^^
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 221, in agent_loop
#     output = run_subagent(block.input["prompt"])
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 163, in run_subagent
#     messageFromLLM = client.messages.create(
#         model=model,
#     ...<3 lines>...
#         tools=CHILD_TOOLS,
#     )
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\_utils\_utils.py", line 282, in wrapper
#     return func(*args, **kwargs)
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\resources\messages\messages.py", line 996, in create
#     return self._post(
#            ~~~~~~~~~~^
#         "/v1/messages",
#         ^^^^^^^^^^^^^^^
#     ...<30 lines>...
#         stream_cls=Stream[RawMessageStreamEvent],
#         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#     )
#     ^
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\_base_client.py", line 1364, in post
#     return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
#                            ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\lolom\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\_base_client.py", line 1137, in request
#     raise self._make_status_error_from_response(err.response) from None
# anthropic.BadRequestError: Error code: 400 - {'error': {'message': 'Failed to deserialize the JSON body into the target type: messages: invalid type: string "Explore the project structure to identify what testing framework is being used. Look for:\\n1. Package.json or similar dependency files\\n2. Test files and their extensions\\n3. Test configuration files\\n4. Any test runner scripts\\n5. Common test framework indicators like Jest, Mocha, Jasmine, Vitest, etc.\\n\\nPlease provide a detailed analysis of the testing framework found.", expected a sequence at line 1 column 406', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}}