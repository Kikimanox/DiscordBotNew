import asyncio
import datetime

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
        await self.execute_reminder(timer)

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

    async def create_timer(self, *, expires_on, meta, gid, reason, uid, len_str,
                           author_id, update_timer=False, orig_id=0):
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

        if not update_timer:
            try:
                if meta.startswith('mute'):
                    Reminderstbl.get(Reminderstbl.guild == gid,
                                     Reminderstbl.user_id == uid)
                    # Only insert below if not exists (1 user mute per guild)
            except:
                tim_id = Reminderstbl.insert(guild=gid, reason=reason, user_id=uid, len_str=len_str,
                                             expires_on=expires_on, executed_by=author_id, meta=meta).execute()
                timer.id = tim_id
        else:
            timer.id = orig_id

        if delta <= 40:
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


def setup(bot):
    ext = Reminders(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.refresh_timers_after_a_while()))
    bot.add_cog(ext)
