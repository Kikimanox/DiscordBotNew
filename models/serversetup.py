"""
Guild: id, muterole, modrole
Welcomemsg: id, content, desc, images, title, FK_GUILD
Logging: id, target_ch, type, FK_GUILD, FK_Hooks
Webhooks: id, url, id, target_ch, FK_GUILD, valid
"""

from peewee import *
from datetime import datetime

DB = "data/serversetup.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Guild(BaseModel):
    guild_id = IntegerField(primary_key=True)
    muterole = IntegerField(null=True)
    modrole = IntegerField(null=True)


class WelcomeMsg(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    content = CharField(null=True)
    desc = CharField(null=True)
    images = CharField(null=True)
    title = CharField(null=True)


class Webhook(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    hook_id = IntegerField(primary_key=True)
    url = CharField()
    target_ch = IntegerField()
    valid = BooleanField(default=True)


class Logging(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    hook = ForeignKeyField(Webhook, null=True)
    target_ch = IntegerField()
    type = CharField()  # reg, leavejoin, modlog


# db.drop_tables([Guild, WelcomeMsg, Logging])
db.create_tables([Guild, WelcomeMsg, Logging])


class SSManager:
    @staticmethod
    def get_all_data():
        pass
