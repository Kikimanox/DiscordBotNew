import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import env
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
from models.cmds import (db, Guild, Command, CommandsToGuild, CmdsManager)


class Cmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_list = []

    @commands.check(checks.admin_check)
    @commands.group()
    async def add(self, ctx, *, args):
        """Add a custom embedded command

        There are mulitple ways to add commands:
        **Embedded message** (you may assign an embed color by adding a hex color at the end)
        Hex color format is any of the following: #A1B2C3 0xA1B2C3 A1B2C3
        [p]add cmdName \`message content here\`
        [p]add "cmd Name" \`message content here\`
        [p]add piccmd image_url
        [p]add bluepiccmd image_url 0000EE

        Similar applies to `add raw [args...]` But when using that the message will not be
        embedded, aka. the message will be sent RAW!
        """
        a = [cmd for cmd in Command.select()]

        first_arg = args.split(' ')[0]
        if first_arg in ctx.command.all_commands:
            c = ctx.command.all_commands[first_arg]
            return await ctx.invoke(c, args)  # unsafe, becareful where you use this
        await self.add_cmd_fun(ctx, args)

    @commands.check(checks.admin_check)
    @add.command()
    async def raw(self, ctx, args):
        """
        Raw version of `add` (See help for add)
        """
        d = 0
        await self.add_cmd_fun(ctx, args, raw=True)

    @commands.check(checks.admin_check)
    @commands.command()
    async def remove(self, ctx, *, cmdName):
        """Remove a custom command"""
        try:
            cmd = CmdsManager.get_cmd_based_on_guld(ctx.guild.id, cmdName)
            if cmd:
                cmd.delete_instance()
                await ctx.send("Removed.")
            else:
                raise Exception("Didn't find that command here")
        except:
            await ctx.send("The command with that name doens't exist on this server")

    async def add_cmd_fun(self, ctx, args, raw=False):
        db_guild = CmdsManager.create_and_get_guild_if_not_exists(ctx.guild.id, ctx.guild.name)
        args = str(args).replace('\n', ' \n').split(' ')
        if raw: args = args[1:]
        if len(args) <= 1: raise commands.errors.MissingRequiredArgument(ctx.command)
        if args[0][0] == '"':
            args2 = [args[0][1:]]
            i = 1
            for a in args[1:]:
                i += 1
                if a[-1] == '"':
                    args2.append(a[:-1])
                    break
                args2.append(a)
            args2 = [' '.join(args2)]
            args2.extend(args[i:])
            if len(args2) == 1:
                return await ctx.send("Are you trying to make a multiword command name? "
                                      "Did you forget the second qoute `\"`?")
            args = args2
        if len(args[0]) > 32:
            return await ctx.send('Command name is too long, please make it under 32 characters, '
                                  'nobody will remember something that long..')
        if args[0] in self.bot.all_commands: return await ctx.send("Custom command name can not have the same "
                                                                   "name as an already existing bot command.")

        # todo: check if command already exists on the guild

        if raw:
            txt = ' '.join(args[1:])
            cmd = Command.create(author=ctx.author.id,
                                 name=args[0],
                                 content=txt,
                                 raw=True)
            CommandsToGuild.create(guild=db_guild, command=cmd, )
            


def setup(bot):
    ext = Cmds(bot)
    bot.add_cog(ext)
