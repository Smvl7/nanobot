import hashlib
import json
from typing import Any

from loguru import logger


class LoopDetectedError(Exception):
    """Raised when the agent is detected to be in a loop."""
    pass


class LoopDetector:
    """
    Detects loops in agent interactions to prevent infinite repetition.
    
    Checks for:
    1. Repeated tool calls (same name and arguments).
    2. Repeated identical text responses.
    """
    
    def __init__(self, max_repeats: int = 3, history_size: int = 10):
        self.max_repeats = max_repeats
        self.history_size = history_size
        self.tool_history: list[str] = []
        self.content_history: list[str] = []
        
    def add_interaction(self, content: str | None, tool_calls: list[dict[str, Any]] | None) -> None:
        """
        Record an interaction and check for loops.
        
        Args:
            content: The text content of the response.
            tool_calls: List of tool calls (dictionaries).
            
        Raises:
            LoopDetectedError: If a loop is detected.
        """
        # Check text content loop
        if content and not tool_calls:
            # Only check content if there are no tool calls (pure text response)
            # Because often text is just "I will now do X" which might repeat but with different tools
            # But if it's just text, it shouldn't repeat identically.
            content_hash = self._hash_content(content)
            self.content_history.append(content_hash)
            if len(self.content_history) > self.history_size:
                self.content_history.pop(0)
            
            if self._count_repeats(self.content_history) >= self.max_repeats:
                logger.warning("Loop detected: Identical text response repeated.")
                raise LoopDetectedError("Repeated text response detected.")
        else:
            # Reset content history if we did something else (like a tool call)
            # actually, maybe not reset, but we don't count it towards the streak
            # Simplest: just append a "non-match" or clear?
            # Let's just append None or similar to break the streak
            self.content_history.append("action") 

        # Check tool calls loop
        if tool_calls:
            # Create a deterministic hash of all tool calls in this turn
            tool_hash = self._hash_tool_calls(tool_calls)
            self.tool_history.append(tool_hash)
            if len(self.tool_history) > self.history_size:
                self.tool_history.pop(0)
                
            if self._count_repeats(self.tool_history) >= self.max_repeats:
                logger.warning("Loop detected: Identical tool calls repeated.")
                raise LoopDetectedError("Repeated tool calls detected.")
        else:
            self.tool_history.append("no_tools")
    
    def _hash_content(self, content: str) -> str:
        """Create a hash of the text content."""
        return hashlib.md5(content.strip().encode()).hexdigest()
    
    def _hash_tool_calls(self, tool_calls: list[dict[str, Any]]) -> str:
        """Create a deterministic hash of tool calls."""
        # Normalize tool calls for hashing
        normalized = []
        for tc in tool_calls:
            # We assume structure is consistent with internal representation
            # We care about function name and arguments
            func = tc.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", "")
            
            # Arguments might be a JSON string or dict, ensure consistent string
            if isinstance(args, str):
                try:
                    # Parse and re-dump to ensure consistent formatting
                    args_obj = json.loads(args)
                    args_str = json.dumps(args_obj, sort_keys=True)
                except json.JSONDecodeError:
                    args_str = args
            else:
                args_str = json.dumps(args, sort_keys=True)
                
            normalized.append(f"{name}:{args_str}")
            
        # Sort to handle order independence if needed (though usually order matters in execution)
        # But here we treat the SET of tools in one turn as the "action"
        normalized.sort()
        return hashlib.md5("|".join(normalized).encode()).hexdigest()

    def _count_repeats(self, history: list[str]) -> int:
        """Count how many times the latest item appears consecutively at the end."""
        if not history:
            return 0
            
        last_item = history[-1]
        
        # If the last item is a placeholder (like "action" or "no_tools"), ignore it
        if last_item in ["action", "no_tools"]:
            return 0
            
        count = 0
        for i in range(len(history) - 1, -1, -1):
            if history[i] == last_item:
                count += 1
            else:
                break
        return count
