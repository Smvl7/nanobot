import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import os

# Import modules to test
from nanobot.cron.types import CronJob, CronPayload, CronSchedule
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.cli.commands import execute_cron_job

class TestCronEchoAndFallback(unittest.IsolatedAsyncioTestCase):
    
    # --- Test 1: Cron Echo Mode Logic ---
    async def test_cron_echo_mode_dispatch(self):
        """
        Verify that a job with kind='echo' bypasses the agent and publishes directly to the bus.
        """
        print("\n[Test] Cron Echo Mode Dispatch")
        
        # Mocks
        mock_agent = AsyncMock()
        mock_bus = AsyncMock()
        mock_bus.publish_outbound = AsyncMock()
        
        # Create a job with kind='echo'
        job = CronJob(
            id="test-job",
            name="Echo Test",
            schedule=CronSchedule(kind="every", every_ms=1000),
            payload=CronPayload(
                kind="echo",
                message="Hello World",
                deliver=True,
                channel="telegram",
                to="user123"
            ),
            state=MagicMock(),
            created_at_ms=0,
            updated_at_ms=0
        )
        
        # Execute the handler (using the actual imported function)
        await execute_cron_job(job, mock_bus, mock_agent)
        
        # Verify:
        # 1. bus.publish_outbound WAS called (echo behavior)
        mock_bus.publish_outbound.assert_called_once()
        args, _ = mock_bus.publish_outbound.call_args
        self.assertIn("Hello World", args[0].content)
        self.assertEqual(args[0].chat_id, "user123")
        
        # 2. agent.process_direct WAS NOT called (bypass behavior)
        mock_agent.process_direct.assert_not_called()
        print("  ✓ Agent was correctly bypassed")
        print("  ✓ Message was published to bus")

    async def test_cron_agent_dispatch(self):
        """Test that cron jobs with kind='agent_turn' go to the agent."""
        
        # Mock dependencies
        mock_bus = MagicMock()
        mock_bus.publish_outbound = AsyncMock()
        
        mock_agent = MagicMock()
        mock_agent.process_direct = AsyncMock(return_value="Done")
        
        # Create a mock CronJob with kind='agent_turn'
        job = CronJob(
            id="test-job-agent",
            name="Test Agent",
            enabled=True,
            schedule=MagicMock(),
            payload=CronPayload(
                kind="agent_turn",
                message="Check weather",
                deliver=True,
                channel="telegram",
                to="12345"
            ),
            state=MagicMock(),
            created_at_ms=0,
            updated_at_ms=0
        )
        
        # Execute the handler
        await execute_cron_job(job, mock_bus, mock_agent)
        
        # Verify:
        # 1. bus.publish_outbound WAS called (result delivery)
        mock_bus.publish_outbound.assert_called_once()
        args, _ = mock_bus.publish_outbound.call_args
        self.assertIn("Done", args[0].content)
        
        # 2. agent.process_direct WAS called
        mock_agent.process_direct.assert_called_once()

    # --- Test 2: LLM Fallback Resolution ---
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"})
    def test_litellm_openrouter_fallback(self):
        """Test that fallback model gets 'openrouter/' prefix if using OpenRouter."""
        
        # Pass api_key to trigger OpenRouter gateway detection
        provider = LiteLLMProvider(
            api_key="sk-or-test",
            default_model="google/gemini-pro"
        )
        
        # Test 1: Fallback resolution
        # Should resolve 'anthropic/claude-sonnet' to 'openrouter/anthropic/claude-sonnet'
        resolved = provider._resolve_model("anthropic/claude-sonnet")
        self.assertEqual(resolved, "openrouter/anthropic/claude-sonnet")
        
        # Test 2: Already prefixed
        resolved = provider._resolve_model("openrouter/google/gemini")
        self.assertEqual(resolved, "openrouter/google/gemini")

    @patch.dict(os.environ, {}, clear=True)
    def test_litellm_native_fallback(self):
        """Test that fallback model stays same if NOT using OpenRouter."""
        
        provider = LiteLLMProvider(default_model="anthropic/claude-3")
        
        # Should NOT add openrouter/ prefix if no key
        resolved = provider._resolve_model("anthropic/claude-sonnet")
        self.assertEqual(resolved, "anthropic/claude-sonnet")

if __name__ == "__main__":
    unittest.main()
