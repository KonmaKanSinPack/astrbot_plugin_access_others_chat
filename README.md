# access_others_chat_history

为 AstrBot 大模型提供**跨会话访问聊天记录**的能力。让机器人在和你聊天时，也能知道在其他平台/会话里聊了什么——实现**全局记忆感知**。

## 功能

- ✅ 查询指定用户的私聊历史记录（最近 N 条）
- ✅ 查询指定群组的消息历史记录（最近 N 条）
- ✅ 支持任意平台适配器（微信 `weixin_qty`、`webchat`、`aiocqhttp` 等）
- ✅ 大模型自动调用，无需人工介入

## 工作原理

插件注册了一个 `@filter.llm_tool` 工具 `access_others_chat_history`。当大模型需要了解其他会话的上下文时（例如你问"刚才微信上那个人说了什么"），会**自动调用**此工具获取记录。

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

## 文件结构

```
astrbot_plugin_access_others_chat_history/
├── main.py        # 插件主代码
├── README.md      # 本文件
├── metadata.yaml  # 插件元信息
└── LICENSE        # AGPL-3.0 license
```

## 许可证

AGPL-3.0

> 本插件在 AGPL v3 协议下发布。如果你修改并部署了本插件，请公开你的修改。
