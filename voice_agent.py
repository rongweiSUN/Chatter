from __future__ import annotations

"""语音 Agent — LLM 驱动的设置/技能管理。

用户说任意自然语言，LLM 判断意图并调用工具函数执行。
"""

import datetime
import json
import time
from dataclasses import dataclass

from confirm_dialog import confirm_high_risk
from lark_cli_runner import lark_cli_needs_confirm, run_lark_cli
from settings import get_settings, save_settings
from llm_client import call_llm


@dataclass
class AgentResult:
    handled: bool
    message: str = ""


# ── 工具定义（OpenAI function calling schema） ──

TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "toggle_setting",
            "description": "开启或关闭一个设置项或技能开关",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "enum": [
                            "auto_paste", "show_float_window", "auto_run",
                            "oral_filter", "auto_structure", "remove_trailing_punct",
                            "personalize", "user_dict",
                        ],
                        "description": "设置项标识。auto_paste=自动粘贴, show_float_window=悬浮窗, "
                                       "auto_run=技能自动运行, oral_filter=口语过滤, "
                                       "auto_structure=自动结构化, remove_trailing_punct=去末尾标点, "
                                       "personalize=个性化偏好, user_dict=用户词典",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "true=开启, false=关闭",
                    },
                },
                "required": ["key", "enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_settings",
            "description": "查看当前所有设置和技能开关的状态",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "列出所有已配置的自定义技能",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_skill",
            "description": "添加一个自定义技能",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称"},
                    "prompt": {"type": "string", "description": "技能的提示词，描述该技能如何处理文本"},
                },
                "required": ["name", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_skill",
            "description": "删除一个自定义技能",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "要删除的技能名称"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_skill",
            "description": "启用或禁用一个已存在的自定义技能",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称"},
                    "enabled": {"type": "boolean", "description": "true=启用, false=禁用"},
                },
                "required": ["name", "enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_all_skills",
            "description": "清空所有自定义技能",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_lark_cli",
            "description": (
                "在本机执行飞书/Lark 官方 CLI（lark-cli），用于日历、消息、文档、多维表格等开放平台能力。"
                "用户需已安装并登录 CLI。参数为传给 lark-cli 的参数列表，不要包含可执行文件名；"
                "不要使用 shell；可读操作可直接调用，发送消息等会先弹窗确认。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "CLI 参数列表。示例：[\"calendar\",\"+agenda\"]；"
                            "[\"calendar\",\"+create\",\"--summary\",\"会议\",\"--start\",\"2026-03-12T14:00:00+08:00\",\"--end\",\"2026-03-12T15:00:00+08:00\"]；"
                            "[\"auth\",\"status\"]；"
                            "[\"im\",\"+messages-send\",\"--chat-id\",\"oc_xxx\",\"--text\",\"你好\"]。"
                            "创建日程必须用 +create，且 --start/--end 为含时区的 ISO 8601。复杂 JSON 可用 CLI 的 --params / --body。"
                        ),
                    },
                },
                "required": ["args"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "你是「随口说」语音助手的 Agent。用户通过语音给你下达指令来管理应用设置和技能。\n"
    "请根据用户的意图调用对应的工具函数。如果用户的话不是管理指令（比如闲聊、提问），"
    "请直接回复一句简短的文字，不要调用任何工具。\n"
    "注意：用户输入来自语音识别，可能有错别字或口语化表达，请尽量理解真实意图。\n\n"
    "【飞书/Lark】当用户明确要通过飞书办事（看/创日程、发消息、查文档、表格、任务等）时，"
    "调用 run_lark_cli，把子命令与选项拆成字符串数组传入 args（不要包含可执行文件名）。\n"
    "- 查看日程：`calendar` + `+agenda`。\n"
    "- 创建日程：必须用 `calendar` + `+create`，并给出 `--summary`（标题）、`--start`、`--end`。"
    "时间为 ISO 8601 且须带时区（国内常用 +08:00），例如 `2026-03-12T14:00:00+08:00`。"
    "用户只说开始时间时，若无时长线索默认会议 30 分钟；用户未给标题时可据语义拟定简短标题。"
    "需要邀请时再附加 `--attendee-ids`，值为逗号分隔的 open_id（ou_/oc_/omm_ 等前缀保留）。\n"
    '- "随口说查看我今天飞书日程" → run_lark_cli(args=["calendar","+agenda"])\n'
    '- "随口说明天下午三点飞书加个会议叫周会" → 根据下方「当前本地时间」推算明天日期后 '
    'run_lark_cli(args=["calendar","+create","--summary","周会","--start","…+08:00","--end","…+08:00"])\n'
    '- "随口说飞书登录了没" → run_lark_cli(args=["auth","status"])\n'
    "切勿调用 auth login：登录必须用户在终端里执行 lark-cli auth login --recommend（应用内无交互环境会失败或卡住）。\n"
    "用户说要「登录飞书」时，用文字引导其打开终端按步骤操作，可建议先 auth status 自查。\n"
    "未安装 CLI 或权限不足时，用工具返回的提示简短告知用户去终端执行 npm install -g @larksuite/cli 并完成 config init 与 auth login。\n\n"
    "添加技能示例：\n"
    '- "添加技能英文润色，把内容润色成自然的英文" → add_skill(name="英文润色", prompt="把内容润色成自然的英文")\n'
    '- "创建一个翻译技能，翻译成英文" → add_skill(name="翻译", prompt="将用户输入的内容翻译成英文")\n'
    '- "加个技能叫摘要，帮我总结要点" → add_skill(name="摘要", prompt="帮我总结要点")\n\n'
    "启用/禁用技能示例：\n"
    '- "打开翻译" / "开启翻译技能" → toggle_skill(name="翻译", enabled=true)\n'
    '- "关闭翻译" / "禁用翻译" → toggle_skill(name="翻译", enabled=false)\n'
)

