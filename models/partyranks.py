import json
import os
import re

from PIL import Image
import aiohttp
from peewee import *
from datetime import datetime

DB = "data/prs.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class PRMembers(BaseModel):
    uid = IntegerField(primary_key=True)
    name = CharField()
    last_update = DateTimeField(default=datetime.utcnow)
    main_avatar_url = CharField()
    main_avatar_path = CharField(default="")
    pr_specific_avatars = CharField(default="{}")  # could've made another table for this but cba ...


# db.drop_tables([PRMembers])
db.create_tables([PRMembers])


async def verify_and_save_avatar(url, subfolder, name):
    ava_tmp_folder = f'tmp/pr_avatars/{subfolder}'
    ava_main_folder = f'data/pr_avatars/{subfolder}'
    os.makedirs(ava_tmp_folder, exist_ok=True)
    os.makedirs(ava_main_folder, exist_ok=True)
    url2 = url.split('?')[::-1][-1]
    ava_tmp_path = os.path.join(ava_tmp_folder, url2.split('/')[-1])
    ava_main_path = os.path.join(ava_main_folder, url2.split('/')[-1])

    if ava_tmp_path.split('.')[-1] not in ['png', 'jpg', 'jpeg']:
        return "File extension needs to be either png, jpg or jpeg", False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                with open(ava_tmp_path, 'wb') as fd:
                    async for data in r.content.iter_chunked(1024):
                        fd.write(data)
    except Exception as ex:
        return ex, False

    try:
        pic = Image.open(ava_tmp_path)
        w, h = pic.size
        if w != h:
            return f"Image width ({w}) is not the same as height ({h})\n" \
                   f"Use sites like https://ezgif.com/crop to crop and or edit your pic", False
        if w > 1200:
            return f"Do we really need a pic bigger than 1200x1200? ... ({w}x{h})\n" \
                   f"Use sites like https://ezgif.com/resize to crop and or edit your pic", False
        if w < 130:
            return f"I don't think this size is big enough... ({w}x{h})\n" \
                   f"Get a bigger pic resolution (if you're uploading /w discord, watch out for the " \
                   f"?size=... argument at the end, set that to a biger 2^n (256, 512, 1024) power", False
        pic.close()
        os.rename(ava_tmp_path, ava_main_path)

        ext = ava_main_path.replace('\\', '/').split('/')[-1].split('.')[-1]
        file_name = f'{name}.{ext}'
        ava_info_path_fixed = '/'.join(ava_main_path.replace('\\', '/').split('/')[:-1]) + '/' + file_name
        if os.path.exists(ava_info_path_fixed):
            os.remove(ava_info_path_fixed)
        os.rename(ava_main_path, ava_info_path_fixed)

        return ava_info_path_fixed, True
    except Exception as ex:
        return f'Unknown exception {ex}', False
    finally:
        try:
            if os.path.exists(ava_main_path):
                os.remove(ava_main_path)
            if os.path.exists(ava_tmp_path):
                os.remove(ava_tmp_path)
        except:
            pass


class PRManager:
    @staticmethod
    async def add_or_update_member(uid, name=None, main_avatar_url=None, pr_specific_avatar=None, specific_pr=None):

        ava_info = ""
        if main_avatar_url is not None:
            ava_info, was_ok = await verify_and_save_avatar(main_avatar_url, 'default', name)
            if not was_ok:
                raise Exception(ava_info)

        if pr_specific_avatar is not None and specific_pr is not None:
            ava_info, was_ok = await verify_and_save_avatar(pr_specific_avatar, specific_pr, name)
            if not was_ok:
                raise Exception(ava_info)

        if ava_info == "":
            raise Exception("Something went wrong when obtaining avatar info")

        member = PRMembers.get_or_none(PRMembers.uid == uid)
        if member is None:
            member = PRMembers.create(uid=uid, name=name, main_avatar_url=main_avatar_url)
        if name is not None:
            member.name = name
        if main_avatar_url is not None:
            member.main_avatar_url = main_avatar_url
            member.main_avatar_path = ava_info
        if pr_specific_avatar is not None and specific_pr is not None:
            spp = json.loads(member.pr_specific_avatars)
            spp[specific_pr] = ava_info
            member.pr_specific_avatars = json.dumps(spp)
        member.last_update = datetime.utcnow()
        member.save()
