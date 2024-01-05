import re
from typing import Dict, Tuple, Union

from discord import Member, Message, Reaction, Thread, User, Webhook, WebhookMessage
from discord.ext import commands

import logging


logger = logging.getLogger('info')
error_logger = logging.getLogger('error')

twitter_url = r"(https?://(?:www\.)?)(twitter|x)\.com"
pixiv_url = r"(https?://(?:www\.)?)pixiv\.net"

class VxLinks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.user_webhooks_ownership: Dict[int, Tuple[int, WebhookMessage]] = {}
        self.message_tracker: Dict[int, WebhookMessage] = {}

    async def cog_load(self) -> None:
        guilds = self.bot.guilds
        for guild in guilds:
            channels = guild.text_channels + guild.forums + guild.voice_channels
            for channel in channels:
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    if webhook.name == "vxlinks" and webhook.user == self.bot.user:
                        await webhook.delete()
        logger.info("Finished checking all old webhooks")

    async def create_webhook(self, channel) -> Webhook:
        if isinstance(channel, Thread):
            channel = channel.parent

        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name == "vxlinks" and webhook.user == self.bot.user:
                return webhook
        return await channel.create_webhook(name="vxlinks")

    async def send_webhook_message(
        self, channel, replied_message: Message, content: str
    ):
        webhook = await self.create_webhook(channel)
        msg = f"{content}\n{replied_message.jump_url}"

        await replied_message.edit(suppress=True)

        if isinstance(channel, Thread):
            webhook_message = await webhook.send(
                msg,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                thread=channel,
                wait=True,
            )
        else:
            webhook_message = await webhook.send(
                msg,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                wait=True,
            )
        self.user_webhooks_ownership.update(
            {webhook_message.id: (replied_message.author.id, webhook_message)}
        )
        self.message_tracker.update({replied_message.id: webhook_message})

    @commands.Cog.listener()
    async def on_message(self, msg: Message):
        if re.search(twitter_url, msg.content) or re.search(pixiv_url, msg.content):

            twitter_content = re.sub(twitter_url, r"\1vxtwitter.com", msg.content)
            combine_content = re.sub(pixiv_url, r"\1phixiv.net", twitter_content)

            await self.send_webhook_message(msg.channel, msg, combine_content)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Union[User, Member]):
        if reaction.message.id in self.user_webhooks_ownership.keys():
            user_id, _ = self.user_webhooks_ownership[reaction.message.id]
            if user.id == user_id:
                if reaction.emoji == "❌":
                    await reaction.message.delete()
                    self.user_webhooks_ownership.pop(reaction.message.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if before.id in self.message_tracker.keys():
            webhook_message = self.message_tracker[before.id]
            update_content = f"{after.content}\n{before.jump_url}"

            update_content = re.sub(twitter_url, r"\1vxtwitter.com", update_content)
            update_content = re.sub(pixiv_url, r"\1phixiv.net", update_content)

            await webhook_message.edit(content=update_content)



async def setup(bot: commands.Bot):
    ext = VxLinks(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
