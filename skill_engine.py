"""技能处理引擎 — ASR 文本后处理。

根据启用的技能，对识别文本进行优化处理：
- 去末尾标点：纯正则，无需 LLM
- 口语过滤 / 自动结构化 / 个性化偏好 / 用户词典：需要 LLM
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from settings import SkillsConfig, get_settings
from llm_client import call_llm
from voice_agent import handle_voice_command


@dataclass
class ProcessResult:
    text: str
    handled_by_agent: bool = False


def process_text(text: str) -> ProcessResult:
    """Main entry: apply all enabled skills to ASR text."""
    agent_result = handle_voice_command(text)
    if agent_result.handled:
        return ProcessResult(text=agent_result.message, handled_by_agent=True)

    s = get_settings()
    sk = s.skills

    if not sk.auto_run:
        return ProcessResult(text=text, handled_by_agent=False)

    has_custom = any(
        cs.get("enabled") and cs.get("prompt", "").strip()
        for cs in getattr(sk, "custom_skills", [])
    )
    needs_llm = sk.oral_filter or sk.auto_structure or sk.personalize or sk.user_dict or has_custom

    if needs_llm:
        provider_id = s.default_llm
        provider_cfg = s.providers.get(provider_id, {})
        if provider_id and provider_cfg:
            prompt = _build_system_prompt(sk)
            result = call_llm(
                provider_id=provider_id,
                provider_cfg=provider_cfg,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
            )
            if result:
                text = result

    if sk.remove_trailing_punct:
        text = _remove_trailing_punct(text)

    return ProcessResult(text=text, handled_by_agent=False)


def _build_system_prompt(sk: SkillsConfig) -> str:
    parts = [
        "你是一个语音输入后处理助手。用户会给你一段语音识别的原始文本，"
        "请你按照以下要求处理后，只输出处理后的纯文本，不要添加任何解释。"
    ]

    rules = []

    if sk.oral_filter:
        rules.append(
            '【口语过滤】去除口语中的语气词、重复、冗余表达（如"嗯"、"那个"、"就是说"、"然后"等），'
            "使文本更简洁书面化，但保留原意"
        )

    if sk.auto_structure:
        rules.append(
            "【自动结构化】如果内容包含多个要点或步骤，使用换行和序号整理成清晰的结构；"
            "如果是简短的一句话则不需要结构化"
        )

    if sk.personalize and sk.personalize_text.strip():
        rules.append(f"【个性化偏好】{sk.personalize_text.strip()}")

    if sk.user_dict and sk.user_dict_text.strip():
        words = [w.strip() for w in sk.user_dict_text.strip().split("\n") if w.strip()]
        if words:
            rules.append(
                "【用户词典】以下是专有名词，如果识别文本中出现类似发音，请纠正为正确写法：\n"
                + "、".join(words)
            )

    for cs in getattr(sk, "custom_skills", []):
        if cs.get("enabled") and cs.get("prompt", "").strip():
            name = cs.get("name", "自定义技能")
            rules.append(f"【{name}】{cs['prompt'].strip()}")

    for i, rule in enumerate(rules, 1):
        parts.append(f"\n{i}. {rule}")

    parts.append(
        "\n\n重要：只输出处理后的文本，不要输出任何标记、解释或额外内容。"
    )
    return "".join(parts)


def process_with_instruction(selected_text: str, instruction: str) -> str:
    """用语音指令处理选中文字：将选中文字和语音指令一起发给 LLM。

    LLM 失败或未配置时返回原始选中文字（不破坏用户内容）。
    """
    s = get_settings()
    provider_id = s.default_llm
    provider_cfg = s.providers.get(provider_id, {})

    if not provider_id or not provider_cfg:
        print("[指令模式] 未配置大模型，跳过")
        return selected_text

    system_prompt = (
        "你是一个文本处理助手。用户选中了一段文字，并通过语音给出了处理指令。\n"
        "请严格根据用户的指令处理选中的文字，只输出处理后的结果，"
        "不要添加任何解释、标记或额外内容。"
    )

    user_content = f"【选中的文字】\n{selected_text}\n\n【用户指令】\n{instruction}"

    print(f"[指令模式] 调用 LLM: 选中{len(selected_text)}字, 指令={instruction[:40]}")
    result = call_llm(
        provider_id=provider_id,
        provider_cfg=provider_cfg,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    if result:
        print(f"[指令模式] LLM 返回: {result[:80]}")
        return result

    print("[指令模式] LLM 无返回，保持原文")
    return selected_text


def classify_intent(selected_text: str, instruction: str) -> str:
    """轻量 LLM 调用判断用户意图：改写 or 提问。

    LLM 未配置或调用失败时 fallback 到 rewrite。
    """
    s = get_settings()
    provider_id = s.default_llm
    provider_cfg = s.providers.get(provider_id, {})
    if not provider_id or not provider_cfg:
        return "rewrite"

    system_prompt = (
        "判断用户对选中文字的操作意图。\n"
        "如果用户想修改/改写/翻译/润色选中文字，回复 rewrite\n"
        "如果用户在对选中文字提问/询问/要求解释/分析/总结，回复 question\n"
        "只回复一个单词：rewrite 或 question"
    )
    user_content = f"选中文字：{selected_text[:200]}\n用户语音：{instruction}"

    try:
        result = call_llm(
            provider_id=provider_id,
            provider_cfg=provider_cfg,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            timeout=5.0,
        )
        if result and "question" in result.strip().lower():
            print(f"[意图分类] question (原始={result.strip()})")
            return "question"
    except Exception as e:
        print(f"[意图分类] 异常，fallback rewrite: {e}")

    print(f"[意图分类] rewrite")
    return "rewrite"


def answer_question(selected_text: str, question: str) -> str:
    """对选中文字进行问答，返回回答内容。"""
    s = get_settings()
    provider_id = s.default_llm
    provider_cfg = s.providers.get(provider_id, {})
    if not provider_id or not provider_cfg:
        return "未配置大模型，无法回答"

    system_prompt = (
        "用户选中了一段文字并提出了问题。"
        "请针对选中的文字内容回答用户的问题。"
        "回答应简洁、准确、有帮助。使用中文回答。"
    )
    user_content = f"【选中的文字】\n{selected_text}\n\n【用户问题】\n{question}"

    print(f"[选中提问] 调用 LLM: 选中{len(selected_text)}字, 问题={question[:40]}")
    result = call_llm(
        provider_id=provider_id,
        provider_cfg=provider_cfg,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        timeout=15.0,
    )
    if result:
        print(f"[选中提问] LLM 返回: {result[:80]}")
        return result

    return "抱歉，未能获取回答"


def _remove_trailing_punct(text: str) -> str:
    return re.sub(r'[。！？；，、．.!?;,]+$', '', text)
