import asyncio
import time
from datetime import datetime
from typing import List, Any
from Task.BaseTask import LongTask,PeriodicOperation

class TaskRunner:

    def __init__(self):
        self.tasks: List[LongTask] = []
        self.results: List[Any] = []

    def add_task(self, task_id: int, duration: float,action):
        self.tasks.append(LongTask(task_id, duration,action))

    async def run_sequential(self):
        self.results = []
        for task in self.tasks:
            result = await task.execute()
            self.results.append(result)
        return self.results


async def main():
    runner = TaskRunner()
    from Task.EnergyTestTask import EnergyTestTask
    runner.add_task(1, 5,EnergyTestTask.start_game)
    runner.add_task(2, 1,EnergyTestTask.nocar)
    runner.add_task(3, 1,EnergyTestTask.nonpc)
    runner.add_task(4, 1,EnergyTestTask.cmd_3)
    runner.add_task(4, 1,EnergyTestTask.start_power_record)

    # Tick operation
    periodic_op = PeriodicOperation(0.3)
    periodic_task = periodic_op.start()

    try:
        # 顺序执行所有任务
        results = await runner.run_sequential()
    finally:
        # cancel tick
        periodic_op.cancel()
        try:
            await periodic_task
        except asyncio.CancelledError:
            print("stop tick")


if __name__ == "__main__":
    asyncio.run(main())