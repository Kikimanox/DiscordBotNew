import asyncio
import re
import sys
import time

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback

from models.antiraid import ArGuild
from models.serversetup import SSManager
from utils.SimplePaginator import SimplePaginator
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
import datetime
from columnar import columnar
from operator import itemgetter
from models.moderation import (Reminderstbl, Actions, Blacklist, ModManager)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tried_setup = False
        # removing multi word cmds, cross out unavail inh cmd

    async def set_server_stuff(self):
        if not self.tried_setup:
            self.tried_setup = True
            if not self.bot.from_serversetup:
                self.bot.from_serversetup = await SSManager.get_setup_formatted(self.bot)

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

    @commands.check(checks.moderator_check)
    @commands.command()
    async def case(self, ctx, case_id: int, *, reason):
        """Supply or edit reason for a moderation action"""
        if case_id > sys.maxsize: return await ctx.send("Case id too big, breaking system limits!")
        try:
            was_empty = False
            old_reason = ""
            case = Actions.get(Actions.guild == ctx.guild.id, Actions.case_id_on_g == case_id)
            if not case.reason:
                was_empty = True
            if case.reason:
                confirm = await dutils.prompt(ctx, "This case already has a reason:\n```\n"
                                                   f"{dutils.escape_at(case.reason)}```\n"
                                                   f"**Are you sure you want to replace that reason?**")
                if not confirm:
                    return await ctx.send("Cancelled update.")
                old_reason = case.reason
                case.reason = reason
                case.save()
                await ctx.send("Reason updated.")
            else:
                case.reason = reason
                old_reason = case.reason
                case.save()
                await ctx.send("Reason added.")
            ctx.bot.logger.info(f"{ctx.author} ({ctx.author.id}) changed case {case_id} reason:\n"
                                f"Old reason: {old_reason}\n"
                                f"New reason: {reason}")
            try:
                if not ctx.bot.from_serversetup:
                    ctx.bot.from_serversetup = await SSManager.get_setup_formatted(ctx.bot)
                if ctx.guild.id not in ctx.bot.from_serversetup: return
                chan = ctx.bot.from_serversetup[ctx.guild.id]['modlog']
                log_in_chan = None
                if chan.id != case.logged_in_ch:
                    log_in_chan = ctx.guild.get_channel(case.logged_in_ch)
                else:
                    log_in_chan = chan
                if not log_in_chan:
                    return
                msg = None
                d = case.logged_after - datetime.timedelta(minutes=5)

                stuff = await log_in_chan.history(limit=2000, after=d).filter(
                    lambda m: len(m.embeds) == 1 and m.embeds[0].footer and f'Case id: {case_id}' in str(
                        m.embeds[0].footer.text)).flatten()
                if not stuff:
                    return
                msg = stuff[-1]
                if msg:
                    em = msg.embeds[0]
                    em = em.copy()
                    # cnt = msg.content
                    old_rsn = ""
                    i = -1
                    for f in em.fields:
                        i += 1
                        if f.name == 'Reason':
                            old_rsn = f.value
                            break
                    if em.fields[i].name == 'Reason':
                        em.set_field_at(i, value=reason, name='Reason')
                    old_rsn = dutils.escape_at(old_rsn) if not was_empty else "No reason provided."
                    cnt = f'**Case {case_id} reason updated by {ctx.author} ({ctx.author.id}).**\n' \
                          f'Old reason: ```\n{old_rsn}```' \
                          f'Edited case log:'
                    sup = self.bot.from_serversetup[ctx.guild.id]
                    case.logged_after = datetime.datetime.utcnow()
                    case.logged_in_ch = log_in_chan.id
                    case.save()
                    await dutils.try_send_hook(ctx.guild, self.bot, hook=sup['hook_modlog'],
                                               regular_ch=sup['modlog'], embed=em, content=cnt)
                    # await chan.send(content=cnt, embed=Embed)
            except:
                print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
                traceback.print_exc()
                ctx.bot.logger.error(f"Something went wrong when trying to update case {case_id} message\n")
        except:
            await ctx.send("There is no case with that id.")

    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.check(checks.moderator_check)
    @commands.command(aliases=["listcase", "lsc", 'showcase', 'showcases'])
    async def listcases(self, ctx, case_id: int = 0, limit=10, *, extra: str = ""):
        """List case(s), see help to see command usage
        Use this command to see a case or multiple caes

        Use case examples (newest first = default sorting):

        **See a list of recent caes**
        `[p]lsc` (will simply show the last 10 cases)
        `[p]lsc 0 30`
        `[p]lsc -1 30` <- use `-1` to use reversed sorting

        **See one specific case by id**
        `[p]lsc case_id`

        **See 40 cases before/after a date (exclusive)**
        snyax: (YEAR, MONTH, DAY, HOUR, MINUTE, SECOND)
        `[p]lsc 0 40 warn before=(2020, 10, 8, 23, 50, 0) ban`
        `[p]lsc 0 40 after=(2020, 5, 5) before=(2020, 5, 3)`

        **See only one or more types of case**
        `[p]lsc 0 40 mute` (Will show up to 40 last mutes)
        `[p]lsc 0 10 softban banish dm_me`

        **See cases from certain responsible or offenders**
        `[p]lsc 0 30 mute resp=(MOD_ID)` (can use multiple)
        `[p]lsc 0 15 offen=(ID1, ID2, ID3) compact`

        **Possible types?**
        `*ban*` <- for any ban action; `ban`, `banish`,
        `kick`, `rcb`, `rcm` (right click ban/mute),
        `unban`, `softbanish`, `massban`, `blacklist`, `whitelist`,
        `softban`, `warn`, `mute`, `unmute`, `massmute`,

        **Other extra agruments:** `compact`, `dm_me`, `hcw` (hide clear warns)
        """
        if isinstance(ctx.channel, discord.DMChannel): return await ctx.send("Can not use this cmmand in dms.")
        if limit > sys.maxsize: return await ctx.send("Limit too big, breaking system limits!")
        if case_id > sys.maxsize: return await ctx.send("Case id too big, breaking system limits!")
        types = ['ban', 'banish', 'softban', 'softbanish', 'massban',
                 'blacklist', 'whitelist', 'warn', 'mute', 'unmute', '*ban*', 'massmute', 'rcb', 'unban', 'rcm']
        b_types = ['ban', 'banish', 'softban', 'softbanish', 'massban', 'rcb', 'unban']
        possible = list(set(types) | {'compact', 'dm_me', 'after', 'before', 'resp', 'offen', 'hcw'})
        q = None
        reverse = True if case_id == -1 else False
        af_date = None
        bf_date = None
        resp = []
        offe = []
        got_t = []
        dm_me = bool('dm_me' in extra)
        compact = bool('compact' in extra)

        if case_id == 0 and limit > 0 and not extra:
            q = Actions.select().where(Actions.guild == ctx.guild.id).order_by(-Actions.case_id_on_g).limit(limit)
        elif case_id == -1 and limit > 0 and not extra:
            q = Actions.select().where(Actions.guild == ctx.guild.id).order_by(+Actions.case_id_on_g).limit(limit)
        elif case_id > 0 and limit == 10 and not extra:
            q = Actions.select().where(Actions.guild == ctx.guild.id, Actions.case_id_on_g == case_id)
        elif case_id > -2 and limit > 0 and extra:
            was_eq = False
            near = ""
            for ex in extra.split():
                if ')' in ex and not was_eq and '(' not in ex:
                    return await ctx.send("Invalid syntax. You either forgot a `(` "
                                          "somewhere **or** "
                                          "you have a "
                                          "space before or after `=`")
                if was_eq:
                    if '(' in ex: break
                    if ')' not in ex: continue
                    was_eq = False
                    continue
                near = ex

                if '=' not in ex:
                    if '(' in ex: return await ctx.send("Invalid syntax. You have an `(` but no `=` before it.")
                    # provided.append(ex)
                    if ex not in possible:
                        inv = ex.replace('@', '@\u200b')
                        return await ctx.send(f"Invalid extra argument `{inv}`")
                else:
                    if '(' not in ex: return await ctx.send("Invalid syntax. You either forgot a `(` somewhere **or** "
                                                            "you have a "
                                                            "space before or after `=`")
                    was_eq = True
                    if '(' in ex and ')' in ex: was_eq = False
                    candidate = ex.split('=')[0]
                    if candidate not in possible:
                        inv = candidate.replace('@', '@\u200b')
                        if not inv: inv = ' '
                        near = near.replace('@', '@\u200b')
                        return await ctx.send(f"Invalid extra argument `{inv}` "
                                              f"(or you have "
                                              f"a space before `=`"
                                              f" somewhere)\n{'' if inv is not ' ' else f'See near `{near}`'}")
            near = near.replace('@', '@\u200b')
            if was_eq: return await ctx.send(f"You forgot to close a `)` at `{near}`")
            if 'after=' in extra or 'before=' in extra:
                try:
                    aa = re.search(r'after=(.*?)\)', extra)
                    bb = re.search(r'before=(.*?)\)', extra)
                    af = tuple(map(int, re.findall(r'\d+', '' if not aa else aa.group(1))))[:6]
                    bf = tuple(map(int, re.findall(r'\d+', '' if not bb else bb.group(1))))[:6]
                    parsing_now = "after"
                    try:
                        if af:
                            af_date = datetime.datetime(*af)
                        parsing_now = "before"
                        if bf:
                            bf_date = datetime.datetime(*bf)
                    except Exception as e:
                        trace = traceback.format_exc()
                        ctx.bot.logger.error(trace)
                        ee = str(e).replace('@', '@\u200b')
                        return await ctx.send(f"Something went wrong when parsing **{parsing_now}** date. "
                                              f"Please check your "
                                              f"syntax and semantics. Exception:\n"
                                              f"```\n{ee}```")
                except:
                    trace = traceback.format_exc()
                    print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
                    print(trace)
                    ctx.bot.logger.error(trace)
                    return await ctx.send("Something went wrong. Please re-check usage.")
            try:
                parsing_now = 'resp'
                if 'resp=' in extra:
                    rr = re.search(r'resp=(.*?)\)', extra)
                    rr_ids = list(map(int, re.findall(r'\d+', '' if not rr else rr.group(1))))
                    if rr_ids: resp = rr_ids

                if 'offen=' in extra:
                    rr = re.search(r'offen=(.*?)\)', extra)
                    b = rr.group(1)
                    rr_ids = list(map(int, re.findall(r'\d+', '' if not rr else rr.group(1))))
                    if rr_ids: offe = rr_ids
            except Exception as e:
                ee = str(e).replace('@', '@\u200b')
                return await ctx.send("Something went wrong when parsing **{parsing_now}** arguments. Exception:\n"
                                      f"```\n{ee}```")
            if extra:
                got_t = list(set(types) & set(extra.split()))
                got_t2 = list(set(possible) & set(extra.split()))
                if '*ban*' in got_t:
                    got_t = list(set(got_t) - {*b_types, '*ban*'})
                    got_t = list(set(got_t) | set(b_types))

                if 'hcw' not in got_t2 and got_t:
                    if 'warn' in got_t:
                        got_t.append('warn(cleared)')

                if 'rcb' in got_t:
                    got_t.remove('rcb')
                    got_t.append('Right click ban')

                if 'rcm' in got_t:
                    got_t.remove('rcm')
                    got_t.append('Right click mute')

            if not af_date: af_date = datetime.datetime.min
            if not bf_date: bf_date = datetime.datetime.max

            #  The big q
            q = Actions.select().where(Actions.guild == ctx.guild.id,
                                       af_date < Actions.date < bf_date,
                                       (Actions.responsible << resp) if resp else (Actions.responsible.not_in(resp)),
                                       (Actions.offender << offe) if offe else (Actions.offender.not_in(offe)),
                                       (Actions.type << got_t) if got_t else (Actions.type.not_in(got_t))
                                       ).order_by((+Actions.case_id_on_g) if reverse else (-Actions.case_id_on_g)
                                                  ).limit(limit)

        else:
            return await ctx.send("Invalid provided arguments.")

        if q:
            try:
                cases = [c for c in q.dicts()]

                title = f"Moderation actions"
                txt = []
                le_max = 1200
                for act in cases:
                    responsible = ctx.guild.get_member(int(act['responsible']))
                    if not responsible:
                        responsible = f"{act['responsible']} (left server)"
                    else:
                        f"{responsible.mention} ({responsible.id})"
                    offender = None
                    offtxt = ""
                    if act['offender']:
                        offender = ctx.guild.get_member(int(act['offender']))
                        offtxt = f"*-offender: {act['offender']} (left server)*\n"
                    if offender:
                        offtxt = f"*-offender: {offender.mention} ({offender.id})*\n"

                    p = dutils.bot_pfx(ctx.bot, ctx.message)
                    rr = act['reason']
                    cid = act["case_id_on_g"]
                    reason = f"{f'Not provided. (To add: {p}case {cid} reason here)' if not rr else rr}"
                    typ = act['type'] if act['no_dm'] is False else f"s{act['type']}"
                    cr = ""
                    if typ == 'warn(cleared)': cr = "~~"
                    if not compact:
                        txt.append(f"{cr}[**Case {cid} ({typ})**]({act['jump_url']})\n"
                                   f"*-responsible: {responsible}*\n"
                                   f"*-on: {act['date'].strftime('%c')}*\n"
                                   f"{offtxt}"
                                   f"**-Reason:\n**"
                                   f"```\n{reason}```{cr}\n")
                    else:
                        le_max = 1900
                        rr = act['reason']
                        reason = f"{f'Not provided.' if not rr else f'{rr[:30]}'}"
                        reason = reason.replace('`', '\`')
                        if rr and len(rr) > 30: reason += '...'
                        txt.append(f"{cr}[**Case {cid} ({typ})**]({act['jump_url']}) | "
                                   f"`{reason}`{cr}\n"
                                   f"{cr}**Offender: {act['user_display_name']}, on: "
                                   f"{act['date'].strftime('%Y-%m-%d %H:%M:%S')}\n**{cr}")

                txt = txt[::-1]
                desc = ""
                desc_arr = []
                while len(txt) > 0:
                    desc += txt.pop()
                    if len(txt) == 0: break
                    if len(desc) > le_max or len(desc) + len(txt[-1]) > 2000:
                        desc_arr.append(desc)
                        desc = ""
                if desc: desc_arr.append(desc)

                embeds = []
                for i in range(len(desc_arr)):
                    em = Embed(title=title + f'\nPage {i + 1}/{len(desc_arr)}',
                               description=desc_arr[i], color=0x48daf7)
                    em.set_footer(text='Times are in UTC')
                    embeds.append(em)

                if not dm_me:
                    if len(embeds) == 1:
                        embeds[0].title = "Moderation action"
                        return await ctx.send(embed=embeds[0])
                    else:
                        return await SimplePaginator(extras=embeds).paginate(ctx)

                else:
                    if len(embeds) < 4:
                        for e in embeds: await ctx.author.send(embed=e)
                    else:
                        await SimplePaginator(extras=embeds, other_target=ctx.author).paginate(ctx)
                        await ctx.author.send("Sent as a paginator because there are more than 3 pages")
                    return await ctx.send("Sent to dms")

            except:
                print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
                traceback.print_exc()
                await ctx.send("Something weird went wrong when executing querry.")
                ctx.bot.logger.error('listcases execution ERROR:\n' + traceback.format_exc())
        else:
            return await ctx.send("No cases found with the provided arguments.")

    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def s_(self, ctx):
        """Run me if you don't know what this is. Use; `[p]s_`
        Silent commands
        In case you haven't known, most of the commands in this module
        can be executed in two ways. Normally, or by prefixing with `s`.

        If they are prefixed, they will be executed "silently".
        Which means that the offender will **not recieve a DM of the action**

        Commands that can be ran in silend mode are:
        `ban`, `banish`, `softban`, `softbanish`, `mute`, `kick`, `unmute`

        Example: `[p]sban @user` will ban the user but
        will not dm them that they were banned.
        """
        raise commands.errors.BadArgument

    @commands.Cog.listener()
    async def on_member_ban(self, guild, member):
        if self.bot.banned_cuz_blacklist and f'{member.id}_{member.guild.id}' in self.bot.banned_cuz_blacklist:
            self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}'] -= \
                self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}']
            if self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}'] == 0:
                del self.bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}']
            return

        if self.bot.just_banned_by_bot and f'{member.id}_{member.guild.id}' in self.bot.just_banned_by_bot:
            del self.bot.just_banned_by_bot[f'{member.id}_{member.guild.id}']
            return

        limit = 5
        found_entry = None
        tries = 3
        while tries >= 0:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=limit):
                if entry.target.id != member.id: continue
                now = datetime.datetime.utcnow()
                if (now - entry.created_at).total_seconds() >= 20: continue
                found_entry = entry
                break
            if found_entry:
                act_id = await dutils.moderation_action(None, '', 'Right click ban', member,
                                                        actually_resp=found_entry.user,
                                                        guild=guild, bot=self.bot)
                await dutils.post_mod_log_based_on_type(None, 'Right click ban', act_id, offender=member,
                                                        reason='',
                                                        actually_resp=found_entry.user,
                                                        guild=guild, bot=self.bot)
                return
            else:
                limit += 20
                tries -= 1
                await asyncio.sleep(2)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        limit = 5
        found_entry = None
        tries = 3
        while tries >= 0:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=limit):
                if entry.target.id != user.id: continue
                now = datetime.datetime.utcnow()
                if (now - entry.created_at).total_seconds() >= 20: continue
                found_entry = entry
                break
            if found_entry:
                act_id = await dutils.moderation_action(None, '', 'unban', user, no_dm=True,
                                                        actually_resp=found_entry.user,
                                                        guild=guild, bot=self.bot)
                await dutils.post_mod_log_based_on_type(None, 'unban', act_id, offender=user,
                                                        reason='',
                                                        actually_resp=found_entry.user,
                                                        guild=guild, bot=self.bot)
                return
            else:
                limit += 20
                tries -= 1
                await asyncio.sleep(2)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        can_even_execute = True
        if before.guild.id in self.bot.from_serversetup:
            sup = self.bot.from_serversetup[before.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if can_even_execute:
            mute_role = discord.utils.get(before.guild.roles, id=self.bot.from_serversetup[before.guild.id]['muterole'])
            if mute_role not in after.roles and mute_role in before.roles:
                # unmute logic time
                try:
                    muted = Reminderstbl.get(Reminderstbl.guild == before.guild.id, Reminderstbl.user_id == before.id,
                                             Reminderstbl.meta.startswith('mute'))
                    muted.delete_instance()
                except:
                    pass
                entry_found = False
                en = None
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=3):
                    if entry.target.id != after.id: continue
                    entry_found = True
                    en = entry
                    break
                if not entry_found:
                    await asyncio.sleep(3)  # if discord is laggy with uptating logs I guess
                    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update,
                                                              limit=10):
                        if entry.target.id != after.id: continue
                        entry_found = True
                        en = entry
                        break
                if entry_found:
                    reason = en.reason
                    actually_resp = en.user
                    member = en.target
                    no_dm = True
                    if reason and '|' in reason:
                        no_dm = True if reason.split('|')[-1] == 'True' else False
                        aa = reason.split('|')[:-1]
                        if len(aa) > 1:
                            reason = '|'.join(aa)
                        else:
                            reason = aa[0]
                    act_id = await dutils.moderation_action(None, reason, "unmute", member, no_dm=no_dm,
                                                            actually_resp=actually_resp,
                                                            guild=before.guild, bot=self.bot)
                    await dutils.post_mod_log_based_on_type(None, "unmute", act_id, offender=member,
                                                            reason=reason, actually_resp=actually_resp,
                                                            guild=before.guild, bot=self.bot)
            if mute_role in after.roles and mute_role not in before.roles:
                if self.bot.just_muted_by_bot and f'{before.id}_{before.guild.id}' in self.bot.just_muted_by_bot:
                    del self.bot.just_muted_by_bot[f'{before.id}_{before.guild.id}']
                    return

                limit = 5
                tries = 3
                found_entry = None
                while tries >= 0:
                    async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update,
                                                              limit=limit):
                        if entry.target.id != after.id: continue
                        now = datetime.datetime.utcnow()
                        if (now - entry.created_at).total_seconds() >= 20: continue
                        found_entry = entry
                        break
                    if found_entry:
                        act_id = await dutils.moderation_action(None, '', 'Right click mute', after,
                                                                actually_resp=found_entry.user,
                                                                guild=after.guild, bot=self.bot)
                        await dutils.post_mod_log_based_on_type(None, 'Right click mute', act_id, offender=after,
                                                                reason='',
                                                                actually_resp=found_entry.user,
                                                                guild=after.guild, bot=self.bot)
                        return
                    else:
                        limit += 20
                        tries -= 1
                        await asyncio.sleep(2)

    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def unmute(self, ctx, user: discord.Member, *, reason=""):
        """Unmutes a user if they are muted.

        `[p]unmute @user`
        `[p]unmute USER_ID`"""
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if not can_even_execute: return await ctx.send(f"Mute role not setup. "
                                                       f"Use `{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolenew "
                                                       f"<role>`")

        await dutils.unmute_user(ctx, user, reason)

    @commands.check(checks.manage_messages_check)
    @commands.command(hidden=True)
    async def sunmute(self, ctx, user: discord.Member, *, reason=""):
        """Unmutes a user if they are muted. (no dm)

        `[p]sunmute @user`
        `[p]sunmute USER_ID`"""
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if not can_even_execute: return await ctx.send(f"Mute role not setup. "
                                                       f"Use `{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolenew "
                                                       f"<role>`")

        await dutils.unmute_user(ctx, user, reason, no_dm=True)

    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def mute(self, ctx, users: commands.Greedy[discord.Member], length="", *, reason=""):
        """Mutes users. Please check usage with .help mute

        Supply a #d#h#m#s for a timed mute. Examples:
        `[p]mute @user` - will mute the user indefinitely
        `[p]mute USER_ID` - can also use id instead of mention
        `[p]mute @user 2h30m Optional reason goes here`
        `[p]mute @user @user2 @user3 10d Muted for ten days for that and this`

        Only this command (and smute) can mute multiple users at once (max 10)"""
        users = list(set(users))
        if len(users) == 0: raise commands.errors.BadArgument
        if len(users) > 10: return await ctx.send("Max 10 users")
        if len(users) > 1:
            if not await dutils.prompt(ctx, "Are you sure you want to mass mute like this? (It will send a dm "
                                            "to each muted user).\nI **suugest** using the `smute` command instedad."):
                return
        await self.el_mute(ctx, users, length, reason, False)

    @commands.check(checks.manage_messages_check)
    @commands.command(hidden=True)
    async def smute(self, ctx, users: commands.Greedy[discord.Member], length="", *, reason=""):
        """Mutes a user. Check usage with .help smute (no dm)

        Same as mute, but won't dm the muted user

        Supply a #d#h#m#s for a timed mute. Examples:
        `[p]smute @user` - will mute the user indefinitely
        `[p]smute USER_ID` - can also use id instead of mention
        `[p]smute @user 2h30m Optional reason goes here`
        `[p]smute @user 10d Muted for ten days for that and this`

        Only this command (and mute) can mute multiple users at once (max 10)"""
        users = list(set(users))
        if len(users) > 10: return await ctx.send("Max 10 users")
        await self.el_mute(ctx, users, length, reason, True)

    async def el_mute(self, ctx, users, length, reason, no_dm):
        if not self.bot.from_serversetup:
            if not self.tried_setup:
                await self.set_server_stuff()
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if not can_even_execute: return await ctx.send(f"Mute role not setup. "
                                                       f"Use `{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolenew "
                                                       f"<role>`")
        rets = []
        if len(users) == 1:
            await dutils.mute_user(ctx, users[0], length, reason, no_dm=no_dm)
        else:
            p = dutils.bot_pfx(ctx.bot, ctx.message)
            for u in users:
                ret = await dutils.mute_user(ctx, u, length, reason, no_dm=no_dm, batch=True)
                if ret == -1000: return ctx.send("Mute role not setup, can not complete mute.")
                if ret == -35: return await ctx.send(f"Could not parse mute length. Are you sure you're "
                                                     f"giving it in the right format? Ex: `{p}mute @user 30m`, "
                                                     f"or `{p}mute @user 1d4h3m2s reason here`, etc.")
                if ret == 9001: return await ctx.send("**Overflow!** Mute time too long. "
                                                      "Please input a shorter mute time.")
                if ret == -989: return await ctx.send('Can not load remidners cog! (Weird error)')
                # if ret == -10 (user already muted)
                # if ret == -19 (no perms)
                # if ret == 10 (OK)
                rets.append(str(ret))
            desc = ""
            for i in range(len(rets)):
                rets[i] = rets[i].replace('-10', '(user already muted) ⚠')
                rets[i] = rets[i].replace('-19', '(no perms) 💢')
                rets[i] = rets[i].replace('10', '(muted) \N{WHITE HEAVY CHECK MARK}')
                rets[i] = rets[i] = f"{users[i]} - {rets[i]}"
            await ctx.send(embed=Embed(color=0x5e77bd, title="Mass mute",
                                       description='\n'.join(rets)))
            rsn = reason + '\n**Offenders:** ' + ', '.join([f'{u} ({str(u.id)})' for u in users])
            act_id = await dutils.moderation_action(ctx, rsn, "massmute", None)
            await dutils.post_mod_log_based_on_type(ctx, 'massmute', act_id, reason=rsn,
                                                    mute_time_str='indefinitely' if not length else length)

    @commands.check(checks.manage_messages_check)
    @commands.command(name='nmute')
    async def newmute(self, ctx, user: discord.Member, length="", *, reason=""):
        """Same as mute, but will also work on already muted users
        (nmute = newmute)
        When muting an already muted user their old timeout will be
        replaced with the new provided timeout (length)

        Supply a #d#h#m#s for a timed mute. Examples:
        `[p]nmute @user` - will mute the user indefinitely
        `[p]nmute USER_ID` - can also use id instead of mention
        `[p]nmute @user 2h30m Optional reason goes here`
        `[p]nmute @user 10d Muted for ten days for that and this`"""
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if not can_even_execute: return await ctx.send(f"Mute role not setup. "
                                                       f"Use `{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolenew "
                                                       f"<role>`")

        await dutils.mute_user(ctx, user, length, reason, new_mute=True)

    @commands.check(checks.manage_messages_check)
    @commands.command(name='snmute', hidden=True)
    async def snewmute(self, ctx, user: discord.Member, length="", *, reason=""):
        """Same as mute, but will also work on already muted users (nodm)

        When muting an already muted user their old timeout will be
        replaced with the new provided timeout (length)

        Supply a #d#h#m#s for a timed mute. Examples:
        `[p]snmute @user` - will mute the user indefinitely
        `[p]snmute USER_ID` - can also use id instead of mention
        `[p]snmute @user 2h30m Optional reason goes here`
        `[p]snmute @user 10d Muted for ten days for that and this`"""
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        if not can_even_execute: return await ctx.send(f"Mute role not setup. "
                                                       f"Use `{dutils.bot_pfx(ctx.bot, ctx.message)}setup muterolenew "
                                                       f"<role>`")

        await dutils.mute_user(ctx, user, length, reason, new_mute=True, no_dm=True)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def ban(self, ctx, user: discord.Member, *, reason=""):
        """Ban a user with an optional reason. Prefix with `s` for "no dm"

        Tip:

        **Every ban/banish/softban/softbanish/mute/kick
        command (except massban)
        has another copy of it but with a `s` prefix**
        For example: `[p]sban @user` will ban them but
        will not dm them that they were banned.

        Ban = Delete no messages
        Banish = Delete 7 days of messages
        Softban = Ban but unban right away

        `[p]ban @user`
        `[p]ban USER_ID`
        `[p]ban USER_ID optional reason goes here here`"""
        await dutils.ban_function(ctx, user, reason)

    @commands.check(checks.kick_members_check)
    @commands.command()
    async def kick(self, ctx, user: discord.Member, *, reason=""):
        """Kick a user from the server

        `[p]sban @user`
        `[p]sban USER_ID`
        `[p]sban USER_ID optional reason goes here here`"""
        try:
            await user.kick(reason=reason)
            return_msg = f"Kicked the user {user.mention} (id: {user.id})"
            if reason:
                return_msg += f" for reason: `{reason}`"
            await ctx.send(embed=Embed(description=return_msg, color=0xed7e00))
            try:
                await user.send(f'You have been kicked from the {str(ctx.guild)} '
                                f'server {"" if not reason else f", reason: {reason}"}')
            except:
                print(f"Member {'' if not user else user.id} disabled dms")
            act_id = await dutils.moderation_action(ctx, reason, 'kick', user, no_dm=False)
            await dutils.post_mod_log_based_on_type(ctx, 'kick', act_id, offender=user, reason=reason)

        except discord.Forbidden:
            await ctx.send('Could not kick user. Not enough permissions.')

    @commands.check(checks.kick_members_check)
    @commands.command(hidden=True)
    async def skick(self, ctx, user: discord.Member, *, reason=""):
        """Kick a user from the server (no dm)

        `[p]sban @user`
        `[p]sban USER_ID`
        `[p]sban USER_ID optional reason goes here here`"""
        try:
            await user.kick(reason=reason)
            return_msg = f"Kicked the user {user.mention} (id: {user.id})"
            if reason:
                return_msg += f" for reason: `{reason}`"
            await ctx.send(embed=Embed(description=return_msg, color=0xed7e00))
            act_id = await dutils.moderation_action(ctx, reason, 'kick', user, no_dm=True)
            await dutils.post_mod_log_based_on_type(ctx, 'kick', act_id, offender=user, reason=reason)

        except discord.Forbidden:
            await ctx.send('Could not kick user. Not enough permissions.')

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def sban(self, ctx, user: discord.Member, *, reason=""):
        """Ban a user with an optionally supplied reason. **(won't dm them)**

        `[p]sban @user`
        `[p]sban USER_ID`
        `[p]sban USER_ID optional reason goes here here`"""
        await dutils.ban_function(ctx, user, reason, no_dm=True)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def banish(self, ctx, user: discord.Member, *, reason=""):
        """Same as ban but also deletes message history (7 days)

        `[p]banish @user`
        `[p]banish USER_ID`
        `[p]banish USER_ID optional reason goes here here`"""
        await dutils.ban_function(ctx, user, reason, removeMsgs=7)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def sbanish(self, ctx, user: discord.Member, *, reason=""):
        """Same as ban but also deletes message history (7 days) **(no dm)**

        `[p]sbanish @user`
        `[p]sbanish USER_ID`
        `[p]sbanish USER_ID optional reason goes here here`"""
        await dutils.ban_function(ctx, user, reason, removeMsgs=7, no_dm=True)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def softban(self, ctx, clear_messages_days: int, user: discord.Member, *, reason=""):
        """Ban then unban (see help for details)

        This command allows you to specifiy the amount of days worth
        of messages to clear when banning the user. (Min=0, Max=7)

        (command similarities)
        `kick` = `softban 0` (kind of)
        `softbanish` = `softban 7`

        `[p]softban @user`
        `[p]softban USER_ID`
        `[p]softban USER_ID optional reason goes here here`"""
        if clear_messages_days < 0: return await ctx.send("**Min=0**, Max=7 for `clear_messages_days`")
        if clear_messages_days > 7: return await ctx.send("Min=0, **Max=7** for `clear_messages_days`")
        await dutils.ban_function(ctx, user, reason, softban=True, removeMsgs=clear_messages_days)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def ssoftban(self, ctx, clear_messages_days: int, user: discord.Member, *, reason=""):
        """Ban then unban right away (won't dm them)

         This command allows you to specifiy the amount of days worth
        of messages to clear when banning the user. (Min=0, Max=7)

        (command similarities)
        `skick` = `ssoftban 0` (kind of)
        `ssoftbanish` = `ssoftban 7`

        `[p]ssoftban @user`
        `[p]ssoftban USER_ID`
        `[p]ssoftban USER_ID optional reason goes here here`"""
        if clear_messages_days < 0: return await ctx.send("**Min=0**, Max=7 for `clear_messages_days`")
        if clear_messages_days > 7: return await ctx.send("Min=0, **Max=7** for `clear_messages_days`")
        await dutils.ban_function(ctx, user, reason, softban=True, no_dm=True, removeMsgs=clear_messages_days)

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def softbanish(self, ctx, user: discord.Member, *, reason=""):
        """Ban, but unban right away also deletes message history (7 days)

        `[p]softbanish @user`
        `[p]softbanish USER_ID`
        `[p]softbanish USER_ID optional reason goes here here`"""
        await dutils.ban_function(ctx, user, reason, removeMsgs=7, softban=True)

    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def ssoftbanish(self, ctx, user: discord.Member, *, reason=""):
        """Ban, but unban right away also dels msg history (7d) **(no dm)**

        `[p]ssoftbanish @user`
        `[p]ssoftbanish USER_ID`
        `[p]ssoftbanish USER_ID optional reason goes here here`"""
        await dutils.ban_function(ctx, user, reason, removeMsgs=7, softban=True, no_dm=True)

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
            rets.append(await dutils.ban_function(ctx, user, removeMsgs=delete_messages_days,
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
        await ctx.send(embed=Embed(description=ret_msg))
        act_id = await dutils.moderation_action(ctx, ', '.join([u.id for u in users]), "massban", None)
        await dutils.post_mod_log_based_on_type(ctx, 'massban', act_id)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
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

    @commands.check(checks.ban_members_check)
    @commands.command()
    async def blacklist(self, ctx, *user_ids: int):
        """Blacklist a user or users by id

        Use `blacklistshow` to see current blacklist
        Use `whitelist` to remove ids from it"""
        user_ids = list(set(user_ids))  # remove dupes
        if len(user_ids) > 90: return await ctx.send("Can only blacklist up to 90 at once")
        data = [{'guild': ctx.guild.id, 'user_id': uid} for uid in user_ids]
        de = Blacklist.delete().where(Blacklist.guild == ctx.guild.id, Blacklist.user_id << user_ids).execute()
        if de > 0:
            await ctx.send("Why did you try to insert ids that were already blacklisted? You can see "
                           f"already blacklisted ids by using `{dutils.bot_pfx(ctx.bot, ctx.message)}blacklistshow`")
        Blacklist.insert_many(data).execute()
        self.bot.moderation_blacklist = ModManager.return_blacklist_lists()
        await ctx.send("Done.")
        bs = ', '.join([str(u) for u in user_ids])
        act_id = await dutils.moderation_action(ctx, bs, "blacklist", None)
        await dutils.post_mod_log_based_on_type(ctx, 'blacklist', act_id, reason=bs)

    @commands.cooldown(1, 20, commands.BucketType.user)
    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def blacklistshow(self, ctx):
        # bs = [b for b in Blacklist.select().dicts()]
        # if not bs: return await ctx.send("Blacklist is empty.")
        # ret = ' '.join([b[''] for b in bs])
        if -1 in self.bot.moderation_blacklist:
            self.bot.moderation_blacklist = ModManager.return_blacklist_lists()
        if ctx.guild.id in self.bot.moderation_blacklist:
            smb = self.bot.moderation_blacklist[ctx.guild.id]
            if smb:
                ret = f"```\n{' '.join([str(b) for b in smb])}```"
                return await dutils.print_hastebin_or_file(ctx, ret)

        await ctx.send("Blacklist is empty.")

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.check(checks.ban_members_check)
    @commands.command(hidden=True)
    async def whitelist(self, ctx, *user_ids: int):
        """Delete ids from the blacklist"""
        user_ids = list(set(user_ids))  # remove dupes
        de = Blacklist.delete().where(Blacklist.guild == ctx.guild.id, Blacklist.user_id << user_ids).execute()
        await ctx.send(f"Removed **{de}** ids from the blacklist.")
        if de > 0:
            act_id = await dutils.moderation_action(ctx, "", "whitelist", ctx.message.content)
            await dutils.post_mod_log_based_on_type(ctx, 'whitelist', act_id,
                                                    reason=f'{ctx.message.content}|'
                                                           f'Removed **{de}** ids from the blacklist.')

    @commands.check(checks.manage_messages_check)
    @commands.command(aliases=['clearwarn'])
    async def clearwarns(self, ctx, user, *, reason=""):
        """Clear warnings of a user (optional reason)"""
        if ctx.message.mentions:
            member = ctx.message.mentions[0]
        elif user and user.isdigit():
            member = ctx.guild.get_member(int(user))
        else:
            member = None
        if not member:
            member = discord.utils.get(ctx.guild.members, name=user)
        if not member and not user.isdigit():
            return await ctx.send("Could not find this user.\n"
                                  "If the user left the server then "
                                  "the argument has to be an integer "
                                  "(user id basically) "
                                  "to clear the left user's warns")
        if member:
            m_id = member.id
        else:
            m_id = user
            await ctx.send("User by provided id is not on the server anymore.")

        w_len = Actions.select().where(Actions.type == 'warn',
                                       Actions.guild == ctx.guild.id,
                                       Actions.offender == m_id).count()
        if w_len == 0:
            return await ctx.send("User has no warnings to clear.")

        Actions.update(type='warn(cleared)').where(Actions.type == 'warn',
                                                   Actions.guild == ctx.guild.id,
                                                   Actions.offender == m_id).execute()

        await ctx.send(f"Cleared **{w_len}** warnings.")
        if member:
            off = member
        else:
            off = m_id
        act_id = await dutils.moderation_action(ctx, reason, 'clearwarn', off)
        await dutils.post_mod_log_based_on_type(ctx, 'clearwarn', act_id, offender=off, reason=reason)

    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def warn(self, ctx, user: discord.Member, *, reason):
        """Warn a user with a necessary supplied reason.

         `[p]warn @user Reason goes here` (reason has to be supplied)
         `[p]warn user_id Reason goes here`"""
        if reason == '': return await ctx.send('Warn failed, please supply '
                                               'a reason for the warn (`.warn @user '
                                               'reason goes here`)')
        act_id = await dutils.moderation_action(ctx, reason, 'warn', user)
        num_warns = Actions.select().where(Actions.type == 'warn',
                                           Actions.guild == ctx.guild.id,
                                           Actions.offender == user.id).count()
        await dutils.post_mod_log_based_on_type(ctx, 'warn', act_id, offender=user,
                                                reason=reason, warn_number=num_warns)
        await ctx.send(content=f'**{user.mention} has been warned, reason:**',
                       embed=Embed(description=reason).set_footer(
                           text=f'Number of warnings: {num_warns}'))
        try:
            await user.send(f'You have been warned on the {str(ctx.guild)} '
                            f'server, reason: {reason}')
        except:
            print(f"Member {'' if not user else user.id} disabled dms")

    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def warnlist(self, ctx, user=None):
        """Show warnings for a user or display all warnings.

        `[p]warnlist @user`
        `[p]warnlist USER_ID`
        `[p]warnlist` **<-- This displays all warnings**"""
        view_all = False
        if not user:
            view_all = True
            if not (await dutils.prompt(ctx, "You are about to view a list of all warnings, proceeed?")):
                return await ctx.send("Cancelled viewing all warnings.")

        if not view_all:
            if ctx.message.mentions:
                member = ctx.message.mentions[0]
            elif user and user.isdigit():
                member = ctx.guild.get_member(int(user))
            else:
                member = None
            if not member:
                member = discord.utils.get(ctx.guild.members, name=user)
            if not member and not user.isdigit():
                return await ctx.send("Could not find this user.\n"
                                      "If the user left the server then "
                                      "the argument has to be an integer "
                                      "(user id basically) "
                                      "to view the left user's warns")
            if member:
                m_id = member.id
            else:
                m_id = user
                await ctx.send("User by provided id is not on the server anymore.")

            ws = [q for q in Actions.select().where(Actions.type == 'warn',
                                                    Actions.offender == m_id,
                                                    Actions.guild == ctx.guild.id).dicts()]
            if not ws:
                return await ctx.send("This user has no warnings.")
            ws = self.ws_to_usr_dict(ws)
            warn_arr = ws[m_id]
            title = f"Warnings for {f'{m_id} __(user not on the server)__' if not member else f'{member} ({m_id})'}"
            txt = []
            for w in warn_arr:
                responsible = ctx.guild.get_member(int(w['responsible']))
                if not responsible: responsible = f"*{w['responsible']} (left server)*"
                txt.append(f"\n\n**->** `{w['reason']}`\n"
                           f"*-by: {responsible}*\n"
                           f"*-on: {w['date'].strftime('%c')}*")
            txt = txt[::-1]
            desc = ""
            desc_arr = []
            while len(txt) > 0:
                desc += txt.pop()
                if len(desc) > 400:
                    desc_arr.append(desc)
                    desc = ""
            if desc: desc_arr.append(desc)

            embeds = []
            for i in range(len(desc_arr)):
                em = Embed(title=title + f'\nPage {i + 1}/{len(desc_arr)}',
                           description=desc_arr[i], color=0xf26338)
                if member: em.set_thumbnail(url=dutils.get_icon_url_for_member(member))
                em.set_footer(text='Times are in UTC')
                embeds.append(em)

            if len(embeds) == 1:
                embeds[0].title = title
                await ctx.send(embed=embeds[0])
            else:
                await SimplePaginator(extras=embeds).paginate(ctx)

        else:
            ws = [q for q in Actions.select().where(Actions.type == 'warn',
                                                    Actions.guild == ctx.guild.id).dicts()]
            if not ws:
                return await ctx.send("This server didn't issue any warnings yet.")
            ws = self.ws_to_usr_dict(ws)
            toEmbed = []
            for k, v in ws.items():
                toEmbed.append([v[0]['user_display_name'], str(k), len(v)])
            embeds = []
            leng = 0
            done = False
            warns = sorted(toEmbed, key=itemgetter(2), reverse=True)
            headers = ['Name', 'Id', 'Count']
            i = 1
            while True:
                desc = []
                idxRange = 0
                for warn in warns:
                    destCpy = desc.copy()
                    warn[0] = warn[0][:10]
                    destCpy.append(warn)
                    cc = columnar(destCpy, headers, no_borders=True)
                    if len(cc) > 990: break
                    desc.append(warn)
                    idxRange += 1
                del warns[:idxRange]
                cc = columnar(desc, headers, no_borders=True)
                embeds.append(Embed(title=f"Warnlist display. Page {i}/[MAX]", description=f'\n```{cc}\n```'))
                if len(warns) == 0: break
                i += 1

            for e in embeds:
                e.title = str(e.title).replace("[MAX]", str(i))

            if len(embeds) == 1:
                await ctx.send(embed=embeds[0])
            else:
                await SimplePaginator(extras=embeds).paginate(ctx)

    @staticmethod
    def ws_to_usr_dict(ws):
        ret = {}
        for w in ws:
            if not w['offender'] in ret: ret[w['offender']] = []
            ret[w['offender']].append(w)
        return ret

    @commands.check(checks.moderator_check)
    @commands.command()
    async def lock(self, ctx, *, channels=""):
        """Lock msg sending in a channel or channels (must be mentioned).

        `[p]lock` - Locks current channel
        `[p]lock silent` - Locks current channel (no feedback)
        `[p]lock #ch1 #ch2 #ch3` - Locks multiple channels
        `[p]lock silent #ch1 #ch2 #ch3` - Locks multiple channels silently (no feedback)
        `[p]lock all` - Locks all channels and posts the lock feedback in all channels
        `[p]lock all silent` - Locks all channels silently

        This command will also set perma locked channels.

        (`[p]lock all silent` = `[p] raid lockdown`)
        """
        await dutils.lock_channels(ctx, channels)

    @commands.check(checks.moderator_check)
    @commands.command()
    async def unlock(self, ctx, *, channels=""):
        """Unlock message sending in the channel.

        `[p]unlock` - Unlocks current channel
        `[p]unlock silent` - Unlocks current channel (no feedback)
        `[p]unlock #ch1 #ch2 #ch3` - Unlocks multiple channels
        `[p]unlock silent #ch1 #ch2 #ch3` - Unlocks multiple channels silently (no feedback)
        `[p]unlock all` - Unlocks all all non perma locked
        channels and posts the lock feedback in all channels
        `[p]unlock all silent` - Unlocks all non perma locked channels silently

        When doing the last two commands, be sure to have ran lock all (silent)
        at least once so perma locked channels are setup ...
        """
        await dutils.unlock_channels(ctx, channels)

    @commands.check(checks.moderator_check)
    @commands.command()
    async def slowmode(self, ctx, seconds: int, *, channels=""):
        """Set a slowmode

        `[p]slowmode 5` - Sets the slowmode to 5 seconds
        `[p]slowmode 10 silent` - Sets the slowmode to 5 seconds (no feedback)
        `[p]slowmode 15 #ch1 #ch2 #ch3` - Slowmodes multiple channels
        `[p]slowmode 30 silent #ch1 #ch2 #ch3` - Slowmodes multiple channels silently (no feedback)
        `[p]slowmode 60 all` - Slowmodes all channels (post feedback to all)
        `[p]slowmode 120 all silent` - Slowmodes all channels silently
        """
        if seconds > 21600: return await ctx.send("Max delay is 21600")
        if seconds < 0: return await ctx.send("Max is 0")
        try:
            all_ch = False
            silent = False
            if "silent" in channels.lower().strip():
                silent = True

            if "all" in channels.lower().strip():
                all_ch = True
                user = ctx.guild.get_member(ctx.bot.user.id)
                channels = [channel for channel in ctx.guild.text_channels if
                            channel.permissions_for(user).manage_roles]
            elif len(ctx.message.channel_mentions) == 0:
                channels = [ctx.channel]
            elif len(ctx.message.channel_mentions) == 0:
                channels = [ctx.channel]
            else:
                channels = ctx.message.channel_mentions
            m = None
            if all_ch:
                m = await ctx.send(f"Slowmoding all channels{'' if not silent else ' silently'}")
            for c in channels:
                await c.edit(slowmode_delay=seconds)
                if not silent:
                    await c.send(f"Slowmode set to **{tutils.convert_sec_to_smh(seconds)}**")
            if all_ch:
                await ctx.send('Done.')
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @commands.check(checks.moderator_check)
    @commands.command(aliases=["hcf"])
    async def hidechannelfrom(self, ctx, channel: discord.TextChannel, members: commands.Greedy[discord.Member]):
        """Hide channel from memebrs"""
        didnt_work = ""
        for m in members:
            try:
                await channel.set_permissions(m, read_messages=False)
            except:
                didnt_work += f'{m.mention} `{m}`\n'
        if didnt_work:
            await ctx.send(embed=Embed(title="Didn't work on", description=didnt_work))
        else:
            await ctx.send("Done.")

    @commands.check(checks.moderator_check)
    @commands.command(aliases=["uhcf"])
    async def unhidechannelfrom(self, ctx, channel: discord.TextChannel, members: commands.Greedy[discord.Member]):
        """Unhide channel from memebrs"""
        didnt_work = ""
        for m in members:
            try:
                await channel.set_permissions(m, read_messages=True)
            except:
                didnt_work += f'{m.mention} `{m}`\n'
        if didnt_work:
            await ctx.send(embed=Embed(title="Didn't work on", description=didnt_work))
        else:
            await ctx.send("Done.")


def setup(bot):
    ext = Moderation(bot)
    bot.add_cog(ext)
