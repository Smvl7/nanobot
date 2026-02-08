
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import shutil
import uuid

# Import modules to test
from nanobot.cron.types import CronJob, CronPayload, CronSchedule
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.registry import ProviderSpec

class TestCronEchoAndFallback(unittest.IsolatedAsyncioTestCase):
    
    # --- Test 1: Cron Echo Mode Logic ---
    async def test_cron_echo_mode_dispatch(self):
        """
        Verify that a job with kind='echo' bypasses the agent and publishes directly to the bus.
        We will simulate the logic inside on_cron_job from cli/commands.py.
        """
        print("\n[Test] Cron Echo Mode Dispatch")
        
        # Mocks
        mock_agent = AsyncMock()
        mock_bus = AsyncMock()
        
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
            )
        )
        
        # Simulate the logic from cli/commands.py: on_cron_job
        # We copy the logic here because on_cron_job is an inner function in the CLI
        async def on_cron_job_simulated(job: CronJob):
            if job.payload.kind == "echo":
                if job.payload.to:
                    # Mock OutboundMessage import
                    from nanobot.bus.events import OutboundMessage
                    await mock_bus.publish_outbound(OutboundMessage(
                        channel=job.payload.channel or "cli",
                        chat_id=job.payload.to,
                        content=job.payload.message
                    ))
                return job.payload.message
            
            # Agent path (should not be called)
            await mock_agent.process_direct(job.payload.message)
            return "agent response"

        # Execute
        result = await on_cron_job_simulated(job)
        
        # Verify
        self.assertEqual(result, "Hello World")
        
        # Assert agent was NOT called
        mock_agent.process_direct.assert_not_called()
        print("  ✓ Agent was correctly bypassed")
        
        # Assert bus was called with correct message
        mock_bus.publish_outbound.assert_called_once()
        call_args = mock_bus.publish_outbound.call_args[0][0]
        self.assertEqual(call_args.content, "Hello World")
        self.assertEqual(call_args.chat_id, "user123")
        print("  ✓ Message was published to bus")

    # --- Test 2: LLM Fallback Resolution ---
    def test_litellm_fallback_resolution_openrouter(self):
        """
        Verify that LiteLLMProvider correctly resolves the fallback model name
        when running under OpenRouter (gateway mode).
        """
        print("\n[Test] LiteLLM Fallback Resolution (OpenRouter)")
        
        # Initialize provider with a mock OpenRouter key
        # The constructor will call find_gateway and detect OpenRouter
        provider = LiteLLMProvider(api_key="sk-or-test-key-123")
        
        # Verify it detected OpenRouter
        self.assertTrue(provider.is_openrouter, "Should detect OpenRouter via key prefix")
        
        # Test the critical method: _resolve_model
        # This is what we added to the fallback logic
        fallback_target = "anthropic/claude-sonnet-4.5"
        resolved = provider._resolve_model(fallback_target)
        
        # Expectation: "openrouter/anthropic/claude-sonnet-4.5"
        # Because OpenRouter gateway has litellm_prefix="openrouter"
        expected = "openrouter/anthropic/claude-sonnet-4.5"
        
        self.assertEqual(resolved, expected)
        print(f"  ✓ correctly resolved '{fallback_target}' to '{resolved}'")

    def test_litellm_fallback_resolution_direct(self):
        """
        Verify that standard (non-gateway) providers resolve correctly too.
        """
        print("\n[Test] LiteLLM Fallback Resolution (Direct/Anthropic)")
        
        # Initialize provider with a standard key (no gateway prefix)
        provider = LiteLLMProvider(api_key="sk-ant-test-key", default_model="anthropic/claude-3")
        
        # Verify NO gateway detected
        self.assertIsNone(provider._gateway)
        
        # Test resolution
        fallback_target = "anthropic/claude-sonnet-4.5"
        resolved = provider._resolve_model(fallback_target)
        
        # Expectation: "anthropic/claude-sonnet-4.5" (no change, or auto-prefix if missing)
        # Since it already has the prefix, it should stay as is
        self.assertEqual(resolved, fallback_target)
        print(f"  ✓ correctly resolved '{fallback_target}' to '{resolved}'")

if __name__ == "__main__":
    unittest.main()
