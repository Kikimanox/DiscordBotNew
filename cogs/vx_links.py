import re

from discord import Message, Webhook, Thread
from discord.ext import commands


class VxLinks(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot


    async def cog_load(self) -> None:
        guilds = self.bot.guilds
        for guild in guilds:
            channels = guild.text_channels + guild.forums + guild.voice_channels
            for channel in channels:
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    if webhook.name == "vxlinks" and webhook.user == self.bot.user:
                        await webhook.delete()

    async def create_webhook(self, channel) -> Webhook:
        if isinstance(channel, Thread):
            channel = channel.parent

        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name == "vxlinks" and webhook.user == self.bot.user:
                return webhook
        return await channel.create_webhook(name="vxlinks")

    async def send_webhook_message(
            self,
            channel,
            replied_message: Message,
            content: str
    ):
        webhook = await self.create_webhook(channel)
        if isinstance(channel, Thread):
            await webhook.send(
                content,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                thread= channel,
                wait=True
            )
        else:
            await webhook.send(
                content,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                wait=True
            )

        await replied_message.delete()




    @commands.Cog.listener()
    async def on_message(
        self,
        msg: Message
    ):

        twitter_url = r'(https?://(?:www\.)?)(twitter|x)\.com'
        if re.search(twitter_url, msg.content):
            vxtwitter_url = re.sub(twitter_url, r'\1vxtwitter.com', msg.content)

            await self.send_webhook_message(
                msg.channel,
                msg,
                vxtwitter_url
            )
        pixiv_url = r'(https?://(?:www\.)?)pixiv\.net'
        if re.search(pixiv_url, msg.content):
            phixiv_url = re.sub(pixiv_url, r'\1phixiv.net', msg.content)

            await self.send_webhook_message(
                msg.channel,
                msg,
                phixiv_url
            )







async def setup(
        bot: commands.Bot
):
    ext = VxLinks(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
