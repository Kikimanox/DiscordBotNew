import discord
from peewee import *
from datetime import datetime
from utils.dataIOa import dataIOa
import aiohttp
import asyncio
import json
import os

prsk_givenName_to_display_map = {
    "一歌": "Ichika Hoshino",
    "咲希": "Saki Tenma",
    "穂波": "Honami Mochizuki",
    "志歩": "Shiho Hinomori",
    "みのり": "Minori Hanasato",
    "遥": "Haruka Kiritani",
    "愛莉": "Airi Momoi",
    "雫": "Shizuku Hinomori",
    "こはね": "Kohane Azusawa",
    "杏": "An Shiraishi",
    "彰人": "Akito Shinonome",
    "冬弥": "Toya Aoyagi",
    "司": "Tsukasa Tenma",
    "えむ": "Emu Otori",
    "寧々": "Nene Kusanagi",
    "類": "Rui Kamishiro",
    "奏": "Kanade Yoisaki",
    "まふゆ": "Mafuyu Asahina",
    "絵名": "Ena Shinonome",
    "瑞希": "Mizuki Akiyama",
    "ミク": "Miku Hatsune",
    "リン": "Rin Kagamine",
    "レン": "Len Kagamine",
    "ルカ": "Luka Megurine",
    "MEIKO": "MEIKO",
    "KAITO": "KAITO"
}


async def fetch_cards(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None


async def fetch_and_save_or_load(url, backup_path):
    fetched_data = await fetch_cards(url)

    # If data was fetched successfully, save it to the backup file and return it
    if fetched_data:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)

        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(fetched_data, f, ensure_ascii=False, indent=4)
        return fetched_data
    # If fetching failed, load the data from the backup file and return it
    else:
        with open(backup_path, 'r', encoding='utf-8') as f:
            return json.load(f)


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
                    # Fetch or load character data for each of the 35 characters and construct the chars dictionary
                    chars = {}
                    for i in range(1, 36):
                        char_data = await fetch_and_save_or_load(
                            f"https://bestdori.com/api/characters/{i}.json",
                            f"data/bandori/{i}.json"
                        )
                        chars[i] = char_data

                    # Fetch or load the cards data
                    cards = await fetch_and_save_or_load(
                        "https://bestdori.com/api/cards/all.5.json",
                        "data/bandori/cards.all.5.json"
                    )

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
                        if v['rarity'] <= 2:
                            continue
                        if v['rarity'] > 2:
                            card_type = ['card_normal', 'card_after_training']
                        if v['type'] in ['kirafes', 'birthday']:
                            card_type.remove('card_normal')

                        for ct in card_type:
                            url = f'https://bestdori.com/assets/{country}/characters/resourceset/{asset}_rip/{ct}.png'
                            pics[char_key][0].append([type('obj', (object,), {'url': url}), False])

                    ret[k] = pics
                    continue

                if k == 'prsk':
                    # Fetch cards, characters, and color codes data or load from backup
                    cards_data = await fetch_and_save_or_load(
                        "https://sekai-world.github.io/sekai-master-db-diff/cards.json",
                        "data/prsk/cards.json"
                    )
                    characters_data = await fetch_and_save_or_load(
                        "https://sekai-world.github.io/sekai-master-db-diff/gameCharacters.json",
                        "data/prsk/gameCharacters.json"
                    )
                    color_codes_data = await fetch_and_save_or_load(
                        "https://sekai-world.github.io/sekai-master-db-diff/gameCharacterUnits.json",
                        "data/prsk/gameCharacterUnits.json"
                    )

                    # Create a dictionary to map characterId to character name and color code
                    char_info = {}
                    for char in characters_data:
                        if 'givenName' in char:
                            char_info[char['id']] = {
                                # 'name': f"{char['firstName']} {char['givenName']}",
                                'name': prsk_givenName_to_display_map[char['givenName']],
                                'modelName': char['modelName']
                            }

                    for color in color_codes_data:
                        if color['gameCharacterId'] in char_info:
                            char_info[color['gameCharacterId']]['color'] = color['colorCode']

                    pics = {}
                    for card in cards_data:
                        char_id = card['characterId']
                        if char_id in char_info:
                            asset_name = card['assetbundleName']
                            char_name = char_info[char_id]['name']
                            char_color = char_info[char_id]['color'][-6:]
                            char_key = f"{char_name}_{char_color}"

                            if char_key not in pics:
                                pics[char_key] = [[], []]

                            # Construct the URLs for the card images
                            normal_url = f"https://storage.sekai.best/sekai-assets/character/member/{asset_name}_rip/card_normal.webp"
                            trained_url = f"https://storage.sekai.best/sekai-assets/character/member/{asset_name}_rip/card_after_training.webp"

                            # Add the URLs to the pics dictionary
                            pics[char_key][0].append([type('obj', (object,), {'url': normal_url}), False])
                            pics[char_key][0].append([type('obj', (object,), {'url': trained_url}), False])

                    ret[k] = pics

                cat = g.get_channel(v)
                pics = {}
                if cat is None:
                    return ret  # probably on dev bot or bot cant see categories
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
