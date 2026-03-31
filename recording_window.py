from __future__ import annotations

"""录音浮窗 — 录音时在屏幕上方显示状态、波形和实时文字。

使用 PyObjC 创建一个无边框、半透明的 NSWindow。
通过 update_level / update_text 从录音线程和 ASR 线程推送数据，
使用 performSelectorOnMainThread 保证 UI 操作在主线程执行。
"""

import math
import objc
from AppKit import (
    NSBezelStyleRounded,
    NSButton,
    NSWindow,
    NSView,
    NSTextField,
    NSFont,
    NSColor,
    NSMakeRect,
    NSApp,
    NSScreen,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSTextAlignmentCenter,
    NSFloatingWindowLevel,
    NSBezierPath,
)
from Foundation import NSObject, NSTimer, NSThread


_WIN_W = 360
_WIN_H = 100
_BAR_COUNT = 20
_BAR_GAP = 3
_BAR_MAX_H = 30
_LEVEL_NOISE_GATE = 0.025
_LEVEL_ATTACK = 0.42
_LEVEL_RELEASE = 0.16
_BAR_INTERP = 0.34
_THINKING_PHASE_STEP = 0.009


class _WaveformView(NSView):
    """显示音量条的自定义视图。"""

    _levels = objc.ivar()

    def initWithFrame_(self, frame):
        self = objc.super(_WaveformView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._levels = [0.0] * _BAR_COUNT
        return self

    def setLevels_(self, levels):
        self._levels = list(levels)
        self.setNeedsDisplay_(True)

    def isFlipped(self):
        return False

    def drawRect_(self, rect):
        bounds = self.bounds()
        w = bounds.size.width
        h = bounds.size.height

        bar_total_w = _BAR_COUNT * (_BAR_GAP + 4) - _BAR_GAP
        x_start = (w - bar_total_w) / 2
        center = (_BAR_COUNT - 1) / 2.0

        for i, level in enumerate(self._levels):
            # 中间柱略高，边缘略低，让视觉重心更稳定。
            dist = abs(i - center) / max(center, 1.0)
            center_weight = 1.0 - 0.38 * (dist ** 1.6)
            center_weight = max(0.62, center_weight)
            weighted_level = max(0.0, min(1.0, level * center_weight))
            bar_h = max(3, 2 + weighted_level * _BAR_MAX_H)
            x = x_start + i * (_BAR_GAP + 4)
            y = (h - bar_h) / 2

            alpha = 0.45 + 0.5 * weighted_level
            accent = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.35, 0.78, 0.98, alpha
            )
            accent.setFill()
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(x, y, 4, bar_h), 2, 2
            )
            path.fill()


