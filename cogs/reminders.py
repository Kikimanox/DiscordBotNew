import asyncio
import datetime
import re

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback

from models.serversetup import SSManager
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
from models.moderation import Reminderstbl


class Timer:
    def __init__(self, *, record):
        self.id = record['id']
        self.meta = record['meta']
        self.guild = record['guild']
        self.reason = record['reason']
        self.user_id = record['user_id']
        self.len_str = record['len_str']
        self.expires = record['expires_on']
        self.executed_by = record['executed_by']

    @classmethod
    def temporary(cls, *, expires, meta, guild, reason, user_id, len_str, executed_by):
        pseudo = {
            'id': None,
            'meta': meta,
            'guild': guild,
            'reason': reason,
            'user_id': user_id,
            'len_str': len_str,
            'expires_on': expires,
            'executed_by': executed_by,
        }
        return cls(record=pseudo)


class Reminders(commands.Cog):
    def __init__(self, bot):
        # Credit to RoboDanny for timeout code help
        self.bot = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = self.bot.loop.create_task(self.dispatch_timers())
        self.tried_setup = False

    def cog_unload(self):
        self._task.cancel()

    @commands.command()
    async def tt(self, ctx):
        """aaa"""
        print("k")

    async def set_server_stuff(self):
        if not self.tried_setup:
            self.tried_setup = True
            if not self.bot.from_serversetup:
                self.bot.from_serversetup = await SSManager.get_setup_formatted(self.bot)

    async def execute_reminder(self, timer: Timer):
        if timer.meta.startswith('mute'):
            guild = self.bot.get_guild(timer.guild)
            if guild:
                user = guild.get_member(timer.user_id)
                if user:
                    can_even_execute = True
                    sup = None
                    if guild.id in self.bot.from_serversetup:
                        sup = self.bot.from_serversetup[guild.id]
                        if not sup['muterole']: can_even_execute = False
                    else:
                        can_even_execute = False
                    if can_even_execute:
                        no_dm = bool(timer.meta == 'mute_nodm')
                        await dutils.unmute_user_auto(user, guild, self.bot, no_dm,
                                                      self.bot.user, "Auto")

    async def short_timer_optimisation(self, seconds, timer):
        await asyncio.sleep(seconds)
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        await self.call_timer(timer)

    async def call_timer(self, timer: Timer):
        try:
            rm = Reminderstbl.get(Reminderstbl.id == timer.id)
            rm.delete_instance()
        except:
            pass
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        await self.execute_reminder(timer)

    async def dispatch_timers(self):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                timer = self._current_timer = await self.wait_for_active_timers(days=30)
                now = datetime.datetime.utcnow()

                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)

        except asyncio.CancelledError:
            print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            print("Raise happened in dispatch_timers")
            self.bot.logger.error(traceback.format_exc())
            raise
        except(OSError, discord.ConnectionClosed):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

    @staticmethod
    async def get_active_timer(days=7):
        now = datetime.datetime.utcnow()
        record = Reminderstbl.select().where(Reminderstbl.expires_on < (now + datetime.timedelta(days=days))).limit(1)
        return Timer(record=record.dicts()[0]) if record else None

    async def wait_for_active_timers(self, days=7):
        timer = await self.get_active_timer(days=days)
        if timer is not None:
            self._have_data.set()
            return timer

        self._have_data.clear()
        self._current_timer = None
        await self._have_data.wait()
        return await self.get_active_timer(days=days)

    async def create_timer(self, *, expires_on, meta, gid, reason, uid, len_str, author_id, should_update=False):
        now = datetime.datetime.utcnow()
        if not expires_on:
            expires_on = datetime.datetime.max
        delta = (expires_on - now).total_seconds()
        timer = Timer.temporary(
            expires=expires_on,
            meta=meta,
            guild=gid,
            reason=reason,
            user_id=uid,
            len_str=len_str,
            executed_by=author_id
        )
        # Insert into REMINDERSTABLE here
        try:
            if not should_update:
                raise

            # due to race conditions with MUTE we check if it's still in the db
            rem = Reminderstbl.get(Reminderstbl.guild == gid,
                                   Reminderstbl.user_id == uid)

            rem.len_str = len_str
            rem.expires_on = expires_on
            rem.executed_by = author_id
            rem.reason = reason
            rem.save()
            timer.id = rem.id
        except:
            # Only insert if not exists (1 user mute per guild)
            tim_id = Reminderstbl.insert(guild=gid, reason=reason, user_id=uid, len_str=len_str,
                                         expires_on=expires_on, executed_by=author_id, meta=meta).execute()
            timer.id = tim_id

        if delta <= 30:
            self.bot.loop.create_task(self.short_timer_optimisation(delta, timer))
            return timer

        # only set the data check if it can be waited on
        if delta <= (86400 * 40):  # 40 days
            self._have_data.set()

        # check if this timer is earlier than our currently run timer
        if self._current_timer and expires_on < self._current_timer.expires:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    async def refresh_timers_after_a_while(self):
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(86400 * 5)  # every 5 days
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command()
    async def remind(self, ctx, *, text):
        """Set a reminder.

        Remind a channel or yourself.

        - Reminding youself, use **me**
        - Reminding a channel, mention that channel or supply it's id or name

        Structure: **[p]remind [me|channel] [the reminder's content] [when]**

        Regarding the **[when]** part, please use the folloing format x[d|h|m|s]{y[h|m|s]}{y[m|s]}, examples:
        - in 1h
        - in 2d
        - in 1h30m
        (those will trigger after an hour, two days, an hour and thirty minutes)
        **__or use:__** 🆕
        - at 23:50
        - on YYYY M D [h m s]
        (hour is optional, defaults to midnight if left empty)

        > Please don't try to use **at** and **on** at once, use only one

        Command examples:

        `[p]remind me take out the trash in 2h`
        `[p]remind #general Hey, ten days have passed in 10d`
        `[p]remind 2953845243582 That's general's channel id btw. in 1m`
        `[p]remind me Something at 23:50` (today sometime) (time is in UTC) 🆕
        `[p]remind me Something on 2020/10/14 16:25` 🆕
        """
        await self.remindFunction(ctx, text)

    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command(aliases=["rm"])
    async def remindme(self, ctx, *, text):
        """Same as doing .remind me

        This is just a shorter version of doing [p]remind me something in Xh

        So you do `[p]rm take out the trash in 2h` instead of `[p]remind me take out the trash in 2h`"""
        await self.remindFunction(ctx, f'me {text}')

    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.check(checks.moderator_check)
    @commands.command(aliases=["rro"])
    async def remindrole(self, ctx, role: discord.Role, *, text):
        """Same as doing .remind me plus a role ping

        Remind role: When you create this reminder, it will automatically make the
        selected role by id pingable and will ping it after the reminder is triggered
        (after the ping the role will be unpinable again or left pingable if it was b4)

        Example: [p]rro 1231432432 #movie-night Hey peeps with the role id 12314.... Movie time in 15h"""
        # r = discord.utils.get(ctx.guild.roles, id=int(roleID))
        if role.is_default():
            return await ctx.send('Cannot use the @\u200beveryone role.')
        if role > ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('This role is higher than your highest role.')
        if role > ctx.me.top_role:
            return await ctx.send('This role is higher than my highest role.')
        await self.remindFunction(ctx, text, role)

    async def remindFunction(self, ctx, text, rolePing=None):
        try:
            timestamp = datetime.datetime.utcnow()
            remind_time = timestamp
            who = ctx.author
            by = who

            firstPart = text.split(' ')[0]
            idx2 = text.rfind('in')
            idx3 = text.rfind('on')
            idx4 = text.rfind('at')
            match2 = re.findall(r"(in [0-9]+[smhd][0-9]*[smh]*[0-9]*[sm]*$)", text)
            match3 = re.findall(r"(on [0-9].*?$)", text)
            match4 = re.findall(r"(at [0-9].*?$)", text)
            not2 = False
            not3 = False
            not4 = False
            if idx2 == -1 or not match2: not2 = True
            if idx3 == -1 or not match3: not3 = True
            if idx4 == -1 or not match4: not4 = True
            if not2 and not3 and not4:
                return await ctx.send("You forgot the `in/on/at` at the end. If needed check the commands help.")
            idx = 0
            if match2: idx = idx2
            if match3: idx = idx3
            if match4: idx = idx4

            lastPart = text[idx + 3::]
            midPart = text[len(firstPart) + 1:idx - 1]
            if not midPart: return await ctx.send("You forgot the reminders content.")
            if not lastPart: return await ctx.send("You forgot to set when to set of the reminder.")

            if firstPart != 'me':
                isMod = await checks.moderator_check(ctx)
                if not isMod: return await ctx.send(
                    "Only moderators and admins may set the reminder's target to be a channel.\n"
                    "You can however remind yourself to do something by replacing the channel name with `me`. "
                    "(Check command's help for more details)")
                ch = await dutils.getChannel(ctx, firstPart)
                if not ch: return
                who = ch

            if idx == idx2:  # in
                unitss = ['d', 'h', 'm', 's']
                for u in unitss:
                    cnt = lastPart.count(u)
                    if cnt > 1: return await ctx.send(f"Error, you used **{u}** twice for the timer, don't do that.")

                units = {
                    "d": 86400,
                    "h": 3600,
                    "m": 60,
                    "s": 1
                }
                seconds = 0
                match = re.findall("([0-9]+[smhd])", lastPart)  # Thanks to 3dshax server's former bot
                if not match:
                    p = dutils.bot_pfx_by_ctx(ctx)
                    return await ctx.send(f"Could not parse length. Are you using "
                                          f"the right format? Check help for details (`{p}help remind` .. "
                                          f"or just `{p}remind`)")
                try:
                    for item in match:
                        seconds += int(item[:-1]) * units[item[-1]]
                    if seconds <= 10:
                        return await ctx.send("Reminder can't be less than 10 seconds from now!")
                    delta = datetime.timedelta(seconds=seconds)
                except OverflowError:
                    return await ctx.send("Reminder time too long. Please input a shorter time.")
                remind_time = timestamp + delta

            if idx == idx3 or idx == idx4:  # on / at
                if idx == idx4:
                    lastPart = f'{timestamp.year} {timestamp.month} {timestamp.day} {lastPart}'
                remind_time, err = tutils.get_time_from_str_and_possible_err(lastPart)
                if err:
                    return await ctx.send(err)

            if remind_time <= timestamp:
                return await ctx.send("Remind time can not be in the past.")
            if remind_time - datetime.timedelta(seconds=10) <= timestamp:
                return await ctx.send("Reminder can't be less than 10 seconds from now!")

            meta = 'reminder_'
            if by.id == who.id:
                meta += 'me'
            if rolePing:
                meta += f'rolePing_{rolePing.id}'
            tim = await self.create_timer(
                expires_on=remind_time,
                meta=meta,
                gid=0 if not ctx.guild else ctx.guild.id,
                reason=midPart.replace('@', '@\u200b'),
                uid=who.id,  # This is the target user or channel
                len_str=remind_time.strftime('%Y/%m/%d %H:%M:%S'),  # used to show when
                author_id=by.id
            )

            cnt = f"⏰  |  **Got it! The reminder has been set up.**"
            desc = f"**Id:** {tim.id}\n" \
                   f"**Target:** {who.mention}\n" \
                   f"**Triggered on:** {tim.len_str}"
            if rolePing:
                await ctx.send(
                    embed=Embed(title='Reminder info', description=f"{desc}\n\nAlongside this reminder "
                                                                   f"the role {rolePing.mention} will be pinged"),
                    content=cnt)
            else:
                await ctx.send(embed=Embed(title='Reminder info', description=desc), content=cnt)
        except:
            print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            traceback.print_exc()
            await ctx.send("Something went wrong")


def setup(bot):
    ext = Reminders(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.refresh_timers_after_a_while()))
    bot.add_cog(ext)
