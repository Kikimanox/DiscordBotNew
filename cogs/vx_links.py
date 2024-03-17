import logging
import re
from typing import Dict, Tuple, Union
from urllib.parse import urlparse, urlunparse

from discord import (
    AllowedMentions,
    Member,
    Message,
    Reaction,
    Thread,
    User,
    Webhook,
    WebhookMessage,
)
from discord.ext import commands

LOGGER = logging.getLogger("info")
ERROR_LOGGER = logging.getLogger("error")

TWITTER_URL = r"(https?://(?:www\.)?)(twitter|x)\.com/\S*"
PIXIV_URL = r"(https?://(?:www\.)?)pixiv\.net/\S*"
REDDIT_URL = r"(https?://(?:www\.|old\.|new\.)?)reddit\.com/\S*"
TIKTOK_URL = r"(https?://(?:www\.|vt\.)?)tiktok\.com/\S*"

def remove_query_params(url):
    parsed = urlparse(url)
    # Reconstruct the URL without query parameters
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return clean_url

def convert_twitter_links_to_markdown(text):
    markdown_link_format = "[Tweet]({})"
    markdown_link_pattern = r'\[.*?\]\((.*?)\)'

    def replace_link(match):
        url = match.group(0)
        url = url.replace("twitter.com", "vxtwitter.com")
        url = url.replace("x.com", "vxtwitter.com")
        url = remove_query_params(url)
        return markdown_link_format.format(url)

    def replace_markdown_link(match):
        url = match.group(1)
        url = url.replace("twitter.com", "vxtwitter.com")
        url = url.replace("x.com", "vxtwitter.com")
        url = remove_query_params(url)
        return match.group(0).replace(match.group(1), url)


    text = re.sub(markdown_link_pattern, replace_markdown_link, text)
    text = re.sub(TWITTER_URL, replace_link, text)

    return text


def convert_pixiv_links_to_markdown(text):
    markdown_link_format = "[Pixiv]({})"
    markdown_link_pattern = r'\[.*?\]\((.*?)\)'

    def replace_link(match):
        url = match.group(0)
        url = url.replace("pixiv.net", "phixiv.net")
        url = remove_query_params(url)
        return markdown_link_format.format(url)

    def replace_markdown_link(match):
        url = match.group(1)
        url = url.replace("pixiv.net", "phixiv.net")
        url = remove_query_params(url)
        return match.group(0).replace(match.group(1), url)

    text = re.sub(markdown_link_pattern, replace_markdown_link, text)
    text = re.sub(PIXIV_URL, replace_link, text)

    return text

def convert_reddit_links_to_markdown(text):
    markdown_link_format = "[Reddit]({})"
    markdown_link_pattern = r'\[.*?\]\((.*?)\)'

    def replace_link(match):
        url = match.group(0)
        url = url.replace("reddit.com", "rxddit.com")
        url = remove_query_params(url)
        return markdown_link_format.format(url)

    def replace_markdown_link(match):
        url = match.group(1)
        url = url.replace("reddit.com", "rxddit.com")
        url = remove_query_params(url)
        return match.group(0).replace(match.group(1), url)

    text = re.sub(markdown_link_pattern, replace_markdown_link, text)
    text = re.sub(REDDIT_URL, replace_link, text)

    return text

def convert_tiktok_links_to_markdown(text):
    markdown_link_format = "[Tiktok]({})"
    markdown_link_pattern = r'\[.*?\]\((.*?)\)'

    def replace_link(match):
        url = match.group(0)
        url = url.replace("tiktok.com", "tnktok.com")
        url = remove_query_params(url)
        return markdown_link_format.format(url)

    def replace_markdown_link(match):
        url = match.group(1)
        url = url.replace("tiktok.com", "tnktok.com")
        url = remove_query_params(url)
        return match.group(0).replace(match.group(1), url)

    text = re.sub(markdown_link_pattern, replace_markdown_link, text)
    text = re.sub(TIKTOK_URL, replace_link, text)

    return text


class VxLinks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.user_webhooks_ownership: Dict[int, Tuple[int, WebhookMessage]] = {}
        self.message_tracker: Dict[int, WebhookMessage] = {}
        self.channels_list = [
            727951803521695795, # mengo-tweets
            727951886896070658, # onk-tweets
            705264951367041086, # raw-spoilers
        ]

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
        msg = f"{content}\n[Original Message]({replied_message.jump_url})"

        await replied_message.edit(suppress=True)

        if isinstance(channel, Thread):
            webhook_message = await webhook.send(
                msg,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                thread=channel,
                wait=True,
                allowed_mentions=AllowedMentions.none(),
            )
        else:
            webhook_message = await webhook.send(
                msg,
                username=replied_message.author.display_name,
                avatar_url=replied_message.author.display_avatar.url,
                wait=True,
                allowed_mentions=AllowedMentions.none(),
            )
        self.user_webhooks_ownership.update(
            {webhook_message.id: (replied_message.author.id, webhook_message)}
        )
        self.message_tracker.update({replied_message.id: webhook_message})

    @commands.Cog.listener()
    async def on_message(self, msg: Message):
        if msg.author.bot:
            return
        # Prevents the bot from sending messages in the vxlinks channels
        if msg.guild is not None:
            if msg.guild.id == 695200821910044783 and msg.channel.id in self.channels_list:
                return

        pattern = r'(?:[^<\|\[]|^)(https?://(?:www\.)?)(twitter\.com/[^/]+/status/\d+|x\.com/[^/]+/status/\d+|pixiv\.net|(old\.|new\.)?reddit\.com|tiktok\.com)(?:[^>\|\]]|$)'
        matches = re.search(pattern, msg.content)
        if matches:
            msg_content = convert_twitter_links_to_markdown(msg.content)
            msg_content = convert_pixiv_links_to_markdown(msg_content)
            msg_content = convert_reddit_links_to_markdown(msg_content)
            msg_content = convert_tiktok_links_to_markdown(msg_content)

            await self.send_webhook_message(msg.channel, msg, msg_content)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Union[User, Member]):
        if user.bot:
            return

        if reaction.message.id in self.user_webhooks_ownership.keys():
            user_id, _ = self.user_webhooks_ownership[reaction.message.id]
            if user.id == user_id:
                if reaction.emoji == "❌":
                    await reaction.message.delete()
                    self.user_webhooks_ownership.pop(reaction.message.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if before.author.bot:
            return

        if before.content == after.content:
            return
        if before.id in self.message_tracker.keys():
            webhook_message = self.message_tracker[before.id]

            if webhook_message.id not in self.user_webhooks_ownership.keys():
                return

            await after.edit(suppress=True)

            update_content = f"{after.content}\n[Original Message]({before.jump_url})"

            update_content = convert_twitter_links_to_markdown(update_content)
            update_content = convert_pixiv_links_to_markdown(update_content)
            update_content = convert_reddit_links_to_markdown(update_content)
            update_content = convert_tiktok_links_to_markdown(update_content)

            await webhook_message.edit(
                content=update_content,
                allowed_mentions=AllowedMentions.none(),
            )

    @commands.Cog.listener()
    async def on_message_delete(self, msg: Message):
        if msg.author.bot:
            return

        if msg.id in self.message_tracker.keys():
            webhook_message = self.message_tracker[msg.id]

            if webhook_message.id not in self.user_webhooks_ownership.keys():
                return

            await webhook_message.delete()
            self.user_webhooks_ownership.pop(webhook_message.id)
            self.message_tracker.pop(msg.id)


async def setup(bot: commands.Bot):
    ext = VxLinks(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
