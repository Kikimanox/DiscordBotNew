import asyncio
import logging
import os
import shutil
import subprocess
import traceback

from discord.ext import commands

import utils.checks as checks
from utils.dataIOa import dataIOa

error_logger = logging.getLogger('error')


class ARestart(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.check(checks.dev_check)
    @commands.command()
    async def arestart(self, ctx, options: str = ""):
        """Restart the bot and git pull changes.

        Use "v" for verbose,
        Use "u" for update
        Use "vu"/"uv" for both """
        if "u" in options:
            # check for git BEFORE renaming anything, otherwise a failure leaves the files renamed
            if shutil.which("git") is None or not os.path.isdir(".git"):
                return await ctx.send("⚠ Can't update: `git` is not installed here or this folder is not a git "
                                      "repository (e.g. inside a docker container). Update the code on the host "
                                      "and use the restart command without `u`. Nothing was changed or restarted.")
            renamed = []
            try:
                if self.bot.config['NEW_MAIN_D'] and os.path.exists(self.bot.config['NEW_MAIN_D']):
                    os.replace(self.bot.config['NEW_MAIN_D'], 'main_d3.py')
                    renamed.append((self.bot.config['NEW_MAIN_D'], 'main_d3.py'))
                if self.bot.config['NEW_BOT_LOOP'] and os.path.exists(self.bot.config['NEW_BOT_LOOP']):
                    os.replace(self.bot.config['NEW_BOT_LOOP'], 'bot_loop3.py')
                    renamed.append((self.bot.config['NEW_BOT_LOOP'], 'bot_loop3.py'))
                await ctx.send("Running `git pull`...")
                loop = asyncio.get_event_loop()
                process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = await loop.run_in_executor(None, process.communicate)
                a = stdout.decode(encoding='utf8') if stdout is not None else ""
                b = stderr.decode(encoding='utf8') if stderr is not None else ""
                a = f'{a}\n{b}' if b else a
                if len(a) > 1900: a = a[:1900] + "\n\n...Content longer than 1900 chars"
                if process.returncode != 0:
                    return await ctx.send(f"⚠ `git pull` failed, not restarting:\n```{a}```")
                if "v" in options:
                    await ctx.send(f"```{a}```")
                else:
                    await ctx.send("Git pulled.")
            finally:
                # always put the custom file names back, even if something above failed
                for original, tmp_name in renamed:
                    try:
                        os.replace(tmp_name, original)
                    except Exception:
                        error_logger.error(f"Failed renaming {tmp_name} back to {original}\n{traceback.format_exc()}")
        await ctx.send("Restarting...")
        restarT = {"guild": ctx.guild.id if ctx.guild else None, "channel": ctx.channel.id}
        dataIOa.save_json("restart.json", restarT)
        for t in self.bot.running_tasks:
            try:
                t.cancel()
            except:
                pass
        os._exit(0)


async def setup(bot: commands.Bot):
    ext = ARestart(bot)
    await bot.add_cog(ext)
