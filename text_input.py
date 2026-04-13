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
import threading
import time

from AppKit import NSPasteboard, NSPasteboardTypeString
from Foundation import NSDate, NSRunLoop
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

try:
    from ApplicationServices import (
        AXUIElementCreateSystemWide,
        AXUIElementCopyAttributeValue,
    )
    _HAS_AX_ELEMENT = True
except ImportError:
    _HAS_AX_ELEMENT = False

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


_AX_TEXT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"}
_FIELD_CONTEXT_MAX = 500


def get_frontmost_app_name() -> str | None:
    """返回当前前台应用的名称（如「备忘录」「微信」「Safari」）。"""
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return app.localizedName() if app else None
    except Exception:
        return None


def get_field_context() -> str | None:
    """通过 AX API 非破坏性地读取当前焦点输入框的已有文本。

    不动剪贴板、不改选区、不模拟按键。
    需要辅助功能权限；非文本控件或读取失败时返回 None。
    """
    if not _HAS_AX_ELEMENT or not _ax_trusted():
        print("[输入] get_field_context: AX 不可用", flush=True)
        return None
    try:
        system = AXUIElementCreateSystemWide()
        err, focused = AXUIElementCopyAttributeValue(
            system, "AXFocusedUIElement", None
        )
        if err != 0 or focused is None:
            print(f"[输入] get_field_context: 无焦点元素 (err={err})", flush=True)
            return None
        err, role = AXUIElementCopyAttributeValue(focused, "AXRole", None)
        if err != 0 or role not in _AX_TEXT_ROLES:
            print(f"[输入] get_field_context: 非文本控件 (role={role})", flush=True)
            return None
        err, value = AXUIElementCopyAttributeValue(focused, "AXValue", None)
        if err != 0 or not value:
            print("[输入] get_field_context: 输入框无内容", flush=True)
            return None
        text = str(value).strip()
        if not text:
            print("[输入] get_field_context: 输入框内容为空", flush=True)
            return None
        if len(text) > _FIELD_CONTEXT_MAX:
            text = text[-_FIELD_CONTEXT_MAX:]
        print(f"[输入] get_field_context: 读取到{len(text)}字", flush=True)
        return text
    except Exception as e:
        print(f"[输入] get_field_context 异常: {e}", flush=True)
        return None


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
    """获取当前活跃应用中的选中文字。

    优先使用 AXSelectedText（Accessibility API），非破坏性且准确。
    对不支持该属性的应用，回退到模拟 Cmd+C + 读取剪贴板。
    如果没有选中内容或无辅助功能权限，返回 None。
    """
    if not _ax_trusted_with_retry():
        print("[输入] get_selected_text: 无辅助功能权限", flush=True)
        return None

    # ── 优先尝试 AXSelectedText（不动剪贴板） ──
    if _HAS_AX_ELEMENT:
        try:
            system = AXUIElementCreateSystemWide()
            err, focused = AXUIElementCopyAttributeValue(
                system, "AXFocusedUIElement", None
            )
            if err == 0 and focused is not None:
                err_sel, ax_sel = AXUIElementCopyAttributeValue(
                    focused, "AXSelectedText", None
                )
                if err_sel == 0:
                    text = str(ax_sel).strip() if ax_sel else ""
                    if text:
                        print(f"[输入] AXSelectedText 检测到选中文字: {text[:50]}", flush=True)
                        return text
                    print("[输入] AXSelectedText: 无选中内容", flush=True)
                    return None
        except Exception as e:
            print(f"[输入] AXSelectedText 异常，回退到 Cmd+C: {e}", flush=True)

    # ── 回退：模拟 Cmd+C + 剪贴板 ──
    old = _get_clipboard()

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    count_after_clear = pb.changeCount()

    if not _simulate_cmd_c():
        print("[输入] get_selected_text: simulate_cmd_c 失败", flush=True)
        if old is not None:
            _set_clipboard(old)
        return None

    deadline = time.monotonic() + 0.5
    changed = False
    while time.monotonic() < deadline:
        time.sleep(0.05)
        if NSPasteboard.generalPasteboard().changeCount() != count_after_clear:
            changed = True
            break

    if not changed:
        if old is not None:
            _set_clipboard(old)
        print("[输入] get_selected_text: 剪贴板未变化，无选中内容", flush=True)
        return None

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
        # Pump the run loop instead of blocking with time.sleep so that
        # the Cmd+V event can be delivered when the focused window belongs
        # to our own process (the main thread must be unblocked for macOS
        # to dispatch the keyboard event to our WKWebView / NSTextField).
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.3)
        )
        if old_clipboard is not None:
            def _restore():
                _set_clipboard(old_clipboard)
            threading.Timer(0.5, _restore).start()

    return ok
