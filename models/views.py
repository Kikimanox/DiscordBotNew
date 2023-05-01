from typing import Optional, List, Union

import discord
from discord import ButtonStyle, Interaction, ui, Member, User
from discord.ui import View, Button, Select
from discord import SelectOption


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


class PaginationView(View):
    def __init__(
            self,
            author: Union[User, Member],
            clubs: List[str],
            current_page: int,
            timeout: Optional[float] = 60.0,

    ):
        super().__init__(timeout=timeout)

        self.author = author

        self.num_of_pages = len(clubs)
        self.current_page = current_page

        if self.current_page == (self.num_of_pages - 1) and self.num_of_pages == 1:
            self.first.disabled = True
            self.previous.disabled = True
            self.next.disabled = True
            self.last.disabled = True

        self.value = None

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                content="This command was not invoked by you so you cannot interact with it.",
                ephemeral=True,
                delete_after=300
            )
            return False
        else:
            return True

    @ui.button(label="<<", style=ButtonStyle.grey)
    async def first(self, interaction: Interaction, button: Button):
        if self.current_page == 0:
            self.current_page = self.num_of_pages - 1
        else:
            self.current_page = 0
        self.value = True
        self.stop()

    @ui.button(label="<", style=ButtonStyle.grey)
    async def previous(self, interaction: Interaction, button: Button):
        if self.current_page == 0:
            self.current_page = self.num_of_pages - 1
        else:
            self.current_page -= 1
        self.value = True
        self.stop()

    @ui.button(label=">", style=ButtonStyle.grey)
    async def next(self, interaction: Interaction, button: Button):
        if self.current_page == (self.num_of_pages - 1):
            self.current_page = 0
        else:
            self.current_page += 1
        self.value = True
        self.stop()

    @ui.button(label=">>", style=ButtonStyle.grey)
    async def last(self, interaction: Interaction, button: Button):
        if self.current_page == (self.num_of_pages - 1):
            self.current_page = 0
        else:
            self.current_page = self.num_of_pages - 1
        self.value = True
        self.stop()

    @ui.button(label="X")
    async def cancel(self, interaction: Interaction, button: Button):
        self.current_page = None
        self.value = None
        self.stop()


class AlertSelectMenuView(ui.View):
    def __init__(self, alerts_data, alert, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alerts_data = alerts_data
        self.alert = alert
        self.add_item(AlertSelectMenu(alerts_data, alert))


class AlertSelectMenu(ui.Select):
    def __init__(self, alerts_data, alert):
        self.alerts_data = alerts_data
        self.alert = alert
        options = [
            SelectOption(label="Only Delete Reported Message", emoji="🗑️", value="delete_message"),
            SelectOption(label="Warn Reportee For Pointless Report", emoji="😐", value="warn_reportee"),
            SelectOption(label="Ban User And Delete Reported Message", emoji="🔨", value="ban_user"),
            SelectOption(label="BANISH Reported User (7d msg history bye)", emoji="☠", value="banish_user"),
            SelectOption(label="View Attachements (if any exist) On Reported Message", emoji="🖼", value="see_att")
        ]

        super().__init__(placeholder="Quick Actions...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # You can use self.values to see which options were selected
        value = self.values[0]
        if value == "delete_message":
            pass
        elif value == "warn_reportee":
            pass
        elif value == "ban_user":
            pass
        elif value == "banish_user":
            pass
        elif value == "see_att":
            pass