class _GradientBorderView(NSView):
    """思考中状态的彩色渐变边框视图，沿边框旋转流动。"""

    _phase = objc.ivar()

    def initWithFrame_(self, frame):
        self = objc.super(_GradientBorderView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._phase = 0.0
        return self

    def setPhase_(self, phase):
        self._phase = float(phase)
        self.setNeedsDisplay_(True)

    def isFlipped(self):
        return False

    def drawRect_(self, rect):
        bounds = self.bounds()
        w = bounds.size.width
        h = bounds.size.height
        radius = 16.0
        border_w = 2.15

        colors = [
            (0.22, 0.92, 1.0),   # cyan
            (0.62, 0.34, 1.0),   # purple
            (1.0, 0.32, 0.78),   # pink
            (1.0, 0.58, 0.15),   # amber
            (0.26, 0.98, 0.58),  # green
            (0.22, 0.92, 1.0),   # cyan (loop)
        ]
        phase = self._phase
        perimeter = self._rounded_rect_perimeter(w, h, radius)

        # 底层柔光：略亮、随相位轻微变色，整体更有“流光”感。
        weak_base = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(border_w / 2, border_w / 2, w - border_w, h - border_w),
            max(0.0, radius - border_w / 2),
            max(0.0, radius - border_w / 2),
        )
        weak_base.setLineWidth_(1.35)
        tb = 0.5 + 0.5 * math.sin(phase * 2.0 * math.pi)
        br = 0.42 + 0.22 * tb
        bg = 0.55 + 0.18 * (1.0 - tb)
        bb = 0.92 + 0.06 * tb
        NSColor.colorWithCalibratedRed_green_blue_alpha_(br, bg, bb, 0.26).setStroke()
        weak_base.stroke()

        seg_count = 52
        highlight_width = 0.28

        # 主高光 + 两道较弱拖尾，形成彩色光带。
        for alpha_mul, phase_off, width_mul in (
            (1.0, 0.0, 1.0),
            (0.4, -0.24, 0.88),
            (0.22, -0.5, 0.78),
        ):
            eff_phase = (phase + phase_off) % 1.0
            for i in range(seg_count):
                pos = i / seg_count
                offset = abs(pos - eff_phase)
                offset = min(offset, 1.0 - offset)
                glow = max(0.0, 1.0 - offset / highlight_width)
                if glow <= 0.01:
                    continue

                t = (pos * 0.75 + eff_phase) % 1.0
                ci = t * (len(colors) - 1)
                idx = int(ci)
                frac = ci - idx
                idx = min(idx, len(colors) - 2)
                r = colors[idx][0] + (colors[idx + 1][0] - colors[idx][0]) * frac
                g = colors[idx][1] + (colors[idx + 1][1] - colors[idx][1]) * frac
                b = colors[idx][2] + (colors[idx + 1][2] - colors[idx][2]) * frac

                alpha = (0.34 + 0.58 * (glow ** 1.45)) * alpha_mul
                NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha).setStroke()

                seg_len = perimeter / seg_count * (0.92 + 0.62 * glow)
                dist_start = pos * perimeter
                dist_end = dist_start + seg_len

                path = NSBezierPath.bezierPath()
                lw = (border_w + 1.25 * glow) * width_mul
                path.setLineWidth_(lw)

                p_start = self._point_on_rounded_rect(w, h, radius, dist_start)

                path.moveToPoint_(p_start)

                steps = 6
                for s in range(1, steps + 1):
                    d = dist_start + (dist_end - dist_start) * s / steps
                    p = self._point_on_rounded_rect(w, h, radius, d)
                    path.lineToPoint_(p)

                path.stroke()

    def _rounded_rect_perimeter(self, w, h, r):
        r = min(r, w / 2, h / 2)
        return 2 * (w + h - 4 * r) + 2 * math.pi * r

    def _point_on_rounded_rect(self, w, h, r, dist):
        """沿圆角矩形周长返回对应点坐标。"""
        r = min(r, w / 2, h / 2)
        segs = [
            w - 2 * r,             # top edge
            math.pi * r / 2,       # top-right corner
            h - 2 * r,             # right edge
            math.pi * r / 2,       # bottom-right corner
            w - 2 * r,             # bottom edge
            math.pi * r / 2,       # bottom-left corner
            h - 2 * r,             # left edge
            math.pi * r / 2,       # top-left corner
        ]
        perimeter = sum(segs)
        dist = dist % perimeter

        cumul = 0.0
        for idx, seg_len in enumerate(segs):
            if seg_len <= 0:
                continue
            if cumul + seg_len >= dist:
                local = dist - cumul
                frac = local / seg_len if seg_len > 0 else 0
                return self._eval_segment(idx, frac, w, h, r)
            cumul += seg_len
        return (r, h)

    def _eval_segment(self, idx, frac, w, h, r):
        """按段编号和分数返回 (x, y) 坐标。"""
        if idx == 0:  # top edge: left-to-right
            return (r + frac * (w - 2 * r), h)
        elif idx == 1:  # top-right corner
            angle = math.pi / 2 * (1 - frac)
            return (w - r + r * math.cos(angle), h - r + r * math.sin(angle))
        elif idx == 2:  # right edge: top-to-bottom
            return (w, h - r - frac * (h - 2 * r))
        elif idx == 3:  # bottom-right corner，圆心 (w-r, r)，从 (w,r) 到 (w-r,0)
            theta = -frac * math.pi / 2
            return (w - r + r * math.cos(theta), r + r * math.sin(theta))
        elif idx == 4:  # bottom edge: right-to-left
            return (w - r - frac * (w - 2 * r), 0)
        elif idx == 5:  # bottom-left corner，圆心 (r, r)，从 (r,0) 到 (0,r)
            theta = -math.pi / 2 * (1.0 + frac)
            return (r + r * math.cos(theta), r + r * math.sin(theta))
        elif idx == 6:  # left edge: bottom-to-top
            return (0, r + frac * (h - 2 * r))
        else:  # top-left corner
            angle = math.pi / 2 * frac
            return (r - r * math.cos(angle), h - r + r * math.sin(angle))


