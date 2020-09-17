import asyncio
import traceback

import discord
import time
import utils.dataIO as dataIO
import os
from discord import Embed

from models.antiraid import ArGuild
from models.bot import BotBlacklist, BotBanlist
from models.serversetup import Guild, SSManager
from utils.dataIOa import dataIOa
import re
import datetime
import aiohttp
import random
from discord import File
from models.moderation import (Reminderstbl, Actions, Blacklist, ModManager)


def bot_pfx(bot, _message):
    """
    :param bot: The bot
    :param _message: Preferrably mesage,
    if there is none use something that has the guild in it under .guild
    :return: prefix
    """
    prefix = bot.config['BOT_PREFIX']
    if hasattr(_message, 'channel') and isinstance(_message.channel, discord.DMChannel): return prefix
    gid = str(_message.guild.id)
    if gid not in bot.config['B_PREF_GUILD']: return prefix
    return bot.config['B_PREF_GUILD'][gid]


def bot_pfx_by_gid(bot, gid):
    prefix = bot.config['BOT_PREFIX']
    if str(gid) not in bot.config['B_PREF_GUILD']: return prefix
    return bot.config['B_PREF_GUILD'][str(gid)]


def escape_at(content):
    return content.replace('@', '@\u200b')


async def getChannel(ctx, arg):
    channels = []
    channel = arg.strip()
    if channel.startswith("<#") and channel.endswith(">"):
        chan = ctx.guild.get_channel(int(channel[2:-1]))
        if chan:
            channels.append(chan)
    else:
        for chan in ctx.guild.text_channels:
            if chan.name == channel or str(chan.id) == channel:
                if chan.permissions_for(ctx.author).read_messages:
                    channels.append(chan)
                    break
    if not channels:
        await ctx.send("The specified channel could not be found.")
        return None
    return channels[0]


def getEmbedFromMsg(msg):
    em = Embed(color=msg.author.color,
               timestamp=msg.created_at,
               description=f'{msg.content}\n\n[Jump to message]({msg.jump_url})')
    if len(msg.attachments) == 1:
        em.set_image(url=msg.attachments[0].url)
    if len(msg.attachments) > 1:
        em = Embed(color=msg.author.color,
                   timestamp=msg.created_at,
                   description=f'{msg.content}\n\n[Jump to message]({msg.jump_url})\n'
                               f'**🖼️ (Post contains multiple images, '
                               f'displaying only the first one)**')
        em.set_image(url=msg.attachments[0].url)

    em.set_author(name=msg.author.name, icon_url=msg.author.avatar_url)
    if not hasattr(msg.channel, 'name'):
        em.set_footer(text='Direct message')
    else:
        em.set_footer(text=f'#{msg.channel.name}')
    pic = str(msg.content).find('http')
    if pic > -1 and len(msg.attachments) == 0:
        urls = re.findall(r'https?:[/.\w\s-]*\.(?:jpg|gif|png|jpeg)', str(msg.content))
        if len(urls) > 0: em.set_image(url=urls[0])
    return em


def cleanUpBannedWords(bannerWordsArr, text):
    # bannedWords = ['@everyone', '@here']

    text = re.sub(r'`', '', text)

    for word in bannerWordsArr:
        if word in text:
            text = re.sub(rf'{word}', f'`{word}`', text)

    return text


async def print_hastebin_or_file(ctx, result):
    if len(result) > 1950:
        m = await ctx.send('Trying to upload to hastebin, this might take a bit')
        async with aiohttp.ClientSession() as session:
            async with session.post("https://hastebin.com/documents", data=str(result).encode('utf-8')) as resp:
                if resp.status == 200:
                    haste_out = await resp.json()
                    url = "https://hastebin.com/" + haste_out["key"]
                    result = 'Large output. Posted to Hastebin: %s' % url
                    await m.delete()
                    return await ctx.send(result)
                else:
                    file = str(int(datetime.datetime.utcnow().timestamp()) - random.randint(100, 100000))
                    with open(f"tmp/{file}.txt", "w") as f:
                        f.write(str(result))
                    with open(f"tmp/{file}.txt", "rb") as f:
                        py_output = File(f, f"{file}.txt")
                        await ctx.send(
                            content="Error posting to hastebin. Uploaded output to file instead.",
                            file=py_output)
                        try:
                            os.remove(f"tmp/{file}.txt")
                        except:
                            ctx.bot.logger.error("Failed to remove tmp/quote_output.txt")
                        await m.delete()
                        return
    else:
        return await ctx.send(result)


