import asyncio
import time

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

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def ban(self, ctx, user: discord.Member, *, reason=""):
        """Ban a user with an optional reason. Prefix with s for "no dm"

        Tip:

        **Every ban/banish/softban/softbanish command (except massban)
        has another copy of it but with a `s` prefix**
        For example: `[p]sban @user` will ban them but
        will not dm them that they were banned.

        Ban = Delete no messages
        Banish = Delete 7 days of messages
        Softban = Ban but unban right away

        `[p]ban @user`
        `[p]ban USER_ID`
        `[p]ban USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def sban(self, ctx, user: discord.Member, *, reason=""):
        """Ban a user with an optionally supplied reason. **(won't dm them)**

        `[p]sban @user`
        `[p]sban USER_ID`
        `[p]sban USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, no_dm=True)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def banish(self, ctx, user: discord.Member, *, reason=""):
        """Same as ban but also deletes message history (7 days)

        `[p]banish @user`
        `[p]banish USER_ID`
        `[p]banish USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, removeMsgs=7)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def sbanish(self, ctx, user: discord.Member, *, reason=""):
        """Same as ban but also deletes message history (7 days) **(no dm)**

        `[p]sbanish @user`
        `[p]sbanish USER_ID`
        `[p]sbanish USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, removeMsgs=7, no_dm=True)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def softban(self, ctx, user: discord.Member, *, reason=""):
        """Ban, but unban right away

        `[p]softban @user`
        `[p]softban USER_ID`
        `[p]softban USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, softban=True)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def ssoftban(self, ctx, user: discord.Member, *, reason=""):
        """Ban, but unban right away (won't dm them)

        `[p]ssoftban @user`
        `[p]ssoftban USER_ID`
        `[p]ssoftban USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, softban=True, no_dm=True)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def softbanish(self, ctx, user: discord.Member, *, reason=""):
        """Ban, but unban right away also deletes message history (7 days)

        `[p]softbanish @user`
        `[p]softbanish USER_ID`
        `[p]softbanish USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, removeMsgs=7, softban=True)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def ssoftbanish(self, ctx, user: discord.Member, *, reason=""):
        """Ban, but unban right away also dels msg history (7d) **(no dm)**

        `[p]ssoftbanish @user`
        `[p]ssoftbanish USER_ID`
        `[p]ssoftbanish USER_ID optional reason goes here here`"""
        await dutils.banFunction(ctx, user, reason, removeMsgs=7, softban=True, no_dm=True)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.ban_members_check)
    @commands.command()
    async def massban(self, ctx, delete_messages_days: int, *users: discord.Member):
        """Ban multiple users at once (no dm by default)

        **delete_messages_days** => Has to be 0 or more and 7 or less

        `[p]multiple 0 @user1 @user2 @user3` ...
        `[p]ban 7 USER_ID1 USER_ID2 USER_ID3 USER_ID4` ...

        ⚠If you got the invalid arguments error. Check the ids or user names/pings.
        Some are wrong.

        You can use `[p]massbantest <SAME_ARGUMENTS_AS_YOU_JUST_USED>`
        To test which of these users/ids/names/pings is wrong."""
        if len(users) == 1: return await ctx.send("Why would you *massban* only 1 user? Aborting.")
        if len(users) > 50: return await ctx.send("Can mass ban up to max 50 users at once.")
        if delete_messages_days > 7 or delete_messages_days < 0: return await ctx.send("**delete_messages_days**"
                                                                                       " has to be"
                                                                                       " 0 or more and 7 or less. Fix "
                                                                                       "that first...")
        users = list(set(users))  # remove dupes
        m = await ctx.send("Massbanning...")
        rets = []
        for user in users:
            rets.append(await dutils.banFunction(ctx, user, removeMsgs=delete_messages_days,
                                                 massbanning=True, no_dm=True, reason="massban"))
        orig_msg = f"Massban complete! Banned **{len([r for r in rets if r])}** users"
        ret_msg = orig_msg
        for i in range(len(rets)):
            if rets[i] < 0:
                if rets[i] == -1: ret_msg += f"\n**F1:** {users[i].id}"
                if rets[i] == -100: ret_msg += f"\n**F2:** {users[i].id}"
            else:
                pass

        await m.delete()
        if ret_msg != orig_msg:
            await ctx.send("**F1** means that the user couldn't be found.\n"
                           "**F2** means that I couldn't ban the user because not enough permissions")
        await ctx.send(ret_msg)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.ban_members_check)
    @commands.command()
    async def massbantest(self, ctx, delete_messages_days: int, *users):
        """Test if massban would work with these arguments"""
        if delete_messages_days > 7 or delete_messages_days < 0: return await ctx.send("**delete_messages_days**"
                                                                                       " has to be"
                                                                                       " 0 or more and 7 or less. Fix "
                                                                                       "that first...")
        wrong = ""
        for _u in users:
            try:
                if _u[:3] == "<@!" and _u[-1] == ">":
                    u = ctx.guild.get_member(int(_u[3:-1]))
                else:
                    u = ctx.guild.get_member(int(_u))
                if not u: wrong += (_u + '\n')
            except:
                u = discord.utils.get(ctx.guild.members, name=_u)
                if not u: wrong += (_u + '\n')
        wrong = wrong.replace('@', '@\u200b')

        if not wrong:
            await ctx.send("✅ Arguments are ok, this should work")
        else:
            await ctx.send("❌ Displaying wrong/bad arguments:\n\n" + wrong)

    async def if_you_need_loop(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                print("Code here")
            except:
                pass
            await asyncio.sleep(10)  # sleep here

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def blacklist(self, ctx, *user_ids: int):
        """Blacklist a user or users by id"""
        user_ids = list(set(user_ids))  # remove dupes
        if len(user_ids) > 90: return await ctx.send("Can only blacklist up to 90 at once")
        data = [{'guild': ctx.guild.id, 'user_id': uid} for uid in user_ids]
        Blacklist.insert_many(data).execute()
        self.bot.moderation_blacklist = ModManager.return_blacklist_lists()
        await ctx.send("Done.")


def setup(bot):
    ext = Moderation(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    bot.add_cog(ext)
