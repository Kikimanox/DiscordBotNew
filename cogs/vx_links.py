import re

from discord import Message, Webhook, Thread, Reaction, User, Member
from discord.ext import commands

from typing import Dict, Union


class VxLinks(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot

        self.user_webhooks_ownership: Dict[int, int] = {}


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
        msg = f"{content}\n{replied_message.jump_url}"
        
        await replied_message.edit(suppress=True)

        if isinstance(channel, Thread):
            webhook_message = await webhook.send(
                msg,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                thread= channel,
                wait=True
            )
        else:
            webhook_message = await webhook.send(
                msg,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                wait=True
            )

        self.user_webhooks_ownership.update({webhook_message.id: replied_message.author.id})




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

    @commands.Cog.listener()
    async def on_reaction_add(
            self,
            reaction: Reaction,
            user: Union[User, Member]
    ):
        if reaction.message.id in self.user_webhooks_ownership.keys():
            if user.id == self.user_webhooks_ownership[reaction.message.id]:
                if reaction.emoji == "❌":
                    await reaction.message.delete()
                    self.user_webhooks_ownership.pop(reaction.message.id)







async def setup(
        bot: commands.Bot
):
    ext = VxLinks(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