async def result_printer(ctx, result):
    if len(str(result)) > 2000:
        with open(f"tmp/{ctx.message.id}.txt", "w") as f:
            f.write(str(result.strip("```")))
        with open(f"tmp/{ctx.message.id}.txt", "rb") as f:
            py_output = File(f, "output.txt")
            await ctx.send(content="uploaded output to file since output was too long.", file=py_output)
            os.remove(f"tmp/{ctx.message.id}.txt")
    else:
        await ctx.send(result)


def getParts2kByDelimiter(text, delimi, extra='', limit=1900):
    ret = []
    arr = text.split(delimi)
    i = -1
    while arr:
        i += 1
        txt = ''
        while len(txt) < limit:
            if not arr: break
            txt += (arr[0] + delimi)
            del arr[0]
        txt = txt[:len(txt) - len(delimi)]
        if i > 0: txt = extra + txt
        if txt != '': ret.append(txt)
    return ret


async def saveFile(link, path, fName):
    fileName = f"{path}/{fName}"
    async with aiohttp.ClientSession() as session:
        async with session.get(link) as r:
            with open(fileName, 'wb') as fd:
                async for data in r.content.iter_chunked(1024):
                    fd.write(data)
    return fileName


async def prompt(ctx, message, *, timeout=60.0, delete_after=True, reactor_id=None):
    """An interactive reaction confirmation dialog.
    Parameters
    -----------
    ctx: any
        context from bot
    message: str
        The message to show along with the prompt.
    timeout: float
        How long to wait before returning.
    delete_after: bool
        Whether to delete the confirmation message after we're done.
    reactor_id: Optional[int]
        The member who should respond to the prompt. Defaults to the author of the
        Context's message.
    Returns
    --------
    Optional[bool]
        ``True`` if explicit confirm,
        ``False`` if explicit deny,
        ``None`` if deny due to timeout
    """

    if not ctx.channel.permissions_for(ctx.me).add_reactions:
        raise RuntimeError('Bot does not have Add Reactions permission.')

    fmt = f'{message}\n\nReact with \N{WHITE HEAVY CHECK MARK} to confirm or \N{CROSS MARK} to deny.'

    reactor_id = reactor_id or ctx.author.id
    msg = await ctx.send(fmt)

    confirm = None

    def check(payload):
        nonlocal confirm

        if payload.message_id != msg.id or payload.user_id != reactor_id:
            return False

        codepoint = str(payload.emoji)

        if codepoint == '\N{WHITE HEAVY CHECK MARK}':
            confirm = True
            return True
        elif codepoint == '\N{CROSS MARK}':
            confirm = False
            return True

        return False

    for emoji in ('\N{WHITE HEAVY CHECK MARK}', '\N{CROSS MARK}'):
        await msg.add_reaction(emoji)

    try:
        await ctx.bot.wait_for('raw_reaction_add', check=check, timeout=timeout)
    except asyncio.TimeoutError:
        confirm = None

    try:
        if delete_after:
            await msg.delete()
    finally:
        return confirm


async def try_send_hook(guild, bot, hook, regular_ch, embed, content=None, log_logMismatch=True):
    hook_ok = False
    if hasattr(hook, 'channel_id'):
        hook_ok = regular_ch.id == hook.channel_id
    if hook and hook_ok:
        try:
            await hook.send(embed=embed, content=content)
        except:
            return await regular_ch.send(embed=embed, content=content)
    else:
        if not hook_ok:
            if log_logMismatch:
                warn = "⚠**Logging hook and channel id mismatch, please fix!**⚠\n" \
                       "Can probably be fiex by changing the hook's target channel.\n" \
                       f"Or `{bot_pfx(bot, regular_ch)}setup webhooks` if there's something else wrong.\n" \
                       f"Target channel has to be {regular_ch.mention}" \
                       f"(tip: run the command `{bot_pfx(bot, regular_ch)}sup cur`)"
                bot.logger.error(f"**Logging hook and channel id mismatch, please fix!!! on: {guild} (id: "
                                 f"{guild.id})**")
                content = f"{'' if not content else content}\n\n{warn}"
        return await regular_ch.send(embed=embed, content=content)


