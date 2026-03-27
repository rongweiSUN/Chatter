"""随口说 — macOS 菜单栏语音输入。

右 Command 键（可配置）短按普通输入，长按召唤语音助手。
"""

from __future__ import annotations

import faulthandler
import json
import os
import sys
import threading
import time
from datetime import datetime

faulthandler.enable(file=sys.stderr, all_threads=True)

os.environ["PYTHONUNBUFFERED"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
elif not getattr(sys.stdout, "line_buffering", True):
    sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)

import objc
import rumps
from AppKit import NSImage, NSApp
from Foundation import NSObject, NSNotificationCenter

import config
from recorder import AudioRecorder
from asr_client import StreamingSession
from text_input import paste_text, get_selected_text
from hotkey import HotkeyMonitor, HotkeyRecorder, KEY_NAMES
from recording_window import get_recording_window
from app_window import AppWindowController
from settings import Settings, get_settings, save_settings, reload_settings
from skill_engine import process_text as _apply_skills, process_with_instruction, ProcessResult
from confirm_dialog import confirm_high_risk
from voice_agent import handle_voice_command

_HISTORY_DIR = os.path.join(
    os.path.expanduser("~"), "Library", "Application Support", "VoiceInput"
)
_HISTORY_PATH = os.path.join(_HISTORY_DIR, "history.json")
_MAX_HISTORY = 50


def _load_history() -> list:
    if not os.path.exists(_HISTORY_PATH):
        return []
    try:
        with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(history: list):
    os.makedirs(_HISTORY_DIR, exist_ok=True)
    with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history[-_MAX_HISTORY:], f, ensure_ascii=False, indent=2)


def _play_success_sound():
    try:
        from AppKit import NSSound
        sound = NSSound.alloc().initWithContentsOfFile_byReference_(
            "/System/Library/Sounds/Tink.aiff", True
        )
        if sound:
            sound.play()
    except Exception:
        pass


def _friendly_asr_error(raw: str) -> str:
    low = raw.lower()
    if "timeout" in low or "超时" in low:
        return "网络连接超时，请检查网络后重试"
    if "refused" in low or "unreachable" in low:
        return "无法连接语音识别服务，请检查网络"
    if "401" in raw or "auth" in low or "key" in low:
        return "API 认证失败，请在「模型」页面检查凭证配置"
    if "403" in raw:
        return "API 无访问权限，请检查凭证是否正确"
    if "429" in raw or "rate" in low:
        return "请求过于频繁，请稍后重试"
    return f"语音识别出错，请稍后重试（{raw[:60]}）"


def _friendly_llm_error(e: Exception) -> str:
    raw = str(e)
    low = raw.lower()
    if "timeout" in low or "超时" in low:
        return "LLM 响应超时，请检查网络或更换模型重试"
    if "401" in raw or "auth" in low:
        return "LLM 认证失败，请在「模型」页面检查 API Key"
    if "404" in raw:
        return "LLM API 地址或模型名称不正确，请在「模型」页面检查配置"
    if "429" in raw or "rate" in low:
        return "LLM 请求频率超限，请稍后重试"
    if "connection" in low or "refused" in low:
        return "无法连接 LLM 服务，请检查网络或服务地址"
    return f"LLM 处理出错，请稍后重试（{raw[:60]}）"


def _sf_icon(name: str, fallback: str = "随口说") -> NSImage | str:
    try:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is not None:
            img.setTemplate_(True)
            return img
    except Exception:
        pass
    return fallback


