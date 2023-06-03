import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Union
from models.club_moderation import ClubPingHistory
from models import club_moderation

import aiofiles
from discord import Member, Interaction
from discord.ext import commands

import logging
import traceback

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


@dataclass
class ClubData:
    club_name: str
    club_data: dict
    creator_id: Optional[int] = 0
    creator_name: Optional[str] = ""
    description: str = ""
    pings: int = 0
    member_count: int = 0
    image_url: str = ""
    members: List[int] = field(default_factory=list)
    moderators: List[int] = field(default_factory=list)
    blacklist: List[int] = field(default_factory=list)

    def __post_init__(self):
        data = self.club_data

        self.creator_id = data.get("creator", None)
        self.description = data.get("desc", "")
        self.pings = data.get("pings", 0)

        self.members = data.get("members", [])

        self.member_count = len(self.members)

        self.moderators = data.get("moderators", [])
        self.blacklist = data.get("blacklist", [])

        self.image_url = data.get("image_url", "")

    def save_ping_history(
            self,
            ctx: commands.Context,
            message_id: int
    ):
        # Ping History
        new_entry = ClubPingHistory(
            author_id=ctx.author.id,
            author_name=ctx.author.display_name,
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            message_id=message_id,
            club_name=self.club_name,
        )
        new_entry.save()

    def get_the_last_ping_from_history(self, guild_id: int) -> Optional[ClubPingHistory]:
        return club_moderation.get_the_last_entry_from_club_name_from_guild(
            club_name=self.club_name,
            guild_id=guild_id
        )

    def check_if_author_is_in_the_club(
            self,
            author_id: int,
            ctx: Optional[commands.Context] = None
    ) -> bool:
        if ctx is not None:
            if isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator:
                return True
        if author_id in self.members:
            return True
        else:
            return False

    def check_if_author_is_blacklisted(
            self,
            author_id: int
    ) -> bool:
        return True if author_id in self.blacklist else False

    def check_if_author_is_a_moderator(
            self,
            author_id: int
    ) -> bool:
        return True if author_id in self.moderators else False

    def check_if_all_of_list_exist_on_this_club(
            self,
            member_list: List[int]
    ) -> bool:
        check = all(item in self.members for item in member_list)
        return check

    def create_member_mention_list(
            self,
            ctx: Union[commands.Context, Interaction]
    ) -> Optional[List[str]]:
        output = []
        pings = ""
        for index, member in enumerate(self.members):
            guild_member = ctx.guild.get_member(member)
            if guild_member is None:
                continue
            pings += f"{guild_member.mention} "
            if len(pings) > 1900:
                output.append(pings)
                pings = ""
        if len(pings) > 0:
            output.append(pings)
        if len(output) == 0:
            return None
        else:
            return output

    async def update_ping(
            self,
            file_path: Path
    ):
        await self.update_pings_from_json(file_path)
        if self.pings is None:
            self.pings = 1
        else:
            self.pings += 1

    async def update_pings_from_json(self, file_path: Path):
        data = await self._read_json_data(file_path)
        club_data: dict = data.get(self.club_name, None)
        if club_data is not None:
            pings = self.pings
            if pings is not None:
                pings += 1
            club_data.update(
                {'pings': pings}
            )
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def update_club_information_from_json(
            self,
            file_path: Path,
            description: str,
            image_url: str
    ):
        data = await self._read_json_data(file_path)
        club_data: dict = data.get(self.club_name, None)
        if club_data is not None:
            club_data.update(
                {
                    'desc': description,
                    'image_url': image_url
                }
            )
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def create_club(
            self,
            file_path: Path,
    ):
        data = await self._read_json_data(file_path)
        new_club = {
            self.club_name: self.club_data
        }
        data.update(
            new_club
        )
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def delete_club(
            self,
            file_path: Path,
    ):
        data = await self._read_json_data(file_path)
        data.pop(self.club_name)
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def set_club_member_status(
            self,
            file_path: Path,
            author_id: int,
            join: bool
    ):
        data = await self._read_json_data(file_path)

        if join:
            self.members.append(author_id)
        else:
            self.members.remove(author_id)

            if author_id in self.moderators:
                try:
                    self.moderators.remove(author_id)
                except Exception as ex:
                    error_message = ''.join(traceback.format_exception(None, ex, ex.__traceback__))
                    error_logger.error(error_message)
                    pass

        club_data: dict = data.get(self.club_name, None)

        if club_data is not None:
            club_data.update(
                {"members": self.members}
            )
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def set_club_moderator_status(
            self,
            file_path: Path,
            author_id: int,
            join: bool
    ):
        data = await self._read_json_data(file_path)

        if join:
            self.moderators.append(author_id)
        else:
            self.moderators.remove(author_id)

        club_data: dict = data.get(self.club_name, None)
        if club_data is not None:
            club_data.update(
                {"moderator": self.moderators}
            )
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def set_club_blacklist_member_status(
            self,
            file_path: Path,
            author_id: int,
            join: bool
    ):
        data = await self._read_json_data(file_path)

        if join:
            self.blacklist.append(author_id)
        else:
            self.blacklist.remove(author_id)

        club_data: dict = data.get(self.club_name, None)
        if club_data is not None:
            club_data.update(
                {"blacklist": self.blacklist}
            )
        async with aiofiles.open(file_path, "w+", encoding="utf-8") as f:
            await f.write(json.dumps(data))

    async def _read_json_data(self, file_path: Path) -> dict:
        try:
            content = await self._read_file(file_path)
            return json.loads(content)
        except FileNotFoundError:
            return {}
        except IsADirectoryError:
            return {}

    @staticmethod
    async def _read_file(file_path: Path):
        async with aiofiles.open(file_path, "r+", encoding="utf-8") as file:
            content = await file.read()
        return content
