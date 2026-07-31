import json
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

# 兄弟模块导入（CHG-2）：AstrBot 以 data.plugins.<插件名>.main 的包式方式加载插件
# （v3.5.4/v4 均为 __import__("data.plugins.<name>.main")），插件目录不在 sys.path 上，
# 绝对导入会失败；本地/测试环境（插件目录在 sys.path）则相对导入失败。
# 因此两者都试：先绝对（测试环境），失败再相对（部署环境）。
try:
    from history_utils import build_friend_umo, extract_text_history, render_context_block
except ModuleNotFoundError:
    from .history_utils import build_friend_umo, extract_text_history, render_context_block


@register(
    "astrbot_plugin_access_others_chat",
    "兔子",
    "为bot提供访问其他聊天会话的工具，并让bot在群聊时自动感知私聊内容",
    "v1.1.0",
)
class MyPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        # SPEC F6：有 _conf_schema.json 时 AstrBot 会传入 AstrBotConfig（dict 子类）；
        # 旧版/无 schema 场景回退 None，靠 _cfg 的默认值兜底。
        self.config = config

    # ---------- 配置读取 ----------
    def _cfg(self, key: str, default):
        """安全读取配置；config 缺失/类型异常时返回默认值，绝不抛异常。"""
        try:
            value = self.config.get(key, default) if self.config else default
            return value if value is not None else default
        except Exception:
            return default

    # ---------- 核心：群聊自动注入私聊上下文 ----------
    @filter.on_llm_request()
    async def inject_private_context(
        self, event: AstrMessageEvent, request: ProviderRequest
    ) -> None:
        """群聊 LLM 请求发出前，注入「同一位发送者」的私聊最近对话。

        设计要点（对应 docs/SPEC.md §1/§2 事实）：
          1. 只处理群聊请求：私聊请求的当前会话本身就是私聊历史，无需注入。
          2. 读取私聊会话走 conversation_manager（F4），会话不存在时
             get_curr_conversation_id 返回 None → 静默跳过。
          3. 注入块放在 request.contexts 末尾（F2：尾部不被 max_context_length
             截断逻辑丢弃）。
          4. 注入块带 "_no_save": True（F3：_save_to_history 过滤该键，
             防止私聊内容被写进群聊对话历史逐轮累积）。
          5. 白名单（D4）与条数/字符上限（D5）在配置中可调。
        """
        # ① 总开关
        if not self._cfg("inject_enabled", True):
            return
        # ② 私聊请求不注入
        if event.is_private_chat():
            return
        # ③ 发送者与白名单
        sender_id = event.get_sender_id()
        if not sender_id:
            return
        whitelist = self._cfg("inject_user_whitelist", []) or []
        if whitelist and sender_id not in whitelist:
            return

        # ④ 读取该用户私聊会话的当前对话（F4/F5）
        friend_umo = build_friend_umo(event.unified_msg_origin, sender_id)
        conv_mgr = self.context.conversation_manager
        try:
            cid = await conv_mgr.get_curr_conversation_id(friend_umo)
            if not cid:
                return  # 从未私聊过 → 无可注入内容
            conversation = await conv_mgr.get_conversation(friend_umo, cid)
            if not conversation or not conversation.history:
                return
            history = json.loads(conversation.history)
        except Exception as e:
            logger.warning(f"[access_others_chat] 读取私聊历史失败: {e}")
            return

        # ⑤ 抽取纯文本 → 渲染注入块 → 追加到 contexts 末尾
        try:
            texts = extract_text_history(history)
            block = render_context_block(
                texts,
                max_messages=self._cfg("inject_max_messages", 10),
                max_chars=self._cfg("inject_max_chars", 2000),
            )
            if not block:
                return
            if not isinstance(request.contexts, list):
                request.contexts = []
            request.contexts.append(
                {
                    "role": "system",   # 参考背景语义，不掺入对话流
                    "content": block,
                    "_no_save": True,   # 关键：防止被持久化进群聊对话（F3）
                }
            )
        except Exception as e:
            # 注入失败只降级为"不注入"，绝不阻断正常 LLM 请求
            logger.warning(f"[access_others_chat] 注入私聊上下文失败，已跳过: {e}")

    # ---------- 按需工具：访问其他会话历史 ----------
    @filter.llm_tool(name="access_others_chat_history")
    async def access_others_chat_history(
        self,
        event: AstrMessageEvent,
        isGroup: bool,
        subject_id: str,
        length: Optional[int] = 20,
    ) -> MessageEventResult:
        """访问他人聊天记录工具。
        大模型可以用它来查看其他会话的上下文，实现全局记忆感知。

        适用场景：
          用户问"刚才微信上那个人说了什么"或"群里那件事你记得吗"时，主动调用此工具获取记录。

        Args:
            isGroup (bool): True=群聊, False=私聊。
            subject_id (str): 只传纯 user_id（如 "o9cq8..."），插件会自动补全当前平台前缀。
                - isGroup=True 时，请将消息类型对应改为 GroupMessage。
            length (int, optional): 返回的最近消息条数，默认20，最大100。
        """
        length = max(1, min(length, 100))  # 确保 length 在 1 到 100 之间
        if not isinstance(isGroup, bool):
            return "参数 isGroup 必须是布尔值，True 表示群记忆，False 表示好友记忆。"

        # 如果 subject_id 已包含 ":"，视为完整 unified_msg_origin 直接使用
        # 否则从当前事件的 unified_msg_origin 提取适配器实例名（如 "zbc"），自动补全前缀
        if ":" in subject_id:
            uid = subject_id
        else:
            adapter_name = (
                event.unified_msg_origin.split(":")[0]
                if event.unified_msg_origin
                else "default"
            )
            type_name = f"{adapter_name}:GroupMessage:" if isGroup else f"{adapter_name}:FriendMessage:"
            uid = type_name + subject_id

        # 获取会话历史
        conv_mgr = self.context.conversation_manager
        try:
            curr_cid = await conv_mgr.get_curr_conversation_id(uid)
            conversation = await conv_mgr.get_conversation(uid, curr_cid)  # Conversation
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return f"获取会话历史失败: {e}"

        history = json.loads(conversation.history) if conversation and conversation.history else []
        # 复用纯逻辑抽取函数：过滤 role + 提取 text 段（行为与 v1.0.3 一致）
        result = extract_text_history(history)

        recent_history = result[-length:]
        return recent_history

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
