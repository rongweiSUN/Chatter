from __future__ import annotations

"""将文本通过剪贴板 + 模拟 Cmd+V 粘贴到当前光标位置。

使用 pyobjc 原生 API：
- AppKit.NSPasteboard 操作剪贴板
- Quartz.CGEvent 模拟键盘事件
"""

import time

from AppKit import NSPasteboard, NSPasteboardTypeString
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)
import ctypes, ctypes.util
_as_lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
_as_lib.AXIsProcessTrusted.restype = ctypes.c_bool
def _ax_trusted() -> bool:
    return _as_lib.AXIsProcessTrusted()

_KEY_V = 9
_KEY_C = 8


def _get_clipboard() -> str | None:
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSPasteboardTypeString)


def _set_clipboard(text: str):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def _simulate_cmd_v() -> bool:
    """模拟 Cmd+V，返回是否成功。"""
    try:
        event_down = CGEventCreateKeyboardEvent(None, _KEY_V, True)
        if event_down is None:
            return False
        CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event_down)

        event_up = CGEventCreateKeyboardEvent(None, _KEY_V, False)
        CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event_up)
        return True
    except Exception:
        return False


def _simulate_cmd_c() -> bool:
    """模拟 Cmd+C 复制选中内容。"""
    try:
        event_down = CGEventCreateKeyboardEvent(None, _KEY_C, True)
        if event_down is None:
            return False
        CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event_down)

        event_up = CGEventCreateKeyboardEvent(None, _KEY_C, False)
        CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event_up)
        return True
    except Exception:
        return False


def get_selected_text() -> str | None:
    """通过模拟 Cmd+C 获取当前活跃应用中的选中文字。

    如果没有选中内容或无辅助功能权限，返回 None。
    会自动恢复原有剪贴板内容。
    """
    if not _ax_trusted():
        return None

    old = _get_clipboard()

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()

    if not _simulate_cmd_c():
        if old is not None:
            _set_clipboard(old)
        return None

    time.sleep(0.15)
    selected = _get_clipboard()

    if old is not None:
        _set_clipboard(old)
    else:
        pb.clearContents()

    if selected and selected.strip():
        print(f"[输入] 检测到选中文字: {selected.strip()[:50]}")
        return selected.strip()
    return None


def request_accessibility():
    """主动触发 macOS 辅助功能权限请求弹窗，并打开系统设置页面。"""
    try:
        import subprocess
        subprocess.Popen([
            "osascript", "-e",
            'tell application "System Preferences" to reveal anchor '
            '"Privacy_Accessibility" of pane id '
            '"com.apple.preference.security"',
        ])
        subprocess.Popen([
            "osascript", "-e",
            'tell application "System Preferences" to activate',
        ])
    except Exception as e:
        print(f"[输入] 打开辅助功能设置异常: {e}", flush=True)


def paste_text(text: str) -> bool:
    """将文本粘贴到当前光标位置。

    返回 True 表示模拟粘贴成功，False 表示仅复制到剪贴板（需用户手动粘贴）。
    """
    if not text:
        return True

    trusted = _ax_trusted()
    print(f"[输入] AXIsProcessTrusted={trusted}", flush=True)

    if not trusted:
        print("[输入] 无辅助功能权限，仅复制到剪贴板，尝试弹出权限请求", flush=True)
        _set_clipboard(text)
        request_accessibility()
        return False

    old_clipboard = _get_clipboard()

    _set_clipboard(text)
    time.sleep(0.05)

    ok = _simulate_cmd_v()
    print(f"[输入] 粘贴{'成功' if ok else '失败'}: {text}", flush=True)

    if ok:
        time.sleep(0.3)
        if old_clipboard is not None:
            _set_clipboard(old_clipboard)

    return ok
