import asyncio
import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils


class Bets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ASDFfsdfds(self, ctx, *args):
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


def setup(bot):
    ext = Bets(bot)
    #bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    bot.add_cog(ext)