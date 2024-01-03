from discord.ext import commands
from discord import app_commands, Interaction, Message


class Spoiler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.spoiler_menu = app_commands.ContextMenu(
            name="spoiler",
            callback=self.spoiler_tag
        )
        self.bot.tree.add_command(self.spoiler_menu)

    async def cog_load(self):
        guilds = self.bot.guilds

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.spoiler_menu.name, type=self.spoiler_menu.type)

    async def spoiler_tag(self, interaction: Interaction, message: Message):
        await interaction.response.defer()
        content = message.content
        await message.delete()
        await interaction.followup.send(
            content=f"||{content}||",
        )


async def setup(bot: commands.Bot):
    ext = Spoiler(bot)
    await bot.add_cog(ext)
