from __future__ import annotations

"""原生 Cocoa 设置窗口。

使用 PyObjC 构建 NSWindow + NSView 层级，与 rumps 共享 NSApplication 事件循环。
支持 App Key 和 App ID+Token 两种鉴权方式。
"""

import threading

import objc
from AppKit import (
    NSWindow,
    NSView,
    NSTextField,
    NSSecureTextField,
    NSPopUpButton,
    NSButton,
    NSBox,
    NSFont,
    NSColor,
    NSMenu,
    NSMenuItem,
    NSAlert,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSBackingStoreBuffered,
    NSTextAlignmentLeft,
    NSTextAlignmentRight,
    NSTextAlignmentCenter,
    NSBezelStyleRounded,
    NSControlStateValueOn,
    NSControlStateValueOff,
    NSSwitchButton,
    NSMakeRect,
    NSApp,
    NSWindowTitleHidden,
)
from Foundation import NSObject

from settings import Settings, get_settings, save_settings


def _ensure_edit_menu():
    """为 LSUIElement 应用添加标准 Edit 菜单，使文本框支持 Cmd+C/V/X/A。"""
    main_menu = NSApp.mainMenu()
    if main_menu is None:
        main_menu = NSMenu.alloc().init()
        NSApp.setMainMenu_(main_menu)

    for i in range(main_menu.numberOfItems()):
        if main_menu.itemAtIndex_(i).title() == "Edit":
            return

    edit_menu = NSMenu.alloc().initWithTitle_("Edit")
    edit_menu.addItemWithTitle_action_keyEquivalent_("Undo", "undo:", "z")
    edit_menu.addItemWithTitle_action_keyEquivalent_("Redo", "redo:", "Z")
    edit_menu.addItem_(NSMenuItem.separatorItem())
    edit_menu.addItemWithTitle_action_keyEquivalent_("Cut", "cut:", "x")
    edit_menu.addItemWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
    edit_menu.addItemWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
    edit_menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")

    edit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Edit", None, "")
    edit_item.setSubmenu_(edit_menu)
    main_menu.addItem_(edit_item)

# ── 布局常量 ──
WIN_W, WIN_H = 560, 500
PAD = 20
LABEL_W = 120
FIELD_W = 380
ROW_H = 28
ROW_GAP = 8
SECTION_GAP = 16

RESOURCE_IDS = [
    "volc.seedasr.sauc.duration",
    "volc.seedasr.sauc.concurrent",
    "volc.bigasr.sauc.duration",
    "volc.bigasr.sauc.concurrent",
]


def _make_label(text: str, frame, bold=False, size=13, align=NSTextAlignmentLeft) -> NSTextField:
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setAlignment_(align)
    if bold:
        label.setFont_(NSFont.boldSystemFontOfSize_(size))
    else:
        label.setFont_(NSFont.systemFontOfSize_(size))
    return label


def _make_text_field(frame, placeholder="", secure=False) -> NSTextField:
    cls = NSSecureTextField if secure else NSTextField
    tf = cls.alloc().initWithFrame_(frame)
    tf.setPlaceholderString_(placeholder)
    tf.setFont_(NSFont.systemFontOfSize_(13))
    return tf


def _make_popup(frame, items: list[str], selected: int = 0) -> NSPopUpButton:
    btn = NSPopUpButton.alloc().initWithFrame_pullsDown_(frame, False)
    for item in items:
        btn.addItemWithTitle_(item)
    if 0 <= selected < len(items):
        btn.selectItemAtIndex_(selected)
    return btn


def _make_section_title(text: str, y: int, parent_w: int) -> NSTextField:
    return _make_label(
        text,
        NSMakeRect(PAD, y, parent_w - 2 * PAD, 22),
        bold=True,
        size=14,
    )


def _make_separator(y: int, parent_w: int) -> NSBox:
    box = NSBox.alloc().initWithFrame_(NSMakeRect(PAD, y, parent_w - 2 * PAD, 1))
    box.setBoxType_(2)  # NSBoxSeparator
    return box


