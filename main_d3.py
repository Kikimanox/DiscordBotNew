import asyncio
import datetime
import logging
import logging.handlers as handlers
import os
import re
import subprocess
import sys
import time
# import utils.discordUtils as dutils
import traceback

import discord
from discord import Embed, Client, Reaction, VoiceClient, app_commands, Activity, ActivityType
from discord.ext import commands

import utils.discordUtils as dutils
import utils.timeStuff as tutils
from models.afking import AfkManager
from models.antiraid import ArManager
from models.reactionroles import RRManager
from utils.checks import owner_check, admin_check, moderator_check_no_ctx
from utils.dataIOa import dataIOa
from utils.help import Help

formatter = logging.Formatter('%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s')
if not os.path.exists("logs"):
    os.makedirs("logs/error")
    os.makedirs("logs/info")
    os.makedirs("logs/workers")


def setup_logger(logger_name, level=logging.INFO):
    name = f"{logger_name}"
    l = logging.getLogger(name)
    logHandler = handlers.RotatingFileHandler(f'logs/{logger_name}/{logger_name}.log', maxBytes=5000, backupCount=20,
                                              encoding='utf-8')
    logHandler.setFormatter(formatter)
    l.setLevel(level)
    l.addHandler(logHandler)


# fixes bug when bot restarted but log file retained loghandler. this will remove any
# handlers it already had and replace with new ones initialized above
setup_logger("info", logging.INFO)
setup_logger("error", logging.ERROR)
logger = logging.getLogger(f"info")
error_logger = logging.getLogger(f"error")
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logging.getLogger('').addHandler(ch)

intents = discord.Intents.default()
intents.emojis = True
intents.reactions = True
intents.webhooks = True
intents.integrations = True
intents.members = True
intents.presences = True
intents.message_content = True

Prefix = dataIOa.load_json('config.json')['BOT_PREFIX']
Prefix_Per_Guild = dataIOa.load_json('config.json')['B_PREF_GUILD']


def get_pre(_bot, _message):
    if isinstance(_message.channel, discord.DMChannel): return Prefix
    gid = str(_message.guild.id)
    if gid not in Prefix_Per_Guild: return Prefix
    return Prefix_Per_Guild[gid]


def get_pre_or_mention(_bot, _message):
    extras = [get_pre(_bot, _message)]
    return commands.when_mentioned_or(*extras)(_bot, _message)


