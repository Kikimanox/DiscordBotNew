import asyncio
import datetime

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.SimplePaginator import SimplePaginator
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
from models.cmds import (db, Guild, Command, CommandsToGuild, CmdsManager)


class Cmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.set_commands()

    def set_commands(self):
        self.bot.all_cmds = CmdsManager.get_commands_formatted()

    @commands.check(checks.moderator_check)
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
        first_arg = args.split(' ')[0]
        if first_arg in ctx.command.all_commands:
            c = ctx.command.all_commands[first_arg]
            if first_arg in ['raw', 'remove', 'inheritcmds', 'icmds'] and not await checks.admin_check(ctx):
                raise commands.MissingPermissions(['Admin'])
            return await ctx.invoke(c, args)  # unsafe, becareful where you use this
        await self.add_cmd_fun(ctx, args)
        self.set_commands()

    @commands.check(checks.admin_check)
    @add.command()
    async def raw(self, ctx, args):
        """
        Raw version of `add` (See help for add)
        """
        d = 0
        await self.add_cmd_fun(ctx, args, raw=True)
        self.set_commands()

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
        self.set_commands()

    async def add_cmd_fun(self, ctx, args, raw=False):
        db_guild = CmdsManager.get_or_create_and_get_guild(ctx.guild.id, ctx.guild.name)
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

        cmd = CmdsManager.get_cmd_based_on_guld(ctx.guild.id, args[0])
        replacing = False
        if cmd:
            await ctx.send('Custom command with that name is already in use, would you like to override it? (y/n)')

            def check(m):
                return (m.content.lower() == 'y' or m.content.lower() == 'n') and \
                       m.author == ctx.author and m.channel == ctx.channel

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=20)
            except asyncio.TimeoutError:
                return await ctx.send("Cancelled overriding.")
            if not reply or reply.content.lower().strip() == 'n':
                return await ctx.send("Cancelled overriding.")
            else:
                replacing = True

        cmdName = args[0]
        cnt = args[1]
        image = True
        color = '0x4f545c'
        if not raw:
            if len(args) > 1 and str(args[1]).startswith('`'):
                if not (str(args[1]).startswith('`') and str(args[-1]).endswith('`')):
                    return await ctx.send('Invalid command usage, please use `.help add` to see the correct usage')
                txt = ' '.join(args[1:])
                cnt = txt[1:-1]
                image = False

                if replacing:
                    cmd.content = cnt
                    cmd.image = image
                    cmd.color = color
                    cmd.author = ctx.message.author.id
                    cmd.save()
                else:
                    cmd = Command.create(author=ctx.author.id,
                                         name=cmdName,
                                         content=cnt,
                                         image=image,
                                         color=color,
                                         raw=False)
                    CommandsToGuild.create(guild=db_guild, command=cmd, )

                return await ctx.send(
                    f'{"Added" if not replacing else "Overrided"} custom{"" if not replacing else ""} '
                    f'**embedded text** command')

            if not str(args[1]).startswith('http'):
                return await ctx.send(
                    '- When adding an **image** custom command please provide a direct link to the image\n'
                    '- When adding a **text** command please start and end your text with \`\n'
                    f'- When adding a multi word trigger command use: '
                    f'{dutils.bot_pfx(ctx.bot, ctx.message)}add "multi words here" <other args>\n'
                    '- For examples check help (`.add` or `.help add`)')

            if len(args) == 3:
                color = args[2]
            image = True
            if replacing:
                cmd.content = args[1]
                cmd.image = image
                cmd.color = color
                cmd.author = ctx.message.author.id
                cmd.save()
            else:
                cmd = Command.create(author=ctx.author.id,
                                     name=cmdName,
                                     content=args[1],
                                     image=image,
                                     color=color,
                                     raw=False)
                CommandsToGuild.create(guild=db_guild, command=cmd, )

            return await ctx.send(
                f'{"Added" if not replacing else "Overrided"} custom{"" if not replacing else ""} '
                f'**image** command')

        else:
            txt = ' '.join(args[1:])
            if not replacing:
                cmd = Command.create(author=ctx.author.id,
                                     name=args[0],
                                     content=txt,
                                     raw=True)
                CommandsToGuild.create(guild=db_guild, command=cmd, )
            else:
                cmd.content = txt
                cmd.save()
            return await ctx.send(
                f'{"Added" if not replacing else "Overrided"} custom{"" if not replacing else ""} '
                f'**raw** command')

    @commands.check(checks.admin_check)
    @commands.command(aliases=["icmds"])
    async def inheritcmds(self, ctx, *, servers):
        """Inherits custom commands from another server.

        `[p]inheritcmd serverID`
        `[p]inheritcmd serverID1$serverID2 $ serverID3` (can inherit multiple servers)
        """
        if '@' in servers: return await ctx.send("Invalid argument (servers)")
        srvs = [s.strip() for s in servers.split("$")]
        db_guild = CmdsManager.get_or_create_and_get_guild(ctx.guild.id, ctx.guild.name)

        for s in srvs:
            try:
                g = self.bot.get_guild(int(s))
                if not g: raise Exception('aaa')
                if g.id == ctx.guild.id: return await ctx.send('You can not inherit from the same server as this one.')
                if CommandsToGuild.select().where(CommandsToGuild.guild == g.id).count() < 1:
                    return await ctx.send(f'The server `{s}` has no custom commands')
            except:
                return await ctx.send(f'Server with the id `{s}` not found.')
        try:
            db_guild.inherits_from = ' '.join(srvs)
            db_guild.save()
        except Exception as e:
            import traceback
            # print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            # traceback.print_exc()
            return await ctx.send(f"Something went wrong in icmds:\n{traceback.format_exc()}")
        self.set_commands()
        return await ctx.send("Done.")

    @commands.group(aliases=["lscmds", "lscmd", "listcmd", "listcommands", "commands", "cmds"])
    async def listcmds(self, ctx):
        """List all available commands"""
        if ctx.invoked_subcommand is None:
            await self.list_cmds_fnc(ctx)

    @listcmds.command()
    async def compact(self, ctx):
        """Very compact view"""
        await self.list_cmds_fnc(ctx, compact=True)

    async def list_cmds_fnc(self, ctx, compact=False):
        if ctx.guild.id not in self.bot.all_cmds: return await ctx.send("This server has no custom commands added")
        cmds = [
            k if compact else f'**{k}** (raw)' if v['raw'] else f'**{k}** (image)' if v['image'] else f'**{k}** (txt)'
            for k, v in self.bot.all_cmds[ctx.guild.id]['cmds'].items()
        ]
        cmds = sorted(cmds)
        icmds_by_g = {}
        if not compact:
            _icmds = [cc for cc in self.bot.all_cmds[ctx.guild.id]['inh_cmd_list']]
            for ic in _icmds:
                for k, v in ic.items():
                    if v['guild_id'] not in icmds_by_g: icmds_by_g[v['guild_id']] = []
                    icmds_by_g[v['guild_id']].append(
                        f'**{k}** (raw)' if v['raw'] else f'**{k}** (image)' if v['image'] else f'**{k}** (txt)'
                    )
                    if k in self.bot.all_cmds[ctx.guild.id]['cmds_name_list']:
                        icmds_by_g[v['guild_id']][-1] = f"~~{icmds_by_g[v['guild_id']][-1]}~~"
            for k, v in icmds_by_g.items():
                icmds_by_g[k] = dutils.getParts2kByDelimiter("**-** " + "\n**-** ".join(v), "\n**-** ", "**-** ", 450)

        if compact:
            icmds = [(f'{c} (i)' if c not in self.bot.all_cmds[ctx.guild.id]['cmds_name_list']
                      else f'~~{c} (i)~~') for c in self.bot.all_cmds[ctx.guild.id]['inh_cmds_name_list']]
            cmds.extend(icmds)
            ret = dutils.getParts2kByDelimiter(' | '.join(cmds), ' | ')
            for r in ret:
                await ctx.send(
                    embed=(Embed(description=r).set_footer(text=f"{'(i) means inherited' if icmds else ''}")))
            return

        ret = "**-** " + "\n**-** ".join(cmds)
        ret = dutils.getParts2kByDelimiter(ret, "\n**-** ", "**-** ", 450)
        embeds = self.make_embeds(icmds_by_g, ret, ctx.guild.name)
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await SimplePaginator(extras=embeds).paginate(ctx)

    def make_embeds(self, icmds, cmds, guild_name):
        embeds = []
        for c in cmds:
            embeds.append(Embed(title=f'Custom cmds for **{guild_name}**\n'
                                      f'Page {len(embeds) + 1}/[MAX]', description=c,
                                color=self.bot.config['BOT_DEFAULT_EMBED_COLOR']))

        for k, v in icmds.items():
            g = self.bot.get_guild(k)
            gu = '**An __unknown__ server**'
            if g: gu = f'**{g.name}**'
            for inh in v:
                embeds.append(Embed(title=f'Inherited cmds from {gu}\n'
                                          f'Page {len(embeds) + 1}/[MAX]', description=inh,
                                    color=self.bot.config['BOT_DEFAULT_EMBED_COLOR']))

        for e in embeds:
            e.title = str(e.title).replace("[MAX]", str(len(embeds)))
        return embeds


async def setup(
    bot: commands.Bot
):
    ext = Cmds(bot)
    await bot.add_cog(ext)
