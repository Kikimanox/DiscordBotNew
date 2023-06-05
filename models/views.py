from typing import Optional, List, Union

import discord
from discord import ButtonStyle, Interaction, ui, Member, User
from discord.ui import View, Button, Select
from discord import SelectOption


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
