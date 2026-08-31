"""Utility for smooth progress reporting."""
import asyncio
from typing import Callable, Awaitable, Optional

class ProgressReporter:
    """Reports progress smoothly between milestones."""
    
    def __init__(self):
        self.current_progress = 0
        self.current_message = "Initializing..."
    
    async def report(
        self, 
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]], 
        message: str, 
        target_progress: int
    ):
        """Smoothly move from current progress to target progress."""
        if not progress_callback:
            return
            
        start = self.current_progress
        diff = target_progress - start
        
        if diff <= 0:
            await progress_callback(target_progress, message)
            self.current_progress = target_progress
            self.current_message = message
            return
            
        # Move in small increments. Max 10 steps so it doesn't block analysis too long.
        steps = min(diff, 10) 
        step_size = diff / steps
        sleep_time = 0.5 / steps # Total 0.5s per transition animation
        
        for i in range(1, steps + 1):
            new_progress = start + (step_size * i)
            await progress_callback(round(new_progress), message)
            await asyncio.sleep(sleep_time)
            
        self.current_progress = target_progress
        self.current_message = message
