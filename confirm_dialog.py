from __future__ import annotations

"""高危操作确认弹窗。"""

import subprocess


def confirm_high_risk(action_title: str, detail: str = "") -> bool:
    title = _escape_osascript(action_title.strip() or "确认高危操作")
    body = _escape_osascript(detail.strip() or "该操作不可恢复，是否继续？")
    script = (
        f'display dialog "{body}" with title "{title}" '
        'buttons {"取消", "确认"} default button "取消" with icon caution'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return result.returncode == 0 and "button returned:确认" in (result.stdout or "")
    except Exception:
        return False


def _escape_osascript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
