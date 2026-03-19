import subprocess

from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
WORKDIR = Path.cwd()
client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
kk
qq"""


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
    "load_skill": lambda **kw: SkillLoader(kw["name"]),
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
        "name": "load_skill",
        "description": "Load expert knowledge and professional background for specialized topics",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name to load"}
            },
            "required": ["name"],
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


def SkillLoader(command: str) -> str:
    print(f"\033[33m$ SkillLoader is excuted\033[0m")
    if command == "kk":
        return """You can get kk through 3 steps:
    1.go to shanghai for A
        2.go to beijing for B
        3.With A and B, you can get kk in wuhan"""
    else:
        return """You can get qq through 3 steps:
    1.go to shanghai for AA
        2.go to beijing for BB
        3.With AA and BB, you can get qq in wuhan"""


def agent_loop(history):
    while True:
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

# #基于对 `agents/agent_learn.py` 文件当前更改的分析，以下是详细的commit name和主要更改内容及其思路：

# ## 主要更改内容

# ### 1. __工具重命名和参数化__

# - 将 `expert_knowledge` 工具重命名为 `load_skill`
# - 从无参数的静态工具改为接受 `name` 参数的动态工具
# - 更新了工具的input_schema，添加了必需的 `name` 参数

# ### 2. __技能加载器实现__

# - 新增 `SkillLoader()` 函数，根据技能名称返回不同的专业知识
# - 支持两种技能：`kk` 和 `qq`，分别返回不同的获取步骤
# - 保持了原有的专业知识内容，但通过函数动态返回

# ### 3. __系统提示更新__

# - 更新SYSTEM提示，从"使用expert_knowledge获取kk的知识"改为"使用load_skill获取kk或qq的知识"
# - 反映了工具功能的扩展

# ### 4. __工具处理逻辑统一化__

# - 移除了对 `expert_knowledge` 的特殊处理逻辑
# - 所有工具现在都通过 `handler(**block.input)` 统一调用
# - 简化了 `agent_loop` 函数中的工具分发逻辑

# ### 5. __代码清理__

# - 移除了未使用的 `import os`
# - 删除了文件末尾的详细注释文档
# - 保持了代码的简洁性

# ## 更改思路分析

# ### 设计思路演进

# 1. __从静态到动态__：之前的 `expert_knowledge` 是硬编码的单一技能，现在改为可参数化的 `load_skill`，支持多种技能
# 2. __从单一到多样__：支持 `kk` 和 `qq` 两种技能，为未来扩展更多技能奠定了基础
# 3. __从特殊处理到统一接口__：移除了特殊处理逻辑，所有工具使用相同的调用模式

# ### 架构改进

# - __可扩展性__：通过添加新的条件分支，可以轻松支持更多技能
# - __一致性__：所有工具现在都有统一的参数化接口
# - __清晰性__：技能加载逻辑集中在一个函数中，便于维护

# ### 技能系统演进路径

# 这次更改是技能系统演进的重要一步：

# 1. __阶段1__：硬编码的单一技能 (`expert_knowledge`)
# 2. __阶段2__：参数化的多技能系统 (`load_skill`)
# 3. __未来阶段__：可能发展为从文件系统动态加载技能

# ### 技术实现亮点

# - 保持了向后兼容性（kk技能内容不变）
# - 通过函数封装实现了更好的代码组织
# - 打印执行日志便于调试
# - 统一的错误处理机制

# 这个更改体现了agent架构从简单到复杂、从硬编码到可配置的自然演进过程，为构建更强大的技能系统奠定了基础。
