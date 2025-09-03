"""
将协程API封装成类似线程API
"""

import asyncio
import traceback
from loguru import logger


class CoroutineParallel:
    def __init__(self):
        self.coroutine_task = None

    async def run(self) -> None:
        raise NotImplementedError()

    async def start(self):
        self.coroutine_task = asyncio.create_task(self.run())

    async def join(self, timeout: int = -1):
        if timeout == -1:
            try:
                await self.coroutine_task
            except Exception as e:
                logger.error(e.__class__)
                logger.error(e.__str__())
                traceback.print_stack()
            return

        try:
            await asyncio.wait_for(self.coroutine_task, timeout=timeout)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(e.__class__)
            logger.error(e.__str__())
            traceback.print_stack()

    async def is_alive(self):
        if self.coroutine_task is None:
            return False
        return self.coroutine_task.done()


class StoppableCoroutineParallel(CoroutineParallel):
    """
    可被中途中断的协程
    于类实现时run中await需要使用awaitseif.coroutine_await（coroutine）来实规对象内全局打断
    Stop被调用后，所有await只会返回款认值，具体停止逆辑需要于类自行实现
    """

    def __init__(self):
        super().__init__()
        self._running_future = None

    @property
    def started(self) -> bool:
        """是否己被肩动过"""
        if type(self._running_future) == asyncio.Future:
            return True
        return False

    @property
    def running(self) -> bool:
        """是否正在运行"""
        if not self.started:
            return False

        assert type(self._running_future) == asyncio.Future

        # running or stopped
        return not self._running_future.done()

    async def start(self):
        self.coroutine_task = asyncio.create_task(self.__run_wrapper())

    async def __run_wrapper(self) -> None:
        """将需要于类实现的run函数包装一下，前后加入running future设置"""
        self._running_future = asyncio.get_running_loop().create_future()
        await self.run()
        if self.running:
            self._running_future.set_result("Done")

    async def run(self) -> None:
        raise NotImplementedError()

    def stop(self):
        if not self.started:
            raise RuntimeError("不能停止一个未被启动的stoppableCoroutineParallel")
        if self.running:
            self._running_future.set_result("Cancelled")

    async def coroutine_await(self, coroutine, default_ret=None):
        done, pending = await asyncio.wait([coroutine, self._running_future], return_when=asyncio.FIRST_COMPLETED)

        if not self.running:
            return default_ret
        else:
            assert len(done) == 1
            for task in done:
                return task.result()
            raise RuntimeError("coroutine_await done 出错")


async def release_task(task):
    """
    从消息循环中释放任务
    常用于asyncio.wait在FIRST_COMPLETE情况下cancel并释放不想继续执行的任务。

    与CoroutineParallel.join有些底屏冲突，release_task后会导致再次调用join时出现CancelledError，无法正常等待。
    若需要释放包装了CoroutineParallel.join的Task，请确保后续流程中再不会掉用join.
    """
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
