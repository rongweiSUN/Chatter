"""AI 回答浮窗 — 选中文字提问后展示 LLM 回答。

使用 NSPanel + WKWebView 显示富文本内容，支持 Markdown 渲染。
浮窗出现在鼠标光标附近，点击外部或按 ESC 自动关闭。
DeskClaw 模式下底部带输入框可继续对话。
"""

from __future__ import annotations

import html as html_mod
import re
import threading

import objc
from AppKit import (
    NSAlert,
    NSApp,
    NSBezelStyleRounded,
    NSBox,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSScreen,
    NSPanel,
    NSTextField,
    NSTextAlignmentLeft,
    NSView,
    NSVisualEffectView,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskFullSizeContentView,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSEvent,
    NSWorkspace,
)
from Foundation import NSObject, NSThread, NSURL
from WebKit import WKWebView, WKWebViewConfiguration

_WIN_W = 480
_WIN_H = 420
_TITLEBAR_H = 44
_BOTTOM_BAR_H = 52

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
    background: transparent;
    color: #1d1d1f;
    font-size: 13.5px;
    line-height: 1.72;
    -webkit-font-smoothing: antialiased;
    display: flex;
    flex-direction: column;
}
.content {
    flex: 1;
    overflow-y: auto;
    padding: 22px 26px 26px;
}
.question-section {
    display: flex;
    align-items: flex-start;
    gap: 11px;
    padding: 13px 16px;
    background: rgba(0,0,0,0.035);
    border-radius: 14px;
    margin-bottom: 20px;
}
.q-badge {
    flex-shrink: 0;
    width: 22px; height: 22px;
    border-radius: 7px;
    background: linear-gradient(135deg, #007aff, #5856d6);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; color: #fff; font-weight: 700;
    margin-top: 1px;
}
.q-text {
    font-size: 13.5px;
    color: #1d1d1f;
    font-weight: 500;
    line-height: 1.55;
}
.answer {
    padding: 0 2px;
    color: #1d1d1f;
    font-size: 13.5px;
    line-height: 1.78;
}
.answer p { margin-bottom: 14px; }
.answer p:last-child { margin-bottom: 0; }
.answer ul, .answer ol { padding-left: 22px; margin-bottom: 14px; }
.answer li { margin-bottom: 6px; }
.answer li:last-child { margin-bottom: 0; }
.answer code {
    background: rgba(0,0,0,0.045);
    padding: 1.5px 6px;
    border-radius: 5px;
    font-family: "SF Mono", Menlo, monospace;
    font-size: 12px;
    word-break: break-word;
}
.answer pre {
    background: rgba(0,0,0,0.03);
    border: 1px solid rgba(0,0,0,0.05);
    border-radius: 10px;
    padding: 14px 16px;
    overflow-x: auto;
    margin-bottom: 14px;
}
.answer pre code {
    background: none;
    padding: 0;
    font-size: 11.5px;
    line-height: 1.6;
    word-break: normal;
}
.answer strong { font-weight: 600; }
.answer em { color: #6e6e73; }
.answer h1, .answer h2, .answer h3 {
    color: #1d1d1f;
    margin: 20px 0 8px;
    font-weight: 600;
    letter-spacing: -0.01em;
}
.answer h1:first-child, .answer h2:first-child, .answer h3:first-child {
    margin-top: 0;
}
.answer h1 { font-size: 17px; }
.answer h2 { font-size: 15.5px; }
.answer h3 { font-size: 14px; }
.answer blockquote {
    border-left: 3px solid rgba(0,122,255,0.35);
    padding: 6px 14px;
    color: #6e6e73;
    margin-bottom: 14px;
    background: rgba(0,122,255,0.03);
    border-radius: 0 8px 8px 0;
}
.answer table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-bottom: 14px;
    border: 1px solid rgba(0,0,0,0.08);
    border-radius: 8px;
    overflow: hidden;
    font-size: 13px;
}
.answer th, .answer td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid rgba(0,0,0,0.06);
}
.answer th {
    background: rgba(0,0,0,0.03);
    font-weight: 600;
    font-size: 12.5px;
    color: #6e6e73;
    letter-spacing: 0.02em;
}
.answer tr:last-child td { border-bottom: none; }
.answer tr:nth-child(even) td { background: rgba(0,0,0,0.015); }
.answer a {
    color: #007aff;
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.15s ease;
    cursor: pointer;
}
.answer a:hover {
    border-bottom-color: rgba(0,122,255,0.4);
}
.answer a[href^="http"]::after {
    content: "\u2197";
    display: inline-block;
    font-size: 9px;
    margin-left: 2px;
    opacity: 0.45;
    vertical-align: super;
    font-style: normal;
}
.user-msg {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
}
.user-msg .msg-bubble {
    max-width: 82%;
    padding: 10px 15px;
    background: #007aff;
    color: #fff;
    border-radius: 16px 16px 4px 16px;
    font-size: 13.5px;
    line-height: 1.55;
    word-break: break-word;
}
.assistant-msg {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid rgba(0,0,0,0.045);
}
.thinking-indicator {
    display: flex; align-items: center; gap: 7px;
    padding: 14px 2px; color: #8e8e93; font-size: 12.5px;
}
.thinking-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: #007aff; opacity: 0.35;
    animation: pulse 1.4s ease-in-out infinite;
}
.thinking-dot:nth-child(2) { animation-delay: 0.15s; }
.thinking-dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes pulse {
    0%, 100% { opacity: 0.25; transform: scale(0.75); }
    50% { opacity: 0.85; transform: scale(1.15); }
}
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.2); }
</style>
</head>
<body>
<div class="content" id="chatContent">
    <div class="question-section">
        <div class="q-badge">?</div>
        <div class="q-text">__QUESTION__</div>
    </div>
    <div class="answer">__ANSWER_HTML__</div>
