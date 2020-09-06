import time

import discord
import pyimgur
from discord.ext import commands
from discord import Embed, abc, File, Member
import aiohttp
import datetime
import asyncio
import utils.timeStuff as tutils
# import utils.discordUtils as dutils
import re
from datetime import timedelta
import traceback
import os
from discord.ext.commands.help import DefaultHelpCommand
import sys
import asyncio
import random
import signal
import subprocess
import git
import re
from utils.checks import owner_check, admin_check
from utils.help import Help
import logging
import logging.handlers as handlers
from utils.dataIOa import dataIOa
import fileinput
import importlib

Prefix = dataIOa.load_json('config.json')['BOT_PREFIX']


def get_pre(_bot, _message): return Prefix


bot = commands.Bot(command_prefix=get_pre)
###
bot.all_cmds = {}
bot.from_serversetup = {}
bot.running_tasks = []
###
bot.config = dataIOa.load_json('config.json')
bot.config['BOT_DEFAULT_EMBED_COLOR'] = int(f"0x{bot.config['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16)
bot.help_command = Help()


@bot.event
async def on_ready():
    ###
    if hasattr(bot, 'all_cmds') and not bot.all_cmds: bot.all_cmds = {}
    if hasattr(bot, 'from_serversetup') and not bot.from_serversetup: bot.from_serversetup = {}
    if hasattr(bot, 'running_tasks') and not bot.running_tasks: bot.running_tasks = []
    ###
    bot.config = dataIOa.load_json('config.json')
    bot.config['BOT_DEFAULT_EMBED_COLOR'] = int(f"0x{bot.config['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16)
    bot.uptime = datetime.datetime.utcnow()
    bot.ranCommands = 0
    bot.help_command = Help()
    bot.logger = logging.getLogger('my_app')
    bot.logger.setLevel(logging.INFO)

    # log formatter -> Credit: appu#4444
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    if not os.path.exists("logs"):
        os.makedirs("logs/error")
        os.makedirs("logs/info")
        os.makedirs("logs/workers")
    logHandler = handlers.RotatingFileHandler('logs/info/info.log', maxBytes=5000, backupCount=10, encoding='utf-8')
    logHandler.setLevel(logging.INFO)
    logHandler.setFormatter(formatter)
    errorLogHandler = handlers.RotatingFileHandler('logs/error/error.log', maxBytes=5000, backupCount=10,
                                                   encoding='utf-8')
    errorLogHandler.setLevel(logging.ERROR)
    errorLogHandler.setFormatter(formatter)

    # fixes bug when bot restarted but log file retained loghandler. this will remove any
    # handlers it already had and replace with new ones initialized above
    for hdlr in list(bot.logger.handlers):
        print(hdlr)
        bot.logger.removeHandler(hdlr)
    bot.logger.addHandler(logHandler)
    bot.logger.addHandler(errorLogHandler)
    bot.help_command = Help()
    bot.logger.info("Bot logged in and ready.")
    print(discord.utils.oauth_url(bot.user.id) + '&permissions=8')
    print('------------------------------------------')
    if os.path.isfile("restart.json"):
        restartData = dataIOa.load_json("restart.json")
        try:
            guild = bot.get_guild(restartData["guild"])
            channel = guild.get_channel(restartData["channel"])
            await channel.send("Restarted.")
        except:
            trace = traceback.format_exc()
            bot.logger.error(trace)
            print(trace)
            print("couldn't send restarted message to channel.")
        finally:
            os.remove("restart.json")


def exit_bot(self):
    # if os.name != 'nt': In case you need to kill some other tasks
    #     try:
    #         os.killpg(0, signal.SIGKILL)
    #     except:
    #         print("error in and killing background tasks on exit")
    #         bot.logger.error("Error in exit_bot")
    #         trace = traceback.format_exc()
    #         bot.logger.error(trace)
    #         print(trace)
    for t in bot.running_tasks:
        try:
            t.cancel()
        except:
            pass
    os._exit(0)


@commands.check(admin_check)
@bot.command()
async def prefix(ctx, new_prefix=""):
    """Check or change the prefix"""
    if not new_prefix:
        return await ctx.send(embed=Embed(title='My prefix is', description=bot.config['BOT_PREFIX']))
    if bot.config['BOT_PREFIX'] == new_prefix: return await ctx.send(
        "Why are you trying to make the new prefix the same "
        "as the previous one?")
    bot.config['BOT_PREFIX'] = new_prefix
    dataIOa.save_json("config.json", bot.config)
    global Prefix
    Prefix = new_prefix
    await ctx.send("Prefix changed.")


@bot.event
async def on_message(message):
    if not bot.is_ready():
        await bot.wait_until_ready()
    if not message.guild and message.author.id != bot.config['CLIENT_ID']:
        print(f'DM LOG: {str(message.author)} (id: {message.author.id}) sent me this: {message.content}')

    if message.content == f'<@!{bot.config["CLIENT_ID"]}>': return await message.channel.send(
        embed=(
            Embed(title='My prefix is', description=bot.config['BOT_PREFIX']).set_footer(text='You can change it with '
                                                                                              f'{bot.config["BOT_PREFIX"]}prefix')))

    if message.content.startswith(bot.config['BOT_PREFIX']) or message.content.split(' ')[0] == \
            f'<@!{bot.config["CLIENT_ID"]}>':
        pfx_len = len(bot.config['BOT_PREFIX']) if message.content.startswith(bot.config['BOT_PREFIX']) else len(
            f'<@!{bot.config["CLIENT_ID"]}>') + 1
        possible_cmd = message.content[pfx_len:].split(' ')[0]
        if possible_cmd in bot.all_commands:
            if hasattr(bot, 'ranCommands'): bot.ranCommands += 1
            return await bot.process_commands(message)
        if message.guild and message.guild.id in bot.all_cmds:
            ctype = -1  # 1 possible_cmd | 2 mutli word | 3 same as 0 but inh | 4 same as 1 but inh
            if possible_cmd in bot.all_cmds[message.guild.id]['cmds_name_list']:
                ctype = 1
            elif message.content[pfx_len:] in bot.all_cmds[message.guild.id]['cmds_name_list']:
                ctype = 2
            elif possible_cmd in bot.all_cmds[message.guild.id]['inh_cmds_name_list']:
                ctype = 3
            elif message.content[pfx_len:] in bot.all_cmds[message.guild.id]['inh_cmds_name_list']:
                ctype = 4

            if ctype != -1:
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
    bot.logger.info("Shut down.")
    exit_bot(0)


@bot.event
async def on_command_error(ctx, error):
    if not bot.is_ready():
        await bot.wait_until_ready()
    error = getattr(error, "original", error)
    if isinstance(error, commands.errors.CommandNotFound):
        pass
    elif isinstance(error, commands.CommandInvokeError):
        print("Command invoke error exception in command '{}', {}".format(ctx.command.qualified_name, str(error)))
    elif isinstance(error, commands.CommandOnCooldown):
        extra = ""
        if error.cooldown.type.name != 'default':
            extra += f" ({error.cooldown.type.name} cooldown)"
        await ctx.send(f"⏲ Command on cooldown, try again"
                       f" in {error.args[0].split(' in ')[-1]}" + extra, delete_after=5)
    elif isinstance(error, commands.errors.CheckFailure):
        await ctx.send("⚠ You don't have permissions to use that command.")
        bot.logger.error('CMD ERROR', 'NoPerms',
                         f'{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}', ctx)
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        formatter = Help()
        help_msg = await formatter.format_help_for(ctx, ctx.command)
        await ctx.send(content="Missing required arguments. Command info:", embed=help_msg[0])
        bot.logger.error('CMD ERROR MissingArgs '
                         f'{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}')
    elif isinstance(error, commands.errors.BadArgument):
        formatter = Help()
        help_msg = await formatter.format_help_for(ctx, ctx.command)
        await ctx.send(content="⚠ You have provided an invalid argument. Command info:", embed=help_msg[0])
        bot.logger.error('CMD ERROR BadArg '
                         f'{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}')
    elif isinstance(error, commands.errors.MaxConcurrencyReached):
        await ctx.send(f"This command has reached the max number of concurrent jobs: "
                       f"`{error.number}`. Please wait for the running commands to finish before requesting again.")
    else:
        await ctx.send("An unknown error occurred with the `{}` command.".format(ctx.command.name))
        trace = traceback.format_exception(type(error), error, error.__traceback__)
        trace_str = "".join(trace)
        print(trace_str)
        print("Other exception in command '{}', {}".format(ctx.command.qualified_name, str(error)))
        bot.logger.error(
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
        bot.logger.error(f"---------- CRASHED ----------: {exc_type}")
        print("exception occurred, restarting...")
        bot.logger.error("exception occurred, restarting bot")
        exit_bot(0)
    else:
        trace = traceback.format_exc()
        bot.logger.error(f"---------- ERROR ----------: {trace}")
        print(trace)


@bot.before_invoke
async def before_any_command(ctx):
    if not bot.is_ready():
        await bot.wait_until_ready()
    if hasattr(bot, 'logger'):
        bot.logger.info(f"Command invoked: {ctx.command} | By user: {str(ctx.author)} (id: {str(ctx.author.id)}) "
                        f"| Message: {ctx.message.content}")


def load_all_cogs_except(cogs_to_exclude):
    for extension in os.listdir("cogs"):
        if extension.endswith('.py'):
            if extension[:-3] not in cogs_to_exclude:
                try:
                    bot.load_extension("cogs." + extension[:-3])
                except Exception as e:
                    traceback.print_exc()


if __name__ == '__main__':
    while True:
        try:
            load_all_cogs_except(['_newCogTemplate'])
            if os.name != 'nt':
                os.setpgrp()
            loop = asyncio.get_event_loop()
            config = dataIOa.load_json("config.json")
            loop.run_until_complete(bot.login(config['BOT_TOKEN']))
            print(f'Connected: ---{datetime.datetime.now().strftime("%c")}---')
            loop.run_until_complete(bot.connect())
            print(f'Disconected: ---{datetime.datetime.now().strftime("%c")}---')
        except Exception as e:
            traceback.print_exc()
        print("Waiting for restart (30 seconds)")
        time.sleep(30)
