import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils


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
    async def everything(self, ctx):
        """Setup everything at once, read instructions.

        Stuff
        """
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @setup.group()
    async def webhooks(self, ctx):
        """Webhook related setups, use subcommands

        By itself this command doesn't do anything

        Setup XYZ webhook by providing it's id and target ch

        Setup X channel and target_channel should match

        ***WARNING!!!***
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
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def leavejoin(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Leave and join logging hook"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def modlog(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Moderation log logging hook"""
        raise NotImplementedError

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
        await self.do_setup(ctx=ctx, logging_ch=channel)

    @commands.check(checks.admin_check)
    @logging.command()
    async def leavejoin(self, ctx, channel: discord.TextChannel):
        """Logging for leave/join messages"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @logging.command()
    async def modlog(self, ctx, channel: discord.TextChannel):
        """Logging for moderation related actions"""
        raise NotImplementedError

    @commands.check(checks.admin_check)
    @setup.group()
    async def muterole(self, ctx, role: discord.Role):
        """Setup muterole"""
        await ctx.send("Aight")

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
        hook_reg = kwargs.get('hook_reg', None)
        hook_reg_target = kwargs.get('hook_reg_target', None)
        hook_leavejoin = kwargs.get('hook_leavejoin', None)
        hook_leavejoin_target = kwargs.get('hook_leavejoin_target', None)
        hook_modlog = kwargs.get('hook_modlog', None)
        hook_modlog_target = kwargs.get('hook_modlog_target', None)

        logging_reg = kwargs.get('logging_ch', None)
        logging_leavejoin = kwargs.get('logging_ch', None)
        logging_modlog = kwargs.get('logging_ch', None)

        mute_role = kwargs.get('mute_role', None)

        if logging_reg and len(kwargs) == 2:
            pass


def setup(bot):
    ext = ServerSetup(bot)
    bot.add_cog(ext)
