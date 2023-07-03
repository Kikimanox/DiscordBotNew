from __future__ import annotations

from discord.ui import View, Button, Select
from discord import Embed, Message, Interaction, ButtonStyle, ui
from typing import List, TYPE_CHECKING, Optional, Union
from discord.ui.item import Item

import logging

if TYPE_CHECKING:
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class MangaPaginationView(View):
    def __init__(
            self,
            ctx: Context,
            chapters: dict,
            chapter_number: int = 1,
            timeout: Union[float, None] = 300,
            page: int = 0,
    ):
        super().__init__(timeout=timeout)
        self.author = ctx.author
        self.message: Optional[Message] = None
        self.select: Optional[Select] = None
        self.chapter_number = chapter_number
        self.ctx = ctx

        self.clear_items()
        self.current_page = page
        self.chapters: dict = chapters

        self.embeds: List[Embed] = self.create_embeds()

        self.fill_items()

    async def start(self):

        self._update_labels(page_number=self.current_page)
        self.message = await self.ctx.send(
            embed=self.embeds[self.current_page],
            view=self
        )

    def create_embeds(self) -> List[Embed]:

        pages = self.chapters.get(f"{self.chapter_number}", None)
        if pages is None:
            return [
                Embed(
                    title="**Oshi No Ko**",
                    description="Stay tuned for the next released"
                )
            ]

        embeds = []

        for index, page in enumerate(pages):
            webpage_url = "https://mangasee123.com/read-online/Oshi-no-Ko-chapter-" \
                f"{self.chapter_number}-page-{index+1}.html"
            em = Embed(
                title="**Oshi No Ko**",
                description=f"[Link]({webpage_url}) | Ch: {self.chapter_number} | Page "
                f"{index+1}/{len(pages)}",
            )
            em.set_image(url=page)
            embeds.append(em)

        return embeds

    def fill_items(self):

        max_pages = len(self.embeds)

        use_last_and_first = max_pages is not None and max_pages >= 2

        if use_last_and_first:
            self.add_item(self.go_to_first_page)
        self.add_item(self.go_to_previous_page)
        self.add_item(self.go_to_current_page)
        self.add_item(self.go_to_next_page)

        if use_last_and_first:
            self.add_item(self.go_to_last_page)

        self.add_item(self.cancel_pages)

    async def go_to_chapter(self, interaction: Interaction, chapter_number: int):
        self.chapter_number = chapter_number
        self.current_page = 1
        self.embeds: List[Embed] = self.create_embeds()

        if interaction.response.is_done():
            if self.message:
                await self.message.edit(
                    embed=self.embeds[self.current_page],
                    view=self
                )
        else:
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page],
                view=self
            )

    async def go_to_page(self, interaction: Interaction, page_number: int):
        self.current_page = page_number

        self._update_labels(page_number=page_number)

        if interaction.response.is_done():
            if self.message:
                await self.message.edit(
                    embed=self.embeds[self.current_page],
                    view=self
                )
        else:
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page],
                view=self
            )

    def _update_labels(self, page_number: int):
        self.go_to_first_page.disabled = page_number == 0

        max_pages = len(self.embeds)

        # self.go_to_previous_page.label = "<"
        # self.go_to_next_page.label = ">"

        self.go_to_previous_page.label = f"{page_number}"
        self.go_to_current_page.label = f"{page_number + 1}"
        self.go_to_next_page.label = f"{page_number+2}"

        self.go_to_last_page.disabled = (page_number + 1) >= max_pages

        self.go_to_previous_page.disabled = False
        self.go_to_next_page.disabled = False

        if page_number == 0:
            self.go_to_previous_page.disabled = True
            self.go_to_previous_page.label = "..."
        if (page_number + 1) >= max_pages:
            self.go_to_next_page.disabled = True
            self.go_to_next_page.label = "..."

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if self.author.id != interaction.user.id:
            await interaction.response.send_message(
                content=f"This command was invoked by {self.author.mention}. "
                        "You cannot interact with it.",
                ephemeral=True,
                delete_after=300,
            )
            return False
        else:
            return True

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

    async def on_error(self, interaction: Interaction, error: Exception, item: Item):
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry',
                                            ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry',
                                                    ephemeral=True)

    @ui.button(label="<<", style=ButtonStyle.grey)
    async def go_to_first_page(self, interaction: Interaction, button: Button):
        await self.go_to_page(interaction, 0)

    @ui.button(label="<", style=ButtonStyle.grey)
    async def go_to_previous_page(self, interaction: Interaction, button: Button):
        await self.go_to_page(interaction, self.current_page - 1)

    @ui.button(label="Current", style=ButtonStyle.green, disabled=True)
    async def go_to_current_page(self, interaction: Interaction, button: Button):
        pass

    @ui.button(label=">", style=ButtonStyle.grey)
    async def go_to_next_page(self, interaction: Interaction, button: Button):
        await self.go_to_page(interaction, self.current_page + 1)

    @ui.button(label=">>", style=ButtonStyle.grey)
    async def go_to_last_page(self, interaction: Interaction, button: Button):
        max_pages = len(self.embeds)
        await self.go_to_page(interaction, max_pages - 1)

    @ui.button(label="❌", style=ButtonStyle.grey)
    async def cancel_pages(self, interaction: Interaction, button: Button):

        await interaction.response.edit_message(
            embed=self.embeds[self.current_page],
            view=None
        )

        self.stop()