async def ban_function(ctx, user, reason="", removeMsgs=0, massbanning=False,
                       no_dm=False, softban=False, actually_resp=None,
                       author=None, guild=None, bot=None, respch=None):
    if ctx:
        respch = ctx
        author = ctx.author
        guild = ctx.guild
        bot = ctx.bot
    member = user
    if not member:
        if massbanning: return -1
        return await respch.send('Could not find this user in this server')
    if member:
        try:
            if massbanning:
                bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}'] = 2
            if not massbanning:
                bot.just_banned_by_bot[f'{member.id}_{member.guild.id}'] = 1
            await member.ban(reason=reason, delete_message_days=removeMsgs)
            if softban:
                await member.unban(reason='Softbanned')
            try:
                if not no_dm and not massbanning:
                    await member.send(f'You have been {"banned" if not softban else "soft-banned"} '
                                      f'from the {str(guild)} '
                                      f'server {"" if not reason else f", reason: {reason}"}')
            except:
                print(f"Member {'' if not member else member.id} disabled dms")
            return_msg = f'{"Banned" if not softban else "Soft-banned"} the user {member.mention} (id: {member.id})'
            if reason:
                return_msg += f" for reason: `{reason}`"

            if not massbanning:
                await respch.send(embed=Embed(description=return_msg, color=0xdd0000))
            if not massbanning:
                typ = "ban"
                if removeMsgs == 7: typ = "banish"
                if softban and removeMsgs == 0: typ = "softban"
                if softban and removeMsgs == 7: typ = "softbanish"
                act_id = await moderation_action(ctx, reason, typ, member, no_dm=no_dm, actually_resp=actually_resp)
                await post_mod_log_based_on_type(ctx, typ, act_id, offender=member,
                                                 reason=reason, actually_resp=actually_resp)
            if not ctx and massbanning:
                act_id = await moderation_action(None, reason, 'ban', member, no_dm=no_dm,
                                                 actually_resp=author,
                                                 guild=guild, bot=bot)
                await post_mod_log_based_on_type(None, 'ban', act_id, offender=member,
                                                 reason=reason,
                                                 actually_resp=author,
                                                 guild=guild, bot=bot)

            return member.id
        except discord.Forbidden:
            if massbanning:
                del bot.banned_cuz_blacklist[f'{member.id}_{member.guild.id}']
            if massbanning: return -100  # special return
            await respch.send('Could not ban user. Not enough permissions.')
    else:
        if massbanning: return -1
        return await respch.send('Could not find user.')


async def unmute_user_auto(member, guild, bot, no_dm=False, actually_resp=None, reason="Auto"):
    try:
        mute_role = discord.utils.get(guild.roles, id=bot.from_serversetup[guild.id]['muterole'])
        if mute_role not in guild.get_member(member.id).roles:
            return
        await member.remove_roles(mute_role, reason=f'{reason}|{no_dm}')
        # try: done in listener
        #     muted = Reminderstbl.get(Reminderstbl.guild == guild.id, Reminderstbl.user_id == member.id)
        #     muted.delete_instance()
        # except:
        #     pass
        try:
            if not no_dm:
                await member.send(f'You have been unmuted on the {str(guild)} server.'
                                  f'{"" if not reason else f" Reason: **{reason}**"}')
        except:
            pass
        # act_id = await moderation_action(None, reason, "unmute", member, no_dm=no_dm,
        #                                  actually_resp=actually_resp, guild=guild, bot=bot)
        # await post_mod_log_based_on_type(None, "unmute", act_id, offender=member,
        #                                  reason=reason, actually_resp=actually_resp,
        #                                  guild=guild, bot=bot)
    except:
        print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
        traceback.print_exc()
        bot.logger.error(f"can not auto unmute {guild} {guild.id}")


