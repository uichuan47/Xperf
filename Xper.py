import asyncio
import time
from datetime import datetime


async def long_task(task_id, duration):
    """耗时任务"""
    print(f"任务 {task_id} 开始执行，耗时 {duration} 秒")
    start_time = time.time()

    # 模拟任务执行（使用 asyncio.sleep 而不是 time.sleep）
    await asyncio.sleep(duration)

    end_time = time.time()
    print(f"任务 {task_id} 完成 耗时 {end_time - start_time:.2f} 秒")
    return f"任务 {task_id} 结果"


async def periodic_operation(interval=0.3):
    start_time = time.time()
    operation_count = 0

    while True:
        operation_count += 1
        current_time = time.time()
        elapsed = current_time - start_time

        # 执行定期操作（这里只是打印信息）
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')}] "
              f"定期操作 #{operation_count}, 已运行 {elapsed:.2f} 秒")

        # 等待指定的间隔时间
        await asyncio.sleep(interval)


async def run_sequential_tasks():
    results = []
    results.append(await long_task(1, 5))
    results.append(await long_task(2, 10))
    results.append(await long_task(3, 15))
    return results


async def main():
    # Tick Task
    periodic_task = asyncio.create_task(periodic_operation(0.3))

    try:
        results = await run_sequential_tasks()
        print(results)
    finally:
        periodic_task.cancel()
        try:
            await periodic_task
        except asyncio.CancelledError:
            print("定期操作已停止")


if __name__ == "__main__":
    asyncio.run(main())