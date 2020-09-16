from peewee import *
from datetime import datetime

DB = "data/claims.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class History(BaseModel):
    user = IntegerField()
    type = IntegerField()
    meta = CharField()


class Claimed(BaseModel):
    id = AutoField()
    user = IntegerField()
    type = IntegerField()
    expires_on = DateTimeField(default=datetime.utcnow)


db.drop_tables([History, Claimed])
db.create_tables([History, Claimed])


class ClaimsManager:
    @staticmethod
    async def get_data_from_server(bot, config):
        ret = {}
        g = bot.get_guild(config['saves_guild'])
        for k, v in config['categories'].items():
            cat = g.get_channel(v)
            pics = {}
            for c in cat.channels:
                color = "4f545c"
                msgs = await c.history().flatten()
                urls = []
                for m in msgs:
                    #  url, is_nsfw
                    urls.extend([[a.url, a.is_spoiler()] for a in m.attachments])
                    if m.content:
                        if m.content.startswith('color: '):
                            color = m.content.split('color: ')[-1][:6]
                dk = (str(c).replace('-', ' ').title()
                      if not str(c).startswith('_') else str(c)[1:].title())
                dk += f'_{color}'
                pics[dk] = urls

            ret[k] = pics
        d = 0
        return ret
