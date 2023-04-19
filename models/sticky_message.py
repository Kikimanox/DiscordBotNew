from peewee import *

DB = "data/sticky_messages.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class StickyMsg(BaseModel):
    id = IntegerField(primary_key=True)
    message = CharField()
    channel_id = IntegerField()
    guild_id = IntegerField()
    current_sticky_message_id = IntegerField()

# db.drop_tables([StickyMsg])
db.create_tables([StickyMsg])