async def unmute_user(ctx, member, reason, no_dm=False, actually_resp=None):
    try:
        can_even_execute = True
        if ctx.guild.id in ctx.bot.from_serversetup:
            sup = ctx.bot.from_serversetup[ctx.guild.id]
            if not sup['muterole']: can_even_execute = False
        else:
            can_even_execute = False
        # if not can_even_execute: return ctx.send("Mute role not setup, can not complete unmute.")
        if not can_even_execute: return ctx.bot.logger.error(f"Mute role not setup, can not "
                                                             f"complete unmute. {ctx.guild}, {ctx.jump_url}")
        mute_role = discord.utils.get(ctx.guild.roles, id=ctx.bot.from_serversetup[ctx.guild.id]['muterole'])
        if mute_role not in ctx.guild.get_member(member.id).roles:
            return await ctx.send("User is not muted")

        await member.remove_roles(mute_role, reason=f'{reason}|{no_dm}')
        # try: (now done in the listener)
        #     muted = Reminderstbl.get(Reminderstbl.guild == ctx.guild.id, Reminderstbl.user_id == member.id)
        #     muted.delete_instance()
        # except:
        #     pass
        await ctx.send(embed=Embed(description=f"{member.mention} has been unmuted.", color=0x76dfe3))
        try:
            if not no_dm:
                await member.send(f'You have been unmuted on the {str(ctx.guild)} server.'
                                  f'{"" if not reason else f" Reason: **{reason}**"}')
        except:
            print(f"Member {'' if not member else member.id} disabled dms")
            # act_id = await moderation_action(ctx, reason, "unmute", member, no_dm=no_dm, actually_resp=actually_resp)
            # await post_mod_log_based_on_type(ctx, "unmute", act_id, offender=member,
            #                                  reason=reason, actually_resp=actually_resp)
    except discord.errors.Forbidden:
        await ctx.send("💢 I don't have permission to do this.")


