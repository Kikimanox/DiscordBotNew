"""
Mutes: id, guild, user, reason, length_str, expires_on
Actions: id, guild, reason, type, date, channel, msg_jump,
responsible, offender
"""

from peewee import *
from datetime import datetime

DB = "data/moderation.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Reminderstbl(BaseModel):
    id = AutoField()
    meta = CharField()
    expires_on = DateTimeField()
    executed_by = IntegerField(null=True)
    guild = IntegerField(null=True)
    reason = CharField(null=True)
    user_id = IntegerField(null=True)
    len_str = CharField(null=True)


class Actions(BaseModel):
    id = AutoField()
    case_id_on_g = IntegerField(default=-1)
    guild = IntegerField()
    channel = IntegerField()
    date = DateTimeField(default=datetime.utcnow)
    reason = CharField(null=True)
    responsible = IntegerField()
    offender = IntegerField(null=True)
    no_dm = BooleanField(default=True)
    user_display_name = CharField(null=True)
    type = CharField()  # mute, warn, ban(types) blacklist
    jump_url = CharField()
    logged_after = DateTimeField(null=True)
    logged_in_ch = IntegerField(null=True)


class Blacklist(BaseModel):
    guild = IntegerField()
    user_id = IntegerField()


# db.drop_tables([Reminderstbl, Actions, Blacklist, Mutes])
db.drop_tables([Reminderstbl])
db.create_tables([Reminderstbl, Actions, Blacklist])


class ModManager:
    @staticmethod
    def get_expired_mutes(gid):
        pass

    @staticmethod
    def return_blacklist_lists():
        bs = [q for q in Blacklist.select().dicts()]
        ret = {}
        for b in bs:
            if b['guild'] not in ret:
                ret[b['guild']] = []
            ret[b['guild']].append(int(b['user_id']))
        for k, v in ret.items():
            ret[k] = list(set(v))
        return ret
