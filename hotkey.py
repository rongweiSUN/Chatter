from __future__ import annotations

"""全局监听修饰键。

支持可配置的 keyCode 和一次性按键录制。
同时使用 global + local monitor 确保事件不被系统听写等拦截。
"""

from typing import Callable

from Cocoa import NSEvent, NSEventMaskFlagsChanged

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
    """监听指定修饰键，支持按下/松开回调。

    同时使用 global + local monitor：
    - global monitor 捕获焦点在其他应用时的事件
    - local monitor 捕获焦点在本应用（或被系统面板拦截后回落）时的事件
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

    def _handle_local(self, event):
        self._handle_event(event)
        return event

    def start(self):
        if self._global_monitor is not None:
            return
        print(f"[HotkeyMonitor] start monitoring keycode={self.keycode}", flush=True)
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged, self._handle_event
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged, self._handle_local
        )

    def stop(self):
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None


class HotkeyRecorder:
    """一次性捕获下一个修饰键按下事件。

    同时使用 global + local monitor，确保无论应用窗口是否聚焦都能捕获。
    """

    def __init__(self, on_recorded: Callable[[int, str], None] | None = None):
        self.on_recorded = on_recorded
        self._global_monitor = None
        self._local_monitor = None

    def start(self):
        if self._global_monitor is not None or self._local_monitor is not None:
            self.stop()
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged, self._handle
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged, self._handle_local
        )

    def stop(self):
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None

    def _handle_local(self, event):
        self._handle(event)
        return event

    def _handle(self, event):
        kc = event.keyCode()
        if kc not in _MODIFIER_KEYCODES:
            return

        pressed = _is_pressed(kc, event.modifierFlags())
        if pressed is None:
            return

        if pressed:
            self.stop()
            name = KEY_NAMES.get(kc, f"Key({kc})")
            if self.on_recorded:
                self.on_recorded(kc, name)
