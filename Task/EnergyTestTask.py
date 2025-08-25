from loguru import logger
import asyncio
import subprocess
import threading
class EnergyTestTask():
    @classmethod
    async def start_game(cls):
        """打开Android应用"""
        # 构造启动应用的ADB命令
        cmd = f"adb shell am start -n com.yottagames.nsgame/com.epicgames.unreal.SplashActivity"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"成功启动应用")
            else:
                print(f"启动应用失败: {result.stderr}")
        except Exception as e:
            print(f"执行命令出错: {e}")
        logger.info(f"Starting game")

    @classmethod
    async def nocar(cls):
        cmd = r"""
        adb shell "am broadcast -a android.intent.action.RUN -e cmd 'ns.ai.debug.nocar'"
        """
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"success")
            else:
                print(f"fail: {result.stderr}")
        except Exception as e:
            print(f"执行命令出错: {e}")
        logger.info(f"cmd1")

    @classmethod
    async def nonpc(cls):
        cmd = r"""
                adb shell "am broadcast -a android.intent.action.RUN -e cmd 'ns.ai.debug.nonpc'"
                """
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"success")
            else:
                print(f"fail: {result.stderr}")
        except Exception as e:
            print(f"执行命令出错: {e}")
        logger.info(f"cmd2")

    @classmethod
    async def cmd_3(cls):
        cmd = r"""
            adb shell "am broadcast -a android.intent.action.RUN -e cmd 'showflag.postprocessing 0'"
            """
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"success")
            else:
                print(f"fail: {result.stderr}")
        except Exception as e:
            print(f"执行命令出错: {e}")
        logger.info(f"cmd2")