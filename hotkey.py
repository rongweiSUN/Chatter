from __future__ import annotations

"""全局监听修饰键。

支持可配置的 keyCode 和一次性按键录制。
同时使用 global + local monitor 确保事件不被系统听写等拦截。
"""

from typing import Callable

import objc
from Cocoa import (
    NSEvent,
    NSEventMaskFlagsChanged,
    NSEventMaskKeyDown,
    NSEventMaskKeyUp,
    NSObject,
)

_CMD_FLAG = 1 << 20
_OPTION_FLAG = 1 << 19
_CTRL_FLAG = 1 << 18
_FN_FLAG = 1 << 23

KEY_NAMES = {
    54: "右 Command",
    55: "左 Command",
    61: "右 Option",
    58: "左 Option",
    60: "右 Control",
    59: "左 Control",
    63: "Fn",
}

_MODIFIER_KEYCODES = set(KEY_NAMES.keys())

_EXCLUDED_KEYCODES = {
    53,   # ESC
    36,   # Return
    48,   # Tab
    49,   # Space
    51,   # Delete/Backspace
    117,  # Forward Delete
    123,  # Left Arrow
    124,  # Right Arrow
    125,  # Down Arrow
    126,  # Up Arrow
}

_NSEventTypeKeyDown = 10
_NSEventTypeKeyUp = 11
_NSEventTypeFlagsChanged = 12


def _is_pressed(keycode: int, flags: int) -> bool | None:
    if keycode in (54, 55):
        return bool(flags & _CMD_FLAG)
    if keycode in (58, 61):
        return bool(flags & _OPTION_FLAG)
    if keycode in (59, 60):
        return bool(flags & _CTRL_FLAG)
    if keycode == 63:
        return bool(flags & _FN_FLAG)
    return None


class HotkeyMonitor:
    """监听指定按键（修饰键或普通键），支持按下/松开回调。

    同时使用 global + local monitor：
    - global monitor 捕获焦点在其他应用时的事件
    - local monitor 捕获焦点在本应用（或被系统面板拦截后回落）时的事件
    普通键在 local monitor 中会被吞掉（返回 None），防止产生字符输入。
    """

    def __init__(
        self,
        keycode: int = 54,
        on_key_down: Callable[[], None] | None = None,
        on_key_up: Callable[[], None] | None = None,
    ):
        self.keycode = keycode
        self.on_key_down = on_key_down
        self.on_key_up = on_key_up
        self._key_down = False
        self._global_monitor = None
        self._local_monitor = None

    def set_keycode(self, keycode: int):
        self.keycode = keycode
        self._key_down = False

    def _handle_event(self, event):
        kc = event.keyCode()
        if kc != self.keycode:
            return

        if self.keycode in _MODIFIER_KEYCODES:
            pressed = _is_pressed(self.keycode, event.modifierFlags())
            if pressed is None:
                return
            if pressed and not self._key_down:
                self._key_down = True
                print(f"[HotkeyMonitor] key_down kc={kc}", flush=True)
                if self.on_key_down:
                    self.on_key_down()
            elif not pressed and self._key_down:
                self._key_down = False
                print(f"[HotkeyMonitor] key_up kc={kc}", flush=True)
                if self.on_key_up:
                    self.on_key_up()
        else:
            et = event.type()
            if et == _NSEventTypeKeyDown:
                if event.isARepeat():
                    return
                if not self._key_down:
                    self._key_down = True
                    print(f"[HotkeyMonitor] key_down kc={kc}", flush=True)
                    if self.on_key_down:
                        self.on_key_down()
            elif et == _NSEventTypeKeyUp:
                if self._key_down:
                    self._key_down = False
                    print(f"[HotkeyMonitor] key_up kc={kc}", flush=True)
                    if self.on_key_up:
                        self.on_key_up()

    def _handle_local(self, event):
        self._handle_event(event)
        if event.keyCode() == self.keycode and self.keycode not in _MODIFIER_KEYCODES:
            return None
        return event

    def start(self):
        if self._global_monitor is not None:
            return
        is_modifier = self.keycode in _MODIFIER_KEYCODES
        mask = NSEventMaskFlagsChanged if is_modifier else (NSEventMaskKeyDown | NSEventMaskKeyUp)
        print(f"[HotkeyMonitor] start monitoring keycode={self.keycode} modifier={is_modifier}", flush=True)
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, self._handle_event
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            mask, self._handle_local
        )
        if self._global_monitor is None:
            print(
                "[HotkeyMonitor] ⚠️ 全局热键监听注册失败，"
                "可能未授予「输入监控」权限，其它应用前台时热键将无效",
                flush=True,
            )

    def stop(self):
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None


