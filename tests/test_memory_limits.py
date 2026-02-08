import sys
from unittest.mock import MagicMock

# Mock dependencies before importing nanobot
sys.modules["litellm"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["loguru"] = MagicMock()

# Mock Config schema to avoid pydantic issues
mock_schema = MagicMock()
mock_schema.ExecToolConfig = MagicMock
sys.modules["nanobot.config.schema"] = mock_schema

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from pathlib import Path
import sys
import json

# Ensure nanobot is in path
sys.path.append(str(Path(__file__).parent.parent))

from nanobot.session.manager import Session
from nanobot.agent.subagent import SubagentManager
from nanobot.bus.queue import MessageBus

class TestMemoryLimits(unittest.IsolatedAsyncioTestCase):
    
    def test_session_get_history_limits(self):
        """Test that Session.get_history respects max_messages and max_tokens."""
        session = Session(key="test:1")
        
        # Add 20 messages
        for i in range(20):
            session.add_message("user", f"Message {i}")
            
        # Test max_messages
        history = session.get_history(max_messages=5)
        self.assertEqual(len(history), 5)
        self.assertEqual(history[-1]["content"], "Message 19") # Last message matches
        
        # Test max_tokens (mocking estimate_tokens)
        # Assuming estimate_tokens is imported in session.manager
        with patch("nanobot.session.manager.estimate_tokens", return_value=10):
            # Each message is 10 tokens. 
            # Requesting max 35 tokens.
            # Should fit 3 messages (30 tokens). 4th would be 40.
            history = session.get_history(max_messages=20, max_tokens=35)
            self.assertEqual(len(history), 3)

    async def test_subagent_token_limit(self):
        """Test that SubagentManager stops when token limit is reached."""
        
        # Mock dependencies
        mock_provider = MagicMock()
        mock_provider.get_default_model.return_value = "gpt-4"
        mock_provider.chat = AsyncMock()
        
        # Simulate a chat response
        mock_response = MagicMock()
        mock_response.has_tool_calls = False
        mock_response.content = "I am working..."
        mock_provider.chat.return_value = mock_response
        
        mock_bus = MagicMock(spec=MessageBus)
        mock_bus.publish_inbound = AsyncMock()
        
        # Initialize manager with low limit
        manager = SubagentManager(
            provider=mock_provider,
            workspace=Path("/tmp"),
            bus=mock_bus,
            agent_max_tokens=50
        )
        
        # Mock estimate_tokens in the subagent module
        # It's now imported as from nanobot.utils.helpers import estimate_tokens
        # but used in nanobot.agent.subagent
        with patch("nanobot.agent.subagent.estimate_tokens", return_value=30):
            # Prompt(30) + Task(30) = 60. Already > 50.
            # Iteration 1 should break immediately.
            
            await manager._run_subagent(
                task_id="test_task",
                task="Do something",
                label="Test",
                origin={"channel": "cli", "chat_id": "1"}
            )
            
            # Verify chat was NEVER called because limit was hit BEFORE first call
            self.assertEqual(mock_provider.chat.call_count, 0)
            
            # Verify result message indicates limit reached
            self.assertTrue(mock_bus.publish_inbound.called)
            call_args = mock_bus.publish_inbound.call_args[0][0]
            self.assertIn("Token limit reached", call_args.content)

if __name__ == "__main__":
    unittest.main()
