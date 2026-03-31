from __future__ import annotations

"""语音 Agent — LLM 驱动的设置/技能管理。

用户说任意自然语言，LLM 判断意图并调用工具函数执行。
"""

import datetime
import json
import time
from dataclasses import dataclass

from confirm_dialog import confirm_high_risk
from settings import get_settings, save_settings
from llm_client import call_llm


@dataclass
class AgentResult:
    handled: bool
    message: str = ""
    used_tool: bool = False


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
]

SYSTEM_PROMPT = (
    "你是「随口说」语音助手的 Agent。用户通过语音给你下达指令来管理应用设置和技能。\n"
    "请根据用户的意图调用对应的工具函数。如果用户的话不是管理指令（比如闲聊、提问），"
    "请直接回复一句简短的文字，不要调用任何工具。\n"
    "注意：用户输入来自语音识别，可能有错别字或口语化表达，请尽量理解真实意图。\n\n"
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


_TOOL_DISPATCH = {
    "toggle_setting": _exec_toggle_setting,
    "query_settings": _exec_query_settings,
    "list_skills": _exec_list_skills,
    "add_skill": _exec_add_skill,
    "delete_skill": _exec_delete_skill,
    "toggle_skill": _exec_toggle_skill,
    "clear_all_skills": _exec_clear_all_skills,
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
    provider_id = s.default_llm_agent
    provider_cfg = s.providers.get(provider_id, {})
    if not provider_id or not provider_cfg or not provider_cfg.get("_configured"):
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
    return AgentResult(True, final, used_tool=True)
