from peewee import *
from datetime import datetime

DB = "data/afks.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class AfkTbl(BaseModel):
    id = AutoField()
    gid = IntegerField()
    uid = IntegerField()
    msg = CharField(default="")
    afk_on = DateTimeField(default=datetime.utcnow)


db.create_tables([AfkTbl])


class AfkManager:
    @staticmethod
    def return_whole_afk_list():
        afks = [q for q in AfkTbl.select().dicts()]
        ret = {}
        for aa in afks:
            if aa['gid'] not in ret:
                ret[aa['gid']] = {}
            ret[aa['gid']][aa['uid']] = [aa['msg'], aa['afk_on']]
        return ret

    @staticmethod
    def set_new_bot_afk(bot, afk: AfkTbl):
        if afk.gid not in bot.currently_afk:
            bot.currently_afk[afk.gid] = {}
        bot.currently_afk[afk.gid][afk.uid] = [afk.msg, afk.afk_on]

    @staticmethod
    def remove_from_afk(bot, uid, gid):
        if gid in bot.currently_afk:
            if uid in bot.currently_afk[gid]:
                try:
                    AfkTbl.delete().where(AfkTbl.uid == uid, AfkTbl.gid == gid).execute()
                    del bot.currently_afk[gid][uid]
                except:
                    pass
