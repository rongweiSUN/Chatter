"""技能处理引擎 — ASR 文本后处理。

auto_run 开启后始终经过 LLM 基础层（去口语 / 去重复 / 改口修正 / 基础结构化），
各开关（oral_filter、auto_structure 等）作为增强选项叠加在基础层之上。
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


def process_text(text: str, field_context: str | None = None,
                  app_name: str | None = None) -> ProcessResult:
    """Main entry: apply all enabled skills to ASR text.

    field_context: 当前输入框已有文本（通过 AX API 读取），供 LLM 推断语气风格。
    app_name: 用户当前使用的应用名称。
    """
    agent_result = handle_voice_command(text)
    if agent_result.handled:
        return ProcessResult(text=agent_result.message, handled_by_agent=True)

    s = get_settings()
    sk = s.skills

    if not sk.auto_run:
        return ProcessResult(text=text, handled_by_agent=False)

    provider_id = s.default_llm
    provider_cfg = s.providers.get(provider_id, {})
    if provider_id and provider_cfg:
        prompt = _build_system_prompt(sk, field_context, app_name)
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


def _build_system_prompt(sk: SkillsConfig, field_context: str | None = None,
                         app_name: str | None = None) -> str:
    parts = [
        "你是一个语音输入后处理助手。用户会给你一段语音识别的原始文本，"
        "请按以下规则处理后，只输出处理后的纯文本，不要添加任何解释。"
    ]

    # ── 当前应用 ──
    if app_name:
        parts.append(
            f"\n\n【当前应用】用户正在「{app_name}」中输入。"
            "\n请根据应用场景调整语气和格式：例如在聊天软件中保持口语化和简短，"
            "在备忘录/文档中使用更规范的书面语，在代码编辑器中保留技术术语原样。"
        )

    # ── 基础层：始终生效 ──
    parts.append(
        "\n\n【基础处理】（始终生效）"
        "\n1. 去除语气词和口头禅（嗯、啊、那个、就是说、然后、对吧等）"
        "\n2. 去除重复的词语和句子片段"
        "\n3. 改口修正（重要）：用户说话中途口误或改主意时，只保留最终正确版本。"
        "识别以下模式并仅保留修正后的内容："
        "\n   - 否定改口：「周三，不对，周四」→「周四」"
        "\n   - 换一个：「橙子，算了，换成橘子」→「橘子」"
        "\n   - 去掉/删掉：「苹果、香蕉、橙子，橙子去掉」→「苹果、香蕉」"
        "\n   - 重说/我再说一遍：「明天开会，不是，后天开会」→「后天开会」"
        "\n   - 犹豫后确定：「买三个，不，五个吧」→「买五个」"
        "\n4. 保持自然的书面表达，不过度修改原意和用词。"
        "除去语气词、重复和改口部分外，尽可能保留用户原本表达的所有信息和细节，"
        "不要省略、概括或合并用户实际说出的内容"
        "\n5. 智能格式化：如果内容包含多个并列项目（如购物清单、待办事项、步骤说明等），"
        "可以整理为清晰的列表格式。但必须保留用户的完整语句，不能只提取列表项而丢掉前后文。"
        "\n   正确示例：「我想买水果、牛奶、香蕉」→「我想买：\n- 水果\n- 牛奶\n- 香蕉」"
        "\n   错误示例：「我想买水果、牛奶、香蕉」→「- 水果\n- 牛奶\n- 香蕉」（丢失了「我想买」）"
        "\n   如果是普通句子则不要强行列表化"
    )

    # ── 输入框上下文 ──
    if field_context:
        parts.append(
            "\n\n【输入框上下文】"
            "\n用户当前正在编辑的内容如下（仅供参考语气和风格）："
            f"\n---\n{field_context}\n---"
            "\n请让处理后的文本在语气、措辞风格上与上述内容自然衔接。"
        )

    # ── 增强选项 ──
    enhancements = []

    if sk.oral_filter:
        enhancements.append(
            "【深度口语优化】在基础去口语之上，进一步将口语化的表达转换为精炼的书面语，"
            "去除所有口语化的连接词和冗余表达，使文本更加简洁专业"
        )

    if sk.auto_structure:
        enhancements.append(
            "【增强结构化】如果内容包含多个要点或步骤，使用换行和序号整理成清晰的结构；"
            "如果是简短的一句话则不需要结构化"
        )

    if sk.personalize and sk.personalize_text.strip():
        enhancements.append(f"【个性化偏好】{sk.personalize_text.strip()}")

    if sk.user_dict and sk.user_dict_text.strip():
        words = [w.strip() for w in sk.user_dict_text.strip().split("\n") if w.strip()]
        if words:
            enhancements.append(
                "【用户词典】以下是专有名词，如果识别文本中出现类似发音，请纠正为正确写法：\n"
                + "、".join(words)
            )

    for cs in getattr(sk, "custom_skills", []):
        if cs.get("enabled") and cs.get("prompt", "").strip():
            name = cs.get("name", "自定义技能")
            enhancements.append(f"【{name}】{cs['prompt'].strip()}")

    if enhancements:
        parts.append("\n\n以下为增强选项，请在基础处理的基础上额外执行：")
        for i, rule in enumerate(enhancements, 1):
            parts.append(f"\n{i}. {rule}")

    parts.append(
        "\n\n重要：只输出处理后的文本，不要输出任何标记、解释或额外内容。"
    )
    return "".join(parts)


def process_with_instruction(selected_text: str, instruction: str) -> str | None:
    """用语音指令处理选中文字：将选中文字和语音指令一起发给 LLM。

    成功返回处理后的文字，LLM 失败或未配置时返回 None。
    """
    s = get_settings()
    provider_id = s.default_llm
    provider_cfg = s.providers.get(provider_id, {})

    if not provider_id or not provider_cfg:
        print("[指令模式] 未配置大模型，跳过")
        return None

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
        timeout=15.0,
    )

    if result:
        print(f"[指令模式] LLM 返回: {result[:80]}")
        return result

    print("[指令模式] LLM 无返回")
    return None


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
