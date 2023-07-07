from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Optional, List, Union

from pathlib import Path
from discord import app_commands, Member
from discord.ext import commands
from aiohttp import ClientSession
from datetime import datetime, timezone

import logging
import json
import re

from utils.manga import MangaPaginationView

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context


class OshiNoKoManga(commands.Cog):
    def __init__(
            self,
            bot: KanaIsTheBest
    ):
        self.bot = bot

        self.oshi_no_ko_mangasee_source = "https://cubari.moe/read/api/mangasee/series/Oshi-no-Ko/"

        self.chapters = {}

        self.chapters_json = Path(__file__).cwd() / "data" / "oshi-no-ko.json"

        self.last_chapter_number = 1

    async def cog_load(self):
        release_day = self.check_if_today_is_release_day()
        if release_day:
            await self.get_updates_from_sources()

        try:
            with open(self.chapters_json) as file:
                self.chapters = json.load(file)
        except FileNotFoundError:
            with open(self.chapters_json, "w") as file:
                file.write(json.dumps({}))

        for key, _ in self.chapters.items():
            try:
                chapter_number = int(key)
                if chapter_number >= self.last_chapter_number:
                    self.last_chapter_number = chapter_number
            except ValueError:
                continue

    @staticmethod
    def check_if_today_is_release_day():
        now = datetime.now(timezone.utc)

        # Release day is UTC 15:00 but will add all the way to 23:59
        # for checking
        return now.weekday == 2 and now.hour >= 15

    @commands.command(name="update_manga")
    async def update_manga_source(self, ctx: Context):
        await ctx.typing()

        await self.get_updates_from_sources()

        await ctx.send("done")

    async def get_updates_from_sources(self):
        async with ClientSession() as session:
            mangasee_chapters = await self.get_mangasee_chapters(
                session=session,
                url=self.oshi_no_ko_mangasee_source,
                upper_chapter_limit=95
            )
            self.chapters.update(mangasee_chapters)

            cubari_url = "https://guya.moe/api/series/Oshi-no-Ko"
            await self.get_cubari_chapter_pages(
                session=session,
                series_link=cubari_url
            )

        with open(self.chapters_json, "w") as file:
            file.write(json.dumps(self.chapters))

    async def get_mangasee_chapters(
            self,
            session: ClientSession,
            url: str,
            upper_chapter_limit: Optional[Union[float, int]] = None,
            lower_chapter_limit: Optional[Union[float, int]] = None
    ) -> dict:
        async with session.get(url) as resp:
            data: dict = await resp.json()

        mangasee_chapters: Optional[dict] = data.get("chapters", None)
        if mangasee_chapters is None:
            return
        value: dict

        fetch_chapters = {}
        for key, value in mangasee_chapters.items():
            try:
                if "." in key:
                    chapter_key = float(key)
                else:
                    chapter_key = int(key)
            except ValueError:
                continue
            if chapter_key >= self.last_chapter_number:
                self.last_chapter_number = chapter_key

            if upper_chapter_limit is not None and \
                    upper_chapter_limit <= chapter_key \
                    and lower_chapter_limit is None:
                pass
            if upper_chapter_limit is None and \
                    lower_chapter_limit >= chapter_key \
                    and lower_chapter_limit is not None:
                pass
            if lower_chapter_limit is not None and \
                    upper_chapter_limit is not None and \
                    upper_chapter_limit <= chapter_key < lower_chapter_limit:
                pass

            if chapter_key >= 95:
                chapter_link_group: dict = value.get("groups", None)
                if chapter_link_group is None:
                    continue
                chapter_link = chapter_link_group.get("1", None)
                if chapter_link is None:
                    continue
                full_chapter_link = f"https://cubari.moe{chapter_link}"
                chapter_pages = await self.get_mangasee_chapter_pages(
                    session=session,
                    chapter_link=full_chapter_link
                )
                fetch_chapters.update({
                    key: chapter_pages
                })
                await asyncio.sleep(0.1)

        return fetch_chapters

    async def get_cubari_chapter_pages(self,
                                       session: ClientSession,
                                       series_link: str):
        async with session.get(series_link) as resp:
            text = await resp.text()
        chapters_json: dict = json.loads(text)

        chapters_details: Optional[dict] = chapters_json.get("chapters", None)
        if chapters_details is None:
            error_logger.error("chapters_details is missing")
            return {}

        value: dict
        for key, value in chapters_details.items():
            folder = value.get("folder", None)
            if folder is None:
                error_logger.error("folder is missing")
                continue
            groups: Optional[dict] = value.get("groups", None)
            if groups is None:
                error_logger.error("groups is missing")
                continue

            first_group = next(iter(groups))
            pages = groups.get(first_group, None)
            if pages is None:
                continue
            new_pages_link = []
            for page in pages:
                page_url = f"https://guya.moe/media/manga/Oshi-no-Ko/chapters/{folder}/{first_group}/{page}"
                new_pages_link.append(page_url)

            self.chapters.update({
                key: new_pages_link
            })

    async def get_mangasee_chapter_pages(self,
                                         session: ClientSession,
                                         chapter_link: str) -> List[str]:
        async with session.get(chapter_link) as resp:
            if resp.status == 200:
                pages = await resp.json()
            else:
                pages = []

        return pages

    class CooldownModified:
        def __init__(self, rate: float = 1, per: float = 10):
            self.rate = rate
            self.per = per

        def __call__(self, ctx: Context) -> Optional[commands.Cooldown]:
            if isinstance(ctx.author, Member) and \
                    ctx.author.guild_permissions.administrator:
                return None

            # underground idol
            role_id = 1099400199920693248
            if ctx.guild.id in ctx.bot.from_serversetup:
                if 'modrole' in ctx.bot.from_serversetup[ctx.guild.id]:
                    modrole_id = role_id
                    if modrole_id in [r.id for r in ctx.author.roles]:
                        return None

            return commands.Cooldown(self.rate, self.per)

    @commands.dynamic_cooldown(cooldown=CooldownModified(),
                               type=commands.BucketType.user)
    @commands.hybrid_group(
        name="manga",
        description="Read Oshi no ko manga",
        aliases=["chapter", "chap"],
        fallback="oshi-no-ko"
    )
    @app_commands.describe(
        chapter="Chapter to read: Defaults to 1",
        page="Page to read: Defaults to 1",
    )
    async def manga(self, ctx: Context, chapter: float = 1.0, page: int = 1):
        try:
            if re.match(r'^\d+\.0$', str(chapter)):
                chapter_number = int(chapter)
            elif re.match(r'^\d+\.\d+$', str(chapter)):
                chapter_number = float(chapter)
            else:
                chapter_number = int(chapter)
        except ValueError:
            chapter_number = 1

        await ctx.typing()

        view = MangaPaginationView(
            chapters=self.chapters,
            ctx=ctx,
            page=page-1,
            chapter_number=chapter_number,
            last_chapter_number=self.last_chapter_number
        )
        await view.start()

    @manga.command(
        name="renai-daikou",
        description="Read Renai Daikou manga",
        aliases=["renai"],
    )
    async def get_renai_manga(self, ctx: Context, chapter: int = 1, page: int = 1):
        await ctx.typing()

        await ctx.send("done")


async def setup(
        bot: KanaIsTheBest
):
    ext = OshiNoKoManga(bot)
    await bot.add_cog(ext)
