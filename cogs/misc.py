import asyncio
import datetime

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
import random
import re


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @commands.command()
    async def say(self, ctx, channel: discord.TextChannel, *, text=""):
        """Say something in a specified channel

        Will also send any/all attached images if any. Usage examples:

        `[p]say #nino` *(and uploading an image while doing the cmd will just send the pic)*
        `[p]say #nino I am best girl`
        `[p]say nino I am indeed best girl`
        `[p]say 424792705529544725 Hmpf, I'm still best girl`
        `[p]say #community-upadtes
        Some long text for community upates
        can also have new lines and emotes and
        links etc.... Goes here`"""

        # ch = await dutils.getChannel(ctx, channel)
        ch = channel
        if not text and len(ctx.message.attachments) == 0: return await ctx.send('Please supply text or at least '
                                                                                 'one attachment')
        atts = []
        if len(ctx.message.attachments) > 0:
            try:
                was = await ctx.channel.send('Wait a second.. saving temporary files')
                with ctx.channel.typing():
                    atts = [await a.to_file(spoiler=a.is_spoiler()) for a in ctx.message.attachments]
                    await was.delete()
            except:
                return await ctx.send('Something went wrong with the `say` command')

        w1 = await ctx.channel.send('**Do you want to see a preview of the message?** (y/n) '
                                    '(if **n** is chosen the message will be posted immediately)'
                                    ' *(You have 20 seconds to respond)*')

        def check(m):
            return (m.content.lower() == 'y' or m.content.lower() == 'n') and \
                   m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await self.bot.wait_for("message", check=check, timeout=20)
        except asyncio.TimeoutError:
            return await ctx.send("Cancelled.")
        if not reply or reply.content.lower().strip() == 'n':
            await w1.delete()
            await reply.delete()
        else:
            await w1.delete()
            await ctx.channel.send('```PREVIEW BELOW```')
            if len(atts) > 0:
                async with ctx.channel.typing():
                    await ctx.channel.send(text, files=atts)
            else:
                await ctx.channel.send(text)
            w2 = await ctx.channel.send(f'```PREVIEW ABOVE```\nDo you want to send this message to {ch.mention} (y/n)')
            try:
                reply2 = await self.bot.wait_for("message", check=check, timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("Cancelled.")
            if not reply2 or reply2.content.lower().strip() == 'n':
                return await ctx.send("Cancelled.")
            else:
                await w2.delete()
                if len(atts) > 0:
                    async with ctx.channel.typing():
                        await ch.send(text, files=atts)
                        return await ctx.send(f'Posted in {ch.mention}')
                else:
                    await ch.send(text)
                    return await ctx.send(f'Posted in {ch.mention}')
        if len(atts) > 0:
            async with ctx.channel.typing():
                await ch.send(text, files=atts)
                return await ctx.send(f'Posted in {ch.mention}')
        else:
            await ch.send(text)
            return await ctx.send(f'Posted in {ch.mention}')

    @commands.check(checks.owner_check)
    @commands.command(aliases=["qs"])
    async def quicksay(self, ctx, channel: discord.TextChannel, *, text: str = ""):
        """Say something in a specified channel quickly"""
        if not text and not ctx.message.attachments:
            return await ctx.send("You forgot the content or attachements")
        atts = []
        if len(ctx.message.attachments) > 0:
            try:
                with ctx.channel.typing():
                    atts = [await a.to_file(spoiler=a.is_spoiler()) for a in ctx.message.attachments]
            except:
                traceback.print_exc()
                return await ctx.send('Something went wrong with the `qs` command')
        await ctx.message.delete()
        async with ctx.channel.typing():
            await channel.send(text, files=atts)

    @commands.cooldown(3, 10, commands.BucketType.user)
    @commands.command()
    async def choose(self, ctx, *, options: str):
        """Split options with | and have the bot pick one of them"""
        opts = options.split('|')
        if len(options) < 2:
            return await ctx.send(f"You need to provite at least two options, cmd ex.: `{dutils.bot_pfx_by_ctx(ctx)}"
                                  f"choose one | two | three`")
        await ctx.send(embed=Embed(color=self.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                                   description=f'🤔 Hmmm, I choose: **{(random.choice(opts)).strip()}**'))



    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.check(checks.manage_emojis_check)
    @commands.command(aliases=['addemotes', "ae"])
    async def addemote(self, ctx, *, emotes):
        """Add emotes to the server.

        `[p]addemote newEmoteName image_url`
        Ex: `[p]addemote ninosmug https://domain/ninopic.png`
        `[p]addemote name url name2 url2` - (etc., can add multiple at once)"""
        await self.add_emote_or_yoink(ctx, emotes, False)

    @commands.check(checks.owner_check)
    @commands.command()
    async def yoink(self, ctx, *, emotes):
        """Yoink some emotes:

        `[p]yoink name url`
        `[p]yoink name url name2 url2` (etc., can have multiple)"""
        await self.add_emote_or_yoink(ctx, emotes, True)

    async def add_emote_or_yoink(self, ctx, emotes, yoink):
        emotes = str(emotes).replace('\n', ' ') + ' '
        await ctx.message.delete()
        member = ctx.author
        icon_url = member.avatar_url if 'gif' in str(member.avatar_url).split('.')[-1] else str(
            member.avatar_url_as(format="png"))
        await ctx.send(embed=Embed(description=ctx.message.content, color=ctx.author.color)
                       .set_author(name=f"{'Add' if not yoink else 'Yoink'} emotes command invoked",
                                   icon_url=icon_url))
        if not yoink: yo = await ctx.send('Adding ...')
        else: yo = await ctx.send("Yoinking ...")
        p = re.compile(r'(\w+)\s*\s\s*(.*?)\s+')
        for e in p.finditer(emotes):
            name = e.group(1).strip()
            try:
                url = e.group(2).strip().split('?')[0]
                ext = url.split('.')[-1]
                if not yoink:
                    renEm, err = await dutils.add_tmp_emote(self.bot, ctx, name, url, ext, ctx.guild.id, True)
                else:
                    renEm, err = await dutils.add_tmp_emote(self.bot, ctx, name, url, ext, 0, True)
                if renEm:
                    await ctx.send(f"{'Added' if not yoink else 'Yoinked'} {renEm}")
                else:
                    await ctx.send(err)
            except:
                nn = name.replace('@', '@\u200b')
                await ctx.send(f'Something went wrong when trying to add **{nn}**')
        await yo.delete()


def setup(bot):
    ext = Misc(bot)
    bot.add_cog(ext)
