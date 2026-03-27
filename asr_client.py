from __future__ import annotations

"""火山引擎大模型流式语音识别 V3 WebSocket 客户端。

支持实时流式识别：录音同时发送音频，停止后立即获得最终结果。
端点: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
"""

import asyncio
import gzip
import json
import queue
import threading
import uuid

import websockets

import config

# ── 协议常量 ──

PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR = 0b1111

MTS_NO_SEQ = 0b0000
MTS_POS_SEQ = 0b0001
MTS_LAST_NO_SEQ = 0b0010
MTS_LAST_NEG_SEQ = 0b0011

NO_SERIAL = 0b0000
JSON_SERIAL = 0b0001
GZIP_COMPRESS = 0b0001
NO_COMPRESS = 0b0000


def _build_header(
    message_type: int = CLIENT_FULL_REQUEST,
    flags: int = MTS_NO_SEQ,
    serial: int = JSON_SERIAL,
    compress: int = GZIP_COMPRESS,
) -> bytearray:
    header = bytearray(4)
    header[0] = (PROTOCOL_VERSION << 4) | DEFAULT_HEADER_SIZE
    header[1] = (message_type << 4) | flags
    header[2] = (serial << 4) | compress
    header[3] = 0x00
    return header


def _parse_response(data: bytes) -> dict:
    header_size = data[0] & 0x0F
    message_type = data[1] >> 4
    msg_flags = data[1] & 0x0F
    serial_method = data[2] >> 4
    compression = data[2] & 0x0F

    offset = header_size * 4
    result: dict = {}

    if message_type == SERVER_FULL_RESPONSE:
        if msg_flags in (MTS_POS_SEQ, MTS_LAST_NEG_SEQ):
            seq = int.from_bytes(data[offset:offset + 4], "big", signed=True)
            result["sequence"] = seq
            offset += 4
        payload_size = int.from_bytes(data[offset:offset + 4], "big", signed=False)
        offset += 4
        payload = data[offset:offset + payload_size]
    elif message_type == SERVER_ERROR:
        error_code = int.from_bytes(data[offset:offset + 4], "big", signed=False)
        result["error_code"] = error_code
        offset += 4
        payload_size = int.from_bytes(data[offset:offset + 4], "big", signed=False)
        offset += 4
        payload = data[offset:offset + payload_size]
    else:
        return result

    if payload:
        if compression == GZIP_COMPRESS:
            payload = gzip.decompress(payload)
        if serial_method == JSON_SERIAL:
            try:
                result["payload"] = json.loads(payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                result["payload_raw"] = payload
        elif serial_method == NO_SERIAL:
            result["payload_raw"] = payload
        else:
            result["payload_raw"] = payload

    return result


def _build_v3_request_payload() -> dict:
    return {
        "user": {"uid": "voice-input-mac"},
        "audio": {
            "format": "pcm",
            "rate": config.SAMPLE_RATE,
            "bits": 16,
            "channel": config.CHANNELS,
            "codec": "raw",
            "language": "zh-CN",
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": False,
            "show_utterances": True,
            "result_type": "full",
        },
    }


def _build_auth_headers(
    auth_method: str = None,
    app_key: str = None,
    appid: str = None,
    token: str = None,
    cluster: str = None,
    resource_id: str = None,
) -> dict:
    """根据鉴权方式构建 V3 HTTP 请求头。"""
    method = auth_method or config.AUTH_METHOD
    headers = {
        "X-Api-Resource-Id": resource_id or config.VOLCENGINE_RESOURCE_ID,
        "X-Api-Connect-Id": str(uuid.uuid4()),
    }

    if method == "app_id_token":
        headers["X-Api-App-Key"] = appid or config.VOLCENGINE_APPID
        headers["X-Api-Access-Key"] = token or config.VOLCENGINE_TOKEN
    else:
        headers["X-Api-App-Key"] = app_key or config.VOLCENGINE_APP_KEY

    return headers


def _pack_audio(pcm_bytes: bytes, is_last: bool) -> bytes:
    """将 PCM 数据打包为 V3 audio-only 请求帧。"""
    compressed = gzip.compress(pcm_bytes)
    flags = MTS_LAST_NO_SEQ if is_last else MTS_NO_SEQ
    header = _build_header(CLIENT_AUDIO_ONLY, flags, NO_SERIAL, GZIP_COMPRESS)
    frame = bytearray(header)
    frame.extend(len(compressed).to_bytes(4, "big"))
    frame.extend(compressed)
    return bytes(frame)


class StreamingSession:
    """实时流式识别会话。

    在后台线程中运行 asyncio 事件循环，管理 WebSocket 连接。
    录音器产生的 PCM 分片通过 chunk_queue 实时发送到服务端。
    设置 on_partial 回调可实时获取中间识别结果。
    """

    def __init__(self, chunk_queue: queue.Queue, on_partial=None):
        self._chunk_queue = chunk_queue
        self._on_partial = on_partial
        self._result_text = ""
        self._error: str | None = None
        self._done_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._send_finished = False

    @property
    def result(self) -> str:
        return self._result_text

    @property
    def error(self) -> str | None:
        return self._error

    def start(self):
        """启动后台线程，建立 WebSocket 连接并开始收发。"""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def wait(self, timeout: float = 30.0) -> str:
        """阻塞等待识别完成，返回最终文本。"""
        self._done_event.wait(timeout=timeout)
        return self._result_text

    def _run(self):
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._session())
        except Exception as e:
            self._error = str(e)
            print(f"[ASR] 会话异常: {e}")
        finally:
            self._loop.close()
            self._done_event.set()

    async def _session(self):
        request_payload = _build_v3_request_payload()
        payload_bytes = gzip.compress(json.dumps(request_payload).encode("utf-8"))
        full_request = bytearray(_build_header(CLIENT_FULL_REQUEST, MTS_NO_SEQ, JSON_SERIAL, GZIP_COMPRESS))
        full_request.extend(len(payload_bytes).to_bytes(4, "big"))
        full_request.extend(payload_bytes)

        auth_headers = _build_auth_headers()

        async with websockets.connect(
            config.ASR_WS_URL, additional_headers=auth_headers, max_size=1_000_000
        ) as ws:
            await ws.send(full_request)
            resp = await ws.recv()
            parsed = _parse_response(resp)
            if "error_code" in parsed:
                self._error = str(parsed.get("payload", parsed.get("payload_raw", "")))
                print(f"[ASR] 连接错误: {self._error}")
                return

            print("[ASR] 实时识别已连接")
            try:
                await asyncio.wait_for(
                    asyncio.gather(self._send_loop(ws), self._recv_loop(ws)),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                print("[ASR] 会话整体超时，使用已有结果")

        print(f"[ASR] 最终结果: {self._result_text}")

    async def _send_loop(self, ws):
        """从 chunk_queue 读取 PCM 分片并发送。None 表示录音结束。"""
        while True:
            try:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, self._chunk_queue.get, True, 0.5
                )
            except queue.Empty:
                continue

            if chunk is None:
                await ws.send(_pack_audio(b"\x00\x00", is_last=True))
                self._send_finished = True
                print("[ASR] 已发送最后一帧")
                break

            await ws.send(_pack_audio(chunk, is_last=False))

    async def _recv_loop(self, ws):
        """接收服务端识别结果，直到最后一包（负序列号）。"""
        while True:
            timeout = 5.0 if self._send_finished else 15.0
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"[ASR] 接收超时({timeout}s)，使用已有结果")
                break
            except Exception:
                break

            parsed = _parse_response(resp)

            if "error_code" in parsed:
                self._error = str(parsed.get("payload", {}))
                print(f"[ASR] 识别错误: {self._error}")
                break

            payload = parsed.get("payload", {})
            if isinstance(payload, dict):
                result_obj = payload.get("result", {})
                if isinstance(result_obj, dict):
                    text = result_obj.get("text", "")
                    if text:
                        self._result_text = text
                        if self._on_partial:
                            try:
                                self._on_partial(text)
                            except Exception:
                                pass

            seq = parsed.get("sequence", 0)
            if seq < 0:
                break