VoiceClient.warn_nacl = False
bot = commands.Bot(command_prefix=get_pre_or_mention, intents=intents)
###
bot.all_cmds = {}
bot.running_tasks = []
bot.from_serversetup = {}
bot.running_chapters = {}
bot.chapters_json = {}
bot.anti_raid = ArManager.get_ar_data()
bot.currently_afk = AfkManager.return_whole_afk_list()
bot.moderation_blacklist = {-1: 'dummy'}
bot.reaction_roles = RRManager.return_whole_rr_list()
###
bot.config = dataIOa.load_json('config.json')
bot.config['BOT_DEFAULT_EMBED_COLOR'] = int(f"0x{bot.config['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16)
bot.help_command = Help()
bot.before_run_cmd = 0
bot.just_banned_by_bot = {}
bot.just_kicked_by_bot = {}
bot.just_muted_by_bot = {}
bot.banned_cuz_blacklist = {}

bot.emote_servers_tmp = [
    777942981197299732,
    777943001539411968,
    777943027241975828,
    777943043223060511,
    777943082300604447,
    777943112764489769
]
bot.emote_servers_perm = [
    777943294353080380
]


@bot.event
async def on_ready():
    ###
    if hasattr(bot, 'all_cmds') and not bot.all_cmds: bot.all_cmds = {}
    if hasattr(bot, 'running_tasks') and not bot.running_tasks: bot.running_tasks = []
    if hasattr(bot, 'from_serversetup') and not bot.from_serversetup: bot.from_serversetup = {}
    if hasattr(bot, 'running_chapters') and not bot.from_serversetup: bot.running_chapters = {}
    if hasattr(bot, 'chapters_json') and not bot.from_serversetup: bot.chapters_json = {}
    if hasattr(bot, 'anti_raid') and not bot.anti_raid: bot.anti_raid = ArManager.get_ar_data()
    if hasattr(bot, 'currently_afk') and not bot.currently_afk: bot.currently_afk = AfkManager.return_whole_afk_list()
    if hasattr(bot, 'moderation_blacklist') and not bot.moderation_blacklist: bot.moderation_blacklist = {-1: 'dummy'}
    if hasattr(bot, 'reaction_roles') and not bot.reaction_roles: bot.reaction_roles = RRManager.return_whole_rr_list()
    ###
    bot.config = dataIOa.load_json('config.json')
    bot.config['BOT_DEFAULT_EMBED_COLOR'] = int(f"0x{bot.config['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16)
    bot.uptime = datetime.datetime.utcnow()
    # bot.ranCommands = 0
    bot.help_command = Help()

    bot.help_command = Help()
    logger.info("Bot logged in and ready.")
    print(discord.utils.oauth_url(bot.user.id) + '&permissions=8')
    print('------------------------------------------')
    if os.path.isfile("restart.json"):
        restartData = dataIOa.load_json("restart.json")
        try:
            guild = bot.get_guild(restartData["guild"])
            channel = guild.get_channel(restartData["channel"])
            await channel.send("Restarted.")
        except:
            print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            trace = traceback.format_exc()
            error_logger.error(trace)
            print(trace)
            print("couldn't send restarted message to channel.")
        finally:
            os.remove("restart.json")

    await load_all_cogs_except(['_newCogTemplate', 'manga', 'bets'])
    if os.name != 'nt':
        os.setpgrp()

    config = dataIOa.load_json("config.json")

    # Temporarily adding manga and bets only to ai bot ~~and dev bot~~
    if config['CLIENT_ID'] in [705157369130123346, 589921811349635072]:
        await bot.load_extension("cogs.manga")
        await bot.load_extension("cogs.bets")

    activity = Activity(name=f"\"{Prefix}\" for the Prefix", type=ActivityType.listening)
    await bot.change_presence(activity=activity)


@bot.event
async def on_reaction_add(reaction: Reaction, user: Client):
    if user != bot.user:
        x_mark = '\U0000274c'
        if str(reaction.emoji) == x_mark:
            if reaction.message.author.id == bot.user.id:
                message = reaction.message
                await message.delete()


def exit_bot(self):
    # if os.name != 'nt': In case you need to kill some other tasks
    #     try:
    #         os.killpg(0, signal.SIGKILL)
    #     except:
    #         print("error in and killing background tasks on exit")
    #         error_logger.error("Error in exit_bot")
    #         trace = traceback.format_exc()
    #         error_logger.error(trace)
    #         print(trace)
    for t in bot.running_tasks:
        try:
            t.cancel()
        except:
            pass
    os._exit(0)


@commands.check(owner_check)
@bot.command(hidden=True)
async def dmlu(ctx, *, urls_paste: str):
    """Combine urls from a dm log"""
    try:
        lines = urls_paste.split('\n')
        base = lines[0].split('...')[0]
        ret = '\n'.join([f'<{base}{line}>' for line in lines[1:]])
        await ctx.send(ret)
    except:
        await ctx.send("Somethign went wrong")
        error_logger.error(traceback.format_exc())


@commands.check(owner_check)
@bot.command()
async def dm(ctx, user: discord.User, *, content=""):
    """Send a direct message to an user [no arguments for user check]"""
    if not content and not ctx.message.attachments and user:
        return await ctx.send(embed=Embed(description=f"{user.mention} - `{user}` `{user.id}`")
                              .set_thumbnail(url=dutils.icon_url(user)))
    try:
        async with ctx.typing():
            m = None
            if ctx.message.attachments:
                m = await ctx.send("Saving files to re-send.")
            atts = [await a.to_file(spoiler=a.is_spoiler()) for a in ctx.message.attachments]
            mm = await user.send(content, files=atts)
            if m: await m.delete()
            await ctx.send(embed=Embed(description=f"{user.mention} - `{user}` `{user.id}`", title='Message '
                                                                                                   'delivered ✅')
                           .set_thumbnail(url=dutils.icon_url(user)).set_footer(text=f'{mm.channel.id} {mm.id}'))
    except:
        await ctx.send(f"Failed to send.\n```\n{traceback.format_exc()}```")


@commands.check(owner_check)
@bot.command(aliases=['dmr', 'dmrm', 'dmd'])
async def dmdel(ctx, ch_id: int, msg_id: int):
    """Delete a message in dms by *chid* and msgid"""
    try:
        ch = await bot.fetch_channel(ch_id)
        msg = await ch.fetch_message(msg_id)
        await msg.delete()
        await ctx.sned("Deleted.")
    except:
        await ctx.send("Something went wrong when trying to delete.")


@commands.check(owner_check)
@bot.command(aliases=['dme'])
async def dmedit(ctx, ch_id: int, msg_id: int, *, new_content):
    """Edit a message in dms by *chid* and msgid"""
    try:
        ch = await bot.fetch_channel(ch_id)
        msg = await ch.fetch_message(msg_id)
        await msg.edit(content=new_content)
        await ctx.sned("Edited.")
    except:
        await ctx.send("Something went wrong when trying to edit.")


@commands.check(admin_check)
@bot.command()
async def prefix(ctx, *, new_prefix=""):
    """Check or change the prefix ({space_here} for a space at the end)

    If you need spaces, do {space_here}
    and it will be replaced with spaces
    ...Or just use spaces (usable if you need the mat the end)"""
    if '@' in new_prefix: return await ctx.send("The character `@` is not allowed in "
                                                "the bot's prefix. Try again.")
    if not new_prefix:
        return await ctx.send(embed=Embed(title='My prefix is', description=dutils.bot_pfx(ctx.bot, ctx.message)))
    if '{space_here}' in new_prefix:  new_prefix = new_prefix.replace('{space_here}', ' ')
    if new_prefix.strip() == "": return await ctx.send("A prefix can not be only spaces.")
    if dutils.bot_pfx(ctx.bot, ctx.message) == new_prefix: return await ctx.send(
        "Why are you trying to make the new prefix the same "
        "as the previous one? Oh yeah, if you are trying to make a prefix"
        "with a space at the end, for example `bb command` then do: "
        "`.prefix bb{space_here}`")
    ctx.bot.config['B_PREF_GUILD'][str(ctx.guild.id)] = new_prefix
    if new_prefix == Prefix: del ctx.bot.config['B_PREF_GUILD'][str(ctx.guild.id)]
    conf_copy = bot.config.copy()
    conf_copy["BOT_DM_LOG"]["CAN_SEND"] = 0
    conf_copy["BOT_DM_LOG"]["HOOK"] = 0
    conf_copy['BOT_DEFAULT_EMBED_COLOR'] = 0
    dataIOa.save_json("config.json", conf_copy)
    global Prefix_Per_Guild
    Prefix_Per_Guild = ctx.bot.config['B_PREF_GUILD']
    await ctx.send("Prefix changed.")


@commands.check(owner_check)
@bot.command(aliases=['gprefix'], hidden=True)
async def globalprefix(ctx, *, new_prefix=""):
    """Check or change the main default prefix

    If you need spaces, do {space_here}
    and it will be replaced with spaces
    ...Or just use spaces (usable if you need the mat the end)"""
    if '@' in new_prefix: return await ctx.send("The character `@` is not allowed in "
                                                "the bot's prefix. Try again.")
    if not new_prefix:
        return await ctx.send(embed=Embed(title='My main prefix is', description=bot.config['BOT_PREFIX']))
    if '{space_here}' in new_prefix:  new_prefix = new_prefix.replace('{space_here}', ' ')
    if new_prefix.strip() == "": return await ctx.send("A prefix can not be only spaces.")
    if bot.config['BOT_PREFIX'] == new_prefix: return await ctx.send(
        "Why are you trying to make the new prefix the same "
        "as the previous one? Oh yeah, if you are trying to make a prefix"
        "with a space at the end, for example `bb command` then do: "
        "`.prefix bb{space_here}`")
    bot.config['BOT_PREFIX'] = new_prefix
    conf_copy = bot.config.copy()
    conf_copy["BOT_DM_LOG"]["CAN_SEND"] = 0
    conf_copy["BOT_DM_LOG"]["HOOK"] = 0
    conf_copy['BOT_DEFAULT_EMBED_COLOR'] = 0
    dataIOa.save_json("config.json", conf_copy)
    global Prefix
    Prefix = new_prefix
    await ctx.send("Prefix changed.")


@bot.event
async def on_message(message):
    # if message.guild.id != 202845295158099980: return  # Testing guild
    # if message.author.id != 174406433603846145: return  # Testing stuff, stop spamming

    # check if it's even a user
    if message.author.bot:
        return

    # TEMPORARY
    if message.guild and message.guild.id == 442952794480050177:
        if message.channel.id == 693792405882929173:  # verification
            try:
                await message.delete()
            except:
                pass
            if message.content.lower() == 'i agree to the rules':
                r = discord.utils.get(message.guild.roles, id=693790666249207808)
                try:
                    await message.author.add_roles(r)
                except:
                    pass

    is_mod = await moderator_check_no_ctx(message.author, message.guild, bot)
    ck = 'censor_list'
    was_deleted = False
    if not is_mod:
        if message.guild and message.guild.id in bot.from_serversetup and bot.from_serversetup[message.guild.id][ck]:
            if any(w.lower() in bot.from_serversetup[message.guild.id][ck] for w in message.content.lower().split()):
                await message.delete()
                was_deleted = True
            if any(c in message.content.lower() for c in
                   bot.from_serversetup[message.guild.id][ck]) and not was_deleted:
                await message.delete()
                was_deleted = True

    arl = 0
    # get anti raid level
    if message.guild and message.guild.id in bot.anti_raid:
        arl = bot.anti_raid[message.guild.id]['anti_raid_level']
        if arl > 1:  # check ping count during raid levels 2 and 3
            mention_count = sum(not m.bot and m.id != message.author.id for m in message.mentions)
            if mention_count > bot.anti_raid[message.guild.id]['max_allowed_mentions']:
                return await dutils.punish_based_on_arl(arl, message, bot, mentions=True)

    # it was a dm
    if not message.guild and message.author.id != bot.config['CLIENT_ID']:
        arl = -1
        # print(f'DM LOG: {str(message.author)} (id: {message.author.id}) sent me this: {message.content}')
        if not bot.is_ready():
            return await message.channel.send("Bot is still starting up, hold on a few seconds.")
        is_setup = await dutils.dm_log_try_setup(bot)
        if is_setup:
            await dutils.dm_log(bot, message)

    pfx = str(get_pre(bot, message))
    if message.content in [f'<@!{bot.config["CLIENT_ID"]}>', f'<@{bot.config["CLIENT_ID"]}>']:
        return await message.channel.send(
            embed=(Embed(title='My prefix here is', description=pfx).set_footer(text='You can change it with '
                                                                                     f'{pfx}prefix')))

    # is_prefix = message.content.startswith(pfx) or message.content.split(' ')[0] in [f'<@!{bot.config["CLIENT_ID"]}>',
    #                                                                                  f'<@{bot.config["CLIENT_ID"]}>']

    #  Check if it's actually a cmd or custom cmd
    possible_cmd = ""
    is_actually_cmd = False
    ctype = -1  # 1 possible_cmd | 2 mutli word | 3 same as 0 but inh | 4 same as 1 but inh
    if message.content.startswith(f'<@{bot.config["CLIENT_ID"]}>'):
        pfx_len = len(f'<@{bot.config["CLIENT_ID"]}>') + 1
    elif message.content.startswith(f'<@!{bot.config["CLIENT_ID"]}>'):
        pfx_len = len(f'<@!{bot.config["CLIENT_ID"]}>') + 1
    elif message.content.startswith(pfx):
        pfx_len = len(pfx)
    else:
        pfx_len = -1
    if pfx_len > 0:
        possible_cmd = message.content[pfx_len:].split(' ')[0]
        if possible_cmd in bot.all_commands:
            is_actually_cmd = True
        if not is_actually_cmd:
            if message.guild and message.guild.id in bot.all_cmds:
                if possible_cmd in bot.all_cmds[message.guild.id]['cmds_name_list']:
                    ctype = 1
                elif message.content[pfx_len:] in bot.all_cmds[message.guild.id]['cmds_name_list']:
                    ctype = 2
                elif possible_cmd in bot.all_cmds[message.guild.id]['inh_cmds_name_list']:
                    ctype = 3
                elif message.content[pfx_len:] in bot.all_cmds[message.guild.id]['inh_cmds_name_list']:
                    ctype = 4

    # if it was a command
    if (is_actually_cmd or ctype > 0) or arl > 1:  # catch messages here for anti spam on arl > 1 regardless of cmd
        if arl in [0, 1]:  # If not checking for message spamming and user is blacklisted return
            if message.author.id in bot.banlist:
                return

        if arl in [0, 1]:  # user can unblacklist themselves here
            if (message.author.id in bot.blacklist) and ('unblacklistme' in message.content):
                if possible_cmd and possible_cmd == 'unblacklistme':
                    if not bot.is_ready():
                        return await message.channel.send("Bot is still starting up, hold on a few seconds.")
                    if was_deleted: return
                    return await bot.process_commands(message)

        if arl in [0, 1]:  # the journey for the blacklisted end shere
            if message.author.id in bot.blacklist:
                return

        bucket = bot.spam_control[arl].get_bucket(message)
        current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()
        retry_after = bucket.update_rate_limit(current)
        author_id = message.author.id

        # spamming has started (but ignore moderators though)
        if retry_after and not is_mod:
            bot._auto_spam_count[author_id] += 1
            d_max = 4  # max number of times they can spam again after bucket triggers
            if arl > 1: d_max = 2
            if bot._auto_spam_count[author_id] >= d_max:

                #  SPAMMER DETECTED HERE!
                if arl > 1:
                    return await dutils.punish_based_on_arl(arl, message, bot)

                if possible_cmd != 'unblacklistme' and arl in [0, 1]:
                    del bot._auto_spam_count[author_id]
                    # await self.log_spammer(ctx, message, retry_after, autoblock=True)
                    out = f'[{retry_after} | {message.content}]({message.jump_url})'
                    # print(out)
                    gid = 0
                    if message.guild: gid = message.guild.id
                    await dutils.blacklist_from_bot(bot, message.author, out, gid,
                                                    ch_to_reply_at=message.channel, arl=arl)
                else:
                    out2 = f"{str(message.author)} {datetime.datetime.utcnow().strftime('%c')}" \
                           f" source: {message.jump_url}"
                    out = f'[{author_id} | {retry_after} |' \
                          f' {message.content}]({message.jump_url})'
                    if message.author.id not in bot.banlist:
                        await dutils.ban_from_bot(bot, message.author, out2, message.guild.id, message.channel)
            else:
                out = f'almost SPAMMER: {author_id} | {retry_after} | {message.content} | {message.jump_url}'
            logger.info(out)
            if bot._auto_spam_count[author_id] == d_max - 1: return
        else:
            bot._auto_spam_count.pop(author_id, None)

        arl1_ret = ("The server has set it's raid protection to level 1.\n"
                    f"{message.author.mention} stop using/spamming bot commands "
                    f"for now or else you will get banned from the bot.")

        sup = None
        kk = 'disabled_onlyEnabled_cmds_and_chs'
        if message.guild and message.guild.id in bot.from_serversetup and bot.from_serversetup[message.guild.id][kk]:
            sup = bot.from_serversetup[message.guild.id][kk]

        if not is_mod and (is_actually_cmd or ctype > 0) and arl > 1:
            return  # we don't want non mods triggering commands during a raid
        if was_deleted:
            return
        if is_actually_cmd:
            if arl == 1 and not is_mod:  # well, during a lvl 1 raid, we can warn them
                return await message.channel.send(arl1_ret)
            if sup and possible_cmd in sup and not is_mod:
                if message.channel.id in sup[possible_cmd]['dis']:
                    return await message.channel.send("❌ This command is disabled in the following channels:\n"
                                                      f"{', '.join((message.guild.get_channel(c)).mention for c in sup[possible_cmd]['dis'])}")
                if sup[possible_cmd]['only_e'] and message.channel.id not in sup[possible_cmd]['only_e']:
                    return await message.channel.send("❌ This command is enabled only in the following channels:\n"
                                                      f"{', '.join((message.guild.get_channel(c)).mention for c in sup[possible_cmd]['only_e'])}")

            if not bot.is_ready():
                return await message.channel.send("Bot is still starting up, hold on a few seconds.")
            return await bot.process_commands(message)

        if ctype != -1:
            if not bot.is_ready():
                return await message.channel.send("Bot is still starting up, hold on a few seconds.")
            if arl == 1 and not is_mod:
                return await message.channel.send(arl1_ret)

            pos_c = '"custom cmds"'
            if sup and pos_c in sup:
                if message.channel.id in sup[pos_c]['dis'] and not is_mod:
                    return await message.channel.send("❌ Custom commands are disabled in the following channels:\n"
                                                      f"{', '.join((message.guild.get_channel(c)).mention for c in sup[pos_c]['dis'])}")
                if sup[pos_c]['only_e'] and message.channel.id not in sup[pos_c]['only_e']:
                    return await message.channel.send("❌ Custom commands are enabled only in the following channels:\n"
                                                      f"{', '.join((message.guild.get_channel(c)).mention for c in sup[pos_c]['only_e'])}")

            if ctype == 1:
                c = bot.all_cmds[message.guild.id]['cmds'][possible_cmd]
            elif ctype == 2:
                c = bot.all_cmds[message.guild.id]['cmds'][message.content[pfx_len:]]
            elif ctype == 3:
                for cc in bot.all_cmds[message.guild.id]['inh_cmd_list']:
                    if possible_cmd in cc: c = cc[possible_cmd]
            elif ctype == 4:
                for cc in bot.all_cmds[message.guild.id]['inh_cmd_list']:
                    if message.content[pfx_len:] in cc: c = cc[message.content[pfx_len:]]

            if bool(c['raw']): return await message.channel.send(c['content'])
            if bool(c['image']):
                em = Embed(color=int(f'0x{c["color"][-6:]}', 16))
                em.set_image(url=c['content'])
            else:
                em = Embed(color=int(f'0x{c["color"][-6:]}', 16), description=c['content'])
                pic = str(c['content']).find('http')
                if pic > -1:
                    urls = re.findall(r'https?:[/.\w\s-]*\.(?:jpg|gif|png|jpeg)', str(c['content']))
                    if len(urls) > 0: em.set_image(url=urls[0])
            return await message.channel.send(embed=em)


@commands.max_concurrency(1)
@commands.check(owner_check)
@bot.command()
async def restart(ctx, options: str = ""):
    """Restart the bot and git pull changes.

    Use "v" for verbose,
    Use "u" for update
    Use "vu"/"uv" for both """
    if "u" in options:
        if bot.config['NEW_MAIN_D']:
            os.rename(bot.config['NEW_MAIN_D'], 'main_d3.py')
        if bot.config['NEW_BOT_LOOP']:
            os.rename(bot.config['NEW_BOT_LOOP'], 'bot_loop3.py')
        await ctx.send("Running `git pull`...")
        loop = asyncio.get_event_loop()
        process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)
        output = await loop.run_in_executor(None, process.communicate)
        if "v" in options:
            a = output[0].decode(encoding='utf8', errors='ignore')
            if len(a) > 1900: a = a[:1900] + "\n\n...Content longer than 1900 chars"
            await ctx.send(f"```{a}```")
        else:
            await ctx.send("Git pulled.")
        if bot.config['NEW_MAIN_D']:
            os.rename('main_d3.py', bot.config['NEW_MAIN_D'])
        if bot.config['NEW_BOT_LOOP']:
            os.rename('bot_loop3.py', bot.config['NEW_BOT_LOOP'])
    await ctx.send("Restarting...")
    restarT = {"guild": ctx.guild.id, "channel": ctx.channel.id}
    dataIOa.save_json("restart.json", restarT)
    exit_bot(0)


@commands.max_concurrency(1)
@commands.check(owner_check)
@bot.command(aliases=["quit", "terminate"])
async def shutdown(ctx):
    """Shut down the bot."""
    with open('quit.txt', 'w', encoding="utf8") as q:
        q.write('.')
    await ctx.send("Shut down.")
    logger.info("Shut down.")
    exit_bot(0)


@bot.event
async def on_command_error(
        ctx: commands.Context,
        error
):
    if not bot.is_ready():
        await bot.wait_until_ready()
    error = getattr(error, "original", error)
    if isinstance(error, commands.errors.CommandNotFound):
        pass
    elif isinstance(error, commands.MissingRole):
        await ctx.send(f"You don't have the right role to invoke the command")
    elif isinstance(error, app_commands.MissingRole):
        await ctx.send(f"You don't have the right role to invoke the command")
    elif isinstance(error, commands.CommandInvokeError):
        # print("Command invoke error exception in command '{}', {}".format(ctx.command.qualified_name, str(error)))
        logger.info("Command invoke error exception in command '{}', "
                    "{}".format(ctx.command.qualified_name, str(error)))
    elif isinstance(error, commands.CommandOnCooldown):
        extra = ""
        if error.cooldown.type.name != 'default':
            extra += f" ({error.cooldown.type.name} cooldown)"
        tim = error.args[0].split(' in ')[-1]
        sec = int(tim.split('.')[0])
        tim = tutils.convert_sec_to_smhd(sec)
        await ctx.send(f"⏲ Command on cooldown, try again"
                       f" in **{tim}**" + extra, delete_after=5)
    elif isinstance(error, commands.errors.CheckFailure):
        if ctx.command.qualified_name == 'getrole booster':
            return await ctx.send("⚠ Only server boosters may use this command.")
        await ctx.send("⚠ You don't have permissions to use that command.")
        error_logger.error('CMD ERROR NoPerms'
                           f'{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}')
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        formatter = Help()
        help_msg = await formatter.format_help_for(ctx, ctx.command)
        await ctx.send(content="Missing required arguments. Command info:", embed=help_msg[0])
        error_logger.error('CMD ERROR MissingArgs '
                           f'{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}')
    elif isinstance(error, commands.errors.BadArgument):
        formatter = Help()
        help_msg = await formatter.format_help_for(ctx, ctx.command)
        await ctx.send(content="⚠ You have provided an invalid argument. Command info:", embed=help_msg[0])
        error_logger.error('CMD ERROR BadArg '
                           f'{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}')
    elif isinstance(error, commands.errors.MaxConcurrencyReached):
        if ctx.command.qualified_name == 'getrole booster':
            return await ctx.send(bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][str(ctx.guild.id)]['WARN_MSG'])
        await ctx.send(f"This command has reached the max number of concurrent jobs: "
                       f"`{error.number}`. Please wait for the running commands to finish before requesting again.")
    else:
        await ctx.send("An unknown error occurred with the `{}` command.".format(ctx.command.name))
        trace = traceback.format_exception(type(error), error, error.__traceback__)
        trace_str = "".join(trace)
        print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
        print(trace_str)
        print("Other exception in command '{}', {}".format(ctx.command.qualified_name, str(error)))
        error_logger.error(
            f"Command invoked but FAILED: {ctx.command} | By user: {ctx.author} (id: {str(ctx.author.id)}) "
            f"| Message: {ctx.message.content} | "
            f"Error: {trace_str}")


