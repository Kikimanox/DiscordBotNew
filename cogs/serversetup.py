import traceback
import json
import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
from models.serversetup import (Guild, WelcomeMsg, Logging, Webhook, SSManager)


class ServerSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.check(checks.admin_check)
    @commands.group()
    async def setup(self, ctx):
        """Use the subcommands to setup server related stuff

        By itself this command doesn't do anything"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @setup.group()
    async def everything(self, ctx,
                         logging_regular_channel: discord.TextChannel,
                         logging_leavejoin_channel: discord.TextChannel,
                         logging_modlog_channel: discord.TextChannel,
                         hook_logging_id: int,
                         hook_logging_target_ch: discord.TextChannel,
                         hook_leavejoin_id: int,
                         hook_leavejoin_target_ch: discord.TextChannel,
                         hook_modlog_id: int,
                         hook_modlog_target_ch: discord.TextChannel,
                         moderator_role: discord.Role,
                         mute_role: discord.Role):
        """Setup everything at once"""
        await self.do_setup(ctx=ctx, logging_reg=logging_regular_channel, quiet_succ=True)
        await self.do_setup(ctx=ctx, logging_leavejoin=logging_leavejoin_channel, quiet_succ=True)
        await self.do_setup(ctx=ctx, logging_modlog=logging_modlog_channel, quiet_succ=True)
        await self.do_setup(hook_reg=hook_logging_id, hook_reg_target=hook_logging_target_ch, ctx=ctx,
                            quiet_succ=True)
        await self.do_setup(hook_leavejoin=hook_leavejoin_id, hook_leavejoin_target=hook_leavejoin_target_ch, ctx=ctx,
                            quiet_succ=True)
        await self.do_setup(hook_modlog=hook_modlog_id, hook_modlog_target=hook_modlog_target_ch, ctx=ctx,
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
                       f"`{ctx.bot.config['BOT_PREFIX']}setup muterolechperms <role_id>/<role_name>`")

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

    @commands.check(checks.admin_check)
    @setup.group()
    async def muterolenew(self, ctx, role: discord.Role):
        """Setup muterole
        Note, this command may be used with any role, but it's main
        purpose/use is to setup the mute role perms on the channels."""
        await self.do_setup(mute_role=role, ctx=ctx)
        await ctx.send("Stored/updated the muted role in the database.\n"
                       "This doesn't mean the channel permissions are setup though.\n"
                       "If they weren't set by hand yet, you can use:\n"
                       f"`{ctx.bot.config['BOT_PREFIX']}setup muterolechperms <role_id>/<role_name>`\n")

    @commands.check(checks.admin_check)
    @setup.group()
    async def modrole(self, ctx, role: discord.Role):
        """Setup moderator specific role"""
        await self.do_setup(mod_role=role, ctx=ctx)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.group()
    async def muterolechperms(self, ctx, role: discord.Role):
        """Update channel perms for the mute role"""
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

    @commands.check(checks.admin_check)
    @setup.group()
    async def welcomemsg(self, ctx):
        """Main w.m. setup command, use subcommands"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def mainsetup(self, ctx):
        """Go trough the entire setup process"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def title(self, ctx):
        """Fine tune embed title"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def desc(self, ctx):
        """Fine tune embed desscription"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def images(self, ctx):
        """Fine tune embed possible images"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def content(self, ctx):
        """Fine tune message outside of the embed"""
        raise NotImplementedError

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

            else:
                await ctx.send(f"You shouldn't have hit this. oi.. <@!{ctx.bot.config['OWNER_ID']}>")
            if not quiet_succ: await ctx.send("Done.")
            return True
        except Exception as e:
            if str(e) == '_fail': return
            traceback.print_exc()
            info = ""
            if quiet_succ:
                for k, v in kwargs.items(): kwargs[k] = str(v)
                info += f" **Kwargs dump:**\n```{json.dumps(kwargs, indent=4)}```"
            await ctx.send("Something went wrong." + info)
            return False


def setup(bot):
    ext = ServerSetup(bot)
    bot.add_cog(ext)
