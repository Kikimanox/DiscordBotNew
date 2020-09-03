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
    inherits_from = CharField(null=True)


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
    def get_or_create_and_get_guild(gid, name):
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

    @staticmethod
    def get_commands_formatted():
        cursor = db.execute_sql("select * from (SELECT * from guild inner join commandstoguild c "
                                "on guild.id = c.guild_id) as a inner join command cc on cc.id == a.command_id")
        columns = [column[0] for column in cursor.description]
        res = [dict(zip(columns, row)) for row in cursor.fetchall()]
        ret = {}
        for row in res:
            if row['guild_id'] not in ret: ret[row['guild_id']] = {'inh_cmd_list': [], 'inh_cmd_gids': None,
                                                                   'cmds': {}, 'cmds_name_list': [],
                                                                   'inh_cmds_name_list': []}
            ret[row['guild_id']]['cmds'][row['name']] = row
            if row['inherits_from']: ret[row['guild_id']]['inh_cmd_gids'] = row['inherits_from']

        for k, v in ret.items():
            if v['inh_cmd_gids']:
                for gid in v['inh_cmd_gids'].split(' '):
                    v['inh_cmd_list'].append(ret[int(gid)]['cmds'])
            for kk, c in v['cmds'].items():
                v['cmds_name_list'].append(kk)

            for vv in v['inh_cmd_list']:
                for cc in vv:
                    v['inh_cmds_name_list'].append(cc)

        return ret