class VoiceInputApp(rumps.App):
    ICON_IDLE = None
    ICON_RECORDING = None

    def __init__(self):
        super().__init__(
            name="随口说",
            title="随口说",
            icon=None,
            quit_button=None,
        )

        self.ICON_IDLE = _sf_icon("mic.fill")
        self.ICON_RECORDING = _sf_icon("mic.circle.fill")

        self._status_item = rumps.MenuItem("状态: 就绪", callback=None)
        self._history_menu = rumps.MenuItem("识别历史")

        self.menu = [
            self._status_item,
            None,
            rumps.MenuItem("打开主窗口", callback=self._open_main_window),
            self._history_menu,
            None,
            rumps.MenuItem("退出", callback=self._quit),
        ]

        self._recorder = AudioRecorder()
        self._asr_session: StreamingSession | None = None
        self._busy = False
        self._rec_window = get_recording_window()
        self._history: list = _load_history()

        s = get_settings()
        self._hotkey_monitor = HotkeyMonitor(
            keycode=s.hotkey_keycode,
            on_key_down=self._on_hotkey_down,
            on_key_up=self._on_hotkey_up,
        )
        self._hotkey_recorder: HotkeyRecorder | None = None

        self._selected_text: str | None = None
        self._record_mode: str | None = None
        self._hotkey_is_down = False
        self._long_press_triggered = False
        self._hold_timer: threading.Timer | None = None
        self._long_press_sec = 0.4
        self._app_window: AppWindowController | None = None
        self._dispatcher = _MainThreadDispatcher.alloc().initWithCallback_(
            self._mainThreadCleanup
        )
        self._assistant_dispatcher = _MainThreadDispatcher.alloc().initWithCallback_(
            self._on_assistant_dispatch
        )

    def _set_dock_icon(self):
        for base in [
            os.path.dirname(os.path.abspath(__file__)),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"),
        ]:
            icon_path = os.path.join(base, "logo.png")
            if os.path.exists(icon_path):
                img = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if img:
                    NSApp.setApplicationIconImage_(img)
                    return

    def _set_icon(self, icon_img):
        if isinstance(icon_img, NSImage):
            try:
                self._app.nsstatusitem.button().setImage_(icon_img)
            except Exception:
                pass

    def _set_status(self, text: str):
        self._status_item.title = f"状态: {text}"

    # ── 录音控制（短按普通输入 / 长按语音助手） ──

    def _on_hotkey_down(self):
        if self._busy:
            return
        self._hotkey_is_down = True
        self._long_press_triggered = False
        self._cancel_hold_timer()
        self._hold_timer = threading.Timer(
            self._long_press_sec, self._on_long_press_detected
        )
        self._hold_timer.daemon = True
        self._hold_timer.start()
        print("[热键] down", flush=True)

    def _on_hotkey_up(self):
        was_down = self._hotkey_is_down
        triggered = self._long_press_triggered
        self._hotkey_is_down = False
        self._cancel_hold_timer()
        print(f"[热键] up  triggered={triggered} recording={self._recorder.is_recording} busy={self._busy}", flush=True)

        if self._recorder.is_recording:
            self._stop_and_recognize()
            return

        if was_down and not triggered and not self._busy:
            self._start_recording(mode="normal")

    def _cancel_hold_timer(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _on_long_press_detected(self):
        """子线程定时器触发：标记长按，调度主线程启动助手录音。"""
        if self._hotkey_is_down and not self._busy:
            self._long_press_triggered = True
            print("[热键] 长按检测到，调度助手")
            self._assistant_dispatcher.call_on_main({"action": "start_assistant"})

    def _on_assistant_dispatch(self, info):
        """在主线程处理助手相关调度。"""
        action = info.get("action") if info else None
        if action == "start_assistant":
            if not self._hotkey_is_down:
                print("[热键] 助手调度到达时按键已松开，跳过")
                return
            if not self._busy and not self._recorder.is_recording:
                print("[热键] 主线程启动助手录音")
                self._start_recording(mode="assistant")
                self._start_assistant_timeout()
        elif action == "timeout_stop":
            if self._recorder.is_recording:
                print("[热键] 主线程执行超时停止")
                self._stop_and_recognize()

    _ASSISTANT_TIMEOUT = 30.0
    _ASSISTANT_WARN_BEFORE = 5.0

    def _start_assistant_timeout(self):
        """助手模式超时保护：如果 30 秒内没有松开，自动结束录音。最后 5 秒给出预警。"""
        self._cancel_assistant_timeout()

        warn_delay = self._ASSISTANT_TIMEOUT - self._ASSISTANT_WARN_BEFORE
        self._assistant_warn_timer = threading.Timer(warn_delay, self._on_assistant_warn)
        self._assistant_warn_timer.daemon = True
        self._assistant_warn_timer.start()

        self._assistant_timeout = threading.Timer(self._ASSISTANT_TIMEOUT, self._on_assistant_timeout)
        self._assistant_timeout.daemon = True
        self._assistant_timeout.start()

    def _cancel_assistant_timeout(self):
        for attr in ("_assistant_timeout", "_assistant_warn_timer"):
            t = getattr(self, attr, None)
            if t:
                t.cancel()
                setattr(self, attr, None)

    def _on_assistant_warn(self):
        """超时前 5 秒：悬浮窗提示即将结束。"""
        if self._recorder.is_recording and self._record_mode == "assistant":
            secs = int(self._ASSISTANT_WARN_BEFORE)
            self._rec_window.update_text(f"录音将在 {secs} 秒后自动结束，请尽快松开按键")

    def _on_assistant_timeout(self):
        if self._recorder.is_recording and self._record_mode == "assistant":
            print("[热键] 助手模式超时，自动结束")
            self._assistant_dispatcher.call_on_main({"action": "timeout_stop"})

    def _is_api_configured(self) -> bool:
        if config.AUTH_METHOD == "app_id_token":
            return bool(config.VOLCENGINE_APPID and config.VOLCENGINE_TOKEN)
        return bool(config.VOLCENGINE_APP_KEY)

    def _start_recording(self, mode: str = "normal"):
        if not self._is_api_configured():
            rumps.notification(
                title="随口说", subtitle="未配置 API",
                message="请打开主窗口 → 模型页面配置 API 凭证",
            )
            return

        if not self._check_microphone():
            return

        self._record_mode = mode
        self._selected_text = get_selected_text() if mode == "normal" else None
        if self._selected_text:
            print(f"[录音] 检测到选中文字({len(self._selected_text)}字)，进入指令模式")

        self._busy = True
        self._set_icon(self.ICON_RECORDING)
        self._set_status("助手聆听中..." if mode == "assistant" else "录音中...")
        self._update_ui_state("recording")

        self._recorder.on_level = self._on_audio_level

        try:
            self._recorder.start()
        except Exception as e:
            self._busy = False
            self._set_icon(self.ICON_IDLE)
            self._set_status("就绪")
            self._update_ui_state("idle")
            rumps.notification(
                title="随口说", subtitle="录音失败",
                message=f"无法启动麦克风: {e}",
            )
            return

        self._asr_session = StreamingSession(
            self._recorder.chunk_queue,
            on_partial=self._on_partial_text,
        )
        self._asr_session.start()

        s = get_settings()
        if s.show_float_window:
            self._rec_window.show()
            if mode == "assistant":
                self._rec_window.update_text("语音助手已召唤，请说指令…")
            elif self._selected_text:
                self._rec_window.update_text("请说出对选中文字的指令…")

    def _on_audio_level(self, level: float):
        self._rec_window.update_level(level)

    def _on_partial_text(self, text: str):
        self._rec_window.update_text(text)

    def _check_microphone(self) -> bool:
        try:
            import sounddevice as sd
            info = sd.query_devices(kind="input")
            if info is None:
                rumps.notification(
                    title="随口说", subtitle="无麦克风",
                    message="未检测到可用的麦克风设备",
                )
                return False
        except Exception:
            rumps.notification(
                title="随口说", subtitle="麦克风不可用",
                message="请在「系统设置→隐私与安全→麦克风」中允许本应用",
            )
            return False
        return True

    def _stop_and_recognize(self):
        self._cancel_assistant_timeout()
        self._set_status("识别中...")
        self._update_ui_state("processing")
        self._rec_window.show_processing()
        self._recorder.stop()

        threading.Thread(
            target=self._wait_for_result,
            daemon=True,
        ).start()

    def _wait_for_result(self):
        notification_info = None
        result_text = None
        selected_text = self._selected_text
        record_mode = self._record_mode or "normal"
        self._selected_text = None

        try:
            if self._asr_session is None:
                return

            session = self._asr_session
            session.wait(timeout=12.0)

            text = session.result
            print(f"[等待结果] ASR 返回: {repr(text)}, 错误: {session.error}")

            if session.error and not text:
                notification_info = ("识别失败", _friendly_asr_error(session.error))
                return

            if not text or not text.strip():
                notification_info = ("未识别到内容", "请靠近麦克风清晰说话后重试")
                return

            if record_mode == "assistant":
                try:
                    self._rec_window.show_thinking()
                    agent_result = handle_voice_command(text, require_wake_word=False)
                    if agent_result.handled:
                        notification_info = ("语音助手", agent_result.message[:100])
                        _play_success_sound()
                    else:
                        notification_info = ("语音助手", f"未识别指令：{text[:80]}")
                    result_text = None
                    self._dispatcher.call_on_main({"refresh_ui": True})
                    return
                except Exception as e:
                    print(f"[助手模式] 异常: {e}")
                    notification_info = ("语音助手异常", _friendly_llm_error(e))
                    return
            elif selected_text:
                print(f"[等待结果] 指令模式: 选中={selected_text[:30]}, 指令={text[:30]}")
                try:
                    self._rec_window.show_thinking()
                    text = process_with_instruction(selected_text, text)
                except Exception as e:
                    print(f"[指令处理] 异常，保持原文: {e}")
                    notification_info = ("指令处理失败", _friendly_llm_error(e))
                    text = selected_text
            else:
                print("[等待结果] 开始技能处理...")
                try:
                    self._rec_window.show_thinking()
                    processed: ProcessResult = _apply_skills(text)
                    text = processed.text
                    if processed.handled_by_agent:
                        notification_info = ("语音 Agent", text[:100])
                        result_text = None
                        return
                except Exception as e:
                    print(f"[技能处理] 异常，使用原始文本: {e}")

            print(f"[等待结果] 处理完成: {repr(text[:80])}")
            result_text = text

        except Exception as e:
            print(f"[等待结果] 异常: {e}")
            notification_info = ("识别异常", _friendly_asr_error(str(e)))
        finally:
            print(f"[等待结果] finally: text={repr(result_text)}, notif={notification_info}")
            self._asr_session = None
            self._record_mode = None
            self._busy = False
            self._dispatcher.call_on_main(
                {"text": result_text, "notif": notification_info}
            )

    def _mainThreadCleanup(self, info):
        """在主线程执行所有 UI 清理操作。"""
        if info and info.get("refresh_ui"):
            self._push_all_settings()
            return

        print("[主线程] cleanup 开始")
        self._set_icon(self.ICON_IDLE)
        self._set_status("就绪")
        self._update_ui_state("idle")

        text = info.get("text") if info else None
        notif = info.get("notif") if info else None

        if text:
            self._rec_window.hide()
            print(f"[主线程] 准备粘贴: {text[:50]}")
            self._add_history(text)
            s = get_settings()
            if s.auto_paste:
                ok = paste_text(text)
                print(f"[主线程] 粘贴结果: {ok}")
                if not ok:
                    self._rec_window.show_result(
                        "已复制到剪贴板",
                        "请授予辅助功能权限后重试，或手动 Cmd+V 粘贴",
                    )
        elif notif:
            print(f"[主线程] 通知: {notif}")
            self._rec_window.show_result(notif[0], notif[1])
        else:
            self._rec_window.hide()
        print("[主线程] cleanup 完成")

    # ── 识别历史 ──

    def _add_history(self, text: str):
        entry = {
            "text": text,
            "time": datetime.now().strftime("%m-%d %H:%M"),
        }
        self._history.append(entry)
        if len(self._history) > _MAX_HISTORY:
            self._history = self._history[-_MAX_HISTORY:]
        _save_history(self._history)
        self._rebuild_history_menu()
        self._push_history_to_ui()

    def _rebuild_history_menu(self):
        try:
            self._history_menu.clear()
        except AttributeError:
            pass
        if not self._history:
            self._history_menu.add(rumps.MenuItem("暂无记录", callback=None))
            return

        for entry in reversed(self._history[-10:]):
            preview = entry["text"][:30]
            if len(entry["text"]) > 30:
                preview += "..."
            label = f"[{entry['time']}] {preview}"
            item = rumps.MenuItem(label, callback=self._on_history_click)
            item.representedObject = entry["text"]
            self._history_menu.add(item)

        if len(self._history) > 10:
            self._history_menu.add(None)
            self._history_menu.add(
                rumps.MenuItem(f"共 {len(self._history)} 条记录", callback=None)
            )

        self._history_menu.add(None)
        self._history_menu.add(
            rumps.MenuItem("清除历史", callback=self._clear_history)
        )

    def _on_history_click(self, sender):
        text = getattr(sender, "representedObject", None)
        if text:
            paste_text(text)

    def _clear_history(self, _sender=None):
        if not confirm_high_risk(
            "确认清除历史",
            "将删除所有识别历史记录，且无法撤销。",
        ):
            return
        self._history = []
        _save_history(self._history)
        self._rebuild_history_menu()
        self._push_history_to_ui()

    # ── 主窗口 ──

    def _open_main_window(self, _sender=None):
        if self._app_window is None:
            self._app_window = AppWindowController.alloc().initWithActionCallback_(
                self._handle_bridge
            )
        self._app_window.show()

    def _handle_bridge(self, method: str, args: dict):
        if method == "_page_loaded":
            self._push_all_settings()
            self._push_history_to_ui()
        elif method == "save_provider":
            self._bridge_save_provider(args)
        elif method == "test_provider":
            self._bridge_test_provider(args)
        elif method == "save_defaults":
            self._bridge_save_defaults(args)
        elif method == "save_general":
            self._bridge_save_general(args)
        elif method == "start_hotkey_record":
            self._bridge_start_hotkey_record()
        elif method == "cancel_hotkey_record":
            self._bridge_cancel_hotkey_record()
        elif method == "save_skills":
            self._bridge_save_skills(args)
        elif method == "open_privacy_settings":
            self._open_privacy_settings()
        elif method == "clear_history":
            self._clear_history()
        elif method == "repaste":
            idx = args.get("index", -1)
            if 0 <= idx < len(self._history):
                paste_text(self._history[idx]["text"])

    def _push_all_settings(self):
        if self._app_window is None:
            return
        s = get_settings()
        v = s.volcengine

        providers = dict(s.providers)
        if "volcengine" not in providers and s.is_volcengine_ready():
            providers["volcengine"] = {
                "auth_method": v.auth_method,
                "app_key": v.app_key,
                "app_id": v.appid,
                "token": v.token,
                "resource_id": v.resource_id,
                "_configured": True,
            }

        providers["builtin_asr"] = {"_configured": True}

        data = {
            "auto_paste": s.auto_paste,
            "show_float_window": s.show_float_window,
            "auto_start": s.auto_start,
            "hotkey_name": s.hotkey_name,
            "providers": providers,
            "default_asr": s.default_asr or "builtin_asr",
            "default_llm": s.default_llm or "",
            "skills": {
                "auto_run": s.skills.auto_run,
                "personalize": s.skills.personalize,
                "personalize_text": s.skills.personalize_text,
                "user_dict": s.skills.user_dict,
                "user_dict_text": s.skills.user_dict_text,
                "auto_structure": s.skills.auto_structure,
                "oral_filter": s.skills.oral_filter,
                "remove_trailing_punct": s.skills.remove_trailing_punct,
                "custom_skills": s.skills.custom_skills,
            },
        }
        self._app_window.call_js("loadSettings", data)

    def _push_history_to_ui(self):
        if self._app_window is None or not self._app_window._page_loaded:
            return
        today = datetime.now().strftime("%m-%d")
        total = len(self._history)
        today_count = sum(1 for h in self._history if h.get("time", "").startswith(today))
        chars = sum(len(h.get("text", "")) for h in self._history)
        state = {
            "history": list(reversed(self._history[-20:])),
            "stats": {"total": total, "today": today_count, "chars": chars},
        }
        self._app_window.call_js_safe("updateState", state)

    def _update_ui_state(self, status: str):
        if self._app_window is None or not self._app_window._page_loaded:
            return
        self._app_window.call_js_safe("updateState", {"status": status})

    # ── Bridge: 服务商配置 ──

    def _bridge_save_provider(self, args: dict):
        provider_id = args.get("id", "")
        category = args.get("category", "")
        if not provider_id:
            return

        cfg = {k: v for k, v in args.items() if k not in ("id", "category")}

        if category == "llm":
            def _validate_and_save():
                from llm_client import test_llm_connection
                ok, msg = test_llm_connection(provider_id, cfg)
                if ok:
                    cfg["_configured"] = True
                    s = get_settings()
                    s.providers[provider_id] = cfg
                    save_settings(s)
                    config.reload()
                if self._app_window:
                    self._app_window.call_js_safe(
                        "onProviderSaveResult", provider_id, ok, msg
                    )
            threading.Thread(target=_validate_and_save, daemon=True).start()
            return

        cfg["_configured"] = True
        s = get_settings()
        s.providers[provider_id] = cfg

        if provider_id == "volcengine":
            v = s.volcengine
            v.auth_method = args.get("auth_method", v.auth_method)
            v.app_key = args.get("app_key", v.app_key)
            v.appid = args.get("app_id", v.appid)
            v.token = args.get("token", v.token)
            v.resource_id = args.get("resource_id", v.resource_id)
            v.enabled = True

        save_settings(s)
        config.reload()
        if self._app_window:
            self._app_window.call_js_safe(
                "onProviderSaveResult", provider_id, True, "已保存"
            )

    def _bridge_test_provider(self, args: dict):
        provider_id = args.get("id", "")

        def _test():
            ok, msg = False, "不支持测试此服务商"
            if provider_id == "volcengine":
                from asr_client import test_connection_sync
                ok, msg = test_connection_sync(
                    auth_method=args.get("auth_method", "app_key"),
                    app_key=args.get("app_key", "").strip(),
                    appid=args.get("app_id", "").strip(),
                    token=args.get("token", "").strip(),
                    cluster="volcano_mega",
                    resource_id=args.get("resource_id", ""),
                )
            if self._app_window:
                self._app_window.call_js_safe(
                    "updateProviderTestResult", provider_id, ok, msg
                )

        threading.Thread(target=_test, daemon=True).start()

    def _bridge_save_defaults(self, args: dict):
        s = get_settings()
        s.default_asr = args.get("default_asr", s.default_asr)
        s.default_llm = args.get("default_llm", s.default_llm)
        save_settings(s)
        config.reload()

    # ── Bridge: 通用设置 ──

    def _bridge_save_general(self, args: dict):
        s = get_settings()
        s.auto_paste = args.get("auto_paste", s.auto_paste)
        s.show_float_window = args.get("show_float_window", s.show_float_window)

        new_auto_start = args.get("auto_start", s.auto_start)
        if new_auto_start != s.auto_start:
            s.auto_start = new_auto_start
            self._set_login_item(new_auto_start)
        save_settings(s)

    def _set_login_item(self, enabled: bool):
        """通过 osascript 设置开机自启动（Login Items）。"""
        app_path = self._get_app_path()
        if not app_path:
            print("[自启动] 未检测到 .app 包，跳过（开发模式下不支持开机自启动）")
            return
        try:
            import subprocess
            if enabled:
                script = (
                    f'tell application "System Events" to make login item '
                    f'at end with properties '
                    f'{{path:"{app_path}", hidden:false}}'
                )
            else:
                app_name = os.path.basename(app_path).replace(".app", "")
                script = (
                    f'tell application "System Events" to delete login item "{app_name}"'
                )
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            print(f"[自启动] {'启用' if enabled else '禁用'} 成功: {app_path}")
        except Exception as e:
            print(f"[自启动] 设置失败: {e}")

    @staticmethod
    def _get_app_path() -> str | None:
        """获取当前运行的 .app 包路径，开发模式下返回 None。"""
        exe = os.path.abspath(sys.executable)
        parts = exe.split(os.sep)
        for i, part in enumerate(parts):
            if part.endswith(".app"):
                return os.sep + os.path.join(*parts[1:i + 1])
        return None

    # ── Bridge: 技能设置 ──

    def _bridge_save_skills(self, args: dict):
        s = get_settings()
        sk = s.skills
        sk.auto_run = args.get("auto_run", sk.auto_run)
        sk.personalize = args.get("personalize", sk.personalize)
        sk.personalize_text = args.get("personalize_text", sk.personalize_text)
        sk.user_dict = args.get("user_dict", sk.user_dict)
        sk.user_dict_text = args.get("user_dict_text", sk.user_dict_text)
        sk.auto_structure = args.get("auto_structure", sk.auto_structure)
        sk.oral_filter = args.get("oral_filter", sk.oral_filter)
        sk.remove_trailing_punct = args.get("remove_trailing_punct", sk.remove_trailing_punct)
        sk.custom_skills = args.get("custom_skills", sk.custom_skills)
        save_settings(s)

    # ── Bridge: 打开系统隐私设置 ──

    @staticmethod
    def _open_privacy_settings():
        import subprocess
        subprocess.Popen([
            "open", "x-apple.systempreferences:com.apple.preference.security?Privacy"
        ])

    # ── Bridge: 快捷键录制 ──

    def _bridge_start_hotkey_record(self):
        self._hotkey_monitor.stop()
        self._hotkey_recorder = HotkeyRecorder(on_recorded=self._on_hotkey_recorded)
        self._hotkey_recorder.start()

    def _bridge_cancel_hotkey_record(self):
        if self._hotkey_recorder:
            self._hotkey_recorder.stop()
            self._hotkey_recorder = None
        self._hotkey_monitor.start()

    def _on_hotkey_recorded(self, keycode: int, name: str):
        self._hotkey_recorder = None

        s = get_settings()
        s.hotkey_keycode = keycode
        s.hotkey_name = name
        save_settings(s)

        self._hotkey_monitor.set_keycode(keycode)
        self._hotkey_monitor.start()

        if self._app_window:
            self._app_window.call_js_safe("onHotkeyRecorded", name)

    # ── 退出 ──

    def _quit(self, _sender):
        self._hotkey_monitor.stop()
        if self._recorder.is_recording:
            self._recorder.stop()
        self._rec_window.hide()
        if self._app_window:
            self._app_window.hide()
        rumps.quit_application()

    @rumps.events.before_start
    def _on_start(self):
        if isinstance(self.ICON_IDLE, NSImage):
            try:
                self._app.nsstatusitem.button().setImage_(self.ICON_IDLE)
                self.title = ""
            except Exception:
                pass

        self._set_dock_icon()
        self._rebuild_history_menu()
        self._hotkey_monitor.start()

        self._dock_handler = _DockActivateHandler.alloc().initWithCallback_(
            self._on_dock_activate
        )
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self._dock_handler,
            "handleActivation:",
            "NSApplicationDidBecomeActiveNotification",
            None,
        )

        self._open_main_window()

        if not self._is_api_configured():
            rumps.notification(
                title="随口说", subtitle="快捷键: " + get_settings().hotkey_name,
                message="请先在「模型」页面配置 API 凭证",
            )

    def _on_dock_activate(self):
        if self._app_window is not None and not self._app_window.is_visible:
            self._open_main_window()


