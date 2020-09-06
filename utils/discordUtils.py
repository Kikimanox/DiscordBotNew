import asyncio

import utils.dataIO as dataIO
import os
from discord import Embed
from utils.dataIOa import dataIOa
import re
import datetime
import aiohttp
import random
from discord import File


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
    hook_ok = regular_ch.id == hook.channel_id
    if hook and hook_ok:
        try:
            await hook.send(embed=embed, content=content)
        except:
            await regular_ch.send(embed=embed, content=content)
    else:
        await regular_ch.send(embed=embed, content=content)
    if not hook_ok:
        await regular_ch.send("**Logging hook and channel id mismatch, please fix!!!**")
        bot.logger.error(f"**Logging hook and channel id mismatch, please fix!!! on: {guild} (id: "
                         f"{guild.id})**")
