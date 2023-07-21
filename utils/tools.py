from difflib import get_close_matches, SequenceMatcher
import asyncio
import os
import logging
from logging import handlers
from typing import Tuple, Union

import discord
from discord import File
from discord import ClientUser


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


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


async def get_text_channel(bot: ClientUser, channel_id: int) -> Tuple[Union[discord.TextChannel, discord.Thread], discord.TextChannel]:
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except:
            return None, None
    parent_channel = channel.parent if hasattr(channel, "parent") else channel
    return channel, parent_channel


def get_user_avatar_url(user: discord.User):
    try:
        return user.avatar.with_format("png").url if user.avatar else user.default_avatar.url
    except ValueError:
        return ""
