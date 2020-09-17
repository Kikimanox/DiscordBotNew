from peewee import *
from datetime import datetime

DB = "data/claims.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db

class UserSettings(BaseModel):
    user = IntegerField()
    type = CharField()
    nsfw = CharField(default='default')  # off | default

class History(BaseModel):
    user = IntegerField()
    type = CharField()
    meta = CharField(default='{}')


class Claimed(BaseModel):
    id = AutoField()
    user = IntegerField()
    type = CharField()
    expires_on = DateTimeField(default=datetime.utcnow)
    char_name = CharField(null=True)
    img_url = CharField(null=True)
    color_string = CharField(null=True)
    is_nsfw = BooleanField(null=True)


# db.drop_tables([History, Claimed, UserSettings])
db.create_tables([History, Claimed, UserSettings])


class ClaimsManager:
    @staticmethod
    async def get_data_from_server(bot, config):
        ret = {}
        g = bot.get_guild(config['saves_guild'])
        for k, v in config['categories'].items():
            cat = g.get_channel(v)
            pics = {}
            for c in cat.channels:
                if c.name == '_resp_specific': continue  # todo logic
                color = "4f545c"
                resps_for_char = []
                msgs = await c.history().flatten()
                attachements = []
                for m in msgs:
                    #  url, is_nsfw
                    attachements.extend([[a, a.is_spoiler()] for a in m.attachments])
                    if m.content:
                        if m.content.lower().startswith('color: '):
                            color = m.content.lower().split('color: ')[-1][:6]
                        if m.content.startswith('resps:'):  # be sure it's resps:
                            rs = "resps:".join(m.content.split('resps:')[1:])
                            resps_for_char.extend(rs.split('```')[1].split('```')[0].split('\n'))
                            for r in resps_for_char:
                                if r == '': resps_for_char.remove(r)
                            a = 0
                dk = (str(c).replace('-', ' ').title()
                      if not str(c).startswith('_') else str(c)[1:].title())
                dk += f'_{color}'
                pics[dk] = [attachements, resps_for_char]  # indexes for ret stuff

            ret[k] = pics
        d = 0
        return ret
