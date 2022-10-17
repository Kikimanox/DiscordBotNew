import asyncio
import json
import random
import re
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands
from discord import Member, Embed, File, utils, DMChannel, TextChannel
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils


class Manga(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Credit: appu1232

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(aliases=["chapter", "chap"])
    async def manga(self, ctx, chapter: str, page: str = None):
        """Display a page from a chapter and flip through pages/chapters.
          `[p]manga 5` - loads the first page of chapter 5.
          `[p]manga 20 7` - loads the 7th page of chapter 20.
          Once the page loads, reactions will appear as ◀ ⬅ ➡ ▶. Click ◀ ▶ to jump chapters. Click ⬅ ➡ to flip through pages. Only the user that sent the command can flip through pages.
          After a while (about an hour) of not flipping pages/chapters, a 🔖 will appear which means you won't be able to flip through pages anymore.
          At this point you will need to call the command again if you want to flip through pages."""

        series = "Oshi-no-Ko"
        await self.chapter(ctx, series, chapter, page)

    async def chapter(self, ctx, series: str, chapter: str, page: str = None):

        if not page:
            page = 1
        else:
            try:
                page = int(page)
            except:
                return await ctx.send("Error, please give valid page number. Ex: .manga 20 4")

        url = f"https://guya.moe/api/series/{series}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    self.bot.chapters_json[series] = json.loads(await resp.text())
        if chapter == "random" and isinstance(ctx.channel, DMChannel):
            chapter = random.choice([ch for ch in self.bot.chapters_json[series]["chapters"]])
        if chapter not in self.bot.chapters_json[series]["chapters"]:
            return await ctx.send("Could not find chapter. Please give valid chapter number.")
        chapter_details = self.bot.chapters_json[series]["chapters"][chapter]
        group, pages = self.get_group_and_pages(series, chapter_details)
        if not 0 < page < len(pages) + 1:
            page = len(pages)
        em = Embed(title=chapter_details["title"],
                   description=f"[Link](https://guya.moe/reader/series/{series}/{chapter.replace('.', '-')}/{page})  "
                               f"|  Ch: {chapter}  |  Page: {page}/{len(pages)}")
        if "folder" in chapter_details:
            url = f"https://guya.moe/media/manga/{series}/chapters/{chapter_details['folder']}/{group}/{pages[page - 1]}"
        else:
            url = pages[page - 1]
        em.set_image(url=url)
        chap = await ctx.channel.send(content="", embed=em)
        self.bot.running_chapters[chap.id] = {"series": series, "chapter": chapter, "current_page": page,
                                              "pages": pages, "total_pages": len(pages), "last_update": datetime.now(),
                                              "message": chap, "user": ctx.author.id}
        await chap.add_reaction("◀")
        await chap.add_reaction("⬅")
        await chap.add_reaction("➡")
        await chap.add_reaction("▶")
        await chap.add_reaction("❌")

    def get_group_and_pages(self, series, chapter_details):
        # preferred_sort = chapter_details["preferred_sort"] if "preferred_sort" in chapter_details else \
        #     self.bot.chapters_json[series].get("preferred_sort", None)
        # if preferred_sort:
        #     groups = [sort for sort in preferred_sort if sort in chapter_details["groups"]]
        # else:
        groups = None
        if not groups:
            group = list(chapter_details["groups"])[0]
        else:
            group = groups[0]
        pages = chapter_details["groups"][group]
        return group, pages

    async def chapter_flip(self, event):
        if str(event.emoji) in ["⬅", "➡", "◀", "▶", "❌"]:
            current_page = self.bot.running_chapters[event.message_id]["current_page"]
            chapter = self.bot.running_chapters[event.message_id]["chapter"]
            series = self.bot.running_chapters[event.message_id]["series"]
            forward_chap = backward_chap = 0
            if chapter + ".5" in self.bot.chapters_json[series]["chapters"]:
                forward_chap = chapter + ".5"
            elif chapter + ".1" in self.bot.chapters_json[series]["chapters"]:
                forward_chap = chapter + ".1"
            if "." in chapter:
                backward_chap = chapter.split(".", 1)[0]
            elif str(int(float(chapter)) - 1) + ".5" in self.bot.chapters_json[series]["chapters"]:
                backward_chap = str(int(float(chapter)) - 1) + ".5"
            elif str(int(float(chapter)) - 1) + ".1" in self.bot.chapters_json[series]["chapters"]:
                backward_chap = str(int(float(chapter)) - 1) + ".1"
            if str(event.emoji) == "⬅":
                if current_page - 1 == 0:
                    chapter = str(int(float(chapter)) - 1) if not backward_chap else backward_chap
                    if chapter in self.bot.chapters_json[series]["chapters"]:
                        chapter_details = self.bot.chapters_json[series]["chapters"][chapter]
                        group, pages = self.get_group_and_pages(series, chapter_details)
                        current_page = len(pages)
                else:
                    current_page -= 1
            elif str(event.emoji) == "➡":
                if current_page + 1 > self.bot.running_chapters[event.message_id]["total_pages"]:
                    current_page = 1
                    chapter = str(int(float(chapter)) + 1) if not forward_chap else forward_chap
                else:
                    current_page += 1
            elif str(event.emoji) in ["◀", "▶"]:
                if str(event.emoji) == "◀":
                    current_page = 1
                    chapter = str(int(float(chapter)) - 1) if not backward_chap else backward_chap
                else:
                    current_page = 1
                    chapter = str(int(float(chapter)) + 1) if not forward_chap else forward_chap
            elif str(event.emoji) == "❌":
                message = self.bot.running_chapters[event.message_id]["message"]
                del self.bot.running_chapters[event.message_id]
                return await message.delete()

            if chapter in self.bot.chapters_json[series]["chapters"]:
                chapter_details = self.bot.chapters_json[series]["chapters"][chapter]
                group, pages = self.get_group_and_pages(series, chapter_details)
                if chapter != self.bot.running_chapters[event.message_id]["chapter"]:
                    self.bot.running_chapters[event.message_id]["total_pages"] = len(pages)
                    self.bot.running_chapters[event.message_id]["pages"] = pages
                    self.bot.running_chapters[event.message_id]["chapter"] = chapter
                message = self.bot.running_chapters[event.message_id]["message"]
                em = message.embeds[0]
                em.title = chapter_details["title"]
                em.description = f"[Link](https://guya.moe/reader/series/" \
                                 f"{series}/{chapter.replace('.', '-')}/{current_page})  |  Ch: {chapter}  |  " \
                                 f"Page: {current_page}/{self.bot.running_chapters[event.message_id]['total_pages']}"
                page_file = self.bot.running_chapters[event.message_id]["pages"][current_page - 1]
                if "folder" in chapter_details:
                    url = f"https://guya.moe/media/manga/{series}/chapters/{chapter_details['folder']}/{group}/{page_file}"
                else:
                    url = page_file
                em.set_image(url=url)
                await message.edit(content=None, embed=em)
                self.bot.running_chapters[event.message_id]["current_page"] = current_page
                self.bot.running_chapters[event.message_id]["last_update"] = datetime.now()
            else:
                return

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        if hasattr(self.bot, "running_chapters") and event.message_id in self.bot.running_chapters and event.user_id == \
                self.bot.running_chapters[event.message_id]["user"]:
            await self.chapter_flip(event)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        if hasattr(self.bot, "running_chapters") and event.message_id in self.bot.running_chapters and event.user_id == \
                self.bot.running_chapters[event.message_id]["user"]:
            await self.chapter_flip(event)

    @commands.command(aliases=['ganti'])
    async def search(self, ctx, *, text: str):
        """Text search through guya.moe, defaults to the Oshi no Ko series.

        --guya mobile phone (for searching the kaguya-sama manga)
        --4koma erika (kaguya-sama 4koma search)
        --doujin maki (kaguya-sama official doujin search)
        """
        series_dict = {
            'main': 'Oshi-no-Ko',
            'guya': 'Kaguya-Wants-To-Be-Confessed-To',
            '4koma': 'We-Want-To-Talk-About-Kaguya',
            'doujin': 'Kaguya-Wants-To-Be-Confessed-To-Official-Doujin'
        }
        if text.strip().startswith('--'):
            series = text.strip().split('--')[1].split(' ', 1)[0]
            if series in series_dict:
                slug = series_dict[series]
                text = text.replace(f'--{series}', '').strip()
            else:
                return await ctx.send(
                    f"The specified series is not recognized. Options are: `{', '.join(series_dict.keys())}`")
        else:
            series = 'main'
            slug = series_dict[series]
        match = re.search(r'^([><=])(\d+(?:\.\d+)?)(-)?(\d+(?:\.\d+)?)?\s.+', text)
        if match:
            if match.group(3):
                operand_match = False
            else:
                operand_match = True
            for i in range(1, 5):
                if match.group(i):
                    text = text[len(match.group(i)):]
        search_response = {}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://guya.moe/api/search_index/{slug}/", data={"searchQuery": text}) as resp:
                if resp.status == 200:
                    search_response = await resp.json()
                else:
                    return await ctx.send(f"Error: server returned {resp.status}")
        first_word = next(iter(search_response))
        final_results = {}
        for variation, matches in search_response[first_word].items():
            for chapter, pages in matches.items():
                chapter_float = float(chapter.replace('-', '.'))
                if match:
                    if operand_match:
                        if match.group(1) == "<" and not chapter_float < float(match.group(2)):
                            continue
                        elif match.group(1) == ">" and not chapter_float > float(match.group(2)):
                            continue
                        elif match.group(1) == "=" and not chapter_float == float(match.group(2)):
                            continue
                    else:
                        if chapter_float <= float(match.group(2)) or chapter_float >= float(match.group(4)):
                            continue
                for page in pages:
                    for search_word in search_response:
                        if not any(chapter in search_response[search_word][matched_word] and page in
                                   search_response[search_word][matched_word][chapter] for matched_word, matched_chap in
                                   search_response[search_word].items()):
                            break
                    else:
                        chapter_float = chapter.replace('-', '.')
                        if chapter_float not in final_results:
                            final_results[chapter_float] = set([page])
                        else:
                            final_results[chapter_float].add(page)
        if not final_results:
            return await ctx.send("Search returned no results.")
        search_desc = ""
        chapter_count = 0
        embeds = []

        def create_embed(embed_page_numb):
            em = Embed(
                title=f"Manga text search for \"{text.strip()}\" in {series} series | Page {embed_page_numb} of ",
                color=0xea7938)
            em.set_thumbnail(url="https://i.imgur.com/PexT2dz.png")
            em.set_footer(text="Search powered by https://guya.moe")
            return em

        for chapter in sorted(final_results, key=float):
            chapter_count += 1
            em = create_embed(len(embeds) + 1)
            this_chapter = f"Ch. {chapter} | Pages: "
            if series == 'main':
                this_chapter += ", ".join(
                    [f"[{p}](https://guya.moe/reader/series/Oshi-no-Ko/{chapter.replace('.', '-')}/{p})" for p in
                     sorted(final_results[chapter])])  # Well this was fun to learn to do
            else:
                this_chapter += ", ".join(
                    [f"[{p}](https://guya.moe/read/manga/{series_dict[series]}/{chapter.replace('.', '-')}/{p})" for p
                     in sorted(final_results[chapter])])
            if len(search_desc) + len(this_chapter) <= 2048 and chapter_count < 10:
                search_desc += f"{this_chapter}\n"
            else:
                em.description = search_desc
                embeds.append(em)
                em = create_embed(len(embeds) + 1)
                search_desc = f"{this_chapter}\n"
                chapter_count = 0
        em.description = search_desc
        embeds.append(em)
        if len(embeds) > 1:
            for em in embeds:
                em.title += str(len(embeds))
            await dutils.SimplePaginator(extras=embeds).paginate(ctx)
        else:
            em.title += "1"
            await ctx.send(content=None, embed=embeds[0])

    # async def if_you_need_loop(self):
    #     await self.bot.wait_until_ready()
    #     while True:
    #         try:
    #             print("Code here")
    #         except:
    #             pass
    #         await asyncio.sleep(10)  # sleep here


async def setup(
        bot: commands.Bot
):
    ext = Manga(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
