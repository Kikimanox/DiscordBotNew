import asyncio
import re
import traceback
from copy import deepcopy
from datetime import datetime

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.SimplePaginator import SimplePaginator
from utils.dataIOa import dataIOa as dataIO
from utils.dataIOa import dataIOa as dataIOa
import utils.checks as checks

import logging

logger = logging.getLogger('info')
error_logger = logging.getLogger('error')


class Bets2(commands.Cog):
    def __init__(self, bot):
        # self.highlights_lock = asyncio.Lock()
        bot.watched_bets = dataIOa.load_json("data/bets.json")
        self.bot = bot
        self.bet_channel = 870272970642292736
        self.bot_channel = 695297906529271888
        self.bet_winner_ch = 695298133885714444

        # self.bet_channel = 824466316362514453
        # self.bot_channel = 824466316362514453
        # self.bet_winner_ch = 824466316362514453

    @commands.group(aliases=["bets"], invoke_without_command=True)
    async def bet(self, ctx, *, msg: str = ""):
        """Make a bet/view bets. [p]help bet for more detailed info on how to make bets and more.

        ----Viewing your points and your rank in the leaderboards----
        .bet - This will bring up the leaderboards. React to flip through the pages and see your own rank vs. others.

        ----Making a bet----
        This is the generic format for making a bet. Follow this exactly:
        .bet <question> (<wager amount>)
        1. <option 1>
        2. <option 2>
        3. <up to 10 total options>

        Example:
        .bet How many chapters will ONK be? (1000)
        1. Over 150 but less than 200
        2. Over 200 but less than 300
        3. Over 300

        If you are not a mod, a mod will have to approve this bet by hitting the ✅ on your message before bets will actually work.
        Once activated, numbers from 1-10 will appear, representing the options in order. React to place your bet on the respective option. You may change your option so long as the bet is open.

        ---Locking/closing a bet----
        Once a bet has been created, the ✅, 🔒, and 🏆 will appear as well.
        Hit the 🔒 reaction to lock a bet. This will prevent people from betting or changing their current bets (stop the betting period).
        Hit the 🏆 reaction to close a bet. This will cause the bot to DM you asking for the winning option. Once that is selected, the bet is now over and closed and the wager amount will have been added/subtracted based on the winners and losers.
        Additionally, hit the ✅ if a bet had been locked previously and you want to reopen for betting again. Note: a closed 🏆 bet cannot be reopened, only 🔒 locked bets.

        Happy gambling! 🍺
        """
        if ctx.invoked_subcommand is None and self.bet_channel is not None:
            if msg and "\n" in msg:
                question, options_str = msg.split("\n", 1)
                options = options_str.split("\n")
                reply_location = ctx if ctx.author.guild_permissions.manage_roles else ctx.author
                if len(options) > 10:
                    return await reply_location.send("Too many options. Please limit to 10.")
                if question.endswith(")") and "(" in question:
                    wager = question[:-1].rsplit("(", 1)[1]
                    if wager.isdigit():
                        wager = int(wager)
                    else:
                        return await reply_location.send(
                            "Invalid wager amount set. Please specify a valid wager after the question. Ex: .bet Some question? (200)\n- option 1\n- option 2")
                else:
                    return await reply_location.send(
                        "Invalid wager amount set. Please specify a valid wager after the question. Ex: .bet Some question? (200)\n- option 1\n- option 2")

                if ctx.author.guild_permissions.manage_roles:
                    bet_loc = ctx.guild.get_channel(self.bet_channel)
                    bet_msg = await bet_loc.send(ctx.message.content.split(" ", 1)[
                                                     1] + "\n--------\nBet status: **OPEN** | You may freely place/change your bets.")
                    self.bot.watched_bets["bets"][str(bet_msg.id)] = {"guild": ctx.guild.id, "channel": bet_loc.id,
                                                                      "jump_url": bet_msg.jump_url,
                                                                      "question": question,
                                                                      "options": {option: {} for option in options},
                                                                      "options_order": options, "status": "open",
                                                                      "wager": wager}
                else:
                    bet_msg = ctx.message
                    self.bot.watched_bets["bets"][str(bet_msg.id)] = {"guild": ctx.guild.id,
                                                                      "channel": ctx.channel.id,
                                                                      "question": question,
                                                                      "options": {option: {} for option in options},
                                                                      "options_order": options,
                                                                      "status": "approval_required", "wager": wager}
                dataIO.save_json("data/bets.json", self.bot.watched_bets)
                if ctx.author.guild_permissions.manage_roles:
                    print(f"Bet created: {bet_msg.id}.")
                    await ctx.message.delete()
                    for i in range(len(options)):
                        if i == 9:
                            await bet_msg.add_reaction("🔟")
                        else:
                            await bet_msg.add_reaction(f"{i + 1}\u20e3")
                else:
                    print(f"Bet created, waiting for approval: {bet_msg.id}.")
                await bet_msg.add_reaction("✅")
                if ctx.author.guild_permissions.manage_roles:
                    await bet_msg.add_reaction("🔒")
                    await bet_msg.add_reaction("🏆")
                try:
                    if ctx.author.guild_permissions.manage_roles:
                        await ctx.author.send(f"{bet_msg.jump_url}\nBet has been created successfully.")
                    else:
                        await ctx.author.send(
                            "Bet was created successfully but awaiting mod approval. Approval is required within 24 hours. Get a mod to approve the bet by hitting the ✅ reaction on it. Once this is done, bets can be placed.")
                except:
                    pass

            if not msg:
                scoreboard_dict = self.bot.watched_bets["scoreboard"]
                if str(ctx.author.id) not in self.bot.watched_bets["scoreboard"]:
                    self.bot.watched_bets["scoreboard"][str(ctx.author.id)] = {"points": 0}
                    dataIO.save_json("data/bets.json", self.bot.watched_bets)
                scores = [[user_id, scoreboard_dict[user_id]["points"]] for user_id in scoreboard_dict]
                scores.sort(key=lambda x: x[1], reverse=True)
                user_rank_index = [i[0] for i in scores].index(str(ctx.author.id))
                if scores[user_rank_index][1] == 0:
                    react = "😕"
                elif user_rank_index + 1 > 10:
                    react = "😐"
                elif 5 < user_rank_index + 1 <= 10:
                    react = "🙂"
                elif 2 < user_rank_index + 1 <= 5:
                    react = "😁"
                elif user_rank_index + 1 == 2:
                    react = "🤑"
                elif user_rank_index + 1 == 1:
                    react = "🍆"
                rank = 1
                entries = []
                for user_id, score in scores:
                    user = ctx.guild.get_member(int(user_id))
                    display_str = f"\n[{rank}]  {str(user)}\n          Score: **{score}**"
                    entries.append(display_str)
                    if rank % 10 == 0 or rank == len(scores):
                        entries.append(
                            f"-------------------------------------\nYour rank:\n{react} Rank: **{user_rank_index + 1}**     Score: **{scores[user_rank_index][1]}**")
                    rank += 1
                await SimplePaginator(entries=entries, colour=0xff0000, title=f"📋 Leaderboard",
                                      length=11).paginate(
                    ctx)

    @commands.check(checks.manage_roles_check)
    @bet.command()
    async def delete(self, ctx, message_id: int):
        """Delete a bet entirely. [Mods only]"""
        if str(message_id) in self.bot.watched_bets["bets"]:
            del self.bot.watched_bets["bets"][str(message_id)]
            dataIO.save_json("data/bets.json", self.bot.watched_bets)
            bet_loc = ctx.guild.get_channel(self.bet_channel)
            msg = await bet_loc.fetch_message(message_id)
            await msg.delete()
            await ctx.send("Deleted bet.")
        else:
            await ctx.send("Could not find bet to delete.")

    @staticmethod
    def check_message_ts(m, user):
        try:
            if (m.author and m.channel and
                    m.author.id == user.id and
                    isinstance(m.channel, discord.DMChannel)):  # and
                # m.channel.recipient and
                # m.channel.recipient.id == user.id):
                return True
            return False
        except AttributeError:
            print("AttributeError encountered.")
            return False

    async def timeshift_bet(self, message_id, user):
        valid_reply = False
        time_shift_confirm = ""
        while not valid_reply:
            reply = await self.bot.wait_for('message', check=lambda m: self.check_message_ts(m, user))

            length = reply.content.strip()
            seconds = 0
            if length == "0":
                valid_reply = True
                return await user.send("Timeshift was not used.")
            else:
                units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
                full_word = {"d": "day", "h": "hour", "m": "minute", "s": "second"}
                match = re.findall("([0-9]+[smhd])", length)  # Thanks to 3dshax server's former bot
                if not match:
                    await user.send(
                        "Could not parse time given. Are you sure you're giving it in the right format? Ex: `1d4h3m2s`, `4h`, `2m30s` etc. Please enter again:")
                else:
                    for item in match:
                        time_shift_confirm += f"{item[:-1]} {full_word[item[-1]]}{'s' if int(item[:-1]) != 1 else ''} "
                        seconds += int(item[:-1]) * units[item[-1]]
                    if (int(datetime.now().timestamp()) - seconds) <= 0:
                        await user.send(
                            "This is not a valid amount of time to go back. Ex: `1d4h3m2s`, `4h`, `2m30s` etc. Please enter again:")
                    else:
                        valid_reply = True
        cutoff_time = int(datetime.now().timestamp()) - seconds
        del_queue = []
        shift_queue = []
        for option in self.bot.watched_bets["bets"][str(message_id)]["options"]:
            for user_id in self.bot.watched_bets["bets"][str(message_id)]["options"][option]:
                if int(self.bot.watched_bets["bets"][str(message_id)]["options"][option][user_id][
                           "last_changed"]) > cutoff_time:
                    if not self.bot.watched_bets["bets"][str(message_id)]["options"][option][user_id]["change_history"]:
                        del_queue.append([option, user_id])
                    else:
                        bkp = None
                        for i, bet_change in enumerate(
                                self.bot.watched_bets["bets"][str(message_id)]["options"][option][user_id][
                                    "change_history"]):
                            if int(bet_change["time"]) < cutoff_time:
                                change_history = \
                                    self.bot.watched_bets["bets"][str(message_id)]["options"][option][user_id][
                                        "change_history"][i:]
                                cutoff_change = change_history.pop(0)
                                option_shift = cutoff_change["option"]
                                bkp = deepcopy(
                                    self.bot.watched_bets["bets"][str(message_id)]["options"][option][user_id])
                                bkp["change_history"] = change_history
                                bkp["last_changed"] = cutoff_change["time"]
                                del_queue.append([option, user_id])
                                shift_queue.append([option_shift, user_id, deepcopy(bkp)])
                                break
                        if not bkp:
                            del_queue.append([option, user_id])
        for option, user_id in del_queue:
            del self.bot.watched_bets["bets"][str(message_id)]["options"][option][user_id]
        for option_shift, user_id, bkp in shift_queue:
            self.bot.watched_bets["bets"][str(message_id)]["options"][option_shift][user_id] = bkp
        await user.send(f"Timeshift complete. Shifted bets back: `{time_shift_confirm}`")

    async def bets_reaction(self, event):
        options_reacts = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣", "🔟"]
        if event.emoji.name in options_reacts and options_reacts.index(event.emoji.name) < len(
                self.bot.watched_bets["bets"][str(event.message_id)]["options"]):
            guild = self.bot.get_guild(self.bot.watched_bets["bets"][str(event.message_id)]["guild"])
            user = guild.get_member(event.user_id)
            channel = self.bot.get_channel(self.bot.watched_bets["bets"][str(event.message_id)]["channel"])
            if self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "open":
                confirmation_msg = f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nFor this bet, you've placed your bet on: "
                change_history = []
                for option in self.bot.watched_bets["bets"][str(event.message_id)]["options"]:
                    if str(event.user_id) in self.bot.watched_bets["bets"][str(event.message_id)]["options"][option]:
                        change_history = \
                            self.bot.watched_bets["bets"][str(event.message_id)]["options"][option][str(event.user_id)][
                                "change_history"]
                        last_changed = \
                            self.bot.watched_bets["bets"][str(event.message_id)]["options"][option][str(event.user_id)][
                                "last_changed"]
                        change_history.insert(0, {"option": option, "time": last_changed})
                        if len(change_history) > 5:
                            change_history = change_history[:-1]
                        del self.bot.watched_bets["bets"][str(event.message_id)]["options"][option][str(event.user_id)]
                        confirmation_msg = confirmation_msg.replace("placed your bet on", "changed your bet to")
                last_changed = int(datetime.now().timestamp())
                wagered_option = self.bot.watched_bets["bets"][str(event.message_id)]["options_order"][
                    options_reacts.index(event.emoji.name)]
                self.bot.watched_bets["bets"][str(event.message_id)]["options"][wagered_option][str(event.user_id)] = {
                    "last_changed": last_changed, "change_history": change_history,
                    "wager": self.bot.watched_bets["bets"][str(event.message_id)]["wager"]}
                print(f"User {user} bet on: {wagered_option} for bet: {event.message_id}")
                if str(event.user_id) not in self.bot.watched_bets["scoreboard"]:
                    self.bot.watched_bets["scoreboard"][str(event.user_id)] = {"points": 0}
                dataIO.save_json("data/bets.json", self.bot.watched_bets)
                try:
                    await user.send(confirmation_msg + wagered_option)
                except:
                    pass
            elif self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "locked":
                try:
                    return await user.send(
                        "This bet is locked so you cannot place/change your bet on this anymore. This is usually done because an outcome of a bet is eminent or major hints on the outcome have been revealed.")
                except:
                    pass
            elif self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "closed":
                try:
                    return await user.send("This bet is closed and over.")
                except:
                    pass
        elif event.emoji.name in ["✅", "🔒", "🏆"]:
            try:
                guild = self.bot.get_guild(self.bot.watched_bets["bets"][str(event.message_id)]["guild"])
                user = guild.get_member(event.user_id)
                channel = self.bot.get_channel(self.bot.watched_bets["bets"][str(event.message_id)]["channel"])
            except:
                trace = traceback.format_exc()
                trace_str = "".join(trace)
                print(f"Error retreiving relevant data for bet message. {trace_str}")
            if user.guild_permissions.manage_channels or event.user_id == 174406433603846145:
                if event.emoji.name == "✅":
                    if self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "closed":
                        try:
                            return await user.send(
                                f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThis bet was closed already and points were already redeemed. Cannot re-open/lock this bet.")
                        except:
                            pass
                    elif self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "approval_required":
                        try:
                            message = await channel.fetch_message(event.message_id)
                        except discord.errors.NotFound:
                            return await user.send("Could not find bet message.")
                        bet_loc = guild.get_channel(self.bet_channel)
                        bet_msg = await bet_loc.send(message.content.split(" ", 1)[
                                                         1] + "\n--------\nBet status: **OPEN** | You may freely place/change your bets.",
                                                     embed=None)
                        self.bot.watched_bets['bets'][str(bet_msg.id)] = deepcopy(
                            self.bot.watched_bets['bets'][str(event.message_id)])
                        del self.bot.watched_bets['bets'][str(event.message_id)]
                        self.bot.watched_bets['bets'][str(bet_msg.id)]["channel"] = bet_loc.id
                        self.bot.watched_bets['bets'][str(bet_msg.id)]["jump_url"] = bet_msg.jump_url
                        self.bot.watched_bets['bets'][str(bet_msg.id)]["status"] = "open"
                        for i in range(len(self.bot.watched_bets["bets"][str(bet_msg.id)]["options_order"])):
                            await bet_msg.add_reaction(f"{i + 1}\u20e3")
                        await bet_msg.add_reaction("🔒")
                        await bet_msg.add_reaction("🏆")
                    else:
                        try:
                            message = await channel.fetch_message(event.message_id)
                        except discord.errors.NotFound:
                            return await user.send("Could not find bet message.")
                        await message.edit(content=message.content.rsplit("\n", 2)[
                                                       0] + "\n--------\nBet status: **OPEN** | You may freely place/change your bets.",
                                           embed=None)
                        self.bot.watched_bets["bets"][str(event.message_id)]["status"] = "open"
                    dataIO.save_json("data/bets.json", self.bot.watched_bets)
                    print(f"Opened bet: {event.message_id}")
                    try:
                        await user.send(
                            f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThis bet has been opened. Users can freely place and change their bets.")
                    except:
                        pass
                elif event.emoji.name == "🔒":
                    if self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "closed":
                        try:
                            return await user.send(
                                f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThis bet was closed already and points were already redeemed. Cannot re-open/lock this bet.")
                        except:
                            pass
                    try:
                        message = await channel.fetch_message(event.message_id)
                    except discord.errors.NotFound:
                        return await user.send("Could not find bet message.")
                    content = message.content.rsplit("\n", 2)[0]
                    await message.edit(content=content + "\n--------\nBet status: **LOCKED**", embed=None)
                    self.bot.watched_bets["bets"][str(event.message_id)]["status"] = "locked"
                    dataIO.save_json("data/bets.json", self.bot.watched_bets)
                    print(f"Locked bet: {event.message_id}")
                    try:
                        await user.send(
                            f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThis bet has been locked. Users can no longer place their bets. Was it locked on time? If not, you may enter an amount of time to go back. Once entered, the bot will disregard bets placed/changed within that period. Useful if you closed the bet late and need to ensure no one changed the bet after the result was made clear already.\n\nEnter the time like so: `<n>d<n>h<n>m<n>s`. Example: `1d2h3m5s` or `4h` or `5h30s` etc.\n\nEnter the time. Enter `0` if this is unnecessary.")
                    except:
                        bot_channel = guild.get_channel(self.bot_channel)
                        return await bot_channel.send(
                            user.mention + " Could not DM you for closing of bet confirmation. Please check your direct message user settings.")
                    await self.timeshift_bet(event.message_id, user)
                    dataIO.save_json("data/bets.json", self.bot.watched_bets)
                else:
                    if self.bot.watched_bets["bets"][str(event.message_id)]["status"] == "closed":
                        try:
                            return await user.send(
                                f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThis bet was closed already and points were already redeemed.")
                        except:
                            pass
                    self.bot.watched_bets["bets"][str(event.message_id)]["status"] = "closed"
                    try:
                        message = await channel.fetch_message(event.message_id)
                    except discord.errors.NotFound:
                        return await user.send("Could not find bet message.")
                    options_str = ""
                    for i, option in enumerate(self.bot.watched_bets["bets"][str(event.message_id)]["options_order"]):
                        options_str += f"\n({i + 1}) {option}"
                    try:
                        await user.send(
                            f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThis bet has been closed. Was it closed on time? If not, you may enter an amount of time to go back. Once entered, the bot will disregard bets placed/changed within that period. Useful if you closed the bet late and need to ensure no one changed the bet after the result was made clear already.\n\nEnter the time like so: `<n>d<n>h<n>m<n>s`. Example: `1d2h3m5s` or `4h` or `5h30s` etc.\n\nEnter the time. Enter `0` if this is unnecessary.")
                    except:
                        bot_channel = guild.get_channel(self.bot_channel)
                        return await bot_channel.send(
                            user.mention + " Could not DM you for closing of bet confirmation. Please check your direct message user settings.")

                    await self.timeshift_bet(event.message_id, user)
                    dataIO.save_json("data/bets.json", self.bot.watched_bets)
                    try:
                        await user.send(f"Finally, please enter the winning option #.{options_str}")
                    except:
                        bot_channel = guild.get_channel(self.bot_channel)
                        return await bot_channel.send(
                            user.mention + " Could not DM you for closing of bet confirmation. Please check your direct message user settings.")

                    try:
                        reply = await self.bot.wait_for('message', timeout=60.0, check=lambda
                            m: m.author.id == event.user_id and m.content.isdigit() and int(m.content) > 0 and int(
                            m.content) <= len(self.bot.watched_bets["bets"][str(event.message_id)]["options_order"]))
                    except asyncio.TimeoutError:
                        await user.send('Sorry, you took too long to respond.')
                    except Exception as e:
                        await user.send('An error has occurred...')
                        logger.error(f"Error at bet cog: {e}")
                    if reply:
                        winning_option_index = int(reply.content)
                        self.bot.watched_bets["bets"][str(event.message_id)]["winning_option"] = winning_option_index
                        bet_question = self.bot.watched_bets["bets"][str(event.message_id)]["question"]
                        winning_option = self.bot.watched_bets["bets"][str(event.message_id)]["options_order"][
                            winning_option_index - 1]
                        for option in self.bot.watched_bets["bets"][str(event.message_id)]["options"]:
                            for user_id in self.bot.watched_bets["bets"][str(event.message_id)]["options"][option]:
                                if str(user_id) not in self.bot.watched_bets["scoreboard"]:
                                    self.bot.watched_bets["scoreboard"][str(user_id)] = {"points": 0}
                                if option == winning_option:
                                    points = self.bot.watched_bets["bets"][str(event.message_id)]["wager"]
                                    self.bot.watched_bets["scoreboard"][str(user_id)]["points"] += points
                                    user_obj = guild.get_member(int(user_id))
                                    if user_obj:
                                        # user_entity = UserEntity(user_obj)
                                        # add_coin(user_entity, points)
                                        pass
                        dataIO.save_json("data/bets.json", self.bot.watched_bets)
                        content = message.content.rsplit("\n", 2)[0]
                        await message.edit(
                            content=content + f"\n--------\nBet status: **CLOSED** | Winning option: **{winning_option}**",
                            embed=None)
                        print(f"Closed bet: {event.message_id}. Winner was: {winning_option}")
                        await user.send(f"Winner has been announced. {channel.mention}")
                        manga_channel = guild.get_channel(
                            self.bet_winner_ch)
                        if manga_channel:
                            await manga_channel.send(
                                f"{self.bot.watched_bets['bets'][str(event.message_id)]['jump_url']}\nThe winners of this bet have been determined. Point gain/loss has been processed. See `.bet` (in bot channel).\n\nQuestion: **{bet_question}**\nAnswer: || **{winning_option}**. ||")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.bot.wait_until_ready()
        # if str(event.guild_id) == "695200821910044783":
        #     async with self.highlights_lock:
        #         await self.highlight_reaction(event)
        if (hasattr(self.bot, "watched_bets") and
                "bets" in self.bot.watched_bets and
                str(event.message_id) in self.bot.watched_bets["bets"] and
                event.user_id != self.bot.user.id):
            await self.bets_reaction(event)


async def setup(
        bot: commands.Bot
):
    ext = Bets2(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
