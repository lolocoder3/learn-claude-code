import re
import subprocess

from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
WORKDIR = Path.cwd()
client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks."

THRESHOLD = 50000
KEEP_RECENT = 3

# 那是不是比如read file这个工具，他的tool result是某个文件的全部内容，但实际上我只是对其中某一段代码有需要，经过几轮对话后，确定这个文件有用的内容已经被我提取出来后，这个历史的tool result 就可以丢弃了
# ## 完全正确！这正是 `micro_compact` 的设计哲学

# ### 你的理解非常准确

# 是的，`read_file` 工具的 `tool_result` 通常是整个文件的内容（可能几千行代码），但实际对话中可能只需要其中的一小部分。

# ### 实际对话场景示例

# 假设对话流程如下：

# 1. **用户**："请帮我分析 `agents/agent_learn.py` 文件"
# 2. **Assistant**：调用 `read_file` 工具读取整个文件（2000行代码）
# 3. **工具结果**：返回完整的 2000 行代码（占用大量 token）
# 4. **用户**："这个文件中的 `agent_loop` 函数是怎么实现的？"
# 5. **Assistant**：从刚才读取的内容中找到 `agent_loop` 函数，并回答
# 6. **用户**："好的，那 `micro_compact` 函数呢？"
# 7. **Assistant**：再次从刚才读取的内容中找到 `micro_compact` 函数，并回答
# 8. **用户**："现在请帮我写一个测试脚本"

# ### 压缩后的效果

# 经过几轮对话后：
# - 你已经从文件中提取了 `agent_loop` 和 `micro_compact` 两个关键函数的信息
# - 这些信息已经体现在 Assistant 的回复中
# - 原始的完整文件内容（2000行）已经完成了它的使命

# 此时 `micro_compact` 会：
# 1. 识别到这个 `read_file` 的 `tool_result` 是"旧的"（不在最近3个工具结果中）
# 2. 将其内容压缩为：`[Previous: used read_file]`
# 3. 节省了约 1995 行的 token 占用

# ### 设计哲学

# 这种设计的核心思想是：**工具结果是为当前任务服务的临时数据，一旦其价值被提取，就可以安全地丢弃细节，只保留"用过什么工具"的元信息**。

# | 阶段 | 工具结果的作用 | 是否重要 |
# |------|---------------|----------|
# | **刚执行完** | 提供完整数据供模型分析 | ✅ 非常重要 |
# | **几轮对话后** | 关键信息已提取到对话中 | ⚠️ 可以压缩 |
# | **很久以后** | 只关心"之前做过什么" | ❌ 只需保留工具名 |

# ### 类比

# 这就像人类工作时的记忆策略：
# - **短期**：记住文件的完整内容以便分析
# - **中期**：记住关键结论和提取的信息
# - **长期**：只记住"我读过那个文件，找到了需要的信息"

# `micro_compact` 实现了 AI Agent 的**选择性遗忘**，让它在长对话中既能保持工作连续性，又不会因历史数据过载而耗尽上下文窗口。

def estimate_tokens(messages: list) -> int:
    """Rough token count: ~4 chars per token."""
    return len(str(messages)) // 4

def micro_compact(messages: list) -> list:
    # Collect (msg_index, part_index, tool_result_dict) for all tool_result entries
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))
    if len(tool_results) <= KEEP_RECENT:
        return messages
    # Find tool_name for each result by matching tool_use_id in prior assistant messages
    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name
    # Clear old results (keep last KEEP_RECENT)
    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        if isinstance(result.get("content"), str) and len(result["content"]) > 100:
            tool_id = result.get("tool_use_id", "")
            tool_name = tool_name_map.get(tool_id, "unknown")
            result["content"] = f"[Previous: used {tool_name}]"
    return messages


def auto_compact(messages: list) -> list:
    summarised_message = messages
    return summarised_message

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
    "compact": lambda **kw: "Manual compression requested.",
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
        "name": "compact",
        "description": "Trigger manual conversation compression.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "What to preserve in the summary",
                }
            },
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
        content = fp.read_text(encoding="utf-8", errors="replace")
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
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
        # Layer 1: micro_compact before each LLM call
        micro_compact(history)
        # Layer 2: auto_compact if token estimate exceeds threshold
        if estimate_tokens(history) > THRESHOLD:
            print("[auto_compact triggered]")
            history[:] = auto_compact(history)
        messageFromLLM = client.messages.create(
            model=model,
            max_tokens=8000,
            system=SYSTEM,
            messages=history,
            tools=TOOLS,
        )

        history.append({"role": "assistant", "content": messageFromLLM.content})
        if messageFromLLM.stop_reason != "tool_use":
            return
        results = []
        manual_compact = False
        for block in messageFromLLM.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                if block.name == "compact":
                    manual_compact = True
                    output = "Compressing..."
                elif handler is not None:
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
        # Layer 3: manual compact triggered by the compact tool
        if manual_compact:
            print("[manual compact]")
            history[:] = auto_compact(history)


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