_KEY_DISPLAY = {
    "auto_paste": "自动粘贴",
    "show_float_window": "悬浮窗",
    "auto_run": "技能自动运行",
    "oral_filter": "口语过滤",
    "auto_structure": "自动结构化",
    "remove_trailing_punct": "去末尾标点",
    "personalize": "个性化偏好",
    "user_dict": "用户词典",
}


# ── 工具执行 ──

def _exec_toggle_setting(args: dict) -> str:
    key = args.get("key", "")
    enabled = args.get("enabled", True)
    if key not in _KEY_DISPLAY:
        return f"未知的设置项：{key}"

    s = get_settings()
    sk = s.skills
    if hasattr(s, key):
        setattr(s, key, enabled)
    elif hasattr(sk, key):
        setattr(sk, key, enabled)
    else:
        return f"无法设置：{key}"
    save_settings(s)
    action = "开启" if enabled else "关闭"
    return f"已{action}「{_KEY_DISPLAY[key]}」"


def _exec_query_settings(_args: dict) -> str:
    s = get_settings()
    sk = s.skills
    lines = []
    for key, name in _KEY_DISPLAY.items():
        val = getattr(s, key, None)
        if val is None:
            val = getattr(sk, key, None)
        lines.append(f"{name}: {'开' if val else '关'}")
    return "；".join(lines)


def _exec_list_skills(_args: dict) -> str:
    s = get_settings()
    skills = s.skills.custom_skills
    if not skills:
        return "当前没有自定义技能"
    parts = []
    for item in skills:
        status = "启用" if item.get("enabled") else "禁用"
        parts.append(f"「{item.get('name', '?')}」({status})")
    return f"自定义技能共 {len(skills)} 个：" + "、".join(parts)


def _exec_add_skill(args: dict) -> str:
    name = (args.get("name") or "").strip()
    prompt = (args.get("prompt") or "").strip()
    if not name or not prompt:
        return "添加失败：技能名和提示词都不能为空"
    s = get_settings()
    sk = s.skills
    sk.custom_skills = [item for item in sk.custom_skills if item.get("name") != name]
    skill_id = f"cs_{int(time.time() * 1000)}"
    sk.custom_skills.append({"id": skill_id, "name": name, "enabled": True, "prompt": prompt})
    save_settings(s)
    return f"已添加技能「{name}」"


def _exec_delete_skill(args: dict) -> str:
    name = (args.get("name") or "").strip()
    if not name:
        return "删除失败：请提供技能名称"
    if not confirm_high_risk("确认删除技能", f"将删除技能「{name}」，且无法撤销。"):
        return f"已取消删除技能「{name}」"
    s = get_settings()
    sk = s.skills
    old_len = len(sk.custom_skills)
    sk.custom_skills = [
        item for item in sk.custom_skills if (item.get("name") or "").strip() != name
    ]
    if len(sk.custom_skills) == old_len:
        return f"未找到技能「{name}」"
    save_settings(s)
    return f"已删除技能「{name}」"


