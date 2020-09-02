"""Overrides the built-in help formatter.
All help messages will be embed and pretty.
Most of the code stolen from
discord.ext.commands.formatter.py and
converted into embeds instead of codeblocks.
Docstr on cog class becomes category.
Docstr on command definition becomes command
summary and usage.
Use [p] in command docstr for bot prefix.
See [p]help here for example.
await bot.formatter.format_help_for(ctx, command)
to send help page for command. Optionally pass a
string as third arg to add a more descriptive
message to help page.
e.g. format_help_for(ctx, ctx.command, "Missing required arguments")
discord.py 1.0.0a
Experimental: compatibility with 0.16.8
Copyrights to logic of code belong to Rapptz (Danny)
Everything else credit to SirThane#1780
Pagination added by appu1232"""

import discord
from discord.ext import commands
from discord.ext.commands.help import HelpCommand, Paginator, DefaultHelpCommand
from utils.SimplePaginator import SimplePaginator
import asyncio
import sys
import re
import inspect
import itertools
import traceback

empty = u'\u200b'

_mentions_transforms = {
    '@everyone': '@\u200beveryone',
    '@here': '@\u200bhere'
}

_mention_pattern = re.compile('|'.join(_mentions_transforms.keys()))

orig_help = None
wiki_link = '\nList of all available commands'

