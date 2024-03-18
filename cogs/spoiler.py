import discord
from discord import Interaction, Message, app_commands
from discord.ext import commands


class Spoiler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.spoiler_menu = app_commands.ContextMenu(
            name="spoiler", callback=self.spoiler_tag
        )
        self.bot.tree.add_command(self.spoiler_menu)

    async def cog_load(self):
        guilds = self.bot.guilds
        for guild in guilds:
            print(f"guild {guild.name} {guild.id}")
            channels = guild.text_channels + guild.forums
            for channel in channels:
                print(f"channel {channel.name} {channel.id}")
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    if webhook.name == "spoilerme" and webhook.user == self.bot.user:
                        await webhook.delete()

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self.spoiler_menu.name, type=self.spoiler_menu.type
        )

    async def create_or_get_webhook(self, channel):
        if isinstance(channel, discord.Thread):
            channel = channel.parent
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            if webhook.name == self.bot.user.name:
                return webhook
        return await channel.create_webhook(
            name="spoilerme",
        )

    async def spoiler_tag(self, interaction: Interaction, message: Message):
        await interaction.response.defer(ephemeral=True)
        content = message.content
        channel = message.channel
        name = message.author.display_name
        webhook = await self.create_or_get_webhook(channel)
        if isinstance(channel, (discord.Thread, discord.ForumChannel)):
            thread = channel
            wait = True
            await webhook.send(
                content=f"||{content}||",
                username=name,
                avatar_url=message.author.display_avatar.url,
                allowed_mentions=message.mentions,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
                thread=thread,
                wait=wait,
            )
        else:
            thread = None
            wait = False
            await webhook.send(
                content=f"||{content}||",
                username=name,
                avatar_url=message.author.display_avatar.url,
                allowed_mentions=message.mentions,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

        await message.delete()
        await interaction.followup.send(
            content=f"{message.author.mention} sent a spoiler",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    ext = Spoiler(bot)
    await bot.add_cog(ext)
