from typing import Optional, List, Union

from discord import ButtonStyle, Interaction, ui, Member, User
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

        if self.current_page == 0 and self.num_of_pages > 1:
            self.first.disabled = True
            self.previous.disabled = True
            self.next.disabled = False
            self.last.disabled = False
        elif self.current_page == (self.num_of_pages - 1) and self.num_of_pages > 1:
            self.first.disabled = False
            self.previous.disabled = False
            self.next.disabled = True
            self.last.disabled = True
        elif self.current_page == (self.num_of_pages - 1) and self.num_of_pages == 1:
            self.first.disabled = True
            self.previous.disabled = True
            self.next.disabled = True
            self.last.disabled = True
        else:
            self.first.disabled = False
            self.previous.disabled = False
            self.next.disabled = False
            self.last.disabled = False

        self.value = None

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(content="You don't have permission to press this button.",
                                                    ephemeral=True, )
            return False
        else:
            return True

    @ui.button(label="First", style=ButtonStyle.green)
    async def first(self, interaction: Interaction, button: Button):
        self.current_page = 0
        self.value = True
        self.stop()

    @ui.button(label="Previous", style=ButtonStyle.green)
    async def previous(self, interaction: Interaction, button: Button):
        self.current_page -= 1
        self.value = True
        self.stop()

    @ui.button(label="Quit", style=ButtonStyle.red, )
    async def cancel(self, interaction: Interaction, button: Button):
        self.current_page = None
        self.value = None
        self.stop()

    @ui.button(label="Next", style=ButtonStyle.green)
    async def next(self, interaction: Interaction, button: Button):
        self.current_page += 1
        self.value = True
        self.stop()

    @ui.button(label="Last", style=ButtonStyle.green)
    async def last(self, interaction: Interaction, button: Button):
        self.current_page = self.num_of_pages - 1
        self.value = True
        self.stop()
