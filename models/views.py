from typing import Optional

from discord import ButtonStyle, Interaction, ui
from discord.ui import View, Button


class ConfirmCancelView(View):
    def __init__(self, *, timeout: Optional[float] = 60.0):
        super().__init__(timeout=timeout)
        self.value = None
        self.member_click = None

    @ui.button(label="Yes", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: Button):
        self.value = True
        self.member_click = interaction.user.name
        self.stop()

    @ui.button(label="No", style=ButtonStyle.red, )
    async def cancel(self, interaction: Interaction, button: Button):
        self.value = False
        self.member_click = interaction.user.name
        self.stop()
