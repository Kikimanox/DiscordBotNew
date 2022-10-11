import asyncio
import itertools

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
from difflib import SequenceMatcher
from utils.SimplePaginator import SimplePaginator


class Ignorethis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verification_channel_id = 931192723447349268
        self.gallery_wh = None

    @commands.check(checks.onk_server_check)
    @commands.command()
    async def listclubsraw(self, ctx, *includes: discord.Member):
        """Display all clubs TITLES
        Optional parameter for checking which clubs members are a part of it, ex:
        `[p]listclubsraw Kiki`
        `[p]listclubsraw @Kiki`
        `[p]listclubsraw 174406433603846145`
        `[p]listclubsraw A B`
        `[p]listclubsraw Kiki Neil Snky`
        `[p]listclubsraw 174406433603846145 Neil @Rollin_Styles`
        For multiple members the command works with **and**
        meaning that in the first example it will
        find clubs where A and B are both in."""

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        embeds = []
        if not includes:
            embeds = self.createEmbedsFromAllClubs2(clubs_data, 'All clubs')
        else:
            includes = list(includes)
            d_clubs = {}
            for k, v in clubs_data.items():
                mems = [ctx.guild.get_member(u) for u in v['members'] if ctx.guild.get_member(u)]
                intersection = list(set(includes) & set(mems))
                if len(intersection) == len(includes):
                    d_clubs[k] = v
            if not d_clubs:
                return await ctx.send("No clubs found for this querry.")
            embeds = self.createEmbedsFromAllClubs2(d_clubs, f'Clubs with: '
                                                             f'{" and ".join([m.name for m in includes])}')

        await SimplePaginator(extras=embeds).paginate(ctx)

    @commands.check(checks.onk_server_check)
    @commands.command()
    async def createclub(self, ctx, club_name, *, description):
        """Create a new club
        Usage:
        `[p]createclub yuri A club for the greatest form of love`
        `[p]createclub pokemon Only true nerds allowed`
        `[p]createclub pits Thanks Appu.`
        After you have created a club it will be active once
        a server staff member will verify the club.
        """
        return await ctx.send("Currently disabled here. Just use -createclubs. ALSO NO DESC, just club names!")
        club_name = club_name.lower()
        if '*' in club_name or '*' in description:
            return await ctx.send("The club name can not include the character `*`, please try again.")

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)

        if club_name in clubs_data:
            return await ctx.send('💢 A club with this name already exists')

        ver_ch = ctx.guild.get_channel(self.verification_channel_id)
        if not ver_ch:
            return await ctx.send("Can't find verification channel (check the id for that)")
        await ctx.send("The club has been created, waiting for server staff aproval, you will be notified in dms"
                       " once the club has been verified or denied.")
        em = Embed(title='A new club has been created', color=self.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                   description=f'**Club Name:** {club_name}\n'
                               f'**Creator:** {ctx.author.mention} ({ctx.author.name}) id: {ctx.author.id}\n'
                               f'**Description:** {description}')
        em.set_footer(text='Press the appropriate emote to verify or deny it')
        m = await ver_ch.send(embed=em)
        await m.add_reaction('✅')
        await m.add_reaction('❌')

    @commands.check(checks.onk_server_check_admin)
    @commands.command()
    async def createclubs(self, ctx, *, clubs):
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

    @commands.check(checks.onk_server_check)
    @commands.command()
    async def clubinfo(self, ctx, club_name):
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

    @commands.check(checks.onk_server_check)
    @commands.command()
    async def listclubs(self, ctx, *includes: discord.Member):
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

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        embeds = []
        if not includes:
            embeds = self.createEmbedsFromAllClubs(clubs_data, 'All clubs')
        else:
            includes = list(includes)
            d_clubs = {}
            for k, v in clubs_data.items():
                mems = [ctx.guild.get_member(u) for u in v['members'] if ctx.guild.get_member(u)]
                intersection = list(set(includes) & set(mems))
                if len(intersection) == len(includes):
                    d_clubs[k] = v
            if not d_clubs:
                return await ctx.send("No clubs found for this querry.")
            embeds = self.createEmbedsFromAllClubs(d_clubs, f'Clubs with: '
                                                            f'{" and ".join([m.name for m in includes])}')

        await SimplePaginator(extras=embeds).paginate(ctx)

    def createEmbedsFromAllClubs(self, clubs, base_title):
        embeds = []
        allClubs = [f"**{k}**\nMembers: {len(c['members'])} | Ping count: {c['pings']}\n"
                    f"{c['desc']}\n\n" for k, c in clubs.items()]

        one_page = ''
        cnt = 0
        for c in allClubs:
            if len(one_page + c) > 1500 or cnt > 7:
                embeds.append(Embed(title=f'{base_title}, page {len(embeds) + 1}/[MAX]', description=one_page,
                                    color=self.bot.config['BOT_DEFAULT_EMBED_COLOR']))
                one_page = ''
                cnt = 0
            cnt += 1
            one_page += c

        embeds.append(Embed(title=f'{base_title}, page {len(embeds) + 1}/[MAX]', description=one_page,
                            color=self.bot.config['BOT_DEFAULT_EMBED_COLOR']))
        for e in embeds:
            e.title = str(e.title).replace("[MAX]", str(len(embeds)))
        return embeds

    def createEmbedsFromAllClubs2(self, clubs, base_title):
        embeds = []
        allClubs = [f"- **{k}** ({c['desc'][:50] if len(c['desc']) <= 50 else (c['desc'][:50] + '...')})\n"
                    for k, c in clubs.items()]

        one_page = ''
        cnt = 0
        for c in allClubs:
            if len(one_page + c) > 1900:
                embeds.append(Embed(title=f'{base_title}, page {len(embeds) + 1}/[MAX]', description=one_page,
                                    color=self.bot.config['BOT_DEFAULT_EMBED_COLOR']))
                one_page = ''
                cnt = 0
            cnt += 1
            one_page += c

        embeds.append(Embed(title=f'{base_title}, page {len(embeds) + 1}/[MAX]', description=one_page,
                            color=self.bot.config['BOT_DEFAULT_EMBED_COLOR']))
        for e in embeds:
            e.title = str(e.title).replace("[MAX]", str(len(embeds)))
        return embeds

    @commands.check(checks.onk_server_check)
    @commands.command(aliases=["ping"])
    async def pingclub(self, ctx, club_name, *, rest="Anything else that you'd like to add"):
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
                if p: await ctx.send(f'Club: {club_name} {p}')

        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await ctx.send(f'{emote} No such club found, did you perhaps mean `{suggestion}`')

    @commands.check(checks.onk_server_check)
    @commands.command(aliases=["ping2"])
    async def pingclubs(self, ctx, *, clubs_and_rest_text):
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
        clubs = clubs_and_rest_text.rsplit(';', 1)[:1][0].split(' ')
        clubs = [c.lower() for c in clubs]
        clubs = list(set(clubs))
        if len(clubs) < 2:
            return await ctx.send("Need at least 2 clubs for this command")

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
                mems_all = list(set([*mems_all, *mems]))
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
                if p: await ctx.send(f'Clubs: {clubs_all[:-2]} {p}')

    async def check_if_clubs_exist(self, ctx, clubs):
        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        for c in clubs:
            if c not in clubs_data:
                suggestion = self.findMostSimilar(c, [*clubs_data])
                emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
                emote = "💢" if not emote_test else str(emote_test)
                await ctx.send(f'{emote} A club in your list is invalid, did you perhaps mean `{suggestion}`'
                               f' for that one? (invalid club: '
                               f'`{dutils.cleanUpBannedWords(["@everyone", "@here"], c)}`)')
                return False
            club = clubs_data[c]
            mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
            if ctx.author not in mems and not ctx.author.guild_permissions.administrator:
                await ctx.send(f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                               f"You can't ping a club you're not a part of (`{c}`)")
                return False
        return True

    @commands.check(checks.onk_server_check)
    @commands.command(aliases=["join"])
    async def joinclub(self, ctx, club_name):
        """Join a club"""
        club_name = club_name.lower()

        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        if club_name in clubs_data:
            club = clubs_data[club_name]
            mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
            if ctx.author in mems:
                return await ctx.send(f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                                      f"You are already in this club")
            clubs_data[club_name]['members'].append(ctx.author.id)
            dataIOa.save_json(path, clubs_data)
            await ctx.send(f"{ctx.author.mention} has joined the club {club_name}")
        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await ctx.send(f'{emote} No such club found, did you perhaps mean `{suggestion}`')

    @commands.check(checks.onk_server_check)
    @commands.command(aliases=["leave"])
    async def leaveclub(self, ctx, club_name):
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
                await ctx.send(f"{ctx.author.mention} has left the club {club_name}")
            else:
                return await ctx.send(f"{self.get_emote_if_exists_else(ctx.guild, 'HestiaNo', '💢')} "
                                      f"You are not even in this club")
        else:
            suggestion = self.findMostSimilar(club_name, [*clubs_data])
            emote_test = utils.get(ctx.guild.emojis, name="HestiaNo")
            emote = "💢" if not emote_test else str(emote_test)
            await ctx.send(f'{emote} No such club found, did you perhaps mean `{suggestion}`')

    @commands.check(checks.onk_server_check_admin)
    @commands.command()
    async def deleteclubs(self, ctx, *, clubs_to_delete):
        """Delete clubs, seperate with a space if deleting many"""
        path = 'data/clubs.json'
        dataIOa.create_file_if_doesnt_exist(path, '{}')
        clubs_data = dataIOa.load_json(path)
        notIn = ""
        wasIn = ""
        for c in clubs_to_delete.split(' '):
            if c in clubs_data:
                del clubs_data[c]
                wasIn += f"{c} "
            else:
                notIn += f"{c} "

        # clbs = '\n'.join([f'`{c.lower()}`' for c in clubs_to_delete])
        confirm = await dutils.prompt(ctx, "https://tenor.com/view/are-you-sure"
                                           "-john-cena-ru-sure-about-dat-gif-14258954")
        if confirm:
            await ctx.send(f"Deleted: {wasIn}\nFailed to delete: {notIn}")
            dataIOa.save_json(path, clubs_data)
        else:
            await ctx.send("Cancelling.")

    @commands.check(checks.admin_check)
    @commands.command(aliases=["gg"])
    async def get_groups(self, ctx, max_gaps: int, *, clubs_and_rest_text):
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
            return await ctx.send("Need at least 2 clubs for this command")
        if len(clubs) > 8:
            return await ctx.send("No more than 8 clubs!")

        all_ok = await self.check_if_clubs_exist(ctx, clubs)

        if all_ok:
            path = 'data/clubs.json'
            dataIOa.create_file_if_doesnt_exist(path, '{}')
            clubs_data = dataIOa.load_json(path)
            mems_all = []
            all_ids = []
            for club_name in clubs:
                club = clubs_data[club_name]
                #mems = [ctx.guild.get_member(u) for u in club['members'] if ctx.guild.get_member(u)]
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
                        m = ", ".join([f'{"~~" if u in ignore_mems else "**"}{str(ctx.guild.get_member(u))}{"~~" if u in ignore_mems else "**"}' for u in c['membs'] if ctx.guild.get_member(u)])
                    rs.append(f'**__{c["clb"]}__** {m}')
                res.append('\n'.join(rs))

            if not res:
                return await ctx.send(f"No order for **{max_gaps}** max gaps")
            res = res[:len(res) // 2]
            if len(res) > 100:
                return await ctx.send("There's more than 100 different permutations. Too much!")
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
                        self.gallery_wh: discord.Webhook = await self.bot.fetch_webhook(833850894101250059)
                    except:
                        return

                atts = [await a.to_file(spoiler=a.is_spoiler()) for a in message.attachments]
                await self.gallery_wh.send(avatar_url=message.author.avatar.url,
                                           username=f'{message.author.name} in #{message.channel.name}'[:32], files=atts, wait=False)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.recc(event)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        await self.recc(event)

    async def recc(self, event):
        # event.guild_id event.user_id event.message_id event.channel_id
        if event.channel_id == self.verification_channel_id:
            g = self.bot.get_guild(int(event.guild_id))
            ch = g.get_channel(int(event.channel_id))
            msg = await ch.fetch_message(event.message_id)
            if event.user_id == self.bot.config["CLIENT_ID"]:
                return  # in case the bot is adding reactions
            if msg.author.id == self.bot.config["CLIENT_ID"] and str(event.emoji) in ['✅', '❌']:
                await msg.clear_reactions()
                try:
                    split = msg.embeds[0].description.split('\n')
                    club_title = split[0].split(' ')[-1]
                    club_creator = g.get_member(int(split[1].split(' ')[-1]))
                    club_desc = ' '.join(split[2].split(' ')[1:])
                    if str(event.emoji) == '✅':
                        path = 'data/clubs.json'
                        dataIOa.create_file_if_doesnt_exist(path, '{}')
                        clubs_data = dataIOa.load_json(path)
                        clubs_data[club_title] = {'creator': club_creator.id, 'desc': club_desc,
                                                  'members': [club_creator.id], 'pings': 0}
                        dataIOa.save_json(path, clubs_data)

                        await club_creator.send(f'The club **{club_title}** has been approved ✅')
                        await ch.send(f'The club **{club_title}** has been '
                                      f'approved by {g.get_member(event.user_id)} ✅')
                    if str(event.emoji) == '❌':
                        await club_creator.send(f'The club **{club_title}** has been denied ❌')
                        await ch.send(f'The club **{club_title}** has been '
                                      f'denied by {g.get_member(event.user_id)} ❌')
                except:
                    pass
                await msg.add_reaction('🔖')
        if event.channel_id == 795720249462882354:
            if event.user_id == self.bot.config["CLIENT_ID"]:
                return  # in case the bot is adding reactions
            g = self.bot.get_guild(int(event.guild_id))
            ch = g.get_channel(int(event.channel_id))
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
                # rch = g.get_channel(470822975676088350)
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


def setup(bot):
    ext = Ignorethis(bot)
    bot.add_cog(ext)
