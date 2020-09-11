from peewee import *
from datetime import datetime

DB = "data/bot.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class BotBlacklist(BaseModel):
    guild = IntegerField()
    user = IntegerField(primary_key=True)
    meta = CharField()
    when = DateTimeField(default=datetime.utcnow)


class BotBanlist(BaseModel):
    guild = IntegerField()
    user = IntegerField(primary_key=True)
    meta = CharField()
    when = DateTimeField(default=datetime.utcnow)


# db.drop_tables([BotBlacklist, BotBanlist])
db.create_tables([BotBlacklist, BotBanlist])
