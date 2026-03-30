# 随口说 — macOS 语音输入助手

macOS 菜单栏语音输入工具，支持 LLM 智能后处理与语音 Agent 管理。

## 功能

- **双模式快捷键**（默认右 Command，可自定义）
  - **短按**：普通输入模式 — 第一次按下开始录音，再按一次结束录音并识别
  - **长按**：语音助手模式 — 按住说话，松开后执行语音指令
- **选中文本 + 语音指令**：先选中一段文字，再短按录音说出指令（如"翻译成英文"），LLM 会按指令改写选中内容
- **LLM 技能引擎**：口语过滤、结构优化、个性化偏好、用户词典、自定义技能，多级后处理
- **语音 Agent**：通过语音直接管理应用设置和技能
- **多模型支持**：ASR / LLM 均可自由配置服务商和模型
- **悬浮窗**：录音波形、实时状态、识别结果展示
- **识别历史**：最近 50 条记录，支持重新粘贴
- 菜单栏实时状态显示（`随口说` / `● 录音中` / `···` 识别中）
- 识别结果自动粘贴到当前光标位置

## 环境要求

- macOS 12+
- Python 3.9+

## 安装

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 配置

### 方式一：通过主窗口配置（推荐）

运行后打开主窗口（点击菜单栏「随口说」或点击 Dock 图标），进入**模型**页面配置 ASR 和 LLM 服务商凭证。首次启动若未配置会弹出提示。

支持的 ASR 服务商：火山引擎、阿里云、SenseVoice（本地）、自定义 API

支持的 LLM 服务商：OpenAI、Claude、DeepSeek、Gemini、通义千问、火山引擎(豆包)、Ollama（本地）、自定义 API

### 方式二：通过 .env 文件

```bash
cp .env.example .env
```

编辑 `.env`，填入火山引擎 API 凭证：

```
VOLCENGINE_APP_KEY=你的AppKey
VOLCENGINE_RESOURCE_ID=volc.seedasr.sauc.duration
```

获取方式：登录 [火山引擎控制台](https://console.volcengine.com/speech/app)，创建语音识别应用。

## 运行

```bash
python main.py
```

也可通过 `setup.py` 打包为 macOS 原生应用：

```bash
python setup.py py2app
```

打包后的应用位于 `dist/随口说.app`。

### 打包为 DMG（便于分发）

在已激活虚拟环境、且已安装 `requirements.txt` 与 `py2app` 的前提下：

```bash
chmod +x build_dmg.sh
./build_dmg.sh
```

生成的磁盘映像为 `dist/随口说.dmg`，内含应用与「应用程序」快捷方式。

- 默认使用 **ad-hoc 签名**（`codesign - -`），本机可运行；若需对外签名，可先执行  
  `export SIGN_IDENTITY="Developer ID Application: 你的名字 (TEAMID)"` 再运行脚本。
- `build.sh` 仍可用于仅构建 `.app` 并使用固定证书名签名；DMG 流程以 `build_dmg.sh` 为准。

## macOS 权限设置

首次运行需要授予以下权限（系统设置 → 隐私与安全性）：

1. **麦克风** — 允许录音
2. **辅助功能** — 允许模拟键盘输入（自动粘贴）
3. **输入监控** — 允许监听全局快捷键

## 使用方法

### 普通输入模式

1. 将光标放在任意文本输入框中
2. **短按快捷键** → 开始录音（菜单栏变为 `● 录音中`）
3. 说话…
4. **再次短按快捷键** → 停止录音，识别并粘贴

### 选中文本指令模式

1. 先选中一段文字
2. **短按快捷键** → 开始录音
3. 说出指令（如"翻译成英文"、"改成更正式的语气"）
4. **再次短按快捷键** → LLM 按指令改写选中内容并替换

### 语音助手模式

1. **长按快捷键** → 开始录音
2. 说出指令
3. **松开快捷键** → 执行指令，结果通过通知展示（不会粘贴到输入框）

## 语音 Agent

带上"随口说"前缀即可触发管理指令：

- `随口说 开启自动粘贴`
- `随口说 关闭悬浮窗`
- `随口说 开启口语过滤`
- `随口说 查看技能`
- `随口说 添加技能 英文润色：把内容润色成自然英文`
- `随口说 删除技能 英文润色`

助手模式下无需"随口说"前缀，直接说指令即可。删除类高危操作会弹窗二次确认。

## 技能系统

在主窗口**技能**页面管理：

- **口语过滤**：去除口语化表达，转为书面语
- **自动结构化**：对长文本自动添加段落和标点
- **个性化偏好**：根据设定的风格偏好调整输出
- **用户词典**：纠正特定领域术语和专有名词
- **去末尾标点**：纯正则处理，不需要 LLM
- **自定义技能**：通过 prompt 定义任意处理逻辑

开启**自动运行**后，所有启用的技能会在每次语音识别后自动执行。

## 项目结构

```
├── main.py              # 菜单栏应用入口 + 核心控制逻辑
├── config.py            # 运行时配置（settings.json 优先，.env 兜底）
├── settings.py          # 设置数据模型 + JSON 持久化
├── recorder.py          # 麦克风录音（实时 PCM 分片）
├── asr_client.py        # 火山引擎 V3 流式 ASR WebSocket 客户端
├── llm_client.py        # OpenAI 兼容 LLM 客户端
├── skill_engine.py      # 技能处理引擎（ASR 文本后处理）
├── voice_agent.py       # 语音 Agent（LLM function calling）
├── text_input.py        # 剪贴板操作 + 模拟粘贴 + 选中文本获取
├── hotkey.py            # 全局快捷键监听（NSEvent）
├── recording_window.py  # 录音悬浮窗（波形 + 状态）
├── app_window.py        # WKWebView 主窗口
├── confirm_dialog.py    # AppleScript 二次确认弹窗
├── setup.py             # py2app 打包配置
└── web/                 # 主窗口前端
    ├── index.html
    ├── app.js
    ├── styles.css
    └── logo.png
```
