from loguru import logger
import asyncio
class EnergyTestTask():
    @classmethod
    async def start_game(cls):
        logger.info(f"Starting game")

    @classmethod
    async def cmd_1(cls):
        logger.info(f"cmd1")

    @classmethod
    async def cmd_2(cls):
        logger.info(f"cmd2")