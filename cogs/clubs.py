from __future__ import annotations
from typing import TYPE_CHECKING

import aiofiles
import json
import re
from discord.ext import commands, tasks
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Optional
from datetime import datetime, timezone

from utils.club_data import ClubData

from discord import Embed, app_commands, Interaction, Message

import logging

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")

img_regex = r'<!--[\s\S]*?-->|(?P<url>(http(s?):)?\/?\/?[^,;" \n\t>]+?\.(jpg|gif|png))'
url_regex = r"(?:https://)?\w+\.\S*[^.\s]"


class ClubsCommand(commands.Cog):
    club_data: List[ClubData] = []

    def __init__(self, bot: KanaIsTheBest):
        self.bot = bot

        self.club_data_path = Path(__file__).cwd() / "data" / "clubs.json"

    async def cog_load(self) -> None:
        await self.club_data_initialization()

    async def cog_unload(self):
        self.refresh_club_data_to_cache.stop()

    async def club_data_initialization(self):
        if not self.club_data_path.exists():
            # If it doesn't exist, create the file
            async with aiofiles.open(
                    self.club_data_path, mode="w+", encoding="utf-8"
            ) as file:
                await file.write(json.dumps({}))
            return

        self.refresh_club_data_to_cache.start()

    @tasks.loop(hours=24, reconnect=True)
    async def refresh_club_data_to_cache(self):
        async with aiofiles.open(
                self.club_data_path, mode="r+", encoding="utf-8"
        ) as file:
            content = await file.read()
            data: dict = json.loads(content)
        temp_data: List[ClubData] = []
        for key, value in data.items():
            value = ClubData(club_name=key, club_data=value)
            temp_data.append(value)
        """
        Multiple sort, since the reverse=False we need to reverse the member count and
        pings too.

        Now it would sort with:
        1st highest number of members
        2nd highest number of pings
        3rd sorted alphabetically
        """
        self.club_data = sorted(
            temp_data, key=lambda x: (-x.member_count, -x.pings, x.club_name)
        )

    class CooldownModified:
        def __init__(self, rate: float = 1, per: float = 30):
            self.rate = rate
            self.per = per

        def __call__(self, ctx: commands.Context) -> Optional[commands.Cooldown]:
            message = ctx.message
            if message.author.id == 123456789:  # ID
                return None
            else:
                return commands.Cooldown(self.rate, self.per)

    @commands.dynamic_cooldown(
        cooldown=CooldownModified(),
        type=commands.BucketType.user
    )
    @commands.command(name="pingclub", aliases=["ping"], description="ping a club")
    @commands.guild_only()
    async def ping_a_club_normal(
            self, ctx: Context, club_name: str, *, link: Optional[str] = None
    ):
        
        await self.pinging_the_club(ctx, club_name, link)

    @commands.hybrid_group(
        name="club", fallback="get", description="Check all Club related commands"
    )
    @commands.guild_only()
    async def get_the_clubs(self, ctx: Context):
        em = Embed(title="Club commands", timestamp=datetime.now(tz=timezone.utc))

        command = ctx.command
        if isinstance(command, commands.Group):
            await ctx.typing()
            for subcommand in command.walk_commands():
                if subcommand.parents[0] == command:
                    em.add_field(
                        name=f"**{subcommand}**",
                        value=f"{subcommand.description}",
                        inline=True,
                    )
            await ctx.send(embed=em, delete_after=60)

    @commands.dynamic_cooldown(
        cooldown=CooldownModified(),
        type=commands.BucketType.user,
    )
    @get_the_clubs.command(name="ping", description="ping a club")
    @app_commands.describe(club_name="Name of the club", link="Link to share")
    async def ping_a_club_v2(
            self, ctx: Context, club_name: str, link: Optional[str] = None
    ):
        await self.pinging_the_club(ctx, club_name, link)

    async def pinging_the_club(
            self, ctx: Context, club_name: str, link: Optional[str] = None
    ):
        async def send_message_via_normal_or_channel(
                searched_for_related_club: bool,
                message_content: str,
                delete_after: Optional[float] = None,
        ) -> Message:
            if searched_for_related_club:
                return_message = await ctx.channel_send(
                    content=message_content, delete_after=delete_after
                )
            else:
                return_message = await ctx.send(
                    content=message_content, delete_after=delete_after
                )

            return return_message

        # Check if it is a normal command and if it has replied message
        # If there is replied message, get the link from there
        if link is None:
            reply_message_link = None
            if ctx.interaction is None and ctx.message.reference is not None:
                content = ctx.message.reference.cached_message.content
                result = re.findall(url_regex, content)
                reply_message_link = result[0] if len(result) > 0 else None
            link = reply_message_link

        # Search for the club with its name
        club = await self._search_the_club_for(club_name=club_name)

        search_for_related_club = False
        if club is None:
            # If there is no club based from name, search for the closest club
            # based from name
            similar_club = await self._fetch_similar_club_or_none_view(ctx=ctx, club_name=club_name)
            if similar_club is None:
                ctx.command.reset_cooldown(ctx)
                return

            club = similar_club
            club_name = similar_club.club_name
            search_for_related_club = True

        check_author = club.check_if_author_is_in_the_club(
            author_id=ctx.author.id, ctx=ctx
        )

        if not check_author:
            content = f"{ctx.author.mention} is not part of {club_name}. "
            "Please join the club {club_name}"
            await send_message_via_normal_or_channel(
                searched_for_related_club=search_for_related_club,
                message_content=content,
                delete_after=10,
            )
            ctx.command.reset_cooldown(ctx)
            return

        check_blacklisted = club.check_if_author_is_blacklisted(author_id=ctx.author.id)
        if check_blacklisted:
            content = (
                f"`{ctx.author.name}#{ctx.author.discriminator}` "
                "can't perform the ping club for the"
                f"club `{club_name}`"
            )
            await send_message_via_normal_or_channel(
                searched_for_related_club=search_for_related_club,
                message_content=content,
                delete_after=15,
            )
            return

        member_mentions = club.create_member_mention_list(ctx)
        if member_mentions is None:
            content = "Error in the number of members"
            await send_message_via_normal_or_channel(
                searched_for_related_club=search_for_related_club,
                message_content=content,
                delete_after=10,
            )
            ctx.command.reset_cooldown(ctx)
            return

        last_entry = club.get_the_last_ping_from_history(guild_id=ctx.guild.id)

        if last_entry is not None and last_entry.check_if_within_24_hours:
            last_channel = ctx.guild.get_channel_or_thread(last_entry.channel_id)
            ping_again = await ctx.prompt(
                content=f"`{club_name}` have already been pinged last {last_entry.time_stamp} at"
                        f" {last_channel.mention}. Would you like to ping again?",
                timeout=30,
            )
            if not ping_again:
                ctx.command.reset_cooldown(ctx)
                return

        await club.update_ping(file_path=self.club_data_path)

        message_list = []
        for index, member_mention in enumerate(member_mentions):
            msg = f"Club: `{club_name}`\n" f"{member_mention}"
            if link is not None:
                msg += f"\n{link}"

            if index == 0 and not search_for_related_club:
                message = await ctx.send(content=msg)
            else:
                # This is for the interaction, so it won't be reply chain
                message = await ctx.channel_send(content=msg)
            message_list.append(message)

        club.save_ping_history(
            ctx=ctx,
            message_id=message_list[0].id
        )

        if len(message_list) > 0 and link is None:
            # If there is no link, wait for 15 seconds and wait for the link
            link_message = await ctx.wait_for_message(timeout=15, check_same_user=True)
            if link_message is None:
                return
            result = re.findall(url_regex, link_message.content)
            result_link = result[0] if len(result) > 0 else None

            # Edit the earlier message if the link was added
            if result_link is not None:
                # If found the link, removed the embed for much easier interface
                await link_message.edit(suppress=True)
                for message in message_list:
                    content = message.content
                    content += f"\n{result_link}"
                    await message.edit(content=content)

    async def _search_the_club_for(self, club_name: str) -> Optional[ClubData]:
        clubs = [
            club
            for club in self.club_data
            if club.club_name.lower() == club_name.lower()
        ]
        if len(clubs) == 0:
            return None
        else:
            return clubs[0]

    async def _fetch_similar_club_or_none_view(
            self, ctx: Context, club_name: str
    ) -> Optional[ClubData]:
        similar_clubs = await self._find_similar_clubs(club_name=club_name)

        result = await ctx.choose_value_with_button(
            content=f"Club `{club_name}` not found\n" f"Is this the club?",
            entries=similar_clubs,
            timeout=30,
        )

        club = await self._search_the_club_for(club_name=f"{result}")
        return club

    async def _find_similar_clubs(
            self, club_name: str, number_of_similar_clubs: int = 5
    ) -> List[str]:
        similarity = []
        for club in self.club_data:
            ratio = SequenceMatcher(None, club_name, club.club_name).ratio()
            similarity.append((ratio, club.club_name))
        similarity = sorted(similarity, reverse=True)
        tmp = [name for ratio, name in similarity]
        return tmp[0:number_of_similar_clubs]

    @ping_a_club_v2.autocomplete(name="club_name")
    async def autocomplete_club_names(self, interaction: Interaction, current: str):
        club_list: List[app_commands.Choice] = []
        author_id = interaction.user.id
        command_name = interaction.command.name

        for club in self.club_data:
            user_check = club.check_if_author_is_in_the_club(author_id=author_id)

            if command_name == "ping" and not user_check:
                continue

            if len(current) == 0:
                item = app_commands.Choice(name=club.club_name, value=club.club_name)
                club_list.append(item)
            else:
                if (
                        current.lower() in club.club_name.lower()
                        or current.lower() in club.description.lower()
                ):
                    item = app_commands.Choice(
                        name=club.club_name, value=club.club_name
                    )
                    club_list.append(item)
            if len(club_list) > 24:
                break

        return club_list


async def setup(bot: KanaIsTheBest):
    ext = ClubsCommand(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
