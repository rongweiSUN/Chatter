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
- 无
