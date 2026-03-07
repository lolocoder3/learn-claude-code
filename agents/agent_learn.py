import os
import subprocess

import anthropic
from dotenv import load_dotenv

# 读取env中的api-key
load_dotenv(override=True)

client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."


TOOLS = [
    {
        "name": "bash",
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
                print(block)
                if block.name == "run_bash":
                    print(f"\033[33m$ {block.input['command']}\033[0m")
                    output = run_bash(block.input["command"])
                    print(output[:200])
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": output}
                    )
                elif block.name == "read_file":
                    output = read_file(block.input["path"])
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": output}
                    )
        print(history)
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

#  read current file ===> OK
# ToolUseBlock(id='call_00_8Z3Sgv4wG5SwotcnZiz8hgnW', caller=None, input={'path': '.'}, name='read_file', type='tool_use')
# $ read_file tools is excuted
# path :.
# [{'role': 'user', 'content': 'read current file'}, {'role': 'assistant', 'content': [TextBlock(citations=None, text="I'll read the current file to see what's available.", type='text'), ToolUseBlock(id='call_00_8Z3Sgv4wG5SwotcnZiz8hgnW', caller=None, input={'path': '.'}, name='read_file', type='tool_use')]}]
# The current file contains "hello world". Is there something specific you'd like me to do with this file or would you like me to read a different file?

# read all file of this folder ===> Issue
# ToolUseBlock(id='call_00_Ufj2rOCUOi51zYNoitgw1lCN', caller=None, input={'command': 'ls -la'}, name='bash', type='tool_use')
# [{'role': 'user', 'content': 'read current file'}, {'role': 'assistant', 'content': [TextBlock(citations=None, text="I'll read the current file to see what's available.", type='text'), ToolUseBlock(id='call_00_8Z3Sgv4wG5SwotcnZiz8hgnW', caller=None, input={'path': '.'}, name='read_file', type='tool_use')]}, {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'call_00_8Z3Sgv4wG5SwotcnZiz8hgnW', 'content': 'hello world'}]}, {'role': 'assistant', 'content': [TextBlock(citations=None, text='The current file contains "hello world". Is there something specific you\'d like me to do with this file or would you like me to read a different file?', type='text')]}, {'role': 'user', 'content': 'read all file of this folder'}, {'role': 'assistant', 'content': [TextBlock(citations=None, text="I'll read all files in the current folder.", type='text'), ToolUseBlock(id='call_00_Ufj2rOCUOi51zYNoitgw1lCN', caller=None, input={'command': 'ls -la'}, name='bash', type='tool_use')]}]
# Traceback (most recent call last):
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 136, in <module>
#     agent_loop(history)
#     ~~~~~~~~~~^^^^^^^^^
#   File "C:\Users\lolom\repo\learn-claude-code\agents\agent_learn.py", line 92, in agent_loop
#     messageFromLLM = client.messages.create(
#         model=model,
#     ...<3 lines>...
#         tools=TOOLS,
#     )
#   File "C:\Users\lolom\repo\learn-claude-code\.venv\Lib\site-packages\anthropic\_utils\_utils.py", line 282, in wrapper
#     return func(*args, **kwargs)
#   File "C:\Users\lolom\repo\learn-claude-code\.venv\Lib\site-packages\anthropic\resources\messages\messages.py", line 996, in create
#     return self._post(
#            ~~~~~~~~~~^
#         "/v1/messages",
#         ^^^^^^^^^^^^^^^
#     ...<30 lines>...
#         stream_cls=Stream[RawMessageStreamEvent],
#         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#     )
#     ^
#   File "C:\Users\lolom\repo\learn-claude-code\.venv\Lib\site-packages\anthropic\_base_client.py", line 1364, in post
#     return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
#                            ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "C:\Users\lolom\repo\learn-claude-code\.venv\Lib\site-packages\anthropic\_base_client.py", line 1137, in request
#     raise self._make_status_error_from_response(err.response) from None
# anthropic.BadRequestError: Error code: 400 - {'error': {'message': 'messages.6: all messages must have non-empty content', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}}