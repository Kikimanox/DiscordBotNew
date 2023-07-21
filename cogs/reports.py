import json
import logging
import logging.handlers as handlers
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

import discord
from discord.ext import commands
from prettytable import PrettyTable
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    PrimaryKeyConstraint,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.session import Session

from utils.checks import ban_members_check, dev_check
from utils.dataIOa import dataIOa
from utils.tools import get_user_avatar_url, result_printer, get_text_channel

DEFAULT_TRUST_SCORE = 2
DEFAULT_REPORT_ESCALATION_THRESHOLD = 3
REPORTS_JSON = "data/reports.json"
ESCALATION_REPORT_STR = "Escalated Report"

REPORTS_ENABLED = "reports_enabled"
REPORTS_CHANNEL = "reports_channel"
REPORTS_CHANNEL_OVERRIDES = "reports_channel_overrides"
REPORTS_CATEGORY_OVERRIDES = "reports_category_overrides"
REPORTS_EMOJI = "reports_emoji"
REPORTS_INFO_MSG = "reports_info_msg"
REPORTS_ESCALATION_THRESHOLD = "reports_escalation_threshold"
STARTING_TRUST_SCORE = "starting_trust_score"
TRUST_SCORE_WEIGHT = "trust_score_weight"
TRUST_SCORE_SCALE = "trust_score_scale"
VALID_REPORT_MSG_MAX_AGE = "valid_report_msg_max_age"

REPORTS_JSON_GUILD_DEFAULTS = {
    REPORTS_ENABLED: True,
    REPORTS_CHANNEL: None,
    REPORTS_CHANNEL_OVERRIDES: {},
    REPORTS_CATEGORY_OVERRIDES: {},
    REPORTS_EMOJI: "📝",
    REPORTS_INFO_MSG: None,
    REPORTS_ESCALATION_THRESHOLD: DEFAULT_REPORT_ESCALATION_THRESHOLD,
    STARTING_TRUST_SCORE: DEFAULT_TRUST_SCORE,
    # Trusted users can weigh their reporters to count more towards the report count, up to a max of REPORT_ESCALATION_THRESHOLD.
    # In other words, the highest trusted users can escalate a report with just their report.
    TRUST_SCORE_WEIGHT: {0: 0, 2: 1, 5: 2, 8: DEFAULT_REPORT_ESCALATION_THRESHOLD},
    TRUST_SCORE_SCALE: (0, 10),
    VALID_REPORT_MSG_MAX_AGE: 3600 * 24 * 7,
}

REPORTS_DB_PATH = "data/reports.db"
REPORTS_TABLE_NAME = "report_table"
USER_TRUST_TABLE_NAME = "user_trust_table"


Base = declarative_base()


class AcknowledgementLevel(Enum):
    NO_ACK = 0
    GOOD_ACK = 1
    BAD_ACK = 2


class EscalationReason(Enum):
    SCORE_THRESHOLD = "score threshold"
    DELETED_MESSAGE = "deleted message"
    BOT_REACT_BLOCKED = "bot react blocked"


class ReportLog(Base):
    __tablename__ = "report_table"
    message_id = Column(Integer, primary_key=True)
    channel_id = Column(Integer)
    guild_id = Column(Integer)
    user_id = Column(Integer)
    report_count = Column(Integer)
    report_score = Column(Integer)
    first_reporter = Column(Integer)
    reporters = Column(String)
    escalated = Column(Boolean)
    acknowledged = Column(Integer)
    timestamp = Column(Integer)


class TrustedUsers(Base):
    __tablename__ = "user_trust_table"
    __table_args__ = (PrimaryKeyConstraint("guild_id", "user_id"),)
    guild_id = Column(Integer)
    user_id = Column(Integer)
    report_count = Column(Integer)
    trust_score = Column(Integer)
    last_report_timestamp = Column(Integer)


os.makedirs("data", exist_ok=True)
engine = create_engine("sqlite:///data/reports.db")


