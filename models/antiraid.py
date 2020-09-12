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
    # todo: on bot restart check somewhere for raid level


db.create_tables([ArGuild])
