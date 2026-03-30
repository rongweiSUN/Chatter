import os
import sys
from setuptools import setup

# 查找 PortAudio dylib 路径
def _find_portaudio():
    import _sounddevice_data
    base = os.path.dirname(_sounddevice_data.__file__)
    dylib = os.path.join(base, "portaudio-binaries", "libportaudio.dylib")
    if os.path.exists(dylib):
        return dylib
    return None

portaudio_path = _find_portaudio()
frameworks = [portaudio_path] if portaudio_path else []

APP = ["main.py"]
DATA_FILES = [("web", ["web/index.html", "web/styles.css", "web/app.js", "web/logo.png"])]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "随口说",
        "CFBundleDisplayName": "随口说",
        "CFBundleIdentifier": "com.xiu.voiceinput",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "12.0",
        "LSUIElement": False,
        "NSMicrophoneUsageDescription": "随口说需要使用麦克风进行语音识别",
        "NSAppleEventsUsageDescription": "随口说需要控制其他应用以输入文本",
    },
    "frameworks": frameworks,
    "packages": [
        "rumps",
        "sounddevice",
        "_sounddevice_data",
        "numpy",
        "websockets",
        "dotenv",
        "objc",
        "AppKit",
        "Foundation",
        "Quartz",
        "WebKit",
    ],
    "includes": [
        "config",
        "recorder",
        "asr_client",
        "text_input",
        "hotkey",
        "settings",
        "recording_window",
        "app_window",
        "llm_client",
        "skill_engine",
        "voice_agent",
        "confirm_dialog",
        "answer_window",
    ],
}
if os.path.exists(os.path.join(os.path.dirname(__file__), "app_icon.icns")):
    OPTIONS["iconfile"] = "app_icon.icns"

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
