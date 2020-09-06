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
from utils.dataIOa import dataIOa

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
    content = CharField(default='')
    desc = CharField(default='')
    images = CharField(default='')
    title = CharField(default='')
    color = IntegerField(default=int(f"0x{dataIOa.load_json('config.json')['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16))
    target_ch = IntegerField()  # target channel


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
    def get_or_create_and_get_welcomemsg(g, chid, gid):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
        except Exception as e:
            wm = WelcomeMsg.create(target_ch=chid, guild=g)
        return wm

    @staticmethod
    async def update_or_error_welcomemsg_target_ch(chid, gid, ctx):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
            wm.target_ch = chid
            wm.save()
            await ctx.send("Updated.")
        except:
            await ctx.send(f"Please run `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg mainsetup <channel>` first")

    @staticmethod
    async def update_or_error_welcomemsg_title(title, gid, ctx):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
            wm.title = title
            wm.save()
            await ctx.send("Updated.")
        except:
            await ctx.send(f"Please run `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg mainsetup <channel>` first")

    @staticmethod
    async def update_or_error_welcomemsg_desc(desc, gid, ctx):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
            wm.desc = desc
            wm.save()
            await ctx.send("Updated.")
        except:
            await ctx.send(f"Please run `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg mainsetup <channel>` first")

    @staticmethod
    async def update_or_error_welcomemsg_images(images, gid, ctx):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
            wm.images = images
            wm.save()
            await ctx.send("Updated.")
        except:
            await ctx.send(f"Please run `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg mainsetup <channel>` first")

    @staticmethod
    async def update_or_error_welcomemsg_content(content, gid, ctx):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
            wm.content = content
            wm.save()
            await ctx.send("Updated.")
        except:
            await ctx.send(f"Please run `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg mainsetup <channel>` first")

    @staticmethod
    async def update_or_error_welcomemsg_color(color, gid, ctx):
        try:
            wm = WelcomeMsg.get(WelcomeMsg.guild == gid)
            wm.color = color
            wm.save()
            await ctx.send("Updated.")
        except:
            await ctx.send(f"Please run `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg mainsetup <channel>` first")

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
    async def get_setup_formatted(bot, updating_g_id=None):
        gs = [q for q in Guild.select().dicts()]
        lgs = [q for q in Logging.select().dicts()]
        whks = [q for q in Webhook.select().dicts()]
        welcs = [q for q in WelcomeMsg.select().dicts()]

        ret = {}
        for g in gs:
            if updating_g_id and updating_g_id != g['id']: continue
            ret[g['id']] = {'muterole': g['muterole'], 'modrole': g['modrole']}
            for lg in lgs:
                if lg['guild'] != g['id']: continue
                try:
                    ret[g['id']][lg['type']] = await bot.fetch_channel(lg['target_ch'])
                except:
                    ret[g['id']][lg['type']] = None
            for wh in whks:
                if wh['guild'] != g['id']: continue
                try:
                    aa = await bot.fetch_webhook(wh['hook_id'])  # wh['hook_id']
                    ret[g['id']][f"hook_{wh['type']}"] = aa
                except:
                    bot.logger.error(f"Webhook for guild {wh['guild']} missing")
                    ret[g['id']][f"hook_{wh['type']}"] = None
            for wel in welcs:
                if wel['guild'] != g['id']: continue
                ret[g['id']]['welcomemsg'] = wel
                try:
                    ret[g['id']]['welcomemsg']['target_ch'] = \
                        await bot.fetch_channel(ret[g['id']]['welcomemsg']['target_ch'])
                except:
                    ret[g['id']]['welcomemsg'] = None
