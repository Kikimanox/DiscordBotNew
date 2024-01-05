import re

from discord import Message
from discord.ext import commands


class VxLinks(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot
    @commands.Cog.listener()
    async def on_message(
        self,
        msg: Message
    ):
        if msg.author.bot:
            return

        twitter_url = r'(https?://(?:www\.)?)(twitter|x)\.com'
        if re.search(twitter_url, msg.content):
            await msg.edit(suppress=True)
            vxtwitter_url = re.sub(twitter_url, r'\1vxtwitter.com', msg.content)

            await msg.reply(
                f"{vxtwitter_url}",
                mention_author=False
            )
        pixiv_url = r'(https?://(?:www\.)?)pixiv\.net'
        if re.search(pixiv_url, msg.content):
            await msg.edit(suppress=True)
            phixiv_url = re.sub(pixiv_url, r'\1phixiv.net', msg.content)
            await msg.reply(
                f"{phixiv_url}",
                mention_author=False
            )







async def setup(
        bot: commands.Bot
):
    ext = VxLinks(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
