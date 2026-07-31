# access_others_chat_history

为 AstrBot 大模型提供**跨会话访问聊天记录**的能力。让机器人在和你聊天时，也能知道在其他平台/会话里聊了什么——实现**全局记忆感知**。

## 功能

- ✅ **群聊自动感知私聊**（v1.1.0 新增）：用户在群聊里和 bot 说话时，插件**自动**把该用户与 bot 的私聊最近对话注入到本次回复的上下文里，无需模型主动调用工具
- ✅ 查询指定用户的私聊历史记录（最近 N 条）
- ✅ 查询指定群组的消息历史记录（最近 N 条）
- ✅ 支持任意平台适配器（微信 `weixin_qty`、`webchat`、`aiocqhttp` 等）
- ✅ 大模型自动调用，无需人工介入

## 工作原理

1. **自动注入（新）**：插件注册了 `@filter.on_llm_request` 钩子。每次群聊 LLM 请求发出前，插件会读取「**同一位发送者**」与该 bot 的私聊最近对话（默认 10 条 / 2000 字符），渲染成一段标记为「记忆参考」的文本，以 `role="system"` 注入本次请求上下文末尾。
2. **按需工具（原有）**：插件注册了 `@filter.llm_tool` 工具 `access_others_chat_history`。当大模型需要了解其他会话的上下文时（例如你问"刚才微信上那个人说了什么"），会**自动调用**此工具获取记录。

### 为什么不会污染群聊历史？

注入块带有 `_no_save` 标记。AstrBot 在保存对话历史时会过滤掉带该标记的消息（见 `astrbot/core/pipeline/process_stage/method/llm_request.py` 的 `_save_to_history`），因此私聊内容**只会出现在单次请求的上下文中，不会写入群聊对话记录**，也不会逐轮累积。

## 配置（v1.1.0 新增，在 AstrBot 面板「插件配置」中修改）

| 配置项 | 类型 | 默认 | 说明 |
|--------|------|------|------|
| `inject_enabled` | bool | `true` | 群聊自动注入私聊上下文总开关 |
| `inject_user_whitelist` | list | `[]` | 只对列表中的 `user_id` 生效；**留空 = 所有用户生效** |
| `inject_max_messages` | int | `10` | 每次注入的私聊最近消息条数（1~50） |
| `inject_max_chars` | int | `2000` | 注入文本总字符数上限（防 token 膨胀） |

> ⚠️ **隐私提示**：群聊中 bot 的回复是**群里所有人都可见**的。若私聊内容不适合公开，请通过 `inject_user_whitelist` 只对可信用户启用注入（例如只填你自己的 user_id）。

## 用法

### subject_id 参数格式

插件接受两种格式的 `subject_id`：

| 格式 | 示例 | 说明 |
|------|------|------|
| **完整 UMO**（推荐） | `weixin_qty:FriendMessage:o9cq8...` | 直接拼接 `{platform_id}:{message_type}:{user_id}` |
| 简写 | `o9cq8...` | 自动补 `default:FriendMessage:` 前缀（仅限 default 平台） |

> **UMO = Unified Message Origin**，格式为 `{platform_id}:{message_type}:{session_id}`，与 AstrBot 底层 `MessageSession` 保持一致。

### 平台前缀参考

| 适配器 | 平台 ID | 私聊 UMO 示例 |
|--------|---------|---------------|
| 微信 | `weixin_qty` | `weixin_qty:FriendMessage:o9cq8...` |
| WebChat | `webchat` | `webchat:FriendMessage:qty!uuid...` |
| OneBot (QQ) | `aiocqhttp` | `aiocqhttp:FriendMessage:123456789` |
| Telegram | `telegram` | `telegram:FriendMessage:123456789` |

> 平台 ID 可以直接从该会话的 `event.unified_msg_origin` 中提取。

### isGroup 参数

- `False` → 查询好友私聊记录，UMO 中 `message_type` 为 `FriendMessage`
- `True` → 查询群组记录，UMO 中 `message_type` 为 `GroupMessage`

### length 参数

可选，默认 20 条，范围 1~100。

### 典型调用场景

**自动注入（无需模型调用）：**

```
用户（群聊）: @bot 刚才私聊里说的那首诗你觉得怎么样？
（插件自动注入该用户私聊最近 10 条 → bot 直接基于私聊内容回答）
```

**大模型内部自动调用：**

```
工具: access_others_chat_history
参数: isGroup=false, subject_id="weixin_qty:FriendMessage:o9cq808...", length=10
```

## 技术细节

插件通过 `self.context.conversation_manager` 访问 AstrBot 的对话存储层：

1. `get_curr_conversation_id(uid)` — 获取当前对话 ID
2. `get_conversation(uid, cid)` — 获取对话完整历史

返回的历史记录会过滤掉非 `user`/`assistant` 角色和图片等非文本内容，仅保留纯文本消息。

> 源码级设计文档见 `docs/PLAN.md` 与 `docs/SPEC.md`（含钩子核心代码设计）。

## 文件结构

```
astrbot_plugin_access_others_chat_history/
├── main.py            # 插件主代码（钩子 + 工具）
├── history_utils.py   # 纯逻辑模块（UMO 构造 / 历史抽取 / 注入块渲染）
├── _conf_schema.json  # 插件配置 schema
├── docs/
│   ├── PLAN.md        # 实施计划（含变更记录）
│   └── SPEC.md        # 设计规格（含核心代码设计）
├── tests/
│   └── test_inject.py # 独立单元/冒烟测试（无需 AstrBot 环境）
├── README.md          # 本文件
├── metadata.yaml      # 插件元信息
└── LICENSE            # AGPL-3.0 license
```

## 许可证

AGPL-3.0

> 本插件在 AGPL v3 协议下发布。如果你修改并部署了本插件，请公开你的修改。
