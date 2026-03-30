"""飞书/Lark Open Platform — 通过本机 lark-cli 子进程执行命令。

依赖用户已安装并登录：https://github.com/larksuite/cli
  npm install -g @larksuite/cli
  lark-cli config init
  lark-cli auth login --recommend
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Iterable

_MAX_ARGS = 64
_MAX_ARG_LEN = 4000
_MAX_OUTPUT_CHARS = 12000
_DEFAULT_TIMEOUT_SEC = 90.0

_ARG_UNSAFE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

_EXTRA_BIN_DIRS = [
    os.path.expanduser("~/.npm-global/bin"),
    "/usr/local/bin",
    os.path.expanduser("~/.deskclaw/node/bin"),
]


def resolve_lark_cli_executable() -> tuple[str | None, list[str]]:
    """返回 (可执行文件路径, 前缀参数)。路径为 None 时表示使用 npx 调起。"""
    path = shutil.which("lark-cli")
    if path:
        return path, []

    for d in _EXTRA_BIN_DIRS:
        candidate = os.path.join(d, "lark-cli")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate, []

    npx = shutil.which("npx")
    if not npx:
        for d in _EXTRA_BIN_DIRS:
            candidate = os.path.join(d, "npx")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                npx = candidate
                break
    if npx:
        return npx, ["-y", "@larksuite/cli"]
    return None, []


def _validate_args(argv: Iterable[str]) -> str | None:
    args = list(argv)
    if not args:
        return "参数不能为空：至少需要一项子命令或选项（如 calendar +agenda）"
    if len(args) > _MAX_ARGS:
        return f"参数过多（最多 {_MAX_ARGS} 项）"
    for i, a in enumerate(args):
        if not isinstance(a, str):
            return "参数必须是字符串列表"
        if _ARG_UNSAFE.search(a):
            return "参数包含非法字符"
        if len(a) > _MAX_ARG_LEN:
            return f"第 {i + 1} 个参数过长（最多 {_MAX_ARG_LEN} 字符）"
    return None


def lark_cli_needs_confirm(argv: list[str]) -> tuple[bool, str]:
    """对明显有副作用的子命令要求用户确认。"""
    joined = " ".join(argv).lower()
    if "+messages-send" in joined or "messages-send" in joined:
        return True, "将使用飞书 CLI 发送消息，是否继续？"
    if "auth" in joined and "logout" in joined:
        return True, "将登出飞书 CLI（需重新登录），是否继续？"
    return False, ""


def run_lark_cli(argv: list[str], timeout_sec: float = _DEFAULT_TIMEOUT_SEC) -> str:
    err = _validate_args(argv)
    if err:
        return err

    exe, prefix = resolve_lark_cli_executable()
    if exe is None:
        return (
            "未找到 lark-cli 与 npx。请先安装 Node.js 后执行：\n"
            "npm install -g @larksuite/cli\n"
            "然后：lark-cli config init && lark-cli auth login --recommend"
        )

    cmd = [exe, *prefix, *argv]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=None,
        )
    except subprocess.TimeoutExpired:
        return f"飞书 CLI 执行超时（{int(timeout_sec)} 秒），请缩小查询范围后重试"
    except OSError as e:
        return f"无法启动飞书 CLI：{e}"

    out = (proc.stdout or "").strip()
    err_out = (proc.stderr or "").strip()
    if proc.returncode != 0:
        parts = []
        if err_out:
            parts.append(err_out)
        if out:
            parts.append(out)
        msg = "\n".join(parts) if parts else f"退出码 {proc.returncode}"
        if len(msg) > _MAX_OUTPUT_CHARS:
            msg = msg[: _MAX_OUTPUT_CHARS] + "\n…（输出已截断）"
        return f"飞书 CLI 失败：{msg}"

    text = out if out else "（无标准输出）"
    if err_out:
        text = f"{text}\n{err_out}" if text else err_out
    if len(text) > _MAX_OUTPUT_CHARS:
        text = text[: _MAX_OUTPUT_CHARS] + "\n…（输出已截断）"
    return text
