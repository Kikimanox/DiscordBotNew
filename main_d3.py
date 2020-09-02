import time

import env
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
from utils.checks import owner_check
from utils.help import Help
import logging
import logging.handlers as handlers
from utils.dataIOa import dataIOa

bot = commands.Bot(command_prefix=env.BOT_PREFIX)

@bot.event
async def on_ready():
    bot.help_command = Help()
    bot.my_globals = {'current_tasks': []}
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
    bot.logger.info("bot logged in and ready")
    print('logged in')
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
    os._exit(0)

@commands.check(owner_check)
@bot.command()
async def restart(ctx, options: str = ""):
    """Restart the bot and git pull changes.

    Use "v" for verbose,
    Use "u" for update
    Use "vu"/"uv" for both """
    if "u" in options:
        if env.NEW_MAIN_D:
            os.rename(env.NEW_MAIN_D, 'main_d3.py')
        if env.NEW_BOT_LOOP:
            os.rename(env.NEW_BOT_LOOP, 'bot_loop3.py')
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
        if env.NEW_MAIN_D:
            os.rename('main_d3.py', env.NEW_MAIN_D)
        if env.NEW_BOT_LOOP:
            os.rename('bot_loop3.py', env.NEW_BOT_LOOP)
    await ctx.send("Restarting...")
    restart = {"guild": ctx.guild.id, "channel": ctx.channel.id}
    dataIOa.save_json("restart.json", restart)
    exit_bot(0)

@commands.check(owner_check)
@bot.command(aliases=["shutdown", "exit", "terminate"])
async def quit(ctx):
    """Shut down the bot. [Bot owner only]"""
    with open('quit.txt', 'w', encoding="utf8") as q:
        q.write('.')
    await ctx.send("Shut down.")
    bot.logger.info("Shut down.")
    exit_bot(0)


# def receiveSignal(sigNum, frame):
#     print('Received signal: ' + str(sigNum))
#     for t in bot.my_globals['current_tasks']: t.cancel()
#     print('shutting down')
#     sys.exit(0)


def load_extensions(cogs):
    try:
        for c in cogs:
            pass
    except Exception as e:
        traceback.print_exc()

if __name__ == '__main__':
    while True:
        try:
            # load_extensions(['aa', 'aaa'])
            if os.name != 'nt':
                os.setpgrp()
            # signal.signal(signal.SIGTERM, receiveSignal)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(bot.login(env.BOT_TOKEN))
            print(f'Connected: ---{datetime.datetime.now().strftime("%c")}---')
            loop.run_until_complete(bot.connect())
            print(f'Disconected: ---{datetime.datetime.now().strftime("%c")}---')
        except Exception as e:
            traceback.print_exc()
        print("Waiting for restart (30 seconds)")
        time.sleep(30)
