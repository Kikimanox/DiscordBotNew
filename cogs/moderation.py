import asyncio
import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
import datetime

from models.moderation import (Mutes, Actions, Blacklist, ModManager)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.check(checks.ban_members_check)
    @commands.command(aliases=['prune'])
    async def purge(self, ctx, count: int, *users: discord.Member):
        """Clears a given number of messages or until the given message id.

        `[p]purge n` - purges the last n messages. Ex: .purge 100
        `[p]purge n @user` - purges all by @user in the last n messages. Ex: .purge 10 @kiki
        `[p]purge n @user1 @user2 @user3` - same as above but for more users
        `[p]purge <message_id>` - purges all up until specified msg. Ex: .purge 543075155458348436"""
        try:
            up_to = await ctx.channel.fetch_message(count)
        except discord.errors.NotFound:
            up_to = None
        if not up_to and count > 100:
            wait = await ctx.send(f"You are about to purge {count}. "
                                  f"Are you sure you want to purge these many messages? (y/n)")

            def check(m):
                return (m.content.lower() == 'y' or m.content.lower() == 'n') and \
                       m.author == ctx.author and m.channel == ctx.channel

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=10)
            except asyncio.TimeoutError:
                return await ctx.send("Cancelled purge.")
            if not reply or reply.content.lower().strip() == 'n':
                return await ctx.send("Cancelled purge.")
            else:
                await wait.delete()
                await ctx.message.delete()
        try:
            if up_to:
                deleted = await ctx.channel.purge(limit=None, after=up_to,
                                                  check=lambda message: message.author in users if users else True)
                await up_to.delete()
            else:
                deleted = await ctx.channel.purge(limit=count + 1,
                                                  check=lambda message: message.author in users if users else True)
            # print(f'{datetime.datetime.now().strftime("%c")} ({ctx.guild.id} | {str(ctx.guild)}) MOD LOG (purge): '
            #       f'{str(ctx.author)} ({ctx.author.id}) purged {len(deleted)} '
            #       f'messages in {str(ctx.channel)} ({ctx.channel.id})')
            await ctx.send(f"Purged **{len(deleted) - 1}** messages", delete_after=5)
        except discord.HTTPException:
            await ctx.send("Something went wrong! Could not purge.")

    @commands.check(checks.manage_channels_check)
    @commands.command()
    async def case(self, ctx, claim_id: int, *, reason):
        """Supply a reason to a claim witht out one"""
        pass

    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def mute(self, ctx, user: discord.Member, length="", *, reason=""):
        """Mutes a user. Please check usage with .help mute

        Supply a #d#h#m#s for a timed mute. Examples:
        `[p]mute @user` - will mute the user indefinitely
        `[p]mute USER_ID` - can also use id instead of mention
        `[p]mute @user 2h30m Optional reason goes here`
        `[p]mute @user 10d Muted for ten days for that and this`"""
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if not can_even_execute: return await ctx.send(f"Mute role not setup. "
                                                       f"Use `{ctx.bot.config['BOT_PREFIX']}setup muterolenew <role>`")

        await dutils.mute_user(ctx, user, length, reason)

    async def moderation_action(self, **kwargs):
        pass

    async def if_you_need_loop(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                print("Code here")
            except:
                pass
            await asyncio.sleep(10)  # sleep here


def setup(bot):
    ext = Moderation(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    bot.add_cog(ext)