async def mute_user(ctx, member, length, reason, no_dm=False, new_mute=False, batch=False,
                    guild=None, bot=None, author=None, fdbch=None):
    """
    When ctx is missing, be sure to input the guild and bot and make.
    If ctx == None and you don't want the feedback, just turn on batch
    """
    if ctx:
        guild = ctx.guild
        bot = ctx.bot
        fdbch = ctx
        author = ctx.author
    can_even_execute = True
    if guild.id in bot.from_serversetup:
        sup = bot.from_serversetup[guild.id]
        if not sup['muterole']: can_even_execute = False
    else:
        can_even_execute = False
    if not can_even_execute:
        if not batch:
            return fdbch.send("Mute role not setup, can not complete mute.")
        else:
            return -1000
    mute_role = discord.utils.get(guild.roles, id=bot.from_serversetup[guild.id]['muterole'])
    if not new_mute:
        if mute_role in guild.get_member(member.id).roles:
            if not batch:
                return await fdbch.send(embed=Embed(description=f'{member.mention} is already muted', color=0x753c34))
            else:
                return -10
    unmute_time = None
    # thanks Luc#5653
    if length:
        units = {
            "d": 86400,
            "h": 3600,
            "m": 60,
            "s": 1
        }
        seconds = 0
        match = re.findall("([0-9]+[smhd])", length)  # Thanks to 3dshax server's former bot
        if not match:
            # p = bot_pfx(bot, ctx.message)
            p = bot_pfx_by_gid(bot, guild.id)
            if not batch:
                return await fdbch.send(f"Could not parse mute length. Are you sure you're "
                                        f"giving it in the right format? Ex: `{p}mute @user 30m`, "
                                        f"or `{p}mute @user 1d4h3m2s reason here`, etc.")
            else:
                return -35

        try:
            for item in match:
                seconds += int(item[:-1]) * units[item[-1]]
            timestamp = datetime.datetime.utcnow()
            delta = datetime.timedelta(seconds=seconds)
        except OverflowError:
            if not batch:
                return await fdbch.send("**Overflow!** Mute time too long. Please input a shorter mute time.")
            else:
                return 9001
        unmute_time = timestamp + delta

    try:
        bot.just_muted_by_bot[f'{member.id}_{member.guild.id}'] = 1
        await member.add_roles(mute_role, reason=reason)
        try:
            if not no_dm:
                await member.send(f'You have been muted on the {str(guild)} server '
                                  f'{"for " + length if length else "indefinitely "}'
                                  f' {"" if not reason else f"reason: {reason}"}')
        except:
            print(f"Member {'' if not member else member.id} disabled dms")
    except discord.errors.Forbidden:
        del bot.just_muted_by_bot[f'{member.id}_{member.guild.id}']
        if not batch:
            return await fdbch.send("💢 I don't have permission to do this.")
        else:
            return -19
    new_reason = reason  # deleted this functionality to not spam db
    reminder = bot.get_cog('Reminders')
    if reminder is None:
        if not batch:
            return await fdbch.send('Can not load remidners cog! (Weird error)')
        else:
            return -989
    try:
        mute = Reminderstbl.get(Reminderstbl.user_id == member.id, Reminderstbl.guild == guild.id)
        mute.len_str = 'indefinitely ' if not length else length
        mute.expires_on = unmute_time if length else datetime.datetime.max
        mute.executed_by = author.id
        mute.reason = new_reason

        mute.save()
        tim = await reminder.create_timer(
            expires_on=unmute_time,
            meta='mute_nodm' if no_dm else 'mute',
            gid=guild.id,
            reason=new_reason,
            uid=member.id,
            len_str='indefinitely ' if not length else length,
            author_id=author.id,
            unmute_user=True,
            orig_id=mute.id
        )
    except:
        tim = await reminder.create_timer(
            expires_on=unmute_time,
            meta='mute_nodm' if no_dm else 'mute',
            gid=guild.id,
            reason=reason,
            uid=member.id,
            len_str='indefinitely ' if not length else length,
            author_id=author.id
        )
    if not batch:
        await fdbch.send(embed=Embed(
            description=f"{member.mention} is now muted from text channels{' for ' + length if length else ''}.",
            color=0x6785da))
        if ctx:
            act_id = await moderation_action(ctx, new_reason, "mute", member, no_dm=no_dm, actually_resp=author)
            await post_mod_log_based_on_type(ctx, "mute", act_id,
                                             mute_time_str='indefinitely' if not length else length,
                                             offender=member, reason=new_reason, actually_resp=author)
    if not ctx and batch:
        act_id = await moderation_action(None, new_reason, 'mute', member, no_dm=no_dm,
                                         actually_resp=author,
                                         guild=guild, bot=bot)
        await post_mod_log_based_on_type(None, 'mute', act_id, offender=member,
                                         reason=new_reason,
                                         mute_time_str='indefinitely' if not length else length,
                                         actually_resp=author,
                                         guild=guild, bot=bot)
    return 10
    # dataIOa.save_json(self.modfilePath, modData)
    # await dutils.mod_log(f"Mod log: Mute", f"**offender:** {str(member)} ({member.id})\n"
    #                                       f"**Reason:** {reason}\n"
    #                                       f"**Responsible:** {str(ctx.author)} ({ctx.author.id})",
    #                     colorr=0x33d8f0, author=ctx.author)


async def moderation_action(ctx, reason, action_type, offender, no_dm=False,
                            actually_resp=None, guild=None, bot=None):
    """
    :param ctx: ctx
    :param reason: reason
    :param action_type: mute, warn, ban, blacklist
    :param offender: offender member
    :param no_dm: did the member recieve a dm of the action
    :param actually_resp: in case the responsible isn't the one in the ctx (has to be filled if ctx is None)
    :param guild: has to be filled if ctx is None
    :param bot: has to be filled if ctx is None
    :return: insert id or None if fails
    """
    chan = 0
    jump = "(auto)"
    if ctx:
        guild = ctx.guild
        bot = ctx.bot
        author = ctx.author
        p = bot_pfx(bot, ctx.message)
        chan = ctx.channel.id
        jump = ctx.message.jump_url
    try:
        disp_n = "(left server)"
        if offender and hasattr(offender, 'id'):
            disp_n = offender.display_name
            offender = offender.id
        resp = None
        if actually_resp:
            resp = actually_resp
        else:
            resp = ctx.author
        ins_id = Actions.insert(guild=guild.id, reason=reason, type=action_type, channel=chan,
                                jump_url=jump, responsible=resp.id,
                                offender=offender, user_display_name=disp_n, no_dm=no_dm).execute()
        case_id = Actions.select().where(Actions.guild == guild.id).count()
        Actions.update(case_id_on_g=case_id).where(Actions.id == ins_id).execute()
        return case_id
    except:
        bot.logger.error(f"Failed to insert mod action: {jump}")
        return None


