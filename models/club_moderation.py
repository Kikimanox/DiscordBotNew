from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from discord import Message, utils
from peewee import (
    CharField,
    DatabaseError,
    DoesNotExist,
    ForeignKeyField,
    IntegerField,
    IntegrityError,
    Model,
    SqliteDatabase,
)
from models.database_field import DiscordLink, TimestampTzField
from models.club_name import Club

if sys.version_info >= (3, 11):
    from enum import StrEnum, auto
else:
    from enum import auto

    from backports.strenum import StrEnum

if TYPE_CHECKING:
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")

DB = "data/club_moderation.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class ClubActivities(StrEnum):
    CREATE = auto()
    PING = auto()
    JOIN = auto()
    LEAVE = auto()
    DELETE = auto()


class BaseModel(Model):
    class Meta:
        database = db


class ClubModeration(BaseModel):
    id = IntegerField(primary_key=True)


class DiscordLinkModel(BaseModel, DiscordLink):
    pass


class ClubHistory(BaseModel):
    id = IntegerField(primary_key=True)
    actions = CharField(
        choices=[(activities, activities) for activities in ClubActivities]
    )
    author_id = IntegerField()
    author_name = CharField()

    # from models.club_name import Club
    club_name = IntegerField()
    discord_link = ForeignKeyField(DiscordLinkModel, backref="link")
    history_datetime = TimestampTzField(default=datetime.now(tz=timezone.utc))

    @property
    def get_club_name(self) -> Club:
        return Club.get(id == self.club_name)

    @property
    def check_if_within_24_hours(self) -> bool:
        now = datetime.now(timezone.utc)
        old: datetime = self.history_datetime
        return now.day - old.day < 1

    @property
    def time_stamp(self):
        ts = utils.format_dt(self.history_datetime, style='R')
        return ts


db.create_tables([DiscordLinkModel, ClubHistory])


def save_join_or_leave_history(
        ctx: Context,
        name: str,
        join: bool
):
    club_action = ClubActivities.JOIN if join else ClubActivities.LEAVE
    club_name = Club.fetch_or_create(club_name=name)
    link = DiscordLinkModel.create(
        guild_id=ctx.guild.id,
        channel_id=ctx.channel.id,
        message_id=ctx.message.id
    )
    ClubHistory.create(
        author_id=ctx.author.id,
        author_name=ctx.author.name,
        club_name=club_name,
        actions=club_action,
        discord_link=link,
    )


def save_create_history(
        ctx: Context,
        name: str
):
    link = DiscordLinkModel.create(
        guild_id=ctx.guild.id,
        channel_id=ctx.channel.id,
        message_id=ctx.message.id
    )
    club_name = Club.fetch_or_create(club_name=name)
    ClubHistory.create(
        author_id=ctx.author.id,
        author_name=ctx.author.name,
        club_name=club_name,
        actions=ClubActivities.CREATE,
        discord_link=link,
    )


def save_delete_history(
        ctx: Context,
        name: str
):
    link = DiscordLinkModel.create(
        guild_id=ctx.guild.id,
        channel_id=ctx.channel.id,
        message_id=ctx.message.id
    )
    club_name = Club.fetch_or_create(club_name=name)
    ClubHistory.create(
        author_id=ctx.author.id,
        author_name=ctx.author.name,
        club_name=club_name,
        actions=ClubActivities.DELETE,
        discord_link=link,
    )


def save_ping_history(
        ctx: Context,
        message: Message,
        name: str
):
    link = DiscordLinkModel.create(
        guild_id=ctx.guild.id,
        channel_id=ctx.channel.id,
        message_id=message.id,
    )
    club_name = Club.fetch_or_create(club_name=name)
    ClubHistory.create(
        actions=ClubActivities.PING,
        author_id=ctx.author.id,
        author_name=ctx.author.name,
        club_name=club_name,
        discord_link=link,
    )


def get_the_last_entry_from_club_name_from_guild(
        club_name: str,
        guild_id: int
) -> Optional[ClubHistory]:
    try:
        last_entry = ClubHistory.select().join(DiscordLinkModel). \
            switch(ClubHistory).join(Club).\
            where(Club.club_name == club_name and
                  DiscordLinkModel.guild_id == guild_id and
                  ClubHistory.actions == ClubActivities.PING
                  ).order_by(
            ClubHistory.id.desc()
        ).get()

        return last_entry
    except DoesNotExist:
        return None
    except IntegrityError:
        trace = traceback.format_exc()
        error_logger.error(trace)
        return None
    except DatabaseError:
        trace = traceback.format_exc()
        error_logger.error(trace)
        return None
