# 变更日志

> 记录每次 AI 辅助开发的改动内容与用户反馈。

---

## 2026-04-01

### 做了什么
- 新建 `.cursor/rules/changelog.mdc` 规则，要求每次对话结束时将改动和用户反馈记录到本文档
- 新建 `docs/changelog.md`（本文件）作为日志载体

### 用户反馈
- 无（首次创建）

## 2026-04-01 (2)

### 做了什么
- 新增「词典自动学习」功能：语音输入粘贴后，自动检测用户的打字修正，将修正内容追加到用户词典
- 新建 `dict_learner.py`：核心学习模块，粘贴后延迟读取输入框，对比快照差异提取修正词
- `settings.py`：`SkillsConfig` 新增 `auto_learn_dict` 字段
- `main.py`：粘贴成功后调用 `start_learning()`；新增 `_on_dict_learned` 回调，学习完成后刷新 UI 并发送系统通知
- `web/index.html`：用户词典卡片下方新增「自动学习」复选框
- `web/app.js`：`onSkillChanged` 和 `loadSettings` 支持 `auto_learn_dict` 字段
- `web/styles.css`：新增 `.auto-learn-check` 样式

### 用户反馈
- 无

## 2026-04-01 (3)

### 做了什么
- 用户词典热词注入 ASR 引擎：将用户词典中的词汇通过 `corpus.context` 字段直接传入火山引擎大模型 ASR 请求，让语音识别引擎在识别阶段就优先匹配这些词，从源头提升专有名词识别准确率
- `asr_client.py`：`_build_v3_request_payload` 新增 `hotwords` 参数，构建 `corpus` 字段（含 API 限制保护：最多 100 行、每行 50 字符、总计 5000 字符）；`StreamingSession.__init__` 新增 `hotwords` 参数并传递给 payload 构建
- `main.py`：新增 `_get_hotwords()` 方法从用户词典提取热词列表；`_start_recording` 中创建 `StreamingSession` 时传入热词

### 用户反馈
- 用户认为原有的自动学习（dict_learner.py 的 AX API 轮询 + 字符 diff）效果不好，讨论后决定优先实现 ASR 热词注入方案

## 2026-04-03

### 做了什么
- 实现并发任务管理器，将语音录音/识别与后续处理解耦，支持多任务并发执行
- 新建 `task_manager.py`：`TaskManager` 类，基于 `ThreadPoolExecutor` 管理后台任务，支持 submit/get_status_text/has_running_tasks，带线程安全锁和状态变化/完成回调
- 重构 `main.py`：将 `_busy` 标志替换为 `_recording_busy` 录音锁，ASR 完成后立即释放（而非等待全部处理完成）；拆分 `_wait_for_result` 为两阶段——阶段一等待 ASR 并提交任务，阶段二在 TaskManager 线程池中执行；三种处理模式（助手/指令/普通）封装为独立任务函数 `_task_assistant`、`_task_instruction`、`_task_normal`
- `main.py` 新增 `_on_task_status_change`、`_on_task_complete` 回调，`_pending_results` 队列在录音期间缓存任务结果、录音结束后批量投递，`_update_status_display` 按优先级管理状态显示，`_deliver_task_result` 统一处理任务结果投递
- `web/app.js`：`updateState` 新增 `executing` 状态分支和任务列表渲染函数 `renderTaskList`
- `web/styles.css`：新增 `.status-indicator.executing` 紫色脉动动画、`.task-list`/`.task-item`/`.task-dot`/`.task-name` 任务列表样式
- `web/index.html`：状态卡片下方新增 `#taskList` 任务列表容器

### 用户反馈
- 用户要求：只有语音助手模式需要任务编号追踪，普通/指令模式不应编号；所有任务完成后编号重置为 1；回答弹窗支持同时多个，用户点击关闭才消失

## 2026-04-03 (2)