</div>
<script>
document.addEventListener('click', function(e) {
    var link = e.target.closest('a');
    if (link && link.href && link.href.startsWith('http')) {
        e.preventDefault();
        window.webkit.messageHandlers.openLink.postMessage(link.href);
    }
});
function appendUserMsg(text) {
    var c = document.getElementById('chatContent');
    var d = document.createElement('div');
    d.className = 'user-msg';
    d.innerHTML = '<div class="msg-bubble"></div>';
    d.querySelector('.msg-bubble').textContent = text;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}
function showThinking() {
    var old = document.getElementById('thinkingEl');
    if (old) old.remove();
    var c = document.getElementById('chatContent');
    var d = document.createElement('div');
    d.className = 'thinking-indicator';
    d.id = 'thinkingEl';
    d.innerHTML = '<div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div><span>思考中\u2026</span>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}
function appendAssistantMsg(html) {
    var old = document.getElementById('thinkingEl');
    if (old) old.remove();
    var c = document.getElementById('chatContent');
    var d = document.createElement('div');
    d.className = 'assistant-msg answer';
    d.innerHTML = html;
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}
</script>
</body>
</html>
"""


def _auto_link_urls(text: str) -> str:
    """将已处理 HTML 中的裸 URL 转为可点击链接，跳过已在标签内的 URL。"""
    parts = re.split(r"(<a\s[^>]*>.*?</a>|<code>[^<]*</code>)", text)
    for i, part in enumerate(parts):
        if not part.startswith("<a ") and not part.startswith("<code>"):
            parts[i] = re.sub(
                r"(https?://[^\s<>\"')\]]+)",
                r'<a href="\1">\1</a>',
                part,
            )
    return "".join(parts)


def _md_to_html(text: str) -> str:
    """Minimal markdown to HTML (no external deps)."""
    lines = text.split("\n")
    html_parts: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    in_list = False
    list_type = ""
    table_lines: list[str] = []

    def _close_list():
        nonlocal in_list, list_type
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
            list_type = ""

    def _flush_table():
        if len(table_lines) < 2:
            for tl in table_lines:
                html_parts.append(f"<p>{_inline(tl)}</p>")
            table_lines.clear()
            return
        sep = table_lines[1].strip()
        if not re.match(r"^\|[\s\-:|]+\|$", sep):
            for tl in table_lines:
                html_parts.append(f"<p>{_inline(tl)}</p>")
            table_lines.clear()
            return
        headers = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
        out = "<table><thead><tr>"
        for cell in headers:
            out += f"<th>{_inline(cell)}</th>"
        out += "</tr></thead><tbody>"
        for row_line in table_lines[2:]:
            cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
            out += "<tr>"
            for cell in cells:
                out += f"<td>{_inline(cell)}</td>"
            out += "</tr>"
        out += "</tbody></table>"
        html_parts.append(out)
        table_lines.clear()

    def _inline(line: str) -> str:
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
        line = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            r'<a href="\2">\1</a>',
            line,
        )
        line = _auto_link_urls(line)
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
            if table_lines:
                _flush_table()
            in_code_block = True
            continue

        stripped = line.strip()
        if not stripped:
            _close_list()
            if table_lines:
                _flush_table()
            continue

        if re.match(r"^\|.+\|$", stripped):
            _close_list()
            table_lines.append(stripped)
            continue

        if table_lines:
            _flush_table()

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

    if table_lines:
        _flush_table()
    _close_list()
    return "\n".join(html_parts)


def _js_escape(s: str) -> str:
    """转义字符串以安全嵌入 JS 单引号字面量。"""
    return (
        s.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("</", "<\\/")
    )


class _LinkHandler(NSObject):
    """WKScriptMessageHandler -- 接收 JS 的链接点击事件并在浏览器中打开。"""

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        url_str = message.body()
        if url_str:
            url = NSURL.URLWithString_(url_str)
            if url:
                NSWorkspace.sharedWorkspace().openURL_(url)


class AnswerWindowController(NSObject):
    """AI 回答浮窗控制器。"""

    _panel = objc.ivar()
    _webview = objc.ivar()
    _input_field = objc.ivar()
    _send_button = objc.ivar()
    _deskclaw_link = objc.ivar()
    _bottom_bar = objc.ivar()
    _click_monitor = objc.ivar()
    _local_monitor = objc.ivar()
    _link_handler = objc.ivar()

    def init(self):
        self = objc.super(AnswerWindowController, self).init()
        if self is None:
            return None
        self._click_monitor = None
        self._local_monitor = None
        self._sending = False
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
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHasShadow_(True)
        self._panel.setMovableByWindowBackground_(True)
        self._panel.setMinSize_((340, 280))
        self._panel.setBecomesKeyOnlyIfNeeded_(False)
        self._panel.setHidesOnDeactivate_(False)

        content = self._panel.contentView()
        content.setWantsLayer_(True)

        effect_view = NSVisualEffectView.alloc().initWithFrame_(content.bounds())
        effect_view.setAutoresizingMask_(0x02 | 0x10)
        effect_view.setBlendingMode_(0)  # behindWindow
        effect_view.setMaterial_(6)  # popover
        effect_view.setState_(1)  # active
        content.addSubview_(effect_view)

        self._link_handler = _LinkHandler.alloc().init()
        wk_config = WKWebViewConfiguration.alloc().init()
        wk_config.preferences().setValue_forKey_(False, "javaScriptCanOpenWindowsAutomatically")
        wk_config.userContentController().addScriptMessageHandler_name_(
            self._link_handler, "openLink"
        )

        ch = _WIN_H - _TITLEBAR_H
        wv_frame = NSMakeRect(0, 0, _WIN_W, ch)
        self._webview = WKWebView.alloc().initWithFrame_configuration_(wv_frame, wk_config)
        self._webview.setAutoresizingMask_(0x02 | 0x10)
        self._webview.setValue_forKey_(False, "drawsBackground")
        self._webview.setAllowsMagnification_(False)
        content.addSubview_(self._webview)

        self._bottom_bar = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, _WIN_W, _BOTTOM_BAR_H)
        )
        self._bottom_bar.setAutoresizingMask_(0x02)
        self._bottom_bar.setHidden_(True)
        content.addSubview_(self._bottom_bar)

        sep = NSBox.alloc().initWithFrame_(
            NSMakeRect(0, _BOTTOM_BAR_H - 1, _WIN_W, 1)
        )
        sep.setBoxType_(2)  # NSBoxSeparator
        sep.setAutoresizingMask_(0x02)
        self._bottom_bar.addSubview_(sep)

        send_w = 48
        pad = 12
        field_y = 22
        self._input_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(pad, field_y, _WIN_W - pad * 2 - send_w - 8, 26)
        )
        self._input_field.setPlaceholderString_("继续对话…")
        self._input_field.setFont_(NSFont.systemFontOfSize_(13))
        self._input_field.setBezeled_(True)
        self._input_field.setEditable_(True)
        self._input_field.setTarget_(self)
        self._input_field.setAction_(
            objc.selector(self.onSendClicked_, signature=b"v@:@")
        )
        self._bottom_bar.addSubview_(self._input_field)

        self._send_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(_WIN_W - pad - send_w, field_y, send_w, 26)
        )
        self._send_button.setTitle_("发送")
        self._send_button.setBezelStyle_(NSBezelStyleRounded)
        self._send_button.setFont_(NSFont.systemFontOfSize_(12))
        self._send_button.setTarget_(self)
        self._send_button.setAction_(
            objc.selector(self.onSendClicked_, signature=b"v@:@")
        )
        self._bottom_bar.addSubview_(self._send_button)

        self._deskclaw_link = NSButton.alloc().initWithFrame_(
            NSMakeRect(pad, 3, _WIN_W - pad * 2, 16)
        )
        self._deskclaw_link.setTitle_("在 DeskClaw 中继续对话 ›")
        self._deskclaw_link.setBordered_(False)
        self._deskclaw_link.setFont_(NSFont.systemFontOfSize_(11))
        self._deskclaw_link.setContentTintColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.48, 1.0, 0.7)
        )
        self._deskclaw_link.setAlignment_(NSTextAlignmentLeft)
        self._deskclaw_link.setTarget_(self)
        self._deskclaw_link.setAction_(
            objc.selector(self.onDeskclawContinue_, signature=b"v@:@")
        )
        self._bottom_bar.addSubview_(self._deskclaw_link)

    def show_answer(
        self,
        question: str,
        answer_text: str,
        *,
        deskclaw_continue: bool = False,
    ):
        """显示回答。可从任意线程调用。"""
        payload = {
            "q": question,
            "a": answer_text,
            "dc": deskclaw_continue,
        }
        if not NSThread.isMainThread():
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._doShowAnswer_, signature=b"v@:@"),
                payload, False,
            )
            return
        self._doShowAnswer_(payload)

    def _layout_bottom_bar(self, show_bar: bool):
        content = self._panel.contentView()
        bounds = content.bounds()
        w = bounds.size.width
        h = bounds.size.height
        bar_h = _BOTTOM_BAR_H if show_bar else 0
        self._bottom_bar.setHidden_(not show_bar)
        self._webview.setFrame_(NSMakeRect(0, bar_h, w, h - bar_h - _TITLEBAR_H))
        if show_bar:
            self._bottom_bar.setFrame_(NSMakeRect(0, 0, w, _BOTTOM_BAR_H))
            pad = 12
            send_w = 48
            field_y = 22
            self._input_field.setFrame_(
                NSMakeRect(pad, field_y, w - pad * 2 - send_w - 8, 26)
            )
            self._send_button.setFrame_(
                NSMakeRect(w - pad - send_w, field_y, send_w, 26)
            )
            self._deskclaw_link.setFrame_(
                NSMakeRect(pad, 3, w - pad * 2, 16)
            )

    @objc.typedSelector(b"v@:@")
    def _doShowAnswer_(self, payload):
        question = payload["q"]
        answer_text = payload["a"]
        deskclaw_continue = bool(payload.get("dc"))

        self._sending = False
        self._input_field.setStringValue_("")
        self._input_field.setEnabled_(True)
        self._send_button.setEnabled_(True)

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
        self._layout_bottom_bar(deskclaw_continue)
        self._panel.makeKeyAndOrderFront_(None)
        self._install_monitors()

    @objc.typedSelector(b"v@:@")
    def onSendClicked_(self, sender):
        if self._sending:
            return
        text = self._input_field.stringValue().strip()
        if not text:
            return
        self._sending = True
        self._input_field.setStringValue_("")
        self._input_field.setEnabled_(False)
        self._send_button.setEnabled_(False)

        escaped = _js_escape(text)
        self._webview.evaluateJavaScript_completionHandler_(
            f"appendUserMsg('{escaped}')", None
        )
        self._webview.evaluateJavaScript_completionHandler_(
            "showThinking()", None
        )

        def _do_chat():
            from deskclaw_client import chat as deskclaw_chat, DeskClawUnavailable
            try:
                resp = deskclaw_chat(text)
                content = (resp.get("content") or "").strip()
                answer_html = _md_to_html(content) if content else "<p>任务已执行</p>"
            except DeskClawUnavailable:
                answer_html = '<p style="color:#ff3b30">无法连接 DeskClaw，请确认应用已启动</p>'
            except Exception as e:
                answer_html = f'<p style="color:#ff3b30">请求失败：{html_mod.escape(str(e))}</p>'

            escaped_html = _js_escape(answer_html)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(self._onChatResult_, signature=b"v@:@"),
                escaped_html, False,
            )

        threading.Thread(target=_do_chat, daemon=True).start()

    @objc.typedSelector(b"v@:@")
    def _onChatResult_(self, escaped_html):
        self._sending = False
        self._input_field.setEnabled_(True)
        self._send_button.setEnabled_(True)
        self._webview.evaluateJavaScript_completionHandler_(
            f"appendAssistantMsg('{escaped_html}')", None
        )
        self._panel.makeKeyAndOrderFront_(None)
        self._input_field.becomeFirstResponder()

    @objc.typedSelector(b"v@:@")
    def onDeskclawContinue_(self, sender):
        from deskclaw_client import open_deskclaw_app

        if open_deskclaw_app():
            self.dismiss()
            return
        alert = NSAlert.alloc().init()
        alert.setMessageText_("无法打开 DeskClaw")
        alert.setInformativeText_(
            "请确认 DeskClaw 已安装并能正常连接本机的 Gateway。"
            "可尝试从「应用程序」或 Launchpad 手动打开 DeskClaw 继续对话。"
        )
        alert.addButtonWithTitle_("好")
        alert.runModal()

    def _install_monitors(self):
        """监听 ESC 关闭浮窗，转发 Cmd+C/V/X/A 确保输入框支持复制粘贴。"""
        self._remove_monitors()

        cmd_actions = {
            "c": "copy:",
            "v": "paste:",
            "x": "cut:",
            "a": "selectAll:",
        }

        def local_handler(event):
            if event.type() == 10:
                if event.keyCode() == 53:
                    self.dismiss()
                    return None
                if event.modifierFlags() & (1 << 20):
                    key = (event.charactersIgnoringModifiers() or "").lower()
                    action = cmd_actions.get(key)
                    if action:
                        NSApp.sendAction_to_from_(action, None, self._panel)
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
