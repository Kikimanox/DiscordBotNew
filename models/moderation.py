"""
Mutes: id, guild, user, reason, length_str, expires_on
Actions: id, guild, reason, type, date, channel, msg_jump,
responsible, offended
"""

from peewee import *
from datetime import datetime

DB = "data/moderation.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Mutes(BaseModel):
    guild = IntegerField()
    reason = CharField()
    user_id = IntegerField()
    len_str = CharField()
    expires_on = DateTimeField()
    muted_by = IntegerField()


class Actions(BaseModel):
    guild = IntegerField()
    channel = IntegerField()
    date = DateTimeField(default=datetime.utcnow)
    reason = CharField()
    responsible = IntegerField()
    offended = IntegerField()
    type = CharField()  # mute, warn, ban(types) blacklist
    jump_url = CharField()


class Blacklist(BaseModel):
    guild = IntegerField()
    user_id = IntegerField()


db.drop_tables([Mutes, Actions, Blacklist])
db.create_tables([Mutes, Actions, Blacklist])


class ModManager:
    @staticmethod
    def get_expired_mutes(gid):
        pass