### 做了什么
- `task_manager.py`：任务全部完成后自动将 `_next_id` 重置为 1，下次任务从任务 1 重新开始编号
- `main.py`：重构 `_wait_for_result`，仅助手模式通过 `TaskManager.submit()` 提交带编号追踪的任务；指令模式和普通模式改为直接 `threading.Thread` 后台执行，不经过 TaskManager、不显示任务编号；新增 `_run_bg_task` 方法封装后台执行 + 结果投递逻辑（含录音期间缓存判断）
- `answer_window.py`：去掉单例模式（删除 `_instance` 和 `get_answer_window()`），改为多实例窗口管理——新增 `_active_windows` 列表和 `create_answer_window()` 工厂函数，每次调用创建新窗口；窗口关闭时自动从列表移除，防止内存泄漏
- `main.py`：`_show_answer_window` 改用 `create_answer_window()` 替代旧的 `get_answer_window()`

### 用户反馈
- 无

## 2026-04-03 (3)

### 做了什么
- 修复录音浮窗在全屏/最大化窗口下不显示：`recording_window.py` 设置 `collectionBehavior` 为 `CanJoinAllSpaces | FullScreenAuxiliary`，使浮窗可跨越所有 Space 和全屏窗口显示
- 修复录音浮窗不跟随显示器切换：`recording_window.py` 新增 `_current_screen()` 方法（根据鼠标位置查找当前屏幕），`show()` 中每次重新计算窗口位置居中于当前屏幕顶部
- 修复识别完成后浮窗卡在"识别中"：`main.py` 的 `_wait_for_result` 中，为普通模式和指令模式在启动后台处理线程后调用 `self._rec_window.hide()`，确保浮窗及时隐藏

### 用户反馈
- 语音识别完后浮窗直接消失，缺少"思考中"过渡，粘贴文本慢于弹窗消失；AI 回答弹窗还是无法在最大化应用上显示

## 2026-04-03 (4)

### 做了什么
- 恢复"思考中"过渡动画：`main.py` 的 `_wait_for_result` 中，普通/指令模式 ASR 完成后改为调用 `show_thinking()` 显示渐变边框动画，替代之前的 `hide()`；`_run_bg_task` 中后台任务完成后再隐藏浮窗（若正在录音则不操作，浮窗已被新录音接管）
- 修复 AI 回答弹窗无法在全屏/最大化应用上显示：`answer_window.py` 的 `_build_panel` 中添加 `setCollectionBehavior_(CanJoinAllSpaces | FullScreenAuxiliary)`

### 用户反馈
- 录音浮窗依旧无法在全屏应用上显示

## 2026-04-03 (5)

### 做了什么
- 修复录音浮窗无法在全屏应用上显示：根据 Apple 文档，`FullScreenAuxiliary` 行为仅对 `NSPanel` 或 `NSPopUpMenuWindowLevel` 以上的 `NSWindow` 生效；将 `recording_window.py` 中的 `NSWindow` 改为 `NSPanel`（`NSWindow` 的子类，专为浮动辅助窗口设计），并设置 `setFloatingPanel_(True)` 和 `setHidesOnDeactivate_(False)` 防止切换应用时浮窗消失

### 用户反馈
- 修改快捷键时应用卡死

## 2026-04-03 (6)

### 做了什么
- 修复修改快捷键时应用卡死：`hotkey.py` 中 `HotkeyRecorder._handle` 原来在事件监听回调内部直接调用 `self.stop()`（即 `NSEvent.removeMonitor_`），在 macOS 的本地事件监听器回调中移除自身会导致 run loop 死锁；新增 `_DeferredCall`（`NSObject` 子类），通过 `performSelectorOnMainThread:waitUntilDone:NO` 将 `stop()` 和回调推迟到下一个 run loop 迭代执行，同时增加 `_done` 标志防止重复触发

### 用户反馈
- 无

## 2026-04-03 (7)

