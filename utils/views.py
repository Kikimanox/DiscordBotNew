from typing import Optional, List, Union

from discord import (ButtonStyle, Interaction, ui, Member, User, Emoji, PartialEmoji, SelectOption)
from discord.ui import View, Button


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

    async def callback(self, interaction: Interaction):
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


class ConfirmCancelView(View):
    def __init__(
            self,
            *,
            author: Optional[Union[User, Member]] = None,
            timeout: Optional[float] = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.value = None
        self.author = author
        self.author_click = None

    @ui.button(label="Yes", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: Button):
        self.value = True
        self.author_click = interaction.user.id
        self.confirm.disabled = True
        self.cancel.disabled = True
        self.stop()

    @ui.button(
        label="No",
        style=ButtonStyle.red,
    )
    async def cancel(self, interaction: Interaction, button: Button):
        self.value = False
        self.author_click = interaction.user.id
        self.confirm.disabled = True
        self.cancel.disabled = True
        self.stop()

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if self.author is None:
            return True
        else:
            if self.author.id != interaction.user.id:
                await interaction.response.send_message(
                    content=f"This command was invoked by {self.author.mention}. You cannot interact with it.",
                    ephemeral=True,
                    delete_after=300,
                )
                return False
            else:
                return True


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
                content=f"This command was invoked by {self.author.mention}. You cannot interact with it.",
                ephemeral=True,
                delete_after=300,
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
            if self.current_page is not None:
                self.current_page -= 1
        self.value = True
        self.stop()

    @ui.button(label=">", style=ButtonStyle.grey)
    async def next(self, interaction: Interaction, button: Button):
        if self.current_page == (self.num_of_pages - 1):
            self.current_page = 0
        else:
            if self.current_page is not None:
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


class DynamicButton(ui.Button):
    def __init__(
            self,
            *,
            style: ButtonStyle = ButtonStyle.secondary,
            value: Optional[Union[str, int, float]] = None,
            label: Optional[Union[str, int, float]] = None,
            disabled: bool = False,
            custom_id: Optional[str] = None,
            url: Optional[str] = None,
            emoji: Optional[Union[str, Emoji, PartialEmoji]] = None,
            row: Optional[int] = None,
    ):
        super().__init__(
            style=style,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )
        self.value: Optional[Union[str, int, float]] = value

        # Limit of the button number of characters
        self.label = f"{label}"[0:80]

    async def callback(self, interaction: Interaction):
        assert self.view is not None
        view: DynamicButtonView = self.view
        view.value = self.value
        view.stop()


class DynamicButtonView(ui.View):
    def __init__(
            self,
            *,
            author: Union[User, Member],
            timeout: Optional[float] = None,
            entries: List[Union[str, float, int]],
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.value: Optional[Union[str, float, int]] = None
        self.click_author: Optional[Union[User, Member]] = None

        row = -1
        for index, entry in enumerate(entries):
            column = index % 5
            if column == 0:
                row += 1
            if index >= 25:
                break
            if 0 <= index < len(entries):
                new_button = DynamicButton(
                    row=row, label=entry, value=entry, custom_id=f"button_{row}{column}"
                )
                self.add_item(new_button)
            else:
                break

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                content=f"This command was invoked by {self.author.mention}. "
                        "You cannot interact with it.",
                ephemeral=True,
                delete_after=300,
            )
            return False
        else:
            return True
