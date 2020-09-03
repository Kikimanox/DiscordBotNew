# cmdID cmdname, cnt, color, image, raw, created_on, author
# guildID
from peewee import *
from datetime import datetime

DB = "data/cmds.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Guild(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()


class Command(BaseModel):
    created_on = DateTimeField(default=datetime.utcnow)
    author = IntegerField()
    name = CharField()
    content = CharField()
    color = CharField(null=True)
    raw = BooleanField()
    image = BooleanField(default=False)


class CommandsToGuild(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    command = ForeignKeyField(Command, on_delete="CASCADE")

    class Meta:
        indexes = (
            (('guild', 'command'), True),
        )


# db.drop_tables([Guild, Command, CommandsToGuild])
db.create_tables([Guild, Command, CommandsToGuild])


class CmdsManager:
    @staticmethod
    def create_and_get_guild_if_not_exists(gid, name):
        try:
            guild = Guild.get(Guild.id == gid)
        except:
            guild = Guild.create(id=gid, name=name)
        return guild

    @staticmethod
    def get_cmd_based_on_guld(gid, name):
        q = (Command.select()
             .join(CommandsToGuild)
             .where(CommandsToGuild.guild == gid)
             .where(Command.name == name))
        if len(q) != 1:
            return None
        return q[0]
