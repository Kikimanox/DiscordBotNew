import itertools
import logging
from difflib import SequenceMatcher
from typing import List, Optional, Union

from discord import Embed, utils, Member, Webhook, app_commands, Interaction, colour, Reaction, Message
from discord.channel import TextChannel, Thread, VoiceChannel, StageChannel, ForumChannel, CategoryChannel
from discord.ext import commands, tasks

import utils.checks as checks
import utils.discordUtils as dutils
from models.club_data import ClubData
from models.views import ConfirmCancelView, PaginationView
from utils.SimplePaginator import SimplePaginator
from utils.dataIOa import dataIOa
from models.react_command_to_delete import CommandOwner

logger = logging.getLogger(f"info")
error_logger = logging.getLogger(f"error")


# TODO return back the verification channel

class Ignorethis(commands.Cog):
    club_data: List[ClubData] = []
    command_owner_dict = {}

    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot
        verification_channel = bot.config["verification_channel"]
        # self.verification_channel_id = 931192723447349268
        self.verification_channel_id = verification_channel
        self.onk_bot_channel = 695297906529271888
        self.gallery_wh = None

        self.clubs_path = 'data/clubs.json'

        self.club_update_info.start()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member):
        if user != self.bot.user:
            x_mark = '\U0000274c'
            if str(reaction.emoji) == x_mark:
                message_id = f"{reaction.message.channel.id}/{reaction.message.id}"
                value: CommandOwner
                value = self.command_owner_dict.get(message_id)
                if value is not None:
                    delete_check = value.check_if_delete(
                        member=user,
                        bot=self.bot,
                        reaction=reaction
                    )
                    if delete_check:
                        message = reaction.message
                        await message.delete()
                        self.command_owner_dict.pop(message_id)

    async def message_sending(
            self,
            content_message: str,
            ctx: Optional[commands.Context] = None,
            delete_after: Optional[float] = None
    ) -> Optional[Message]:
        try:
            if ctx.interaction is not None:
                message = await ctx.send(
                    content=content_message,
                    delete_after=delete_after
                )
                await self.message_context_save_for_deletion(
                    message,
                    ctx
                )
                return message
            else:
                channel = ctx.channel
                message = await channel.send(
                    content=content_message,
                    delete_after=delete_after
                )
                await self.message_context_save_for_deletion(message, ctx)
                return message
        except Exception as ex:
            error_logger.error(f"{ex}")
            return None

    async def message_context_save_for_deletion(
            self,
            message: Message,
            ctx: commands.Context
    ):
        message_id = f"{message.channel.id}/{message.id}"
        value = CommandOwner(
            message=message,
            author_id=ctx.author.id
        )
        self.command_owner_dict.update(
            {message_id: value}
        )

    def initialize_clubs(self):
        logger.info("initialized the clubs")
        self.club_data.clear()
        dataIOa.create_file_if_doesnt_exist(self.clubs_path, '{}')
        clubs_data = dataIOa.load_json(self.clubs_path)

        values: dict
        temp_data: List[ClubData] = []
        for key, values in clubs_data.items():
            value = ClubData(
                club_name=key,
                club_data=values
            )
            temp_data.append(value)

        """
        Multiple sort, since the reverse=False we need to reverse the member count and pings too.
        Now it would sort with:
        1st highest number of members
        2nd highest number of pings 
        3rd sorted alphabetically
        """
        self.club_data = sorted(temp_data, key=lambda x: (-x.member_count, -x.pings, x.club_name))

    @tasks.loop(hours=24)
    async def club_update_info(self):
        """
        updates all of the club info every 1 day
        """
        logger.info("Updating the clubs")
        self.initialize_clubs()

    # @commands.check(checks.onk_server_check)
    @commands.hybrid_command(
        name="createclub",
        description="Create a new club"
    )
    @app_commands.describe(
        club_name="Name of the club",
        description="Description of the club"
    )
    async def create_club(
            self,
            ctx: commands.Context,
            club_name: str,
            *,
            description: str
    ):
        """Create a new club
        Usage:
        `[p]createclub yuri A club for the greatest form of love`
        `[p]createclub pokemon Only true nerds allowed`
        `[p]createclub pits Thanks Appu.`
        After you have created a club it will be active once
        a server staff member will verify the club.
        """
        club_name = club_name.lower()
        if '*' in club_name or '*' in description:
            return await ctx.send("The club name can not include the character `*`, please try again.")

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)

        if club_name in clubs_data:
            await self.message_sending(
                content_message='💢 A club with this name already exists',
                ctx=ctx
            )
            return

        await self.create_club_approval(ctx=ctx, club_name=club_name, description=description)

    async def create_club_approval(
            self,
            ctx: commands.Context,
            club_name: str,
            description: str
    ):
        # channel_id = ctx.channel.id
        # ver_ch = ctx.guild.get_channel_or_thread(self.verification_channel_id)
        # onk_guild = self.bot.get_guild(695200821910044783)
        # ver_ch = onk_guild.get_channel_or_thread(self.verification_channel_id)

        ver_ch = ctx.channel
        if not ver_ch:
            return await ctx.send("Can't find verification channel (check the id for that)")
        club_created_message = await ctx.send(
            "The club has been created, waiting for server staff aproval, you will be notified in dms"
            " once the club has been verified or denied.")
        em = Embed(title='A new club has been created', color=self.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                   description=f'**Club Name:** {club_name}\n'
                               f'**Creator:** {ctx.author.mention} ({ctx.author.name}) id: {ctx.author.id}\n'
                               f'**Description:** {description}')
        await ver_ch.send(embed=em)

        view = ConfirmCancelView(timeout=None)
        view_message = await ver_ch.send(view=view)
        await view.wait()
        await view_message.delete()

        club_creator = ctx.author
        club_creator_id = club_creator.id

        if view.value is True:

            path = 'data/clubs.json'
            dataIOa.create_file_if_doesnt_exist(path, '{}')
            clubs_data = dataIOa.load_json(path)
            clubs_data[club_name] = {'creator': club_creator_id, 'desc': description,
                                     'members': [club_creator_id], 'pings': 0}
            dataIOa.save_json(path, clubs_data)

            await club_creator.send(f'The club **{club_name}** has been approved ✅')
            await club_created_message.edit(content=f'The club **{club_name}** has been '
                                                    f'approved by {view.member_click} ✅')
            self.initialize_clubs()
        else:
            await club_creator.send(f'The club **{club_name}** has been denied ❌')
            await club_created_message.edit(content=f'The club **{club_name}** has been '
                                                    f'denied by {view.member_click} ❌')

    @commands.check(checks.onk_server_check_admin)
    @commands.command()
    async def createclubs(self, ctx: commands.Context, *, clubs):
        """Multiple clubs"""
        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        clubs = clubs.split()
        for c in clubs:
            c = c.lower()
            if c in clubs_data:
                c = c.replace('@', '@\u200b')
                return await ctx.send(f'💢 `{c}` already exists')

        ret = ""
        for c in clubs:
            c = c.lower()
            clubs_data[c] = {'creator': ctx.message.author.id, 'desc': f"[create clubs command]"
                                                                       f"({ctx.message.jump_url})",
                             'members': [ctx.message.author.id], 'pings': 0}
            ret += f"✅ {c}\n"
        clbs = '\n'.join([f'`{c.lower()}`' for c in clubs])
        confirm = await dutils.prompt(ctx, f"This will create the club(s):\n{clbs}".replace('@', '@\u200b'))
        if confirm:
            dataIOa.save_json(path, clubs_data)
            await ctx.send(ret)
        else:
            await ctx.send("Cancelling.")

    # @commands.check(checks.onk_server_check)
    @commands.hybrid_command(
        name="clubinfo",
        description="Display info for a club if it exists"
    )
    @app_commands.describe(
        club_name="Name of the club",
    )
    async def club_info(
            self,
            ctx: commands.Context,
            club_name: str
    ):
        """Display info for a club if it exists"""
        club_name = club_name.lower()

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        if club_name in clubs_data:
            club = clubs_data[club_name]
            creator = ctx.guild.get_member(int(club['creator']))
            mems = [(str(ctx.guild.get_member(u))) for u in club['members'] if ctx.guild.get_member(u)]
            em = Embed(title=f'Club: {club_name}', color=creator.color,
                       description=f'**Creator:** {creator.mention} ({creator.name})\n'
                                   f'**Description:** {club["desc"]}\n'
                                   f'**Ping count:** {club["pings"]}\n\n'
                                   f'**Members:** {", ".join(mems)}')
            await ctx.send(embed=em)
        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await ctx.send(f'{emote} No such club found, did you perhaps mean `{suggestion}`')

    # @commands.check(checks.onk_server_check)
    @commands.hybrid_command(
        name="listclubs",
        description="Optional parameter for checking which clubs members are a part of it"
    )
    @app_commands.describe(
        user_1="Check the club the user is in",
        user_2="Check the club the user is in",
        user_3="Check the club the user is in",
        user_4="Check the club the user is in",
        user_5="Check the club the user is in",
    )
    async def listclubs(
            self,
            ctx: commands.Context,
            user_1: Optional[Member] = None,
            user_2: Optional[Member] = None,
            user_3: Optional[Member] = None,
            user_4: Optional[Member] = None,
            user_5: Optional[Member] = None,
    ):
        """Display all clubs
        Optional parameter for checking which clubs members are a part of it, ex:
        `[p]listclubs Kiki`
        `[p]listclubs @Kiki`
        `[p]listclubs 174406433603846145`
        `[p]listclubs A B`
        `[p]listclubs Kiki Neil Snky`
        `[p]listclubs 174406433603846145 Neil @Rollin_Styles`
        For multiple members the command works with **and**
        meaning that in the first example it will
        find clubs where A and B are both in."""

        members: list[int] = []
        if user_1 is not None:
            members.append(user_1.id)
        if user_2 is not None:
            members.append(user_2.id)
        if user_3 is not None:
            members.append(user_3.id)
        if user_4 is not None:
            members.append(user_4.id)
        if user_5 is not None:
            members.append(user_5.id)

        current_page = 0

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)

        values: dict
        temp_data: List[ClubData] = []
        for key, values in clubs_data.items():
            value = ClubData(
                club_name=key,
                club_data=values
            )
            if len(members) == 0:
                temp_data.append(value)
            else:
                if_they_are_club_members = value.check_if_all_of_list_exist_on_this_club(members)
                if if_they_are_club_members:
                    temp_data.append(value)

        messages: list[str] = []
        if len(temp_data) == 0:
            await ctx.send("No clubs found.")
            return
        current_message = ""
        count = 0
        for item in temp_data:
            count += 1
            current_message += f"**{item.club_name}**\n" \
                               f"Members: {item.member_count} | Ping count: {item.pings}\n" \
                               f"{item.description}\n\n"
            if count > 8 or len(current_message) > 1500:
                messages.append(current_message)
                current_message = ""
                count = 0

        if len(current_message) > 0:
            messages.append(current_message)

        embed = Embed(
            description=messages[current_page]
        )
        embed.set_footer(text=f"page {current_page + 1}/{len(messages)}")
        embed_message = await ctx.send(embed=embed)
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        channel = self.bot.get_guild(guild_id).get_channel_or_thread(channel_id)

        while True:
            view = PaginationView(
                author=ctx.author,
                clubs=messages,
                current_page=current_page,
                timeout=300
            )

            view_message = await channel.send(view=view)
            await view.wait()

            current_page = view.current_page
            value = view.value
            await view_message.delete()
            if value is None:
                break
            else:
                new_embed = Embed(
                    description=messages[current_page]
                )
                new_embed.set_footer(text=f"page {current_page + 1}/{len(messages)}")
                await embed_message.edit(
                    embed=new_embed
                )

    # @commands.check(checks.onk_server_check)
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    @commands.hybrid_command(
        name="pingclub",
        aliases=["ping"],
        description="Ping a club"
    )
    @app_commands.describe(
        club_name="You can only ping a club you are part of. If you don't see any choices mean you "
                  "are not part of any club",
    )
    async def ping_club(
            self,
            ctx: commands.Context,
            club_name: str,
            *, rest="Anything else that you'd like to add"
    ):
        """Ping a club"""
        club_name = club_name.lower()

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        if club_name in clubs_data:
            club = clubs_data[club_name]
            # creator = ctx.guild.get_member(int(club['creator']))
            mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
            if ctx.author not in mems and not ctx.author.guild_permissions.administrator:
                return await ctx.send(f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                                      f"You can't ping a club you're not a part of")
            pings = ['']
            clubs_data[club_name]['pings'] += 1
            dataIOa.save_json(path, clubs_data)
            cur_idx = 0
            for m in mems:
                pings[cur_idx] += m.mention + ' '
                if len(pings[cur_idx]) + len(club_name) > 1900:
                    cur_idx += 1
                    pings.append('')

            for p in pings:
                if p:
                    await ctx.send(f'Club: {club_name} {p}')

        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await ctx.send(f'{emote} No such club found, did you perhaps mean `{suggestion}`')

    @commands.HybridCommand.autocomplete(ping_club, "club_name")
    async def club_autocomplete_author_part_of(
            self,
            interaction: Interaction,
            current: str
    ) -> List[app_commands.Choice[str]]:
        author_id = interaction.user.id
        club_list = []

        try:
            for clubs in self.club_data:
                check_if_author_in_the_club = clubs.check_if_author_is_in_the_club(author_id=author_id)
                if not check_if_author_in_the_club:
                    continue
                if len(current) == 0:
                    item = app_commands.Choice(
                        name=clubs.club_name,
                        value=clubs.club_name
                    )
                    club_list.append(item)
                else:
                    if current.lower() in clubs.club_name.lower() or current.lower() in clubs.description.lower():
                        item = app_commands.Choice(
                            name=clubs.club_name,
                            value=clubs.club_name
                        )
                        club_list.append(item)

                if len(club_list) > 24:
                    break
        except Exception as ex:
            error_logger.error(ex)

        return club_list

    # @commands.check(checks.onk_server_check)
    @commands.hybrid_command(
        name="pingclubs",
        aliases=["ping2"],
        description="Ping multiple clubs up to 5 clubs at a time"
    )
    @app_commands.describe(
        club_1="Club 1",
        club_2="Club 2",
        club_3="Club 3",
        club_4="Club 4",
        club_5="Club 5",
    )
    @app_commands.autocomplete(
        club_1=club_autocomplete_author_part_of,
        club_2=club_autocomplete_author_part_of,
        club_3=club_autocomplete_author_part_of,
        club_4=club_autocomplete_author_part_of,
        club_5=club_autocomplete_author_part_of,
    )
    async def ping_clubs(
            self,
            ctx: commands.Context,
            club_1: Optional[str] = None,
            club_2: Optional[str] = None,
            club_3: Optional[str] = None,
            club_4: Optional[str] = None,
            club_5: Optional[str] = None,
    ):
        """Ping multiple clubs, please see detailed usage
        Syntax:
        `[p]ping2 club1 club2 club3; any other content you wish`
        `[p]ping2 club1 club2`
        Example:
        Club Yuri: ['user1', 'user2']
        Club Fate: ['user1', 'user3']
        This command works with the **OR** or **UNION** operator.
        When doing `[p]ping2 yuri fate; cool Eresh x Ishtar pics`
        The bot will ping the users: @user1 @user2 @user3
        """
        clubs: list[str] = []
        if club_1 is not None:
            clubs.append(club_1)
        if club_2 is not None:
            clubs.append(club_2)
        if club_3 is not None:
            clubs.append(club_3)
        if club_4 is not None:
            clubs.append(club_4)
        if club_5 is not None:
            clubs.append(club_5)
        if len(clubs) < 2:
            await self.message_sending(
                content_message="Need at least 2 clubs for this command",
                ctx=ctx,
                delete_after=15
            )
            return

        all_ok = await self.check_if_clubs_exist(ctx, clubs)

        if all_ok:
            path = 'data/clubs.json'
            dataIOa.create_file_if_doesnt_exist(path, '{}')
            clubs_data = dataIOa.load_json(path)
            mems_all = []
            clubs_all = ""
            for club_name in clubs:
                club = clubs_data[club_name]
                mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
                clubs_data[club_name]['pings'] += 1
                mems_all = list({*mems_all, *mems})
                clubs_all += club_name + ', '
            dataIOa.save_json(path, clubs_data)

            pings = ['']
            cur_idx = 0
            for m in mems_all:
                pings[cur_idx] += m.mention + ' '
                if len(pings[cur_idx]) + len(clubs_all) > 1900:
                    cur_idx += 1
                    pings.append('')

            for p in pings:
                if p:
                    await self.message_sending(
                        content_message=f'Clubs: {clubs_all[:-2]} {p}',
                        ctx=ctx
                    )

    async def check_if_clubs_exist(
            self,
            ctx: commands.Context,
            clubs
    ) -> bool:
        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        for c in clubs:
            if c not in clubs_data:
                suggestion = self.findMostSimilar(c, [*clubs_data])
                emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
                emote = "💢" if not emote_test else str(emote_test)
                await self.message_sending(
                    content_message=f'{emote} A club in your list is invalid, did you perhaps mean `{suggestion}`'
                                    f' for that one? (invalid club: '
                                    f'`{dutils.cleanUpBannedWords(["@everyone", "@here"], c)}`)',
                    ctx=ctx,
                    delete_after=60
                )
                return False
            club = clubs_data[c]
            mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
            if ctx.author not in mems and not ctx.author.guild_permissions.administrator:
                await self.message_sending(
                    content_message=f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                                    f"You can't ping a club you're not a part of (`{c}`)",
                    ctx=ctx,
                    delete_after=15
                )
                return False
        return True

    # @commands.check(checks.onk_server_check)
    @commands.hybrid_command(
        name="joinclub",
        aliases=["join"],
        description="Join a club"
    )
    @app_commands.describe(
        club_name="Name of the club",
    )
    async def join_club(
            self,
            ctx: commands.Context,
            club_name: str
    ):
        """Join a club"""
        club_name = club_name.lower()

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        if club_name in clubs_data:
            club = clubs_data[club_name]
            mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
            if ctx.author in mems:
                await self.message_sending(
                    content_message=f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                                    f"You are already in this club {club_name}",
                    ctx=ctx
                )
                return
            clubs_data[club_name]['members'].append(ctx.author.id)
            dataIOa.save_json(path, clubs_data)
            await self.message_sending(
                content_message=f"{ctx.author.mention} has joined the club {club_name}",
                ctx=ctx,
            )
            self.initialize_clubs()
        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await self.message_sending(
                content_message=f'{emote} No such club found, did you perhaps mean `{suggestion}`',
                ctx=ctx
            )

    @commands.HybridCommand.autocomplete(join_club, "club_name")
    async def club_autocomplete_author_not_member_of_club(
            self,
            interaction: Interaction,
            current: str
    ) -> List[app_commands.Choice[str]]:
        author_id = interaction.user.id
        club_list = []

        try:
            for clubs in self.club_data:
                check_if_author_in_the_club = clubs.check_if_author_is_in_the_club(author_id=author_id)
                if check_if_author_in_the_club:
                    continue
                if len(current) == 0:
                    item = app_commands.Choice(
                        name=clubs.club_name,
                        value=clubs.club_name
                    )
                    club_list.append(item)
                else:
                    if current.lower() in clubs.club_name.lower() or current.lower() in clubs.description.lower():
                        item = app_commands.Choice(
                            name=clubs.club_name,
                            value=clubs.club_name
                        )
                        club_list.append(item)

                if len(club_list) > 24:
                    break
        except Exception as ex:
            error_logger.error(ex)

        return club_list

    # @commands.check(checks.onk_server_check)
    @commands.hybrid_command(
        name="leaveclub",
        aliases=["leave"],
        description="Leave a club"
    )
    @app_commands.describe(
        club_name="You can leave a club you are part of. If you don't see any choices mean you are not part of any club"
    )
    @app_commands.autocomplete(club_name=club_autocomplete_author_part_of)
    async def leave_club(
            self,
            ctx: commands.Context,
            club_name
    ):
        """Leave a club"""
        club_name = club_name.lower()

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        if club_name in clubs_data:
            club = clubs_data[club_name]
            mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
            if ctx.author in mems:
                clubs_data[club_name]['members'].remove(ctx.author.id)
                dataIOa.save_json(path, clubs_data)
                await self.message_sending(
                    content_message=f"{ctx.author.mention} has left the club {club_name}",
                    ctx=ctx,
                    delete_after=60
                )
                self.initialize_clubs()
            else:
                await self.message_sending(
                    content_message=f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                                    f"You are not even in this club {club_name}",
                    ctx=ctx,
                    delete_after=60
                )
                return
        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await self.message_sending(
                content_message=f'{emote} No such club found, did you perhaps mean `{suggestion}`',
                ctx=ctx,
                delete_after=60
            )

    @commands.HybridCommand.autocomplete(club_info, "club_name")
    async def club_autocomplete(
            self,
            interaction: Interaction,
            current: str
    ) -> List[app_commands.Choice[str]]:

        club_list = []

        try:
            for clubs in self.club_data:
                if len(current) == 0:
                    item = app_commands.Choice(
                        name=clubs.club_name,
                        value=clubs.club_name
                    )
                    club_list.append(item)
                else:
                    if current.lower() in clubs.club_name.lower() or current.lower() in clubs.description.lower():
                        item = app_commands.Choice(
                            name=clubs.club_name,
                            value=clubs.club_name
                        )
                        club_list.append(item)

                if len(club_list) > 24:
                    break
        except Exception as ex:
            error_logger.error(ex)

        return club_list

    @commands.check(checks.onk_server_check_admin)
    @commands.hybrid_command(
        name="deleteclub",
        description="Only those who hold power can delete clubs. beware"
    )
    @app_commands.describe(
        clubs_to_delete="Club to be deleted"
    )
    @app_commands.autocomplete(clubs_to_delete=club_autocomplete)
    async def delete_club(
            self,
            ctx: commands.Context, *,
            clubs_to_delete: str
    ):
        """Delete clubs, seperate with a space if deleting many"""
        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        notIn = ""
        wasIn = ""
        for c in clubs_to_delete.split(' '):
            if c in clubs_data:
                del clubs_data[c]
                wasIn += f"{c}\n"
            else:
                notIn += f"{c} "

        view = ConfirmCancelView(timeout=None)
        warning_message = await self.message_sending(
            content_message=f"**Are you sure? This action cannot be reversed.**\n"
                            f"__Club to be deleted__\n"
                            f"{wasIn}",
            ctx=ctx
        )
        channel = ctx.channel
        message = await channel.send(view=view)
        await view.wait()
        if view.value is True:
            await message.delete()
            if warning_message is not None:
                await warning_message.edit(content=f"The following club was deleted by {ctx.author.name}\n"
                                                   f"{wasIn}")
            dataIOa.save_json(path, clubs_data)
            self.initialize_clubs()
        else:
            await message.delete()
            if warning_message is not None:
                await warning_message.edit(content=f"Cancelled deletion of the following:\n{wasIn}")

    # @commands.check(checks.admin_check)
    @commands.command(aliases=["gg"])
    async def get_groups(self, ctx: commands.Context, max_gaps: int, *, clubs_and_rest_text):
        """Get groups so there is no gaps use | to ignore people (more than 100 (-100) for just clubs)"""
        just_club = False
        if max_gaps > 99:
            just_club = True
            max_gaps -= 100
        ignore_mems = []
        if ' | ' in clubs_and_rest_text:
            spl = clubs_and_rest_text.split(' | ')
            c1 = spl[0]
            c2 = spl[1]
            for cc in c2.split(' '):
                im = await commands.MemberConverter().convert(ctx, cc)
                if im:
                    ignore_mems.append(im.id)
        else:
            c1 = clubs_and_rest_text
            c2 = ""

        clubs = c1.rsplit(';', 1)[:1][0].split(' ')
        clubs = [c.lower() for c in clubs]
        clubs = list(set(clubs))
        if len(clubs) < 2:
            await self.message_sending(
                content_message="Need at least 2 clubs for this command",
                ctx=ctx,
                delete_after=15
            )
            return
        if len(clubs) > 8:
            await self.message_sending(
                content_message="No more than 8 clubs!",
                ctx=ctx,
                delete_after=15
            )
            return

        all_ok = await self.check_if_clubs_exist(ctx, clubs)

        if all_ok:
            path = 'data/clubs.json'
            dataIOa.create_file_if_doesnt_exist(path, '{}')
            clubs_data = dataIOa.load_json(path)
            mems_all = []
            all_ids = []
            for club_name in clubs:
                club = clubs_data[club_name]
                # mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
                mems = [u for u in club['members'] if ctx.guild.get_member(u)]
                mems_all.append({"clb": club_name, "membs": sorted(mems)})
                all_ids = list({*all_ids, *mems})
            permutations = [t for t in itertools.permutations(mems_all)]
            # permutations = permutations[:len(permutations)//2]

            ok_permutations = []
            for p in permutations:
                if self.check_if_is_ok_for_all(p, all_ids, max_gaps, ignore_mems):
                    ok_permutations.append(p)

            res = []
            for cbs in ok_permutations:
                rs = []
                for c in cbs:
                    m = ""
                    if not just_club:
                        m = ", ".join([
                            f'{"~~" if u in ignore_mems else "**"}{str(ctx.guild.get_member(u))}{"~~" if u in ignore_mems else "**"}'
                            for u in c['membs'] if ctx.guild.get_member(u)])
                    rs.append(f'**__{c["clb"]}__** {m}')
                res.append('\n'.join(rs))

            if not res:
                await self.message_sending(
                    content_message=f"No order for **{max_gaps}** max gaps",
                    ctx=ctx,
                )
                return
            res = res[:len(res) // 2]
            if len(res) > 100:
                await self.message_sending(
                    content_message="There's more than 100 different permutations. Too much!",
                    ctx=ctx,
                )
                return
            await dutils.print_hastebin_or_file(ctx, '\n\n'.join(res), just_file=True)

    @staticmethod
    def check_if_is_ok_for_all(permutation, uids, max_gaps, ignore):
        for u in uids:
            if u in ignore:
                continue
            _fin = []
            fin = []
            for club in permutation:
                _fin.append(u in club['membs'])
            fin.append(_fin[0])
            for f in _fin[1:]:
                if f != fin[-1]:
                    fin.append(f)
            # num_blocks = fin.count(True)
            if fin.count(True) - 1 > max_gaps:
                return False
        return True

    @staticmethod
    def get_emote_if_exists_else(guild, emoteName, elseEmote):
        emote_test = utils.get(guild.emojis, name=emoteName)
        emote = elseEmote if not emote_test else str(emote_test)
        return emote

    @commands.Cog.listener()
    async def on_message(self, message):
        # 833850894101250059
        if self.bot.user.id == 750518704760029190:
            if message.channel.id in [424792581176557579, 424792705529544725, 424792877546340372,
                                      424792986136608770, 424793140223016961] and len(message.attachments) > 0:

                if not self.bot.is_ready():
                    await self.bot.wait_until_ready()
                if not self.gallery_wh:
                    try:
                        self.gallery_wh: Webhook = await self.bot.fetch_webhook(833850894101250059)
                    except:
                        return

                atts = [await a.to_file(spoiler=a.is_spoiler()) for a in message.attachments]
                await self.gallery_wh.send(avatar_url=message.author.avatar.url,
                                           username=f'{message.author.name} in #{message.channel.name}'[:32],
                                           files=atts, wait=False)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.recc(event)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        await self.recc(event)

    async def recc(self, event):
        if event.channel_id == 795720249462882354:
            if event.user_id == self.bot.config["CLIENT_ID"]:
                return  # in case the bot is adding reactions
            g = self.bot.get_guild(int(event.guild_id))
            ch = g.get_channel_or_thread(int(event.channel_id))
            msg = await ch.fetch_message(event.message_id)
            dic = {(ll.split(' ')[0]).replace('<a:', '<:'): (' '.join(ll.split(' ')[1:])).strip() for ll in
                   msg.content.split('\n')}
            d = 0
            add = event.event_type == 'REACTION_ADD'
            e = str(event.emoji).replace('<a:', '<:')
            if e in dic:
                club_name = dic[e]
                club_name = club_name.lower()
                path = 'data/clubs.json'
                dataIOa.create_file_if_doesnt_exist(path, '{}')
                clubs_data = dataIOa.load_json(path)
                club = clubs_data[club_name]
                mems = [(g.get_member(u)).id for u in club['members'] if g.get_member(u)]
                # rch = g.get_channel_or_thread(470822975676088350)
                if event.user_id not in mems and add:
                    clubs_data[club_name]['members'].append(event.user_id)
                    dataIOa.save_json(path, clubs_data)
                    await ch.send(f"<@{event.user_id}> has joined the club **{club_name}** ✅", delete_after=5)
                if event.user_id in mems and not add:
                    clubs_data[club_name]['members'].remove(event.user_id)
                    dataIOa.save_json(path, clubs_data)
                    await ch.send(f"<@{event.user_id}> has left the club **{club_name}** ❌", delete_after=5)

    def findMostSimilar(self, target, str_arr):
        maxx = -99999
        ret = ''
        for s in str_arr:
            sim = self.similar(s, target)
            if sim > maxx:
                ret = s
                maxx = sim
        return ret

    @staticmethod
    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()


async def setup(
        bot: commands.Bot
):
    ext = Ignorethis(bot)
    await bot.add_cog(ext)
