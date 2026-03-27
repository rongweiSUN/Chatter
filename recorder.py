from __future__ import annotations

import queue
from typing import Callable

import numpy as np
import sounddevice as sd

import config


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
        if self.is_recording:
            self.stop()

        self._pending = bytearray()
        self.chunk_queue = queue.Queue()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            callback=self._audio_callback,
        )
        self._stream.start()
        self.is_recording = True

    def stop(self):
        """停止录音，将剩余数据和 None 哨兵放入队列。"""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.is_recording = False

        if self._pending:
            self.chunk_queue.put(bytes(self._pending))
            self._pending = bytearray()

        self.chunk_queue.put(None)
