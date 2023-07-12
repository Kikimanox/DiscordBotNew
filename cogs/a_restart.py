import asyncio
import os
import subprocess

from discord.ext import commands

from utils.checks import dev_check
from utils.dataIOa import dataIOa


class ARestart(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.check(dev_check)
    @commands.command()
    async def arestart(self, ctx, options: str = ""):
        """Restart the bot and git pull changes.

        Use "v" for verbose,
        Use "u" for update
        Use "vu"/"uv" for both """
        if "u" in options:
            if self.bot.config['NEW_MAIN_D']:
                os.rename(self.bot.config['NEW_MAIN_D'], 'main_d3.py')
            if self.bot.config['NEW_BOT_LOOP']:
                os.rename(self.bot.config['NEW_BOT_LOOP'], 'bot_loop3.py')
            await ctx.send("Running `git pull`...")
            loop = asyncio.get_event_loop()
            process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)
            stdout, stderr = await loop.run_in_executor(None, process.communicate)
            if "v" in options:
                a = stdout.decode(encoding='utf8') if stdout is not None else ""
                b = stderr.decode(encoding='utf8') if stderr is not None else ""
                a = f'{a}\n{b}' if b else a
                if len(a) > 1900: a = a[:1900] + "\n\n...Content longer than 1900 chars"
                await ctx.send(f"```{a}```")
            else:
                await ctx.send("Git pulled.")
            if self.bot.config['NEW_MAIN_D']:
                os.rename('main_d3.py', self.bot.config['NEW_MAIN_D'])
            if self.bot.config['NEW_BOT_LOOP']:
                os.rename('bot_loop3.py', self.bot.config['NEW_BOT_LOOP'])
        await ctx.send("Restarting...")
        restarT = {"guild": ctx.guild.id, "channel": ctx.channel.id}
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
