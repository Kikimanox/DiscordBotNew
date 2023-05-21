from __future__ import annotations
from typing import TYPE_CHECKING
from discord.ext import commands

from discord import Embed
from datetime import datetime

import logging

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class ClubsCommand(commands.Cog):
    def __init__(
            self,
            bot: KanaIsTheBest
    ):
        self.bot = bot

    @commands.command(
        name="pingclub",
        aliases=["ping"],
        description="ping a club"
    )
    async def ping_a_club_normal(self, ctx: Context):
        await ctx.send("here")

    @commands.hybrid_group(
        name="club",
        fallback="get",
        description="Check all Club related commands"
    )
    @commands.guild_only()
    async def get_the_clubs(self, ctx: Context):

        em = Embed(
            title="Club commands",
            timestamp=datetime.now()
        )

        command = ctx.command
        if isinstance(command, commands.Group):
            await ctx.typing()
            for subcommand in command.walk_commands():
                if subcommand.parents[0] == command:
                    em.add_field(
                        name=f"**{subcommand}**",
                        value=f"{subcommand.description}",
                        inline=True
                    )
            await ctx.send(embed=em, delete_after=60)

    @get_the_clubs.command(
        name="ping",
        description="ping a club"
    )
    async def ping_a_club_v2(self, ctx: Context):
        await ctx.send("here2")


async def setup(
        bot: KanaIsTheBest
):
    ext = ClubsCommand(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
