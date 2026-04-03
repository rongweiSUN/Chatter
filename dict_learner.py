"""自动学习用户打字修正 → 用户词典。

语音输入粘贴后，延迟读取输入框内容，对比粘贴瞬间的快照与用户修改后的文本，
将修正的词语自动追加到用户词典中。
"""

from __future__ import annotations

import difflib
import threading
import time

from text_input import get_field_context
from settings import get_settings, save_settings

_MIN_CORRECTION_LEN = 2
_MAX_CORRECTIONS_PER_SESSION = 5
_SNAPSHOT_DELAY = 1.0
_EDIT_WAIT = 5.0
_POLL_INTERVAL = 2.0
_MAX_POLLS = 8
_STABLE_THRESHOLD = 2

_lock = threading.Lock()
_session_id = 0
_on_learned_callback = None


def set_on_learned(callback):
    """设置学习完成回调，签名: callback(new_words: list[str])"""
    global _on_learned_callback
    _on_learned_callback = callback


def start_learning(asr_text: str):
    """粘贴成功后调用，后台延迟读取输入框快照并检测用户修正。"""
    global _session_id

    s = get_settings()
    if not s.skills.auto_learn_dict:
        return

    with _lock:
        _session_id += 1
        sid = _session_id

    threading.Thread(
        target=_learn_worker,
        args=(asr_text, sid),
        daemon=True,
    ).start()


def _is_current_session(sid: int) -> bool:
    with _lock:
        return sid == _session_id


def _learn_worker(asr_text: str, sid: int):
    """后台线程：延迟读取快照，等待用户编辑完成，提取修正并写入词典。"""
    # 等待焦点回到目标应用后再读取快照
    time.sleep(_SNAPSHOT_DELAY)

    if not _is_current_session(sid):
        return

    snapshot = get_field_context()
    if not snapshot or asr_text not in snapshot:
        print(f"[词典学习] 快照不可用或未包含 ASR 文本，跳过 "
              f"(snapshot={'None' if snapshot is None else repr(snapshot[:40])})",
              flush=True)
        return

    print(f"[词典学习] 已获取快照({len(snapshot)}字)，开始监听编辑",
          flush=True)

    # 等待用户开始并完成编辑
    time.sleep(_EDIT_WAIT)

    if not _is_current_session(sid):
        return

    prev_text = None
    stable_count = 0

    for _ in range(_MAX_POLLS):
        if not _is_current_session(sid):
            return

        current = get_field_context()
        if current is None:
            print("[词典学习] 无法读取输入框，放弃", flush=True)
            return

        if current == prev_text:
            stable_count += 1
            if stable_count >= _STABLE_THRESHOLD:
                break
        else:
            stable_count = 0
            prev_text = current

        time.sleep(_POLL_INTERVAL)

    if prev_text is None or prev_text == snapshot:
        print("[词典学习] 输入框无变化，跳过", flush=True)
        return

    corrections = _extract_corrections(asr_text, snapshot, prev_text)
    if corrections:
        _save_corrections(corrections)
        print(f"[词典学习] 自动学习了 {len(corrections)} 个词: "
              f"{'、'.join(corrections)}", flush=True)
        if _on_learned_callback:
            try:
                _on_learned_callback(corrections)
            except Exception as e:
                print(f"[词典学习] 回调异常: {e}", flush=True)
    else:
        print("[词典学习] 未检测到有效修正", flush=True)


def _extract_corrections(
    asr_text: str, snapshot_before: str, snapshot_after: str,
) -> list[str]:
    """对比粘贴后快照和编辑后快照，提取 ASR 文本区域内的修正词。"""
    pos = snapshot_before.find(asr_text)
    if pos < 0:
        return []

    prefix = snapshot_before[:pos]
    suffix = snapshot_before[pos + len(asr_text):]

    if suffix:
        if snapshot_after.startswith(prefix) and snapshot_after.endswith(suffix):
            modified = snapshot_after[len(prefix):-len(suffix)]
        else:
            return _extract_replacements(snapshot_before, snapshot_after)
    else:
        if snapshot_after.startswith(prefix):
            modified = snapshot_after[len(prefix):]
        else:
            return _extract_replacements(snapshot_before, snapshot_after)

    if modified == asr_text:
        return []

    return _extract_replacements(asr_text, modified)


def _extract_replacements(before: str, after: str) -> list[str]:
    """用 SequenceMatcher 提取替换操作中的新文本（用户修正后的词）。"""
    if not before or not after:
        return []

    ratio = difflib.SequenceMatcher(None, before, after, autojunk=False).ratio()
    if ratio < 0.4:
        return []

    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    corrections: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        old_seg = before[i1:i2].strip()
        new_seg = after[j1:j2].strip()
        if (
            len(new_seg) >= _MIN_CORRECTION_LEN
            and len(old_seg) >= _MIN_CORRECTION_LEN
            and new_seg != old_seg
        ):
            corrections.append(new_seg)
            if len(corrections) >= _MAX_CORRECTIONS_PER_SESSION:
                break

    return corrections


def _save_corrections(corrections: list[str]):
    """将修正词追加到用户词典，避免重复。"""
    s = get_settings()
    existing = set(
        w.strip()
        for w in s.skills.user_dict_text.strip().split("\n")
        if w.strip()
    )

    new_words = [w for w in corrections if w not in existing]
    if not new_words:
        return

    lines = s.skills.user_dict_text.strip()
    for w in new_words:
        lines = (lines + "\n" + w) if lines else w

    s.skills.user_dict_text = lines
    if not s.skills.user_dict:
        s.skills.user_dict = True
    save_settings(s)
