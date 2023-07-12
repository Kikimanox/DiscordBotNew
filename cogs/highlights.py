import asyncio
import json
import re
from collections import defaultdict
from datetime import datetime
from typing import Union

import aiohttp
import discord
from discord import ClientUser
from discord.ext import commands

from utils.checks import manage_roles_check
from utils.dataIOa import dataIOa

SPOILER_SETTINGS_JSON = "settings/spoiler_settings.json"
HIGHLIGHTS_DATA_JSON = "data/highlights.json"
HIGHLIGHTS_THRESHOLD_JSON = "settings/highlights_threshold.json"

MANGA_CATEGORY_ID = "manga_category_id"
MANGA_SPOILER_CHANNELS = "manga_spoiler_channels"
RAW_CHANNELS = "raw_channels"


HIGHLIGHTS_ENABLED = "highlights_enabled"
HIGH_ACTIVITY_SECONDS = "high_activity_seconds"
HIGH_ACTIVITY_UPSCALE = "high_activity_upscale"
HIGHLIGHT_ELIGIBLE_EXPIRY_SECONDS = "highlight_eligible_expiry_seconds"
HIGHLIGHT_MESSAGE_CACHE_SIZE = "highlight_message_cache_size"
HISTORY_CACHE_SIZE = "history_cache_size"
LOW_ACTIVITY_SECONDS = "low_activity_seconds"
LOW_ACTIVITY_UPSCALE = "low_activity_upscale"
MAX_THRESHOLD = "max_threshold"
MIN_THRESHOLD = "min_threshold"
SOFT_MAX_THRESHOLD = "soft_max_threshold"
THRESHOLD_EXPONENTIAL_UPSCALE = "threshold_exponential_upscale"
THRESHOLD_UPSCALE_DURATION = "threshold_upscale_duration"
THRESHOLD_UPSCALE_MAX_TIMES = "threshold_upscale_max_times"
USERS_TO_THRESHOLD_RATIO = "users_to_threshold_ratio"
EMBED_OR_ATTACHMENT_UPSCALE = "embed_or_attachment_upscale"
HIGHLIGHT_CHANNEL = "highlight_channel"
SPOILER_HIGHLIGHT_CHANNEL = "spoiler_highlight_channel"
HIGHLIGHT_BLACKLIST = "highlight_blacklist"


