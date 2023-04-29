import discord
from peewee import *
from datetime import datetime
from utils.dataIOa import dataIOa

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
        possible_for_bot = config['use_these']
        gs = config['saves_guild']
        for G in gs:
            g = bot.get_guild(int(G))
            if not g:
                raise Exception(f"Can't find the claims guild {G}")
            for k, v in config['saves_guild'][G]['categories'].items():
                if k not in possible_for_bot: continue

                # for i in {1..35}; do curl -v -X GET https://bestdori.com/api/characters/$i.json > $i.json; end; done
                # curl -v -X GET https://bestdori.com/api/characters/main.3.json > characters.main.3.json (not needed)
                # curl -v -X GET https://bestdori.com/api/cards/all.5.json > cards.all.5.json
                if k == 'bandori':
                    chars = {k: v for e in [{i: dataIOa.load_json(f'data/bandori/{i}.json')} for i in range(1, 36)] for
                             k, v in e.items()}
                    cards = dataIOa.load_json(f'data/bandori/cards.all.5.json')
                    d = 0
                    pics = {}
                    for _, v in cards.items():
                        url = ""
                        country_codes = {0: 'jp', 1: 'en', 2: 'tw', 3: 'cn', 4: 'kr'}
                        country = country_codes[[i for i, el in enumerate(v['releasedAt']) if el is not None][0]]
                        card_type = []
                        asset = v['resourceSetName']
                        char = chars[v['characterId']]
                        char_name = char['characterName'][1]
                        char_color = char['colorCode'][-6:]
                        char_key = f"{char_name}_{char_color}"
                        if char_key not in pics: pics[char_key] = [[], []]
                        #if v['rarity'] in [1, 2]:
                        #    card_type = ['card_normal']
                        if v['rarity'] <= 2:
                            continue
                        if v['rarity'] > 2:
                            card_type = ['card_normal', 'card_after_training']
                        if v['type'] in ['kirafes', 'birthday']:
                            card_type.remove('card_normal')

                        for ct in card_type:
                            url = f'https://bestdori.com/assets/{country}/characters/resourceset/{asset}_rip/{ct}.png'

                            pics[char_key][0].append([type('obj', (object,), {'url': url}), False])
                            # todo: add to pics
                            d = 0

                    ret[k] = pics
                    continue

                cat = g.get_channel(v)
                pics = {}
                for c in cat.channels:
                    if c.name == '_resp_specific': continue  # todo logic
                    color = "4f545c"
                    resps_for_char = []
                    msgs = []
                    async for m in c.history():
                        msgs.append(m)
                    attachements = []
                    for m in msgs:
                        #  url, is_nsfw
                        attachements.extend([[a, a.is_spoiler()] for a in m.attachments])
                        if m.content:
                            if m.content.lower().startswith('color: '):
                                color = m.content.lower().split('color: ')[-1][-6:]
                            if m.content.lower().startswith('resps:'):  # be sure it's resps:
                                rs = "resps:".join(m.content.split('resps:')[1:])
                                resps_for_char.extend(rs.split('```')[1].split('```')[0].split('\n'))
                                for r in resps_for_char:
                                    if r == '': resps_for_char.remove(r)
                                a = 0
                    dk = (str(c).replace('-', ' ').title()
                          if not str(c).startswith('_') else str(c)[1:].title())  # _ at the start maens don't replace -
                    dk += f'_{color}'
                    pics[dk] = [attachements, resps_for_char]  # indexes for ret stuff

                ret[k] = pics
        d = 0
        return ret
