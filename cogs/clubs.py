from __future__ import annotations
from typing import TYPE_CHECKING

import aiofiles
import json
from discord.ext import commands, tasks
from pathlib import Path
from typing import List, Optional

from models.club_data import ClubData

from discord import Embed, app_commands, Interaction
from datetime import datetime

import logging

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class ClubsCommand(commands.Cog):
    club_data: List[ClubData] = []

    def __init__(
            self,
            bot: KanaIsTheBest
    ):
        self.bot = bot

        self.club_data_path = Path(__file__).cwd() / "data" / "clubs.json"

    async def cog_load(self) -> None:
        await self.club_data_initialization()

    async def cog_unload(self):
        self.refresh_club_data_to_cache.stop()

    async def club_data_initialization(self):
        if not self.club_data_path.exists():
            # If it doesn't exist, create the file
            async with aiofiles.open(self.club_data_path, mode="w+", encoding="utf-8") as file:
                await file.write(json.dumps({}))
            return

        self.refresh_club_data_to_cache.start()

    @tasks.loop(hours=24, reconnect=True)
    async def refresh_club_data_to_cache(self):
        async with aiofiles.open(self.club_data_path, mode="r+", encoding="utf-8") as file:
            content = await file.read()
            data: dict = json.loads(content)
        temp_data: List[ClubData] = []
        for key, value in data.items():
            value = ClubData(
                club_name=key,
                club_data=value
            )
            temp_data.append(value)
        """
        Multiple sort, since the reverse=False we need to reverse the member count and
        pings too.

        Now it would sort with:
        1st highest number of members
        2nd highest number of pings
        3rd sorted alphabetically
        """
        self.club_data = sorted(temp_data, key=lambda x: (-x.member_count, -x.pings, x.club_name))

    @commands.command(
        name="pingclub",
        aliases=["ping"],
        description="ping a club"
    )
    async def ping_a_club_normal(
            self,
            ctx: Context,
            club_name: str
    ):
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
    @app_commands.describe(
        club_name="Name of the club"
    )
    async def ping_a_club_v2(
            self,
            ctx: Context,
            club_name: str
    ):
        await ctx.send("here2")

    @ping_a_club_v2.autocomplete(name="club_name")
    async def autocomplete_club_names(
            self,
            interaction: Interaction,
            current: str
    ):
        club_list: List[app_commands.Choice] = []
        author_id = interaction.user.id
        command_name = interaction.command.name

        for club in self.club_data:
            user_check = club.check_if_author_is_in_the_club(
                author_id=author_id)

            if command_name == "ping" and not user_check:
                continue

            if len(current) == 0:
                item = app_commands.Choice(
                    name=club.club_name,
                    value=club.club_name
                )
                club_list.append(item)
            else:
                if current.lower() in club.club_name.lower() or \
                   current.lower() in club.description.lower():

                    item = app_commands.Choice(
                        name=club.club_name,
                        value=club.club_name
                    )
                    club_list.append(item)
            if len(club_list) > 24:
                break

        return club_list


async def setup(
        bot: KanaIsTheBest
):
    ext = ClubsCommand(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
