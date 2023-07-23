import logging
import traceback

from discord import Embed
from discord.ext import commands

import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils

logger = logging.getLogger('info')
error_logger = logging.getLogger('error')


class Quoting(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(aliases=["q"])
    async def quote(self, ctx, *args):
        """Quote a message.
        I should really rewrite this horribly written command already ...
        `[p]q` (will quote the last message)
        `[p]q Message_id` (will find the message with this id in this channel)
        `[p]q Message content` here (will find the message with this content in this channel (last 2k messages max))
        Note: message content is CASE SENSITIVE
        `[p]q msg | channel_name` (eg. general)
        `[p]q msg | channel_id` (eg. 12345678910)
        `[p]q msg | channel_mention` (eg. #general)"""
        msg = None
        if len(args) == 0:
            messages = []
            async for message in ctx.channel.history(limit=2):
                messages.append(message)
            msg = messages[1]
        if len(args) >= 1:
            potentialID = args[0]
            chan = ctx.channel
            qu = ' '.join(args[0:])
            split = qu.split(' | ')
            if len(split) > 1:
                ch = await dutils.getChannel(ctx, split[-1])
                if ch:
                    chan = ch
                else:
                    return
            if len(potentialID) > 15 and potentialID.isdigit():
                try:
                    msg = await chan.fetch_message(int(potentialID))
                except:
                    pass
            if not msg:
                async for ms in chan.history(limit=2000, before=ctx.message.created_at):
                    if split[0] in ms.content:
                        msg = ms
                        break
        if not msg:
            await ctx.send('No such message found.')
            return
        em = dutils.getEmbedFromMsg(msg)
        if len(em.description) > 1960:
            em.description = em.description[:1850] + "\n\nℹ **Orignal content is longer, " \
                                                     "please view original message**" \
                                                     f"\n\n[Jump to message]({msg.jump_url})"
            # em.description = f'**Content too long, uploaded to hastebin**\n' \
            #                  f'{await dutils.getHasteBinLinkOrMakeFileRet(ctx, em.description)}\n\n' \
            #                  f'[Jump to message]({msg.jump_url})'

        if len(msg.embeds) > 0:
            e = msg.embeds[0]
            b = (e.thumbnail and e.thumbnail.url in msg.content)
            if not (b and not e.description and not e.title and not e.image):
                if msg.content:
                    await ctx.send("**Content quote:**")
                    await ctx.send(embed=em)
                else:
                    await ctx.send(embed=Embed(description=f"*[This message]({msg.jump_url}) has no content*"))
                await ctx.send("**Embed quote:**")
                for emm in msg.embeds:
                    await ctx.send(embed=emm)
            else:
                await ctx.send(embed=em)
        else:
            await ctx.send(embed=em)

    @quote.error
    async def avatar_error(self, ctx, error):
        await ctx.send('Error in the quote command')

    @commands.cooldown(1, 15, commands.BucketType.channel)
    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.check(checks.admin_check)
    @commands.command()
    async def archive(self, ctx):
        """Remove all pins and post them in the channel.

        Make sure to lock the channel from view before doing so, avoiding
        spamming notifications to everyone that has them enabled.

        The bot will pin the last message of the
        output, incidating old pins above when done.

        This command has a 1 hour cooldown per channel."""

        pins = await ctx.channel.pins()
        if len(pins) <= 1:
            return await ctx.send("💢 I won't archive only one or less pins. ")

        firstMsg = await ctx.send(f"Starting archive "
                                  f"({tutils.convertTimeToReadable1(ctx.message.created_at)})")

        for pin in pins:
            try:
                # await ctx.send(embed=dutils.getEmbedFromMsg(pin))

                em = dutils.getEmbedFromMsg(pin)
                if len(em.description) > 1960:
                    em.description = em.description[:1850] + "\n\nℹ **Orignal content is longer, " \
                                                             "please view original message**" \
                                                             f"\n\n[Jump to message]({pin.jump_url})"
                    # em.description = f'**Content too long, uploaded to hastebin**\n' \
                    #                f'{await dutils.getHasteBinLinkOrMakeFileRet(ctx, em.description)}\n\n' \
                    #                f'[Jump to message]({pin.jump_url})'
                if len(pin.embeds) > 0:
                    if hasattr(pin.embeds[0], 'author') and hasattr(pin.embeds[0].author, 'id'):
                        if not pin.embeds[0].author.id == ctx.bot.config['CLIENT_ID']:
                            if not pin.embeds[0].description or 'Finished archiving pins' \
                                    not in pin.embeds[0].description:
                                if pin.content:
                                    await ctx.send("**Content quote:**")
                                    await ctx.send(embed=em)
                                else:
                                    await ctx.send(embed=Embed(description=f"*[This message]({pin.jump_url}) "
                                                                           f"has no content*"))

                                await ctx.send("**Embed quote:**")
                        for emm in pin.embeds:
                            await ctx.send(embed=emm)
                    else:
                        await ctx.send(embed=em)
                else:
                    await ctx.send(embed=em)

                await pin.unpin()
            except:
                # print(f'Archive error at message {pin.id}')
                error_logger.error(f'Archive error at message {pin.id}\n{traceback.format_exc()}')
                await ctx.send(embed=Embed(description=f'Archive error at message {pin.id}'))

        msg = await ctx.send(embed=Embed(description=f'Finished archiving pins '
                                                     f'**({tutils.convertTimeToReadable1(ctx.message.created_at)})**\n'
                                                     f'You can view the archived pins above this message'
                                                     f'\n\n[Jump to the top of this session]({firstMsg.jump_url})',
                                         color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR']))
        await msg.pin()

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.manage_messages_check)
    @commands.command()
    async def pinstatus(self, ctx, *arg):
        """Check pin count status on the server.

        Pin counts exceeding 40 will be bolded in the output. Usage:

        `[p]pinstatus` (get all pin counts from all channels)
        `[p]pinstatus #general` (get pin count from general, by channel link)
        `[p]pinstatus 409738380797018123` (get pin status from general, but by id)
        `[p]pinstatus general` (get pin status from genera, but by name)"""
        msg = await ctx.send('Gathering data...')
        if arg and len(arg) == 1:
            ch = await dutils.getChannel(ctx, arg[0])
            if ch:
                await ctx.send(f'```{str(ch)} - {len(await ch.pins())}```')

        if not arg:
            res = ""
            for chp in sorted([[str(ch), len(await ch.pins())] for ch in ctx.guild.text_channels],
                              key=lambda x: x[1], reverse=True):
                if chp[1] == 0: continue
                if chp[1] > 40: chp[1] = f'**{chp[1]}**'
                res += "{} | {}\n".format(*chp)
            await ctx.send(embed=Embed(description=res, title='Pin status', color=0xea7938))
        await msg.delete()

    @commands.command()
    async def raw(self, ctx, *args):
        """
        Get raw message content and display it.

        Command syntax is the same as for the quote command.

        `[p]raw` (will get the last message)
        `[p]raw Message_id` (will find the message with this id in this channel)
        `[p]raw Message content here` (will find the message with this content in this channel (last 2k messages max))
        Note: message content is CASE SENSITIVE
        `[p]raw msg | channel_name` (eg. general)
        `[p]raw msg | channel_id` (eg. 12345678910)
        `[p]raw msg | channel_mention` (eg. #general)"""
        msg = None
        if len(args) == 0:
            messages = []
            async for message in ctx.channel.history(limit=2):
                messages.append(message)
            msg = messages[1]
        if len(args) >= 1:
            potentialID = args[0]
            chan = ctx.channel
            qu = ' '.join(args[0:])
            split = qu.split(' | ')
            if len(split) > 1:
                ch = await dutils.getChannel(ctx, split[-1])
                if ch:
                    chan = ch
                else:
                    return
            if len(potentialID) > 15 and potentialID.isdigit():
                try:
                    msg = await chan.fetch_message(int(potentialID))
                except:
                    pass
            if not msg:
                async for ms in chan.history(limit=2000, before=ctx.message.created_at):
                    if split[0] in ms.content:
                        msg = ms
                        break
        if not msg:
            await ctx.send('No such message found.')
            return
        msgCnt = msg.content.replace("```", "\`\`\`")
        if msgCnt:
            await ctx.send(embed=Embed(description=f'```\n{msgCnt}\n```'))
        for e in msg.embeds:
            msgCnt2 = e.description.replace("```", "\`\`\`")
            await ctx.send(embed=Embed(description=f'```\n{msgCnt2}\n```'))


async def setup(bot: commands.Bot):
    ext = Quoting(bot)
    await bot.add_cog(ext)
