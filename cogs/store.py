import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils

class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=["s"])
    async def store(self, ctx):
        """Store desc here"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @store.command()
    async def buy(self, ctx, item, amount, payment):
        """Buy an x amount of items for a payment of n"""
        await ctx.send("Buying lol")

    @store.command()
    @commands.check(checks.owner_check)
    async def sell(self, ctx, item, amount, payment):
        """Sell an x amount of items and get payed"""
        await ctx.send("Selling lol")


def setup(bot):
    ext = Store(bot)
    bot.add_cog(ext)
