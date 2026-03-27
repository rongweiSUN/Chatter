"""配置管理：优先从 settings.json 加载，兼容 .env 文件。"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_from_settings():
    try:
        from settings import get_settings
        s = get_settings()
        if s.is_volcengine_ready():
            return s
    except Exception:
        pass
    return None


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _load_config():
    s = _get_from_settings()
    if s is not None:
        v = s.volcengine
        return {
            "auth_method": v.auth_method,
            "app_key": v.app_key,
            "appid": v.appid,
            "token": v.token,
            "cluster": v.cluster,
            "resource_id": v.resource_id,
            "sample_rate": s.sample_rate,
        }
    return {
        "auth_method": _env("VOLCENGINE_AUTH_METHOD", "app_key"),
        "app_key": _env("VOLCENGINE_APP_KEY"),
        "appid": _env("VOLCENGINE_APPID"),
        "token": _env("VOLCENGINE_TOKEN"),
        "cluster": _env("VOLCENGINE_CLUSTER", "volcano_mega"),
        "resource_id": _env("VOLCENGINE_RESOURCE_ID", "volc.seedasr.sauc.duration"),
        "sample_rate": int(_env("SAMPLE_RATE", "16000")),
    }


_cfg = _load_config()

AUTH_METHOD: str = _cfg["auth_method"]
VOLCENGINE_APP_KEY: str = _cfg["app_key"]
VOLCENGINE_APPID: str = _cfg["appid"]
VOLCENGINE_TOKEN: str = _cfg["token"]
VOLCENGINE_CLUSTER: str = _cfg["cluster"]
VOLCENGINE_RESOURCE_ID: str = _cfg["resource_id"]
SAMPLE_RATE: int = _cfg["sample_rate"]

CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit
ASR_WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"


def reload():
    global AUTH_METHOD, VOLCENGINE_APP_KEY, VOLCENGINE_APPID, VOLCENGINE_TOKEN
    global VOLCENGINE_CLUSTER, VOLCENGINE_RESOURCE_ID
    global SAMPLE_RATE, _cfg

    from settings import reload_settings
    reload_settings()

    _cfg = _load_config()
    AUTH_METHOD = _cfg["auth_method"]
    VOLCENGINE_APP_KEY = _cfg["app_key"]
    VOLCENGINE_APPID = _cfg["appid"]
    VOLCENGINE_TOKEN = _cfg["token"]
    VOLCENGINE_CLUSTER = _cfg["cluster"]
    VOLCENGINE_RESOURCE_ID = _cfg["resource_id"]
    SAMPLE_RATE = _cfg["sample_rate"]
