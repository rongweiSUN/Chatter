"""AI 回答浮窗 — 选中文字提问后展示 LLM 回答。

使用 NSPanel + WKWebView 显示富文本内容，支持 Markdown 渲染。
浮窗出现在鼠标光标附近，点击外部或按 ESC 自动关闭。
"""

from __future__ import annotations

import html as html_mod
import re

import objc
from AppKit import (
    NSColor,
    NSMakeRect,
    NSScreen,
    NSPanel,
    NSView,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskFullSizeContentView,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSEvent,
)
from Foundation import NSObject, NSThread
from WebKit import WKWebView, WKWebViewConfiguration

_WIN_W = 440
_WIN_H = 340
_TITLEBAR_H = 44

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
    height: 100%;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    background: transparent;
    color: #1d1d1f;
    font-size: 13.5px;
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
    display: flex;
    flex-direction: column;
}
.content {
    flex: 1;
    overflow-y: auto;
    padding: 20px 22px;
}
.question-section {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 16px;
    background: #fff;
    border-radius: 12px;
    margin-bottom: 18px;
    border: 1px solid rgba(0,0,0,0.06);
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.q-badge {
    flex-shrink: 0;
    width: 22px; height: 22px;
    border-radius: 7px;
    background: linear-gradient(135deg, #0071e3, #af52de);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; color: #fff; font-weight: 700;
    margin-top: 1px;
}
.q-text {
    font-size: 14px;
    color: #1d1d1f;
    font-weight: 500;
    line-height: 1.5;
}
.answer {
    padding: 0;
    color: #1d1d1f;
    font-size: 14px;
    line-height: 1.75;
}
.answer p { margin-bottom: 12px; }
.answer p:last-child { margin-bottom: 0; }
.answer ul, .answer ol { padding-left: 22px; margin-bottom: 12px; }
.answer li { margin-bottom: 5px; }
.answer code {
    background: rgba(0,0,0,0.05);
    padding: 2px 6px;
    border-radius: 5px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 12.5px;
}
.answer pre {
    background: #f5f5f7;
    border: 1px solid rgba(0,0,0,0.06);
    border-radius: 10px;
    padding: 14px 16px;
    overflow-x: auto;
    margin-bottom: 12px;
}
.answer pre code {
    background: none;
    padding: 0;
    font-size: 12px;
    line-height: 1.55;
}
.answer strong { color: #1d1d1f; font-weight: 600; }
.answer em { color: #6e6e73; font-style: italic; }
.answer h1, .answer h2, .answer h3 {
    color: #1d1d1f;
    margin: 16px 0 8px;
    font-weight: 600;
}
.answer h1 { font-size: 17px; }
.answer h2 { font-size: 15.5px; }
.answer h3 { font-size: 14.5px; }
.answer blockquote {
    border-left: 3px solid #0071e3;
    padding: 4px 14px;
    color: #6e6e73;
    margin-bottom: 12px;
    background: rgba(0,113,227,0.03);
    border-radius: 0 8px 8px 0;
}
.answer a { color: #0071e3; text-decoration: none; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.18); }
</style>
</head>
<body>
<div class="content">
    <div class="question-section">
        <div class="q-badge">?</div>
        <div class="q-text">__QUESTION__</div>
    </div>
    <div class="answer">__ANSWER_HTML__</div>
</div>
</body>
</html>
"""


def _md_to_html(text: str) -> str:
    """Minimal markdown to HTML (no external deps)."""
    lines = text.split("\n")
    html_parts = []
    in_code_block = False
    code_lines: list[str] = []
    in_list = False
    list_type = ""

    def _close_list():
        nonlocal in_list, list_type
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
            list_type = ""

    def _inline(line: str) -> str:
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
        line = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r'<a href="\2" target="_blank">\1</a>',
            line,
        )
        return line

    for line in lines:
        if in_code_block:
            if line.strip().startswith("```"):
                html_parts.append(
                    "<pre><code>"
                    + "\n".join(code_lines).replace("&", "&amp;").replace("<", "&lt;")
                    + "</code></pre>"
                )
                code_lines = []
                in_code_block = False
            else:
                code_lines.append(line)
            continue

        if line.strip().startswith("```"):
            _close_list()
            in_code_block = True
            continue

        stripped = line.strip()
        if not stripped:
            _close_list()
            continue

        m_heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m_heading:
            _close_list()
            level = len(m_heading.group(1))
            html_parts.append(f"<h{level}>{_inline(m_heading.group(2))}</h{level}>")
            continue

        m_blockquote = re.match(r"^>\s*(.*)$", stripped)
        if m_blockquote:
            _close_list()
            html_parts.append(f"<blockquote>{_inline(m_blockquote.group(1))}</blockquote>")
            continue

        m_ul = re.match(r"^[-*]\s+(.+)$", stripped)
        if m_ul:
            if not in_list or list_type != "ul":
                _close_list()
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            html_parts.append(f"<li>{_inline(m_ul.group(1))}</li>")
            continue

        m_ol = re.match(r"^\d+\.\s+(.+)$", stripped)
        if m_ol:
            if not in_list or list_type != "ol":
                _close_list()
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            html_parts.append(f"<li>{_inline(m_ol.group(1))}</li>")
            continue

        _close_list()
        html_parts.append(f"<p>{_inline(stripped)}</p>")

    if in_code_block:
        html_parts.append(
            "<pre><code>"
            + "\n".join(code_lines).replace("&", "&amp;").replace("<", "&lt;")
            + "</code></pre>"
        )

    _close_list()
    return "\n".join(html_parts)


class AnswerWindowController(NSObject):
    """AI 回答浮窗控制器。"""

    _panel = objc.ivar()
    _webview = objc.ivar()
    _click_monitor = objc.ivar()
    _local_monitor = objc.ivar()

    def init(self):
        self = objc.super(AnswerWindowController, self).init()
        if self is None:
            return None
        self._click_monitor = None
        self._local_monitor = None
        self._build_panel()
        return self

    def _build_panel(self):
        screen = NSScreen.mainScreen()
        sf = screen.frame()
        x = (sf.size.width - _WIN_W) / 2
        y = (sf.size.height - _WIN_H) / 2

        mask = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskFullSizeContentView
        )
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, _WIN_W, _WIN_H),
            mask,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setTitle_("AI 回答")
        self._panel.setTitlebarAppearsTransparent_(True)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.98)
        )
        self._panel.setHasShadow_(True)
        self._panel.setMovableByWindowBackground_(True)
        self._panel.setMinSize_((320, 220))
        self._panel.setBecomesKeyOnlyIfNeeded_(False)
        self._panel.setHidesOnDeactivate_(False)

        content = self._panel.contentView()
        content.setWantsLayer_(True)

        config = WKWebViewConfiguration.alloc().init()
        config.preferences().setValue_forKey_(False, "javaScriptCanOpenWindowsAutomatically")

        wv_frame = NSMakeRect(0, 0, _WIN_W, _WIN_H - _TITLEBAR_H)
        self._webview = WKWebView.alloc().initWithFrame_configuration_(wv_frame, config)
        self._webview.setAutoresizingMask_(0x02 | 0x10)
        self._webview.setValue_forKey_(False, "drawsBackground")
        self._webview.setAllowsMagnification_(False)
        content.addSubview_(self._webview)

    def show_answer(self, question: str, answer_text: str):
        """显示回答。可从任意线程调用。"""
        if not NSThread.isMainThread():
            payload = {"q": question, "a": answer_text}
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doShowAnswer_, signature=b"v@:@"),
                payload, False,
            )
            return
        self._doShowAnswer_({"q": question, "a": answer_text})

    @objc.typedSelector(b"v@:@")
    def _doShowAnswer_(self, payload):
        question = payload["q"]
        answer_text = payload["a"]

        answer_html = _md_to_html(answer_text)
        q_escaped = html_mod.escape(question)
        full_html = _HTML_TEMPLATE.replace(
            "__QUESTION__", q_escaped
        ).replace(
            "__ANSWER_HTML__", answer_html
        )
        self._webview.loadHTMLString_baseURL_(full_html, None)

        mouse_loc = NSEvent.mouseLocation()
        screen = NSScreen.mainScreen()
        vf = screen.visibleFrame()

        x = mouse_loc.x + 20
        y = mouse_loc.y - _WIN_H - 10

        if x + _WIN_W > vf.origin.x + vf.size.width:
            x = mouse_loc.x - _WIN_W - 20
        if y < vf.origin.y:
            y = mouse_loc.y + 30
        if x < vf.origin.x:
            x = vf.origin.x + 10

        self._panel.setFrame_display_(NSMakeRect(x, y, _WIN_W, _WIN_H), True)
        self._panel.makeKeyAndOrderFront_(None)
        self._install_monitors()

    def _install_monitors(self):
        """监听窗口外部点击和 ESC 按键以自动关闭。"""
        self._remove_monitors()

        def global_handler(event):
            if self._panel.isVisible():
                click_window = event.window()
                if click_window is None or click_window != self._panel:
                    self.dismiss()

        self._click_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            (1 << 1) | (1 << 3),
            global_handler,
        )

        def local_handler(event):
            if event.type() == 10 and event.keyCode() == 53:
                self.dismiss()
                return None
            return event

        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            (1 << 10),
            local_handler,
        )

    def _remove_monitors(self):
        if self._click_monitor is not None:
            NSEvent.removeMonitor_(self._click_monitor)
            self._click_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None

    def dismiss(self):
        """关闭浮窗。"""
        if not NSThread.isMainThread():
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doDismiss_, signature=b"v@:@"),
                None, False,
            )
            return
        self._doDismiss_(None)

    @objc.typedSelector(b"v@:@")
    def _doDismiss_(self, _):
        self._remove_monitors()
        self._panel.orderOut_(None)


_instance: AnswerWindowController | None = None


def get_answer_window() -> AnswerWindowController:
    global _instance
    if _instance is None:
        _instance = AnswerWindowController.alloc().init()
    return _instance