class SettingsWindowController(NSObject):

    window = objc.ivar()
    volcEnabledSwitch = objc.ivar()
    volcAuthMethodPopup = objc.ivar()
    volcAppKeyLabel = objc.ivar()
    volcAppKeyField = objc.ivar()
    volcAppIdLabel = objc.ivar()
    volcAppIdField = objc.ivar()
    volcTokenLabel = objc.ivar()
    volcTokenField = objc.ivar()
    volcResourceIdPopup = objc.ivar()
    volcStatusLabel = objc.ivar()
    saveBtn = objc.ivar()
    asrModelPopup = objc.ivar()

    _on_save_callback = objc.ivar()
    _is_validating = objc.ivar()

    def initWithCallback_(self, callback):
        self = objc.super(SettingsWindowController, self).init()
        if self is None:
            return None
        self._on_save_callback = callback
        self._build_window()
        return self

    def _build_window(self):
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, WIN_W, WIN_H), style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("随口说 - 设置")
        self.window.center()

        content = self.window.contentView()
        y = WIN_H - PAD

        # ═══ 默认模型 ═══
        y -= 22
        content.addSubview_(_make_section_title("默认模型", y, WIN_W))
        y -= ROW_GAP

        y -= ROW_H
        content.addSubview_(_make_label(
            "语音识别模型:", NSMakeRect(PAD, y, LABEL_W, ROW_H)
        ))
        self.asrModelPopup = _make_popup(
            NSMakeRect(PAD + LABEL_W, y, FIELD_W, ROW_H),
            ["豆包流式语音识别模型 2.0"],
            0,
        )
        content.addSubview_(self.asrModelPopup)

        y -= SECTION_GAP
        y -= 1
        content.addSubview_(_make_separator(y, WIN_W))
        y -= SECTION_GAP

        # ═══ 语音识别服务商 ═══
        y -= 22
        content.addSubview_(_make_section_title("语音识别服务商", y, WIN_W))
        y -= ROW_GAP + 4

        card_x = PAD
        card_w = WIN_W - 2 * PAD
        card_h = 228
        y -= card_h

        card = NSBox.alloc().initWithFrame_(NSMakeRect(card_x, y, card_w, card_h))
        card.setTitle_("")
        card.setTitlePosition_(0)  # NSNoTitle
        card.setBorderType_(3)  # NSBezelBorder
        card.setCornerRadius_(8)
        card_content = card.contentView()
        cw = card_w - 10
        cy = card_h - 36

        card_content.addSubview_(_make_label(
            "🔵 火山引擎", NSMakeRect(8, cy, 200, 24), bold=True, size=13
        ))

        self.volcEnabledSwitch = NSButton.alloc().initWithFrame_(
            NSMakeRect(cw - 60, cy, 50, 24)
        )
        self.volcEnabledSwitch.setButtonType_(NSSwitchButton)
        self.volcEnabledSwitch.setTitle_("")
        card_content.addSubview_(self.volcEnabledSwitch)

        cy -= ROW_H + 4
        card_content.addSubview_(_make_label("鉴权方式:", NSMakeRect(8, cy, 90, ROW_H)))
        self.volcAuthMethodPopup = _make_popup(
            NSMakeRect(100, cy, cw - 110, ROW_H),
            ["App Key（新版控制台）", "App ID + Token（旧版控制台）"],
            0,
        )
        self.volcAuthMethodPopup.setTarget_(self)
        self.volcAuthMethodPopup.setAction_(
            objc.selector(self.authMethodChanged_, signature=b"v@:@")
        )
        card_content.addSubview_(self.volcAuthMethodPopup)

        cy -= ROW_H + 4
        self.volcAppKeyLabel = _make_label("App Key:", NSMakeRect(8, cy, 90, ROW_H))
        card_content.addSubview_(self.volcAppKeyLabel)
        self.volcAppKeyField = _make_text_field(
            NSMakeRect(100, cy, cw - 110, ROW_H), "输入 App Key"
        )
        card_content.addSubview_(self.volcAppKeyField)

        self.volcAppIdLabel = _make_label("App ID:", NSMakeRect(8, cy, 90, ROW_H))
        self.volcAppIdLabel.setHidden_(True)
        card_content.addSubview_(self.volcAppIdLabel)
        self.volcAppIdField = _make_text_field(
            NSMakeRect(100, cy, cw - 110, ROW_H), "输入 App ID"
        )
        self.volcAppIdField.setHidden_(True)
        card_content.addSubview_(self.volcAppIdField)

        cy -= ROW_H + 4
        self.volcTokenLabel = _make_label("Token:", NSMakeRect(8, cy, 90, ROW_H))
        self.volcTokenLabel.setHidden_(True)
        card_content.addSubview_(self.volcTokenLabel)
        self.volcTokenField = _make_text_field(
            NSMakeRect(100, cy, cw - 110, ROW_H), "输入 Access Token", secure=True
        )
        self.volcTokenField.setHidden_(True)
        card_content.addSubview_(self.volcTokenField)

        cy -= ROW_H + 4
        card_content.addSubview_(_make_label("Resource ID:", NSMakeRect(8, cy, 90, ROW_H)))
        self.volcResourceIdPopup = _make_popup(
            NSMakeRect(100, cy, cw - 110, ROW_H),
            RESOURCE_IDS,
            0,
        )
        card_content.addSubview_(self.volcResourceIdPopup)

        cy -= ROW_H + 4
        self.volcStatusLabel = _make_label(
            "", NSMakeRect(8, cy, cw - 16, ROW_H), size=12
        )
        self.volcStatusLabel.setTextColor_(NSColor.secondaryLabelColor())
        card_content.addSubview_(self.volcStatusLabel)

        content.addSubview_(card)

        y -= SECTION_GAP
        y -= 1
        content.addSubview_(_make_separator(y, WIN_W))
        y -= SECTION_GAP

        # ═══ 快捷键（信息展示） ═══
        y -= 22
        content.addSubview_(_make_section_title("快捷键", y, WIN_W))
        y -= ROW_GAP

        y -= ROW_H
        hint = _make_label(
            "短按右 Command 键 → 开始/停止语音输入",
            NSMakeRect(PAD, y, WIN_W - 2 * PAD, ROW_H),
            size=13,
        )
        hint.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(hint)

        # ═══ 底部按钮 ═══
        y -= ROW_H + SECTION_GAP + 8

        cancel_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(WIN_W - PAD - 80 - 10 - 80, y, 80, 32)
        )
        cancel_btn.setTitle_("取消")
        cancel_btn.setBezelStyle_(NSBezelStyleRounded)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_(objc.selector(self.cancelClicked_, signature=b"v@:@"))
        content.addSubview_(cancel_btn)

        self.saveBtn = NSButton.alloc().initWithFrame_(
            NSMakeRect(WIN_W - PAD - 80, y, 80, 32)
        )
        self.saveBtn.setTitle_("保存")
        self.saveBtn.setBezelStyle_(NSBezelStyleRounded)
        self.saveBtn.setKeyEquivalent_("\r")
        self.saveBtn.setTarget_(self)
        self.saveBtn.setAction_(objc.selector(self.saveClicked_, signature=b"v@:@"))
        content.addSubview_(self.saveBtn)

    # ── 鉴权方式切换 ──

    @objc.typedSelector(b"v@:@")
    def authMethodChanged_(self, sender):
        is_app_key = self.volcAuthMethodPopup.indexOfSelectedItem() == 0
        self.volcAppKeyLabel.setHidden_(not is_app_key)
        self.volcAppKeyField.setHidden_(not is_app_key)
        self.volcAppIdLabel.setHidden_(is_app_key)
        self.volcAppIdField.setHidden_(is_app_key)
        self.volcTokenLabel.setHidden_(is_app_key)
        self.volcTokenField.setHidden_(is_app_key)

    def _apply_auth_method_visibility(self, method: str):
        is_app_key = (method != "app_id_token")
        self.volcAuthMethodPopup.selectItemAtIndex_(0 if is_app_key else 1)
        self.volcAppKeyLabel.setHidden_(not is_app_key)
        self.volcAppKeyField.setHidden_(not is_app_key)
        self.volcAppIdLabel.setHidden_(is_app_key)
        self.volcAppIdField.setHidden_(is_app_key)
        self.volcTokenLabel.setHidden_(is_app_key)
        self.volcTokenField.setHidden_(is_app_key)

    # ── 数据加载/收集 ──

    def show(self):
        _ensure_edit_menu()
        self._load_settings()
        self.window.setLevel_(3)  # NSFloatingWindowLevel
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def _load_settings(self):
        s = get_settings()

        self.volcEnabledSwitch.setState_(
            NSControlStateValueOn if s.volcengine.enabled else NSControlStateValueOff
        )

        self._apply_auth_method_visibility(s.volcengine.auth_method)

        self.volcAppKeyField.setStringValue_(s.volcengine.app_key or "")
        self.volcAppIdField.setStringValue_(s.volcengine.appid or "")
        self.volcTokenField.setStringValue_(s.volcengine.token or "")

        rid = s.volcengine.resource_id or "volc.seedasr.sauc.duration"
        idx = RESOURCE_IDS.index(rid) if rid in RESOURCE_IDS else 0
        self.volcResourceIdPopup.selectItemAtIndex_(idx)

    def _gather_settings(self) -> Settings:
        s = get_settings()

        s.asr_model = self.asrModelPopup.titleOfSelectedItem()

        s.volcengine.enabled = (
            self.volcEnabledSwitch.state() == NSControlStateValueOn
        )

        is_app_key = self.volcAuthMethodPopup.indexOfSelectedItem() == 0
        s.volcengine.auth_method = "app_key" if is_app_key else "app_id_token"
        s.volcengine.app_key = str(self.volcAppKeyField.stringValue())
        s.volcengine.appid = str(self.volcAppIdField.stringValue())
        s.volcengine.token = str(self.volcTokenField.stringValue())
        s.volcengine.resource_id = str(self.volcResourceIdPopup.titleOfSelectedItem())

        return s

    # ── 保存与验证 ──

    @objc.typedSelector(b"v@:@")
    def cancelClicked_(self, sender):
        self.window.orderOut_(None)

    @objc.typedSelector(b"v@:@")
    def saveClicked_(self, sender):
        s = self._gather_settings()

        if not s.volcengine.enabled:
            save_settings(s)
            self.window.orderOut_(None)
            if self._on_save_callback:
                self._on_save_callback()
            return

        if s.volcengine.auth_method == "app_id_token":
            appid = s.volcengine.appid.strip()
            token = s.volcengine.token.strip()
            if not appid or not token:
                self._show_status("请填写 App ID 和 Token", error=True)
                return
        else:
            app_key = s.volcengine.app_key.strip()
            if not app_key:
                self._show_status("请填写 App Key", error=True)
                return

        self._show_status("正在验证连接...", error=False)
        self.saveBtn.setEnabled_(False)
        self._is_validating = True

        threading.Thread(
            target=self._validate_and_save,
            args=(s,),
            daemon=True,
        ).start()

    def _validate_and_save(self, settings):
        from asr_client import test_connection_sync
        v = settings.volcengine
        ok, msg = test_connection_sync(
            auth_method=v.auth_method,
            app_key=v.app_key.strip(),
            appid=v.appid.strip(),
            token=v.token.strip(),
            cluster=v.cluster,
            resource_id=v.resource_id,
        )
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(self.handleValidationResult_, signature=b"v@:@"),
            {"ok": ok, "msg": msg, "settings": settings},
            False,
        )

    @objc.typedSelector(b"v@:@")
    def handleValidationResult_(self, result):
        self._is_validating = False
        self.saveBtn.setEnabled_(True)

        ok = result["ok"]
        msg = result["msg"]
        settings = result["settings"]

        if ok:
            self._show_status("✅ " + msg, error=False)
            save_settings(settings)
            self.window.orderOut_(None)
            if self._on_save_callback:
                self._on_save_callback()
        else:
            self._show_status("❌ " + msg, error=True)
            alert = NSAlert.alloc().init()
            alert.setMessageText_("API 连接验证失败")
            alert.setInformativeText_(msg)
            alert.addButtonWithTitle_("确定")
            alert.beginSheetModalForWindow_completionHandler_(self.window, None)

    def _show_status(self, text, error=False):
        self.volcStatusLabel.setStringValue_(text)
        if error:
            self.volcStatusLabel.setTextColor_(NSColor.systemRedColor())
        else:
            self.volcStatusLabel.setTextColor_(NSColor.secondaryLabelColor())


_controller: SettingsWindowController | None = None


def open_settings(on_save=None):
    global _controller
    if _controller is None:
        _controller = SettingsWindowController.alloc().initWithCallback_(on_save)
    _controller.show()
