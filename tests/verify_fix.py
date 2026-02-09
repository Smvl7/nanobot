
import asyncio
import os
import shutil
import uuid
from pathlib import Path

# --- Test LiteLLMProvider Fallback Logic ---
def test_litellm_fallback_resolution():
    print("Testing LiteLLMProvider fallback resolution...")
    
    # Simulate OpenRouter environment
    api_key = "sk-or-test-key"
    
    # Import provider (it will use the registry)
    from nanobot.providers.litellm_provider import LiteLLMProvider
    
    # Initialize provider with OpenRouter key
    provider = LiteLLMProvider(api_key=api_key)
    
    # Verify gateway detection
    assert provider._gateway is not None
    assert provider._gateway.name == "openrouter"
    print("  Gateway detected: OpenRouter")
    
    # Test resolution of the fallback model name
    fallback_model_name = "anthropic/claude-sonnet-4.5"
    resolved_model = provider._resolve_model(fallback_model_name)
    
    # Expectation: openrouter/anthropic/claude-sonnet-4.5
    expected = "openrouter/anthropic/claude-sonnet-4.5"
    
    if resolved_model == expected:
        print(f"  [PASS] Resolved model: {resolved_model}")
    else:
        print(f"  [FAIL] Expected {expected}, got {resolved_model}")
        exit(1)

# --- Test Cron Tool Echo Mode ---
async def test_cron_tool_echo_default():
    print("\nTesting CronTool echo default...")
    
    from nanobot.cron.service import CronService
    from nanobot.agent.tools.cron import CronTool
    
    # Setup temp store
    temp_dir = Path(f"temp_test_{uuid.uuid4()}")
    temp_dir.mkdir()
    store_path = temp_dir / "jobs.json"
    
    try:
        service = CronService(store_path)
        tool = CronTool(service)
        tool.set_context(channel="cli", chat_id="test_user")
        
        # Add job without specifying type
        result = await tool.execute(action="add", message="Remind me")
        print(f"  Tool result: {result}")
        
        # Verify job in service
        jobs = service.list_jobs(include_disabled=True)
        assert len(jobs) == 1
        job = jobs[0]
        
        if job.payload.kind == "echo":
            print(f"  [PASS] Job kind is '{job.payload.kind}'")
        else:
            print(f"  [FAIL] Job kind is '{job.payload.kind}', expected 'echo'")
            exit(1)
            
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_litellm_fallback_resolution()
    asyncio.run(test_cron_tool_echo_default())