class RecordingWindowController(NSObject):
    """录音浮窗控制器。"""

    window = objc.ivar()
    _waveform_view = objc.ivar()
    _text_label = objc.ivar()
    _status_label = objc.ivar()
    _level_history = objc.ivar()
    _timer = objc.ivar()
    _current_level = objc.ivar()
    _smoothed_level = objc.ivar()
    _gradient_border = objc.ivar()
    _thinking_phase = objc.ivar()
    _is_thinking = objc.ivar()
    _result_timer = objc.ivar()
    _esc_cancel_button = objc.ivar()

    def init(self):
        self = objc.super(RecordingWindowController, self).init()
        if self is None:
            return None
        self._level_history = [0.0] * _BAR_COUNT
        self._current_level = 0.0
        self._smoothed_level = 0.0
        self._thinking_phase = 0.0
        self._is_thinking = False
        self._result_timer = None
        self._cancel_handler = None
        self._build_window()
        return self

    def set_cancel_handler(self, handler):
        """录音中指左上角「ESC」或键盘 Esc 时调用，放弃识别。"""
        self._cancel_handler = handler

    def _build_window(self):
        screen = NSScreen.mainScreen()
        screen_frame = screen.frame()
        x = (screen_frame.size.width - _WIN_W) / 2
        y = screen_frame.size.height - _WIN_H - 80

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, _WIN_W, _WIN_H),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.85)
        )
        self.window.setHasShadow_(True)
        self.window.setMovableByWindowBackground_(True)

        content = self.window.contentView()
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(16)
        content.layer().setMasksToBounds_(True)

        self._status_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(8, _WIN_H - 28, _WIN_W - 16, 20)
        )
        self._status_label.setStringValue_("正在聆听...")
        self._status_label.setBezeled_(False)
        self._status_label.setDrawsBackground_(False)
        self._status_label.setEditable_(False)
        self._status_label.setSelectable_(False)
        self._status_label.setAlignment_(NSTextAlignmentCenter)
        self._status_label.setFont_(NSFont.systemFontOfSize_(12))
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)
        )
        content.addSubview_(self._status_label)

        self._waveform_view = _WaveformView.alloc().initWithFrame_(
            NSMakeRect(0, 28, _WIN_W, 40)
        )
        content.addSubview_(self._waveform_view)

        self._text_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(10, 4, _WIN_W - 20, 24)
        )
        self._text_label.setStringValue_("")
        self._text_label.setBezeled_(False)
        self._text_label.setDrawsBackground_(False)
        self._text_label.setEditable_(False)
        self._text_label.setSelectable_(False)
        self._text_label.setAlignment_(NSTextAlignmentCenter)
        self._text_label.setFont_(NSFont.systemFontOfSize_(13))
        self._text_label.setTextColor_(NSColor.whiteColor())
        self._text_label.setLineBreakMode_(5)  # NSLineBreakByTruncatingMiddle
        content.addSubview_(self._text_label)

        self._gradient_border = _GradientBorderView.alloc().initWithFrame_(
            NSMakeRect(0, 0, _WIN_W, _WIN_H)
        )
        self._gradient_border.setHidden_(True)
        content.addSubview_(self._gradient_border)

        self._esc_cancel_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(8, _WIN_H - 28, 36, 20)
        )
        self._esc_cancel_button.setTitle_("esc")
        self._esc_cancel_button.setToolTip_("取消录音（与键盘左上角 Esc 相同）")
        self._esc_cancel_button.setBordered_(False)
        self._esc_cancel_button.setFont_(NSFont.systemFontOfSize_(10))
        self._esc_cancel_button.setContentTintColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.55, 0.55, 0.55, 0.6)
        )
        self._esc_cancel_button.setTarget_(self)
        self._esc_cancel_button.setAction_(
            objc.selector(self.onEscCancelClicked_, signature=b"v@:@")
        )
        self._esc_cancel_button.setHidden_(True)
        content.addSubview_(self._esc_cancel_button)

    @objc.typedSelector(b"v@:@")
    def onEscCancelClicked_(self, sender):
        if self._cancel_handler:
            self._cancel_handler()

    def show(self):
        self._cancel_result_timer()
        self._text_label.setStringValue_("")
        self._status_label.setStringValue_("正在聆听...")
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)
        )
        self._level_history = [0.0] * _BAR_COUNT
        self._current_level = 0.0
        self._smoothed_level = 0.0
        self._is_thinking = False
        self._waveform_view.setHidden_(False)
        self._gradient_border.setHidden_(True)
        self._esc_cancel_button.setHidden_(False)

        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None

        self.window.orderFrontRegardless()

        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.05, self,
            objc.selector(self._tick_, signature=b"v@:@"),
            None, True,
        )

    def hide(self):
        """隐藏窗口。可从任意线程安全调用。"""
        if not NSThread.isMainThread():
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doHide_, signature=b"v@:@"),
                None, False,
            )
            return
        self._doHide_(None)

    @objc.typedSelector(b"v@:@")
    def _doHide_(self, _):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None
        self.window.orderOut_(None)

    def show_processing(self):
        """切换到"识别中"状态。可从任意线程安全调用。"""
        if not NSThread.isMainThread():
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doShowProcessing_, signature=b"v@:@"),
                None, False,
            )
            return
        self._doShowProcessing_(None)

    @objc.typedSelector(b"v@:@")
    def _doShowProcessing_(self, _):
        self._cancel_result_timer()
        self._is_thinking = False
        self._status_label.setStringValue_("识别中...")
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)
        )
        self._level_history = [0.0] * _BAR_COUNT
        self._smoothed_level = 0.0
        self._waveform_view.setHidden_(False)
        self._gradient_border.setHidden_(True)
        self._esc_cancel_button.setHidden_(True)
        self._waveform_view.setLevels_(self._level_history)

    def update_level(self, level: float):
        """从录音线程调用，更新当前音量（线程安全）。"""
        self._current_level = level

    def update_text(self, text: str):
        """从 ASR 线程调用，更新实时识别文字。"""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self.handlePartialText_, signature=b"v@:@"),
            text,
            False,
        )

    @objc.typedSelector(b"v@:@")
    def handlePartialText_(self, text):
        if text:
            self._text_label.setStringValue_(text)

    @objc.typedSelector(b"v@:@")
    def _tick_(self, timer):
        if self._is_thinking:
            self._thinking_phase = (self._thinking_phase + _THINKING_PHASE_STEP) % 1.0
            self._gradient_border.setPhase_(self._thinking_phase)
        else:
            target = max(0.0, min(1.0, self._current_level))
            if target < _LEVEL_NOISE_GATE:
                target = 0.0

            # attack/release 平滑，避免音量突然跳变。
            coeff = _LEVEL_ATTACK if target >= self._smoothed_level else _LEVEL_RELEASE
            self._smoothed_level += (target - self._smoothed_level) * coeff

            next_levels = self._level_history[1:] + [self._smoothed_level]
            blended_levels = [
                old + (new - old) * _BAR_INTERP
                for old, new in zip(self._level_history, next_levels)
            ]
            self._level_history = blended_levels
            self._waveform_view.setLevels_(blended_levels)

    def show_thinking(self):
        """切换到"思考中"状态，彩色渐变边框旋转。可从任意线程安全调用。"""
        if not NSThread.isMainThread():
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doShowThinking_, signature=b"v@:@"),
                None, False,
            )
            return
        self._doShowThinking_(None)

    @objc.typedSelector(b"v@:@")
    def _doShowThinking_(self, _):
        self._cancel_result_timer()
        self._is_thinking = True
        self._thinking_phase = 0.0
        self._status_label.setStringValue_("思考中...")
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)
        )
        self._waveform_view.setHidden_(True)
        self._gradient_border.setHidden_(False)
        self._esc_cancel_button.setHidden_(True)

    def show_result(self, title: str, message: str, duration: float = 2.5):
        """显示结果消息，停留 duration 秒后自动隐藏。可从任意线程调用。"""
        payload = {"title": title, "message": message, "duration": duration}
        if not NSThread.isMainThread():
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doShowResult_, signature=b"v@:@"),
                payload, False,
            )
            return
        self._doShowResult_(payload)

    @objc.typedSelector(b"v@:@")
    def _doShowResult_(self, payload):
        title = payload["title"]
        message = payload["message"]
        duration = payload["duration"]

        self._cancel_result_timer()

        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None

        self._is_thinking = False
        self._waveform_view.setHidden_(True)
        self._gradient_border.setHidden_(True)
        self._esc_cancel_button.setHidden_(True)

        self._status_label.setStringValue_(title)
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.35, 0.78, 0.98, 1.0)
        )
        self._text_label.setStringValue_(message)
        self.window.orderFrontRegardless()

        self._result_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            duration, self,
            objc.selector(self._resultTimerFired_, signature=b"v@:@"),
            None, False,
        )

    def _cancel_result_timer(self):
        if self._result_timer is not None:
            self._result_timer.invalidate()
            self._result_timer = None

    @objc.typedSelector(b"v@:@")
    def _resultTimerFired_(self, timer):
        self._result_timer = None
        self._status_label.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.7, 0.7, 0.7, 1.0)
        )
        self.window.orderOut_(None)


_instance: RecordingWindowController | None = None


def get_recording_window() -> RecordingWindowController:
    global _instance
    if _instance is None:
        _instance = RecordingWindowController.alloc().init()
    return _instance
