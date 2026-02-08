"""Cron tool for scheduling reminders and tasks."""

from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return "Schedule tasks. Use 'echo' type for simple text reminders (sent directly to chat). Use 'agent' type for tasks requiring tool use or reasoning (e.g. 'check weather'). Actions: add, list, remove."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform"
                },
                "type": {
                    "type": "string",
                    "enum": ["echo", "agent"],
                    "description": "Job type: 'echo' for reminders (loudspeaker), 'agent' for tasks. Defaults to 'echo'."
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message (for add)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for scheduled tasks)"
                },
                "at": {
                    "type": "string",
                    "description": "ISO 8601 timestamp for one-time task (e.g., '2023-10-27T10:00:00')"
                },
                "timezone": {
                    "type": "string",
                    "description": "User timezone (e.g., 'Europe/Moscow'). MANDATORY if not UTC."
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        at: str | None = None,
        timezone: str | None = None,
        job_id: str | None = None,
        type: str = "echo",
        **kwargs: Any
    ) -> str:
        if action == "add":
            return self._add_job(message, every_seconds, cron_expr, at, timezone, type)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"
    
    def _add_job(
        self, 
        message: str, 
        every_seconds: int | None, 
        cron_expr: str | None,
        at: str | None,
        timezone: str | None,
        type: str = "echo"
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        
        # Build schedule
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr, tz=timezone)
        elif at:
            try:
                import datetime
                from zoneinfo import ZoneInfo
                
                # Parse ISO string
                dt = datetime.datetime.fromisoformat(at)
                
                # Handle timezone if provided and dt is naive
                if timezone and (dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None):
                    tz = ZoneInfo(timezone)
                    dt = dt.replace(tzinfo=tz)
                
                # Convert to UTC timestamp
                at_ms = int(dt.timestamp() * 1000)
                schedule = CronSchedule(kind="at", at_ms=at_ms, tz=timezone)
            except Exception as e:
                return f"Error parsing time: {e}"
        else:
            return "Error: either every_seconds, cron_expr, or at is required"
        
        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            kind=type,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
        )
        return f"Created job '{job.name}' (id: {job.id})"
    
    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, schedule: {j.schedule.kind}, type: {j.payload.kind})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
