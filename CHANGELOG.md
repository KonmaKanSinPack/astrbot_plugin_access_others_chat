# 更新日志（CHANGELOG）

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [v1.1.2] - 2026-08-23

### Security
- 跨会话历史工具和自动私聊注入改为默认关闭。
- 工具调用新增管理员与调用者白名单校验，并补全参数校验。
- 私聊参考内容改为明确标记为不可信的 user 上下文，避免尾部 system 消息覆盖人格或被部分供应商忽略。

## [v1.1.1] - 2026-07-31

### Fixed
- **修复部署环境兄弟模块导入失败（CHG-2）**：AstrBot 以 `data.plugins.<插件名>.main` 包式方式加载插件，插件目录不在 `sys.path` 上，`main.py` 对 `history_utils` 的绝对导入会报 `No module named 'history_utils'`。
  现改为「绝对导入 → 相对导入」双路径回退（先绝对，失败再相对），本地测试环境与部署环境均可正常加载。
  对应设计文档：`docs/SPEC.md` §2 F7、`docs/PLAN.md` §6 变更记录 CHG-2。

## [v1.1.0] - 2026-07-31

### Added
- **群聊自动感知私聊（核心新功能）**：用户在群聊中触发 bot 回复时，插件通过 `@filter.on_llm_request()` 钩子自动把「同一位发送者」与该 bot 的私聊最近对话（默认 10 条 / 2000 字符）注入本次 LLM 请求上下文，无需模型主动调用工具。
  - 注入块带 `_no_save` 标记，AstrBot 保存历史时会过滤，**不会污染群聊对话记录**，也不会逐轮累积。
  - 注入块置于 `request.contexts` 末尾，可躲过 `max_context_length` 的尾部截断。
- **插件配置（`_conf_schema.json`，面板可视化）**：`inject_enabled`（总开关）、`inject_user_whitelist`（user_id 白名单，空=全部用户）、`inject_max_messages`（注入条数）、`inject_max_chars`（注入字符上限）。
- **代码结构拆分**：纯逻辑抽至 `history_utils.py`（零 astrbot 依赖），与 `main.py` 解耦。
- **独立测试**：新增 `tests/test_inject.py`（自含 astrbot 桩，无需安装 AstrBot 即可运行）。

### Changed
- 既有工具 `access_others_chat_history` 重构复用 `extract_text_history`，对外行为与 v1.0.3 完全一致（回归测试覆盖）。
- 实现审查加固（CHG-1）：`render_context_block` 参数防御性 clamp（0/负数/非数字退安全值），注入失败仅降级跳过、绝不阻断正常 LLM 请求。
  对应设计文档：`docs/SPEC.md` §6、`docs/PLAN.md` §6 变更记录 CHG-1。

## [v1.0.3] - 2026-03-22

### Added
- 初始功能：注册 `@filter.llm_tool` 工具 `access_others_chat_history`，让大模型可**按需**访问其他会话（私聊/群聊）的历史记录，实现全局记忆感知。
