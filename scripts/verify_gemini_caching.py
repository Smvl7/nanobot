import asyncio
import sys
import os
import json
from pathlib import Path

# Add project root to path (assuming script is in scripts/)
sys.path.append(str(Path(__file__).parent.parent))

from nanobot.config.loader import load_config
from nanobot.providers.litellm_provider import LiteLLMProvider

async def main():
    print("🐈 Verifying Gemini Caching via Nanobot Provider...")
    
    # Load config (optional, can use env var)
    try:
        config = load_config()
        print("✓ Config loaded")
    except Exception as e:
        print(f"⚠️ Failed to load config: {e}")
        config = None

    # Get API Key from Env or Config
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and config and config.providers.openrouter.api_key:
        api_key = config.providers.openrouter.api_key

    if not api_key:
        print("❌ No OpenRouter API key found (env: OPENROUTER_API_KEY or config).")
        return

    # Initialize provider
    model_name = "openrouter/google/gemini-3-pro-preview"
    print(f"✓ Initializing provider for model: {model_name}")
    
    provider = LiteLLMProvider(
        api_key=api_key,
        default_model=model_name
    )
    
    # Generate large context (~5000 tokens) to guarantee cache eligibility
    print("📦 Generating large context (~5000 tokens)...")
    large_text = "This is a test sentence to fill up the context window. " * 4000
    
    # Construct system prompt with cache_control
    # This matches the structure in nanobot/agent/context.py
    system_prompt = [
        {
            "type": "text",
            "text": "You are a helpful assistant.",
        },
        {
            "type": "text",
            "text": f"Here is some background information:\n{large_text}",
            "cache_control": {"type": "ephemeral"}
        }
    ]
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "What is the background information about? Reply with 1 sentence."}
    ]
    
    # Request 1: Cache Write
    print("\n🚀 Sending Request 1 (Cache Write)...")
    try:
        resp1 = await provider.chat(messages=messages, model=model_name)
        print(f"Response: {resp1.content}")
        print(f"Usage: {json.dumps(resp1.usage, indent=2)}")
        
        # Check if we are hitting Google Vertex
        # Note: We can't easily check provider from LiteLLM response unless we enabled verbose logs
        # but the registry override should be in effect.
        
    except Exception as e:
        print(f"❌ Request 1 failed: {e}")
        return

    # Request 2: Cache Read
    print("\n🚀 Sending Request 2 (Cache Read)...")
    try:
        resp2 = await provider.chat(messages=messages, model=model_name)
        print(f"Response: {resp2.content}")
        print(f"Usage: {json.dumps(resp2.usage, indent=2)}")
        
        # Verification
        cached = resp2.usage.get("cached_tokens", 0)
        
        if cached > 0:
            print(f"\n✅ SUCCESS: Caching works! ({cached} tokens cached)")
            print("Note: If 'cached_tokens' matches the prompt size of Request 1, it's a perfect hit.")
        else:
            print(f"\n⚠️ WARNING: No cached tokens reported in Request 2.")
            print("Possible reasons: Provider didn't cache, TTL expired (unlikely), or routing changed.")
            
    except Exception as e:
        print(f"❌ Request 2 failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
