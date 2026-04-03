from __future__ import annotations

import queue
import threading
from typing import Callable

import numpy as np
import sounddevice as sd

import config

_STREAM_CLOSE_TIMEOUT = 1.0
_STREAM_OPEN_TIMEOUT = 3.0


class AudioRecorder:
    """麦克风录音器，支持实时 PCM 分片输出和音量回调。

    调用 start() 后，每 200ms 的音频数据会被放入 chunk_queue。
    如果设置了 on_level 回调，每个分片都会回调当前音量级别 (0.0~1.0)。
    """

    CHUNK_DURATION_MS = 200

    def __init__(self, sample_rate: int = None, channels: int = None):
        self.sample_rate = sample_rate or config.SAMPLE_RATE
        self.channels = channels or config.CHANNELS
        self._stream: sd.InputStream | None = None
        self.is_recording = False
        self.on_level: Callable[[float], None] | None = None

        self.chunk_queue: queue.Queue[bytes | None] = queue.Queue()

        self._chunk_samples = int(self.sample_rate * self.CHUNK_DURATION_MS / 1000)
        self._pending = bytearray()
        self._pa_poisoned = False

    def _audio_callback(self, indata: np.ndarray, frames, time_info, status):
        if status:
            print(f"[录音] 状态警告: {status}")

        if self.on_level is not None:
            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            level = min(rms / 3000.0, 1.0)
            try:
                self.on_level(level)
            except Exception:
                pass

        self._pending.extend(indata.tobytes())

        bytes_per_chunk = self._chunk_samples * self.channels * config.SAMPLE_WIDTH
        while len(self._pending) >= bytes_per_chunk:
            chunk = bytes(self._pending[:bytes_per_chunk])
            del self._pending[:bytes_per_chunk]
            self.chunk_queue.put(chunk)

    def start(self):
        """开始录音。如果已在录音则先停止。

        Raises: 麦克风打开失败时抛出异常，由调用方处理。
        """
        if self._pa_poisoned:
            self._try_recover_pa()

        if self.is_recording:
            self.stop()

        self._pending = bytearray()
        self.chunk_queue = queue.Queue()

        exc_box: list[BaseException | None] = [None]

        def _open():
            try:
                stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    callback=self._audio_callback,
                )
                stream.start()
                self._stream = stream
            except BaseException as e:
                exc_box[0] = e

        t = threading.Thread(target=_open, daemon=True)
        t.start()
        t.join(timeout=_STREAM_OPEN_TIMEOUT)

        if t.is_alive():
            self._pa_poisoned = True
            raise RuntimeError("麦克风打开超时（portaudio 异常），请重启应用")

        if exc_box[0] is not None:
            raise exc_box[0]

        if self._stream is None:
            raise RuntimeError("麦克风打开失败")

        self.is_recording = True

    def stop(self):
        """停止录音，将剩余数据和 None 哨兵放入队列。

        portaudio 的 abort/close 偶发死锁，因此放到独立线程并限时等待，
        超时后放弃关闭（daemon 线程会在进程退出时回收）。
        """
        if not self.is_recording:
            return

        stream = self._stream
        self._stream = None
        self.is_recording = False

        if stream is not None:
            t = threading.Thread(target=self._close_stream, args=(stream,), daemon=True)
            t.start()
            t.join(timeout=_STREAM_CLOSE_TIMEOUT)
            if t.is_alive():
                self._pa_poisoned = True
                print("[录音] 警告: 音频流关闭超时，已跳过", flush=True)

        if self._pending:
            self.chunk_queue.put(bytes(self._pending))
            self._pending = bytearray()

        self.chunk_queue.put(None)

    def _try_recover_pa(self):
        """stream close 超时后尝试重置 portaudio。"""
        print("[录音] 尝试重置 portaudio...", flush=True)
        try:
            sd._terminate()
            sd._initialize()
            self._pa_poisoned = False
            print("[录音] portaudio 重置成功", flush=True)
        except Exception as e:
            print(f"[录音] portaudio 重置失败: {e}", flush=True)

    @staticmethod
    def _close_stream(stream: sd.InputStream):
        try:
            stream.abort()
            stream.close()
        except Exception:
            pass
