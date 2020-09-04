import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils

class ClassName(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["q"])
    async def CommandName(self, ctx, *args):
        """Desc here"""
        await ctx.send("Something")

def setup(bot):
    ext = ClassName(bot)
    bot.add_cog(ext)
