from __future__ import annotations
from email.policy import default

import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from models.database_field import TimestampTzField
from models.club_moderation import ClubHistory
from models.club_name import Club

from peewee import (
    CharField,
    ForeignKeyField,
    IntegerField,
    BooleanField,
    Model,
    SqliteDatabase,
)

if sys.version_info >= (3, 11):
    from enum import StrEnum, auto
else:
    from enum import auto

    from backports.strenum import StrEnum

if TYPE_CHECKING:
    from utils.context import Context

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")

DB = "data/club_data.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class MemberType(StrEnum):
    Admin = auto()
    Moderator = auto()
    Member = auto()


class ClubStatus(StrEnum):
    Approved = auto()
    Pending = auto()
    Denied = auto()
    Deleted = auto()


class BaseModel(Model):
    class Meta:
        database = db


class ClubMemberStatus(BaseModel):
    id = IntegerField(primary_key=True)
    member_status = BooleanField(default=True)
    update_status_datetime = TimestampTzField(
        default=datetime.now(tz=timezone.utc))


class ClubMembers(BaseModel):
    id = IntegerField(primary_key=True)
    author_id = IntegerField()
    author_name = CharField()
    member_status = ForeignKeyField(ClubMemberStatus, backref="status")
    member_type = CharField(
        choices=[(member_type, member_type) for member_type in MemberType],
        default=MemberType.Member
    )


class ClubDataModel(BaseModel):
    id = IntegerField(primary_key=True)
    guild_id = IntegerField()
    # from models.club_name import Club
    club_name = IntegerField()

    image_banner_url = CharField(default=None, null=True)
    description = CharField(default=None, null=True)
    members = ForeignKeyField(ClubMembers)
    club_status = CharField(
        choices=[(status, status) for status in ClubStatus],
        default=ClubStatus.Pending
    )
    created = TimestampTzField(default=datetime.now(tz=timezone.utc))

    # from models.club_moderation import ClubHistory
    history = IntegerField()


    @property
    def get_club_name(self) -> Club:
        return Club.get(id == self.club_name)
    
    @property
    def get_history(self) -> ClubHistory:
        return ClubHistory.get(id == self.history)


db.create_tables([ClubMemberStatus, ClubMembers, ClubDataModel])



def create_club(
        ctx: Context,
        name: str,
        description: Optional[str] = None,
        image_banner_url: Optional[str] = None
):
    club_member_status = ClubMemberStatus.create()
    club_member = ClubMembers.create(
        author_id=ctx.author.id,
        author_name=ctx.author.name,
        member_status=club_member_status,
        member_type=MemberType.Admin
    )
    club_name = Club.fetch_or_create(club_name=name)
    ClubDataModel.create(
        guild_id=ctx.guild.id,
        club_name=club_name,
        image_banner_url=image_banner_url,
        description=description,
        members=club_member
    )


def update_club_status(
        ctx: Context,
        club_name: str,
        status: ClubStatus
):
    ClubDataModel.update(
        club_status=status
    ).join(Club).where(
        ClubDataModel.guild_id == ctx.guild.id and Club.club_name == club_name
    ).execute()

