"""LLM 客户端 — 统一调用 OpenAI 兼容接口。

支持 OpenAI / Claude / DeepSeek / Gemini / 通义千问 / 火山引擎(豆包) / Ollama / 自定义 API。
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional


_DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "claude": "https://api.anthropic.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "volcengine_llm": "https://ark.cn-beijing.volces.com/api/v3",
    "ollama": "http://localhost:11434/v1",
    "custom_llm": "",
}

_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "claude": "claude-sonnet-4-20250514",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.5-flash",
    "qwen": "qwen-plus",
    "volcengine_llm": "doubao-seed-2-0-lite-260215",
    "ollama": "llama3.2",
    "custom_llm": "",
}


def test_llm_connection(
    provider_id: str,
    provider_cfg: dict,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """验证 LLM 连接是否可用，返回 (是否成功, 提示信息)。"""
    api_url = (provider_cfg.get("api_url") or "").strip()
    if not api_url:
        api_url = _DEFAULT_URLS.get(provider_id, "")
    if not api_url:
        return False, "未设置 API 地址"

    api_url = api_url.rstrip("/")
    if not api_url.endswith("/chat/completions"):
        api_url += "/chat/completions"

    model = (provider_cfg.get("model") or "").strip()
    if not model:
        model = _DEFAULT_MODELS.get(provider_id, "")
    if not model:
        return False, "未设置模型名称"

    api_key = (provider_cfg.get("api_key") or "").strip()

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.1,
        "max_tokens": 10,
    }
    headers = _build_headers(api_key)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                return True, "验证通过，已保存"
            return False, "API 返回格式异常，请检查地址和模型"
    except urllib.error.HTTPError as e:
        msg_map = {
            401: "API Key 无效或已过期",
            403: "无访问权限，请检查 API Key 或 API 地址",
            404: "API 地址不正确或模型不存在",
            429: "请求频率超限，请稍后重试",
        }
        detail = msg_map.get(e.code, e.reason)
        return False, f"HTTP {e.code}: {detail}"
    except urllib.error.URLError as e:
        return False, f"无法连接: {e.reason}"
    except Exception as e:
        return False, f"请求异常: {str(e)[:80]}"


_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _build_headers(api_key: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _UA,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def call_llm(
    provider_id: str,
    provider_cfg: dict,
    messages: list[dict],
    temperature: float = 0.3,
    timeout: float = 10.0,
    tools: list[dict] | None = None,
) -> Optional[str | dict]:
    """Call LLM via OpenAI-compatible chat completions API.

    Without tools: returns assistant message content string, or None.
    With tools: returns the full message dict (may contain tool_calls), or None.
    """
    api_url = (provider_cfg.get("api_url") or "").strip()
    if not api_url:
        api_url = _DEFAULT_URLS.get(provider_id, "")
    if not api_url:
        return None

    api_url = api_url.rstrip("/")
    if not api_url.endswith("/chat/completions"):
        api_url += "/chat/completions"

    model = (provider_cfg.get("model") or "").strip()
    if not model:
        model = _DEFAULT_MODELS.get(provider_id, "")
    if not model:
        return None

    api_key = (provider_cfg.get("api_key") or "").strip()

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools

    headers = _build_headers(api_key)

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                if tools:
                    return msg
                return (msg.get("content") or "").strip()
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, Exception) as e:
        print(f"[LLM] {provider_id} error: {e}")

    return None
