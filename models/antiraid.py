from peewee import *
from datetime import datetime

DB = "data/antiraid.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class ArGuild(BaseModel):
    id = IntegerField(primary_key=True)
    perma_locked_channels = CharField(default="")
    anti_raid_level = IntegerField(default=0)
    # todo: more fields?


db.drop_tables([ArGuild])
db.create_tables([ArGuild])


class ArManager:
    @staticmethod
    def get_ar_data():
        ret = {}
        gs = [q for q in ArGuild.select().dicts()]
        for g in gs:
            ret[g['id']] = g

        return ret
