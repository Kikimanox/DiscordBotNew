from peewee import (SqliteDatabase, Model, IntegerField, CharField, DoesNotExist,
                    IntegrityError, DatabaseError, Field)
from datetime import datetime, timezone
from discord import utils
from typing import Optional
import logging
import traceback

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")

DB = "data/club_moderation"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class TimestampTzField(Field):
    field_type = 'TEXT'

    def db_value(self, value: datetime) -> str:
        if value:
            return value.isoformat()

    def python_value(self, value: str) -> datetime:
        if value:
            return datetime.fromisoformat(value)


class BaseModel(Model):
    class Meta:
        database = db


class ClubModeration(BaseModel):
    id = IntegerField(primary_key=True)


class ClubPingHistory(BaseModel):
    id = IntegerField(primary_key=True)
    guild_id = IntegerField()
    channel_id = IntegerField()
    message_id = IntegerField()
    author_id = IntegerField()
    author_name = CharField()
    club_name = CharField()
    ping_datetime = TimestampTzField(default=datetime.now(tz=timezone.utc))

    @property
    def check_if_within_24_hours(self) -> bool:
        now = utils.utcnow()
        old: datetime = self.ping_datetime
        return now.day - old.day < 1

    @property
    def time_stamp(self):
        ts = utils.format_dt(self.ping_datetime, style='R')
        return ts


db.create_tables([ClubPingHistory])


def get_the_last_entry_from_club_name_from_guild(
        club_name: str,
        guild_id: int
) -> Optional[ClubPingHistory]:
    try:
        last_entry = ClubPingHistory.select().where(
            ClubPingHistory.club_name == club_name and
            ClubPingHistory.guild_id == guild_id
        ).order_by(
            ClubPingHistory.id.desc()
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