### 做了什么
- 快捷键支持符号/标点键：`hotkey.py` 全面扩展，从仅支持修饰键扩展到同时支持普通按键（如 ` / ; ' [ ] \ 等）
- `HotkeyMonitor`：`start()` 根据 keycode 类型自动选择事件掩码——修饰键用 `NSEventMaskFlagsChanged`，普通键用 `NSEventMaskKeyDown | NSEventMaskKeyUp`；`_handle_event` 分两路径处理按下/松开逻辑；`_handle_local` 对普通键返回 `None` 吞掉事件防止产生字符输入
- `HotkeyRecorder`：`start()` 同时监听 `NSEventMaskFlagsChanged | NSEventMaskKeyDown` 捕获所有类型按键；`_handle` 根据事件类型分别处理修饰键和普通键录制，排除 ESC/Return/Tab/Space/Delete/方向键等不适合作为快捷键的按键；用 `event.charactersIgnoringModifiers()` 获取普通键的显示名
- 新增 `_EXCLUDED_KEYCODES` 集合和事件类型常量

### 用户反馈
- 无

## 2026-04-03 (8)

### 做了什么
- AI 回答窗口支持图片展示：`answer_window.py` 的 `_inline` 函数新增 markdown 图片语法 `![alt](src)` 解析，在链接正则之前匹配，转为 `<img>` 标签
- `_HTML_TEMPLATE` CSS 新增 `.answer img` 样式（`max-width: 100%`、圆角、居中），图片自适应窗口宽度
- `loadHTMLString_baseURL_` 的 `baseURL` 从 `None` 改为 `NSURL.fileURLWithPath_("/")`，使 WKWebView 能加载本地文件路径的图片

### 用户反馈
- 无

## 2026-04-03 (9)

### 做了什么
- 修复在 AI 回答窗口中使用语音输入时粘贴为旧剪贴板内容的问题：`text_input.py` 的 `paste_text` 函数中，剪贴板恢复从同步立即执行改为 `threading.Timer(0.5s)` 异步延迟执行，确保 Cmd+V 事件被本应用的 NSTextField 完全处理后再恢复旧剪贴板
- 新用户安装默认开启技能润色：`settings.py` 的 `SkillsConfig.auto_run` 默认值从 `False` 改为 `True`

### 用户反馈
- 无

## 2026-04-03 (10)

### 做了什么
- 新建 `docs/当随口说X DeskClaw.md` 项目介绍文档，包含功能介绍、使用方法、架构图、常见问题等内容

### 用户反馈
- 无

## 2026-04-13

### 做了什么
- 将本地已提交的改动经分支 `feature/sync-2026-04-13` 合并入 `main` 并推送到 GitHub `origin`（`rongweiSUN/Chatter`，提交 `a2c9514`）；包含快捷键扩展、`answer_window` 图片展示、`text_input` 剪贴板延迟恢复、`settings`/`setup`/`recording_window` 等变更及 `docs/当随口说X DeskClaw.md`
- 将 GitHub 仓库 `rongweiSUN/Chatter` 从私有（private）转为公开（public）

### 用户反馈
- 用户要求同步到 GitHub 并将仓库设为公开

## 2026-04-13 (2)

### 做了什么
- 清理仓库中泄露的密钥：`default_settings.json` 中的 API Key、火山引擎 Token/AppID 全部置空
- 将 `default_settings.json` 和 `secrets_backup.txt` 加入 `.gitignore`，从 Git 跟踪中移除 `default_settings.json`
- 使用 `git filter-repo --replace-text` 重写整个 Git 历史，将三个密钥字符串替换为 `***REMOVED***`
- 强制推送到 GitHub，确保远程仓库历史中也不再包含任何明文密钥
- 密钥已备份至本地 `secrets_backup.txt`（不受 Git 跟踪）

### 用户反馈
- 用户要求清理仓库中的密钥

## 2026-04-13 (3)

### 做了什么
- `README.md` 顶部新增"截图"部分，以表格并排展示两张截图：AI 回答浮窗、技能设置界面
- 新增 `docs/images/ai-answer-window.png` 和 `docs/images/skills-settings.png` 两张截图文件

### 用户反馈
- 用户提供飞书 Wiki 链接和两张截图，要求更新到 README
