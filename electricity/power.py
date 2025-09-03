"""
可编程电源
"""

import asyncio
import functools
import glob
import re
import time
import platform
import aioserial
import serial
from loguru import logger
import common
from base.thread_safe_exclusive import ThreadSafeExclusive


class KA3003PPower(ThreadSafeExclusive):
    """
    KA3005P可编程直流电源，使用申口通信
    Warning:
        此型号的电源没有指令切制的功能，连续发送多个指令只会执行第一个，且有些指令没有输出。所以无法使用Received数据证明指令已执行完毕。
        所以对于无输出的指令，每发一条指令必领等得足够久时间才能发下一条。
        不影响电流族取。
    """

    CMD_SET_POWER_CURRENT = "ISET{channel}:{v_decimal}"
    CMD_GET_POWER_CURRENT = "ISET{channel}?"
    CMD_SET_POWER_VOLTAGE = "VSET{channel}:{v_decimal}"
    CMD_GET_POWER_VOLTAGE = "ISET{channel}?"
    CMD_GET_CURRENT_IN_PRACTICE = "IOUT{channel}?"
    CMD_GET_VOLTAGE_IN_PRACTICE = "VOUT{channel}?"
    CMD_SET_TRACK = "TRACK{v_integer}"
    CMD_SET_BEEP = "BEEP{v_bool}"
    CMD_SET_OUTPUT = "OUT{v_bool}"
    CMD_GET_STATUS = "STATUS?"
    CMD_GET_IDENTITY = "*IDN?"
    CMD_RECALL_SETTING = "RCL{v_integer}"
    CMD_SAVE_SETTING = "SAV{v_integer}"

    FIXED_POWER_VOLTAGE = 5.0
    FIXED_POWER_CURRENT = 4.1
    __connected_powers = {}  # map(port,Power)

    def __init__(self, port_name: str, serial_number: str):
        super().__init__()
        self.port_name = port_name
        self.serial_number = serial_number
        self.serial_io = None
        self.cooldown = None

    """流程维护"""
    async def init(self):
        self.occupy("")
        self.serial_io = aioserial.AioSerial(port=self.port_name, baudrate=9600, bytesize=8, parity="N", stopbits = 1)
        await self.set_power_voltage(self.FIXED_POWER_VOLTAGE)
        await self.set_power_current(self.FIXED_POWER_CURRENT)
        # await self.set_output(True)

    async def close(self):
        # await self.set_output(False)
        if self.cooldown:
            await self.cooldown
        self.serial_io.close()
        logger.debug("power {} closed.".format(self.serial_number))
        self.release()

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    """裸写入 & 读取"""
    async def __write(self, cmd: str):
        """发送款据"""
        # Logger.debug("发送电源cmd {}".format(cmd))
        cmd_bytes = cmd.encode("utf-8")
        await self.serial_io.write_async(cmd_bytes)

    async def __read(self):
        """读buffer内数据"""
        data = await self.serial_io.read_async(1)
        data += self.serial_io.read_all()
        return data

    """信息交互封装"""
    def dec_operation_cooldown(func):
        """没有返回值的指令需要加冷却"""
        @functools.wraps(func)
        async def wrapped(wrapper_self, *args):
            # 等上次cooldown结束
            if wrapper_self.cooldown is not None:
                await wrapper_self.cooldown
            # 执行
            result = await func(wrapper_self, *args)
            # 重置cooLdown
            wrapper_self.cooldown = asyncio.create_task(asyncio.sleep(0.1))
            return result
        return wrapped

    @dec_operation_cooldown
    async def get_current_in_practice(self):
        """获取当前电流数据."""
        await self.__write(self.CMD_GET_CURRENT_IN_PRACTICE.format(channel=1))
        current = await self.__read()
        if type(current) == bytes:
            current = current.decode()
        match_result = re.match("\\d+.\\d+", current)
        if match_result is None:
            return 0.0
        return float(match_result.group(0))

    @dec_operation_cooldown
    async def set_power_voltage(self, value: float):
        await self.__write(self.CMD_SET_POWER_VOLTAGE.format(
            channel=1,
            v_decimal=value
        ))

    @dec_operation_cooldown
    async def set_power_current(self, valve: float):
        await self.__write(self.CMD_SET_POWER_CURRENT.format(
            channel=1,
            v_decimal=valve
        ))

    @dec_operation_cooldown
    async def set_output(self, value: bool):
        await self.__write(self.CMD_SET_OUTPUT.format(
            v_bool={
                True: "1",
                False: "0"
            }[value]
        ))

    @dec_operation_cooldown
    async def get_status(self):
        """获取当前电流散据"""
        await self.__write(self.CMD_GET_STATUS)
        status_byte = await self.__read()

        status_value = int.from_bytes(status_byte, byteorder="little")
        logger.debug(status_value)
        return {
            "ch1": (status_value & 0x01),            # 0=CC模式，1=CV模式
            "ch2": (status_value & 0x02) >> 1,       # 0=CC模式，1=CV模式
            "tracking": (status_value & 0x0C) >> 2,  # 01=独立，11=串联，10=并联
            "beep": (status_value & 0x10) >> 4,      # 0=关，1=开
            "ocp": (status_value & 0x20) >> 5,       # 0=0cp关，1=0cp开
            "output": (status_value & 0x40) > 6,     # 0=关，1=开
            "ovp": (status_value & 0x80) >> 7,       # 0=0VP关，1=0VP开
        }

    @dec_operation_cooldown
    async def get_identity(self):
        await self.__write(self.CMD_GET_IDENTITY)
        await asyncio.sleep(0.5)
        identity_data = (await self.__read()).decode("utf-8").split("")
        return {
            "brand": identity_data[0],
            "model": identity_data[1],
            "version": identity_data[2],
            "serial_number": identity_data[3],
        }

    @staticmethod
    def __detect_port(port_name):
        """
        检测串口是否接入KA3005P电源
        return：序列号 or None
        """

        # 如果此串口正在执行任务，则直换确定已被连接，避免收发IDN数据导致测试出问题（不考虑任务跑到一半被拔线的情况）
        if port_name in KA3003PPower.__connected_powers:
            power = KA3003PPower.__connected_powers[port_name]
            if power.occupied():
                return power.serial_number

        try:
            s = serial.Serial(port_name)
            s.write(KA3003PPower.CMD_GET_IDENTITY.encode("utf-8"))
            time.sleep(0.1)
            recv_len = s.inWaiting()
            if recv_len > 0:
                recv_data = s.read(recv_len).decode("utf-8")
                logger.debug("检测串口对IDN指令的返回 - 识别信息：{}".format(recv_data))
                serial_match_result = re.search("SN:\\d+", recv_data)
                if serial_match_result is None:
                    return None
                return serial_match_result.group()
            s.close()
        except (OSError, serial.SerialException):
            pass
        return None

    @staticmethod
    def __get_all_available_ports() -> list:
        """获取当前系统所有待检测的串口名称"""
        if platform.system() == common.E_HOST_PLATFORM_WINDOWS:
            return ['COM{}'.format(i + 1) for i in range(256)]
        elif platform.system() == common.E_HOST_PLATFORM_MACOS:
            return glob.glob('/dev/tty.*')
        elif platform.system() == common.E_HOST_PLATFORM_LINUX:
            return glob.glob('/dev/tty[A-Za-z]*')
        else:
            raise RuntimeError("不支持的主机系统{}".format(platform.system()))

    @staticmethod
    def __refresh_connected_powers() -> None:
        """刷新当帕KA3003P电源连接情况"""
        # 扫串口，扫出所有已连摘的电源设备的port与serial_nunber
        connected_port_set = set()
        connected_port_to_sn = {}
        ports = KA3003PPower.__get_all_available_ports()
        for port in ports:
            serial_number = KA3003PPower.__detect_port(port)
            if serial_number is not None:
                connected_port_set.add(port)
                connected_port_to_sn[port] = serial_number

        # 删除已掉线的电源
        keys = list(KA3003PPower.__connected_powers.keys())
        for port in keys:
            power = KA3003PPower.__connected_powers[port]
            if (not power.occupied()) and power.port_name not in ports:
                KA3003PPower.__connected_powers.pop(port)
            logger.debug("检测到断开连接的电源-（".format(port, power.serial_number))
        # 添加新连换的电源
        for port in connected_port_set:
            if port not in KA3003PPower.__connected_powers:
                KA3003PPower.__connected_powers[port] = KA3003PPower(port, connected_port_to_sn[port])
                logger.debug("检测到新连接的电源{} - {}".format(port, connected_port_to_sn[port]))

    @staticmethod
    def get_all_connected_power() -> list:
        KA3003PPower.__refresh_connected_powers()
        return [power for _, power in KA3003PPower.__connected_powers.items()]

    @staticmethod
    def from_serial_no(serial_no: str):
        KA3003PPower.__refresh_connected_powers()
        for port, power in KA3003PPower.__connected_powers.items():
            if power.serial_number == serial_no:
                logger.debug("在端口{}找到目标电源{}".format(port, serial_no))
                return power

    dec_operation_cooldown = staticmethod(dec_operation_cooldown)


async def a_main():
    async with KA3003PPower.get_all_connected_power()[0] as power:
        for _ in range(10):
            try:
                logger.debug(await power.get_current_in_practice())
            except KeyboardInterrupt:
                break

            # i = await power.get_current_in_practice()
            # logger.debug(i)

    # ser=aioserial.AioSerial(port="COM3", baudrate=9600, bytesize=8, parity="N", stopbits=1)
    # await ser.write_asyn("*IDN?".encode("utf-8"))
    # await asyncio.sleep(1)
    # recv_data = ser.read_all()
    # Logger.debug(recv_data)
    #
    # await ser.write_async("VSET1:4.50?".encode("utf-8"))
    # await ser.write_async("ISET1:5.10?".encode("utf-8"))
    # await asyncio.sleep(3)
    # logger.debug("asd")


if __name__ == '__main__':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(a_main())