async def post_mod_log_based_on_type(ctx, log_type, act_id, mute_time_str="",
                                     offender=None, reason=None, warn_number=1,
                                     actually_resp=None, guild=None, bot=None):
    # Make CTX None if it doesnt exist, but do make guild and bot and actually_resp are something
    if ctx:
        guild = ctx.guild
        bot = ctx.bot
        author = ctx.author
        p = bot_pfx(bot, ctx.message)
    else:
        p = bot_pfx_by_gid(bot, guild.id)

    em = Embed()
    responsb = None
    le_none = "*No reason provided.\n" \
              "Can still be supplied with:\n" \
              f"`{p}case {act_id} reason here`*"
    if actually_resp:
        responsb = actually_resp
    else:
        responsb = ctx.author
    if not reason: reason = le_none

    em.add_field(name='Responsible', value=f'{responsb.mention}\n{responsb}', inline=True)
    off_left_id = -1  # -1 means that offender exists on the server
    if offender and not hasattr(offender, 'id'):
        off_left_id = offender

    if offender and off_left_id == -1:
        em.add_field(name='Offender', value=f'{offender.mention}\n{offender}\n{offender.id}', inline=True)
    if offender and off_left_id != -1:
        em.add_field(name='Offender', value=f'{off_left_id}\n(left server)', inline=True)

    if log_type == 'blacklist':
        em.add_field(name='Reason', value=f'{le_none}\n**Ofenders:**\n{reason}', inline=True if offender else False)
    if log_type == 'whitelist':
        em.add_field(name='Reason', value=f'{le_none}\n**Command:**\n{reason.split("|")[0]}'
                                          f'\n**Result:**\n{reason.split("|")[-1]}', inline=True if offender else False)
    # these above have to be the ones in the bottom array
    if log_type not in ['blacklist', 'whitelist']:
        em.add_field(name='Reason', value=reason, inline=True if offender else False)

    title = ""
    if log_type == 'mute':
        title = "User muted indefinitely" if mute_time_str == 'indefinitely' else f'User muted for {mute_time_str}'
        em.colour = 0xbf5b30

    if log_type == 'Right click mute':
        title = "User right click muted"
        em.colour = 0xbf5b30

    if 'ban' in log_type and log_type != 'unban':
        title = log_type.capitalize()
        em.colour = 0xe62d10

    if log_type == 'unban':
        title = "User unbanned"
        em.colour = 0x45ed9c

    if log_type == 'blacklist':
        title = "Blacklist"
        em.colour = 0x050100

    if log_type == 'whitelist':
        title = "whitelist"
        em.colour = 0xfcf7f7

    if log_type == 'warn':
        tim = 'times already' if warn_number > 1 else 'time'
        title = f'User warned ({warn_number} {tim})'
        em.colour = 0xfa8507

    if log_type == 'unmute':
        title = f"User unmuted"
        em.colour = 0x62f07f

    if log_type == 'kick':
        title = f"User kicked"
        em.colour = 0xe1717d

    if log_type == 'massmute':
        title = "Users muted indefinitely" if mute_time_str == 'indefinitely' else f'Users muted for {mute_time_str}'
        em.colour = 0x9e4b28

    # em.set_thumbnail(url=get_icon_url_for_member(ctx.author))
    if offender:
        em.set_author(name=title, icon_url=get_icon_url_for_member(offender))
    else:
        em.title = title
    em.set_footer(text=f"{datetime.datetime.utcnow().strftime('%c')} | "
                       f'Case id: {act_id}')
    now = datetime.datetime.utcnow()
    await log(bot, this_embed=em, this_hook_type='modlog', guild=guild)
    if not bot.from_serversetup:
        bot.from_serversetup = await SSManager.get_setup_formatted(bot)
    if guild.id not in bot.from_serversetup: return
    chan = bot.from_serversetup[guild.id]['modlog']
    if chan:
        Actions.update(logged_after=now, logged_in_ch=chan.id
                       ).where(Actions.case_id_on_g == act_id,
                               Actions.guild == guild.id).execute()


