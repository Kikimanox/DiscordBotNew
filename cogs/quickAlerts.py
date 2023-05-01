import datetime
import logging
import traceback

import discord
from discord import Embed
from discord.ext import commands

import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils

from models.quickAlerts import QuickAlerts
from models.views import AlertSelectMenuView

logger = logging.getLogger(f"info")
error_logger = logging.getLogger(f"error")


def get_human_readable_timedelta(seconds):
    # Calculate time components
    years, remainder = divmod(seconds, 31536000)
    months, remainder = divmod(remainder, 2592000)
    days, remainder = divmod(remainder, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format the string
    time_str = f"{int(years)} years, " if years else ""
    time_str += f"{int(months)} months, " if months else ""
    time_str += f"{int(days)} days, " if days else ""
    time_str += f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

    return time_str


class QuickAlertsC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # move this out of the code somewhere ~~someday~~
        self.__alerts_data = {
            123: {
                "alert_emoji_id": 123,  # emoji id that will trigger the reaction
                "alerts_target_channel": 123,  # where the alert will be posted
                "alerts_ping_role": 123  # which role will be pinged upon posting
            },
            202845295158099980: {
                "alert_emoji_id": 1100530861960597664,  # :Alert:
                "alerts_target_channel": 792875906401566750,  # #spam
                "alerts_ping_role": 658793130560061460  # ---Anchor1
            }
        }
        self.alerts_data = {}
        bot.loop.create_task(self.set_setup())

    async def set_setup(self):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
        logger.info("Loaidng alerts data")
        try:
            for k, v in self.__alerts_data.items():
                g = self.bot.get_guild(k)
                if not g:
                    error_logger.error(f'While loading QuickAlers: guild {k} not found')
                    continue
                emoji = discord.utils.get(g.emojis, id=v["alert_emoji_id"])
                if not emoji:
                    error_logger.error(f'While loading QuickAlers: emoji {v["alert_emoji_id"]} not found')
                    continue
                ch = g.get_channel(v["alerts_target_channel"])
                if not ch:
                    error_logger.error(f'While loading QuickAlers: channel {v["alert_emoji_id"]} not found')
                    continue
                role = discord.utils.get(g.roles, id=v["alerts_ping_role"])
                if not role:
                    error_logger.error(f'While loading QuickAlers: channel {v["alert_emoji_id"]} not found')
                    continue
                self.alerts_data[k] = {
                    "alert_emoji_id": emoji,
                    "alerts_target_channel": ch,
                    "alerts_ping_role": role
                },

        except Exception as ex:
            error_logger.error(f"{ex}")
            # traceback.print_exc()
        logger.info("Alerts data loaded")

    @commands.command()
    async def test123(self, ctx):
        test_ch = 545660080184492046
        test_msg_id = 601379769283510272
        test_msg = await (ctx.guild.get_channel(test_ch)).fetch_message(test_msg_id)

    async def process_existing_alert(self, alert, target, emoji):
        try:
            alert_msg = await target.fetch_message(alert.target_embed_message_id)
        except:
            # embed doesn't exist anymore...
            alert.status = 1
            logger.info(f"Alert purged from db due to embed not existing anymore...")

        embed = alert_msg.embeds[0]
        footer = embed.footer.text
        reported_count = int(footer.split("Reported ")[1][:-1]) + 1
        embed.set_footer(text=f"Alert unsolved 🔃 | Reported {reported_count}x")
        await alert_msg.edit(embed=embed)

    async def create_new_alert(self, guild_id, event, msg, emoji, target, alert_role):
        message_str = await self.get_message_history_str(msg)
        embed = self.create_alert_embed(msg, event, message_str)
        alert = QuickAlerts.create(
            alerted_message_id=event.message_id,
            alerted_message_ch_id=event.channel_id,
            alerted_user_id=msg.author.id,
            reportee_user_id=event.member.id,
            target_embed_message_id=0,
            status=0
        )
        view = AlertSelectMenuView(self.alerts_data, alert)
        alert_msg_sent = await target.send(content=f'{alert_role.mention}', embed=embed, view=view)
        alert.target_embed_message_id = alert_msg_sent.id
        alert.save()

    async def get_message_history_str(self, msg):
        messages = []
        async for message in msg.channel.history(limit=5, before=msg):
            messages.append(message)
        messages.reverse()

        message_str = ""
        for message in messages:
            content = message.content if message.content else f"[{len(message.attachments)} attachment(s) in msg]"
            if len(content) > 50:
                content = content[:50]
                content += "..."
            timestamp = message.created_at.strftime("%H:%M:%S")
            message_str += f"[{timestamp}] {message.author.display_name} ({message.author.id}): {content}\n"
        return message_str

    def create_alert_embed(self, msg, event, message_str):
        reacted_message_content = msg.content if msg.content else f"[{len(msg.attachments)} attachment(s) in msg]"
        if len(reacted_message_content) > 100:
            reacted_message_content = reacted_message_content[:100]
            reacted_message_content += "..."
        reacted_message_timestamp = msg.created_at.strftime("%H:%M:%S")
        message_str += f"**[{reacted_message_timestamp}] {msg.author.display_name} ({msg.author.id}): {reacted_message_content}**"

        embed = discord.Embed(title=f"ALERT ACTIVATED IN {msg.jump_url}", color=discord.Color.orange())
        embed.add_field(name="Context + Reported Message", value=f'{message_str}', inline=False)

        reported_user = msg.author
        reportee = event.member

        for user, user_title in [(reported_user, "⚠ Reported user info ⚠ 💀"), (reportee, "🗣 Reportee 🗣")]:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            account_age = (current_time - user.created_at).total_seconds()
            joined_server_age = (current_time - user.joined_at).total_seconds()

            account_age_str = get_human_readable_timedelta(account_age)
            joined_server_age_str = get_human_readable_timedelta(joined_server_age)

            user_info = f"Username: {user} | Nickname: {user.display_name}\n"
            user_info += f"Account age: **{account_age_str}**\n"
            user_info += f"Joined server: **{joined_server_age_str} ago**"
            embed.add_field(name=user_title, value=user_info, inline=False)

        embed.add_field(name="Moderator actions history", value="*No action history*", inline=False)
        embed.set_footer(text=f"Alert unsolved 🔃 | Reported 1x")
        embed.set_thumbnail(url=reported_user.display_avatar.url)
        return embed

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        if event.member.bot:
            return
        guild_id = event.guild_id
        if guild_id not in self.alerts_data:
            return
        emoji = self.alerts_data[guild_id][0]["alert_emoji_id"]
        target = self.alerts_data[guild_id][0]["alerts_target_channel"]
        alert_role = self.alerts_data[guild_id][0]["alerts_ping_role"]

        if event.emoji.id != emoji.id:
            return
        try:
            channel = self.bot.get_channel(event.channel_id)
            msg = await channel.fetch_message(event.message_id)

            # Remove the user's reaction and add the bot's reaction
            await msg.remove_reaction(emoji, event.member)
            await msg.add_reaction(emoji)

            # Check if the alert already exists in the DB
            alert = QuickAlerts.get_or_none(alerted_message_id=event.message_id, alerted_message_ch_id=event.channel_id)
            if alert:
                if alert.status == 1:  # alert status is 1 if it was already resolved
                    return
                await self.process_existing_alert(alert, target, emoji)
            else:
                await self.create_new_alert(guild_id, event, msg, emoji, target, alert_role)

        except Exception as ex:
            error_logger.error(f"Error when trying to make or create alert {ex}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        guild_id = message.guild.id
        if guild_id not in self.alerts_data:
            return
        alert = QuickAlerts.get_or_none(QuickAlerts.target_embed_message_id == message.id)
        if alert:
            alert.delete_instance()  # Delete the instance from the database
            logger.info(f"Alert with target_embed_message_id {message.id} deleted due to message deletion")


async def setup(bot: commands.Bot):
    ext = QuickAlertsC(bot)
    await bot.add_cog(ext)