class _MainThreadDispatcher(NSObject):
    """NSObject subclass for reliable main-thread dispatch from background threads."""

    _callback = objc.ivar()

    def initWithCallback_(self, cb):
        self = objc.super(_MainThreadDispatcher, self).init()
        if self is None:
            return None
        self._callback = cb
        return self

    @objc.typedSelector(b"v@:@")
    def dispatch_(self, arg):
        if self._callback:
            self._callback(arg)

    def call_on_main(self, arg):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "dispatch:", arg, False
        )


class _DockActivateHandler(NSObject):

    _callback = objc.ivar()

    def initWithCallback_(self, cb):
        self = objc.super(_DockActivateHandler, self).init()
        if self is None:
            return None
        self._callback = cb
        return self

    @objc.typedSelector(b"v@:@")
    def handleActivation_(self, notification):
        if self._callback:
            self._callback()


def _kill_existing():
    """Kill other instances of this app before starting."""
    import signal, subprocess, time
    my_pid = os.getpid()
    parent_pid = os.getppid()
    killed = []
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "python.*main\\.py"], text=True
        ).strip()
        for line in out.splitlines():
            pid = int(line.strip())
            if pid != my_pid and pid != parent_pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed.append(pid)
                except ProcessLookupError:
                    pass
    except Exception:
        pass
    if killed:
        time.sleep(0.5)
        for pid in killed:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(0.3)


def main():
    _kill_existing()
    VoiceInputApp().run()


if __name__ == "__main__":
    main()
