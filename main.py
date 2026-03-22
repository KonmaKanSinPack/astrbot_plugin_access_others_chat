import json

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("access_others_chat_history", "兔子", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""


    @filter.llm_tool(name="access_others_chat_history") 
    async def access_others_chat_history(self, GroupOrFriend: bool, subject_id: str,
                                ) -> MessageEventResult:

        '''访问他人聊天记录工具，
        大模型可以调用这个工具来访问与其他id的聊天记录，调用时请按顺序确保提供正确的参数。
        当大模型需要增加或更新全局记忆时，可以辅助这个函数来更新记忆。
         

        Args:
            GroupOrFriend (bool): True 表示更新群记忆，False 表示更新好友记忆。
            subject_id (str): 群id或好友id.
        '''
        
        if not isinstance(GroupOrFriend, bool):
            return "参数 GroupOrFriend 必须是布尔值，True 表示群记忆，False 表示好友记忆。"
        type_name = "default:GroupMessage:" if GroupOrFriend else "default:FriendMessage:"
        
        uid = type_name + subject_id
        logger.info(f"查看当前uid：{uid}")
        logger.info(f"查看当前会话id：{subject_id}")
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

        return history
        

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