class Reports(commands.Cog):
    """
    Reporting system.
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.report_logger = logging.getLogger("reports")
        self.report_logger.setLevel(logging.INFO)

        # log formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logHandler = handlers.RotatingFileHandler(
            "logs/info/reports.log", maxBytes=500000, backupCount=10, encoding="utf-8"
        )
        logHandler.setLevel(logging.INFO)
        logHandler.setFormatter(formatter)

        # fixes bug when bot restarted but log file retained loghandler. this will remove any handlers it already had and replace with new ones initialized above
        for hdlr in list(self.report_logger.handlers):
            self.report_logger.removeHandler(hdlr)
        self.report_logger.addHandler(logHandler)

        if not os.path.exists(REPORTS_JSON):
            with open(REPORTS_JSON, "w") as fp:
                json.dump({}, fp, indent=4)
        self.reports_json = dataIOa.load_json(REPORTS_JSON)

        self.Session = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Username: {0.name}\nID: {0.id}".format(self.bot.user))

    def ensure_reports_configured(self, guild_id: int) -> bool:
        if str(guild_id) not in self.reports_json:
            self.reports_json[str(guild_id)] = REPORTS_JSON_GUILD_DEFAULTS
            dataIOa.save_json(REPORTS_JSON, self.reports_json)

    def get_reports_setting(self, guild_id: int, key: str) -> Dict[str, Any]:
        guild_id_str = str(guild_id)
        self.ensure_reports_configured(guild_id)
        return self.reports_json[guild_id_str].get(key)

    def update_reports_setting(
        self, guild_id: int, parameter: str, value: Any
    ) -> Dict[str, Any]:
        guild_id_str = str(guild_id)
        self.ensure_reports_configured(guild_id)
        self.reports_json[guild_id_str][parameter] = value
        dataIOa.save_json(REPORTS_JSON, self.reports_json)
        return self.reports_json[guild_id_str]

    @commands.group(aliases=["ru"])
    @commands.check(ban_members_check)
    async def reportsutils(self, ctx):
        """Reports admin settings."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    async def send_guild_settings(
        self, channel: discord.TextChannel, guild_settings: Dict[str, Any]
    ) -> None:
        await channel.send(
            f"Guild settings:\n```json\n{json.dumps(guild_settings, indent=4)}\n```"
        )

    @reportsutils.command()
    @commands.check(dev_check)
    async def trusted_users(self, ctx, count: int = 10):
        with self.Session() as session:
            users = (
                session.query(TrustedUsers)
                .filter_by(guild_id=ctx.guild.id)
                .order_by(
                    TrustedUsers.trust_score.desc(), TrustedUsers.report_count.desc()
                )
                .limit(count)
                .all()
            )
            table = PrettyTable()
            table.field_names = ["User", "Score", "Reports", "Last Report"]
            for user in users:
                user_obj = self.bot.get_user(user.user_id)
                if not user_obj:
                    user_obj = f"User not in guild (id: {user.user_id})"
                else:
                    user_obj = str(user_obj)
                table.add_row(
                    (
                        user_obj,
                        user.trust_score,
                        user.report_count,
                        datetime.fromtimestamp(user.last_report_timestamp).strftime(
                            "%c"
                        ),
                    )
                )
        return await result_printer(ctx, f"```\n{table}\n```")

    @reportsutils.command()
    @commands.check(ban_members_check)
    async def enable(self, ctx):
        """Enable and (if it doesn't exist) configure default admin reports settings for current guild."""
        guild_settings = self.update_reports_setting(
            ctx.guild.id, REPORTS_ENABLED, True
        )
        if not self.get_reports_setting(ctx.guild.id, REPORTS_CHANNEL):
            guild_settings = self.update_reports_setting(
                ctx.guild.id, REPORTS_CHANNEL, ctx.channel.id
            )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @reportsutils.command()
    @commands.check(ban_members_check)
    async def disable(self, ctx):
        """Disable admin reports settings for current guild."""
        guild_settings = self.update_reports_setting(
            ctx.guild.id, REPORTS_ENABLED, False
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @reportsutils.command(aliases=["v"])
    @commands.check(ban_members_check)
    async def view(self, ctx):
        """View admin reports settings for current guild."""
        guild_settings = self.reports_json.get(str(ctx.guild.id), False)
        if not guild_settings:
            return await ctx.send(
                f"This guild has not been configured to use the reporting system. Enable and configure with the `{ctx.prefix}ru enable`"
            )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @reportsutils.group(aliases=["e"])
    @commands.check(ban_members_check)
    async def edit(self, ctx) -> None:
        """Edit admin reports settings. [p]help ru edit for all settings options."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @edit.command()
    @commands.check(ban_members_check)
    async def reports_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where escalated reports appear in."""
        self.ensure_reports_configured(ctx.guild.id)
        guild_settings = self.update_reports_setting(
            ctx.guild.id, REPORTS_CHANNEL, channel.id
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    async def mapping_add(
        self, ctx, reports_setting: str, key: str, value: Any
    ) -> None:
        self.ensure_reports_configured(ctx.guild.id)
        reports_channel_overrides = self.get_reports_setting(
            ctx.guild.id, reports_setting
        )
        reports_channel_overrides[key] = value
        guild_settings = self.update_reports_setting(
            ctx.guild.id, reports_setting, reports_channel_overrides
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    async def mapping_remove(self, ctx, reports_setting: str, key: str) -> None:
        self.ensure_reports_configured(ctx.guild.id)
        reports_channel_overrides = self.get_reports_setting(
            ctx.guild.id, reports_setting
        )
        if key in reports_channel_overrides:
            del reports_channel_overrides[key]
            guild_settings = self.update_reports_setting(
                ctx.guild.id, reports_setting, reports_channel_overrides
            )
            await self.send_guild_settings(ctx.channel, guild_settings)
        else:
            await ctx.send(f"Can't remove `{key}`. Not found in mapping.")

    @edit.group()
    @commands.check(ban_members_check)
    async def reports_channel_overrides(self, ctx):
        """Set a different channel for escalated reports for a given channel."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @reports_channel_overrides.command(aliases=["add", "a"])
    @commands.check(ban_members_check)
    async def add_(
        self, ctx, channel: discord.TextChannel, reports_channel: discord.TextChannel
    ):
        """Add a reports channel override. Ex: `[p]ru e reports_channel_override #general #channel-to-escalate-to`"""
        await self.mapping_add(
            ctx, REPORTS_CHANNEL_OVERRIDES, str(channel.id), reports_channel.id
        )

    @reports_channel_overrides.command(aliases=["remove", "r", "delete"])
    @commands.check(ban_members_check)
    async def remove_(self, ctx, channel: discord.TextChannel):
        """Remove a channel override."""
        await self.mapping_remove(ctx, REPORTS_CHANNEL_OVERRIDES, str(channel.id))

    @edit.group()
    @commands.check(ban_members_check)
    async def reports_category_overrides(self, ctx):
        """Set a different channel for escalated reports for a given category."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @reports_category_overrides.command(aliases=["add", "a"])
    @commands.check(ban_members_check)
    async def add__(self, ctx, category: int, reports_channel: discord.TextChannel):
        """Add a category. Ex: `[p]ru e reports_channel_override <category id> #channel-to-escalate-to`"""
        category_obj = discord.utils.get(ctx.guild.categories, id=category)
        if not category_obj:
            return await ctx.send(f"The specified category could not be found.")
        await self.mapping_add(
            ctx, REPORTS_CATEGORY_OVERRIDES, str(category_obj.id), reports_channel.id
        )

    @reports_category_overrides.command(aliases=["remove", "r", "delete"])
    @commands.check(ban_members_check)
    async def remove__(self, ctx, category: str):
        """Remove a category override."""
        await self.mapping_remove(ctx, REPORTS_CATEGORY_OVERRIDES, category)

    @edit.command()
    @commands.check(ban_members_check)
    async def reports_emoji(self, ctx, emoji: str):
        """Set the emoji used for reporting."""
        self.ensure_reports_configured(ctx.guild.id)
        if emoji.startswith("<") and emoji.endswith(">"):
            emoji = int(emoji[:-1].rsplit(":", 1)[1])
        guild_settings = self.update_reports_setting(ctx.guild.id, REPORTS_EMOJI, emoji)
        await self.send_guild_settings(ctx.channel, guild_settings)

    @edit.command()
    @commands.check(ban_members_check)
    async def reports_info_msg(self, ctx, url: str = None):
        """Set the link to the message detailing the reporting system. Can be any url. Leave empty to remove."""
        self.ensure_reports_configured(ctx.guild.id)
        guild_settings = self.update_reports_setting(
            ctx.guild.id, REPORTS_INFO_MSG, url
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @edit.command()
    @commands.check(ban_members_check)
    async def reports_escalation_threshold(self, ctx, threshold: int):
        """Set the minimum score for reports (based on sum of reporters trust score) before the report is escalated to the reports channel."""
        self.ensure_reports_configured(ctx.guild.id)
        guild_settings = self.update_reports_setting(
            ctx.guild.id, REPORTS_ESCALATION_THRESHOLD, threshold
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @edit.command()
    @commands.check(ban_members_check)
    async def starting_trust_score(self, ctx, score: int):
        """Set the default trust score that any reporter starts with. Must be in bounds of `trust_score_scale`."""
        self.ensure_reports_configured(ctx.guild.id)
        trust_score_scale = self.get_reports_setting(ctx.guild.id, TRUST_SCORE_SCALE)
        if score >= trust_score_scale[0] and score <= trust_score_scale[1]:
            guild_settings = self.update_reports_setting(
                ctx.guild.id, STARTING_TRUST_SCORE, score
            )
            await self.send_guild_settings(ctx.channel, guild_settings)
        else:
            await ctx.send(
                f"Invalid starting trust score. Trust score must be within the bounds set for the trust_score_scale (Currently set as: `{trust_score_scale}`)"
            )

    @edit.command()
    @commands.check(ban_members_check)
    async def trust_score_scale(self, ctx, min_trust_score: int, max_trust_score: int):
        """Set the minimum and maximum trust a user can attain. Do not modify unless you know exactly what you're doing."""
        self.ensure_reports_configured(ctx.guild.id)
        guild_settings = self.update_reports_setting(
            ctx.guild.id, TRUST_SCORE_SCALE, (min_trust_score, max_trust_score)
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @edit.group()
    @commands.check(ban_members_check)
    async def trust_score_weight(self, ctx):
        """Set the thresholds for trust score to report weight conversion. Do not modify unless you know exactly what you're doing."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @trust_score_weight.command(aliases=["a"])
    @commands.check(ban_members_check)
    async def add(self, ctx, trust_score: int, report_weight: int):
        """Add a threshold."""
        self.ensure_reports_configured(ctx.guild.id)
        trust_score_weight = self.get_reports_setting(ctx.guild.id, TRUST_SCORE_WEIGHT)
        trust_score_scale = self.get_reports_setting(ctx.guild.id, TRUST_SCORE_SCALE)
        if trust_score >= trust_score_scale[0] and trust_score <= trust_score_scale[1]:
            trust_score_weight[str(trust_score)] = report_weight
            guild_settings = self.update_reports_setting(
                ctx.guild.id, TRUST_SCORE_WEIGHT, trust_score_weight
            )
            await self.send_guild_settings(ctx.channel, guild_settings)
        else:
            await ctx.send(
                f"Invalid trust score mapping. Trust score must be within the bounds set for the trust_score_scale (Currently set as: `{trust_score_scale}`)"
            )

    @trust_score_weight.command(aliases=["r", "delete"])
    @commands.check(ban_members_check)
    async def remove(self, ctx, trust_score: int):
        """Remove a threshold."""
        self.ensure_reports_configured(ctx.guild.id)
        trust_score_weight = self.get_reports_setting(ctx.guild.id, TRUST_SCORE_WEIGHT)
        if str(trust_score) in trust_score_weight:
            del trust_score_weight[str(trust_score)]
            guild_settings = self.update_reports_setting(
                ctx.guild.id, TRUST_SCORE_WEIGHT, trust_score_weight
            )
            await self.send_guild_settings(ctx.channel, guild_settings)
        else:
            await ctx.send(
                f"Can't remove specified trust score mapping. No trust score found."
            )

    @edit.command()
    @commands.check(ban_members_check)
    async def valid_report_msg_max_age(self, ctx, age: int):
        """Set the maximum age of a message before it can no longer be reported. Set to 0 for no max age."""
        self.ensure_reports_configured(ctx.guild.id)
        guild_settings = self.update_reports_setting(
            ctx.guild.id, VALID_REPORT_MSG_MAX_AGE, age
        )
        await self.send_guild_settings(ctx.channel, guild_settings)

    @commands.command()
    async def report(self, ctx, channel: discord.TextChannel, message_id: int):
        await ctx.message.delete()
        try:
            message = await channel.fetch_message(message_id)
        except discord.errors.NotFound:
            await self.send_to_user(
                ctx.author,
                f"Message not found, could not file report. Ensure you have properly tagged the right channel and gotten the correct message id. Ex: `{ctx.prefix}report #general 754821521258327320`",
                None,
            )
        else:
            await self.handle_report(
                message,
                ctx.author.id,
                self.get_reports_setting(ctx.guild.id, REPORTS_EMOJI),
            )

    @staticmethod
    def get_reporters_list(report: ReportLog) -> List[int]:
        return [int(r) for r in report.reporters.split(",")]

    async def get_reports_channel(self, guild_id: int, channel_id: int) -> int:
        reports_channel_overrides = self.get_reports_setting(
            guild_id, REPORTS_CHANNEL_OVERRIDES
        )
        if str(channel_id) in reports_channel_overrides:
            return reports_channel_overrides[str(channel_id)]
        reports_category_overrides = self.get_reports_setting(
            guild_id, REPORTS_CATEGORY_OVERRIDES
        )
        category = (await get_text_channel(self.bot, channel_id))[1].category
        if category and str(category.id) in reports_category_overrides:
            return reports_category_overrides[str(category.id)]
        else:
            return self.get_reports_setting(guild_id, REPORTS_CHANNEL)

    def get_trusted_user(
        self, session: Session, guild_id: int, reporter_id: int
    ) -> TrustedUsers:
        user = (
            session.query(TrustedUsers)
            .filter_by(guild_id=guild_id, user_id=reporter_id)
            .first()
        )
        if not user:
            user = TrustedUsers(
                guild_id=guild_id,
                user_id=reporter_id,
                report_count=0,
                trust_score=DEFAULT_TRUST_SCORE,
                last_report_timestamp=0,
            )
            session.add(user)
            session.commit()
        return user

    def update_trust_score(
        self, user: TrustedUsers, guild_id: int, value: int
    ) -> TrustedUsers:
        trust_score_scale = self.get_reports_setting(guild_id, TRUST_SCORE_SCALE)
        trust_score = user.trust_score
        trust_score += value
        trust_score = max(min(trust_score, trust_score_scale[1]), trust_score_scale[0])
        user.trust_score = trust_score
        return user

    async def update_user_report_count(
        self, session: Session, guild_id: int, reporter_id: int
    ) -> None:
        user = self.get_trusted_user(session, guild_id, reporter_id)
        user.report_count += 1
        user.last_report_timestamp = datetime.utcnow().timestamp()

    async def send_escalated_report_msg(
        self,
        message: discord.Message,
        mod_channel_id: int,
        escalation_reason: EscalationReason,
    ) -> None:
        has_embed = "\n\n[Has Embed]" if message.embeds or message.attachments else ""
        if escalation_reason != EscalationReason.DELETED_MESSAGE.value:
            jump_to_msg_str = f"\n\n[Jump to message]({message.jump_url})"
        else:
            jump_to_msg_str = f"\n\nChannel: {message.channel.mention}"
        user_id = f"\nUser id: {message.author.id}"
        em = discord.Embed(
            color=0xBD0808,
            title=f"{ESCALATION_REPORT_STR} ({escalation_reason})",
            description=message.content[:1500]
            + f"{' ...' if len(message.content) > 1500 else ''}{has_embed}{jump_to_msg_str}{user_id}",
            timestamp=message.created_at,
        )
        em.set_author(
            name=str(message.author), icon_url=get_user_avatar_url(message.author)
        )
        em.set_footer(text=f"#{message.channel} | {message.id}")
        escalated_report_msg = await self.bot.get_channel(mod_channel_id).send(
            content=None, embed=em
        )
        await escalated_report_msg.add_reaction("✅")
        await escalated_report_msg.add_reaction("❌")

    def is_escalated(self, guild_id: int, report_score: int) -> bool:
        return report_score >= self.get_reports_setting(
            guild_id, REPORTS_ESCALATION_THRESHOLD
        )

    def log_report(self, message: discord.Message, reporter_id: int) -> None:
        self.report_logger.info(
            f"Reporter: {reporter_id} | Message author: {message.author.id} name: {message.author} | Message url: {message.jump_url}"
        )

    async def add_report(
        self,
        session: Session,
        report: ReportLog,
        reporter_id: int,
        message: discord.Message,
        *,
        auto_escalate: bool = False,
    ) -> ReportLog:
        guild_id = message.channel.guild.id
        trusted_user = self.get_trusted_user(session, guild_id, reporter_id)
        reporter_trust_score = trusted_user.trust_score
        trust_score_weight = self.get_reports_setting(
            message.channel.guild.id, TRUST_SCORE_WEIGHT
        )
        report_score = 0

        # Report count is a function of trust score. More trusted users can have more value set for their reports with an increment to the report count
        for trust_score in trust_score_weight:
            if reporter_trust_score >= int(trust_score):
                report_score = max(trust_score_weight[trust_score], report_score)

        # No report exists so create it
        if not report:
            is_escalated = (
                self.is_escalated(guild_id, report_score)
                if not auto_escalate
                else auto_escalate
            )
            report = ReportLog(
                message_id=message.id,
                channel_id=message.channel.id,
                guild_id=guild_id,
                user_id=message.author.id,
                report_count=1,
                report_score=report_score,
                first_reporter=reporter_id,
                reporters=str(reporter_id),
                escalated=is_escalated,
                acknowledged=AcknowledgementLevel.NO_ACK.value,
                timestamp=datetime.utcnow().timestamp(),
            )
            session.add(report)
        else:
            report.report_count += 1
            report.report_score += report_score
            report.escalated = (
                self.is_escalated(guild_id, report.report_score)
                if not auto_escalate
                else auto_escalate
            )
            reporters = self.get_reporters_list(report)
            reporters.append(reporter_id)
            report.reporters = ",".join(str(r) for r in reporters)
        self.log_report(message, reporter_id)
        await self.update_user_report_count(
            session, message.channel.guild.id, reporter_id
        )
        session.commit()
        return report

    async def send_to_user(
        self, user: discord.User, msg: str, embed: discord.Embed
    ) -> None:
        try:
            await user.send(content=msg, embed=embed)
        except discord.errors.Forbidden:
            pass

    async def report_message(
        self, message: discord.Message, reporter_id: int, *, auto_escalate: bool = False
    ) -> None:
        guild_id = message.channel.guild.id
        mod_channel_id = await self.get_reports_channel(guild_id, message.channel.id)
        reporter_duser = self.bot.get_user(reporter_id)
        reports_info_msg = self.get_reports_setting(guild_id, REPORTS_INFO_MSG)
        if reports_info_msg:
            info_msg = f"\n\n[Reporting System Info]({reports_info_msg})"
        else:
            info_msg = ""
        default_ack_msg = f"✅ Your report for [this message]({message.jump_url}) has been submitted. Thank you for the report, please continue to help make this community a better place. :){info_msg}"
        default_ack_em = discord.Embed(
            color=0xBD0808, title="Report Filed", description=default_ack_msg
        )
        with self.Session() as session:
            report = session.query(ReportLog).filter_by(message_id=message.id).first()

            # No report exists so create it
            if not report:
                report = await self.add_report(
                    session, report, reporter_id, message, auto_escalate=auto_escalate
                )

            elif report.acknowledged == AcknowledgementLevel.GOOD_ACK.value:
                already_ackd_msg = f"This message has already been reported enough, leading to escalation and acknowlegment by the mods. Thank you for the report anyway and please continue to help make this community a better place. :)"
                already_ackd_em = discord.Embed(
                    title="Report Already Acknowledged", description=already_ackd_msg
                )
                return await self.send_to_user(reporter_duser, None, already_ackd_em)

            # Return if report has already been escalated or reporter has already reported this message
            elif report.escalated or str(reporter_id) in report.reporters.split(","):
                return await self.send_to_user(reporter_duser, None, default_ack_em)

            # Add reporter to this report log, recalculate report score to determine if past the escalation threshold
            else:
                report = await self.add_report(
                    session, report, reporter_id, message, auto_escalate=auto_escalate
                )

            if report.escalated:
                await self.send_escalated_report_msg(
                    message,
                    mod_channel_id,
                    EscalationReason.SCORE_THRESHOLD.value
                    if not auto_escalate
                    else EscalationReason.BOT_REACT_BLOCKED.value,
                )

        await self.send_to_user(reporter_duser, None, default_ack_em)

    async def handle_report(
        self,
        message: discord.Message,
        reporter_id: int,
        emoji: Union[discord.Emoji, str],
    ) -> None:
        # Ignore if self-react
        if message.author.id == reporter_id:
            return

        max_age = self.get_reports_setting(
            message.channel.guild.id, VALID_REPORT_MSG_MAX_AGE
        )
        if max_age == 0 or (
            datetime.utcnow().timestamp() - max_age <= message.created_at.timestamp()
        ):
            auto_escalate = False
            try:
                await message.add_reaction(emoji)
            except discord.errors.Forbidden:
                auto_escalate = True
            await message.remove_reaction(emoji, self.bot.get_user(reporter_id))
            await self.report_message(message, reporter_id, auto_escalate=auto_escalate)

    async def handle_report_ack(
        self, message: discord.Message, is_good_report: bool
    ) -> None:
        reporters_list = []
        with self.Session() as session:
            report = (
                session.query(ReportLog)
                .filter_by(
                    message_id=int(message.embeds[0].footer.text.rsplit("|")[1].strip())
                )
                .first()
            )
            if report and report.acknowledged == AcknowledgementLevel.NO_ACK.value:
                report.acknowledged = (
                    AcknowledgementLevel.GOOD_ACK.value
                    if is_good_report
                    else AcknowledgementLevel.BAD_ACK.value
                )
                reporters = session.query(TrustedUsers).filter(
                    TrustedUsers.user_id.in_(self.get_reporters_list(report)),
                    TrustedUsers.guild_id == message.channel.guild.id,
                )
                for reporter in reporters:
                    self.update_trust_score(
                        reporter, message.channel.guild.id, 1 if is_good_report else -1
                    )
                    if is_good_report:
                        reporters_list.append(reporter.user_id)
                session.commit()

            good_ack_notif_em = discord.Embed(
                color=0x2ECF2B,
                title="Report Acknowledged",
                description="A report filed by you was acknowledged by the mods. Mod action will be taken as necessary. Thanks for your help!",
            )
            for reporter_id in reporters_list:
                await self.send_to_user(
                    self.bot.get_user(reporter_id), None, good_ack_notif_em
                )
            await message.add_reaction("👌")

    async def get_ctx_from_esc_report(self, event, message):
        ctx = await self.bot.get_context(message)
        ctx.author = self.bot.get_user(event.user_id)
        return ctx

    async def invoke_audit_log(
        self, event: discord.RawReactionActionEvent, message: discord.Message
    ) -> None:
        if "Mod" in self.bot.cogs and hasattr(self.bot.cogs["Mod"], "get_audit_logs_msg"):
            user = self.bot.get_user(
                int(message.embeds[0].description.rsplit("User id:")[1].strip())
            )
            ctx = await self.get_ctx_from_esc_report(event, message)
            return await self.bot.cogs["Mod"].get_audit_logs_msg(ctx, 50, user, "all")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event: discord.RawReactionActionEvent) -> None:
        await self.bot.wait_until_ready()
        if not event.guild_id or event.user_id == self.bot.user.id:
            return
        elif str(event.guild_id) in self.reports_json and self.get_reports_setting(
            event.guild_id, REPORTS_ENABLED
        ):
            guild_reports_emoji = self.get_reports_setting(
                event.guild_id, REPORTS_EMOJI
            )
            if event.emoji.id == guild_reports_emoji or (
                not event.emoji.id and event.emoji.name == guild_reports_emoji
            ):
                channel, _ = await get_text_channel(self.bot, event.channel_id)
                message = await channel.fetch_message(event.message_id)
                await self.handle_report(message, event.user_id, event.emoji)
            elif event.emoji.name in ["✅", "❌"]:
                channel = (await get_text_channel(self.bot, event.channel_id))[1]
                if not channel.permissions_for(
                    channel.guild.get_member(event.user_id)
                ).manage_messages:
                    return
                message = await channel.fetch_message(event.message_id)
                if (
                    not message.embeds
                    or not message.embeds[0].title
                    or not message.embeds[0].title.startswith(ESCALATION_REPORT_STR)
                ):
                    return
                await self.handle_report_ack(message, event.emoji.name == "✅")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        await self.bot.wait_until_ready()
        if not isinstance(message.channel, discord.TextChannel):
            return
        if str(message.guild.id) in self.reports_json:
            with self.Session() as session:
                report = (
                    session.query(ReportLog).filter_by(message_id=message.id).first()
                )
                if report and not report.escalated:
                    await self.send_escalated_report_msg(
                        message,
                        (await self.get_reports_channel(message.guild.id, message.channel.id)),
                        EscalationReason.DELETED_MESSAGE.value,
                    )


async def setup(bot: discord.Client) -> None:
    reports = Reports(bot)
    await bot.add_cog(reports)
