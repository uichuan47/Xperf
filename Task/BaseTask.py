import asyncio
import time
from datetime import datetime
from typing import List, Any

class LongTask:
    def __init__(self, task_id: int, duration: float):
        self.task_id = task_id
        self.duration = duration
        self.start_time = None
        self.end_time = None

    async def execute(self) -> str:
        print(f"任务 {self.task_id} 开始执行，耗时 {self.duration} 秒")
        self.start_time = time.time()

        await asyncio.sleep(self.duration)

        self.end_time = time.time()
        elapsed = self.end_time - self.start_time
        print(f"任务 {self.task_id} 完成 耗时 {elapsed:.2f} 秒")
        return f"任务 {self.task_id} 结果"

class PeriodicOperation:
    """定期执行的操作"""

    def __init__(self, interval: float = 0.3):
        self.interval = interval
        self.operation_count = 0
        self.start_time = time.time()
        self.task = None

    async def run(self):
        """运行定期操作"""
        while True:
            self.operation_count += 1
            current_time = time.time()
            elapsed = current_time - self.start_time

            # 执行定期操作（这里只是打印信息）
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')}] "
                  f"定期操作 #{self.operation_count}, 已运行 {elapsed:.2f} 秒")

            # 等待指定的间隔时间
            await asyncio.sleep(self.interval)

    def start(self):
        self.task = asyncio.create_task(self.run())
        return self.task

    def cancel(self):
        if self.task:
            self.task.cancel()