@bot.event
async def on_error(event, *args, **kwargs):
    if not bot.is_ready():
        await bot.wait_until_ready()
    exc_type, _, _ = sys.exc_info()
    print(exc_type)
    if isinstance(exc_type, discord.errors.ConnectionClosed) or isinstance(exc_type, discord.ConnectionClosed) or \
            issubclass(exc_type, discord.errors.ConnectionClosed) or issubclass(exc_type, discord.ConnectionClosed) or \
            issubclass(exc_type, ConnectionResetError):
        error_logger.error(f"---------- CRASHED ----------: {exc_type}")
        print("exception occurred, restarting...")
        error_logger.error("exception occurred, restarting bot")
        exit_bot(0)
    else:
        # print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
        trace = traceback.format_exc()
        error_logger.error(f"---------- ERROR ----------: {trace}")
        # print(trace)


@bot.before_invoke
async def before_any_command(ctx):
    if not bot.is_ready():
        await bot.wait_until_ready()
    if hasattr(bot, 'logger'):
        if ctx.guild:
            gg = f' In {ctx.guild} (id: {ctx.guild.id}) |'
        else:
            gg = ' In dms'
        logger.info(f"Command invoked: {ctx.command} | By user: {str(ctx.author)} (id: {str(ctx.author.id)}) "
                    f"|{gg} Message: {ctx.message.content}")
    bot.before_run_cmd += 1


