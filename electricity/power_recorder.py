"""
功耗录制器
"""

import asyncio
import datetime
import time
from loguru import logger
from base.coroutine_parallel import CoroutineParallel
from electricity.power import KA3003PPower
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import socket


class PowerRecorder(CoroutineParallel):
    __power_recorder_instances = {}

    def __init__(self, power: KA3003PPower, sample_interval_second:float = 1.0):
        """
        sample_interval_second为对电源的原始采样间陷，最低建议不小于0.1
        """

        super().__init__()
        self.power = power
        self.sample_interval_second = sample_interval_second
        self.running = False
        self.power_data = {
            "voltage": self.power.FIXED_POWER_VOLTAGE,
            "data":[]
        }

        PowerRecorder.__power_recorder_instances[self.power.serial_number] = self
        self.on_new_data_callback = set()

    async def run(self) -> None:
        self.running = True
        async with self.power:
            if self.sample_interval_second <= 0.1:
                logger.warning("电源功耗获取时间间隔设过短，可能会导致中途漏点".format(self.power.serial_number))
            next_record_time = datetime.datetime.now().timestamp()

            while self.running:
                # 打点时间间隔为interval值，若压力过高则允许漏点但间隔固定
                current_time = datetime.datetime.now().timestamp()
                await asyncio.sleep(next_record_time - current_time)

                current_record_time = datetime.datetime.now().timestamp()
                next_record_time = next_record_time + self.sample_interval_second
                while next_record_time <= current_record_time:
                    next_record_time = next_record_time + self.sample_interval_second

                current = await self.power.get_current_in_practice()
                self.power_data["data"].append({
                    "time": current_record_time,
                    "current": current,
                })

                logger.debug({
                    "time": current_record_time,
                    "current": current
                })
                for callback_func in self.on_new_data_callback:
                    callback_func(current_record_time, self.power.FIXED_POWER_VOLTAGE, current)

    def get_data(self, statistic_interval: float = -1):
        if statistic_interval == -1 or len(self.power_data["data"]) == 0:
            return self.power_data
        return self.get_statistic_data(statistic_interval)

    def get_statistic_data(self, statistic_interval: float = 1.0):
        """
            对原始采样点进行统计，按interval指定的间隔生成平均点数据。
            使用短原始采样点 + 长统计采样点的方式，一定程度上可以避免数据跳变产生的影响。
        """
        if len(self.power_data["data"]) == 0:
            return self.power_data

        result = {
            "voltage": self.power.FIXED_POWER_VOLTAGE,
            "data": []
        }

        # 扫描原始数据，以statistic_interval为间隔统计每个间隔区间中的电流平均值
        statistic_start_time = self.power_data["data"][0]["time"]
        temp_data = []
        for index, point in enumerate(self.power_data["data"]):
            if point["time"] < statistic_start_time + statistic_interval:
                temp_data.append(point)
            else:
                average_current = sum([data["current"] for data in temp_data]) / len(temp_data)
                result["data"].append({
                    "time": statistic_start_time,
                    "current": average_current
                })
                statistic_start_time += statistic_interval
                temp_data = [point]
        if len(temp_data) > 0:
            average_current = round(sum([data["current"] for data in temp_data]) / len(temp_data), 3)
            result["data"].append({
                "time": statistic_start_time,
                "current": average_current
            })
            statistic_start_time += statistic_interval
        return result


    async def start_record(self, interval_second: float = 1.0):
        self.sample_interval_second = interval_second
        logger.debug("start_record_power")
        await self.start()

    async def stop_record(self):
        logger.debug("stop_record_power")
        self.running = False
        await self.join()
        logger.info("Power record stopped")
        return self.power_data

    def clear_current_data(self):
        """清空当前电流数据"""
        logger.debug("请空当前电流数据")
        self.power_data["data"] = []

    def add_on_new_data_callback(self, callback_func):
        self.on_new_data_callback.add(callback_func)

    def delete_on_nen_data_caztback(self,callback_func):
        self.on_new_data_callback.remove(callback_func)

    @staticmethod
    def get_power_record_by_power_id(power_id:str):
        return PowerRecorder.__power_recorder_instances.get(power_id, None)


def send_data_to_ue(data):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_address = ('192.168.148.180', 27779)
    client_socket.connect(server_address)

    try:
        client_socket.sendall(data.encode('utf-8'))

        response = client_socket.recv(1024)
        print(f"recive : {response.decode('utf-8')}")

    finally:
        client_socket.close()

def save_data_to_excel(data_list, file_path):
    # 将数据转换为 pandas DataFrame
    df = pd.DataFrame(data_list)

    # 保存数据到 Excel 文件
    df.to_excel(file_path, index=False)

    # # 生成可视化图表
    # plt.figure(figsize=(10, 6))
    # sns.set(style="whitegrid")
    #
    # # 画出电流值随时间变化的折线图
    # sns.lineplot(x='time', y='current', hue='tag', data=df, marker='o')
    #
    # # 设置图表标题和标签
    # plt.title('Current Over Time')
    # plt.xlabel('Time')
    # plt.ylabel('Current (A)')
    # plt.legend(title='Tag', loc='upper left')
    #
    # # 保存图表到 Excel 文件的同一个目录中
    # chart_path = file_path.replace('.xlsx', '_chart.png')
    # plt.savefig(chart_path)
    #
    # plt.show()


async def a_main():
    recorder = PowerRecorder(KA3003PPower.get_all_connected_power()[0])
    await recorder.start_record(0.3)
    await asyncio.sleep(3)
    await recorder.stop_record()
    logger.debug(recorder.get_data(1.0))


async def power_test():
    # 初始化功耗记录器
    recorder = PowerRecorder(KA3003PPower.get_all_connected_power()[0])

    # 开启功耗打点
    await recorder.start_record(0.3)

    # 与客户端建立一个tcp长连接
    # client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # server_address = ('192.168.148.180', 27777)
    # client_socket.connect(server_address)
    #
    # # 发起任务
    #
    #
    # # 测试过程需要保证与客户端的长连接，直到收到停止游戏的消息
    # while True:
    #     response = client_socket.recv(1024)
    #     if response:
    #         response_data = response.decode('utf-8')
    #         if response_data == "autotest_end":
    #             break
    #         else:
    #             logger.debug(f"recive power tag : {response_data}")
    #
    # logger.debug("power test end")

    await asyncio.sleep(180)
    await recorder.stop_record()

    record = recorder.get_data(1.0)
    logger.debug(record)

    # save_data_to_excel(record["data"], './casino-r.Mobile.AntiAliasing1.xlsx')
    save_data_to_excel(record["data"], 'data_0715/s22-0714-venice-distance_scale-05-round-1.xlsx')

if __name__ == '__main__':
    asyncio.run(power_test())
