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

    asr_model: str = "豆包流式语音识别模型 2.0"

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

    skills: SkillsConfig = field(default_factory=SkillsConfig)

    providers: dict = field(default_factory=dict)
    default_asr: str = "builtin_asr"
    default_llm: str = ""

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
            )

        if "sample_rate" in data:
            s.sample_rate = int(data["sample_rate"])

        if "auto_paste" in data:
            s.auto_paste = bool(data["auto_paste"])
        if "show_float_window" in data:
            s.show_float_window = bool(data["show_float_window"])
        if "auto_start" in data:
            s.auto_start = bool(data["auto_start"])
        if "hotkey_keycode" in data:
            s.hotkey_keycode = int(data["hotkey_keycode"])
        if "hotkey_name" in data:
            s.hotkey_name = str(data["hotkey_name"])

        if "providers" in data:
            s.providers = dict(data["providers"])
        if "default_asr" in data:
            s.default_asr = str(data["default_asr"])
        if "default_llm" in data:
            s.default_llm = str(data["default_llm"])

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
        if not os.path.exists(_SETTINGS_PATH):
            return cls()
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[设置] 加载失败，使用默认配置: {e}")
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
