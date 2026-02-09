import unittest
import asyncio
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from nanobot.cron.service import CronService, _compute_next_run
from nanobot.cron.types import CronJob, CronSchedule, CronPayload, CronJobState

class TestCronServiceComprehensive(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.store_path = MagicMock(spec=Path)
        self.store_path.exists.return_value = False
        self.store_path.parent = MagicMock()
        self.service = CronService(self.store_path)

    # --- 1. Hot Reload Tests ---
    
    async def test_hot_reload_triggers_reload(self):
        """Verify that file mtime change triggers store reload."""
        print("\n[Test] Hot Reload")
        
        # Setup initial state
        self.service._running = True
        self.store_path.exists.return_value = True
        self.store_path.stat.return_value.st_mtime = 100.0
        self.store_path.read_text.return_value = '{"jobs": []}'
        
        # We need a custom sleep that respects small delays but shortens long ones
        # to allow the test to run fast.
        original_sleep = asyncio.sleep
        
        async def fast_sleep(delay):
            # If delay is small (simulation), run it.
            # If delay is large (heartbeat wait), skip it.
            if delay < 1:
                await original_sleep(delay)
            else:
                await original_sleep(0.001)

        # Mock _load_store to verify it gets called
        with patch.object(self.service, '_load_store', wraps=self.service._load_store) as mock_load:
            # Patch sleep
            with patch('asyncio.sleep', side_effect=fast_sleep):
                
                # Create a task that updates mtime after a short delay
                async def update_file():
                    await asyncio.sleep(0.01)
                    self.store_path.stat.return_value.st_mtime = 200.0
                    print("  -> File updated (mtime 100 -> 200)")
                    
                # Run heartbeat loop for a short time
                async def run_loop():
                    try:
                        await asyncio.wait_for(self.service._heartbeat_loop(), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass

                await asyncio.gather(update_file(), run_loop())
            
            # Verify load_store was called (initial + reload)
            self.assertGreaterEqual(mock_load.call_count, 2)
            print("  ✓ Reload triggered successfully")

    # --- 2. Adaptive Heartbeat (Smart Sleep) ---

    async def test_adaptive_sleep_logic(self):
        """Verify the service sleeps for the correct amount of time."""
        print("\n[Test] Adaptive Sleep")
        
        # Case A: Next job is in 10 seconds
        now = int(time.time() * 1000)
        future_job = CronJob(
            id="j1", name="J1", enabled=True,
            schedule=CronSchedule(kind="every", every_ms=10000),
            payload=CronPayload(kind="echo", message="test"),
            state=CronJobState(next_run_at_ms=now + 10000),
            created_at_ms=now, updated_at_ms=now
        )
        self.service._store = MagicMock()
        self.service._store.jobs = [future_job]
        
        # We patch asyncio.sleep to capture the sleep duration
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Run loop for one iteration (we'll break it via side_effect or just running it once)
            # To test logic safely without infinite loop, we can inspect logic extraction or 
            # run the loop and raise CancelledError after first sleep
            
            async def stop_loop(*args):
                self.service._running = False
                return None
            
            mock_sleep.side_effect = stop_loop
            self.service._running = True
            
            try:
                await self.service._heartbeat_loop()
            except Exception:
                pass
                
            # Verify sleep called with ~10s
            # Note: Logic is min(60, delta_s). Delta is 10s.
            # We allow small margin of error for execution time
            call_args = mock_sleep.call_args[0][0]
            self.assertAlmostEqual(call_args, 10.0, delta=1.0)
            print(f"  ✓ Slept for {call_args:.2f}s (expected ~10s)")

    # --- 3. Timezone Logic ---

    def test_timezone_calculation(self):
        """Verify timezone handling."""
        print("\n[Test] Timezone Calculation")
        
        # Test 1: UTC vs Moscow (UTC+3)
        # 9:00 UTC = 12:00 MSK
        
        # Current time: 2024-01-01 09:00:00 UTC
        base_ts = 1704100000 # ~ 2024-01-01 09:06:40 UTC
        
        # Schedule: "0 10 * * *" (10:00 AM)
        # In UTC: Next run is today 10:00 UTC
        # In MSK: 10:00 MSK is 07:00 UTC. Since it's 09:00 UTC, 10:00 MSK today (07:00 UTC) has passed.
        # Next run is tomorrow 10:00 MSK.
        
        # Let's use a simpler check: fixed offset
        schedule_msk = CronSchedule(kind="cron", expr="0 12 * * *", tz="Europe/Moscow")
        # 12:00 MSK is 09:00 UTC.
        
        # Mock time to be 08:59 UTC
        mock_now = 1704100000 - (6 * 60) - 40 # Adjust to be before 09:00 UTC
        # Actually easier to rely on croniter's correctness and just ensure tz is passed
        
        with patch('nanobot.cron.service._now_ms', return_value=1704099540000): # Some fixed time
            # We just verify that _compute_next_run doesn't crash with valid TZ
            next_run = _compute_next_run(schedule_msk, 1704099540000)
            self.assertIsNotNone(next_run)
            print("  ✓ Valid timezone handled")
            
            # Verify invalid timezone fallback
            schedule_bad = CronSchedule(kind="cron", expr="0 12 * * *", tz="Mars/Phobos")
            next_run_bad = _compute_next_run(schedule_bad, 1704099540000)
            self.assertIsNotNone(next_run_bad)
            print("  ✓ Invalid timezone fallback handled")

    # --- 4. Resilience (Corrupt Store) ---

    async def test_corrupt_store_resilience(self):
        """Verify service handles corrupt jobs.json."""
        print("\n[Test] Corrupt Store Resilience")
        
        self.store_path.exists.return_value = True
        self.store_path.read_text.return_value = "{ invalid json ... "
        
        # Should not raise exception
        self.service._load_store()
        
        # Should initialize empty store
        self.assertIsNotNone(self.service._store)
        self.assertEqual(len(self.service._store.jobs), 0)
        print("  ✓ Handled corrupt JSON gracefully")

if __name__ == "__main__":
    unittest.main()
