import glob
import io
import math
import os
# Common imports that can be used by the debugger.
import re
import shutil
import textwrap
import traceback
from contextlib import redirect_stdout

import aiohttp
import discord
from utils.dataIOa import dataIOa
import asyncio
from discord.ext import commands

import utils.discordUtils as dutils

'''Module for the python interpreter as well as saving, loading, viewing, etc. the cmds/_scripts ran with the 
interpreter. '''


def owner_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID']


class Debugger(commands.Cog):

    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot
        self.channel = None
        self._last_result = None

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    # Executes/evaluates code.Pretty much the same as Rapptz implementation for RoboDanny with slight variations.
    async def interpreter(self, env, code, ctx):
        body = self.cleanup_code(code)
        stdout = io.StringIO()

        os.chdir(os.getcwd())
        if not os.path.exists('%s/_scripts' % os.getcwd()):
            os.makedirs('%s/_scripts' % os.getcwd())
        with open('%s/_scripts/temp.txt' % os.getcwd(), 'w') as temp:
            temp.write(body)

        to_compile = 'async def func():\n{}'.format(textwrap.indent(body, "  "))

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send('```\n{}: {}\n```'.format(e.__class__.__name__, e))

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send('```\n{}{}\n```'.format(value, traceback.format_exc()))
        else:
            value = stdout.getvalue()

            result = None
            if ret is None:
                if value:
                    result = '```\n{}\n```'.format(value)
                else:
                    try:
                        result = '```\n{}\n```'.format(repr(eval(body, env)))
                    except:
                        pass
            else:
                self._last_result = ret
                result = '```\n{}{}\n```'.format(value, ret)

            if result:
                if len(str(result)) > 1950:
                    async with aiohttp.ClientSession() as session:
                        async with session.post("https://hastebin.com/documents",
                                                data=str(result).encode('utf-8')) as resp:
                            if resp.status == 200:
                                haste_out = await resp.json()
                                url = "https://hastebin.com/" + haste_out["key"]
                            else:
                                with open("tmp/py_output.txt", "w") as f:
                                    f.write(str(result))
                                with open("tmp/py_output.txt", "rb") as f:
                                    py_output = discord.File(f, "py_output.txt")
                                    await ctx.send(
                                        content="Error posting to hastebin. Uploaded output to file instead.",
                                        file=py_output)
                                    os.remove("tmp/py_output.txt")
                                    return
                    result = 'Large output. Posted to Hastebin: %s' % url
                    await ctx.send(result)

                else:
                    await ctx.send(result)
            else:
                await ctx.send("```\n```")

    @commands.check(owner_check)
    @commands.group(pass_context=True, invoke_without_command=True)
    async def py(self, ctx, *, msg=""):
        """Python interpreter. [Bot owner only]"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'server': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())
        if msg.strip() == "" and len(ctx.message.attachments) == 1:
            file = await ctx.message.attachments[0].to_file()
            msg = file.fp.read().decode('utf-8')

        if msg.strip() == "" and len(ctx.message.attachments) == 1:
            file = await ctx.message.attachments[0].to_file()
            msg = file.fp.read().decode('utf-8')

        await self.interpreter(env, msg, ctx)

    # Save last [p]py cmd/script.
    @commands.check(owner_check)
    @py.command(pass_context=True)
    async def save(self, ctx, *, msg):
        """Save the code you last ran. Ex: [p]py save stuff"""
        msg = msg.strip()[:-4] if msg.strip().endswith('.txt') else msg.strip()
        os.chdir(os.getcwd())
        if not os.path.exists('%s/_scripts/temp.txt' % os.getcwd()):
            return await ctx.send('Nothing to save. Run a ``>py`` cmd/script first.')
        if not os.path.isdir('%s/_scripts/save/' % os.getcwd()):
            os.makedirs('%s/_scripts/save/' % os.getcwd())
        if os.path.exists('%s/_scripts/save/%s.txt' % (os.getcwd(), msg)):
            await ctx.send('``%s.txt`` already exists. Overwrite? ``y/n``.' % msg)
            reply = await self.bot.wait_for('message', check=lambda m: m.author == ctx.message.author and (
                    m.content.lower() == 'y' or m.content.lower() == 'n'))
            if reply.content.lower().strip() != 'y':
                return await ctx.send('Cancelled.')
            if os.path.exists('%s/_scripts/save/%s.txt' % (os.getcwd(), msg)):
                os.remove('%s/_scripts/save/%s.txt' % (os.getcwd(), msg))

        try:
            shutil.move('%s/_scripts/temp.txt' % os.getcwd(), '%s/_scripts/save/%s.txt' % (os.getcwd(), msg))
            await ctx.send('Saved last run cmd/script as ``%s.txt``' % msg)
        except:
            await ctx.send('Error saving file as ``%s.txt``' % msg)

    # Load a cmd/script saved with the [p]save cmd
    @commands.check(owner_check)
    @py.command(aliases=['start'], pass_context=True)
    async def run(self, ctx, *, msg):
        """Run code that you saved with the save commmand. Ex: [p]py run stuff parameter1 parameter2"""
        # Like in unix, the first parameter is the script name
        parameters = msg.split()
        save_file = parameters[0]  # Force scope
        if save_file.endswith('.txt'):
            save_file = save_file[:-(len('.txt'))]  # Temptation to put '.txt' in a constant increases
        else:
            parameters[0] += '.txt'  # The script name is always full

        if not os.path.exists('%s/_scripts/save/%s.txt' % (os.getcwd(), save_file)):
            return await ctx.send('Could not find file ``%s.txt``' % save_file)

        script = open('%s/_scripts/save/%s.txt' % (os.getcwd(), save_file)).read()

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'server': ctx.guild,
            'message': ctx.message,
            '_': self._last_result,
            'argv': parameters
        }

        env.update(globals())

        await self.interpreter(env, script, ctx)

    # List saved cmd/_scripts
    @commands.check(owner_check)
    @py.command(aliases=['ls'], pass_context=True)
    async def list(self, ctx, page: str = None):
        """List all saved _scripts. Ex: [p]py list or [p]py ls"""
        try:
            if page:
                numb = page.strip()
                if numb.isdigit():
                    numb = int(numb)
                else:
                    await ctx.send('Invalid syntax. Ex: ``>py list 1``')
            else:
                numb = 1
            filelist = glob.glob('_scripts/save/*.txt')
            if len(filelist) == 0:
                return await ctx.send('No saved cmd/_scripts.')
            filelist.sort()
            msg = ''
            pages = int(math.ceil(len(filelist) / 10))
            if numb < 1:
                numb = 1
            elif numb > pages:
                numb = pages

            for i in range(10):
                try:
                    msg += filelist[i + (10 * (numb - 1))][13:] + '\n'
                except:
                    break

            await ctx.send('List of saved cmd/_scripts. Page ``%s of %s`` ```%s```' % (numb, pages, msg))
        except Exception as e:
            await ctx.send('Error, something went wrong: ``%s``' % e)

    # View a saved cmd/script
    @commands.check(owner_check)
    @py.group(aliases=['vi', 'vim', 'cat'], pass_context=True)
    async def view(self, ctx, *, msg: str):
        """View a saved script's contents. Ex: [p]py view stuff"""
        msg = msg.strip()[:-4] if msg.strip().endswith('.txt') else msg.strip()
        try:
            if os.path.isfile('_scripts/save/%s.txt' % msg):
                f = open('_scripts/save/%s.txt' % msg, 'r').read()
                await ctx.send('Viewing ``%s.txt``: ```py\n%s```' % (msg, f.strip('` ')))
            else:
                await ctx.send('``%s.txt`` does not exist.' % msg)

        except Exception as e:
            await ctx.send('Error, something went wrong: ``%s``' % e)

    # Delete a saved cmd/script
    @commands.check(owner_check)
    @py.group(aliases=['rm'], pass_context=True)
    async def delete(self, ctx, *, msg: str):
        """Delete a saved script. Ex: [p]py delete stuff"""
        msg = msg.strip()[:-4] if msg.strip().endswith('.txt') else msg.strip()
        try:
            if os.path.isfile('_scripts/save/%s.txt' % msg):
                os.remove('_scripts/save/%s.txt' % msg)
                await ctx.send('Deleted ``%s.txt`` from saves.' % msg)
            else:
                await ctx.send('``%s.txt`` does not exist.' % msg)
        except Exception as e:
            await ctx.send('Error, something went wrong: ``%s``' % e)

    @commands.check(owner_check)
    @commands.command()
    async def tail(self, ctx, lines: int, directory: str, log_group: str = None):
        """Do tail on a log file

        lines = how much last lines
        directory = which dir
        log_group = (optional) which log group"""
        if not log_group:
            log_group = directory
        directories = os.listdir("logs")
        if directory in directories:
            curr_dir = f"logs/{directory}"
            nested_directory = os.listdir(curr_dir)
            available_logs = []

            for logfile in nested_directory:
                if logfile.startswith(log_group):
                    available_logs.append(logfile)

            def nat_log_sort(name):
                numbers = re.findall("([0-9]+)", name)
                return int(numbers[-1]) if numbers else 0

            available_logs.sort(key=nat_log_sort)

            if available_logs:
                log_lines = []
                for logfile in available_logs:
                    with open(f"{curr_dir}/{logfile}", "r") as f:
                        temporary_lines = f.read().splitlines()
                        lines_left = lines - len(log_lines)
                        log_lines = temporary_lines[-lines_left:] + log_lines
                        if len(log_lines) >= lines:
                            break

                result = "\n".join(log_lines)
                result = result.replace('@', '@\u200b')
                return await dutils.result_printer(ctx, f"```shell\n{result}```")
            else:
                return await ctx.send(f"No logs found in `logs/{directory}` for `{log_group}`.")
        else:
            return await ctx.send(f"Incorrect folder specified. Options are: `{directories}`")


async def setup(bot):
    debug_cog = Debugger(bot)
    await bot.add_cog(debug_cog)
