import asyncio
import random
import re
import time
import traceback
import json
import discord
from discord.ext import commands, tasks
from discord import Member, Embed, File, utils
import os

from models.antiraid import ArGuild, ArManager
from models.moderation import Blacklist, ModManager
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
from models.serversetup import (Guild, WelcomeMsg, Logging, Webhook, SSManager)
import datetime


class Serversetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tryParseOnce = 0
        bot.loop.create_task(self.set_setup())

        self.bulk_deleted_before = {}
        self.bulk_deleted = {}
        self.check_bulk_msg_delete.start()
        self.welcomed_in_guild = {}

    async def set_setup(self, gid=None):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
        self.bot.from_serversetup = await SSManager.get_setup_formatted(self.bot)

    @commands.check(checks.admin_check)
    @commands.group(aliases=["sup"])
    async def setup(self, ctx):
        """Use the subcommands to setup server related stuff

        By itself this command doesn't do anything"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @setup.command(aliases=["cur"], name="current")
    async def _current(self, ctx):
        """Display current server setup"""
        desc = ""
        em = Embed(title="Current setup", color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'])
        if hasattr(ctx.bot, 'from_serversetup') and (ctx.guild.id not in ctx.bot.from_serversetup):
            if self.tryParseOnce < 1:
                ctx.bot.from_serversetup = await SSManager.get_setup_formatted(self.bot)
                self.tryParseOnce += 1
                return await ctx.reinvoke(restart=True)

            desc = "This server has no setup."
        else:
            data = ctx.bot.from_serversetup[ctx.guild.id]

            chn = None
            if data['muterole']: chn = discord.utils.get(ctx.guild.roles, id=data['muterole'])
            desc += f'❌ __**Mute role**__\n' if not chn else f'✅ __**Mute role**__ {chn.mention} (id: {chn.id})\n'

            chn = None
            if data['modrole']: chn = discord.utils.get(ctx.guild.roles, id=data['modrole'])
            desc += f'❌ __**Mod role**__\n' if not chn else f'✅ __**Mod role**__ {chn.mention} (id: {chn.id})\n'

            descField = ""
            chn1 = None
            if 'reg' in data: chn1 = data['reg']
            descField += f'❌ __**Regular log channel**__\n' if not chn1 else \
                f'✅ __**Regular log channel**__ {chn1.mention} (id: {chn1.id})\n'

            chn2 = None
            if 'leavejoin' in data: chn2 = data['leavejoin']
            descField += f'❌ __**Leavejoin log channel**__\n' if not chn2 else \
                f'✅ __**Leavejoin log channel**__ {chn2.mention} (id: {chn2.id})\n'

            chn3 = None
            if 'modlog' in data: chn3 = data['modlog']
            descField += f'❌ __**Mod log channel**__\n' if not chn3 else \
                f'✅ __**Moderation log channel**__ {chn3.mention} (id: {chn3.id})\n'
            em.add_field(name='Logging channels', value=descField, inline=False)

            descField = ""
            chn = None
            if 'hook_reg' in data: chn = data['hook_reg']
            descField += f'❌ __**Regular logging webhook**__\n' if not chn else \
                f'✅ __**Regular logging webhook**__\n{chn.name} (id: {chn.id})\n' \
                f'Target: {chn.channel.mention}\n'
            if chn and chn1 and chn.channel_id != chn1.id: descField = descField[:-1] + "⚠**MISMATCH**⚠\n"

            chn = None
            if 'hook_leavejoin' in data: chn = data['hook_leavejoin']
            descField += f'❌ __**Leavejoin logging webhook**__\n' if not chn else \
                f'✅ __**Leavejoin logging webhook**__\n{chn.name} (id: {chn.id})\n' \
                f'Target: {chn.channel.mention}\n'
            if chn and chn2 and chn.channel_id != chn2.id: descField = descField[:-1] + "⚠**MISMATCH**⚠\n"

            chn = None
            if 'hook_modlog' in data: chn = data['hook_modlog']
            descField += f'❌ __**Moderation log webhook**__\n' if not chn else \
                f'✅ __**Moderation log webhook**__\n{chn.name} (id: {chn.id})\n' \
                f'Target: {chn.channel.mention}\n'
            if chn and chn3 and chn.channel_id != chn3.id: descField = descField[:-1] + "⚠**MISMATCH**⚠\n"
            em.add_field(name='Logging webhooks', value=descField, inline=False)

            val = "There are no ignored channels"
            if data['ignored_chs_at_log']:
                chs = [discord.utils.get(ctx.guild.channels, id=int(ch)) for ch in data['ignored_chs_at_log'].split()]
                val = '\n'.join([f'{c.mention} (id: {c.id})' for c in chs])
            em.add_field(name='Logging ingores these channels', value=val, inline=False)

            val = f"❌ __**Welcome message not setup**__ (see `{dutils.bot_pfx(ctx.bot, ctx.message)}sup wm`)"
            if 'welcomemsg' in data:
                val = f"✅ __**Welcome message is setup**__ (see `{dutils.bot_pfx(ctx.bot, ctx.message)}sup wm cur`)"
            em.add_field(name='Welcome message status', value=val, inline=False)

            em.description = desc
            return await ctx.send(embed=em)

        em.description = desc
        await ctx.send(embed=em)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.command(aliases=["ae"])
    async def almosteverything(self, ctx,
                               mute_role: discord.Role,
                               moderator_role: discord.Role,
                               logging_regular_channel: discord.TextChannel,
                               logging_leavejoin_channel: discord.TextChannel,
                               logging_modlog_channel: discord.TextChannel,
                               hook_logging_id: int = 0,
                               # hook_logging_target_ch: discord.TextChannel,
                               hook_leavejoin_id: int = 0,
                               # hook_leavejoin_target_ch: discord.TextChannel,
                               hook_modlog_id: int = 0
                               # hook_modlog_target_ch: discord.TextChannel,
                               ):
        """Setup (almost) everything at once

        If you don't want to setup webhooks by hand.
        You can just leave the webhook parameters empty
        and the bot will make the webhooks."""
        m = await ctx.send("Setup started")
        async with ctx.typing():
            await self.do_setup(ctx=ctx, logging_reg=logging_regular_channel, quiet_succ=True)
            await self.do_setup(ctx=ctx, logging_leavejoin=logging_leavejoin_channel, quiet_succ=True)
            await self.do_setup(ctx=ctx, logging_modlog=logging_modlog_channel, quiet_succ=True)
            rr = ("Could not create logging webhook, missing perms, "
                  "please update my perms so I can "
                  "make webhooks.")
            if hook_logging_id == 0:
                try:
                    h = await logging_regular_channel.create_webhook(name="log_hook_tmp_name")
                    hook_logging_id = h.id
                except:
                    return await ctx.send(rr)
            if hook_leavejoin_id == 0:
                try:
                    h = await logging_leavejoin_channel.create_webhook(name="joinlog_hook_tmp_name")
                    hook_leavejoin_id = h.id
                except:
                    return await ctx.send(rr)
            if hook_modlog_id == 0:
                try:
                    h = await logging_modlog_channel.create_webhook(name="modlog_hook_tmp_name")
                    hook_modlog_id = h.id
                except:
                    return await ctx.send(rr)
            await self.do_setup(hook_reg=hook_logging_id, hook_reg_target=logging_regular_channel, ctx=ctx,
                                quiet_succ=True)
            await self.do_setup(hook_leavejoin=hook_leavejoin_id, hook_leavejoin_target=logging_leavejoin_channel,
                                ctx=ctx,
                                quiet_succ=True)
            await self.do_setup(hook_modlog=hook_modlog_id, hook_modlog_target=logging_modlog_channel, ctx=ctx,
                                quiet_succ=True)
            await self.do_setup(mod_role=moderator_role, ctx=ctx, quiet_succ=True)
            await self.do_setup(mute_role=mute_role, ctx=ctx, quiet_succ=True)
            await ctx.send("--------------\n"
                           "*The following message always appears.\n"
                           "If you didn't get any errors during the setup it actually worked.\n"
                           "If you got errors ignore the following msg...*")
            await ctx.send("Done!! As for the muted role, it's stored but...\n"
                           "This doesn't mean the channel permissions are setup though.\n"
                           "If they weren't set by hand yet, you can use:\n"
                           f"`{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolechperms <role_id>/<role_name>`")
            await m.delete()

    @commands.check(checks.admin_check)
    @setup.group()
    async def webhooks(self, ctx):
        """Webhook related setups, use subcommands

        By itself this command doesn't do anything

        Setup XYZ webhook by providing it's id and target ch

        **Setup X channel and target_channel should match**

        ***WARNING!!! (NEVER PASTE THE FULL WEBHOOK URL IN CHAT)***
        Do not copy more than the webhook id. DO NOT post the entire url.
        When you copy the webhook url, insert only the id as the parameter.

        Example:
        https://discordapp.com/api/webhooks/123123/Som-E-LoNgmese_a432d#@#1MessyStriNg
        For the command you should only paste 123123.

        ex: `[p]setup webhooks regularlogging 123123 #logs`"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def regularlogging(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Regular logging hook"""
        await self.do_setup(hook_reg=hook_id, hook_reg_target=target_channel, ctx=ctx)

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def leavejoin(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Leave and join logging hook"""
        await self.do_setup(hook_leavejoin=hook_id, hook_leavejoin_target=target_channel, ctx=ctx)

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def modlog(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Moderation log logging hook"""
        await self.do_setup(hook_modlog=hook_id, hook_modlog_target=target_channel, ctx=ctx)

    @commands.check(checks.admin_check)
    @setup.group()
    async def logging(self, ctx):
        """Logging channels related setups, use subcommands

        By itself this command doesn't do anything"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @logging.command()
    async def regular(self, ctx, channel: discord.TextChannel):
        """Logging for deleted/edited messages"""
        await self.do_setup(ctx=ctx, logging_reg=channel)

    @commands.check(checks.admin_check)
    @logging.command()
    async def leavejoin(self, ctx, channel: discord.TextChannel):
        """Logging for leave/join messages"""
        await self.do_setup(ctx=ctx, logging_leavejoin=channel)

    @commands.check(checks.admin_check)
    @logging.command()
    async def modlog(self, ctx, channel: discord.TextChannel):
        """Logging for moderation related actions"""
        await self.do_setup(ctx=ctx, logging_modlog=channel)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.command()
    async def muterolenew(self, ctx, *, role: discord.Role):
        """Setup muterole
        Note, this command may be used with any role, but it's main
        purpose/use is to setup the mute role perms on the channels."""
        if role.is_default():
            return await ctx.send('Cannot use the @\u200beveryone role.')
        if role > ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('This role is higher than your highest role.')
        if role > ctx.me.top_role:
            return await ctx.send('This role is higher than my highest role.')
        old_mute_role = None
        if ctx.guild.id in self.bot.from_serversetup:
            sup = self.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']:
                pass
            else:
                old_mute_role = discord.utils.get(ctx.guild.roles, id=sup['muterole'])
                if old_mute_role and old_mute_role.id == role.id: return await ctx.send(
                    "This role is already in use as "
                    "the mute role.")
                maxx = 10
                some_owner = (ctx.author.id == ctx.guild.owner_id or ctx.author.id == ctx.bot.config['OWNER_ID'])
                if len(old_mute_role.members) > maxx and not some_owner:
                    return await ctx.send(f"More than {maxx} users have this role. Because of that only the server or "
                                          f"bot owner may execute this command. Please contact them.")
                prompt = await dutils.prompt(ctx, "Mute role already exists, are you sure you want to update it?")
                if not prompt:
                    await ctx.message.delete()
                    return
                if not old_mute_role: await ctx.send("It seems like the old mute role has been deleted from the server")
                async with ctx.typing():
                    m1 = await ctx.send("Automatically applying channel permissions and then "
                                        "replacing the old mute role on every member.")
                    m0 = await self.update_mute_role_perms(ctx, role)
                    m2 = await ctx.send("Applied channel permissions.")
                    good = 0
                    m3 = None
                    if old_mute_role:
                        for m in old_mute_role.members:
                            try:
                                await m.add_roles(role, reason=f"{ctx.author} {ctx.author.id} updated the mute role")
                                good += 1
                            except:
                                pass
                        m3 = await ctx.send(f"Updated the role for {good}/{len(old_mute_role.members)} users")
                    await self.do_setup(mute_role=role, ctx=ctx)
                    m4 = None
                    m5 = None
                    if old_mute_role:
                        m4 = await ctx.send("Removing old mute role from members")
                        good = 0
                        ll = len(old_mute_role.members)
                        for m in old_mute_role.members:
                            try:
                                await m.remove_roles(old_mute_role,
                                                     reason=f"{ctx.author} {ctx.author.id} updated the mute role")
                                good += 1
                            except:
                                pass
                        m5 = await ctx.send(f"Removed the old fole from from {good}/{ll} users")
                    await asyncio.sleep(10)
                    await m0.delete()
                    await m1.delete()
                    await m2.delete()
                    if m3: await m3.delete()
                    if m4: await m4.delete()
                    if m5: await m5.delete()
                    return

        await self.do_setup(mute_role=role, ctx=ctx)
        await ctx.send("Stored the muted role in the database.\n"
                       "This doesn't mean the channel permissions are setup though.\n"
                       "If they weren't set by hand yet, you can use:\n"
                       f"`{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolechperms <role_id>/<role_name>`\n")

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.group()
    async def muterolechperms(self, ctx, *, role: discord.Role):
        """Update channel perms for the mute role"""
        if role.is_default():
            return await ctx.send('Cannot use the @\u200beveryone role.')
        if role > ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('This role is higher than your highest role.')
        if role > ctx.me.top_role:
            return await ctx.send('This role is higher than my highest role.')
        await self.update_mute_role_perms(ctx, role)

    @staticmethod
    async def update_mute_role_perms(ctx, role):
        msg = await ctx.send('Applying channel permissions')
        for ch in ctx.guild.text_channels:
            overwrites_muted = ch.overwrites_for(role)
            overwrites_muted.send_messages = False
            overwrites_muted.add_reactions = False
            await ch.set_permissions(role, overwrite=overwrites_muted)
        for ch in ctx.guild.voice_channels:
            overwrites_muted = ch.overwrites_for(role)
            overwrites_muted.speak = False
            overwrites_muted.connect = False
            await ch.set_permissions(role, overwrite=overwrites_muted)
        await msg.edit(content='Done, setup complete')
        return msg

    @commands.check(checks.admin_check)
    @setup.command()
    async def modrole(self, ctx, *, role: discord.Role):
        """Setup moderator specific role"""
        if role.is_default():
            return await ctx.send('Cannot use the @\u200beveryone role.')
        if role > ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send('This role is higher than your highest role.')
        if role > ctx.me.top_role:
            return await ctx.send('This role is higher than my highest role.')
        await self.do_setup(mod_role=role, ctx=ctx)

    @commands.check(checks.admin_check)
    @setup.group(aliases=['dlg'])
    async def dontlogchannel(self, ctx):
        """Add or remove channels to not log from"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @dontlogchannel.command()
    async def add(self, ctx, channels: commands.Greedy[discord.TextChannel]):
        """Add chanenls (max 3 at once) to be ignore by the bot when logging"""
        if len(channels) > 3: return await ctx.send("Command takes up to 3 channels at once for a batch update.")
        for channel in channels:
            await self.do_setup(add_ignore=str(channel.id), ctx=ctx)
        await ctx.message.delete()

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @dontlogchannel.command()
    async def remove(self, ctx, channels: commands.Greedy[discord.TextChannel]):
        """Remove chanenls (max 3 at once) from ignored channels when loggin"""
        if len(channels) > 3: return await ctx.send("Command takes up to 3 channels at once for a batch update.")
        for channel in channels:
            await self.do_setup(remove_ignore=str(channel.id), ctx=ctx)
        await ctx.message.delete()

    @commands.check(checks.moderator_check)
    @commands.group(aliases=['cl', 'censorlist'])
    async def censor(self, ctx):
        """Add or remove words to the censor list."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.moderator_check)
    @censor.command()
    async def add(self, ctx, *words):
        """Add words to censor list"""
        if len(words) == 0: await ctx.send("You didn't provide any words.")
        await self.do_setup(add_c_words=list(words), ctx=ctx)

    @commands.check(checks.moderator_check)
    @censor.command()
    async def remove(self, ctx, *words):
        """Remove words from censor list"""
        if len(words) == 0: await ctx.send("You didn't provide any words.")
        await self.do_setup(remove_c_words=list(words), ctx=ctx)

    @commands.check(checks.moderator_check)
    @censor.command()
    async def show(self, ctx, compact=""):
        """Show censor list (for compact view `[p]cl show compact`)"""
        db_guild = SSManager.get_or_create_and_get_guild(ctx.guild.id)
        delim = '\n' if compact != 'compact' else ' '
        if db_guild.censor_list == "": return await ctx.send("No censored words here yet.")
        arrs = dutils.getParts2kByDelimiter(db_guild.censor_list, delim, limit=1000)
        ems = dutils.getEmbedsFromTxtArrs(ctx.bot, arrs, '**Censor list**', cnt_join_instd_of_spc=delim)
        return await dutils.send_and_maybe_paginate_embeds(ctx, ems)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.command(aliases=['cmdschs', 'cc'])
    async def commandschannels(self, ctx, *, settings=""):
        """Disable cmds in certain channels, or only enable them in certain chs.

        > Running this command with no arguments will display current settings

        Use the following syntax: (channel can be id, name or mention)
        Command example:
        `[p]sup cmdschs disable [cm1, cmd2, cmd2] those in [channel1, channel2]
        disable [cm10, "custom cmds", cmd21] those in [channel12, channel2]
        disable [cmd10, cmd2, cmd24] those in [channel14, channel22]
        enable [cmd54, cmd51] only in [channel3]
        enable [cmd44, cmd15] only in [channel35]`

        If you want to revert or change something, just run the command again
        or something (see the message history).

        ~~Yes I was a bit lazy when adding this command, I *might* make it
        more flexible in the future. But is should be fiiine~~
        **So please follow the syntax as shown in the example exactly.**

        This setting doesn't work on mods and admins.
        """
        if not settings:
            g = Guild.get_or_none(id=ctx.guild.id)
            if not g or not g.disabled_onlyEnabled_cmds_and_chs or g.disabled_onlyEnabled_cmds_and_chs == '{}':
                return await ctx.send("No disabled/only_enabled settings setup for this sever.")
            chs = json.loads(g.disabled_onlyEnabled_cmds_and_chs)
            ret = 'Displaying the current setup, sending it in command invoke format in case any changes ' \
                  'need to be applied.:\n'
            cc = {}
            r = ''
            for de in [('disable', 'those in'), ('enable', 'only in')]:
                keyy = 'only_e' if de[0] == 'enable' else 'dis'
                for k, v in chs.items():
                    for ch in v[keyy]:
                        ch = str(ch)
                        if ch not in cc: cc[ch] = {'only_e': [], 'dis': []}
                        cc[ch][keyy].append(k)
                for kk, vv in cc.items():
                    if not vv[keyy]: continue
                    chn = ctx.guild.get_channel(int(kk))
                    if chn:
                        r += f'{de[0]} [{", ".join(vv[keyy])}] {de[1]} [{chn.name}]\n'
            ret += f'```\n{dutils.bot_pfx_by_ctx(ctx)}sup cmdschs {r}```'
            return await ctx.send(ret.replace('@', '@\u200b'))
        try:
            settings = settings.replace(',', ', ')
            settings = re.sub(' +', ' ', settings)
            chs = {}  # ch: {"only_e": [...], "dis": [...]}
            for line in settings.split('\n'):
                left = 'disable \['
                right = 'those in \['
                if 'enable [' in line:
                    left = 'enable \['
                    right = 'only in \['
                k = 'only_e' if left == 'enable \[' else 'dis'
                for _ch in (re.search(f'{right}(.*?)\]', line)).group(1).split(', '):
                    ch = await dutils.getChannel(ctx, _ch, silent=True)
                    if ch:
                        for _cm in (re.search(f'{left}(.*?)\]', line)).group(1).split(', '):
                            if _cm in self.bot.all_commands or _cm == '"custom cmds"':
                                if _cm not in chs: chs[_cm] = {"only_e": [], "dis": []}
                                chs[_cm][k].append(ch.id)
                            if _cm in chs: chs[_cm][k] = list(set(chs[_cm][k]))
            for k in chs.copy():
                if not chs[k]['only_e'] and not chs[k]['dis']:
                    del chs[k]
                if chs[k]['only_e'] and chs[k]['dis']:
                    ctx.command.reset_cooldown(ctx)
                    return await ctx.send(f"You tried to only enable and just disable **{k}** in "
                                          f"multiple channels at once. Please try again without doing that. "
                                          f"Only enable the command in some channels or just disable it in "
                                          f"some channels, not both at once.")
            await self.do_setup(cmds_chs_meta=chs, ctx=ctx)
        except:
            self.bot.logger.error(traceback.format_exc())
            await ctx.send("Something went wrong, ~~are you using the correct syntax?~~")
            ctx.command.reset_cooldown(ctx)
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @setup.group(aliases=['wm'])
    async def welcomemsg(self, ctx):
        """Main w.m. setup command, use subcommands

        Initially you're suppose to use
        `[p]sup wm m`
        or
        `[p]setup welcomemessage mainsetup`
        In case of activating raid mode, the welcome message
        welcoming will be changed to a webhook that the bot
        will create right after running this command.
        """
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @welcomemsg.command(aliases=['m'])
    async def mainsetup(self, ctx, target_channel: discord.TextChannel):
        """Go trough the entire setup process

        With this command you can setup an image or more images to be randomly picked
        when the user joins the server, what the message content should be, embed title, and embed
        content. Usage examples are shown below:

        The only requiered argument is the welcome channel id, you will be querried for the rest of the data
        during this comamnd's execution. Example below will set the channel with the following id to be the welcome one.

        `[p]setup welcomemsg mainsetup 589190883857924154`

        In case of activating raid mode, the welcome message
        welcoming will be changed to a webhook that the bot
        will create right after running this command."""

        db_guild = SSManager.get_or_create_and_get_guild(ctx.guild.id)

        db_wmsg = SSManager.get_or_create_and_get_welcomemsg(db_guild, target_channel.id, ctx.guild.id)
        hook = None
        if db_wmsg.backup_hook != 0:
            hook = db_wmsg.backup_hook
        if not hook:
            try:
                hook = await target_channel.create_webhook(name=f'Tmp name', reason="Backup hook "
                                                                                    "for welcoming "
                                                                                    "in case of a "
                                                                                    "raid")
                db_wmsg.backup_hook = hook.id
                db_wmsg.save()
                url = str(ctx.bot.user.avatar_url).replace('.webp', '.png')
                tf = f'w{str(int(datetime.datetime.utcnow().timestamp()))}w'
                fnn = await dutils.saveFile(url, 'tmp', tf)  # copy from dutils because circular import
                with open(fnn, 'rb') as fp:
                    await hook.edit(name=f'{ctx.bot.user.display_name}'[:32], avatar=fp.read())
                os.remove(fnn)
            except discord.errors.Forbidden:
                return await ctx.send("Please give me manage webhooks permissions first to even run this command.")

        # This code is copy pasted from the old bot code, didn't feel like it needed to be changed
        # (even though it's pretty spaghetti code)

        # --- CHECKS START

        def checkYN(m):
            return (m.content.lower() == 'y' or m.content.lower() == 'n') and \
                   m.author == ctx.author and m.channel == ctx.channel

        def checkAuthor(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # --- CHECKS END

        if db_wmsg.images or db_wmsg.content or db_wmsg.desc or db_wmsg.title:
            #  Display old data

            await ctx.send('Welcome data already setup, displaying current data:')
            pics = '\n'.join([f'<{p}>' for p in db_wmsg.images.split()])
            cnt = f"**Channel:** <#{db_wmsg.target_ch}>\n" \
                  f"**Non embed msg:** {db_wmsg.content}\n" \
                  f"**Embed Title:** {db_wmsg.title}\n" \
                  f"**Embed Content:** {db_wmsg.desc}\n" \
                  f"**Embed Color:** {hex(db_wmsg.color)}\n" \
                  f"**Member count:**  {'True' if db_wmsg.display_mem_count else 'False'}\n" \
                  f"**\nWelcome images:**\n" \
                  f"{pics}"
            em = Embed(title=f'Data for {str(ctx.guild)}', color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                       description=cnt)
            await ctx.send(embed=em)
            # Prompt to start over
            pr = await ctx.send('Do you wish to start the setup from the start? (y/n)')
            try:
                reply = await self.bot.wait_for("message", check=checkYN, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send("Cancelled.")
            if not reply or reply.content.lower().strip() == 'n':
                return await ctx.send("Cancelled.")

        # Start prompting
        emm = Embed(description='Starting setup, please reply with the required data, careful becasue '
                                'there are no undos\n(you can start over by sending: `STOP THIS NOW` '
                                'though ... but still, be careful)')
        emm.set_image(url='http://totally-not.a-sketchy.site/7UAZyTZ.png')
        await ctx.send(embed=emm)
        await ctx.send('**▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬**')

        # QUESTION 1
        pr = await ctx.send(
            'What should the message be? (the one outside the embed, send just **$** if nothing)\n'
            'If you want to ping the user who has just joined use [username] in this message. Example:\n'
            '\n[username] welcome to the server!')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            mm = reply.content.strip()
            if mm == '$': mm = ""
            if mm: db_wmsg.content = mm
            await reply.delete()

        # QUESTION 2
        pr = await ctx.send('What should the embed title be? (send **$** if nothing)')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            rp = reply.content.strip()
            if rp == '$': rp = ""
            if rp: db_wmsg.title = rp
            await reply.delete()

        # QUESTION 3
        pr = await ctx.send('What should the embed content be? (send **$** if nothing)')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            rp2 = reply.content.strip()
            if rp2 == '$': rp2 = ""
            if rp2: db_wmsg.desc = rp2
            await reply.delete()

        # QUESTION 4
        pr = await ctx.send('What should the embed color be? (send **$** if you want to keep '
                            'the default bot embed color)\nColor format, one of:\n'
                            '0x1F2E3C | #1F2E3C | 1F2E3C')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            rp3 = reply.content.strip()
            if rp3 == '$':
                color = -100
                await reply.delete()
            else:
                color = -100
                try:
                    if len(rp3) < 6: raise Exception("fail")
                    color = int(rp3[-6:], 16)
                except:
                    await ctx.send("**(*This message* will auto delete in 20 seconds)"
                                   "\nYou failed to input a correct color format, keeping the default bot color.\n"
                                   f"Can still be changed with `{dutils.bot_pfx(ctx.bot, ctx.message)}setup welcomemsg "
                                   f"color color_here`\n**"
                                   f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
                                   delete_after=20)
                    color = -100

                if color != -100: db_wmsg.color = color
                await reply.delete()

        # QUESTION 5
        pr = await ctx.send('Please provide the image or images that should be used for the welcome message '
                            'picture. (If more are provided then a random one will be chosen once '
                            'a user joins the server)\nSend the images'
                            'in the following format:\n\n- If none: just send **$**'
                            '\n- If just one: Just send the one picture link.\n'
                            '- If multiple: '
                            'link1 link2 link3 link4 link5')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            if reply.content.strip() == '$':
                images = ""
            else:
                images = " ".join(reply.content.replace('\n', ' ').split())
                for i in images.split():
                    if not i.startswith('http'):
                        await ctx.send(
                            "One of the image links doesn't start with `http`...\n"
                            f"Try adding them again with `{dutils.bot_pfx(ctx.bot, ctx.message)}"
                            f"setup welcomemsg images <pics>`",
                            delete_after=20)
                        images = ""
                        break
            db_wmsg.images = images
            await reply.delete()

        confirm = await dutils.prompt(ctx, "**Do you wish to enable showing member count on welcome message?**")
        if not confirm:
            db_wmsg.display_mem_count = False
        else:
            db_wmsg.display_mem_count = True

        # DONE QUERRYING, DISPLAY FINAL PREVIEW
        await ctx.send('⚠ Setup done, preview below, if all is ok reply with **y** if not with **n** ⚠\n'
                       '**▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬**')

        pics = '\n'.join([f'<{p}>' for p in db_wmsg.images.split()])
        cnt = f"**Channel:** <#{db_wmsg.target_ch}>\n" \
              f"**Non embed msg:** {db_wmsg.content}\n" \
              f"**Embed Title:** {db_wmsg.title}\n" \
              f"**Embed Content:** {db_wmsg.desc}\n" \
              f"**Embed Color:** {hex(db_wmsg.color)}\n" \
              f"**Member count:**  {'True' if db_wmsg.display_mem_count else 'False'}\n" \
              f"**\nWelcome images:**\n" \
              f"{pics}"
        em = Embed(title=f'Data for {str(ctx.guild)}', color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                   description=cnt)
        await ctx.send(embed=em)

        try:
            reply = await self.bot.wait_for("message", check=checkYN, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Cancelled.")
        if not reply or reply.content.lower().strip() == 'n':
            return await ctx.send("Cancelled.")
        else:
            db_wmsg.save()
            await ctx.send('Done, saved.')
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def targetch(self, ctx, target_channel: discord.TextChannel):
        """Fine tune target channel"""
        await SSManager.update_or_error_welcomemsg_target_ch(target_channel.id, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def displaymemcount(self, ctx):
        """Fine tune if you want to display member count"""
        the_bool = True
        confirm = await dutils.prompt(ctx, "**Do you wish to enable showing member count on welcome message?**")
        if not confirm:
            the_bool = False

        await SSManager.update_or_error_welcomemsg_mem_cnt(the_bool, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def title(self, ctx, *, title):
        """Fine tune embed title"""
        await SSManager.update_or_error_welcomemsg_title(title, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def desc(self, ctx, *, description):
        """Fine tune embed desscription"""
        await SSManager.update_or_error_welcomemsg_desc(description, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def images(self, ctx, *, images):
        """Fine tune embed image(s) (seperate with a space)"""
        images = " ".join(images.replace('\n', ' ').split())
        for i in images.split():
            if not i.startswith('http'): return await ctx.send("One of the image links doesn't start with `http`...")
        await SSManager.update_or_error_welcomemsg_images(images, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def content(self, ctx, *, cnt):
        """Fine tune message outside of the embed

        [username] will be replaced with new user ping"""
        await SSManager.update_or_error_welcomemsg_content(cnt, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def color(self, ctx, *, color):
        """Fine tune embed color

        Color format, one of:
        0x1F2E3C | #1F2E3C | 1F2E3C"""
        try:
            if len(color) < 6: raise Exception("fail")
            _color = int(color[-6:], 16)
        except:
            return await ctx.send("Invalid color format, please use one of:\n"
                                  "0x1F2E3C | #1F2E3C | 1F2E3C")

        await SSManager.update_or_error_welcomemsg_color(_color, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command(aliases=["cur"])
    async def current(self, ctx):
        """Display all current information regarding welcome messages"""
        if hasattr(ctx.bot, 'from_serversetup') and ('welcomemsg' not in ctx.bot.from_serversetup):
            if self.tryParseOnce < 1:
                ctx.bot.from_serversetup = await SSManager.get_setup_formatted(self.bot)
                self.tryParseOnce += 1
                return await ctx.reinvoke(restart=True)
        try:
            db_wmsg = WelcomeMsg.get(WelcomeMsg.guild == ctx.guild.id)
        except:
            return await ctx.send("No data setup.")

        if db_wmsg.images or db_wmsg.content or db_wmsg.desc or db_wmsg.title:
            #  Display old data

            await ctx.send('Ddisplaying current data:')
            pics = '\n'.join([f'<{p}>' for p in db_wmsg.images.split()])
            cnt = f"**Channel:** <#{db_wmsg.target_ch}>\n" \
                  f"**Non embed msg:** {db_wmsg.content}\n" \
                  f"**Embed Title:** {db_wmsg.title}\n" \
                  f"**Embed Content:** {db_wmsg.desc}\n" \
                  f"**Embed Color:** {hex(db_wmsg.color)}\n" \
                  f"**Member count:**  {'True' if db_wmsg.display_mem_count else 'False'}\n" \
                  f"**\nWelcome images:**\n" \
                  f"{pics}"
            em = Embed(title=f'Data for {str(ctx.guild)}', color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                       description=cnt)
            await ctx.send(embed=em)

        else:
            await ctx.send("No data setup.")

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def test(self, ctx):
        """Do a test welcome on yourself in this channel"""
        try:
            db_wmsg = WelcomeMsg.get(WelcomeMsg.guild == ctx.guild.id)
        except:
            return await ctx.send("No data setup.")

        if db_wmsg.images or db_wmsg.content or db_wmsg.desc or db_wmsg.title:
            em = Embed(title=db_wmsg.title, description=db_wmsg.desc, color=db_wmsg.color)
            if db_wmsg.display_mem_count:
                em.set_footer(text=f'Member count: {len(ctx.guild.members)}')
            if db_wmsg.images:
                pic = random.choice(db_wmsg.images.split())
                if pic.startswith('http'):
                    em.set_image(url=pic)
            cnt = db_wmsg.content.replace('[username]', ctx.author.mention)
            if not db_wmsg.images and db_wmsg.content and not db_wmsg.desc \
                    and not db_wmsg.title and not db_wmsg.display_mem_count:
                await ctx.send(content=cnt)
            else:
                await ctx.send(embed=em, content=cnt)

        else:
            await ctx.send("No data setup.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if -1 in self.bot.moderation_blacklist:
            self.bot.moderation_blacklist = ModManager.return_blacklist_lists()
        smb = self.bot.moderation_blacklist
        do_wel_msg = True
        if member.guild.id in smb and member.id in smb[member.guild.id]:
            try:
                self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}'] = 2
                await member.ban(reason="User joined when they were blacklisted. Removed the user from "
                                        "the datbase blacklist", delete_message_days=0)
                Blacklist.delete().where(Blacklist.user_id == member.id, Blacklist.guild == member.guild.id).execute()
                self.bot.moderation_blacklist = ModManager.return_blacklist_lists()
            except:
                self.bot.moderation_blacklist = ModManager.return_blacklist_lists()
            do_wel_msg = False

        if do_wel_msg:
            try:
                if self.bot.from_serversetup and member.guild.id in self.bot.from_serversetup:
                    if 'welcomemsg' in self.bot.from_serversetup[member.guild.id]:
                        wmsg = self.bot.from_serversetup[member.guild.id]['welcomemsg']
                        em = Embed(title=wmsg['title'], description=wmsg['desc'], color=wmsg['color'])
                        if wmsg['display_mem_count']:
                            em.set_footer(text=f'Member count: {len(member.guild.members)}')
                        if wmsg['images']:
                            pic = random.choice(wmsg['images'].split())
                            if pic.startswith('http'):
                                em.set_image(url=pic)
                        cnt = wmsg['content'].replace('[username]', member.mention)

                        # STUFF
                        send_with_hook = False
                        send_with = wmsg['target_ch']
                        gid = member.guild.id
                        now = datetime.datetime.utcnow().timestamp()
                        anti_spam_cd = 5  # so 5 seconds
                        if gid in self.welcomed_in_guild:
                            if now - self.welcomed_in_guild[gid][1] < anti_spam_cd:  # see if its less than 5s
                                self.welcomed_in_guild[gid][0] += 1
                                if self.welcomed_in_guild[gid][0] > 3:  # 4th+ join in last 5s
                                    send_with_hook = True
                                else:
                                    pass  # Almost reached the limit
                            else:
                                del self.welcomed_in_guild[gid]
                        else:
                            self.welcomed_in_guild[gid] = [0, now]
                        if send_with_hook and wmsg['backup_hook']:
                            send_with = wmsg['backup_hook']

                        try:
                            if not wmsg['images'] and wmsg['content'] and not wmsg['desc'] \
                                    and not wmsg['title'] and not wmsg['display_mem_count']:
                                await send_with.send(content=cnt)
                            else:
                                await send_with.send(embed=em, content=cnt)
                        except:
                            # idk if this will ever be hit but aight
                            self.bot.logger.info(f"Error at welcome webhook send in {member.guild.id} {member.guild}! "
                                                 f"Making new hook one.")

                            try:
                                hook = await wmsg['backup_hook'].create_webhook(name=f'Tmp name', reason="!Backup hook "
                                                                                                         "for "
                                                                                                         "welcoming "
                                                                                                         "in case of a "
                                                                                                         "raid")
                                db_wmsg = WelcomeMsg.get(WelcomeMsg.guild == member.guild.id)
                                db_wmsg.backup_hook = hook.id
                                db_wmsg.save()
                                self.bot.from_serversetup[member.guild.id]['welcomemsg']['backup_hook'] = hook
                                send_with = hook
                                self.bot.logger.info(f'Newest hook id {hook.id}')
                                url = str(self.bot.user.avatar_url).replace('.webp', '.png')
                                tf = f'w{str(int(datetime.datetime.utcnow().timestamp()))}w'
                                fnn = await dutils.saveFile(url, 'tmp', tf)  # copy from dutils because circular import
                                with open(fnn, 'rb') as fp:
                                    await hook.edit(name=f'{self.bot.user.display_name}'[:32], avatar=fp.read())
                                os.remove(fnn)
                            except discord.errors.Forbidden:
                                await self.bot.logger.error(f'Missing webhook perms in '
                                                            f'{member.guild.id} {member.guild}!')

                            if not wmsg['images'] and wmsg['content'] and not wmsg['desc'] \
                                    and not wmsg['title'] and not wmsg['display_mem_count']:
                                await send_with.send(content=cnt)
                            else:
                                await send_with.send(embed=em, content=cnt)
            except:
                print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
                traceback.print_exc()
                self.bot.logger.error(f"Couldn't welcome {str(member)} {member.id} "
                                      f"in {str(member.guild)} {member.guild.id}")

        if member.guild.id in self.bot.from_serversetup:
            try:  # log it
                sup = self.bot.from_serversetup[member.guild.id]
                if sup['leavejoin']:
                    icon_url = member.avatar_url if 'gif' in str(member.avatar_url).split('.')[-1] else str(
                        member.avatar_url_as(format="png"))

                    embed = Embed(color=0x5ace47, title=f'{str(member.name)} has joined.',
                                  description=f'📈 {member.mention} (id: {member.id})')
                    embed.set_footer(text=f"{datetime.datetime.utcnow().strftime('%c')} | "
                                          f"Member count: {len(member.guild.members)}")
                    embed.set_author(name=f"{str(member)}", icon_url=icon_url)
                    embed.add_field(name="Joined", value=tutils.convertTimeToReadable1(member.joined_at), inline=True)
                    embed.add_field(name="Join Position", value=str(len(member.guild.members)), inline=True)
                    embed.add_field(name="Registered on", value=tutils.convertTimeToReadable1(member.created_at),
                                    inline=False)

                    cnt = None
                    bjac = (member.joined_at - member.created_at).total_seconds()
                    if bjac < 60: cnt = f"⚠⚠ **User joined {int(bjac)} seconds after account creation** ⚠⚠"
                    if 60 <= bjac < 3600: cnt = f"⚠ User joined **less than 1 hour** after account creation"
                    if 3600 <= bjac < 604800: cnt = f"ℹ User joined **less than 1 week** after account creation"

                    if not do_wel_msg:
                        cnt = "💥 **User was banned right away because they were on the blacklist**"
                        embed.colour = 0x338026

                    await dutils.try_send_hook(member.guild, self.bot, hook=sup['hook_leavejoin'],
                                               regular_ch=sup['leavejoin'], embed=embed, content=cnt)
            except:
                self.bot.logger.error(f"Join log error: {str(member)} {member.id} "
                                      f"in {str(member.guild)} {member.guild.id}")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        await self.set_setup(channel.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if self.bot.banned_cuz_blacklist and f'{member.id}_{member.guild.id}' in self.bot.banned_cuz_blacklist:
            self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}'] -= \
                self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}']
            if self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}'] == 0:
                del self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}']
            return

        if member.guild.id in self.bot.from_serversetup:
            try:  # log it
                sup = self.bot.from_serversetup[member.guild.id]
                if sup['leavejoin']:
                    embed = Embed(color=0xFF2244, description=f'📉 {str(member)} (id: {member.id}) has left the server',
                                  timestamp=datetime.datetime.utcfromtimestamp(datetime.datetime.utcnow().timestamp()))
                    embed.set_footer(text=f'New member count: {str(len(member.guild.members))}')
                    await dutils.try_send_hook(member.guild, self.bot, hook=sup['hook_leavejoin'],
                                               regular_ch=sup['leavejoin'], embed=embed)
            except:
                self.bot.logger.error(f"Leave log error: {str(member)} {member.id} "
                                      f"in {str(member.guild)} {member.guild.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if isinstance(message.channel, discord.DMChannel) or message.author.bot or \
                message.guild.id not in self.bot.from_serversetup:
            return
        if str(message.channel.id) in self.bot.from_serversetup[message.guild.id]['ignored_chs_at_log']: return
        txt = f"By: {message.author.mention} (id: {message.author.id}) in " \
              f"{message.channel.mention}\n\n{message.content}\n"
        if len(message.attachments) > 0:
            txt += '\n**Attachments:**\n'
            txt += '\n'.join([a.filename for a in message.attachments])
        await dutils.log(self.bot, "Message deleted", txt, message.author, 0xd6260b, guild=message.guild)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        msgs = payload.cached_messages
        ch_id = payload.channel_id
        g_id = payload.guild_id
        if g_id not in self.bot.from_serversetup: return
        if str(ch_id) in self.bot.from_serversetup[g_id]['ignored_chs_at_log']: return
        # for message in msgs: Don't display them
        #     if isinstance(message.channel, discord.DMChannel) or message.author.bot or \
        #             message.guild.id not in self.bot.from_serversetup:
        #         continue
        #     txt = f"{message.author.name} (id: {message.author.id}): {message.content}"
        #     if len(message.attachments) > 0:
        #         txt += '\n**Attachments:**\n'
        #         txt += '\n'.join([a.filename for a in message.attachments])
        #     # await dutils.log("Message deleted", txt, message.author, 0xd6260b)
        #     ret += (txt + '\n')
        # if len(msgs) > 0:
        #     print(ret)
        kk = f'{g_id}_{ch_id}'
        if len(payload.message_ids) < 3: return
        if kk not in self.bulk_deleted: self.bulk_deleted[kk] = 0
        self.bulk_deleted[kk] += len(payload.message_ids)

    @tasks.loop(seconds=4.0)
    async def check_bulk_msg_delete(self):
        try:
            if self.bulk_deleted:
                self.bulk_deleted_before = self.bulk_deleted.copy()
                await asyncio.sleep(8)
                for k, v in self.bulk_deleted.items():
                    if self.bulk_deleted_before[k] == self.bulk_deleted[k]:
                        val = self.bulk_deleted_before[k]
                        g_id, ch_id = k.split('_')
                        del self.bulk_deleted[k]
                        del self.bulk_deleted_before[k]
                        g = self.bot.get_guild(int(g_id))
                        await dutils.log(self.bot, "Bulk message delete detected", f"{val - 1} messages deleted in "
                                                                                   f"{(g.get_channel(int(ch_id))).mention}",
                                         None, 0x960f0f, guild=g)
                        ret = f"BULK DELETION HAPPENED AT {datetime.datetime.utcnow().strftime('%c')}\n" \
                              f"(ch: {ch_id}) (guild: {g_id})"
                        print(ret)
        except:
            await asyncio.sleep(2)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if isinstance(before.channel, discord.DMChannel) or before.author.bot or \
                before.guild.id not in self.bot.from_serversetup:
            return
        if str(before.channel.id) in self.bot.from_serversetup[before.guild.id]['ignored_chs_at_log']: return
        try:
            txt = f"By: {before.author.mention} (id: {before.author.id}) in {before.channel.mention}\n\n" \
                  f"**Before:**\n{before.content}\n\n**After:**\n{after.content}\n" \
                  f"[Jump to message]({after.jump_url})"
        except:
            txt = "can not retrieve edited message content, please contact the bot owner about this"
        await dutils.log(self.bot, "Message edited", txt, before.author, 0xffb81f, guild=before.guild)

    async def do_setup(self, **kwargs):
        ctx = kwargs.get('ctx', None)
        if not ctx: raise Exception("Missing ctx in do_setup")
        quiet_succ = kwargs.get('quiet_succ', False)
        hook_reg = kwargs.get('hook_reg', None)
        hook_reg_target = kwargs.get('hook_reg_target', None)
        hook_leavejoin = kwargs.get('hook_leavejoin', None)
        hook_leavejoin_target = kwargs.get('hook_leavejoin_target', None)
        hook_modlog = kwargs.get('hook_modlog', None)
        hook_modlog_target = kwargs.get('hook_modlog_target', None)

        logging_reg = kwargs.get('logging_reg', None)
        logging_leavejoin = kwargs.get('logging_leavejoin', None)
        logging_modlog = kwargs.get('logging_modlog', None)

        mute_role = kwargs.get('mute_role', None)
        mod_role = kwargs.get('mod_role', None)
        add_ignore = kwargs.get('add_ignore', None)
        remove_ignore = kwargs.get('remove_ignore', None)
        cmds_chs_meta = kwargs.get('cmds_chs_meta', None)

        add_c_words = kwargs.get('add_c_words', None)
        remove_c_words = kwargs.get('remove_c_words', None)

        db_guild = SSManager.get_or_create_and_get_guild(ctx.guild.id)
        try:
            if logging_reg and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                SSManager.create_or_update_logging(db_guild, logging_reg.id, 'reg')
            elif logging_leavejoin and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                SSManager.create_or_update_logging(db_guild, logging_leavejoin.id, 'leavejoin')
            elif logging_modlog and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                SSManager.create_or_update_logging(db_guild, logging_modlog.id, 'modlog')
            elif hook_reg and hook_reg_target and (len(kwargs) == 3 or (len(kwargs) == 4 and quiet_succ)):
                await SSManager.create_or_update_logging_hook(db_guild, hook_reg, hook_reg_target.id, 'reg',
                                                              await ctx.bot.fetch_webhook(hook_reg), ctx)
            elif hook_leavejoin and hook_leavejoin_target and (len(kwargs) == 3 or (len(kwargs) == 4 and quiet_succ)):
                await SSManager.create_or_update_logging_hook(db_guild, hook_leavejoin, hook_leavejoin_target.id,
                                                              'leavejoin', await ctx.bot.fetch_webhook(hook_leavejoin),
                                                              ctx)
            elif hook_modlog and hook_modlog_target and (len(kwargs) == 3 or (len(kwargs) == 4 and quiet_succ)):
                await SSManager.create_or_update_logging_hook(db_guild, hook_modlog, hook_modlog_target.id, 'modlog',
                                                              await ctx.bot.fetch_webhook(hook_modlog), ctx)
            elif mute_role and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                db_guild.muterole = mute_role.id
                db_guild.save()
            elif mod_role and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                db_guild.modrole = mod_role.id
                db_guild.save()
            elif add_ignore and len(kwargs) == 2:
                if add_ignore not in db_guild.ignored_chs_at_log:
                    arr = db_guild.ignored_chs_at_log.split()
                    arr.append(add_ignore)
                    db_guild.ignored_chs_at_log = " ".join(arr)
                    db_guild.save()
                else:
                    await ctx.send(f"<#{add_ignore}> is already being ignored.")
                    raise Exception("_fail")
            elif remove_ignore and len(kwargs) == 2:
                if remove_ignore in db_guild.ignored_chs_at_log:
                    arr = db_guild.ignored_chs_at_log.split()
                    arr.remove(remove_ignore)
                    db_guild.ignored_chs_at_log = " ".join(arr)
                    db_guild.save()
                else:
                    await ctx.send(f"<#{remove_ignore}> is not being ignored.")
                    raise Exception("_fail")
            elif add_c_words and len(kwargs) == 2:
                cur_c = db_guild.censor_list.split()
                cur_c.extend(add_c_words)
                new_c = list(set(cur_c))
                db_guild.censor_list = ' '.join(new_c)
                db_guild.save()
            elif remove_c_words and len(kwargs) == 2:
                cur_c = db_guild.censor_list.split()
                new_c = list(set(cur_c) - set(remove_c_words))
                db_guild.censor_list = ' '.join(new_c)
                db_guild.save()
            elif cmds_chs_meta and len(kwargs) == 2:
                c = json.dumps(cmds_chs_meta)
                if c != db_guild.disabled_onlyEnabled_cmds_and_chs:
                    db_guild.disabled_onlyEnabled_cmds_and_chs = c
                    db_guild.save()
                else:
                    await ctx.send(f"No changes were made to commands disabled/enabled setings "
                                   f"because the previous settings are the same as the one you set.")
                    raise Exception("_fail")

            else:
                await ctx.send(f"You shouldn't have hit this. oi.. <@!{ctx.bot.config['OWNER_ID']}>")
            if not quiet_succ: await ctx.send("Done.")
            await self.set_setup(ctx.guild.id)
            return True
        except Exception as e:
            if str(e) == '_fail': return
            print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            traceback.print_exc()
            info = ""
            if quiet_succ:
                for k, v in kwargs.items(): kwargs[k] = str(v)
                info += f" **Kwargs dump:**\n```{json.dumps(kwargs, indent=4)}```"
            await ctx.send("Something went wrong." + info)
            return False

    @commands.check(checks.moderator_check)
    @commands.group(aliases=['r'])
    async def raid(self, ctx):
        """Setup raid and protection related settings
        By itself this comand doesn't do anything, use subcommands
        """
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.moderator_check)
    @raid.command(aliases=['m'])
    async def manual(self, ctx):
        """Read up the manual
        By itself this comand doesn't do anything except show the manual
        Level explenations

        ✅ **Level 0:**
        - Bot works normally, all commands available normally

        ⚠ **Level 1:**
        - Disable bot commands from non moderators
        *users will be notified on command invoke
        that commands are disabled for them*
        - Welcome message will be posted with a webhook
        instead of by the bot itself (less latency hit)

        🔥 **Level 2:**
        - Disable bot commands from non moderators
        *users will not be not notified on command invoke*
        - Disable image/embed perms in all (public) channels
        - Those who post more than X mentions/spam get muted automatically
        (this includes only people without roles)

        💥 **Level 3:**
        - Same as level 2, with aditionally:
        - Users who post more than X mentions/spam get removed automatically:
        No role = Ban with 1 day message history deleted
        With role = Just kicks them
        """
        raise commands.errors.BadArgument

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.moderator_check)
    @raid.command(aliases=['l', 'lvl'])
    async def level(self, ctx, anti_raid_level: int = -1, max_allowed_mentions: int = 3):
        """Fine tune raid protection level [0-3]"""
        db_guild = None
        pl = {0: '✅', 1: '⚠', 2: '🔥', 3: '💥'}
        arl = 0
        try:
            db_guild = ArGuild.get(ArGuild.id == ctx.guild.id)
            arl = db_guild.anti_raid_level
        except:
            pass
        if anti_raid_level == -1: return await ctx.send(f"Current raid level is **{arl}** {pl[arl]}")
        if anti_raid_level > 3: return await ctx.send("Max level is 3")
        if anti_raid_level < 0: return await ctx.send("Min level is 0")
        if max_allowed_mentions < 0: return await ctx.send("Min max_allowed_mentions is 1")
        # chs = " ".join([str(c.id) for c in channels_to_ignore_for_mention_punishing])
        try:
            db_guild = ArGuild.get(ArGuild.id == ctx.guild.id)
            db_guild.anti_raid_level = anti_raid_level
            db_guild.max_allowed_mentions = max_allowed_mentions
            db_guild.save()
        except:
            db_guild = ArGuild.create(id=ctx.guild.id,
                                      anti_raid_level=anti_raid_level,
                                      max_allowed_mentions=max_allowed_mentions)
        ctx.bot.anti_raid = ArManager.get_ar_data()
        # if chs: chs = '\n' + '\n'.join([c.mention for c in channels_to_ignore_for_mention_punishing])
        await ctx.send(f"Protection level: **{anti_raid_level}** {pl[anti_raid_level]}")
        m = None
        if anti_raid_level > 1:
            edit_channels = []
            m = await ctx.send("Disabling image perms in all (public) channels.")
            for ch in ctx.guild.text_channels:
                dr = ctx.guild.default_role
                overwrites_everyone = ch.overwrites_for(dr)
                if not (overwrites_everyone.embed_links is False and overwrites_everyone.attach_files is False) and \
                        overwrites_everyone.read_messages is not False:
                    edit_channels.append(str(ch.id))
                    overwrites_everyone.embed_links = False
                    overwrites_everyone.attach_files = False
                    await ch.set_permissions(dr, overwrite=overwrites_everyone)
            db_guild.chs_had_img_perms_on = " ".join(edit_channels)
            db_guild.save()
            await m.edit(content="**Disabled imaged perms in all (public) channels.**")

        if anti_raid_level < 2 and db_guild.chs_had_img_perms_on:
            m = await ctx.send("Enabling image perms back in all (public) channels.")
            chs = db_guild.chs_had_img_perms_on.split()
            for ch in ctx.guild.text_channels:
                if str(ch.id) in chs:
                    dr = ctx.guild.default_role
                    overwrites_everyone = ch.overwrites_for(dr)
                    if (overwrites_everyone.embed_links is False and overwrites_everyone.attach_files is False) and \
                            overwrites_everyone.read_messages is not False:
                        overwrites_everyone.embed_links = True
                        overwrites_everyone.attach_files = True
                        await ch.set_permissions(dr, overwrite=overwrites_everyone)
            db_guild.chs_had_img_perms_on = ""
            db_guild.save()
            await m.edit(content="**Enabled imaged perms in all (public) channels.**")

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.moderator_check)
    @raid.command()
    async def lockdown(self, ctx):
        """Same as using `[p]lock all silent`"""
        await dutils.lock_channels(ctx, "all silent")
        await ctx.send(f"To revert thise use the command `{dutils.bot_pfx(ctx.bot, ctx.message)} unlock all silent`")


def setup(bot):
    ext = Serversetup(bot)
    bot.add_cog(ext)
