import asyncio
import datetime
import re

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback

from models.serversetup import SSManager
from utils.SimplePaginator import SimplePaginator
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
from models.moderation import Reminderstbl, Timezones


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
        self.executed_on = record['executed_on']

    @classmethod
    def temporary(cls, *, expires, meta, guild, reason, user_id, len_str, executed_by, executed_on):
        pseudo = {
            'id': None,
            'meta': meta,
            'guild': guild,
            'reason': reason,
            'user_id': user_id,
            'len_str': len_str,
            'expires_on': expires,
            'executed_by': executed_by,
            'executed_on': executed_on,
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
        if timer.meta.startswith('reminder_'):
            exec_user = self.bot.get_user(timer.executed_by)
            guild = self.bot.get_guild(timer.guild)
            if timer.meta == 'reminder_me':
                if exec_user:
                    try:
                        return await exec_user.send(timer.reason)
                    except:
                        pass  # oh well ... we tried
            elif timer.meta.startswith('reminder_rolePing_'):
                if guild:
                    role: discord.Role = discord.utils.get(guild.roles, id=int(timer.meta.split('_')[-1]))
                    if role:
                        target_ch = guild.get_channel(timer.user_id)
                        if target_ch:
                            was_mentionable = role.mentionable
                            if not was_mentionable:
                                try:
                                    await role.edit(mentionable=True, reason=f"{exec_user} made a rro with this role")
                                except:
                                    pass
                            try:
                                await target_ch.send(f"{role.mention} {timer.reason}")
                            except:
                                pass
                            if not was_mentionable:
                                try:
                                    await role.edit(mentionable=False, reason=f"{exec_user} made a rro with this role "
                                                                              f"(reverting back to unmentionable)")
                                except:
                                    pass

            else:
                if guild:
                    target_ch = guild.get_channel(timer.user_id)
                    if target_ch:
                        try:
                            await target_ch.send(timer.reason)
                        except:
                            pass

    async def short_timer_optimisation(self, seconds, timer):
        await asyncio.sleep(seconds)
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        await self.call_timer(timer)

    async def call_timer(self, timer: Timer):
        try:
            rm: Reminderstbl = Reminderstbl.get(Reminderstbl.id == timer.id)
            # this is only for some weird race conciditons
            if timer.executed_on != rm.executed_on:
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.dispatch_timers())
                return
            if rm.periodic != 0:
                rm.expires_on = rm.expires_on + datetime.timedelta(seconds=rm.periodic)
                rm.save()
            else:
                rm.delete_instance()
        except:
            return  # reminder should have been executed but it was deleted
            # and no other reminders have been created during that time. Just return here.
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
            raise  # a timer with a shorter time has beeb found
        except(OSError, discord.ConnectionClosed):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

    @staticmethod
    async def get_active_timer(days=7):
        now = datetime.datetime.utcnow()
        record = Reminderstbl.select().where(Reminderstbl.expires_on < (now + datetime.timedelta(days=days))).order_by(
            +Reminderstbl.expires_on
        ).limit(1)

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
            executed_by=author_id,
            executed_on=0  # tmp value
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
            timer.executed_on = rem.executed_on
        except:
            # Only insert if not exists (1 user mute per guild)
            tim_id = Reminderstbl.insert(guild=gid, reason=reason, user_id=uid, len_str=len_str,
                                         expires_on=expires_on, executed_by=author_id, meta=meta).execute()
            timer.id = tim_id
            timer.executed_on = (Reminderstbl.get_by_id(tim_id)).executed_on

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

    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.command(aliases=['mutc', 'setmyutc'])
    async def myutc(self, ctx, new_utc: float):
        """Set your utc so you don't need to use UTC time for reminding

        if your timezone is UTC+2 use:
        `[p]setmyutc 2`
        if your timezone is UTC+3.5 use:
        `[p]setmyutc 3.5`
        if your timezone is UTC+12.45 use:
        `[p]setmyutc 12.45`
        If your timezone is UTC-9 use:
        `[p]setmyutc -9`
        If your timezone is UTC or you want to reset use:
        `[p]setmyutc 0`

        Why is this useful? Simple, when doing remind commands
        you won't have to convert the time to uct anymore, but the
        bot will do that for you. **And you can use your own time
        for setting any reminder.** 🎉
        """
        new_utc = round(new_utc * 4) / 4
        if new_utc < -12: return await ctx.send(embed=Embed(description='[Min offset is -12](https://en.wikipedia.org/w'
                                                                        'iki/List_of_UTC_time_offsets)'))
        if new_utc > 14: return await ctx.send(embed=Embed(description='[Max offset is 14](https://en.wikipedia.org/w'
                                                                       'iki/List_of_UTC_time_offsets)'))

        Timezones.insert(user=ctx.author.id, utc_offset=new_utc).on_conflict_replace().execute()
        await ctx.send(f'When using remind commands your new utc offset will be **{new_utc}**'.replace('@', '@\u200b'))

    @commands.cooldown(3, 3, commands.BucketType.user)
    @commands.command()
    async def remind(self, ctx, *, text):
        """Set a reminder. (Please see `[p]myutc`)
         [Times are in UTC] (unless user set their timezone with ℹ `[p]myutc` ℹ)
        Structure: **[p]remind [me|channel] [the reminder's content] [when]**

        - Reminding youself, use **me** (you can use `[p]rm ...` instead of `[p]remind me ...`)

        Command examples:
        ℹ **All time inputs should use the 24 hour format (aka. don't use 3PM, use 15)**
        **When using the `on` format, be sure to use Y then M then D** (Y can be skipped)
        `[p]remind me take out the trash in 2h`
        `[p]remind #general Hey, ten days have passed in 10 days`
        `[p]remind 31232132 channel id btw. tomorrow at 15:50`
        `[p]remind me Something at 23:50` (today sometime)
        `[p]remind me Something on 2020/10/14 16:25` (no, this example isn't incorrect)
        `[p]remind me stuff on July 10th` (triggers at midnight July 10th)
        `[p]remind me stuff on 10. 12. at 14:55` (triggers on oct 12nd, at 14:55)
        `[p]remind me stuff at 3:25 on 3.3` (3rd march 3:25(AM))
        `[p]remind me stuff tomorrow at 3:25`
        `[p]remind me stuff at 3:25 tomorrow`
        `[p]rm stuff in 3 days 2hour 1sec`
        `[p]rm stuff in 3d2h1s`
        `[p]rm stuff in 24hours`
        `[p]rm stuff in 1 day`
        """
        await self.remindFunction(ctx, text)

    @commands.cooldown(3, 4, commands.BucketType.user)
    @commands.command(aliases=["rm"])
    async def remindme(self, ctx, *, text):
        """Same as doing .remind me

        This is just a shorter version of doing [p]remind me something in Xh

        So you do `[p]rm take out the trash in 2h` instead of `[p]remind me take out the trash in 2h`"""
        await self.remindFunction(ctx, f'me {text}')

    @commands.cooldown(3, 4, commands.BucketType.user)
    @commands.check(checks.moderator_check)
    @commands.command(aliases=["rro"])
    async def remindrole(self, ctx, role: discord.Role, *, text):
        """Same as doing .remind me plus a role ping

        Remind role: When you create this reminder, it will automatically make the
        selected role by id pingable and will ping it after the reminder is triggered
        (after the ping the role will be unpinable again or left pingable if it was b4)

        Example: `[p]rro 1231432432 #movie-night Hey peeps with the role id 12314.... Movie time in 15h`
        `[p]rro #general Muted lol you guys are muted at 15:30`
        """
        # r = discord.utils.get(ctx.guild.roles, id=int(roleID))
        if role.is_default():
            return await ctx.send('Cannot use the @\u200beveryone role.')
        if role > ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('This role is higher than your highest role.')
        if role > ctx.me.top_role:
            return await ctx.send('This role is higher than my highest role.')
        await self.remindFunction(ctx, text, role)

    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.command(aliases=["listreminders", "lsrm", "lsrms", "reminderslist", "reminderlist", 'rms'])
    async def reminders(self, ctx, only_check_this_id: int = 0):
        """Display all your ongoing reminders (or see just one) sorted by remind time"""
        if only_check_this_id < 0: return await ctx.send("Single reminder id can not be less than 0")
        if only_check_this_id == 0:
            reminders = Reminderstbl.select().where(Reminderstbl.executed_by == ctx.author.id,
                                                    Reminderstbl.meta.startswith('reminder_')).order_by(
                +Reminderstbl.expires_on)
        else:
            reminders = Reminderstbl.select().where(Reminderstbl.meta.startswith('reminder_'),
                                                    Reminderstbl.id == only_check_this_id)
            if not reminders:
                return await ctx.send(f"A reminder with that id does not exist. {ctx.author.mention}")
            reminder: Reminderstbl = reminders[0]
            if reminder.executed_by != ctx.author.id:
                return await ctx.send("The reminder with that id does not belong to you!")

        if not reminders:
            return await ctx.send(f"{ctx.author.mention} you have no ongoing reminders right now.")
        cnt = f"⏰  |  {ctx.author.mention} these are your current reminders."
        rms = []
        for r in reminders:
            reminder: Reminderstbl = r
            target = None
            g = self.bot.get_guild(reminder.guild)
            role = None
            rolePing = False
            if g:
                if reminder.executed_by == reminder.user_id: target = self.bot.get_user(reminder.executed_by)
                if not target: target = g.get_channel(reminder.user_id)
                if 'rolePing_' in reminder.meta:
                    rolePing = True
                    roleId = reminder.meta.split('rolePing_')[-1]
                    role = discord.utils.get(g.roles, id=int(roleId))

            p = "" if target else "~~"
            if target:
                target = target.mention
            if rolePing and not role: p = "~~"
            rol = ""
            if not role and rolePing:
                rol = "DELETED_ROLE"
            if role and rolePing:
                rol = role.name
            rsn = reminder.reason.replace('@', '@\u200b')
            desc = f"\n{p}**Id:** {reminder.id}{p}\n" \
                   f"{p}**Target:** {target}{p}\n" \
                   f"{p}**Triggers on:** {reminder.len_str}{p}\n" \
                   f"{p}**Reminder content:**{p}\n" \
                   f"{p}```\n{rsn if not rolePing else f'@{rol} {rsn}'}```{p}"
            if reminder.periodic != 0:
                desc += f'{p}🔁 **Periodic reminder:** every {tutils.convert_sec_to_smhd(reminder.periodic)}{p}\n'

            if not target or p == "~~":
                desc += '\n⚠ **Target or role is gone for some reason, deleting this reminder**'
                g.delete_instance()
            rms.append(desc)

        title = f"Reminders for {ctx.author}"
        le_max = 450
        txt = rms
        txt = txt[::-1]
        desc = ""
        desc_arr = []
        while len(txt) > 0:
            desc += txt.pop()
            if len(txt) == 0: break
            if len(desc) > le_max or len(desc) + len(txt[-1]) > 2000:
                desc_arr.append(desc)
                desc = ""
        if desc: desc_arr.append(desc)

        embeds = []
        for i in range(len(desc_arr)):
            em = Embed(title=title + f'\nPage {i + 1}/{len(desc_arr)}',
                       description=desc_arr[i], color=ctx.author.color)
            embeds.append(em)

        if len(embeds) == 1:
            embeds[0].title = title
            return await ctx.send(embed=embeds[0])
        else:
            return await SimplePaginator(extras=embeds).paginate(ctx)

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(aliases=["reminderremove", "rmrm", "rmr", "rmrs", "rmrms", "rmsrm",
                               "removereminders", "remindersremove"])
    async def removereminder(self, ctx, reminder_ids: commands.Greedy[int]):
        """Remove reminder(s) by id.

        `[p]rmr 1`, `[p] rmr 1 2 5 6`"""
        if not reminder_ids:
            await ctx.send("You are either missing the argument <reminder_ids> or you have inputed some non intiger "
                           "(number) symbols.\nPlease see the examples on how to use this commands.")
            raise commands.errors.BadArgument
        reminders = Reminderstbl.select().where(Reminderstbl.executed_by == ctx.author.id,
                                                Reminderstbl.meta.startswith('reminder_'),
                                                Reminderstbl.id << reminder_ids)
        if not reminders:
            return await ctx.send(f"You do not own any reminders with those ids {ctx.author.mention}")
        correct_ids = [r.id for r in reminders]
        will_delete = list(set(correct_ids) & set(reminder_ids))
        will_exclude = list(set(reminder_ids) - set(correct_ids))
        p = f"Deleting reminders with the id: **{', '.join([str(w) for w in will_delete])}**"
        if will_exclude: p += f"\n~~Excluding the following ids, because you don't own those reminders or they " \
                              f"don't exist: **{', '.join([str(w) for w in will_exclude])}**~~"
        if await dutils.prompt(ctx, p):
            d = Reminderstbl.delete().where(Reminderstbl.executed_by == ctx.author.id,
                                            Reminderstbl.meta.startswith('reminder_'),
                                            Reminderstbl.id << will_delete).execute()
            await ctx.send(f"Removed **{d}** reminder." if d == 1 else f"Removed **{d}** reminders.")
            # check if this timer is earlier than our currently run timer
        else:
            await ctx.send("Cancelled.")

    @commands.cooldown(3, 3, commands.BucketType.user)
    @commands.command(aliases=['mp'])
    async def makeperiodic(self, ctx, reminder_id: int, *, execute_every):
        """Make reminder periodic
        Example:
        `[p]makeperiodic 15 3hours` Execute every 3h
        `[p]makeperiodic 15 20m` Execute every 20 minutes

        To cancel the periodic nature, you have to delete the reminder.
        """
        reminder = Reminderstbl.select().where(Reminderstbl.meta.startswith('reminder_'),
                                               Reminderstbl.id == reminder_id)
        if not reminder:
            return await ctx.send(f"A reminder with that id does not exist. {ctx.author.mention}")
        reminder: Reminderstbl = reminder[0]
        if reminder.executed_by != ctx.author.id:
            return await ctx.send(f"The reminder with that id does not belong to you! {ctx.author.mention}")
        seconds, err = tutils.get_seconds_from_smhdw(execute_every)
        if err:
            return await ctx.send(err)
        if seconds < 60: return await ctx.send("Min periodic time is 60 seconds. Cancelling.")
        reminder.periodic = seconds
        reminder.save()
        ss = tutils.convert_sec_to_smhd(seconds)
        await ctx.send(f"Reminder with the id **{reminder_id}** is going to be executed again "
                       f"every **{ss}** after the next scheduled execution happens.")

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(aliases=["clearreminders", "clrrms", "rmsclr"])
    async def remindersclear(self, ctx):
        """Clear all your owned reminders"""
        confirm = await dutils.prompt(ctx, "Are you sure you want to clear **all** your reminders?")
        if not confirm:
            return await ctx.send("Cancelled.")

        reminders = Reminderstbl.select().where(Reminderstbl.executed_by == ctx.author.id,
                                                Reminderstbl.meta.startswith('reminder_'))
        if not reminders:
            return await ctx.send(f"You don't have any active reminders {ctx.author.mention}")

        d = Reminderstbl.delete().where(Reminderstbl.executed_by == ctx.author.id,
                                        Reminderstbl.meta.startswith('reminder_')).execute()

        await ctx.send(f"I've cleared all (**{d}**) of your reminders {ctx.author.mention}")

    async def remindFunction(self, ctx, text, rolePing=None):
        utc_offset = 0.0
        try:
            tz = Timezones.get(Timezones.user == ctx.author.id)
            utc_offset = tz.utc_offset
        except:
            pass
        try:
            timestamp = datetime.datetime.utcnow()
            utcnow = timestamp
            timestamp = timestamp + datetime.timedelta(hours=utc_offset)
            remind_time = timestamp
            who = ctx.author
            by = who

            firstPart = text.split(' ')[0]

            if firstPart != 'me':
                isMod = await checks.moderator_check(ctx)
                if not isMod: return await ctx.send(
                    "Only moderators and admins may set the reminder's target to be a channel.\n"
                    "You can however remind yourself to do something by replacing the channel name with `me`. "
                    "(Check command's help for more details)")
                ch = await dutils.getChannel(ctx, firstPart)
                if not ch: return
                who = ch

            mid_part, remind_time, error = await tutils.try_get_time_from_text(ctx, text, timestamp, firstPart,
                                                                               utc_offset=utc_offset)
            if error:
                return await ctx.send(error)

            diff = remind_time - timestamp
            if (diff.seconds < 30 and diff.days <= 0) or diff.days < 0:
                return await ctx.send("Reminder can't be less than 30 seconds in the future.")

            if remind_time <= timestamp:
                return await ctx.send("Remind time can not be in the past.")
            if remind_time - datetime.timedelta(seconds=10) <= timestamp:
                return await ctx.send("Reminder can't be less than 10 seconds from now!")

            meta = 'reminder_'
            if by.id == who.id:
                meta += 'me'
            if rolePing:
                meta += f'rolePing_{rolePing.id}'

            len_str = remind_time.strftime('%Y/%m/%d %H:%M:%S')
            if utc_offset != 0.0:
                len_str += f' UTC{"+" if utc_offset >= 0.0 else ""}{utc_offset}'
            else:
                len_str += ' UTC'
            tim = await self.create_timer(
                expires_on=remind_time - datetime.timedelta(hours=utc_offset),
                meta=meta,
                gid=0 if not ctx.guild else ctx.guild.id,
                reason=mid_part,
                uid=who.id,  # This is the target user or channel
                len_str=len_str,  # used to show when
                author_id=by.id
            )
            to_info = f'Reminder created: {ctx.author} {ctx.author.id} triggers on {len_str} ({tim.executed_on})'
            self.bot.logger.info(to_info)
            mid_part = mid_part.replace('@', '@\u200b')
            cnt = f"⏰  |  **Got it! The reminder has been set up.**"
            desc = f"**Id:** {tim.id}\n" \
                   f"**Target:** {who.mention}\n" \
                   f"**Triggers on:** {tim.len_str}\n" \
                   f"**Reminder content:**\n" \
                   f"```\n{mid_part if not rolePing else f'@{rolePing.name} {mid_part}'}```"
            if rolePing:
                em = Embed(title='Reminder info', description=f"{desc}\nAlongside this reminder "
                                                              f"the role {rolePing.mention} will be pinged")
                await ctx.send(embed=em, content=cnt)
            else:
                em = Embed(title='Reminder info', description=desc)
                await ctx.send(embed=em, content=cnt)
        except:
            # print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            # traceback.print_exc()
            await ctx.send(f"Something went wrong, please try again.")
            self.bot.logger.error(f"Something went wrong when making a reminder\n{traceback.format_exc()}")


def setup(bot):
    ext = Reminders(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.refresh_timers_after_a_while()))
    bot.add_cog(ext)
