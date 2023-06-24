from peewee import Field, IntegerField, Model
from datetime import datetime, timezone
from typing import Optional


# For Timezone aware datetime field

class TimestampTzField(Field):
    field_type = 'TEXT'

    def db_value(self, value: datetime) -> str:
        if value:
            return value.isoformat()
        else:
            return ''

    def python_value(self, value: str) -> Optional[datetime]:
        if value:
            return datetime.fromisoformat(value)
        else:
            return None

class DiscordLink(Model):
    id = IntegerField(primary_key=True)
    guild_id = IntegerField(null=True)
    channel_id = IntegerField(null=True)
    message_id = IntegerField(null=True)
    link_datetime = TimestampTzField(default=datetime.now(tz=timezone.utc))