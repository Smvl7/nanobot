import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from types import SimpleNamespace

from nanobot.agent.context import ContextBuilder
from nanobot.providers.litellm_provider import LiteLLMProvider, LLMResponse

class TestContextBuilderCaching(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("/tmp/mock_workspace")
        self.context_builder = ContextBuilder(self.workspace)
        
        # Mock dependencies to avoid file I/O
        self.context_builder.memory = MagicMock()
        self.context_builder.memory.get_memory_context.return_value = "Mock Memory"
        self.context_builder.skills = MagicMock()
        self.context_builder.skills.get_always_skills.return_value = []
        self.context_builder.skills.build_skills_summary.return_value = ""
        
        # Mock _load_bootstrap_files to avoid reading disk
        self.context_builder._load_bootstrap_files = MagicMock(return_value="## Mock Bootstrap")
        
        # Mock layer methods
        self.context_builder._get_layer_1_static = MagicMock(return_value="# Layer 1: Static Identity")
        self.context_builder._get_layer_2_memory = MagicMock(return_value="# Layer 2: Memory & Tasks")
        self.context_builder._get_layer_3_dynamic = MagicMock(return_value="# Layer 3: Dynamic Time")

    def test_integration_no_mocks(self):
        """Integration Test: Verify ContextBuilder works without mocking internal methods."""
        # Use a real ContextBuilder without method mocks
        real_builder = ContextBuilder(self.workspace)
        
        # Mock only the I/O parts (memory reading, skills) to avoid file system errors
        real_builder.memory = MagicMock()
        real_builder.memory.get_memory_context.return_value = "Real Memory"
        real_builder.skills = MagicMock()
        real_builder.skills.get_always_skills.return_value = []
        real_builder.skills.build_skills_summary.return_value = ""
        
        # Mock file reading to avoid FS dependency
        real_builder._load_bootstrap_files = MagicMock(return_value="## Bootstrap")
        
        # This call should succeed if all internal methods (_get_static_identity, etc.) exist
        messages = real_builder.build_messages(
            history=[], current_message="Test", enable_caching=True
        )
        
        self.assertEqual(len(messages), 2) # System + User
        system_content = messages[0]["content"]
        self.assertEqual(len(system_content), 3) # L1, L2, L3
        
        # Verify real content generation
        self.assertIn("nanobot", system_content[0]["text"]) # From _get_static_identity
        self.assertIn("Real Memory", system_content[1]["text"]) # From _get_layer_2_memory
        self.assertIn("Current Time", system_content[2]["text"]) # From _get_layer_3_dynamic

    def test_smart_caching_cold_start(self):
        """Test: First run (L2 hash unknown) -> Cache control on L1 (Safe fallback)."""
        messages = self.context_builder.build_messages(
            history=[], current_message="Hi", enable_caching=True
        )
        
        system_content = messages[0]["content"]
        self.assertEqual(len(system_content), 3)
        
        # Layer 1: Should have cache_control (Safe fallback)
        self.assertIn("cache_control", system_content[0])
        self.assertEqual(system_content[0]["cache_control"], {"type": "ephemeral"})
        
        # Layer 2: No cache control
        self.assertNotIn("cache_control", system_content[1])
        
        # Verify L2 hash stored
        self.assertIsNotNone(self.context_builder.last_l2_hash)

    def test_smart_caching_stable_memory(self):
        """Test: Second run (L2 unchanged) -> Cache control on L2 (Aggressive caching)."""
        # Run 1: Initialize hash
        self.context_builder.build_messages(
            history=[], current_message="Hi", enable_caching=True
        )
        initial_hash = self.context_builder.last_l2_hash
        
        # Run 2: Memory unchanged
        messages = self.context_builder.build_messages(
            history=[], current_message="Hi", enable_caching=True
        )
        
        system_content = messages[0]["content"]
        
        # Layer 1: No cache control
        self.assertNotIn("cache_control", system_content[0])
        
        # Layer 2: Should have cache_control (Aggressive)
        self.assertIn("cache_control", system_content[1])
        self.assertEqual(system_content[1]["cache_control"], {"type": "ephemeral"})
        
        # Hash should remain same
        self.assertEqual(self.context_builder.last_l2_hash, initial_hash)

    def test_smart_caching_changed_memory(self):
        """Test: Third run (L2 changed) -> Cache control back to L1 (Safe fallback)."""
        # Run 1: Initialize hash
        self.context_builder.build_messages(
            history=[], current_message="Hi", enable_caching=True
        )
        
        # Change memory content
        self.context_builder._get_layer_2_memory.return_value = "# Layer 2: UPDATED Memory"
        
        # Run 2: Memory changed
        messages = self.context_builder.build_messages(
            history=[], current_message="Hi", enable_caching=True
        )
        
        system_content = messages[0]["content"]
        
        # Layer 1: Should have cache_control (Safe fallback)
        self.assertIn("cache_control", system_content[0])
        
        # Layer 2: No cache control
        self.assertNotIn("cache_control", system_content[1])
        
        # Hash should update
        self.assertNotEqual(self.context_builder.last_l2_hash, None)

    def test_build_messages_caching_disabled(self):
        """Test that enable_caching=False produces standard string system prompt."""
        history = []
        current_message = "Hello"
        
        messages = self.context_builder.build_messages(
            history=history,
            current_message=current_message,
            enable_caching=False
        )
        
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIsInstance(system_msg["content"], str)
        self.assertIn("# Layer 1: Static Identity", system_msg["content"])
        self.assertIn("# Layer 2: Memory & Tasks", system_msg["content"])
        self.assertIn("# Layer 3: Dynamic Time", system_msg["content"])

class TestLiteLLMProviderCaching(unittest.TestCase):
    def test_parse_response_with_cached_tokens(self):
        """Test that _parse_response extracts cached_tokens from usage details."""
        provider = LiteLLMProvider(api_key="mock", default_model="mock/model")
        
        # Mock LiteLLM response object
        mock_response = SimpleNamespace()
        mock_response.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content="Response", tool_calls=None),
                finish_reason="stop"
            )
        ]
        
        # Mock usage with prompt_tokens_details
        mock_usage = SimpleNamespace()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150
        
        # Mock details with cached_tokens
        mock_details = SimpleNamespace()
        mock_details.cached_tokens = 80
        mock_usage.prompt_tokens_details = mock_details
        
        mock_response.usage = mock_usage
        
        # Parse
        llm_response = provider._parse_response(mock_response)
        
        # Verify
        self.assertIn("cached_tokens", llm_response.usage)
        self.assertEqual(llm_response.usage["cached_tokens"], 80)
        self.assertEqual(llm_response.usage["prompt_tokens"], 100)

    def test_parse_response_without_cached_tokens(self):
        """Test that _parse_response works when cached_tokens is missing."""
        provider = LiteLLMProvider(api_key="mock", default_model="mock/model")
        
        mock_response = SimpleNamespace()
        mock_response.choices = [
            SimpleNamespace(
                message=SimpleNamespace(content="Response", tool_calls=None),
                finish_reason="stop"
            )
        ]
        
        mock_usage = SimpleNamespace()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150
        # No details
        mock_usage.prompt_tokens_details = None
        
        mock_response.usage = mock_usage
        
        llm_response = provider._parse_response(mock_response)
        
        self.assertNotIn("cached_tokens", llm_response.usage)
        self.assertEqual(llm_response.usage["prompt_tokens"], 100)

if __name__ == '__main__':
    unittest.main()
