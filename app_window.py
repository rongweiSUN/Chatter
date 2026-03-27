"""主应用窗口 — WKWebView 渲染 HTML 界面，Python ↔ JS 桥接。

JS → Python:  window.webkit.messageHandlers.bridge.postMessage(JSON)
Python → JS:  evaluateJavaScript_completionHandler_
"""

from __future__ import annotations

import json
import os

import objc
from AppKit import (
    NSWindow,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSBackingStoreBuffered,
    NSMakeRect,
    NSApp,
    NSMenu,
    NSMenuItem,
)
from Foundation import NSObject, NSURL, NSBundle, NSSelectorFromString
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController

_WIN_W, _WIN_H = 820, 560


def _web_dir() -> str:
    bundle = NSBundle.mainBundle()
    if bundle:
        p = os.path.join(bundle.resourcePath(), "web")
        if os.path.isdir(p):
            return p
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "web")
    if os.path.isdir(p):
        return p
    return ""


def _ensure_edit_menu():
    """Add a standard Edit menu so Cmd+C/V/X/A work in WKWebView inputs."""
    mainMenu = NSApp.mainMenu()
    if mainMenu is None:
        mainMenu = NSMenu.alloc().init()
        NSApp.setMainMenu_(mainMenu)

    for i in range(mainMenu.numberOfItems()):
        if mainMenu.itemAtIndex_(i).title() == "Edit":
            return

    editMenu = NSMenu.alloc().initWithTitle_("Edit")
    for title, action, key in [
        ("Undo", "undo:", "z"),
        ("Redo", "redo:", "Z"),
        ("---", None, ""),
        ("Cut", "cut:", "x"),
        ("Copy", "copy:", "c"),
        ("Paste", "paste:", "v"),
        ("Select All", "selectAll:", "a"),
    ]:
        if title == "---":
            editMenu.addItem_(NSMenuItem.separatorItem())
        else:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, NSSelectorFromString(action), key
            )
            editMenu.addItem_(item)

    editMenuItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Edit", None, "")
    editMenuItem.setSubmenu_(editMenu)
    mainMenu.addItem_(editMenuItem)


class AppWindowController(NSObject):

    window = objc.ivar()
    _webview = objc.ivar()
    _on_action = objc.ivar()
    _page_loaded = objc.ivar()

    def initWithActionCallback_(self, callback):
        self = objc.super(AppWindowController, self).init()
        if self is None:
            return None
        self._on_action = callback
        self._page_loaded = False
        self._build()
        return self

    def _build(self):
        config = WKWebViewConfiguration.alloc().init()
        uc = config.userContentController()
        uc.addScriptMessageHandler_name_(self, "bridge")

        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, _WIN_W, _WIN_H),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("随口说")
        self.window.center()
        self.window.setMinSize_((640, 480))

        content = self.window.contentView()

        self._webview = WKWebView.alloc().initWithFrame_configuration_(
            content.bounds(), config
        )
        self._webview.setAutoresizingMask_(0x12)
        content.addSubview_(self._webview)

        nav_delegate = _NavDelegate.alloc().initWithController_(self)
        self._webview.setNavigationDelegate_(nav_delegate)
        self._nav_delegate = nav_delegate

        _ensure_edit_menu()

        web_path = _web_dir()
        if web_path:
            index = os.path.join(web_path, "index.html")
            url = NSURL.fileURLWithPath_(index)
            access_url = NSURL.fileURLWithPath_(web_path)
            self._webview.loadFileURL_allowingReadAccessToURL_(url, access_url)

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        try:
            body = json.loads(message.body())
            method = body.get("method", "")
            args = body.get("args", {})
            if self._on_action:
                self._on_action(method, args)
        except Exception as e:
            print(f"[Bridge] {e}")

    def show(self):
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def hide(self):
        self.window.orderOut_(None)

    @property
    def is_visible(self) -> bool:
        return self.window.isVisible()

    def call_js(self, func: str, *args):
        parts = [json.dumps(a, ensure_ascii=False) for a in args]
        script = f"{func}({', '.join(parts)})"
        self._webview.evaluateJavaScript_completionHandler_(script, None)

    def call_js_safe(self, func: str, *args):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self.handleJSPayload_, signature=b"v@:@"),
            json.dumps({"f": func, "a": list(args)}, ensure_ascii=False),
            False,
        )

    @objc.typedSelector(b"v@:@")
    def handleJSPayload_(self, payload):
        data = json.loads(payload)
        self.call_js(data["f"], *data["a"])

    def _on_page_loaded(self):
        self._page_loaded = True
        if self._on_action:
            self._on_action("_page_loaded", {})


class _NavDelegate(NSObject):

    _ctrl = objc.ivar()

    def initWithController_(self, ctrl):
        self = objc.super(_NavDelegate, self).init()
        if self is None:
            return None
        self._ctrl = ctrl
        return self

    def webView_didFinishNavigation_(self, webView, navigation):
        if self._ctrl:
            self._ctrl._on_page_loaded()
