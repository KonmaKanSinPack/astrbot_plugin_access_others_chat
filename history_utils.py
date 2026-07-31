"""纯逻辑工具模块：不依赖 astrbot，可独立单元测试。

职责：UMO 构造、历史抽取、注入块渲染。全部为同步纯函数。
设计定稿见 docs/SPEC.md §3.1。
"""


def build_friend_umo(unified_msg_origin: str, sender_id: str) -> str:
    """由当前群聊事件的 UMO 构造「同一位用户」的私聊会话 UMO。

    例：
        unified_msg_origin="weixin_qty:GroupMessage:group_123", sender_id="o9cq8..."
        -> "weixin_qty:FriendMessage:o9cq8..."

    依据 SPEC F5：UMO 格式为 {platform}:{type}:{session_id}，
    私聊的 session_id 在主流适配器（微信/QQ/Telegram）下就是对方的 user_id。
    """
    platform = unified_msg_origin.split(":")[0] if unified_msg_origin else "default"
    return f"{platform}:FriendMessage:{sender_id}"


def extract_text_history(history: list) -> list:
    """从 OpenAI 格式的历史记录中抽取纯文本 {role, content} 列表。

    过滤规则：
      - role 只保留 user / assistant（跳过 system、tool、工具调用等角色）
      - content 支持两种格式：
          str             —— 直接取用
          list[dict]      —— 只取 {type: "text", text: ...} 段（跳过图片等）
      - 空文本消息跳过
    """
    result = []
    for msg in history:
        if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # OpenAI 多段格式：[{"type": "text", "text": "..."}, {"type": "image_url", ...}]
            text = " ".join(
                seg.get("text", "")
                for seg in content
                if isinstance(seg, dict) and seg.get("type") == "text"
            )
        else:
            continue
        text = text.strip()
        if text:
            result.append({"role": msg["role"], "content": text})
    return result


def render_context_block(messages: list, max_messages: int, max_chars: int) -> str:
    """把私聊纯文本历史渲染成注入用的参考块；空输入返回 ""。

    - 只取最近 max_messages 条
    - 总字符超过 max_chars 时截断，保留尾部（最近的对话）
    - 头部带「记忆参考」标记，明确这是背景信息而非当前对话
    """
    if not messages:
        return ""
    # 防御性 clamp：配置异常（0/负数/超大）时退回安全值，
    # 否则 messages[-0:] 会返回全部消息，max_chars 为负会反向截断
    try:
        max_messages = max(1, int(max_messages))
    except (TypeError, ValueError):
        max_messages = 10
    try:
        max_chars = max(1, int(max_chars))
    except (TypeError, ValueError):
        max_chars = 2000
    recent = messages[-max_messages:]
    lines = []
    for m in recent:
        role = "用户" if m["role"] == "user" else "你"
        lines.append(f"{role}: {m['content']}")
    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[-max_chars:]  # 保留最近部分；行边界不强制，允许截断在行中
    header = (
        "【记忆参考】以下是你与该用户在其他私聊中的最近对话记录，"
        "仅作背景参考，与当前群聊无关，不要把它当成当前对话的一部分对外复述。"
    )
    return header + "\n" + block
