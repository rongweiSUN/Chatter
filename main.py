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
from AppKit import NSAlert, NSBezierPath, NSColor, NSCompositingOperationSourceOver, NSImage, NSApp
from Foundation import NSObject, NSNotificationCenter

import config
from recorder import AudioRecorder
from asr_client import StreamingSession
from text_input import (
    accessibility_denied_user_hint,
    get_field_context,
    get_frontmost_app_name,
    get_selected_text,
    paste_text,
    prompt_accessibility_registration,
)
from hotkey import EscapeRecordingMonitor, HotkeyMonitor, HotkeyRecorder, KEY_NAMES
from recording_window import get_recording_window
from app_window import AppWindowController
from settings import Settings, get_settings, save_settings, reload_settings
from skill_engine import (
    process_text as _apply_skills,
    process_with_instruction,
    classify_intent,
    answer_question,
    ProcessResult,
)
from confirm_dialog import confirm_high_risk
from deskclaw_client import chat as deskclaw_chat, DeskClawUnavailable, is_available as deskclaw_is_available
from voice_agent import handle_voice_command
from dict_learner import start_learning as _start_dict_learning, set_on_learned
from task_manager import TaskManager, Task, TaskStatus

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


def _apply_icon_mask(img: NSImage) -> NSImage:
    """为 Dock 图标应用 macOS squircle 圆角蒙版，并缩小以匹配系统图标视觉大小。"""
    from Foundation import NSMakeRect, NSZeroRect
    sz = img.size()
    w, h = sz.width, sz.height
    pad = w * 0.07
    iw, ih = w - 2 * pad, h - 2 * pad
    radius = iw * 0.2237

    masked = NSImage.alloc().initWithSize_(sz)
    masked.lockFocus()
    NSColor.clearColor().set()
    NSBezierPath.fillRect_(NSMakeRect(0, 0, w, h))
    clip = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(pad, pad, iw, ih), radius, radius
    )
    clip.addClip()
    img.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, w, h), NSZeroRect, NSCompositingOperationSourceOver, 1.0
    )
    masked.unlockFocus()
    return masked