async def log(bot, title=None, txt=None, author=None,
              colorr=0x222222, imageUrl='', guild=None, content=None,
              this_embed=None, this_content=None,
              this_hook_type=None):
    """
    :param title:
    :param txt:
    :param author:
    :param colorr:
    :param imageUrl:
    :param guild:
    :param content:
    :param this_embed:
    :param this_content:
    :param this_hook_type: this_hook_type: reg | leavejoin | modlog
    :param bot:
    :return:
    """
    try:
        hook_typ = 'reg'
        if this_hook_type: hook_typ = this_hook_type
        if not bot.from_serversetup:
            bot.from_serversetup = await SSManager.get_setup_formatted(bot)
        if guild.id not in bot.from_serversetup: return
        sup = bot.from_serversetup[guild.id]
        if not this_content and not this_embed:
            desc = []
            while len(txt) > 0:
                desc.append(txt[:2000])
                txt = txt[2000:]
            i = 0
            for txt in desc:
                em = discord.Embed(description=txt, color=colorr)
                if author:
                    icon_url = author.avatar_url if 'gif' in str(author.avatar_url).split('.')[-1] else str(
                        author.avatar_url_as(format="png"))
                    em.set_author(name=f"{title}", icon_url=icon_url)
                em.set_footer(text=f"{datetime.datetime.utcnow().strftime('%c')}")
                if imageUrl:
                    try:
                        em.set_thumbnail(url=imageUrl)
                    except:
                        pass
                if title and not author:
                    em.title = title
                cnt = None
                if i == 0 and content:
                    cnt = content
                    i += 1

                return await try_send_hook(guild, bot, hook=sup[f'hook_{hook_typ}'],
                                           regular_ch=sup[hook_typ], embed=em, content=cnt)
        else:
            return await try_send_hook(guild, bot,
                                       hook=sup[f'hook_{hook_typ}'],
                                       regular_ch=sup[hook_typ], embed=this_embed,
                                       content=this_content)

    except:
        print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
        traceback.print_exc()
        bot.logger.error("Something went wrong when logging")


async def ban_from_bot(bot, offender, meta, gid, ch_to_reply_at=None, arl=0):
    if offender.id == bot.config['OWNER_ID']: return
    print(meta)
    bot.banlist[offender.id] = meta
    try:
        bb = BotBanlist.get(BotBlacklist.user == offender.id)
        bb.meta = meta
        bb.when = datetime.datetime.utcnow()
        bb.guild = gid
        bb.save()
    except:
        BotBanlist.insert(user=offender.id, guild=gid, meta=meta).execute()
    if ch_to_reply_at:
        if arl < 2:
            await ch_to_reply_at.send(f'💢 💢 💢 {offender.mention} you have been banned from the bot!')


async def blacklist_from_bot(bot, offender, meta, gid, ch_to_reply_at=None, arl=0):
    if offender.id == bot.config['OWNER_ID']: return
    print(meta)
    bot.blacklist[offender.id] = meta
    try:
        bb = BotBlacklist.get(BotBlacklist.user == offender.id)
        bb.meta = meta
        bb.when = datetime.datetime.utcnow()
        bb.guild = gid
        bb.save()
    except:
        BotBlacklist.insert(user=offender.id, guild=gid, meta=meta).execute()
    if arl < 2:
        await ch_to_reply_at.send(
            f'💢 {offender.mention} you have been blacklisted from the bot '
            f'for spamming. You may remove yourself from the blacklist '
            f'once in a certain period. '
            f'To do that you can use `{bot_pfx_by_gid(bot, gid)}unblacklistme`')


def get_icon_url_for_member(member):
    return member.avatar_url if 'gif' in str(member.avatar_url).split('.')[-1] else \
        str(member.avatar_url_as(format="png"))


async def saveFiles(links, savePath='tmp', fName=''):
    # https://cdn.discordapp.com/attachments/583817473334312961/605911311401877533/texture.png
    fileNames = []
    for ll in links:
        try:
            urll = ll.url
        except:
            urll = ll
        fileName = f'{savePath}/' + str(datetime.datetime.now().timestamp()).replace('.', '') \
                   + '.' + str(urll).split('.')[-1] \
            if not fName else f'{savePath}/{fName}_{str(datetime.datetime.now().timestamp()).replace(".", "")}' + \
                              '.' + str(urll).split('.')[-1]
        fileNames.append(fileName)
        async with aiohttp.ClientSession() as session:
            async with session.get(urll) as r:
                with open(fileName, 'wb') as fd:
                    async for data in r.content.iter_chunked(1024):
                        fd.write(data)
    return fileNames


