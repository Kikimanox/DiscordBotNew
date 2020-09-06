import asyncio
import datetime
import itertools

import discord
import pkg_resources
import psutil
import pygit2
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.process = psutil.Process()

    @commands.cooldown(1, 20, commands.BucketType.user)
    @commands.command()
    async def latency(self, ctx):
        """Check bot response time."""
        await ctx.send(f"Current latency **{round(self.bot.latency * 1000)}ms**")

    def get_bot_uptime(self, *, brief=False):
        return tutils.human_timedelta(self.bot.uptime, accuracy=None, brief=brief, suffix=False)

    @commands.command()
    async def uptime(self, ctx):
        """Check how long the bot has been up for."""
        if not hasattr(self.bot, 'ranCommands'): return await ctx.send("I am still starting up, hold on please.")
        await ctx.send(f'Uptime: **{self.get_bot_uptime()}**')

    def format_commit(self, commit):
        short, _, _ = commit.message.partition('\n')
        short_sha2 = commit.hex[0:6]
        commit_tz = datetime.timezone(datetime.timedelta(minutes=commit.commit_time_offset))
        commit_time = datetime.datetime.fromtimestamp(commit.commit_time).replace(tzinfo=commit_tz)

        # [`hash`](url) message (offset)
        offset = tutils.human_timedelta(commit_time.astimezone(datetime.timezone.utc).replace(tzinfo=None), accuracy=1)
        return f'[`{short_sha2}`](https://github.com/Kikimanox/DiscordBot/commit/{commit.hex}) {short} ({offset})'

    def get_last_commits(self, count=5):
        repo = pygit2.Repository('.git')
        commits = list(itertools.islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))
        return '\n'.join(self.format_commit(c) for c in commits)

    @commands.command()
    async def about(self, ctx):
        """Tells you information about the bot itself."""
        if not hasattr(self.bot, 'uptime'): return await ctx.send("I am still starting up, hold on please.")
        revision = self.get_last_commits()
        itext = 'Made by: <@!174406433603846145> (Kiki#0002)\n' \
                'Special thanks to Appu for the help with learning how to make the bot.'
        embed = discord.Embed(description=itext + '\n\nLatest Changes:\n' + revision)
        embed.title = 'About page'
        # embed.url = 'https://discord.gg/DWEaqMy'
        embed.colour = ctx.bot.config['BOT_DEFAULT_EMBED_COLOR']

        owner = self.bot.get_user(ctx.bot.config['OWNER_ID'])
        embed.set_author(name=str(owner), icon_url=owner.avatar_url)

        # statistics
        total_members = 0
        total_online = 0
        offline = discord.Status.offline
        for member in self.bot.get_all_members():
            total_members += 1
            if member.status is not offline:
                total_online += 1

        total_unique = len(self.bot.users)

        text = 0
        voice = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice += 1

        embed.add_field(name='Members',
                        value=f'{total_members} total\n{total_unique} unique\n{total_online} unique online')
        embed.add_field(name='Channels', value=f'{text + voice} total\n{text} text\n{voice} voice')

        try:
            memory_usage = self.process.memory_full_info().uss / 1024 ** 2
            cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
            embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')
        except:
            embed.add_field(name='Process', value=f'Process is not allowing viewing CPU usage.')

        version = pkg_resources.get_distribution('discord.py').version
        embed.add_field(name='Guilds', value=str(guilds))
        embed.add_field(name='Commands Ran', value=self.bot.ranCommands)
        embed.add_field(name='Uptime', value=self.get_bot_uptime(brief=True))
        embed.set_footer(text=f'Made with discord.py v{version}', icon_url='http://i.imgur.com/5BFecvA.png')
        embed.timestamp = datetime.datetime.utcnow()
        await ctx.send(embed=embed)

def setup(bot):
    ext = Stats(bot)
    bot.add_cog(ext)
