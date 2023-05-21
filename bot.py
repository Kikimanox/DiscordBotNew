import logging
import os
import traceback
from datetime import datetime
from typing import Union, List

from discord import Message, Interaction, app_commands, utils, Reaction, Member, User
from discord.ext import commands
from discord.ext.commands import errors

from models.afking import AfkManager
from models.antiraid import ArManager
from models.reactionroles import RRManager
from utils.context import Context
from utils.dataIOa import dataIOa
from utils.help import Help

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class KanaIsTheBest(commands.Bot):
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            *args,
            **kwargs,
        )
        self.react_delete: dict = {}

        self.all_cmds = {}
        self.running_tasks = []
        self.from_serversetup = {}
        self.running_chapters = {}
        self.chapters_json = {}
        self.anti_raid = ArManager.get_ar_data()
        self.currently_afk = AfkManager.return_whole_afk_list()
        self.moderation_blacklist = {-1: "dummy"}
        self.reaction_roles = RRManager.return_whole_rr_list()
        ###
        self.config = dataIOa.load_json("config.json")
        self.config["BOT_DEFAULT_EMBED_COLOR"] = int(
            f"0x{self.config['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16
        )
        self.help_command = Help()
        self.before_run_cmd = 0
        self.just_banned_by_bot = {}
        self.just_kicked_by_bot = {}
        self.just_muted_by_bot = {}
        self.banned_cuz_blacklist = {}

        self.emote_servers_tmp = [
            777942981197299732,
            777943001539411968,
            777943027241975828,
            777943043223060511,
            777943082300604447,
            777943112764489769,
            1102341791312773191,
            1102341945499586600,
            1102341791312773191
        ]
        self.emote_servers_perm = [777943294353080380]
        self.uptime = datetime.utcnow()

    async def setup_hook(self) -> None:
        await self.load_all_cogs_except(["_newCogTemplate", "manga", "bets"])
        # if os.name != "nt":
        #     os.setpgrp()

        # config = dataIOa.load_json("config.json")

        # Temporarily adding manga and bets only to ai bot ~~and dev bot~~
        # if config["CLIENT_ID"] in [705157369130123346, 589921811349635072]:
        #     await self.load_extension("cogs.manga")
        #     await self.load_extension("cogs.bets")

    async def on_ready(self):
        if hasattr(self, "all_cmds") and not self.all_cmds:
            self.all_cmds = {}
        if hasattr(self, "running_tasks") and not self.running_tasks:
            self.running_tasks = []
        if hasattr(self, "from_serversetup") and not self.from_serversetup:
            self.from_serversetup = {}
        if hasattr(self, "running_chapters") and not self.from_serversetup:
            self.running_chapters = {}
        if hasattr(self, "chapters_json") and not self.from_serversetup:
            self.chapters_json = {}
        if hasattr(self, "anti_raid") and not self.anti_raid:
            self.anti_raid = ArManager.get_ar_data()
        if hasattr(self, "currently_afk") and not self.currently_afk:
            self.currently_afk = AfkManager.return_whole_afk_list()
        if hasattr(self, "moderation_blacklist") and not self.moderation_blacklist:
            self.moderation_blacklist = {-1: "dummy"}
        if hasattr(self, "reaction_roles") and not self.reaction_roles:
            self.reaction_roles = RRManager.return_whole_rr_list()
        ###
        self.config = dataIOa.load_json("config.json")
        self.config["BOT_DEFAULT_EMBED_COLOR"] = int(
            f"0x{self.config['BOT_DEFAULT_EMBED_COLOR_STR'][-6:]}", 16
        )

        # bot.ranCommands = 0
        self.help_command = Help()

        logger.info("Bot logged in and ready.")
        print(utils.oauth_url(self.user.id) + "&permissions=8")
        print("------------------------------------------")
        if os.path.isfile("restart.json"):
            restartData = dataIOa.load_json("restart.json")
            try:
                guild = self.get_guild(restartData["guild"])
                if guild is not None:
                    channel = guild.get_channel(restartData["channel"])
                    if channel is not None:
                        await channel.send("Restarted.")
            except Exception as ex:
                print(f"{ex}")
                print(f'---{datetime.utcnow().strftime("%c")}---')
                trace = traceback.format_exc()
                error_logger.error(trace)
                print(trace)
                print("couldn't send restarted message to channel.")
            finally:
                os.remove("restart.json")

    async def on_reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        if user != self.user:
            if reaction.emoji == str("\N{CROSS MARK}"):
                author_id = self.react_delete.get(reaction.message.id)
                if author_id is not None and author_id == user.id:
                    await reaction.message.delete()
                    self.react_delete.pop(reaction.message.id)

    async def load_all_cogs_except(self, cogs_to_exclude: List[str]):
        for extension in os.listdir("cogs"):
            if extension.endswith(".py"):
                if extension[:-3] not in cogs_to_exclude:
                    try:
                        await self.load_extension("cogs." + extension[:-3])
                    except Exception as ex:
                        print(f'---{datetime.utcnow().strftime("%c")}---')
                        traceback.print_exc()
                        error_message = "".join(
                            traceback.format_exception(None, ex, ex.__traceback__)
                        )
                        error_logger.error(error_message)

    async def get_context(
        self, origin: Union[Message, Interaction], /, *, cls=Context
    ) -> Context:
        return await super().get_context(origin, cls=cls)

    async def on_command_error(
        self,
        ctx: Context,
        exception: errors.CommandError,
    ) -> None:
        if not self.is_ready():
            await self.wait_until_ready()

        error = getattr(exception, "original", exception)

        if isinstance(error, commands.errors.CommandNotFound):
            pass
        elif isinstance(error, commands.MissingRole):
            await ctx.send(
                "You don't have the right role to invoke the command", delete_after=10
            )
        elif isinstance(error, app_commands.MissingRole):
            await ctx.send(
                "You don't have the right role to invoke the command", delete_after=10
            )
        elif isinstance(error, commands.CommandInvokeError):
            # print("Command invoke error exception in command '{}', {}"
            # .format(ctx.command.qualified_name, str(error)))
            logger.info(
                "Command invoke error exception in command '{}', "
                "{}".format(ctx.command.qualified_name, str(error))
            )
        elif isinstance(error, commands.CommandOnCooldown):
            extra = ""
            time_until = float("{:.2f}".format(error.retry_after))
            await ctx.send(
                f"⏲ Command on cooldown, try again" f" in **{time_until}s**" + extra,
                delete_after=10,
            )
        elif isinstance(error, commands.errors.CheckFailure):
            if ctx.command.qualified_name == "getrole booster":
                await ctx.send(content="⚠ Only server boosters may use this command.")
                return
            await ctx.send(
                "⚠ You don't have permissions to use that command.", delete_after=10
            )
            error_logger.error(
                "CMD ERROR NoPerms"
                f"{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}"
            )
        elif isinstance(error, app_commands.CheckFailure):
            if ctx.command.qualified_name == "getrole booster":
                await ctx.send(content="⚠ Only server boosters may use this command.")
                return
            await ctx.send(
                "⚠ You don't have permissions to use that command.", delete_after=10
            )
            error_logger.error(
                "CMD ERROR NoPerms"
                f"{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}"
            )
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            formatter = Help()

            help_msg = await formatter.format_help_for(ctx, ctx.command)

            await ctx.send(
                content="Missing required arguments. Command info:",
                embed=help_msg[0],
                delete_after=60,
            )

            error_logger.error(
                "CMD ERROR MissingArgs "
                f"{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}"
            )
        elif isinstance(error, commands.errors.BadArgument):
            formatter = Help()
            help_msg = await formatter.format_help_for(ctx, ctx.command)

            await ctx.send(
                content="⚠ You have provided an invalid argument. Command info:",
                embed=help_msg[0],
                delete_after=60,
            )
            error_logger.error(
                "CMD ERROR BadArg "
                f"{ctx.author} ({ctx.author.id}) tried to invoke: {ctx.message.content}"
            )
        elif isinstance(error, commands.errors.MaxConcurrencyReached):
            if ctx.command.qualified_name == "getrole booster":
                await ctx.send(
                    self.config["BOOSTER_CUSTOM_ROLES_GETTER"][str(ctx.guild.id)][
                        "WARN_MSG"
                    ],
                    delete_after=60,
                )
                return

            await ctx.send(
                f"This command has reached the max number of concurrent jobs: "
                f"`{error.number}`. Please wait for the running commands to finish before requesting again.",
                delete_after=60,
            )
        else:
            await ctx.send(
                "An unknown error occurred with the `{}` command.".format(
                    ctx.command.name
                ),
                delete_after=60,
            )
            trace = traceback.format_exception(type(error), error, error.__traceback__)
            trace_str = "".join(trace)
            print(f'---{datetime.utcnow().strftime("%c")}---')
            print(trace_str)
            print(
                "Other exception in command '{}', {}".format(
                    ctx.command.qualified_name, str(error)
                )
            )
            error_logger.error(
                f"Command invoked but FAILED: {ctx.command} | By user: {ctx.author} (id: {str(ctx.author.id)}) "
                f"| Message: {ctx.message.content} | "
                f"Error: {trace_str}"
            )
