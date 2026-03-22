import json
from astrbot.api.provider import ProviderRequest

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from typing import Any, Dict, List, Optional, Tuple
import json_repair

from astrbot.api import AstrBotConfig

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

        '''访问他人聊天记录工具，
        大模型可以调用这个工具来访问与其他id的聊天记录，调用时请按顺序确保提供正确的参数。
        当大模型需要增加或更新全局记忆时，可以辅助这个函数来更新记忆。
         

        Args:
            isGroup (bool): True 表示更新群记忆，False 表示更新好友记忆。
            subject_id (str): 群id或好友id.
            length (int, optional): (可选）需要访问的聊天记录条数，默认为20条。注意，不易过长，否则会报错
        '''
        
        if not isinstance(isGroup, bool):
            return "参数 isGroup 必须是布尔值，True 表示群记忆，False 表示好友记忆。"
        type_name = "default:GroupMessage:" if isGroup else "default:FriendMessage:"
        
        uid = type_name + subject_id
        logger.info(f"查看当前uid：{uid}")
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
            if msg.get("role") in ["user", "assistant"]:
                content_result = []
                # logger.info(f"测试1：{msg.get('content', [])}")
                # logger.info(f"测试2：{msg.get('content')[0]}")
                for content in msg.get("content") or []:
                    if isinstance(content, dict):
                        # logger.info(f"测试3：{content}")
                        if content.get("type", "") == "text":
                            content_result.append(content.get("text", ""))

                result.append({
                    "role": msg.get("role"),
                    "content": content_result if content_result else ""
                })

        recent_history = result[-length:]
        return recent_history
        

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