def _exec_toggle_skill(args: dict) -> str:
    name = (args.get("name") or "").strip()
    enabled = args.get("enabled", True)
    if not name:
        return "请提供技能名称"
    s = get_settings()
    sk = s.skills
    for item in sk.custom_skills:
        if (item.get("name") or "").strip() == name:
            item["enabled"] = enabled
            save_settings(s)
            action = "启用" if enabled else "禁用"
            return f"已{action}技能「{name}」"
    return f"未找到技能「{name}」"


def _exec_clear_all_skills(_args: dict) -> str:
    if not confirm_high_risk("确认清空自定义技能", "将删除全部自定义技能，且无法撤销。"):
        return "已取消清空自定义技能"
    s = get_settings()
    s.skills.custom_skills = []
    save_settings(s)
    return "已清空全部自定义技能"


def _exec_run_lark_cli(args: dict) -> str:
    raw = args.get("args")
    if not isinstance(raw, list) or not raw:
        return "请提供 args 数组，例如 [\"calendar\",\"+agenda\"]"

    argv: list[str] = []
    for i, x in enumerate(raw):
        if not isinstance(x, str):
            x = str(x)
        s = x.strip()
        if not s:
            return f"第 {i + 1} 个参数不能为空"
        argv.append(s)

    need_confirm, detail = lark_cli_needs_confirm(argv)
    if need_confirm and not confirm_high_risk("飞书 CLI", detail):
        return "已取消飞书 CLI 操作"

    return run_lark_cli(argv)


_TOOL_DISPATCH = {
    "toggle_setting": _exec_toggle_setting,
    "query_settings": _exec_query_settings,
    "list_skills": _exec_list_skills,
    "add_skill": _exec_add_skill,
    "delete_skill": _exec_delete_skill,
    "toggle_skill": _exec_toggle_skill,
    "clear_all_skills": _exec_clear_all_skills,
    "run_lark_cli": _exec_run_lark_cli,
}


# ── Agent 主入口 ──

def handle_voice_command(text: str, require_wake_word: bool = True) -> AgentResult:
    cmd = (text or "").strip()
    if not cmd:
        return AgentResult(False, "")

    if require_wake_word:
        normalized = cmd.replace("，", "").replace("。", "").replace(" ", "")
        if "随口说" not in normalized:
            return AgentResult(False, "")

    s = get_settings()
    provider_id = s.default_llm
    provider_cfg = s.providers.get(provider_id, {})
    if not provider_id or not provider_cfg:
        print("[语音Agent] 未配置大模型，无法执行")
        return AgentResult(True, "请先配置大模型才能使用语音助手")

    now = datetime.datetime.now().astimezone()
    time_hint = (
        "【当前本地时间】"
        f"{now.strftime('%Y-%m-%d %H:%M')} {now.tzname() or ''}（ISO：{now.isoformat(timespec='seconds')}）。"
        "推断「今天、明天、本周、下周一」等时请以此为准；每周第一天为周一。\n"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + time_hint},
        {"role": "user", "content": cmd},
    ]

    print(f"[语音Agent] 调用 LLM: {cmd[:60]}", flush=True)
    result = call_llm(
        provider_id=provider_id,
        provider_cfg=provider_cfg,
        messages=messages,
        tools=TOOLS_SCHEMA,
        temperature=0.1,
        timeout=15.0,
    )

    if result is None:
        print("[语音Agent] LLM 无响应", flush=True)
        return AgentResult(True, "语音助手暂时无法响应，请稍后再试")

    if isinstance(result, str):
        return AgentResult(True, result)

    tool_calls = result.get("tool_calls")
    content = (result.get("content") or "").strip()

    if not tool_calls:
        return AgentResult(True, content or "收到，但未识别到具体操作")

    responses = []
    for tc in tool_calls:
        fn_name = tc.get("function", {}).get("name", "")
        fn_args_raw = tc.get("function", {}).get("arguments", "{}")
        try:
            fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
        except json.JSONDecodeError:
            fn_args = {}

        print(f"[语音Agent] 执行工具: {fn_name}({fn_args})", flush=True)

        executor = _TOOL_DISPATCH.get(fn_name)
        if executor:
            resp = executor(fn_args)
        else:
            resp = f"未知工具：{fn_name}"
        responses.append(resp)

    final = "；".join(responses)
    print(f"[语音Agent] 结果: {final}", flush=True)
    return AgentResult(True, final)
