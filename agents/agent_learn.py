# Two-layer skill injection that avoids bloating the system prompt:

#     Layer 1 (cheap): skill names in system prompt (~100 tokens/skill)
#     Layer 2 (on demand): full skill body in tool_result

#     skills/
#       pdf/
#         SKILL.md          <-- frontmatter (name, description) + body
#       code-review/
#         SKILL.md

#     System prompt:
#     +--------------------------------------+
#     | You are a coding agent.              |
#     | Skills available:                    |
#     |   - pdf: Process PDF files...        |  <-- Layer 1: metadata only
#     |   - code-review: Review code...      |
#     +--------------------------------------+

#     When model calls load_skill("pdf"):
#     +--------------------------------------+
#     | tool_result:                         |
#     | <skill>                              |
#     |   Full PDF processing instructions   |  <-- Layer 2: full body
#     |   Step 1: ...                        |
#     |   Step 2: ...                        |
#     | </skill>                             |
#     +--------------------------------------+

# Key insight: "Don't put everything in the system prompt. Load on demand."

import subprocess

from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
WORKDIR = Path.cwd()
client = anthropic.Anthropic(base_url="https://api.deepseek.com/anthropic")
model = "deepseek-chat"

class SkillLoader:
    def __init__(self):
        self.skills = {
            "kk": {
                "description": "how to get kk",
                "content": """You can get kk through 3 steps:
                                1.go to shanghai for A
                                2.go to beijing for B
                                3.With A and B, you can get kk in wuhan""",
            },
            "qq": {
                "description": "how to get qq",
                "content": """You can get qq through 3 steps:
                                1.go to shanghai for AA
                                2.go to beijing for BB
                                3.With AA and BB, you can get qq in wuhan""",
            },
        }

    def get_content(self, name: str) -> str:
        skill = self.skills.get(name)
        if skill:
            return skill["content"]
        else:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills.keys())}"

    def get_descriptions(self) -> str:
        """Get all skill descriptions as formatted string."""
        lines = []
        for name, skill in self.skills.items():
            lines.append(f"{name} : {skill['description']}")
        return "\n".join(lines)

# Create a global instance
skill_loader = SkillLoader()

# Build SYSTEM prompt dynamically using skill_loader.getdescription()
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
{skill_loader.get_descriptions()}"""


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
    "load_skill": lambda **kw: skill_loader.get_content(kw["name"]),
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

# __`agent_learn.py` 文件的当前更改总结：__

# __主要变更：__

# 1. __SkillLoader 从函数重构为类__：

#    - 原来的 `SkillLoader()` 函数变为 `SkillLoader` 类
#    - 添加了 `__init__` 方法初始化技能数据
#    - 技能数据结构：每个技能包含 `description` 和 `content` 字段

# 2. __新增了两个核心方法__：

#    - `get_content(name: str) -> str`：根据技能名称返回详细内容
#    - `get_descriptions() -> str`：返回所有技能的格式化描述字符串

# 3. __SYSTEM prompt 动态化__：

#    - 从硬编码的 "kk : how to get kk" 和 "qq : how to get qq"
#    - 改为使用 `skill_loader.get_descriptions()` 动态获取
#    - 实现了技能描述的集中管理

# 4. __工具处理优化__：

#    - `TOOL_HANDLERS` 中的 `load_skill` 工具使用 `skill_loader.get_content()`
#    - 保持了与原有工具调用方式的兼容性

# 5. __代码架构改进__：

#    - 技能数据集中存储在 `SkillLoader` 类中
#    - 便于未来添加新技能
#    - 错误处理更加完善（未知技能返回友好错误信息）

# __当前技能数据：__

# - `kk`：描述为 "kk : how to get kk"，包含3个步骤的详细内容
# - `qq`：描述为 "qq : how to get qq"，包含3个步骤的详细内容

# __设计理念：__ 实现了"两层技能注入"模式：

# - __第一层（系统提示中）__：只包含技能名称和简短描述
# - __第二层（按需加载）__：通过 `load_skill` 工具获取完整技能内容

# __最终效果：__

# - `SkillLoader` 类现在是一个功能完整的技能管理系统
# - SYSTEM prompt 动态显示可用技能
# - 代码更加模块化、可维护、可扩展