def _sf_icon(name: str, fallback: str = "随口说") -> NSImage | str:
    from Foundation import NSMakeSize
    try:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is not None:
            img.setSize_(NSMakeSize(18, 18))
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
        self._recording_busy = False
        self._rec_window = get_recording_window()
        self._task_manager = TaskManager(
            on_status_change=self._on_task_status_change,
            on_task_complete=self._on_task_complete,
        )
        self._pending_results: list[dict] = []
        self._pending_lock = threading.Lock()
        self._rec_window.set_cancel_handler(self._on_escape_cancel_recording)
        self._history: list = _load_history()

        s = get_settings()
        self._hotkey_monitor = HotkeyMonitor(
            keycode=s.hotkey_keycode,
            on_key_down=self._on_hotkey_down,
            on_key_up=self._on_hotkey_up,
        )
        self._hotkey_recorder: HotkeyRecorder | None = None
        self._escape_monitor = EscapeRecordingMonitor(on_escape=self._on_escape_cancel_recording)

        self._selected_text: str | None = None
        self._record_session_id: int = 0
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
        self._task_dispatcher = _MainThreadDispatcher.alloc().initWithCallback_(
            self._on_task_dispatch
        )
        self._dict_learn_dispatcher = _MainThreadDispatcher.alloc().initWithCallback_(
            self._on_dict_learned
        )
        set_on_learned(lambda words: self._dict_learn_dispatcher.call_on_main(
            {"words": words}
        ))

    def _set_dock_icon(self):
        for base in [
            os.path.dirname(os.path.abspath(__file__)),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"),
        ]:
            icon_path = os.path.join(base, "logo.png")
            if os.path.exists(icon_path):
                img = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if img:
                    NSApp.setApplicationIconImage_(_apply_icon_mask(img))
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
        self._notify_hotkey_event(True)
        if self._recording_busy:
            return
        self._hotkey_is_down = True
        self._long_press_triggered = False
        self._pre_field_context = get_field_context()
        self._pre_app_name = get_frontmost_app_name()
        self._cancel_hold_timer()
        self._hold_timer = threading.Timer(
            self._long_press_sec, self._on_long_press_detected
        )
        self._hold_timer.daemon = True
        self._hold_timer.start()
        print("[热键] down", flush=True)

    def _on_hotkey_up(self):
        self._notify_hotkey_event(False)
        was_down = self._hotkey_is_down
        triggered = self._long_press_triggered
        self._hotkey_is_down = False
        self._cancel_hold_timer()
        print(f"[热键] up  triggered={triggered} recording={self._recorder.is_recording} busy={self._recording_busy}", flush=True)

        if self._recorder.is_recording:
            self._stop_and_recognize()
            return

        if was_down and not triggered and not self._recording_busy:
            self._start_recording(mode="normal")

    def _cancel_hold_timer(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _on_long_press_detected(self):
        """子线程定时器触发：标记长按，调度主线程启动助手录音。"""
        if self._hotkey_is_down and not self._recording_busy:
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
            if not self._recording_busy and not self._recorder.is_recording:
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
        if get_settings().default_asr == "builtin_asr":
            return True
        if config.AUTH_METHOD == "app_id_token":
            return bool(config.VOLCENGINE_APPID and config.VOLCENGINE_TOKEN)
        return bool(config.VOLCENGINE_APP_KEY)

    def _show_error_alert(self, title: str, message: str):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("好")
        alert.runModal()

    @staticmethod
    def _get_hotwords() -> list[str] | None:
        """从用户词典提取热词列表，供 ASR 引擎优先匹配。"""
        s = get_settings()
        sk = s.skills
        if not sk.user_dict or not sk.user_dict_text.strip():
            return None
        words = [w.strip() for w in sk.user_dict_text.strip().split("\n") if w.strip()]
        return words or None

    def _start_recording(self, mode: str = "normal"):
        if not self._is_api_configured():
            self._show_error_alert(
                "未配置语音识别",
                "请先打开主窗口 → 模型页面，配置 API 凭证后再使用。",
            )
            self._open_main_window()
            return

        if not self._check_microphone():
            return

        self._record_mode = mode
        self._selected_text = None
        self._field_context = getattr(self, '_pre_field_context', None) or get_field_context()
        self._pre_field_context = None
        self._app_name = getattr(self, '_pre_app_name', None) or get_frontmost_app_name()
        self._pre_app_name = None
        self._record_session_id += 1

        self._recording_busy = True
        self._set_icon(self.ICON_RECORDING)
        self._set_status(
            "助手聆听中…（按 ESC 取消）" if mode == "assistant" else "录音中…（按 ESC 取消）"
        )
        self._update_ui_state("recording")

        self._recorder.on_level = self._on_audio_level

        try:
            self._recorder.start()
        except Exception as e:
            self._recording_busy = False
            self._set_icon(self.ICON_IDLE)
            self._update_status_display()
            self._show_error_alert("录音失败", f"无法启动麦克风: {e}")
            return

        self._escape_monitor.start()

        hotwords = self._get_hotwords()
        self._asr_session = StreamingSession(
            self._recorder.chunk_queue,
            on_partial=self._on_partial_text,
            hotwords=hotwords,
        )
        self._asr_session.start()

        threading.Thread(target=self._fetch_selected_text, daemon=True).start()

        s = get_settings()
        if s.show_float_window:
            self._rec_window.show()
            if mode == "assistant":
                self._rec_window.update_text("语音助手已召唤，请说指令…")

    def _fetch_selected_text(self):
        """在后台线程获取选中文字；需要延迟以等待修饰键完全释放。"""
        sid = self._record_session_id
        time.sleep(0.15)
        selected = get_selected_text()
        if selected:
            if self._record_session_id != sid:
                print(f"[录音] 选中文字到达时 session 已过期，丢弃", flush=True)
                return
            self._selected_text = selected
            if self._record_mode == "assistant":
                print(f"[录音] 检测到选中文字({len(selected)}字)，助手模式将附带发送")
                self._rec_window.update_text("已捕获选中文字，请说指令…")
            else:
                print(f"[录音] 检测到选中文字({len(selected)}字)，进入指令模式")
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
                self._show_error_alert("无麦克风", "未检测到可用的麦克风设备。")
                return False
        except Exception:
            self._show_error_alert(
                "麦克风不可用",
                "请在「系统设置 → 隐私与安全 → 麦克风」中允许「随口说」访问麦克风。",
            )
            return False
        return True

    def _on_escape_cancel_recording(self):
        """ESC：放弃当前录音，不识别、不粘贴。"""
        if not self._recorder.is_recording:
            return
        print("[录音] ESC 取消", flush=True)
        self._escape_monitor.stop()
        self._cancel_assistant_timeout()
        self._recorder.stop()
        threading.Thread(target=self._drain_asr_after_cancel, daemon=True).start()

    def _drain_asr_after_cancel(self):
        try:
            if self._asr_session:
                self._asr_session.wait(timeout=8.0)
        except Exception as e:
            print(f"[录音] 取消后 ASR 等待: {e}", flush=True)
        finally:
            self._dispatcher.call_on_main({"recording_cancelled": True})

    def _stop_and_recognize(self):
        if not self._recorder.is_recording:
            return
        print("[停止录音] 1/6 escape_monitor.stop", flush=True)
        self._escape_monitor.stop()
        print("[停止录音] 2/6 cancel_timeout", flush=True)
        self._cancel_assistant_timeout()
        print("[停止录音] 3/6 set_status", flush=True)
        self._set_status("识别中...")
        print("[停止录音] 4/6 update_ui_state", flush=True)
        self._update_ui_state("processing")
        print("[停止录音] 5/6 show_processing", flush=True)
        self._rec_window.show_processing()
        print("[停止录音] 6/6 recorder.stop", flush=True)
        self._recorder.stop()
        print("[停止录音] 完成，启动_wait_for_result线程", flush=True)

        threading.Thread(
            target=self._wait_for_result,
            daemon=True,
        ).start()

    def _wait_for_result(self):
        """阶段一：等待 ASR 结果，然后释放录音锁并提交后续处理为后台任务。"""
        print(f"[等待结果] 线程已启动, mode={self._record_mode}", flush=True)
        selected_text = self._selected_text
        field_context = self._field_context
        app_name = getattr(self, '_app_name', None)
        record_mode = self._record_mode or "normal"
        self._selected_text = None
        self._field_context = None
        self._app_name = None
        notification_info = None

        try:
            if self._asr_session is None:
                print("[等待结果] asr_session 为 None，直接返回", flush=True)
                return

            session = self._asr_session
            print("[等待结果] 开始 session.wait(12s)...", flush=True)
            session.wait(timeout=12.0)
            print("[等待结果] session.wait 已返回", flush=True)

            text = session.result
            print(f"[等待结果] ASR 返回: {repr(text)}, 错误: {session.error}", flush=True)

            if session.error and not text:
                notification_info = ("识别失败", _friendly_asr_error(session.error))
                return

            if not text or not text.strip():
                notification_info = ("未识别到内容", "请靠近麦克风清晰说话后重试")
                return

            task_name = text[:10].strip()
            if record_mode == "assistant":
                self._task_manager.submit(
                    task_name,
                    self._task_assistant, text, selected_text,
                )
                self._rec_window.show_result("已提交任务", task_name, duration=1.5)
            elif selected_text:
                threading.Thread(
                    target=self._run_bg_task,
                    args=(self._task_instruction, text, selected_text),
                    daemon=True,
                ).start()
                self._rec_window.show_thinking()
            else:
                threading.Thread(
                    target=self._run_bg_task,
                    args=(self._task_normal, text, field_context, app_name),
                    daemon=True,
                ).start()
                self._rec_window.show_thinking()

        except Exception as e:
            print(f"[等待结果] 异常: {e}", flush=True)
            notification_info = ("识别异常", _friendly_asr_error(str(e)))
        finally:
            print(f"[等待结果] 释放录音锁, notif={notification_info}", flush=True)
            self._asr_session = None
            self._record_mode = None
            self._recording_busy = False
            self._dispatcher.call_on_main(
                {"asr_done": True, "notif": notification_info}
            )

    def _run_bg_task(self, fn, *args):
        """在后台线程中执行非 TaskManager 任务并投递结果。"""
        try:
            result = fn(*args)
        except Exception as e:
            print(f"[后台任务] 异常: {e}", flush=True)
            result = {"notif": ("处理失败", str(e)[:80])}
        if result is None:
            if not self._recording_busy:
                self._rec_window.hide()
            return
        if self._recording_busy:
            with self._pending_lock:
                self._pending_results.append(result)
            print("[后台任务] 结果已缓存（正在录音中）", flush=True)
        else:
            self._rec_window.hide()
            self._task_dispatcher.call_on_main({"deliver_result": result})

    # ── 后台任务函数（在 TaskManager 线程池中执行） ──

    def _task_assistant(self, text: str, selected_text: str | None) -> dict:
        """助手模式任务：voice_agent + DeskClaw。"""
        print("[任务-助手] 调用 handle_voice_command...", flush=True)
        try:
            agent_result = handle_voice_command(text, require_wake_word=False)
        except Exception as ae:
            print(f"[任务-助手] 本地 Agent 异常，继续走 DeskClaw: {ae}", flush=True)
            agent_result = None
        print(f"[任务-助手] voice_agent 返回: handled={getattr(agent_result, 'handled', None)}, used_tool={getattr(agent_result, 'used_tool', None)}", flush=True)

        if agent_result and agent_result.handled and agent_result.used_tool:
            print(f"[任务-助手] 本地 Agent 已处理: {agent_result.message[:80]}", flush=True)
            _play_success_sound()
            self._task_dispatcher.call_on_main({"refresh_ui": True})
            return {
                "notif": ("语音助手", agent_result.message[:150]),
                "assistant_entry": {"question": text, "reply": agent_result.message},
            }

        try:
            deskclaw_msg = text
            if selected_text:
                deskclaw_msg = f"[用户选中的文本]\n{selected_text}\n\n[语音指令]\n{text}"
                print(f"[任务-助手] 附带选中文本({len(selected_text)}字)", flush=True)
            print(f"[任务-助手] 发送至 DeskClaw: {deskclaw_msg[:80]}", flush=True)
            resp = deskclaw_chat(deskclaw_msg)
            content = (resp.get("content") or "").strip()
            print(f"[任务-助手] DeskClaw 回复({len(content)}字): {content[:100]}", flush=True)
            _play_success_sound()
            return {
                "show_answer": True,
                "answer_text": content or "任务已执行",
                "question": text,
                "deskclaw_continue": True,
                "assistant_entry": {"question": text, "reply": content or "（无文本回复）"},
            }
        except DeskClawUnavailable:
            return {"notif": ("DeskClaw 未连接", "请先启动 DeskClaw 应用")}
        except Exception as e:
            print(f"[任务-助手] DeskClaw 异常: {e}")
            return {"notif": ("DeskClaw 异常", str(e)[:80])}

    def _task_instruction(self, text: str, selected_text: str) -> dict:
        """指令模式任务：classify + rewrite/answer。"""
        print(f"[任务-指令] 选中={selected_text[:30]}, 指令={text[:30]}")
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:
                classify_future = pool.submit(classify_intent, selected_text, text)
                rewrite_future = pool.submit(process_with_instruction, selected_text, text)

                try:
                    intent = classify_future.result(timeout=6.0)
                except Exception as ce:
                    print(f"[任务-指令] 意图分类异常，fallback rewrite: {ce}")
                    intent = "rewrite"

                if intent == "question":
                    rewrite_future.cancel()
                    print("[任务-指令] 意图=提问，启动 answer_question")
                    answer = answer_question(selected_text, text)
                    return {
                        "show_answer": True,
                        "answer_text": answer,
                        "question": text,
                    }
                else:
                    print("[任务-指令] 意图=改写，等待改写结果")
                    rewrite_result = rewrite_future.result(timeout=20.0)
                    if rewrite_result is not None:
                        return {"text": rewrite_result}
                    else:
                        return {"notif": ("指令处理失败", "大模型未返回结果，请检查模型配置")}
        except Exception as e:
            print(f"[任务-指令] 异常: {e}")
            return {"notif": ("指令处理失败", _friendly_llm_error(e))}

    def _task_normal(self, text: str, field_context: str | None, app_name: str | None) -> dict:
        """普通模式任务：skill_engine 处理。"""
        print("[任务-普通] 开始技能处理...", flush=True)
        try:
            processed: ProcessResult = _apply_skills(text, field_context=field_context, app_name=app_name)
            text = processed.text
            if processed.handled_by_agent:
                return {"notif": ("语音 Agent", text[:100])}
        except Exception as e:
            print(f"[任务-普通] 技能处理异常，使用原始文本: {e}")

        print(f"[任务-普通] 处理完成: {repr(text[:80])}")
        return {"text": text}

    def _mainThreadCleanup(self, info):
        """在主线程执行 ASR 阶段结束后的 UI 清理。"""
        if info and info.get("refresh_ui"):
            self._push_all_settings()
            return

        if info and info.get("recording_cancelled"):
            print("[主线程] 录音已取消", flush=True)
            self._asr_session = None
            self._record_mode = None
            self._recording_busy = False
            self._set_icon(self.ICON_IDLE)
            self._update_status_display()
            self._rec_window.hide()
            self._flush_pending_results()
            return

        if info and info.get("asr_done"):
            print("[主线程] ASR 阶段完成，录音锁已释放", flush=True)
            self._set_icon(self.ICON_IDLE)
            self._update_status_display()
            notif = info.get("notif")
            if notif:
                print(f"[主线程] ASR 阶段通知: {notif}")
                self._rec_window.show_result(notif[0], notif[1])
            self._flush_pending_results()
            return

        self._rec_window.hide()
        print("[主线程] cleanup 完成")

    # ── 任务管理回调 ──

    def _on_task_status_change(self, status_text: str):
        """TaskManager 状态变化回调（从后台线程调用）。"""
        self._task_dispatcher.call_on_main({"update_status": True})

    def _on_task_complete(self, task: Task):
        """TaskManager 任务完成回调（从后台线程调用）。"""
        result = task.result if task.status == TaskStatus.COMPLETED else None
        if result is None and task.status == TaskStatus.FAILED:
            result = {"notif": ("任务失败", task.error or "未知错误")}
        if result is None:
            return

        if self._recording_busy:
            with self._pending_lock:
                self._pending_results.append(result)
            print(f"[任务完成] 任务{task.id} 结果已缓存（正在录音中）", flush=True)
        else:
            self._task_dispatcher.call_on_main({"deliver_result": result})

    def _on_task_dispatch(self, info):
        """在主线程处理任务相关调度。"""
        if not info:
            return

        if info.get("refresh_ui"):
            self._push_all_settings()
            return

        if info.get("update_status"):
            self._update_status_display()
            return

        result = info.get("deliver_result")
        if result:
            self._deliver_task_result(result)

    def _deliver_task_result(self, result: dict):
        """在主线程投递单个任务结果。"""
        if result.get("show_answer"):
            print("[任务投递] 显示 AI 回答浮窗")
            assistant_entry = result.get("assistant_entry")
            if assistant_entry:
                try:
                    self._add_history(
                        assistant_entry["question"], reply=assistant_entry["reply"]
                    )
                except Exception as e:
                    print(f"[任务投递] 保存助手历史失败: {e}", flush=True)
            self._show_answer_window(
                result["answer_text"],
                result.get("question", ""),
                deskclaw_continue=bool(result.get("deskclaw_continue")),
            )
            self._update_status_display()
            return

        text = result.get("text")
        notif = result.get("notif")
        assistant_entry = result.get("assistant_entry")

        if assistant_entry:
            try:
                self._add_history(
                    assistant_entry["question"], reply=assistant_entry["reply"]
                )
            except Exception as e:
                print(f"[任务投递] 保存助手历史失败: {e}", flush=True)

        if text:
            print(f"[任务投递] 准备粘贴: {text[:50]}")
            try:
                self._add_history(text)
            except Exception as e:
                print(f"[任务投递] 保存历史失败: {e}", flush=True)
            s = get_settings()
            if s.auto_paste:
                ok = paste_text(text)
                print(f"[任务投递] 粘贴结果: {ok}")
                if ok:
                    _start_dict_learning(text)
                else:
                    alert = NSAlert.alloc().init()
                    alert.setMessageText_("已复制到剪贴板")
                    alert.setInformativeText_(
                        "无法模拟键盘自动粘贴。可手动 Cmd+V。\n\n"
                        + accessibility_denied_user_hint()
                    )
                    alert.addButtonWithTitle_("好")
                    alert.runModal()
        elif notif:
            print(f"[任务投递] 通知: {notif}")
            self._rec_window.show_result(notif[0], notif[1])

        self._update_status_display()

    def _flush_pending_results(self):
        """投递录音期间缓存的任务结果。"""
        with self._pending_lock:
            pending = list(self._pending_results)
            self._pending_results.clear()
        for result in pending:
            print("[主线程] 投递缓存的任务结果", flush=True)
            self._deliver_task_result(result)

    def _update_status_display(self):
        """根据当前状态优先级更新菜单栏和 Web UI 的状态显示。"""
        if self._recording_busy:
            return

        if self._task_manager.has_running_tasks():
            status_text = self._task_manager.get_status_text()
            self._set_status(status_text)
            ui_state = self._task_manager.get_status_for_ui()
            self._update_ui_state_full(ui_state)
        else:
            self._set_status("就绪")
            self._update_ui_state("idle")

    # ── AI 回答浮窗 ──

    def _show_answer_window(
        self,
        answer_text: str,
        question: str,
        *,
        deskclaw_continue: bool = False,
    ):
        """在主线程创建并显示 AI 回答浮窗（每次新建窗口）。"""
        from answer_window import create_answer_window
        win = create_answer_window()
        win.show_answer(question, answer_text, deskclaw_continue=deskclaw_continue)

    # ── 识别历史 ──

    def _add_history(self, text: str, *, reply: str | None = None):
        entry = {
            "text": text,
            "time": datetime.now().strftime("%m-%d %H:%M"),
        }
        if reply is not None:
            entry["reply"] = reply
            entry["type"] = "assistant"
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
            if entry.get("type") == "assistant":
                q = entry["text"][:12]
                r = (entry.get("reply") or "")[:15]
                preview = f"🤖 {q} → {r}"
                if len(entry["text"]) > 12 or len(entry.get("reply", "")) > 15:
                    preview += "…"
                paste_obj = entry.get("reply") or entry["text"]
            else:
                preview = entry["text"][:30]
                if len(entry["text"]) > 30:
                    preview += "..."
                paste_obj = entry["text"]
            label = f"[{entry['time']}] {preview}"
            item = rumps.MenuItem(label, callback=self._on_history_click)
            item.representedObject = paste_obj
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
            self._check_deskclaw_status()
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
        elif method == "open_privacy_microphone":
            self._open_privacy_microphone()
        elif method == "open_privacy_accessibility":
            self._open_privacy_accessibility()
        elif method == "open_privacy_input_monitoring":
            self._open_privacy_input_monitoring()
        elif method == "check_deskclaw":
            self._check_deskclaw_status()
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

        providers = {pid: dict(cfg) for pid, cfg in s.providers.items()}
        if "volcengine" not in providers and s.is_volcengine_ready():
            providers["volcengine"] = {
                "auth_method": v.auth_method,
                "app_key": v.app_key,
                "app_id": v.appid,
                "token": v.token,
                "resource_id": v.resource_id,
                "_configured": True,
                "_builtin": v.is_builtin,
            }

        providers["builtin_asr"] = {"_configured": True}

        if "volcengine_llm" not in providers or not providers["volcengine_llm"].get("_configured"):
            providers["volcengine_llm"] = {
                "api_key": "",
                "api_url": "https://llm.onerouter.pro/v1",
                "model": "openai/gpt-oss-120b",
                "_configured": True,
            }

        _SECRET_KEYS = ("app_key", "api_key", "token", "appid", "app_id")
        for prov in providers.values():
            if prov.get("_builtin"):
                for k in _SECRET_KEYS:
                    if k in prov and prov[k]:
                        prov[k] = ""

        data = {
            "auto_paste": s.auto_paste,
            "show_float_window": s.show_float_window,
            "auto_start": s.auto_start,
            "hotkey_name": s.hotkey_name,
            "providers": providers,
            "default_asr": s.default_asr or "builtin_asr",
            "default_llm": s.default_llm or "volcengine_llm",
            "default_llm_agent": s.default_llm_agent or "volcengine_llm",
            "skills": {
                "auto_run": s.skills.auto_run,
                "personalize": s.skills.personalize,
                "personalize_text": s.skills.personalize_text,
                "user_dict": s.skills.user_dict,
                "user_dict_text": s.skills.user_dict_text,
                "auto_learn_dict": s.skills.auto_learn_dict,
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

    def _update_ui_state_full(self, state: dict):
        if self._app_window is None or not self._app_window._page_loaded:
            return
        self._app_window.call_js_safe("updateState", state)

    def _notify_hotkey_event(self, is_down: bool):
        if self._app_window is None or not self._app_window._page_loaded:
            return
        self._app_window.call_js_safe("obOnHotkeyEvent", is_down)

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
        s.default_llm_agent = args.get("default_llm_agent", s.default_llm_agent)
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

    # ── 词典自动学习回调 ──

    def _on_dict_learned(self, info):
        """词典自动学习完成后在主线程刷新 UI。"""
        words = info.get("words", []) if info else []
        if not words:
            return
        print(f"[主线程] 词典自动学习: {'、'.join(words)}", flush=True)
        self._push_all_settings()
        rumps.notification(
            title="随口说",
            subtitle="词典自动学习",
            message=f"已学习: {'、'.join(words)}",
        )

    # ── Bridge: 技能设置 ──

    def _bridge_save_skills(self, args: dict):
        s = get_settings()
        sk = s.skills
        sk.auto_run = args.get("auto_run", sk.auto_run)
        sk.personalize = args.get("personalize", sk.personalize)
        sk.personalize_text = args.get("personalize_text", sk.personalize_text)
        sk.user_dict = args.get("user_dict", sk.user_dict)
        sk.user_dict_text = args.get("user_dict_text", sk.user_dict_text)
        sk.auto_learn_dict = args.get("auto_learn_dict", sk.auto_learn_dict)
        sk.auto_structure = args.get("auto_structure", sk.auto_structure)
        sk.oral_filter = args.get("oral_filter", sk.oral_filter)
        sk.remove_trailing_punct = args.get("remove_trailing_punct", sk.remove_trailing_punct)
        sk.custom_skills = args.get("custom_skills", sk.custom_skills)
        save_settings(s)

    # ── Bridge: 打开系统隐私设置 ──

    @staticmethod
    def _open_privacy_page(anchor: str):
        import subprocess
        subprocess.Popen([
            "open",
            f"x-apple.systempreferences:com.apple.preference.security?{anchor}",
        ])

    def _open_privacy_settings(self):
        self._open_privacy_page("Privacy")

    def _open_privacy_microphone(self):
        self._open_privacy_page("Privacy_Microphone")

    def _open_privacy_accessibility(self):
        self._open_privacy_page("Privacy_Accessibility")

    def _open_privacy_input_monitoring(self):
        self._open_privacy_page("Privacy_ListenEvent")

    def _warn_input_monitoring_missing(self):
        """热键全局监听注册失败时弹窗提醒用户授予「输入监控」权限。"""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("快捷键无法使用")
        alert.setInformativeText_(
            "全局快捷键监听注册失败，可能未授予「输入监控」权限。\n\n"
            "请打开「系统设置 → 隐私与安全性 → 输入监控」，\n"
            "将「随口说」的开关打开，然后重启应用。\n\n"
            "没有此权限时，在其它应用中按快捷键将无法触发语音输入。"
        )
        alert.addButtonWithTitle_("打开输入监控设置")
        alert.addButtonWithTitle_("稍后")
        resp = alert.runModal()
        if resp == 1000:
            self._open_privacy_input_monitoring()

    # ── DeskClaw 连接检测 ──

    def _check_deskclaw_status(self):
        def _check():
            try:
                ok = deskclaw_is_available(timeout=3.0)
            except Exception:
                ok = False
            msg = "已连接" if ok else "未连接"
            if self._app_window:
                self._app_window.call_js_safe("updateDeskclawStatus", ok, msg)
        threading.Thread(target=_check, daemon=True).start()

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
        self._escape_monitor.stop()
        if self._recorder.is_recording:
            self._recorder.stop()
        self._task_manager.shutdown()
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

        if self._hotkey_monitor._global_monitor is None:
            self._warn_input_monitoring_missing()

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

        s = get_settings()
        if s.first_run:
            try:
                prompt_accessibility_registration()
            except Exception as e:
                print(f"[首次启动] 辅助功能注册异常: {e}", flush=True)

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
