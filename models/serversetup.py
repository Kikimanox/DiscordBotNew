"""
Guild: id, muterole, modrole
Welcomemsg: id, content, desc, images, title, FK_GUILD
Logging: id, target_ch, type, FK_GUILD, FK_Hooks
Webhooks: id, url, id, target_ch, FK_GUILD, valid
"""
import os

from peewee import *
from datetime import datetime
import utils.discordUtils as dutils

DB = "data/serversetup.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Guild(BaseModel):
    id = IntegerField(primary_key=True)
    muterole = IntegerField(null=True)
    modrole = IntegerField(null=True)


class WelcomeMsg(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    content = CharField(null=True)
    desc = CharField(null=True)
    images = CharField(null=True)
    title = CharField(null=True)


class Webhook(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    hook_id = IntegerField()
    url = CharField()
    target_ch = IntegerField()
    type = CharField()  # reg, leavejoin, modlog
    valid = BooleanField(default=True)


class Logging(BaseModel):
    guild = ForeignKeyField(Guild, on_delete="CASCADE")
    target_ch = IntegerField()
    type = CharField()  # reg, leavejoin, modlog


# db.drop_tables([Guild, WelcomeMsg, Logging, Webhook])
db.create_tables([Guild, WelcomeMsg, Logging, Webhook])


class SSManager:
    @staticmethod
    def get_or_create_and_get_guild(gid):
        try:
            guild = Guild.get(Guild.id == gid)
        except:
            guild = Guild.create(id=gid)
        return guild

    @staticmethod
    def create_or_update_logging(g, tar_id, typ):
        try:
            log = Logging.select().where((Logging.type == typ) & (Logging.guild == g))
            log = log[0]
            log.target_ch = tar_id
            log.save()
        except:
            Logging.insert(guild=g, target_ch=tar_id, type=typ).execute()

    @staticmethod
    async def create_or_update_logging_hook(g, hook_id, tar_id, typ, raw_hook, ctx):
        if raw_hook.channel.id != tar_id:
            await ctx.send(f"Setup failed! The webhook's actual target channel is {raw_hook.channel.mention}. "
                           f"Please fix that by hand first or change your argument")
            raise Exception('_fail')
        h_url = raw_hook.url
        log = Logging.select().where((Logging.type == typ) & (Logging.guild == g))
        if len(log) == 0:
            await ctx.send(f"Setup failed! Please setup **{typ}** logging first")
            raise Exception('_fail')
        log = log[0]
        if log.target_ch != tar_id:
            await ctx.send(f"Setup failed!\nReason: **{typ}** logging channel"
                           f" (id {log.target_ch} does not match the hook's target"
                           f" channel that you have provided in the arguments")
            raise Exception('_fail')

        if f'{ctx.bot.user.display_name} logging hook'[:32] != raw_hook.name:
            url = str(ctx.bot.user.avatar_url).replace('.webp', '.png')
            tf = f'a{str(int(datetime.utcnow().timestamp()))}a'
            fnn = await dutils.saveFile(url, 'tmp', tf)
            with open(fnn, 'rb') as fp:
                await raw_hook.edit(name=f'{ctx.bot.user.display_name} logging hook'[:32], avatar=fp.read())
            os.remove(fnn)
        try:
            hook = Webhook.select().where((Webhook.type == typ) & (Webhook.guild == g))
            hook = hook[0]
            hook.url = h_url
            hook.target_ch = tar_id
            hook.save()
        except:
            Webhook.insert(type=typ, guild=g, target_ch=tar_id, url=h_url, hook_id=hook_id).execute()

    @staticmethod
    def get_all_data():
        pass
