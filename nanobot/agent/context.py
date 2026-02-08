"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """
    
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
        self.last_l2_hash: str | None = None
    
    def _get_layer_1_static(self, skill_names: list[str] | None = None) -> str:
        """
        Build Layer 1: Immutable Static Context.
        Includes: Identity, Bootstrap Files, Sorted Skills.
        """
        parts = []
        
        # Core identity
        parts.append(self._get_static_identity())
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Skills (Sorted in SkillsLoader)
        # 1. Always-loaded skills
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills summary
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)

    def _get_static_identity(self) -> str:
        """Get the core identity section (static part)."""
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        
        return f"""# nanobot 🐈

You are nanobot, a helpful AI assistant. You have access to tools that allow you to:
- Read, write, and edit files
- Execute shell commands
- Search the web and fetch web pages
- Send messages to users on chat channels
- Spawn subagents for complex background tasks

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## System Architecture
- Source Code: /usr/local/lib/python3.12/site-packages/nanobot/
- Config: /root/.nanobot/config.json

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp).
For normal conversation, just respond with text - do not call the message tool.

Always be helpful, accurate, and concise. When using tools, explain what you're doing.
When remembering something, write to {workspace_path}/memory/MEMORY.md"""

    def _get_layer_2_memory(self) -> str:
        """
        Build Layer 2: Semi-Mutable Context.
        Includes: Memory (Long-term + Daily), Heartbeat Tasks.
        """
        parts = []
        
        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        # Heartbeat Tasks
        heartbeat_file = self.workspace / "HEARTBEAT.md"
        if heartbeat_file.exists():
            content = heartbeat_file.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"# Pending Tasks (Heartbeat)\n\n{content}")
        
        return "\n\n---\n\n".join(parts)

    def _get_layer_3_dynamic(self, channel: str | None = None, chat_id: str | None = None) -> str:
        """
        Build Layer 3: Highly Mutable Context.
        Includes: Time, Session Info.
        """
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        
        parts = [f"## Current Time\n{now}"]
        
        if channel and chat_id:
            parts.append(f"## Current Session\nChannel: {channel}\nChat ID: {chat_id}")
            
        return "\n\n".join(parts)
    
    # Deprecated methods mapping to new structure
    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """Legacy wrapper for static layer (Layer 1)."""
        return self._get_layer_1_static(skill_names)

    def _get_dynamic_identity(self, channel: str | None = None, chat_id: str | None = None) -> str:
        """Legacy wrapper for dynamic layer (Layer 3)."""
        return self._get_layer_3_dynamic(channel, chat_id)


    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        enable_caching: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.
            enable_caching: Whether to enable prompt caching (e.g. for Gemini).

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt parts
        import hashlib
        
        # Layer 1: Static (Always base)
        layer_1 = self._get_layer_1_static(skill_names)
        
        # Layer 2: Semi-Mutable (Memory + Tasks)
        layer_2 = self._get_layer_2_memory()
        
        # Layer 3: Dynamic (Time + Session)
        layer_3 = self._get_layer_3_dynamic(channel, chat_id)
        
        if enable_caching:
            # Smart Caching Logic
            # Check if Layer 2 has changed since last request
            current_l2_hash = hashlib.md5(layer_2.encode()).hexdigest()
            l2_unchanged = self.last_l2_hash == current_l2_hash
            
            # Update hash for next time
            self.last_l2_hash = current_l2_hash
            
            if l2_unchanged:
                # OPTION A: Aggressive Caching (L1 + L2)
                # If L2 is stable, we cache everything up to end of L2.
                messages.append({
                    "role": "system", 
                    "content": [
                        {
                            "type": "text", 
                            "text": layer_1
                        },
                        {
                            "type": "text",
                            "text": layer_2,
                            "cache_control": {"type": "ephemeral"} # Cache boundary here
                        },
                        {
                            "type": "text",
                            "text": layer_3
                        }
                    ]
                })
            else:
                # OPTION B: Safe Caching (L1 Only)
                # If L2 changed, we only cache L1 to ensure high hit rate for the heavy part.
                messages.append({
                    "role": "system", 
                    "content": [
                        {
                            "type": "text", 
                            "text": layer_1,
                            "cache_control": {"type": "ephemeral"} # Cache boundary here
                        },
                        {
                            "type": "text",
                            "text": layer_2
                        },
                        {
                            "type": "text",
                            "text": layer_3
                        }
                    ]
                })
        else:
            # Concatenate for standard providers
            full_prompt = f"{layer_1}\n\n{layer_2}\n\n{layer_3}"
            messages.append({"role": "system", "content": full_prompt})

        # History
        messages.extend(history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text
        
        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        
        if not images:
            return text
        return images + [{"type": "text", "text": text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        messages.append(msg)
        return messages