async def lock_channels(ctx, channels):
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
        perma_locked_channels = []
        m = None
        if all_ch:
            m = await ctx.send(f"Locking all channels{'' if not silent else ' silently'}")
        for c in channels:
            ow = ctx.guild.default_role
            overwrites_everyone = c.overwrites_for(ow)
            if all_ch and overwrites_everyone.send_messages is False:
                perma_locked_channels.append(str(c.id))
                continue
            elif overwrites_everyone.send_messages is False:
                await ctx.send(f"🔒 {c.mention} is already locked down. Use `.unlock` to unlock.")
                continue
            overwrites_everyone.send_messages = False
            await c.set_permissions(ow, overwrite=overwrites_everyone)
            if not silent:
                await c.send("🔒 Channel locked.")

        if perma_locked_channels:
            try:
                g = ArGuild.get(ArGuild.id == ctx.guild.id)
                g.perma_locked_channels = ' '.join(perma_locked_channels)
            except:
                ArGuild.insert(id=ctx.guild.id).execute()
        if m: await m.delete()
        if all_ch:
            await ctx.send('Done.')
    except discord.errors.Forbidden:
        await ctx.send("💢 I don't have permission to do this.")


async def unlock_channels(ctx, channels):
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
        else:
            channels = ctx.message.channel_mentions
        perma_locked_channels = []
        if all_ch:
            try:
                g = ArGuild.get(ArGuild.id == ctx.guild.id)
                perma_locked_channels = g.perma_locked_channels.split()
            except:
                if all_ch: return await ctx.send(
                    'Can not use `unlock all` without `lock all` '
                    'being used at least once before on the server.')
        m = None
        if all_ch:
            m = await ctx.send(f"Unlocking all channels{'' if not silent else ' silently'}")
        for c in channels:
            ow = ctx.guild.default_role
            overwrites_everyone = c.overwrites_for(ow)
            if all_ch and str(c.id) in perma_locked_channels:
                continue
            elif overwrites_everyone.send_messages is None:
                await ctx.send(f"🔓 {c.mention} is already unlocked.")
                continue
            overwrites_everyone.send_messages = None
            await c.set_permissions(ow, overwrite=overwrites_everyone)
            if not silent:
                await c.send("🔓 Channel unlocked.")
        if m: await m.delete()
        if all_ch:
            return await ctx.send('Done.')

    except discord.errors.Forbidden:
        await ctx.send("💢 I don't have permission to do this.")


async def punish_based_on_arl(arl, message, bot, mentions=False):
    extra_rsn = ' mass mention' if mentions else ' spam'
    rsn = f"Level {arl} raid protection:\n**{extra_rsn}**"
    if arl == 2:
        # async def mute_user(ctx, member, length, reason, no_dm=False, new_mute=False, batch=False,
        #                     guild=None, bot=None, author=None, fdbch=None):
        if message.guild:
            return await mute_user(None, message.author, '', rsn,
                                   no_dm=True, batch=True, guild=message.guild, bot=bot,
                                   author=bot.user)
    if arl == 3:
        if len(message.author.roles) == 1:  # if member has no roles
            await ban_function(None, message.author, rsn,
                               removeMsgs=1, no_dm=True,
                               author=bot.user, guild=message.guild, bot=bot, massbanning=True)
        else:
            m = message.guild.get_member(message.author.id)
            print(str(m))
            if m:
                try:
                    await message.author.kick(reason=rsn)
                    act_id = await moderation_action(None, rsn, 'kick', message.author, no_dm=True,
                                                     actually_resp=bot.user,
                                                     guild=message.guild, bot=bot)
                    await post_mod_log_based_on_type(None, 'kick', act_id, offender=message.author,
                                                     reason=rsn,
                                                     actually_resp=bot.user,
                                                     guild=message.guild, bot=bot)
                except:
                    pass


async def try_get_member(ctx, user):
    member = None
    if not user: return member
    
    if ctx.message.mentions:
        member = ctx.message.mentions[0]
    elif user and user.isdigit():
        member = ctx.guild.get_member(int(user))
    else:
        member = discord.utils.get(ctx.guild.members, name=user)
    return member
