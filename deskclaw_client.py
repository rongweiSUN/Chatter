"""DeskClaw 本地 Gateway 客户端。

通过 HTTP 调用本地运行的 DeskClaw Gateway Adapter，
将消息发送给 DeskClaw Agent 处理。
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
import urllib.error

GATEWAY_URL = "http://127.0.0.1:18790"
DEFAULT_TIMEOUT = 120.0

_session_id: str | None = None


class DeskClawUnavailable(Exception):
    """DeskClaw Gateway 无法连接。"""


def chat(message: str, *, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """发送消息给 DeskClaw，返回 {content, session_id, run_id, tool_calls}。"""
    global _session_id

    payload: dict = {"message": message}
    if _session_id:
        payload["session_id"] = _session_id

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GATEWAY_URL}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except ConnectionRefusedError as e:
        raise DeskClawUnavailable("无法连接 DeskClaw，请确认应用已启动") from e
    except (urllib.error.URLError, OSError) as e:
        if any(k in str(e) for k in ("Connection refused", "No route", "timed out")):
            raise DeskClawUnavailable(
                "无法连接 DeskClaw，请确认应用已启动"
            ) from e
        raise

    raw = resp.read()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[DeskClaw] 响应解析失败: {raw[:200]}", flush=True)
        raise RuntimeError(f"DeskClaw 返回了无法解析的响应: {e}") from e
    _session_id = body.get("session_id")
    return body


def is_available(timeout: float = 3.0) -> bool:
    """检查 DeskClaw Gateway 是否可用。"""
    try:
        req = urllib.request.Request(f"{GATEWAY_URL}/health")
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("status") == "ok"
    except Exception:
        return False


def open_deskclaw_app() -> bool:
    """激活 DeskClaw 应用（与 Gateway 配套的桌面端对话界面）。"""
    for name in ("DeskClaw",):
        try:
            r = subprocess.run(
                ["open", "-a", name],
                capture_output=True,
                timeout=8,
            )
            if r.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    for bundle_id in ("ai.openclaw.mac", "ai.openclaw.mac.debug"):
        try:
            r = subprocess.run(
                ["open", "-b", bundle_id],
                capture_output=True,
                timeout=8,
            )
            if r.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False
