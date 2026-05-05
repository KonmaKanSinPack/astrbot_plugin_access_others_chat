import json
from astrbot.api.provider import ProviderRequest

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from typing import Any, Dict, List, Optional, Tuple
import json_repair



@register("access_others_chat_history", "兔子", "为bot提供访问其他聊天会话的工具，让bot在和你聊天的时候也能知道在其他地方聊了什么", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""


    @filter.llm_tool(name="access_others_chat_history") 
    async def access_others_chat_history(
        self,
        event: AstrMessageEvent,
        isGroup: bool,
        subject_id: str,
        length: Optional[int] = 20
    ) -> MessageEventResult:

        '''访问他人聊天记录工具。
        大模型可以用它来查看其他会话的上下文，实现全局记忆感知。

        适用场景：
          用户问"刚才微信上那个人说了什么"或"群里那件事你记得吗"时，主动调用此工具获取记录。

        Args:
            isGroup (bool): True=群聊, False=私聊。
            subject_id (str): 推荐传入完整 unified_msg_origin 格式，即 "{platform_id}:FriendMessage:{user_id}"。
                - 微信平台: "weixin_qty:FriendMessage:o9cq808..."（私聊）
                - 微信平台: "weixin_qty:GroupMessage:xxxxx"（群聊）
                - WebChat:   "webchat:FriendMessage:qty!uuid..."
                - 也可只传纯 user_id（如 "o9cq8..."），但仅当平台为 default 时才能查到。
                - isGroup=True 时，请将消息类型对应改为 GroupMessage。
            length (int, optional): 返回的最近消息条数，默认20，最大100。
        '''
        length = max(1, min(length, 100))  # 确保 length 在 1 到 100 之间
        if not isinstance(isGroup, bool):
            return "参数 isGroup 必须是布尔值，True 表示群记忆，False 表示好友记忆。"
        
        # 如果 subject_id 已包含 ":"，视为完整 unified_msg_origin 直接使用
        # 否则按旧逻辑补上默认前缀
        if ":" in subject_id:
            uid = subject_id
        else:
            type_name = "default:GroupMessage:" if isGroup else "default:FriendMessage:"
            uid = type_name + subject_id
        # provider_id = await self.context.get_current_chat_provider_id(uid)
        # logger.info(f"uid:{uid}")

        #获取会话历史
        conv_mgr = self.context.conversation_manager
        try:
            curr_cid = await conv_mgr.get_curr_conversation_id(uid)
            conversation = await conv_mgr.get_conversation(uid, curr_cid)  # Conversation
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return f"获取会话历史失败: {e}" 
        history = json.loads(conversation.history) if conversation and conversation.history else []
        result = []
        for msg in history:
            if msg.get("role") not in ["user", "assistant"]:
                continue  # 尽早跳过不需要的 role，减少嵌套
            
            # 用列表推导式，一行搞定过滤 image 和提取 text
            # 遍历 content，只要它是字典且 type 是 text，就把它的 text 值拿出来放到列表里。
            text_parts = [
                item.get("text", "") 
                for item in (msg.get("content") or []) 
                if isinstance(item, dict) and item.get("type") == "text"
            ]

            result.append({
                "role": msg.get("role"),
                "content": " ".join(text_parts) if text_parts else ""
            })

        recent_history = result[-length:]
        return recent_history
        

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
