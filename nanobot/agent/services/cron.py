import time
import os
import json
import logging
from croniter import croniter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class CronService:
    def __init__(self, agent):
        self.agent = agent
        self.cron_file = os.path.join(self.agent.workspace, "cron/jobs.json")
        self.jobs = []
        self.last_mtime = 0
        self.load_jobs()

    def load_jobs(self):
        """Load jobs from the JSON file."""
        if not os.path.exists(self.cron_file):
            self.jobs = []
            return

        try:
            # Update last known modification time
            self.last_mtime = os.path.getmtime(self.cron_file)
            
            with open(self.cron_file, "r") as f:
                self.jobs = json.load(f)
            logger.info(f"Loaded {len(self.jobs)} cron jobs")
        except Exception as e:
            logger.error(f"Failed to load cron jobs: {e}")
            self.jobs = []

    def start(self):
        """Start the cron scheduler loop."""
        logger.info("Starting CronService...")
        while True:
            try:
                self._check_reload()
                self._check_schedule()
            except Exception as e:
                logger.error(f"Error in cron loop: {e}")
            
            # Sleep for 60 seconds to check every minute
            time.sleep(60)

    def _check_reload(self):
        """Check if jobs file has changed and reload if needed."""
        if not os.path.exists(self.cron_file):
            return

        try:
            current_mtime = os.path.getmtime(self.cron_file)
            if current_mtime > self.last_mtime:
                logger.info("Cron file changed, reloading jobs...")
                self.load_jobs()
        except Exception as e:
            logger.error(f"Error checking reload: {e}")

    def _check_schedule(self):
        """Check if any jobs are due."""
        now = datetime.now(timezone.utc)
        
        for job in self.jobs:
            try:
                if self._is_due(job, now):
                    self._execute_job(job)
            except Exception as e:
                logger.error(f"Error checking job {job.get('name')}: {e}")

    def _is_due(self, job, now):
        """Check if a specific job is due."""
        # Handle one-time jobs (at specific time)
        if "at" in job:
            job_time = datetime.fromisoformat(job["at"])
            if job_time.tzinfo is None:
                job_time = job_time.replace(tzinfo=timezone.utc)
            
            # Check if time has passed (within last minute)
            diff = (now - job_time).total_seconds()
            return 0 <= diff < 60

        # Handle recurring jobs (cron expression)
        if "cron" in job:
            iter = croniter(job["cron"], now)
            prev = iter.get_prev(datetime)
            diff = (now - prev).total_seconds()
            return 0 <= diff < 60

        # Handle interval jobs (every X seconds)
        if "every" in job:
            # This requires tracking last run time, which is complex without persistence
            # For now, simplistic check based on current timestamp
            return int(now.timestamp()) % int(job["every"]) < 60

        return False

    def _execute_job(self, job):
        """Execute a job."""
        logger.info(f"Executing job: {job.get('name')}")
        
        # Send message if configured
        if "message" in job:
            content = job["message"]
            # Default to current channel if not specified
            channel = job.get("channel", "telegram") 
            chat_id = job.get("chat_id")
            
            if chat_id:
                self.agent.message(content, channel=channel, chat_id=chat_id)
            else:
                logger.warning(f"Job {job.get('name')} has message but no chat_id")

        # Execute command if configured
        if "command" in job:
            self.agent.exec(job["command"])
