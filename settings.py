from __future__ import annotations

"""设置数据模型，使用 JSON 文件持久化。

配置文件位置: ~/Library/Application Support/VoiceInput/settings.json
"""

import json
import os
from dataclasses import dataclass, field, asdict

_APP_DIR = os.path.join(
    os.path.expanduser("~"), "Library", "Application Support", "VoiceInput"
)
_SETTINGS_PATH = os.path.join(_APP_DIR, "settings.json")
_DEFAULTS_FILENAME = "default_settings.json"


def _find_bundled_defaults() -> str | None:
    """查找内置的默认配置文件（app bundle Resources 或项目根目录）。"""
    try:
        from AppKit import NSBundle
        res = NSBundle.mainBundle().resourcePath()
        if res:
            p = os.path.join(res, _DEFAULTS_FILENAME)
            if os.path.exists(p):
                return p
    except Exception:
        pass
    p = os.path.join(os.path.dirname(__file__), _DEFAULTS_FILENAME)
    if os.path.exists(p):
        return p
    return None


@dataclass
class ASRProviderConfig:
    """火山引擎 ASR 配置，支持 App Key 和 App ID+Token 两种鉴权。"""
    name: str = ""
    enabled: bool = False
    auth_method: str = "app_key"  # "app_key" | "app_id_token"
    app_key: str = ""
    appid: str = ""
    token: str = ""
    cluster: str = "volcano_mega"
    resource_id: str = ""
    is_builtin: bool = False


@dataclass
class SkillsConfig:
    auto_run: bool = False
    personalize: bool = False
    personalize_text: str = ""
    user_dict: bool = False
    user_dict_text: str = ""
    auto_structure: bool = False
    oral_filter: bool = False
    remove_trailing_punct: bool = False
    custom_skills: list = field(default_factory=list)


@dataclass
class Settings:

    asr_model: str = "随口说语音识别模型"

    volcengine: ASRProviderConfig = field(default_factory=lambda: ASRProviderConfig(
        name="火山引擎",
        enabled=True,
        resource_id="volc.seedasr.sauc.duration",
    ))

    sample_rate: int = 16000

    auto_paste: bool = True
    show_float_window: bool = True
    auto_start: bool = False
    hotkey_keycode: int = 54
    hotkey_name: str = "右 Command"
    first_run: bool = True

    skills: SkillsConfig = field(default_factory=SkillsConfig)

    providers: dict = field(default_factory=lambda: {
        "volcengine_llm": {
            "api_key": "",
            "api_url": "https://llm.onerouter.pro/v1",
            "model": "openai/gpt-oss-120b",
            "_configured": True,
        },
        "builtin_agent": {
            "api_key": "",
            "api_url": "https://llm.onerouter.pro/v1",
            "model": "google/gemini-3-flash-preview",
            "_configured": True,
        },
        "custom_llm": {
            "api_key": "",
            "api_url": "https://llm.onerouter.pro/v1",
            "model": "google/gemini-3-flash-preview",
            "_configured": False,
        },
    })
    default_asr: str = "builtin_asr"
    default_llm: str = "volcengine_llm"
    default_llm_agent: str = "builtin_agent"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        s = cls()
        if "asr_model" in data:
            s.asr_model = data["asr_model"]

        if "volcengine" in data:
            vc = data["volcengine"]
            s.volcengine = ASRProviderConfig(
                name=vc.get("name", "火山引擎"),
                enabled=vc.get("enabled", True),
                auth_method=vc.get("auth_method", "app_key"),
                app_key=vc.get("app_key", ""),
                appid=vc.get("appid", ""),
                token=vc.get("token", ""),
                cluster=vc.get("cluster", "volcano_mega"),
                resource_id=vc.get("resource_id", "volc.seedasr.sauc.duration"),
                is_builtin=vc.get("_builtin", vc.get("is_builtin", False)),
            )

        if "sample_rate" in data:
            try:
                s.sample_rate = int(data["sample_rate"])
            except (ValueError, TypeError):
                pass

        if "auto_paste" in data:
            s.auto_paste = bool(data["auto_paste"])
        if "show_float_window" in data:
            s.show_float_window = bool(data["show_float_window"])
        if "auto_start" in data:
            s.auto_start = bool(data["auto_start"])
        if "hotkey_keycode" in data:
            try:
                s.hotkey_keycode = int(data["hotkey_keycode"])
            except (ValueError, TypeError):
                pass
        if "hotkey_name" in data:
            s.hotkey_name = str(data["hotkey_name"])
        if "first_run" in data:
            s.first_run = bool(data["first_run"])

        if "providers" in data:
            s.providers = dict(data["providers"])
        if "default_asr" in data:
            s.default_asr = str(data["default_asr"])
        if "default_llm" in data:
            s.default_llm = str(data["default_llm"])
        if "default_llm_agent" in data:
            s.default_llm_agent = str(data["default_llm_agent"])

        if "skills" in data:
            sk = data["skills"]
            s.skills = SkillsConfig(
                auto_run=sk.get("auto_run", False),
                personalize=sk.get("personalize", False),
                personalize_text=sk.get("personalize_text", ""),
                user_dict=sk.get("user_dict", False),
                user_dict_text=sk.get("user_dict_text", ""),
                auto_structure=sk.get("auto_structure", False),
                oral_filter=sk.get("oral_filter", False),
                remove_trailing_punct=sk.get("remove_trailing_punct", False),
                custom_skills=sk.get("custom_skills", []),
            )
        return s

    def save(self):
        os.makedirs(_APP_DIR, exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> Settings:
        print(f"[设置] 配置路径: {_SETTINGS_PATH} (存在={os.path.exists(_SETTINGS_PATH)})", flush=True)
        if os.path.exists(_SETTINGS_PATH):
            try:
                with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pid, cfg in (data.get("providers") or {}).items():
                    k = cfg.get("api_key", "")
                    print(f"[设置] 从文件读取 {pid}: key={'***'+k[-6:] if len(k)>6 else '(空)'}", flush=True)
                return cls.from_dict(data)
            except Exception as e:
                print(f"[设置] 加载失败: {e}")

        bundled = _find_bundled_defaults()
        print(f"[设置] 回退到内置默认: {bundled}", flush=True)
        if bundled:
            try:
                with open(bundled, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print("[设置] 使用内置默认配置")
                if "volcengine" in data and isinstance(data["volcengine"], dict):
                    data["volcengine"]["_builtin"] = True
                for prov in (data.get("providers") or {}).values():
                    if isinstance(prov, dict) and prov.get("_configured"):
                        prov["_builtin"] = True
                s = cls.from_dict(data)
                s.first_run = True
                s.save()
                return s
            except Exception as e:
                print(f"[设置] 内置配置加载失败: {e}")

        return cls()

    def is_volcengine_ready(self) -> bool:
        v = self.volcengine
        if not v.enabled:
            return False
        if v.auth_method == "app_id_token":
            return bool(v.appid and v.token)
        return bool(v.app_key)


_current: Settings = None


def get_settings() -> Settings:
    global _current
    if _current is None:
        _current = Settings.load()
    return _current


def reload_settings() -> Settings:
    global _current
    _current = Settings.load()
    return _current


def save_settings(s: Settings):
    global _current
    _current = s
    s.save()
