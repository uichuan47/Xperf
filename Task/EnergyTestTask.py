from loguru import logger
import asyncio
import subprocess
import threading
from electricity.power import KA3003PPower
from electricity.power_recorder import PowerRecorder,save_data_to_excel
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

    @classmethod
    async def start_power_record(cls):
        # 初始化功耗记录器
        recorder = PowerRecorder(KA3003PPower.get_all_connected_power()[0])

        # 开启功耗打点
        await recorder.start_record(0.3)
        await asyncio.sleep(180)
        await recorder.stop_record()

        record = recorder.get_data(1.0)
        logger.debug(record)

        # save_data_to_excel(record["data"], './casino-r.Mobile.AntiAliasing1.xlsx')
        save_data_to_excel(record["data"], '/Users/kento/Documents/Scripts/Xperf/Task/data_0715/s22-0714-venice-distance_scale-05-round-1.xlsx')