class _DeferredCall(NSObject):
    """将回调延迟到下一个 run loop 迭代执行，避免在事件监听回调内部移除监听器导致死锁。"""

    _callback = objc.ivar()

    def initWithCallback_(self, cb):
        self = objc.super(_DeferredCall, self).init()
        self._callback = cb
        return self

    @objc.typedSelector(b"v@:@")
    def invoke_(self, _sender):
        if self._callback:
            self._callback()

_deferred_prevent_gc: list = []


class HotkeyRecorder:
    """一次性捕获下一个按键事件（修饰键或普通键）。

    同时使用 global + local monitor，确保无论应用窗口是否聚焦都能捕获。
    """

    def __init__(self, on_recorded: Callable[[int, str], None] | None = None):
        self.on_recorded = on_recorded
        self._global_monitor = None
        self._local_monitor = None
        self._done = False

    def start(self):
        self._done = False
        if self._global_monitor is not None or self._local_monitor is not None:
            self.stop()
        mask = NSEventMaskFlagsChanged | NSEventMaskKeyDown
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, self._handle
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            mask, self._handle_local
        )

    def stop(self):
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None

    def _handle_local(self, event):
        recorded = self._handle(event)
        return None if recorded else event

    def _handle(self, event) -> bool:
        if self._done:
            return False

        kc = event.keyCode()
        et = event.type()

        if et == _NSEventTypeFlagsChanged:
            if kc not in _MODIFIER_KEYCODES:
                return False
            pressed = _is_pressed(kc, event.modifierFlags())
            if not pressed:
                return False
            name = KEY_NAMES.get(kc, f"Key({kc})")
        elif et == _NSEventTypeKeyDown:
            if kc in _EXCLUDED_KEYCODES or kc in _MODIFIER_KEYCODES:
                return False
            if event.isARepeat():
                return False
            chars = event.charactersIgnoringModifiers()
            name = chars.upper() if chars and len(chars) == 1 and chars.isalpha() else (chars or f"Key({kc})")
        else:
            return False

        self._done = True

        def _finish():
            _deferred_prevent_gc.remove(helper)
            self.stop()
            if self.on_recorded:
                self.on_recorded(kc, name)

        helper = _DeferredCall.alloc().initWithCallback_(_finish)
        _deferred_prevent_gc.append(helper)
        helper.performSelectorOnMainThread_withObject_waitUntilDone_(
            "invoke:", None, False,
        )
        return True


_ESC_KEYCODE = 53


class EscapeRecordingMonitor:
    """录音期间监听 ESC，用于取消当前录音（需输入监控权限）。"""

    def __init__(self, on_escape: Callable[[], None] | None = None):
        self.on_escape = on_escape
        self._global_monitor = None
        self._local_monitor = None

    def _maybe_fire(self, event):
        if event.keyCode() != _ESC_KEYCODE:
            return
        if event.isARepeat():
            return
        if self.on_escape:
            self.on_escape()

    def _handle_global(self, event):
        self._maybe_fire(event)

    def _handle_local(self, event):
        self._maybe_fire(event)
        return event

    def start(self):
        if self._global_monitor is not None or self._local_monitor is not None:
            return
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, self._handle_global
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, self._handle_local
        )
        if self._global_monitor is None:
            print(
                "[EscapeMonitor] ⚠️ 全局 ESC 监听注册失败，"
                "可能未授予「输入监控」权限",
                flush=True,
            )

    def stop(self):
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None