# ── 连接测试（设置窗口用）──

async def _test_connection(
    auth_method: str = "app_key",
    app_key: str = "",
    appid: str = "",
    token: str = "",
    cluster: str = "",
    resource_id: str = "",
) -> tuple:
    request_payload = {
        "user": {"uid": "connection-test"},
        "audio": {
            "format": "pcm", "rate": 16000, "bits": 16,
            "channel": 1, "codec": "raw", "language": "zh-CN",
        },
        "request": {"model_name": "bigmodel"},
    }
    payload_bytes = gzip.compress(json.dumps(request_payload).encode("utf-8"))
    full_request = bytearray(_build_header(CLIENT_FULL_REQUEST, MTS_NO_SEQ, JSON_SERIAL, GZIP_COMPRESS))
    full_request.extend(len(payload_bytes).to_bytes(4, "big"))
    full_request.extend(payload_bytes)

    auth_headers = _build_auth_headers(
        auth_method=auth_method,
        app_key=app_key,
        appid=appid,
        token=token,
        cluster=cluster,
        resource_id=resource_id,
    )

    try:
        async with websockets.connect(
            config.ASR_WS_URL, additional_headers=auth_headers,
            max_size=1_000_000, open_timeout=5, close_timeout=3,
        ) as ws:
            await ws.send(full_request)
            resp = await asyncio.wait_for(ws.recv(), timeout=5)
            parsed = _parse_response(resp)

            if "error_code" in parsed:
                code = parsed["error_code"]
                payload = parsed.get("payload", parsed.get("payload_raw", b""))
                return False, f"服务端错误 ({code}): {payload}"

            return True, "连接成功"

    except asyncio.TimeoutError:
        return False, "连接超时，请检查网络"
    except ConnectionRefusedError:
        return False, "连接被拒绝，请检查网络"
    except Exception as e:
        return False, f"连接失败: {e}"


def test_connection_sync(**kwargs) -> tuple:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_test_connection(**kwargs))
    finally:
        loop.close()
