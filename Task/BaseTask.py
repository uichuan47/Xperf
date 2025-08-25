import asyncio
import time
from datetime import datetime
from loguru import logger
from typing import List, Any

class LongTask:
    def __init__(self, task_id: int, duration: float):
        self.task_id = task_id
        self.duration = duration
        self.start_time = None
        self.end_time = None

    async def execute(self) -> str:
        print(f"task {self.task_id} begin duration {self.duration} seconds")
        await asyncio.sleep(self.duration)
        return f"task{self.task_id} done"

class PeriodicOperation:

    def __init__(self, interval: float = 0.3):
        self.interval = interval
        self.operation_count = 0
        self.start_time = time.time()
        self.task = None

    async def run(self):
        while True:
            current_time = time.time()
            elapsed = current_time - self.start_time
            logger.info(f"elapsed_time:{elapsed:.2f}")
            await asyncio.sleep(self.interval)

    def start(self):
        self.task = asyncio.create_task(self.run())
        return self.task

    def cancel(self):
        if self.task:
            self.task.cancel()