class Highlights(commands.Cog):
    """
    Made by appu (formerly appu#4444) on Discord. Github: https://github.com/appu1232
    """
    def __init__(self, bot):
        self.bot = bot

        if not dataIOa.is_valid_json(SPOILER_SETTINGS_JSON):
            dataIOa.create_file_if_doesnt_exist(SPOILER_SETTINGS_JSON, "{}")
        if not dataIOa.is_valid_json(HIGHLIGHTS_DATA_JSON):
            dataIOa.create_file_if_doesnt_exist(HIGHLIGHTS_DATA_JSON, "[]")
        if not dataIOa.is_valid_json(HIGHLIGHTS_THRESHOLD_JSON):
            dataIOa.create_file_if_doesnt_exist(HIGHLIGHTS_THRESHOLD_JSON, "{}")

        self.spoiler_settings = dataIOa.load_json(SPOILER_SETTINGS_JSON)
        self.highlight_msgs = dataIOa.load_json(HIGHLIGHTS_DATA_JSON)
        self.highlights_settings = dataIOa.load_json(HIGHLIGHTS_THRESHOLD_JSON)
        self.highlight_checker = {}
        self.channel_highlights_threshold = {}
        self.channel_history = defaultdict(list)
        self.highlights_lock = asyncio.Lock()

    @staticmethod
    async def is_url_image(image_url):
        image_formats = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/x-icon")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        if resp.headers["content-type"] in image_formats:
                            return True
        except aiohttp.client_exceptions.InvalidURL:
            pass
        return False

    @staticmethod
    def get_user_avatar_url(user: discord.User):
        try:
            return user.display_avatar.with_format("png").url if user.avatar else user.default_avatar.url
        except ValueError:
            return ""

    @staticmethod
    async def get_text_channel(bot: ClientUser, channel_id: int):
        channel = bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception:
                return None, None
        parent_channel = channel.parent if hasattr(channel, "parent") else channel
        return channel, parent_channel

    @commands.check(manage_roles_check)
    @commands.command(aliases=["initialize_smuglights"])
    async def initialize_highlights(self, ctx):
        """First-time initialization command. Run once to initialize highlights settings and configurations on the global bot scope."""
        if self.spoiler_settings == {}:
            self.spoiler_settings = {
                str(ctx.guild.id): {MANGA_CATEGORY_ID: None, MANGA_SPOILER_CHANNELS: [], RAW_CHANNELS: []}
            }
        default_highlight_settings = {
            HIGHLIGHTS_ENABLED: False,
            HIGH_ACTIVITY_SECONDS: 300.0,
            HIGH_ACTIVITY_UPSCALE: 1.25,
            HIGHLIGHT_ELIGIBLE_EXPIRY_SECONDS: 21600,
            HIGHLIGHT_MESSAGE_CACHE_SIZE: 500.0,
            HISTORY_CACHE_SIZE: 50.0,
            LOW_ACTIVITY_SECONDS: 10800.0,
            LOW_ACTIVITY_UPSCALE: 1.2,
            MAX_THRESHOLD: 30.0,
            MIN_THRESHOLD: 6.0,
            SOFT_MAX_THRESHOLD: 20.0,
            THRESHOLD_EXPONENTIAL_UPSCALE: 1.1,
            THRESHOLD_UPSCALE_DURATION: 3600.0,
            THRESHOLD_UPSCALE_MAX_TIMES: 8.0,
            USERS_TO_THRESHOLD_RATIO: 5.0,
            EMBED_OR_ATTACHMENT_UPSCALE: 1.5,
            HIGHLIGHT_CHANNEL: None,
            SPOILER_HIGHLIGHT_CHANNEL: None,
            HIGHLIGHT_BLACKLIST: [],
        }
        if str(ctx.guild.id) not in self.highlights_settings:
            self.highlights_settings[str(ctx.guild.id)] = default_highlight_settings
        
        else:
            for setting, value in default_highlight_settings.items():
                if setting not in self.highlights_settings[str(ctx.guild.id)]:
                    self.highlights_settings[str(ctx.guild.id)][setting] = value
        
        dataIOa.save_json(SPOILER_SETTINGS_JSON, self.spoiler_settings)
        dataIOa.save_json(HIGHLIGHTS_THRESHOLD_JSON, self.highlights_settings)
        await ctx.send(
            "Initialized default highlights settings for this server. View and edit them with `.smugsettings view/edit` alias: `.highlightsettings view/edit`"
        )

    @commands.check(manage_roles_check)
    @commands.command(aliases=["togglesmuglights"])
    async def togglehighlights(self, ctx, channel: Union[discord.Thread, discord.abc.GuildChannel] = None):
        """Toggle highlights on or off for the entire server or specific channels."""
        if channel and channel.guild.id != ctx.guild.id:
            return await ctx.send("Error, channel must belong to this server.")
        guild_highlights_settings = self.highlights_settings.get(str(ctx.guild.id), {})
        if not guild_highlights_settings:
            return await ctx.send("Highlights have not been configured for this server.")

        if channel:
            if channel.id in guild_highlights_settings[HIGHLIGHT_BLACKLIST]:
                guild_highlights_settings[HIGHLIGHT_BLACKLIST].remove(channel.id)
                await ctx.send(f"Toggled highlights on for {channel.mention}")
            else:
                guild_highlights_settings[HIGHLIGHT_BLACKLIST].append(channel.id)
                await ctx.send(f"Toggled highlights off for {channel.mention}")
        else:
            if guild_highlights_settings[HIGHLIGHTS_ENABLED]:
                guild_highlights_settings[HIGHLIGHTS_ENABLED] = False
                await ctx.send("Toggled highlights off")
            else:
                guild_highlights_settings[HIGHLIGHTS_ENABLED] = True
                await ctx.send("Toggled highlights on")
        self.highlights_settings[str(ctx.guild.id)] = guild_highlights_settings
        dataIOa.save_json(HIGHLIGHTS_THRESHOLD_JSON, self.highlights_settings)

    @commands.check(manage_roles_check)
    @commands.command(aliases=["highlightsthreshold"])
    async def smugthreshold(self, ctx, *channels: Union[discord.Thread, discord.abc.GuildChannel]):
        """View the current threshold for number of unique users needing to react to a message in order to hit the highlights channel."""
        txt = ""
        for channel in channels:
            last_message = None
            async for msg in channel.history(limit=1):
                last_message = msg
                break
            required_stars, formula = await self.get_highlight_threshold(last_message)
            txt += f"\n{channel.mention}: {required_stars} | {formula}"
        await ctx.send(f"Required stars for:{txt}")

    @commands.check(manage_roles_check)
    @commands.command(aliases=["smuglights_channel"])
    async def highlights_channel(self, ctx, channel: Union[discord.Thread, discord.abc.GuildChannel] = None):
        """Set the highlights channel where highlights get posted. Provide no channel to remove (same as disabling highlights across the entire server with `.togglehiglights`)."""
        if str(ctx.guild.id) not in self.highlights_settings:
            return await ctx.send("Highlights have not been configured for this server.")

        if channel:
            self.highlights_settings[str(ctx.guild.id)][HIGHLIGHT_CHANNEL] = channel.id
            await ctx.send(f"Set highlights channel to {channel.mention}")
        else:
            self.highlights_settings[str(ctx.guild.id)][HIGHLIGHT_CHANNEL] = None
            await ctx.send(
                "Removed highlights channel. Warning: If you meant to disable highlights, it would be better to do so with `.togglehighlights`. To re-enable highlights, you will now have to ensure `.togglehighlights` enables highlights as well as run `.higlights_channel <#channel>` to ensure there is a highlights channel configured."
            )
        dataIOa.save_json(HIGHLIGHTS_THRESHOLD_JSON, self.highlights_settings)

    @commands.check(manage_roles_check)
    @commands.command(aliases=["spoiler_smuglights_channel"])
    async def spoiler_highlights_channel(self, ctx, channel: Union[discord.Thread, discord.abc.GuildChannel] = None):
        """Set the spoiler highlights channel where highlights from spoiler channels get posted. NOTE: `.highlights_channel` must be configured as well in order to function. Provide no channel to remove (will default to regular highlights)."""
        if str(ctx.guild.id) not in self.highlights_settings:
            return await ctx.send("Highlights have not been configured for this server.")

        if channel:
            self.highlights_settings[str(ctx.guild.id)][SPOILER_HIGHLIGHT_CHANNEL] = channel.id
            await ctx.send(f"Set spoiler highlights channel to {channel.mention}")
        else:
            self.highlights_settings[str(ctx.guild.id)][SPOILER_HIGHLIGHT_CHANNEL] = None
            await ctx.send(
                "Removed spoiler highlights channel. All highlights will now default to the highlights channel specified by `.highlights_channel` if there is one."
            )
        dataIOa.save_json(HIGHLIGHTS_THRESHOLD_JSON, self.highlights_settings)

    @commands.check(manage_roles_check)
    @commands.group(aliases=["highlightssettings"])
    async def smugsettings(self, ctx):
        """View and configure settings for determining message highlight thresholds."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(manage_roles_check)
    @smugsettings.group()
    async def edit(self, ctx, setting_key: str, value: float):
        """Configure settings for determining message highlight thresholds.

        Defining "threshold": The # of reacts a message needs to aquire in order for a message to be added to the highlights channel. Thresholds can differ per channel and per message.
        All highlights settings:
        - highlight_channel - Main highlights channel where highlights are posted.
        - spoiler_highlight_channel - Optional second highlights channel for spoilery content. E.g. A highglights channel for manga channels. This will check settings/spoiler_settings.json configurations to determine what are spoiler channels.
        - min_threshold - Absolute minimum number of reacts necessary for a message to be a highlight.
        - soft_max_threshold - Maximum a threshold can be, based off of channel activity alone. Threshold can still pass this in the case of threshold upscale due to frequent highlights from this channel.
        - max_threshold - Absolute maximum that the threshold can be regardless of channel or message.
        - users_to_threshold_ratio - Calculating reactions threshold based on active unique users in channel message history active cache. Used to determine channel activity based threshold in high-activity periods.
        - history_cache_size - Size in # of messages of message history being held in-memory cache per channel in order to calculate channel activity.
        - threshold_exponential_upscale - Upon a message from a channel entering highlights, that channel's threshold will increase exponentially with respect to this number. (Ideally between 1-3)
        - threshold_upscale_duration - Duration in seconds before a channel's threshold upscale is reverted (decrement based on exponential upscale value).
        - threshold_upscale_max_times - Number of times threshold can upscale for a channel before upscaling is capped. Note, max_threshold will limit this if not configured properly.
        - low_activity_seconds - Age of the oldest message in channel history cache before the channel is considered low activity. Usually want to configure this for detecting "dead" chats which may have a disproportionate amount of reactions on latest messages.
        - high_activity_seconds - Highest age of oldest message in channel cache before the channel is considered high activity. Once high activity, threshold for highlights gets a bump.
        - highlight_message_cache_size - Cache for highlighted messages. Checked against to ensure no repeated messages enter highlights.
        - highlight_eligible_expiry_seconds - Age at which a message is considered too old to enter highlights.
        """
        if str(ctx.guild.id) not in self.highlights_settings:
            return await ctx.send("Highlights have not been configured for this server.")
        if setting_key not in self.highlights_settings[str(ctx.guild.id)]:
            return await ctx.send("Invalid highlights setting.")
        else:
            if setting_key == HIGHLIGHTS_ENABLED:
                if setting_key.lower() == "true":
                    self.highlights_settings[str(ctx.guild.id)][setting_key] = True
                elif setting_key.lower() == "false":
                    self.highlights_settings[str(ctx.guild.id)][setting_key] = False
                else:
                    return await ctx.send(
                        f"Invalid setting for `{HIGHLIGHTS_ENABLED}` setting. Must be either `true` or `false`."
                    )
            elif setting_key == HIGHLIGHT_CHANNEL:
                return await ctx.send("Use `.highlights_channel <#channel>` set the highlights channel.")
            elif setting_key == SPOILER_HIGHLIGHT_CHANNEL:
                return await ctx.send(
                    "Use `.spoiler_highlights_channel <#channel>` set the spoiler highlights channel."
                )
            elif setting_key == HIGHLIGHT_BLACKLIST:
                return await ctx.send(
                    "Use `.togglehighlights <#channel>` to add or remove a channel from the blacklist. `.togglehighlights` with no argument to enable/disable highlights for the entire server."
                )
            else:
                self.highlights_settings[str(ctx.guild.id)][setting_key] = value
                if setting_key == HISTORY_CACHE_SIZE:
                    self.channel_history = defaultdict(list)
            dataIOa.save_json(HIGHLIGHTS_THRESHOLD_JSON, self.highlights_settings)
        await ctx.send(f"Saved setting {setting_key} with value {value}")

    @commands.check(manage_roles_check)
    @smugsettings.group()
    async def upscale(self, ctx, channel: Union[discord.Thread, discord.abc.GuildChannel], value: int):
        """Temporarily upscale the threshold for an unusually active channel. Downscaling can also be done by giving a negative number.

        Upscale effects will erode according to the set value for threshold_upscale_duration.
        """
        self.update_channel_upscale_count(channel.guild.id, channel.id, value)
        if channel.id in self.channel_highlights_threshold:
            await ctx.send(
                f"Successfully upscaled threshold for {channel} to {self.channel_highlights_threshold[channel.id][0]}"
            )
        else:
            await ctx.send(f"Successfully removed threshold upscale for {channel}")

    @commands.check(manage_roles_check)
    @smugsettings.command()
    async def view(self, ctx):
        """View highlights settings."""
        settings_str = f"""```{json.dumps(self.highlights_settings[str(ctx.guild.id)], indent=4)}```"""
        await ctx.send(settings_str)

    def update_channel_upscale_count(self, guild_id, channel_id, value, update_time=None):
        if not update_time:
            update_time = int(datetime.now().timestamp())
        if channel_id not in self.channel_highlights_threshold:
            self.channel_highlights_threshold[channel_id] = [value, update_time]
        else:
            self.channel_highlights_threshold[channel_id][0] += value
            self.channel_highlights_threshold[channel_id][1] = update_time

        threshold_upscale_max_times = self.highlights_settings[str(guild_id)][THRESHOLD_UPSCALE_MAX_TIMES]
        if self.channel_highlights_threshold[channel_id][0] < 1:
            del self.channel_highlights_threshold[channel_id]
        elif self.channel_highlights_threshold[channel_id][0] > threshold_upscale_max_times:
            self.channel_highlights_threshold[channel_id][0] = threshold_upscale_max_times

    def threshold_upscale(self, message, highlights_settings):
        if (
            self.channel_highlights_threshold.get(message.channel.id, None)
            and self.channel_highlights_threshold[message.channel.id][0] >= 1
        ):
            return int(
                (self.channel_highlights_threshold[message.channel.id][0] + 1)
                ** highlights_settings[THRESHOLD_EXPONENTIAL_UPSCALE]
            )
        else:
            return 0

    async def get_highlight_threshold(self, message):
        chnl_history = self.channel_history.get(message.channel.id, [])
        if len(chnl_history) == 0:
            last_msg = None
            async for msg in message.channel.history(limit=1):
                last_msg = msg
                break
            chnl_history.append((last_msg.author.id, last_msg.created_at.timestamp()))
            self.channel_history[message.channel.id] = chnl_history
        guild_highlights_settings = self.highlights_settings[str(message.guild.id)]

        required_stars = guild_highlights_settings[MIN_THRESHOLD]

        if message.embeds or message.attachments:
            required_stars = int(required_stars * guild_highlights_settings[EMBED_OR_ATTACHMENT_UPSCALE])

        if (
            datetime.now().timestamp() - chnl_history[0][1] > guild_highlights_settings[LOW_ACTIVITY_SECONDS]
        ):  # dead chat
            required_stars = int(required_stars * guild_highlights_settings[LOW_ACTIVITY_UPSCALE])
            formula = "low activity"
        elif len(chnl_history) == int(
            guild_highlights_settings[HISTORY_CACHE_SIZE]
        ):  # calculate rate based on unique users in cache
            total_users = len(set([x[0] for x in chnl_history]))
            user_based_upscale = int(total_users / guild_highlights_settings[USERS_TO_THRESHOLD_RATIO])
            required_stars += user_based_upscale
            formula = f"user based activity (upscale: {user_based_upscale} total users: {total_users})"
            if (
                datetime.now().timestamp() - chnl_history[0][1] < guild_highlights_settings[HIGH_ACTIVITY_SECONDS]
            ):  # high activity
                required_stars = int(required_stars * guild_highlights_settings[HIGH_ACTIVITY_UPSCALE])
                formula += ", high activity"
        else:  # not enough messages in cache, default to min threshold
            formula = "min threshold"

        if required_stars < guild_highlights_settings[MIN_THRESHOLD]:
            required_stars = guild_highlights_settings[MIN_THRESHOLD]
            formula += ", min threshold"
        if required_stars > guild_highlights_settings[SOFT_MAX_THRESHOLD]:
            required_stars = guild_highlights_settings[SOFT_MAX_THRESHOLD]
            formula += ", soft max threshold"
        threshold_upscale = self.threshold_upscale(
            message, guild_highlights_settings
        )  # calculate if threshold needs to be upscaled if there's recent highlights from channel
        if threshold_upscale > 0:
            required_stars += threshold_upscale
            formula += f", threshold upscale: {threshold_upscale}"
        if required_stars > guild_highlights_settings[MAX_THRESHOLD]:
            required_stars = guild_highlights_settings[MAX_THRESHOLD]
            formula += ", max threshold"
        return required_stars, formula

    async def highlight_reaction(self, event):
        guild_highlights_settings = self.highlights_settings[str(event.guild_id)]
        if (
            guild_highlights_settings[HIGHLIGHTS_ENABLED]
            and guild_highlights_settings[HIGHLIGHT_CHANNEL]
            and event.message_id not in self.highlight_msgs
            and event.channel_id != guild_highlights_settings[HIGHLIGHT_CHANNEL]
            and event.channel_id != guild_highlights_settings[SPOILER_HIGHLIGHT_CHANNEL]
        ):
            if event.channel_id in guild_highlights_settings[HIGHLIGHT_BLACKLIST]:
                return
            sub_channel, parent_channel = await self.get_text_channel(self.bot, event.channel_id)
            if parent_channel and parent_channel.id in guild_highlights_settings[HIGHLIGHT_BLACKLIST]:
                return

            # Filter out ineligible messages
            if not isinstance(parent_channel, discord.ForumChannel) and parent_channel.overwrites_for(parent_channel.guild.default_role).send_messages is False:
                return
            starred_msg = None
            try:
                starred_msg = await sub_channel.fetch_message(event.message_id)
            except Exception:
                self.bot.logger.error(f"highlight msg not found: {event.message_id}")
                return
            if (
                datetime.now().timestamp() - guild_highlights_settings[HIGHLIGHT_ELIGIBLE_EXPIRY_SECONDS]
                > starred_msg.created_at.timestamp()
            ):
                return
            if starred_msg.author.bot:
                return

            # Threshold upscale has timed out, decrement upscale by configured exponential factor.
            if (
                self.channel_highlights_threshold.get(sub_channel.id, None)
                and int(datetime.now().timestamp()) - self.channel_highlights_threshold[sub_channel.id][1]
                > guild_highlights_settings[THRESHOLD_UPSCALE_DURATION]
            ):
                self.update_channel_upscale_count(sub_channel.guild.id, sub_channel.id, -1)

            if event.message_id not in self.highlight_checker:
                self.highlight_checker[event.message_id] = {}
            if "min_reacts" not in self.highlight_checker[event.message_id]:
                required_stars, _ = await self.get_highlight_threshold(starred_msg)
                if event.message_id not in self.highlight_msgs and event.message_id in self.highlight_checker:
                    self.highlight_checker[event.message_id]["min_reacts"] = required_stars

            # If # of total reactions isn't over the threshold, just return. Checking this before actually checking unique users will help us lower api calls.
            if sum(x.count for x in starred_msg.reactions) < self.highlight_checker[event.message_id]["min_reacts"]:
                return

            # Get unique users reacting on message.
            unique_reactors = set([])
            for reaction in starred_msg.reactions:
                async for user in reaction.users():
                    unique_reactors.add(user.id)

            # Message has passed min reacts threshold, prepare to add to highlights channel
            if len(unique_reactors) >= self.highlight_checker[event.message_id]["min_reacts"]:

                # Increase channel's highlight count for use by threshold upscale formula
                self.update_channel_upscale_count(sub_channel.guild.id, sub_channel.id, 1)

                self.highlight_msgs.append(starred_msg.id)
                self.highlight_msgs = self.highlight_msgs[
                    -int(guild_highlights_settings[HIGHLIGHT_MESSAGE_CACHE_SIZE]) :
                ]
                dataIOa.save_json(HIGHLIGHTS_DATA_JSON, self.highlight_msgs)
                del self.highlight_checker[event.message_id]
                spoiler_settings = self.spoiler_settings.get(str(event.guild_id), {})
                is_spoiler_channel = parent_channel.category.id == spoiler_settings.get(
                    MANGA_CATEGORY_ID, None
                ) or parent_channel.id in spoiler_settings.get(MANGA_SPOILER_CHANNELS, [])
                is_raw_channel = parent_channel.id in spoiler_settings.get(RAW_CHANNELS, [])
                is_nsfw = parent_channel.is_nsfw()
                em = discord.Embed(timestamp=starred_msg.created_at)
                em.set_author(
                    name=starred_msg.author.display_name,
                    icon_url=self.get_user_avatar_url(starred_msg.author),
                )
                description = starred_msg.content
                image_spoiler = False

                # Attach embed or attachments if not spoiler tagged or from raw channel(s)
                if not is_nsfw:
                    if not starred_msg.attachments:
                        if not is_raw_channel:
                            em, _ = await self.first_non_spoiler_image_embed(starred_msg, em)
                    elif starred_msg.attachments[0].is_spoiler():
                        image_spoiler = True
                    else:
                        if not is_raw_channel:
                            em.set_image(url=starred_msg.attachments[0].url)
                        else:
                            image_spoiler = True

                if is_raw_channel:
                    description = f"[May contain raw spoilers] || {description.replace('||', '').replace('```', '').replace('> ', '')} ||"
                if image_spoiler:
                    description += "\n\n[Spoiler image hidden]"
                if is_nsfw:
                    description += "\n\n[May contain NSFW]"
                description += f"\n\n[Jump to message]({starred_msg.jump_url})"
                em.description = description
                em.set_footer(
                    text=f"#{sub_channel.name} "
                    if sub_channel.id == parent_channel.id
                    else f"#{sub_channel.name} | #{parent_channel.name} "
                )
                if is_spoiler_channel and guild_highlights_settings[SPOILER_HIGHLIGHT_CHANNEL]:
                    highlight_channel_id = guild_highlights_settings[SPOILER_HIGHLIGHT_CHANNEL]
                else:
                    highlight_channel_id = guild_highlights_settings[HIGHLIGHT_CHANNEL]

                highlight_channel = parent_channel.guild.get_channel(highlight_channel_id)
                highlight = await highlight_channel.send(content=None, embed=em)
                smug_emoji = discord.utils.get(parent_channel.guild.emojis, name="BunnySmug")
                await highlight.add_reaction(smug_emoji if smug_emoji else "😏")

                # delay to ensure embed had time to load before checking height 0
                await asyncio.sleep(2)
                highlight = await highlight_channel.fetch_message(highlight.id)
                if starred_msg.attachments and highlight.embeds[0].image.height == 0:
                    await highlight_channel.send(content="\n".join([a.proxy_url for a in starred_msg.attachments]))
                if starred_msg.embeds and not highlight.embeds[0].image and starred_msg.embeds[0].url:
                    await highlight_channel.send(content=starred_msg.embeds[0].url)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.bot.wait_until_ready()
        if str(event.guild_id) in self.highlights_settings:
            async with self.highlights_lock:
                await self.highlight_reaction(event)

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.bot.wait_until_ready()

        # track latest 50 messages in each channel
        if message.guild and self.highlights_settings.get(str(message.guild.id), {}).get(HISTORY_CACHE_SIZE, None):
            self.channel_history[message.channel.id].append((message.author.id, message.created_at.timestamp()))
            if (
                len(self.channel_history[message.channel.id])
                > self.highlights_settings[str(message.guild.id)][HISTORY_CACHE_SIZE]
            ):
                self.channel_history[message.channel.id].pop(0)

    def get_user(self, message, user):
        try:
            member = self.bot.get_user(message.raw_mentions[0])
        except Exception:
            member = message.guild.get_member_named(user)
        if not member:
            try:
                member = message.guild.get_member(int(user))
            except ValueError:
                pass
        if not member:
            return None
        return member

    async def first_non_spoiler_image_embed(self, message, output_embed):
        urls = re.findall(
            "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            message.content,
        )
        for url in urls:
            if await self.is_url_image(url):
                output_embed.set_image(url=url)
                break
        else:
            if not len(message.content.split("||")) > 2:
                for embed in message.embeds:
                    if embed.image and await self.is_url_image(embed.image.url):
                        output_embed.set_image(url=embed.image.url)
                        break
                    elif await self.is_url_image(embed.url):
                        output_embed.set_image(url=embed.url)
                        break
            return output_embed, False
        return output_embed, True


async def setup(bot: commands.Bot):
    ext = Highlights(bot)
    await bot.add_cog(ext)
