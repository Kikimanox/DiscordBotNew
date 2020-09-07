import asyncio
import traceback

import discord
import time
import utils.dataIO as dataIO
import os
from discord import Embed
from utils.dataIOa import dataIOa
import re
import datetime
import aiohttp
import random
from discord import File
from models.moderation import (Mutes, Actions, Blacklist, ModManager)


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


async def getHasteBinLinkOrMakeFileRet(ctx, result):
    m = await ctx.send('Trying to upload to hastebin, this might take a bit')
    async with aiohttp.ClientSession() as session:
        async with session.post("https://hastebin.com/documents", data=str(result).encode('utf-8')) as resp:
            if resp.status == 200:
                haste_out = await resp.json()
                url = "https://hastebin.com/" + haste_out["key"]
            else:
                with open("tmp/quote_output.txt", "w") as f:
                    f.write(str(result))
                with open("tmp/quote_output.txt", "rb") as f:
                    py_output = File(f, "quote_output.txt")
                    await ctx.send(
                        content="Error posting to hastebin. Uploaded output to file instead.",
                        file=py_output)
                    try:
                        os.remove("tmp/quote_output.txt")
                    except:
                        ctx.bot.logger.error("Failed to remove tmp/quote_output.txt")
                    await m.delete()
                    return ''
    result = url
    await m.delete()
    return result


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


async def try_send_hook(guild, bot, hook, regular_ch, embed, content=None):
    hook_ok = False
    if hasattr(hook, 'channel_id'):
        hook_ok = regular_ch.id == hook.channel_id
    if hook and hook_ok:
        try:
            await hook.send(embed=embed, content=content)
        except:
            await regular_ch.send(embed=embed, content=content)
    else:
        await regular_ch.send(embed=embed, content=content)
    if not hook_ok:
        await regular_ch.send("⚠**Logging hook and channel id mismatch, please fix!**⚠\n"
                              f"(tip: run the command `{bot.config['BOT_PREFIX']}sup cur`)")
        bot.logger.error(f"**Logging hook and channel id mismatch, please fix!!! on: {guild} (id: "
                         f"{guild.id})**")


async def mute_user(ctx, member, length, reason):
    mute_role = discord.utils.get(ctx.guild.roles, id=ctx.bot.from_serversetup[ctx.guild.id]['muterole'])
    if mute_role in ctx.guild.get_member(member.id).roles:
        return await ctx.send(embed=Embed(description=f'{member.mention} is already muted', color=0x753c34))
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
            p = ctx.bot.config['BOT_PREFIX']
            return await ctx.send(f"Could not parse mute length. Are you sure you're "
                                  f"giving it in the right format? Ex: `{p}mute @user 30m`, "
                                  f"or `{p}mute @user 1d4h3m2s reason here`, etc.")
        try:
            for item in match:
                seconds += int(item[:-1]) * units[item[-1]]
            timestamp = datetime.datetime.now()
            delta = datetime.timedelta(seconds=seconds)
        except OverflowError:
            return await ctx.send("**Overflow!** Mute time too long. Please input a shorter mute time.")
        unmute_time = timestamp + delta

        # modData[str(ctx.guild.id)]["muted_users"][str(member.id)] = {"until": unmute_time.timestamp(),
        #                                                             "muted_member": str(member),
        #                                                             "reason": reason,
        #                                                             "until_ver2": unmute_time.strftime('%c')}
    try:
        await member.add_roles(mute_role)
        try:
            await member.send(f'You have been muted on the {str(ctx.guild)} server '
                              f'{"for " + length if length else "indefinitely "}'
                              f' {"" if not reason else f"reason: {reason}"}')
        except:
            print(f"Member {'' if not member else member.id} disabled dms")
    except discord.errors.Forbidden:
        return await ctx.send("💢 I don't have permission to do this.")
    # if not length:
    # modData[str(ctx.guild.id)]["muted_users"][str(member.id)] = {"until": 999999999999,
    #                                                             "muted_member": str(member),
    #                                                             "reason": reason,
    #                                                            "until_ver2": 'indefinitely '}
    # print(f'{datetime.datetime.now().strftime("%c")} ({ctx.guild.id} | {str(ctx.guild)}) MOD LOG (mute):'
    #       f' {str(ctx.author)} ({ctx.author.id}) muted '
    #       f'the user {str(member)} ({member.id}).{" Length: " + length if length else " Length: indefinitely "} '
    #       f'Reason: {reason}')

    try:
        mute = Mutes.get(Mutes.user_id == member.id, Mutes.guild == ctx.guild.id)
        mute.len_str = 'indefinitely ' if not length else length
        mute.expires_on = unmute_time if length else datetime.datetime.max
        mute.muted_by = ctx.author.id
        mute.reason = mute.reason + ' ||| ' + reason
        mute.save()
    except:
        Mutes.insert(guild=ctx.guild.id, reason=reason, user_id=member.id,
                     len_str='indefinitely ' if not length else length,
                     expires_on=unmute_time if length else datetime.datetime.max,
                     muted_by=ctx.author.id).execute()
    await ctx.send(embed=Embed(
        description=f"{member.mention} is now muted from text channels{' for ' + length if length else ''}.",
        color=0x6785da))
    act_id = await moderation_action(ctx, reason, "mute", member)
    await post_mod_log_based_on_type(ctx, "mute", act_id)
    # dataIOa.save_json(self.modfilePath, modData)
    # await dutils.mod_log(f"Mod log: Mute", f"**Offended:** {str(member)} ({member.id})\n"
    #                                       f"**Reason:** {reason}\n"
    #                                       f"**Responsible:** {str(ctx.author)} ({ctx.author.id})",
    #                     colorr=0x33d8f0, author=ctx.author)


async def moderation_action(ctx, reason, action_type, offended):
    """
    :param ctx: ctx
    :param reason: reason
    :param action_type: mute, warn, ban, blacklist
    :param offended: offended member
    :return: insert id or None if fails
    """
    try:
        ins_id = Actions.insert(guild=ctx.guild.id, reason=reason, type=action_type, channel=ctx.channel.id,
                                jump_url=ctx.message.jump_url, responsible=ctx.author.id,
                                offended=offended.id).execute()
        return ins_id
    except:
        ctx.bot.logger.error(f"Failed to insert mod action: {ctx.message.jump_url}")
        return None


async def post_mod_log_based_on_type(ctx, log_type, act_id):
    await log(ctx, this_content="TODO", this_embed=Embed(description="TODO"), this_hook_type='modlog')


async def log(ctx, title=None, txt=None, author=None,
              colorr=0x222222, imageUrl='', guild=None, content=None,
              this_embed=None, this_content=None, this_hook_type=None):
    """
    :param ctx:
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
    :return:
    """
    try:
        guild = ctx.guild if not guild else guild
        sup = ctx.bot.from_serversetup[guild.id]
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
                em.set_footer(text=f"{datetime.datetime.now().strftime('%c')}")
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

                await try_send_hook(guild, ctx.bot, hook=sup['hook_reg'],
                                    regular_ch=sup['reg'], embed=em, content=cnt)
        else:
            await try_send_hook(guild, ctx.bot,
                                hook=sup['hook_reg' if not this_hook_type else f'hook_{this_hook_type}'],
                                regular_ch=sup['reg' if not this_hook_type else this_hook_type], embed=this_embed,
                                content=this_content)

    except:
        traceback.print_exc()
        ctx.bot.logger.error("Something went wrong when logging")