class Help(DefaultHelpCommand):

    def __init__(self, **options):
        self.show_hidden = options.pop('show_hidden', False)
        self.verify_checks = options.pop('verify_checks', True)
        self.command_attrs = attrs = options.pop('command_attrs', {})
        attrs.setdefault('name', 'help')
        attrs.setdefault('help', 'Shows this message')
        self.context = None
        self._command_impl = None
        self.width = 80
        self.indent = 2
        self.sort_commands = True
        self.dm_help = False
        self.dm_help_threshold = 1000
        self.show_check_failure = False
        self.commands_heading = "Commands:"
        self.no_category = 'No Category'
        self.paginator = Paginator()

    def get_ending_note(self):
        # command_name = self.context.invoked_with
        return "Type {0}help <command> for more info on a command.\n" \
               "You can also type {0}help <category> for more info on a category.".format(self.clean_prefix)

    def get_command_signature(self, command):
        """Retrieves the signature portion of the help page.
        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.
        Returns
        --------
        :class:`str`
            The signature for the command.
        """

        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = '[%s|%s]' % (command.name, aliases)
            if parent:
                fmt = parent + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent else parent + ' ' + command.name
        return '%s%s %s' % (self.clean_prefix, alias, command.signature)

    def has_subcommands(self):
        """:class:`bool`: Specifies if the command has subcommands."""
        return isinstance(self.command, commands.GroupMixin)

    def is_cog(self):
        """:class:`bool`: Specifies if the command being formatted is actually a cog."""
        return not self.is_bot() and not isinstance(self.command, commands.Command)

    def is_bot(self):
        """:class:`bool`: Specifies if the command being formatted is the bot itself."""
        return self.command is self.context.bot

    def shorten(self, text):
        """Shortens text to fit into the :attr:`width`."""
        if len(text) > self.width:
            return text[:self.width - 3] + '...'
        return text

    async def filter_command_list(self):
        """Returns a filtered list of commands based on the two attributes
        provided, :attr:`show_check_failure` and :attr:`show_hidden`.
        Also filters based on if :meth:`~.HelpFormatter.is_cog` is valid.
         Returns
        --------
        iterable
            An iterable with the filter being applied. The resulting value is
            a (key, value) :class:`tuple` of the command name and the command itself.
        """

        def sane_no_suspension_point_predicate(tup):
            cmd = tup[1]
            if self.is_cog():
                # filter commands that don't exist to this cog.
                if cmd.cog is not self.command:
                    return False

            if cmd.hidden and not self.show_hidden:
                return False

            return True

        async def predicate(tup):
            if sane_no_suspension_point_predicate(tup) is False:
                return False

            cmd = tup[1]
            try:
                return await cmd.can_run(self.context)
            except commands.errors.CommandError:
                return False

        iterator = self.command.all_commands.items() if not self.is_cog() else self.context.bot.all_commands.items()
        if self.show_check_failure:
            return filter(sane_no_suspension_point_predicate, iterator)

        # Gotta run every check and verify it
        ret = []
        for elem in iterator:
            valid = await predicate(elem)
            if valid:
                ret.append(elem)

        return ret

    def _add_subcommands(self, cmds):
        list_entries = []
        entries = ''
        for name, command in cmds:
            if name in command.aliases:
                # skip aliases
                continue

            new_short_doc = command.short_doc.replace('[p]', self.clean_prefix)

            if self.is_cog() or self.is_bot():
                name = '{0}{1}'.format(self.clean_prefix, name)

            if len(entries + '**{0}**  -  {1}\n'.format(name, new_short_doc)) > 1000:
                list_entries.append(entries)
                entries = ''
            entries += '**{0}**  -  {1}\n'.format(name, new_short_doc)
        list_entries.append(entries)
        return list_entries

    def _add_subcommands_to_page(self, max_width, commands):
        for name, command in commands:
            if name in command.aliases:
                # skip aliases
                continue
            width_gap = discord.utils._string_width(name) - len(name)
            entry = '  {0:<{width}} {1}'.format(name, command.short_doc, width=max_width - width_gap)
            shortened = self.shorten(entry)
            self.paginator.add_line(shortened)

    def pm_check(self, ctx):
        return isinstance(ctx.channel, discord.abc.PrivateChannel)

    @property
    def me(self):
        return self.context.me

    @property
    def bot_all_commands(self):
        return self.context.bot.all_commands

    @property
    def avatar(self):
        return str(self.context.bot.user.avatar_url_as(format='png'))

    @property
    def color(self):
        if self.pm_check(self.context):
            return 0
        else:
            return self.me.color

    @property
    def author(self):
        # Get author dict with username if PM and display name in guild
        if self.pm_check(self.context):
            name = self.context.bot.user.name
        else:
            name = self.me.display_name if not '' else self.context.bot.user.name
        author = {
            'name': '{0} Help Manual'.format(name),
            'icon_url': self.avatar
        }
        return author

    @property
    def destination(self):
        return self.context.message.channel

    async def format(self, ctx, command):
        """Formats command for output.
        Returns a dict used to build embed"""

        # All default values for embed dict
        self.command = command
        self.context = ctx
        emb = {
            'embed': {
                'title': '',
                'description': '',
            },
            'footer': {
                'text': self.get_ending_note()
            },
            'fields': []
        }

        emb['embed']['description'] = wiki_link

        if isinstance(command, discord.ext.commands.core.Command):
            # <signature portion>
            # emb['embed']['title'] = emb['embed']['description']
            emb['embed']['description'] = '`Syntax: {0}`'.format(self.get_command_signature(command))

            # <long doc> section
            if command.help:
                cmd_help = command.help.replace('[p]', self.clean_prefix)
                name = '{0}'.format(cmd_help.split('\n\n')[0])
                name_length = len(name)
                name = name.replace('[p]', self.clean_prefix)
                value = cmd_help[name_length:]
                if value == '':
                    name = '{0}'.format(cmd_help.split('\n')[0])
                    name_length = len(name)
                    value = cmd_help[name_length:]
                if value == '':
                    value = empty
                if len(value) > 1024:
                    first = value[:1024].rsplit('\n', 1)[0]
                    list_values = [first, value[len(first):]]
                    while len(list_values[-1]) > 1024:
                        next_val = list_values[-1][:1024].rsplit('\n', 1)[0]
                        remaining = [next_val, list_values[-1][len(next_val):]]
                        list_values = list_values[:-1] + remaining
                    for new_val in list_values:
                        field = {
                            'name': name,
                            'value': new_val,
                            'inline': False
                        }
                        emb['fields'].append(field)
                else:
                    field = {
                        'name': name,
                        'value': value,
                        'inline': False
                    }
                    emb['fields'].append(field)

            # end it here if it's just a regular command
            if not self.has_subcommands():
                return emb

        def category(tup):
            # Turn get cog (Category) name from cog/list tuples
            cog = tup[1].cog_name
            return '**__{0}:__**'.format(cog) if cog is not None else '**__\u200bNo Category:__**'

        # Get subcommands for bot or category
        filtered = await self.filter_command_list()

        if self.is_bot():
            # Get list of non-hidden commands for bot.
            data = sorted(filtered, key=category)
            for category, commands in itertools.groupby(data, key=category):
                # there simply is no prettier way of doing this.

                commands = sorted(commands)
                if len(commands) > 0:
                    for count, subcommands in enumerate(self._add_subcommands(commands)):
                        field = {
                            'inline': False
                        }
                        if count > 0:
                            field['name'] = category + ' pt. {}'.format(count + 1)
                        else:
                            field['name'] = category
                        field['value'] = subcommands  # May need paginated
                        emb['fields'].append(field)

        else:
            # Get list of commands for category
            filtered = sorted(filtered)
            if filtered:
                for subcommands in self._add_subcommands(filtered):
                    field = {
                        'name': '**__Commands:__**' if not self.is_bot() and self.is_cog() else '**__Subcommands:__**',
                        'value': subcommands,  # May need paginated
                        'inline': False
                    }

                    emb['fields'].append(field)

        return emb

    async def format_help_for(self, ctx, command_or_bot, reason: str = None):
        """Formats the help page and handles the actual heavy lifting of how  ### WTF HAPPENED?
        the help command looks like. To change the behaviour, override the
        :meth:`~.HelpFormatter.format` method.
        Parameters
        -----------
        ctx: :class:`.Context`
            The context of the invoked help command.
        command_or_bot: :class:`.Command` or :class:`.Bot`
            The bot or command that we are getting the help of.
        Returns
        --------
        list
            A paginated output of the help command.
        """
        self.context = ctx
        self.command = command_or_bot
        emb = await self.format(ctx, command_or_bot)

        if reason:
            emb['embed']['title'] = "{0}".format(reason)

        embeds = []
        embed = discord.Embed(color=self.color, **emb['embed'])
        embed.set_author(name='{0} Help Manual Page 1'.format(self.context.bot.user.name), icon_url=self.avatar)
        embed.set_footer(**emb['footer'])
        txt = ""
        for field in emb['fields']:
            txt += field["name"] + field["value"]
            if len(txt) > 1000 and len(embed.fields) != 0:
                embeds.append(embed)
                txt = field["name"] + field["value"]
                del embed
                embed = discord.Embed(color=self.color, **emb['embed'])
                embed.set_footer(**emb['footer'])
            embed.add_field(**field)
        embeds.append(embed)
        embed.set_footer(**emb['footer'])
        for page, embed in enumerate(embeds):
            embed.set_author(name='{} Help Manual Page {}/{}'.format(self.context.bot.user.name, page + 1, len(embeds)),
                             icon_url=self.avatar)
        return embeds

        def simple_embed(self, title=None, description=None, color=None, author=None):
            # Shortcut
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text=self.bot.formatter.get_ending_note())
            if author:
                embed.set_author(**author)
            return embed

        def cmd_not_found(self, cmd, color=0):
            # Shortcut for a shortcut. Sue me
            embed = self.simple_embed(title=self.bot.command_not_found.format(cmd),
                                      description='Commands are case sensitive. Please check your spelling and try again',
                                      color=color, author=self.author)
            return embed

    def shorten_text(self, text):
        """Shortens text to fit into the :attr:`width`."""
        if len(text) > self.width:
            return text[:self.width - 3] + '...'
        return text

    def add_indented_commands(self, commands, *, heading, max_size=None):
        """Indents a list of commands after the specified heading.
        The formatting is added to the :attr:`paginator`.
        The default implementation is the command name indented by
        :attr:`indent` spaces, padded to ``max_size`` followed by
        the command's :attr:`Command.short_doc` and then shortened
        to fit into the :attr:`width`.
        Parameters
        -----------
        commands: Sequence[:class:`Command`]
            A list of commands to indent for output.
        heading: :class:`str`
            The heading to add to the output. This is only added
            if the list of commands is greater than 0.
        max_size: Optional[:class:`int`]
            The max size to use for the gap between indents.
            If unspecified, calls :meth:`get_max_size` on the
            commands parameter.
        """

        if not commands:
            return

        self.paginator.add_line(heading)
        max_size = max_size or self.get_max_size(commands)

        get_width = discord.utils._string_width
        for command in commands:
            name = command.name
            width = max_size - (get_width(name) - len(name))
            entry = '{0}{1:<{width}} {2}'.format(self.indent * ' ', name, command.short_doc, width=width)
            self.paginator.add_line(self.shorten_text(entry))

    async def send_page(self, ctx, help_type):
        embeds = await self.format_help_for(ctx, help_type)
        if len(embeds) == 1:
            await ctx.send(content=None, embed=embeds[0])
        else:
            await SimplePaginator(extras=embeds).paginate(ctx)

    async def send_bot_help(self, mapping):
        await self.send_page(self.context, self.context.bot)

    async def send_command_help(self, command):
        await self.send_page(self.context, command)

    async def send_group_help(self, group):
        await self.send_page(self.context, group)

    async def send_cog_help(self, cog):
        await self.send_page(self.context, cog)