@bot.after_invoke
async def after_any_command(ctx):
    # do something after a command is called
    if not bot.is_ready():
        await bot.wait_until_ready()
    bot.before_run_cmd -= 1


@bot.hybrid_command(
    description="Sync the slash commands."
)
@app_commands.describe(
    guild_id="The guild id of the server to be sync. Blank option means all servers sync"
)
async def synctree(
        ctx: commands.Context,
        guild_id: str = None
):
    if not guild_id:
        await bot.tree.sync()  # sync global commands
    else:
        await bot.tree.sync(guild=discord.Object(id=int(guild_id)))
    await ctx.send("Synced the application commands tree!", delete_after=10)


async def load_all_cogs_except(cogs_to_exclude):
    for extension in os.listdir("cogs"):
        if extension.endswith('.py'):
            if extension[:-3] not in cogs_to_exclude:
                try:
                    await bot.load_extension("cogs." + extension[:-3])
                except Exception as e:
                    print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
                    traceback.print_exc()


async def main() -> None:
    async with bot:
        config = dataIOa.load_json("config.json")
        token = config['BOT_TOKEN']

        await bot.start(token=token)


if __name__ == '__main__':
    while True:
        try:
            print(f'Connected: ---{datetime.datetime.utcnow().strftime("%c")}---')
            asyncio.run(main())
            print(f'Disconected: ---{datetime.datetime.utcnow().strftime("%c")}---')
        except Exception as e:
            print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            traceback.print_exc()
        print("Waiting for restart (30 seconds)")
        time.sleep(30)
