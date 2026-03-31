from __future__ import annotations

"""将文本通过剪贴板 + 模拟 Cmd+V 粘贴到当前光标位置。

使用 pyobjc 原生 API：
- AppKit.NSPasteboard 操作剪贴板
- Quartz.CGEvent 模拟键盘事件
"""

import ctypes
import ctypes.util
import platform
import subprocess
import sys
import time

from AppKit import NSPasteboard, NSPasteboardTypeString
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

# AXIsProcessTrusted：直接从 HIServices 加载；返回值类型为 MacTypes.Boolean（unsigned char）。
_HISERVICES = (
    "/System/Library/Frameworks/ApplicationServices.framework/"
    "Versions/Current/Frameworks/HIServices.framework/HIServices"
)
try:
    _as_lib = ctypes.cdll.LoadLibrary(_HISERVICES)
except OSError:
    _as_lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
_as_lib.AXIsProcessTrusted.restype = ctypes.c_uint8
_as_lib.AXIsProcessTrusted.argtypes = []

def prompt_accessibility_registration() -> bool:
    """若尚无辅助功能权限，请求系统弹出授权流程。

    调用 AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: true})
    触发 macOS 标准对话框，并在「隐私与安全性 → 辅助功能」列表中自动注册本应用。

    使用 pyobjc NSDictionary 构建参数（toll-free bridge CFDictionary），
    避免 ctypes 手动构建 CF 对象在 py2app 环境中因 kCFBooleanTrue 为空指针导致 SIGSEGV。
    """
    if _ax_trusted():
        return True
    try:
        AXOpts = getattr(_as_lib, "AXIsProcessTrustedWithOptions", None)
        if AXOpts in (None, 0):
            request_accessibility()
            return _ax_trusted()

        import objc
        from Foundation import NSDictionary

        AXOpts.restype = ctypes.c_uint8
        AXOpts.argtypes = [ctypes.c_void_p]

        opts = NSDictionary.dictionaryWithObject_forKey_(
            True, "AXTrustedCheckOptionPrompt"
        )
        AXOpts(objc.pyobjc_id(opts))
        time.sleep(0.15)
        return _ax_trusted()
    except Exception as e:
        print(f"[输入] prompt_accessibility_registration 异常: {e}", flush=True)
        try:
            request_accessibility()
        except Exception:
            pass
        time.sleep(0.1)
        return _ax_trusted()


def _ax_trusted() -> bool:
    return bool(_as_lib.AXIsProcessTrusted())


def _ax_trusted_with_retry() -> bool:
    """首帧偶发未就绪时重试一次，减轻启动瞬间误判。"""
    if _ax_trusted():
        return True
    time.sleep(0.2)
    return _ax_trusted()


def accessibility_denied_user_hint() -> str:
    """用户已在设置里打开开关仍失败时的说明（TCC 绑定的是当前二进制路径）。"""
    try:
        from AppKit import NSBundle

        b = NSBundle.mainBundle()
        bp = b.bundlePath() if b else None
    except Exception:
        bp = None
    parts = [
        "若此处已开启但仍无法粘贴：请到「隐私与安全性 → 辅助功能」中移除「随口说」"
        "或列表中的 Python，再点「+」添加当前正在运行的程序；更新、重装或换过"
        "venv 后，开关可能仍显示为开，但未对应实际进程。",
        f"需授权的主程序路径：{sys.executable}",
    ]
    # 仅在实际以 .app 运行时展示包路径（命令行 python 时 mainBundle 可能指向系统工具链）
    if bp and str(bp).endswith(".app"):
        parts.append(f"应用包路径：{bp}")
    return "\n".join(parts)

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
    if not _ax_trusted_with_retry():
        print("[输入] get_selected_text: 无辅助功能权限", flush=True)
        return None

    old = _get_clipboard()
    old_count = NSPasteboard.generalPasteboard().changeCount()

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()

    if not _simulate_cmd_c():
        print("[输入] get_selected_text: simulate_cmd_c 失败", flush=True)
        if old is not None:
            _set_clipboard(old)
        return None

    # 轮询等待剪贴板 changeCount 变化（目标应用写入），最多 0.5 秒
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        time.sleep(0.05)
        if NSPasteboard.generalPasteboard().changeCount() != old_count:
            break

    selected = _get_clipboard()

    if old is not None:
        _set_clipboard(old)
    else:
        pb.clearContents()

    if selected and selected.strip():
        print(f"[输入] 检测到选中文字: {selected.strip()[:50]}", flush=True)
        return selected.strip()
    print("[输入] get_selected_text: 剪贴板无选中内容", flush=True)
    return None


def request_accessibility():
    """打开「辅助功能」设置页（兼容 System Settings / 旧版 System Preferences）。"""
    try:

        def _open_url(url: str) -> bool:
            try:
                return subprocess.call(["open", url], timeout=8) == 0
            except (OSError, subprocess.SubprocessError):
                return False

        if _open_url(
            "x-apple.systempreferences:com.apple.preference.security?"
            "Privacy_Accessibility"
        ):
            return

        ver = platform.mac_ver()[0]
        mac_major = 12
        if ver:
            try:
                mac_major = int(ver.split(".")[0])
            except ValueError:
                pass

        if mac_major >= 13:
            script = (
                'tell application "System Settings" to reveal anchor '
                '"Privacy_Accessibility" of pane id '
                '"com.apple.settings.PrivacySecurity.extension"\n'
                'tell application "System Settings" to activate'
            )
        else:
            script = (
                'tell application "System Preferences" to reveal anchor '
                '"Privacy_Accessibility" of pane id '
                '"com.apple.preference.security"\n'
                'tell application "System Preferences" to activate'
            )

        subprocess.Popen(["osascript", "-e", script])
    except Exception as e:
        print(f"[输入] 打开辅助功能设置异常: {e}", flush=True)


def paste_text(text: str) -> bool:
    """将文本粘贴到当前光标位置。

    返回 True 表示模拟粘贴成功，False 表示仅复制到剪贴板（需用户手动粘贴）。
    """
    if not text:
        return True

    trusted = _ax_trusted_with_retry()
    print(
        f"[输入] AXIsProcessTrusted={trusted} executable={sys.executable}",
        flush=True,
    )

    if not trusted:
        print(
            "[输入] 无辅助功能权限，仅复制到剪贴板，尝试弹出权限请求",
            flush=True,
        )
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
