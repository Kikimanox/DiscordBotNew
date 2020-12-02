from peewee import *
from datetime import datetime

DB = "data/rrs.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class ReactionRolesModel(BaseModel):
    id = AutoField()
    gid = IntegerField()
    chid = IntegerField()
    msgid = IntegerField(unique=True)
    msg_link = CharField()
    meta = CharField(default='')


db.create_tables([ReactionRolesModel])


class RRManager:
    @staticmethod
    def return_whole_rr_list():
        rrs = [q for q in ReactionRolesModel.select().dicts()]
        ret = {}
        for aa in rrs:
            if aa['gid'] not in ret:
                ret[aa['gid']] = {}
            if aa['chid'] not in ret[aa['gid']]:
                ret[aa['gid']][aa['chid']] = {}
            ret[aa['gid']][aa['chid']][aa['msgid']] = [aa['meta'].split(' '), aa['msg_link']]
        return ret

    @staticmethod
    def add_or_update_rrs_bot(bot, gid, chid, msgid, jump, meta):
        if gid not in bot.reaction_roles:
            bot.reaction_roles[gid] = {}
        if chid not in bot.reaction_roles[gid]:
            bot.reaction_roles[gid][chid] = {}
        bot.reaction_roles[gid][chid][msgid] = [meta, jump]

    @staticmethod
    def remove_from_rrs(bot, gid, chid, msgid):
        if gid in bot.reaction_roles:
            if chid in bot.reaction_roles[gid]:
                if msgid in bot.reaction_roles[gid][chid]:
                    try:
                        ReactionRolesModel.delete().where(ReactionRolesModel.msgid == msgid).execute()
                        del bot.reaction_roles[gid][chid][msgid]
                    except:
                        pass
