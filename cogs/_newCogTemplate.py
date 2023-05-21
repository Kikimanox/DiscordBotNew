from __future__ import annotations
from typing import TYPE_CHECKING
from discord.ext import commands

import logging

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class ClassName(commands.Cog):
    def __init__(
            self,
            bot: KanaIsTheBest
    ):
        self.bot = bot

    @commands.command(aliases=["q"])
    async def CommandName(self, ctx: Context, *args):
        """Desc here"""
        await ctx.send("Something")

    # async def if_you_need_loop(self):
    #     await self.bot.wait_until_ready()
    #     while True:
    #         try:
    #             print("Code here")
    #         except:
    #             pass
    #         await asyncio.sleep(10)  # sleep here


async def setup(
        bot: KanaIsTheBest
):
    ext = ClassName(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
