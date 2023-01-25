import asyncio
import datetime
import itertools
from collections import Counter, defaultdict
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
from models.bot import BotBlacklist, BotBanlist


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
        return f'[`{short_sha2}`](https://github.com/Kikimanox/DiscordBotNew/commit/{commit.hex}) {short} ({offset})'

    def get_last_commits(self, count=5):
        repo = pygit2.Repository('.git')
        commits = list(itertools.islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))
        return '\n'.join(self.format_commit(c) for c in commits)

    @commands.command()
    async def about(self, ctx):
        """Tells you information about the bot itself."""
        if not hasattr(self.bot, 'uptime'): return await ctx.send("I am still starting up, hold on please.")
        revision = self.get_last_commits()
        inv = discord.utils.oauth_url(ctx.bot.user.id) + '&permissions=8'
        itext = f'Made by: <@!174406433603846145> (Kiki#0002)\n' \
                f'Special thanks to Appu for the help with learning how to make the bot.\n' \
                f'[Bot invite link (currently not public)]({inv})'
        embed = discord.Embed(description=itext + '\n\nLatest Changes:\n' + revision)
        embed.title = 'About page'
        # embed.url = 'https://discord.gg/DWEaqMy'
        embed.colour = ctx.bot.config['BOT_DEFAULT_EMBED_COLOR']

        owner = self.bot.get_user(ctx.bot.config['OWNER_ID'])
        embed.set_author(name=str(owner), icon_url=owner.display_avatar.url)

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
        embed.add_field(name='Commands Ran', value=sum(self.bot.command_stats.values()))
        embed.add_field(name='Uptime', value=self.get_bot_uptime(brief=True))
        embed.set_footer(text=f'Made with discord.py v{version}', icon_url='http://i.imgur.com/5BFecvA.png')
        embed.timestamp = datetime.datetime.utcnow()
        await ctx.send(embed=embed)

    @commands.command(aliases=['hp'])
    @commands.check(checks.owner_check)
    async def bothealth(self, ctx):
        """Various bot health monitoring tools."""

        # This uses a lot of private methods because there is no
        # clean way of doing this otherwise.

        HEALTHY = discord.Colour(value=0x43B581)
        UNHEALTHY = discord.Colour(value=0xF04947)
        WARNING = discord.Colour(value=0xF09E47)
        total_warnings = 0

        embed = discord.Embed(title='Bot Health Report', colour=HEALTHY)

        description = []

        arl = 0
        if ctx.guild and ctx.guild.id in ctx.bot.anti_raid:
            arl = ctx.bot.anti_raid[ctx.guild.id]['anti_raid_level']
        spam_control = self.bot.spam_control[arl]
        # a = spam_control._cache.items()
        being_spammed = [
            str(key) for key, value in spam_control._cache.items()
            if value._tokens == 0
        ]
        if being_spammed: being_spammed = '\n' + ", ".join(being_spammed)
        description.append(f'Current Spammers (bucket): {being_spammed or "**None**"}')

        if being_spammed:
            embed.colour = WARNING
            total_warnings += 1

        spam_control = self.bot.spam_control[-1]
        # a = spam_control._cache.items()
        being_spammed_dm = [
            str(key) for key, value in spam_control._cache.items()
            if value._tokens == 0
        ]
        if being_spammed_dm: being_spammed_dm = '\n' + ", ".join(being_spammed_dm)
        description.append(f'Dm Spammers (bucket): {being_spammed_dm or "**None**"}')

        if being_spammed_dm:
            embed.colour = WARNING
            total_warnings += 1

        try:
            task_retriever = asyncio.Task.all_tasks
        except AttributeError:
            # future proofing for 3.9 I guess
            task_retriever = asyncio.all_tasks
        else:
            all_tasks = task_retriever(loop=self.bot.loop)

        event_tasks = [
            t for t in all_tasks
            if 'Client._run_event' in repr(t) and not t.done()
        ]

        cogs_directory = os.path.dirname(__file__)
        tasks_directory = os.path.join('discord', 'ext', 'tasks', '__init__.py')
        inner_tasks = [
            t for t in all_tasks
            if cogs_directory in repr(t) or tasks_directory in repr(t)
        ]

        bad_inner_tasks = ", ".join(hex(id(t)) for t in inner_tasks if t.done() and t._exception is not None)
        total_warnings += bool(bad_inner_tasks)
        embed.add_field(name='Inner Tasks', value=f'Total: **{len(inner_tasks)}**\nFailed: '
                                                  f'**{bad_inner_tasks or "None"}**')
        embed.add_field(name='Events Waiting', value=f'Total: **{len(event_tasks)}**', inline=False)

        command_waiters = self.bot.before_run_cmd - 1  # Because this one will be counted
        description.append(f'Commands Waiting: **{command_waiters}**')

        try:
            memory_usage = self.process.memory_full_info().uss / 1024 ** 2
            cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
            embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU', inline=False)
        except:
            embed.add_field(name='Process', value=f'Process does not allow memory and CPU usage view', inline=False)

        global_rate_limit = not self.bot.http._global_over.is_set()
        description.append(f'Global Rate Limit: **{global_rate_limit}**')

        if command_waiters >= 8:
            total_warnings += 1
            embed.colour = WARNING

        if global_rate_limit or total_warnings >= 9:
            embed.colour = UNHEALTHY

        embed.set_footer(text=f'{total_warnings} warning(s)')
        embed.description = '\n'.join(description)
        await ctx.send(embed=embed)

    async def register_command(self, ctx):
        if ctx.command is None:
            return
        command = ctx.command.qualified_name
        self.bot.command_stats[command] += 1

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        await self.register_command(ctx)

    @commands.command(aliases=['cmdss'])
    @commands.check(checks.owner_check)
    async def commandstats(self, ctx, limit=20):
        """Shows command stats.
        Use a negative number for bottom instead of top.
        This is only for the current session.
        """
        if len(self.bot.command_stats) == 0:
            return await ctx.send("No ran commands yet")
        counter = self.bot.command_stats
        width = len(max(counter, key=len))
        total = sum(counter.values())

        if limit > 0:
            common = counter.most_common(limit)
        else:
            common = counter.most_common()[limit:]

        output = '\n'.join(f'{k :<{width + 1}}| {c}' for k, c in common)
        ic = dutils.get_icon_url_for_member(ctx.bot.user)
        await ctx.send(embed=Embed(description=output,
                                   color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'])
                       .set_author(icon_url=ic, name="Comand statistics"))

    @commands.command(aliases=['bb'], hidden=True)
    @commands.check(checks.owner_check)
    async def lsbotblacklist(self, ctx, limit=20):
        """Show blacklisted users up to a limit"""
        await self.botbl_disp(ctx, limit, self.bot.blacklist, "Bot blacklist")

    @commands.command(aliases=['bbb'], hidden=True)
    @commands.check(checks.owner_check)
    async def lsbotbanlist(self, ctx, limit=20):
        """Show banned users up to a limit"""
        await self.botbl_disp(ctx, limit, self.bot.banlist, "Bot banlist")

    @staticmethod
    async def botbl_disp(ctx, limit, bb, title):
        if not bb:
            return await ctx.send(f"{title} is empty")
        users = [(k, v) for k, v in bb.items()]
        output = '\n'.join(f'{k} : {c}' for k, c in users[:limit])
        await ctx.send(embed=Embed(description=f'{output}', title=title))

    @commands.cooldown(1, 60 * 60 * 7, commands.BucketType.user)
    @commands.command(hidden=True)
    async def unblacklistme(self, ctx):
        """Remove yourself from the blacklist"""
        if ctx.author.id in ctx.bot.blacklist:
            BotBlacklist.delete().where(BotBlacklist.user == ctx.author.id).execute()
            del ctx.bot.blacklist[ctx.author.id]
            await ctx.send("\N{WHITE HEAVY CHECK MARK} You have "
                           "been removed from the blacklist.")
        else:
            await ctx.send("\N{CROSS MARK} You are not blacklisted")
            ctx.command.reset_cooldown(ctx)

    @commands.command()
    @commands.check(checks.admin_check)
    async def botunblacklist(self, ctx, user_ids: commands.Greedy[int]):
        """Unblacklist user by id [Admin only]"""
        ret = ''
        for user_id in user_ids:
            if user_id in ctx.bot.blacklist:
                del ctx.bot.blacklist[user_id]
                BotBlacklist.delete().where(BotBlacklist.user == user_id).execute()
            else:
                ret += f"{user_id} is not blacklisted from the bot.\n"
        await ctx.send("Done." if not ret else ret + 'Done.')

    @commands.command()
    @commands.check(checks.admin_check)
    async def botunban(self, ctx, user_ids: commands.Greedy[int]):
        """Unban user by id [Admin only]"""
        ret = ''
        for user_id in user_ids:
            if user_id in ctx.bot.banlist:
                del ctx.bot.banlist[user_id]
                BotBanlist.delete().where(BotBanlist.user == user_id).execute()
            else:
                ret += f"{user_id} is not banned from the bot.\n"
        await ctx.send("Done." if not ret else ret + '\nDone.')


def setup(bot):
    if not hasattr(bot, 'command_stats'):
        bot.command_stats = Counter()

    # in case of even further spam, add a cooldown mapping
    # for people who excessively spam commands
    bot.spam_control = {
        -1: commands.CooldownMapping.from_cooldown(6, 8, commands.BucketType.user),
        0: commands.CooldownMapping.from_cooldown(7, 12, commands.BucketType.user),
        1: commands.CooldownMapping.from_cooldown(4, 4, commands.BucketType.user),
        2: commands.CooldownMapping.from_cooldown(3, 4, commands.BucketType.user),
        3: commands.CooldownMapping.from_cooldown(3, 4, commands.BucketType.user)
    }

    # A counter to auto-ban frequent spammers
    # Triggering the rate limit 5 times in a row will auto-ban the user from the bot.
    bot._auto_spam_count = Counter()

    bot.blacklist = {}
    bs = [q for q in BotBlacklist.select().dicts()]
    for b in bs:  bot.blacklist[b['user']] = b['meta']

    bot.banlist = {}
    bs = [q for q in BotBanlist.select().dicts()]
    for b in bs:  bot.banlist[b['user']] = b['meta']

    ext = Stats(bot)
    bot.add_cog(ext)
