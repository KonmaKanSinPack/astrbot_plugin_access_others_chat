from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT.parent))

from astrbot_plugin_access_others_chat.main import MyPlugin  # noqa: E402


class _ConversationManager:
    def __init__(self):
        self.requested_umo = ""

    async def get_curr_conversation_id(self, umo):
        self.requested_umo = umo
        return "conversation-1"

    async def get_conversation(self, umo, cid):
        return SimpleNamespace(
            history=json.dumps(
                [{"role": "user", "content": "private reference"}],
                ensure_ascii=False,
            )
        )


class _Event:
    unified_msg_origin = "telegram:GroupMessage:group-1"

    def __init__(self, *, admin=False, private=False, sender="user-1"):
        self._admin = admin
        self._private = private
        self._sender = sender

    def is_admin(self):
        return self._admin

    def is_private_chat(self):
        return self._private

    def get_sender_id(self):
        return self._sender


def _plugin(config):
    plugin = object.__new__(MyPlugin)
    plugin.config = config
    plugin.context = SimpleNamespace(conversation_manager=_ConversationManager())
    return plugin


@pytest.mark.asyncio
async def test_cross_session_tool_is_disabled_by_default():
    plugin = _plugin({})

    result = await plugin.access_others_chat_history(
        _Event(admin=True), False, "target", 20
    )

    assert result == "跨会话历史访问工具未启用。"


@pytest.mark.asyncio
async def test_cross_session_tool_rejects_non_admin_by_default():
    plugin = _plugin({"tool_enabled": True})

    result = await plugin.access_others_chat_history(
        _Event(admin=False), False, "target", 20
    )

    assert "仅限管理员" in result


@pytest.mark.asyncio
async def test_private_context_is_untrusted_user_context_and_not_saved():
    plugin = _plugin({"inject_enabled": True})
    request = SimpleNamespace(contexts=[])

    await plugin.inject_private_context(_Event(), request)

    assert request.contexts[0]["role"] == "user"
    assert request.contexts[0]["_no_save"] is True
    assert "untrusted=\"true\"" in request.contexts[0]["content"]
    assert "private reference" in request.contexts[0]["content"]
