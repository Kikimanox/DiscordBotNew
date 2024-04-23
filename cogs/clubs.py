from utils.dataIOa import dataIOa
from difflib import get_close_matches, SequenceMatcher
import logging
import logging.handlers as handlers
import asyncio
import discord
import sqlite3
import traceback
from discord.ext import commands
from utils.SimplePaginator import SimplePaginator
from utils.checks import is_url_image, is_url_image_of_ratio, ban_members_check
from utils.dataIOa import dataIOa
from utils.errors import InvalidCommandUsage
from utils.tools import result_printer
from utils.parsers import time_string_to_seconds, time_seconds_to_string
import utils.discordUtils as dutils
from datetime import datetime, timedelta
from string import hexdigits
from pprint import pformat
import random
import re
from peewee import *
import json
# import networkx as nx
# import matplotlib.pyplot as plt
import os
import math
import copy

"""
    Core DB Schema. It relies on a many-to-many relationship between
    a user and club table, with its metadata stored in a TextField as
    a JSON string.

    Performance might be a bit worse, but at least we get a flexible-ish
    schema while still using SQLite.
"""

DB = "data/clubs.db"
db = SqliteDatabase(DB, pragmas={"foreign_keys": 1})


class BaseModel(Model):
    class Meta:
        database = db


class Club(BaseModel):
    ident = CharField(unique=True)
    metadata = TextField()


class User(BaseModel):
    ident = CharField(unique=True)
    metadata = TextField()


class ClubToUser(BaseModel):
    metadata = TextField()
    club = ForeignKeyField(Club, on_delete="CASCADE")
    user = ForeignKeyField(User, on_delete="CASCADE")

    class Meta:
        indexes = ((("club", "user"), True),)


class Permissions:
    PRESIDENT = 0
    MODERATOR = 1
    USER = 2


class AccessLevel:
    STRICT = 0
    STANDARD = 1
    PUBLIC = 2


ACCESS_LEVEL_MAP = {
    AccessLevel.STRICT: "strict",
    AccessLevel.STANDARD: "standard",
    AccessLevel.PUBLIC: "public",
}

DESCRIPTION_STRING = "0"
ROLE_STRING = "1"
APPROVAL_LISTENER_STRING = "4"
THUMBNAIL_STRING = "5"
NOPING_LIST_STRING = "6"
PINGCOUNT_STRING = "7"
MEMBERCOUNT_STRING = "8"
IGNORED_USER_STRING = "9"
PERMISSIONS_STRING = "11"
METADATA_STRING = "12"
LINK_METADATA_STRING = "13"
DISPLAY_NAME_STRING = "14"
LAST_PING_TIMESTAMP_STRING = "15"
ACCESS_LEVEL_STRING = "17"
BANNER_STRING = "18"
REACTS_COUNT_STRING = "19"
CREATION_TIMESTAMP_STRING = "20"
COLOUR_INT_STRING = "21"
RATE_LIMIT_STRING = "22"
CHANNEL_ID_STRING = "23"
ROOM_ACCESS_LEVEL_STRING = "24"
SOFT_DELETED_STRING = "25"

STRING_MAP = {
    DESCRIPTION_STRING: "description",
    ROLE_STRING: "role",
    APPROVAL_LISTENER_STRING: "approval_message_id",
    BANNER_STRING: "banner_url",
    NOPING_LIST_STRING: "noping_array",
    PINGCOUNT_STRING: "ping_count",
    MEMBERCOUNT_STRING: "member_count",
    IGNORED_USER_STRING: "ignoredusers",
    PERMISSIONS_STRING: "permissions",
    METADATA_STRING: "metadata",
    LINK_METADATA_STRING: "link_metadata",
    DISPLAY_NAME_STRING: "display_name",
    LAST_PING_TIMESTAMP_STRING: "last_ping",
    ACCESS_LEVEL_STRING: "access_level",
    THUMBNAIL_STRING: "thumbnail_url",
    REACTS_COUNT_STRING: "reacts_count",
    CREATION_TIMESTAMP_STRING: "created_on",
    COLOUR_INT_STRING: "colour_code",
    RATE_LIMIT_STRING: "rate_limit",
    CHANNEL_ID_STRING: "channel_id",
    ROOM_ACCESS_LEVEL_STRING: "room_visibility",
    SOFT_DELETED_STRING: "soft_deleted",
}

CLUB_METADATA_DEFAULTS = {
    DESCRIPTION_STRING: "No description.",
    ROLE_STRING: None,
    APPROVAL_LISTENER_STRING: None,
    BANNER_STRING: None,
    THUMBNAIL_STRING: None,
    PINGCOUNT_STRING: 0,
    MEMBERCOUNT_STRING: 0,
    DISPLAY_NAME_STRING: None,
    LAST_PING_TIMESTAMP_STRING: 0,
    NOPING_LIST_STRING: [],
    ACCESS_LEVEL_STRING: AccessLevel.STANDARD,
    REACTS_COUNT_STRING: 0,
    CREATION_TIMESTAMP_STRING: int(
        datetime.now().timestamp()
    ),  # Old clubs will be appended with the bot restart time,
    COLOUR_INT_STRING: 0xFFFFFF,
    RATE_LIMIT_STRING: 0,
    CHANNEL_ID_STRING: None,
    ROOM_ACCESS_LEVEL_STRING: AccessLevel.STANDARD,
    SOFT_DELETED_STRING: False,
}

USER_METADATA_DEFAULTS = {
    IGNORED_USER_STRING: [],
}

LINK_METADATA_DEFAULTS = {
    PERMISSIONS_STRING: Permissions.USER,
}

MAX_DESCRIPTION_LEN = 1000
MAX_CLUB_NAME_LENGTH = 64

MAX_PING_REACT_TIME = 60 * 60 * 6  # 6 hours

CLUB_JSON = "data/club_settings.json"
CLUB_JSON_CATEGORY = "category"
CLUB_JSON_ACCESS_ROLE = "access_role"
CLUB_JSON_CHANNEL_PING_OVERRIDES = "channel_ping_overrides"

CLUB_MODERATION_JSON = "data/club_moderation_mutes.json"
CLUB_MODERATION_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
CLUB_MODERATION_MAX_MUTE_TIME = 60 * 60 * 24 * 7

BACKUP_DIR = "data/club_backups"

MAX_RATE_LIMIT_TIME = 60 * 60 * 24 * 7


class ClubManagerCommons:
    @staticmethod
    def standardize_dict(values, model):
        """Return a dict that follows a model, using new values if available."""
        return {
            key: values[key] if key in values else fallback
            for key, fallback in model.items()
        }

    @staticmethod
    def exists_common(model, predicate):
        try:
            model.get(predicate())
            return True
        except:
            return False

    @staticmethod
    def get_all_common(model, defaults):
        try:
            # We won't repair completely on get, but we'll at least get expected keys
            return {
                m.ident: ClubManagerCommons.standardize_dict(
                    json.loads(m.metadata), defaults
                )
                for m in model.select()
            }
        except:
            return {}

    @staticmethod
    def create_new_common(model, ident, defaults, **metadata):
        try:
            model.create(
                ident=ident,
                metadata=json.dumps(
                    ClubManagerCommons.standardize_dict(metadata, defaults)
                ),
            )
            return True
        except:
            return False

    @staticmethod
    def get_metadata_common(model, predicate, defaults):
        try:
            current_metadata = json.loads(model.get(predicate()).metadata)
            current_keyset = set(current_metadata)
            expected_keyset = set(defaults)

            if current_keyset == expected_keyset:
                return current_metadata

            repaired_metadata = ClubManagerCommons.standardize_dict(
                current_metadata, defaults
            )
            model.update(metadata=json.dumps(repaired_metadata)).where(
                predicate()
            ).execute()
            return repaired_metadata
        except:
            pass

    @staticmethod
    def edit_metadata_common(model, predicate, defaults, **metadata):
        current_metadata = ClubManagerCommons.get_metadata_common(
            model, predicate, defaults
        )
        if current_metadata:
            to_be_committed_metadata = ClubManagerCommons.standardize_dict(
                {**current_metadata, **metadata}, defaults
            )
            model.update(metadata=json.dumps(to_be_committed_metadata)).where(
                predicate()
            ).execute()
            return True
        else:
            return False

    @staticmethod
    def delete_common(model, predicate):
        try:
            model.delete().where(predicate()).execute()
            return True
        except:
            return False


class ClubManager(ClubManagerCommons):
    def __init__(self):
        db.create_tables([Club, User, ClubToUser])

    def club_exists(self, club, **options):
        return self.exists_common(Club, lambda: Club.ident == club)

    def get_all_clubs(self, **options):
        return self.get_all_common(Club, CLUB_METADATA_DEFAULTS)

    def create_new_club(self, club, **metadata):
        return self.create_new_common(Club, club, CLUB_METADATA_DEFAULTS, **metadata)

    def get_club_metadata(self, club, **options):
        return self.get_metadata_common(
            Club, lambda: Club.ident == club, CLUB_METADATA_DEFAULTS
        )

    def edit_club_metadata(self, club, **metadata):
        return self.edit_metadata_common(
            Club, lambda: Club.ident == club, CLUB_METADATA_DEFAULTS, **metadata
        )

    def delete_club(self, club):
        return self.delete_common(Club, lambda: Club.ident == club)

    def prune_club(self, club):
        return self.delete_club(club)

    def restore_club(self, club):
        return True

    def user_exists(self, user_id):
        return self.exists_common(User, lambda: User.ident == user_id)

    def get_all_users(self):
        return self.get_all_common(User, USER_METADATA_DEFAULTS)

    def create_new_user(self, user_id, **metadata):
        return self.create_new_common(User, user_id, USER_METADATA_DEFAULTS, **metadata)

    def get_user_metadata(self, user_id):
        return self.get_metadata_common(
            User, lambda: User.ident == user_id, USER_METADATA_DEFAULTS
        )

    def edit_user_metadata(self, user_id, **metadata):
        return self.edit_metadata_common(
            User, lambda: User.ident == user_id, USER_METADATA_DEFAULTS, **metadata
        )

    def delete_user(self, user_id):
        return self.delete_common(User, lambda: User.ident == user_id)

    def link_exists(self, club, user_id):
        return self.exists_common(
            ClubToUser,
            lambda: (
                    (ClubToUser.club == Club.get(Club.ident == club))
                    & (ClubToUser.user == User.get(User.ident == user_id))
            ),
        )

    def create_new_link(self, club, user_id, **metadata):
        try:
            ClubToUser.create(
                club=Club.get(Club.ident == club),
                user=User.get(User.ident == user_id),
                metadata=json.dumps(
                    self.standardize_dict(metadata, LINK_METADATA_DEFAULTS)
                ),
            )
            club_metadata = self.get_club_metadata(club)
            club_metadata[MEMBERCOUNT_STRING] += 1
            self.edit_club_metadata(club, **club_metadata)
            return True
        except:
            return False

    def delete_link(self, club, user_id):
        try:
            self.delete_common(
                ClubToUser,
                lambda: (
                        (ClubToUser.club == Club.get(Club.ident == club))
                        & (ClubToUser.user == User.get(User.ident == user_id))
                ),
            )
            club_metadata = self.get_club_metadata(club)
            club_metadata[MEMBERCOUNT_STRING] -= 1
            self.edit_club_metadata(club, **club_metadata)
            return True
        except:
            return False

    def get_link_metadata(self, club, user_id):
        return self.get_metadata_common(
            ClubToUser,
            lambda: (
                    (ClubToUser.club == Club.get(Club.ident == club))
                    & (ClubToUser.user == User.get(User.ident == user_id))
            ),
            LINK_METADATA_DEFAULTS,
        )

    def edit_link_metadata(self, club, user_id, **metadata):
        return self.edit_metadata_common(
            ClubToUser,
            lambda: (
                    (ClubToUser.club == Club.get(Club.ident == club))
                    & (ClubToUser.user == User.get(User.ident == user_id))
            ),
            LINK_METADATA_DEFAULTS,
            **metadata,
        )

    def get_club_users(self, club):
        """Get the relationship from a club to their users."""
        try:
            return {
                user.user.ident: {
                    METADATA_STRING: ClubManagerCommons.standardize_dict(
                        json.loads(user.user.metadata), USER_METADATA_DEFAULTS
                    ),
                    LINK_METADATA_STRING: ClubManagerCommons.standardize_dict(
                        json.loads(user.metadata), LINK_METADATA_DEFAULTS
                    ),
                }
                for user in ClubToUser.select(
                    User.ident, User.metadata, ClubToUser.metadata
                )
                .join(User, on=(ClubToUser.user == User.id))
                .where(ClubToUser.club == Club.get(Club.ident == club))
            }
        except Club.DoesNotExist:
            return {}

    def get_user_clubs(self, user_id):
        """Get the relationship from a user to their clubs."""
        try:
            return {
                club.club.ident: {
                    METADATA_STRING: ClubManagerCommons.standardize_dict(
                        json.loads(club.club.metadata), CLUB_METADATA_DEFAULTS
                    ),
                    LINK_METADATA_STRING: ClubManagerCommons.standardize_dict(
                        json.loads(club.metadata), LINK_METADATA_DEFAULTS
                    ),
                }
                for club in ClubToUser.select(
                    Club.ident, Club.metadata, ClubToUser.metadata
                )
                .join(Club, on=(ClubToUser.club == Club.id))
                .where(ClubToUser.user == User.get(User.ident == user_id))
            }
        except User.DoesNotExist:
            return {}


class SoftDeleteClubManager(ClubManager):
    def __init__(self):
        db.create_tables([Club, User, ClubToUser])

    def club_exists(self, club, **options):
        if "check_deleted" in options and options["check_deleted"]:
            return self.exists_common(Club, lambda: Club.ident == club)
        else:
            if self.exists_common(Club, lambda: Club.ident == club):
                md = super().get_club_metadata(club, **options)
                return not md[SOFT_DELETED_STRING]
            else:
                return False

    def get_all_clubs(self, **options):
        if "check_deleted" in options and options["check_deleted"]:
            return super().get_all_clubs(**options)
        else:
            data = self.get_all_common(Club, CLUB_METADATA_DEFAULTS)
            return {c: md for c, md in data.items() if not md[SOFT_DELETED_STRING]}

    def get_club_metadata(self, club, **options):
        if "check_deleted" in options and options["check_deleted"]:
            return super().get_club_metadata(club, **options)
        else:
            if self.exists_common(Club, lambda: Club.ident == club):
                md = super().get_club_metadata(club, **options)
                if not md[SOFT_DELETED_STRING]:
                    return md
                else:
                    return None
            else:
                return None

    def delete_club(self, club):
        return self.edit_metadata_common(
            Club,
            lambda: Club.ident == club,
            CLUB_METADATA_DEFAULTS,
            **{
                SOFT_DELETED_STRING: True,
                ROLE_STRING: CLUB_METADATA_DEFAULTS[ROLE_STRING],
                CHANNEL_ID_STRING: CLUB_METADATA_DEFAULTS[CHANNEL_ID_STRING],
            },
        )

    def prune_club(self, club):
        return super().delete_club(club)

    def restore_club(self, club):
        return self.edit_metadata_common(
            Club,
            lambda: Club.ident == club,
            CLUB_METADATA_DEFAULTS,
            **{SOFT_DELETED_STRING: False},
        )

    def get_club_users(self, club):
        """Get the relationship from a club to their users."""
        if self.club_exists(club):
            try:
                return super().get_club_users(club)
            except Club.DoesNotExist:
                return {}
        else:
            return {}

    def get_user_clubs(self, user_id):
        """Get the relationship from a user to their clubs."""
        return {
            k: v
            for k, v in super().get_user_clubs(user_id).items()
            if not v[METADATA_STRING][SOFT_DELETED_STRING]
        }


"""
    We're making the club manager a module-wide field since the permissions
    check needs to be able to access it.
"""
club_manager = SoftDeleteClubManager()


def permissions_check(
        *, club_name_position, requires_president=True, server_mods_capable=True
):
    async def predicate(ctx):
        # Help text runs this check for subcommands, so we'll return true to show all
        if ctx.message.content.startswith(f"{ctx.prefix}help"):
            return True
        try:
            club = (
                ctx.message.content[len(ctx.prefix):]
                .split()[club_name_position]
                .lower()
            )
            if not club_manager.club_exists(club):
                return True
        except IndexError:
            return True
        link_metadata = club_manager.get_link_metadata(club, str(ctx.author.id))
        checks = []
        if link_metadata:
            checks.append(link_metadata[PERMISSIONS_STRING] == Permissions.PRESIDENT)
            if not requires_president:
                checks.append(
                    link_metadata[PERMISSIONS_STRING] == Permissions.MODERATOR
                )
        if server_mods_capable:
            checks.append(await ban_members_check(ctx))
        return any(checks)

    return commands.check(predicate)


def club_manage_messages_check():
    # Check permissions scoped to rooms
    club_json = dataIOa.load_json(CLUB_JSON)

    async def predicate(ctx):
        nonlocal club_json
        if not club_json:
            club_json = dataIOa.load_json(CLUB_JSON)
        # Help text runs this check for subcommands, so we'll return true to show all
        if ctx.message.content.startswith(f"{ctx.prefix}help"):
            return True
        if not club_json or (
                CLUB_JSON_CATEGORY not in club_json
                and CLUB_JSON_ACCESS_ROLE not in club_json
        ):
            return False
        else:
            return ctx.channel.category_id == int(club_json[CLUB_JSON_CATEGORY]) and (
                    ctx.author.id == ctx.bot.config["OWNER_ID"]
                    or (
                            isinstance(ctx.author, discord.Member)
                            and (
                                    ctx.author.guild_permissions.manage_messages
                                    or ctx.channel.permissions_for(ctx.author).manage_messages
                            )
                    )
            )

    return commands.check(predicate)


class Clubs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        dataIOa.init_json(CLUB_MODERATION_JSON)
        dataIOa.init_json(CLUB_JSON)
        self.club_manager = club_manager
        self.approvals = {
            metadata[APPROVAL_LISTENER_STRING]: club
            for club, metadata in self.club_manager.get_all_clubs().items()
            if metadata[APPROVAL_LISTENER_STRING]
        }
        self.react_listeners = {}
        self.room_mutes = dataIOa.load_json(CLUB_MODERATION_JSON)
        self.room_mutes_lock = asyncio.Lock()

        ## Taken from guyacoin.py
        self.club_logger = logging.getLogger("clubs")
        self.club_logger.setLevel(logging.INFO)

        # log formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logHandler = handlers.RotatingFileHandler(
            "logs/info/clubs.log", maxBytes=500000, backupCount=10, encoding="utf-8"
        )
        logHandler.setLevel(logging.INFO)
        logHandler.setFormatter(formatter)

        # fixes bug when bot restarted but log file retained loghandler. this will remove any handlers it already had and replace with new ones initialized above
        for hdlr in list(self.club_logger.handlers):
            self.club_logger.removeHandler(hdlr)
        self.club_logger.addHandler(logHandler)

    @staticmethod
    def get_club_sentiment(club_metadata):
        return (
            0.0
            if club_metadata[PINGCOUNT_STRING] == 0
            else round(
                club_metadata[REACTS_COUNT_STRING]
                / club_metadata[PINGCOUNT_STRING]
                / club_metadata[MEMBERCOUNT_STRING]
                * 100,
                3,
            )
        )

    async def closest_club(self, ctx, club_guess):
        clubs = self.club_manager.get_all_clubs()
        matches = get_close_matches(club_guess, clubs)
        if matches:
            await ctx.send(
                f"The club `{club_guess}` does not exist. Did you mean the club `{matches[0]}`?\n\nIf not, you can view a list of clubs with `.club list`",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            longest_substring = [0, None]
            for c in clubs:
                seq_match = SequenceMatcher(None, c, club_guess)
                match = seq_match.find_longest_match(0, len(c), 0, len(club_guess))
                if match.size != 0 and match.size > longest_substring[0]:
                    longest_substring = [match.size, c]
            if longest_substring[0] > 2:
                await ctx.send(
                    f"The club `{club_guess}` does not exist. Did you mean the club `{longest_substring[1]}`?\n\nIf not, you can view a list of clubs with `.club list`",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            else:
                await ctx.send(
                    f"The club `{club_guess}` does not exist. View a list of clubs with `.club list`",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

    def get_ping_club_string(self, ctx, member_dict: dict, metadata_dict: dict):
        ping_str = "Clubs: "
        for club in metadata_dict:
            ping_str += metadata_dict[club][DISPLAY_NAME_STRING] + " "
        ping_str_list = []
        processed_users = set()
        for club in metadata_dict:
            if metadata_dict[club][ROLE_STRING]:
                ping_str += f"{ctx.guild.get_role(int(metadata_dict[club][ROLE_STRING])).mention} ({len(member_dict[club])} users) "
                self.club_manager.edit_club_metadata(
                    club,
                    **{
                        PINGCOUNT_STRING: metadata_dict[club][PINGCOUNT_STRING] + 1,
                        LAST_PING_TIMESTAMP_STRING: int(datetime.now().timestamp()),
                    },
                )
            else:
                for user, md in member_dict[club].items():
                    if str(ctx.author.id) in md[METADATA_STRING][IGNORED_USER_STRING]:
                        continue
                    user = ctx.guild.get_member(int(user))
                    if user in processed_users:
                        continue
                    else:
                        processed_users.add(user)
                self.club_manager.edit_club_metadata(
                    club,
                    **{
                        PINGCOUNT_STRING: metadata_dict[club][PINGCOUNT_STRING] + 1,
                        LAST_PING_TIMESTAMP_STRING: int(datetime.now().timestamp()),
                    },
                )
        for user in processed_users:
            if (len(ping_str) + len(f"{user.mention} ")) > 2000:
                ping_str_list.append(ping_str)
                ping_str = ""
            ping_str += f"{user.mention} "
        ping_str_list.append(ping_str)
        return ping_str_list

    async def join_helper(
            self, ctx, club: str, user_id: str, permissions=Permissions.USER
    ):
        """Helper function to wrap user creation (if they don't
        exist) and link creation. You must validate that the
        club exists.
        """
        if not self.club_manager.user_exists(user_id):
            self.club_manager.create_new_user(user_id)
        success = self.club_manager.create_new_link(
            club,
            user_id,
            **{PERMISSIONS_STRING: permissions},
        )
        if success:
            club_metadata = self.club_manager.get_club_metadata(club)
            if club_metadata[ROLE_STRING]:
                await self.role_add_helper(
                    ctx.guild, club_metadata[ROLE_STRING], int(user_id)
                )
            if club_metadata[CHANNEL_ID_STRING]:
                await self.channel_perm_add_helper(
                    ctx.guild,
                    club_metadata[CHANNEL_ID_STRING],
                    (int(user_id), permissions),
                )
            return f"Successfully joined the club: `{club}`.", True
        else:
            return f"Error in joining `{club}`. Try again later.", False

    async def room_delete_helper(self, guild, channel_id: str, club: str):
        """Club should exist."""
        channel = guild.get_channel(int(channel_id))
        category = guild.get_channel(channel.category_id)
        overwrites = category.overwrites
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            read_messages=False
        )
        await channel.edit(
            sync_permissions=True, name=f"{club}-deprecated", overwrites=overwrites
        )
        await channel.send("**NOTE**: This channel has been de-roomified.")

    async def delete_helper(self, guild, club_metadata: dict, club: str):
        self.club_manager.delete_club(club)
        key = None
        for k, c in self.approvals.items():
            if c == club:
                key = k
                break
        if key:
            del self.approvals[key]
        if club_metadata[ROLE_STRING]:
            await self.role_delete_helper(guild, club_metadata[ROLE_STRING])
        if club_metadata[CHANNEL_ID_STRING]:
            await self.room_delete_helper(guild, club_metadata[CHANNEL_ID_STRING], club)

    async def leave_helper(self, guild, club: str, user_id: str):
        """Helper function to wrap permissions transfer on leave,
        or club deletion if they're the only member. You must
        validate that both the club and user exists.

        There's several cases to consider:
            1. User leaves club, there are other members. Best case.
            2. User leaves club, they're the only member. Delete the club too.
            3. User leaves club, they're the president and there are other members. Transfer ownership.
        """
        club_users = self.club_manager.get_club_users(club)
        if user_id in club_users:
            permission = self.club_manager.get_link_metadata(club, user_id)[
                PERMISSIONS_STRING
            ]
            club_metadata = self.club_manager.get_club_metadata(club)
            self.club_manager.delete_link(club, user_id)
            if len(club_users) == 1:
                await self.delete_helper(guild, club_metadata, club)
                return (
                    f"Left `{club}`. Since you were the only member, it was also deleted.",
                    True,
                )
            else:
                if club_metadata[ROLE_STRING]:
                    await self.role_remove_helper(
                        guild, club_metadata[ROLE_STRING], user_id
                    )
                if club_metadata[CHANNEL_ID_STRING]:
                    await self.channel_perm_remove_helper(
                        guild, club_metadata[CHANNEL_ID_STRING], (user_id, None)
                    )
                if permission == Permissions.PRESIDENT:
                    del club_users[user_id]
                    club_mods = {
                        u: m
                        for u, m in club_users.items()
                        if m[LINK_METADATA_STRING][PERMISSIONS_STRING]
                           == Permissions.MODERATOR
                    }
                    try:
                        new_president_id = (
                            random.choice(
                                [
                                    m
                                    for m in club_mods.keys()
                                    if guild.get_member(int(m))
                                ]
                            )
                            if len(club_mods)
                            else random.choice(
                                [
                                    m
                                    for m in club_users.keys()
                                    if guild.get_member(int(m))
                                ]
                            )
                        )
                        self.club_manager.edit_link_metadata(
                            club,
                            new_president_id,
                            **{PERMISSIONS_STRING: Permissions.PRESIDENT},
                        )
                        return (
                            f"Successfully left club. Since you were the president, the ownership of `{club}` has been transfered to {guild.get_member(int(new_president_id))}",
                            True,
                        )
                    except IndexError:
                        # This will be thrown if all the other members of the club are gone
                        self.club_manager.delete_club(club)
                else:
                    return f"Successfully left `{club}`.", True
        else:
            return f"You're not in `{club}`.", False

    async def role_add_helper(self, guild, role_id, *user_ids, role=None):
        if not role:
            role = guild.get_role(int(role_id))
        for user in user_ids:
            user = guild.get_member(int(user))
            if user:
                await user.add_roles(role)

    async def role_remove_helper(self, guild, role_id, *user_ids):
        role = guild.get_role(int(role_id))
        if role:
            for user in user_ids:
                user = guild.get_member(int(user))
                if user:
                    await user.remove_roles(role)

    async def role_delete_helper(self, guild, role_id):
        role = guild.get_role(int(role_id))
        if role:
            await role.delete()

    async def channel_perm_add_helper(self, guild, channel_id, *user_ids):
        for user, permission in user_ids:
            await self.channel_perm_edit_helper(
                guild,
                channel_id,
                user,
                read_messages=True,
                manage_messages=True
                if (permission in [Permissions.MODERATOR, Permissions.PRESIDENT])
                else None,
            )

    async def channel_perm_remove_helper(self, guild, channel_id, *user_ids):
        for user, _ in user_ids:
            await self.channel_perm_edit_helper(
                guild, channel_id, user, read_messages=None, manage_messages=None
            )

    async def channel_perm_edit_helper(self, guild, channel_id, user_id, **perms):
        user = guild.get_member(int(user_id))
        channel = guild.get_channel(int(channel_id))
        if user and channel:
            existing_permissions = channel.overwrites_for(user)
            existing_permissions.update(**perms)
            await channel.set_permissions(
                user,
                overwrite=None
                if existing_permissions.is_empty()
                else existing_permissions,
            )

    async def channel_init_helper(
            self, guild, club, channel_obj, category_id, club_access_role_id
    ):
        """Helper that handles all channel properties. Assumes the channel exists and club is valid."""
        club = club.lower()
        category_id = int(category_id)
        club_access_role_id = int(club_access_role_id)
        club_metadata = self.club_manager.get_club_metadata(club)
        category = guild.get_channel(category_id)
        public_room_access_role = guild.get_role(club_access_role_id)
        overwrites = category.overwrites

        overwrites[guild.default_role] = discord.PermissionOverwrite(
            read_messages=False
        )
        overwrites[public_room_access_role] = discord.PermissionOverwrite(
            read_messages=(
                    club_metadata[ROOM_ACCESS_LEVEL_STRING] == AccessLevel.PUBLIC
            )
        )

        users = self.club_manager.get_club_users(club)
        if users:
            for user, md in users.items():
                user = guild.get_member(int(user))
                if user:
                    overwrites[user] = discord.PermissionOverwrite(
                        read_messages=True,
                        manage_messages=True
                        if (
                                md[LINK_METADATA_STRING][PERMISSIONS_STRING]
                                in [Permissions.MODERATOR, Permissions.PRESIDENT]
                        )
                        else None,
                    )
        # Discord restricts permissions overwrites to 100 or fewer, so we'll
        # batch the first 100 then individually apply the rest
        MAX_OVERWRITES_THRESHOLD = 100
        batched_perms = {}
        individual_perms = {}
        for i, (u, ov) in enumerate(overwrites.items()):
            if i >= MAX_OVERWRITES_THRESHOLD:
                individual_perms[u] = ov
            else:
                batched_perms[u] = ov
        await channel_obj.edit(
            name=club_metadata[DISPLAY_NAME_STRING],
            topic=club_metadata[DESCRIPTION_STRING],
            overwrites=batched_perms,
        )
        for u, ov in individual_perms.items():
            await channel_obj.set_permissions(u, overwrite=ov)

        self.club_manager.edit_club_metadata(
            club, **{CHANNEL_ID_STRING: str(channel_obj.id)}
        )

    # async def time_mute_check(self):
    #     await self.bot.wait_until_ready()
    #     print("started club timemutes checker")
    #     while self is self.bot.get_cog("Clubs"):
    #         try:
    #             async with self.room_mutes_lock:
    #                 diff = False
    #                 timestamp = datetime.now()
    #                 for user, channels in copy.deepcopy(self.room_mutes).items():
    #                     for channel, metadata in channels.items():
    #                         expiry, guild = metadata
    #                         guild = self.bot.get_guild(int(guild))
    #                         expiry = datetime.strptime(
    #                             expiry, CLUB_MODERATION_TIME_FORMAT
    #                         )
    #                         if timestamp > expiry:
    #                             diff = True
    #                             await self.channel_perm_edit_helper(
    #                                 guild,
    #                                 channel,
    #                                 user,
    #                                 send_messages=None,
    #                             )
    #                             del self.room_mutes[user][channel]
    #                             if not self.room_mutes[user]:
    #                                 del self.room_mutes[user]
    #                         else:
    #                             # Re-apply the mute if the permission was changed
    #                             # We don't delete the entry until the mute expires to prevent
    #                             # users from leaving the guild nad joining back to evade the mute
    #                             user_obj = guild.get_member(int(user))
    #                             channel_obj = guild.get_channel(int(channel))
    #                             if user_obj and channel_obj:
    #                                 overwrites = channel_obj.overwrites_for(user_obj)
    #                                 if overwrites.send_messages is not False:
    #                                     await self.channel_perm_edit_helper(
    #                                         guild, channel, user, send_messages=False
    #                                     )
    #                 if diff:
    #                     dataIOa.save_json(CLUB_MODERATION_JSON, self.room_mutes)
    #         except:
    #             trace = traceback.format_exc()
    #             if hasattr(self.bot, "logger"):
    #                 self.bot.logger.error(trace)
    #             print(trace)
    #         finally:
    #             await asyncio.sleep(5)

    @staticmethod
    def sanitize_string(string):
        return (
            string.replace("*", "").replace("`", "").replace("_", "").replace("|", "")
        )

    async def edit_club_metadata(self, ctx, club, thing, metadata, silent=False):
        club = club.lower()
        if self.club_manager.club_exists(club):
            success = self.club_manager.edit_club_metadata(club, **metadata)
            club_metadata = self.club_manager.get_club_metadata(club)
            if club_metadata[CHANNEL_ID_STRING]:
                channel = ctx.guild.get_channel(int(club_metadata[CHANNEL_ID_STRING]))
                if ROOM_ACCESS_LEVEL_STRING in metadata:
                    club_category = dataIOa.load_json(CLUB_JSON)
                    public_room_access_role = ctx.guild.get_role(
                        club_category[CLUB_JSON_ACCESS_ROLE]
                    )
                    if metadata[ROOM_ACCESS_LEVEL_STRING] == AccessLevel.PUBLIC:
                        await channel.set_permissions(
                            public_room_access_role, read_messages=True
                        )
                    else:
                        await channel.set_permissions(
                            public_room_access_role, read_messages=False
                        )
                if DESCRIPTION_STRING in metadata:
                    await channel.edit(topic=metadata[DESCRIPTION_STRING])
            if not silent:
                if success:
                    return await ctx.send(f"Updated {thing} for `{club}`.")
                else:
                    return await ctx.send(f"Failed to edit `{club}`. Try again later.")
        elif not silent:
            await self.closest_club(ctx, club)

    async def edit_link_metadata(
            self, ctx, club, user_id, thing, metadata, silent=False
    ):
        club = club.lower()
        if self.club_manager.link_exists(club, user_id):
            success = self.club_manager.edit_link_metadata(club, user_id, **metadata)
            club_metadata = self.club_manager.get_club_metadata(club)
            if club_metadata[CHANNEL_ID_STRING]:
                channel = ctx.guild.get_channel(int(club_metadata[CHANNEL_ID_STRING]))
                user = ctx.guild.get_member(int(user_id))
                if channel and user:
                    if PERMISSIONS_STRING in metadata:
                        permissions = channel.permissions_for(user)
                        await channel.set_permissions(
                            user,
                            read_messages=permissions.read_messages,
                            manage_messages=True
                            if (
                                    metadata[PERMISSIONS_STRING]
                                    in [Permissions.MODERATOR, Permissions.PRESIDENT]
                            )
                            else None,
                        )
            if not silent:
                if success:
                    await ctx.send(f"Updated {thing} for `{club}`.")
                else:
                    await ctx.send(f"Failed to edit `{club}`. Try again later.")
            return success
        elif not silent:
            await ctx.send(
                f"Couldn't complete request. Check that the club exists or the user is in the club?"
            )
            return False

    async def edit_user_metadata(self, ctx, user_id, thing, metadata, silent=False):
        """This one is a bit special since it'll handle creating the user; it doesn't necessarily need to exist."""
        if not self.club_manager.user_exists(user_id):
            success = self.club_manager.create_new_user(user_id, **metadata)
        else:
            success = self.club_manager.edit_user_metadata(user_id, **metadata)
        if not silent:
            if success:
                return await ctx.send(
                    f"Updated {thing} for `{ctx.guild.get_member(int(user_id))}`."
                )
            else:
                return await ctx.send(
                    f"Failed to edit `{ctx.guild.get_member(int(user_id))}`. Try again later."
                )

    # @commands.group()
    # @commands.guild_only()
    # async def room(self, ctx):
    #     """Functionality related to club room moderation."""
    #     if ctx.invoked_subcommand is None:
    #         raise commands.errors.BadArgument

    # @room.command()
    # @club_manage_messages_check()
    # async def mute(self, ctx, user: discord.Member, length=""):
    #     """Mutes a user from a particular room. Ie. `[p]room mute @user 10s`"""
    #     seconds = time_string_to_seconds(length)
    #     if seconds is None:
    #         p = dutils.bot_pfx(ctx.bot, ctx.message)
    #         return await ctx.send(
    #             f"Could not parse mute length. Are you sure you're giving it in the right format? Ex: {p}slow 30m, or {p}slow 1d4h3m2s, etc."
    #         )
    #     if seconds > CLUB_MODERATION_MAX_MUTE_TIME:
    #         return await ctx.send("You can't mute somebody in a room for that long.")
    #     if user.guild_permissions.manage_messages:
    #         return await ctx.send("You can't mute server mods/admins in rooms.")
    #     if user.id == ctx.author.id:
    #         return await ctx.send(
    #             "You can't mute yourself. Ask a club moderator to do so if you *really* want to."
    #         )
    #     unmute_time = datetime.now() + timedelta(seconds=seconds)
    #     unmute_time_string = unmute_time.strftime(CLUB_MODERATION_TIME_FORMAT)
    #     async with self.room_mutes_lock:
    #         if str(user.id) not in self.room_mutes:
    #             self.room_mutes[str(user.id)] = {}
    #         self.room_mutes[str(user.id)][str(ctx.channel.id)] = (
    #             unmute_time_string,
    #             ctx.guild.id,
    #         )
    #         dataIOa.save_json(CLUB_MODERATION_JSON, self.room_mutes)
    #     await self.channel_perm_edit_helper(
    #         ctx.guild, ctx.channel.id, user.id, send_messages=False
    #     )
    #     await ctx.send(
    #         f"{user.mention} is now muted from {ctx.channel.mention} for {length}."
    #     )

    # # @room.command()
    # # @club_manage_messages_check()
    # # async def unmute(self, ctx, user: discord.Member):
    # #     """Unmutes a user from a room. Ie. `[p]room unmute @user`"""
    # #     async with self.room_mutes_lock:
    # #         if (
    # #             str(user.id) in self.room_mutes
    # #             and str(ctx.channel.id) in self.room_mutes[str(user.id)]
    # #         ):
    # #             del self.room_mutes[str(user.id)][str(ctx.channel.id)]
    # #             if not self.room_mutes[str(user.id)]:
    # #                 del self.room_mutes[str(user.id)]
    # #             dataIOa.save_json(CLUB_MODERATION_JSON, self.room_mutes)
    # #     await self.channel_perm_edit_helper(
    # #         ctx.guild, ctx.channel.id, user.id, send_messages=None
    # #     )
    # #     await ctx.send(f"{user.mention} has been unmuted.")

    # # @room.command()
    # # @club_manage_messages_check()
    # # async def slow(self, ctx, length: str = "5s"):
    #     """Sets or disables slowmode for a room. Ie. `[p]room slow 5s`"""
    #     # This code is duplicated from mod.py; consider refactoring
    #     seconds = time_string_to_seconds(length)
    #     if length.lower() == "off":
    #         seconds = 0
    #     if seconds is None:
    #         p = dutils.bot_pfx(ctx.bot, ctx.message)
    #         return await ctx.send(
    #             f"Could not parse slow length. Are you sure you're giving it in the right format? Ex: {p}slow 30m, or {p}slow 1d4h3m2s, etc."
    #         )
    #     if seconds > 60 * 60 * 6:
    #         return await ctx.send(
    #             "You can't set slow mode intervals for that long. Can't be over 6 hours."
    #         )
    #     await ctx.channel.edit(slowmode_delay=seconds)
    #     if seconds == 0:
    #         await ctx.send("🚦Slow mode off.")
    #     else:
    #         await ctx.send(f"🚦Slow mode set to {seconds}s.")

    # @room.command()
    # @commands.check(ban_members_check)
    # async def visibility(self, ctx, club, level: str):
    #     """Edits the visibility of a room. Available options are: public and standard. [Admins only] Ie. `[p]room visibility pcmasterrace public`"""
    #     modes = {"public": AccessLevel.PUBLIC, "standard": AccessLevel.STANDARD}
    #     if level not in modes:
    #         return await ctx.send(
    #             "Invalid level for visibility. Available levels: `public` (everybody), `standard` (club members)."
    #         )
    #     await self.edit_club_metadata(
    #         ctx, club, "room access level", {ROOM_ACCESS_LEVEL_STRING: modes[level]}
    #     )

    @commands.group(aliases=["c"])
    @commands.guild_only()
    async def club(self, ctx):
        """Functionality related to clubs."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    async def _create(self, ctx, club, txt):
        club_pattern = re.compile("^[A-Za-zÀ-ÖØ-öø-ÿ0-9一-龯ぁ-んァ-ン_;'-]*$")
        if not club_pattern.match(club):
            return await ctx.send(
                f"`{discord.utils.escape_mentions(club).replace('`', '')}` is not a valid club name."
            )
        if len(club) > MAX_CLUB_NAME_LENGTH:
            raise InvalidCommandUsage(
                f"Your club name is too long. Please limit it to under {MAX_CLUB_NAME_LENGTH} characters."
            )
        if len(txt) > MAX_DESCRIPTION_LEN:
            raise InvalidCommandUsage(
                f"Your description is too long, please shorten it to under {MAX_DESCRIPTION_LEN} characters."
            )
        club_display_name = club
        club = club.lower()
        if not self.club_manager.club_exists(club, check_deleted=True):
            em = discord.Embed(
                title="Club approval",
                description=f"New club: `{club}`\nBy: {ctx.author.mention}\nDescription: {txt}\n\n[Source]({ctx.message.jump_url})",
                timestamp=ctx.message.created_at,
            )
            if "Reports" in self.bot.cogs:
                mod_channel = self.bot.cogs["Reports"].get_reports_setting(ctx.guild.id, "reports_channel")
            else:
                mod_channel = None
            if mod_channel:
                approval_msg = await self.bot.get_channel(mod_channel).send(
                    content=None, embed=em
                )
                self.approvals[approval_msg.id] = club
            else:
                approval_msg = None
            self.club_manager.create_new_club(
                club,
                **{
                    DESCRIPTION_STRING: txt,
                    APPROVAL_LISTENER_STRING: getattr(approval_msg, "id", None),
                    DISPLAY_NAME_STRING: club_display_name,
                    CREATION_TIMESTAMP_STRING: int(datetime.now().timestamp()),
                },
            )
            await self.join_helper(ctx, club, str(ctx.author.id), Permissions.PRESIDENT)
            if approval_msg:
                await approval_msg.add_reaction("✅")
                await approval_msg.add_reaction("❌")
            await ctx.send(
                f"Successfully created club and added you to it!\n\nNote: A mod will still need to approve this club. In the event of a veto, the club will be deleted.\n\nGet others to join this club by having them type `[p]join {club}` Anyone can then ping all the members of the club with the command `[p]ping {club}` or `[p]pingclub {club}`".replace(
                    '[p]', dutils.bot_pfx_by_ctx(ctx))
            )
        else:
            raise InvalidCommandUsage(
                "This club already exists. View a list of clubs with `[p]club list`"
            )

    @club.command()
    async def create(self, ctx, club, *, txt):
        """Create a club that people can join. Ie. `[p]club create pcmasterrace enthusiasts of gaming-ready desktop PCs.`"""
        await self._create(ctx, club, txt)

    @club.command()
    @permissions_check(club_name_position=2)
    async def delete(self, ctx, club):
        """Delete a club."""
        club = club.lower()
        club_metadata = self.club_manager.get_club_metadata(club)
        if club_metadata:
            await ctx.send("Are you sure? This **cannot** be reversed. (y/n)")
            reply = await ctx.bot.wait_for(
                "message",
                check=lambda m: m.channel == ctx.channel and m.author == ctx.author,
                timeout=30,
            )
            if not reply or reply.content.lower() != "y":
                await ctx.send("Deletion cancelled.")
            else:
                self.club_logger.info(f"Deleted {club} by {ctx.author}")
                await self.delete_helper(ctx.guild, club_metadata, club)
                await ctx.send(f"Successfully deleted the club: `{club}`.")
        else:
            await self.closest_club(ctx, club)

    async def _join(self, ctx, club):
        club = club.lower()
        if self.club_manager.club_exists(club):
            if not self.club_manager.link_exists(club, str(ctx.author.id)):
                return_msg, join_success = await self.join_helper(
                    ctx, club, str(ctx.author.id)
                )
                return await ctx.send(return_msg)
            else:
                return await ctx.send("You're already in the club.")
        else:
            await self.closest_club(ctx, club)

    @club.command(name="join")
    async def club_join(self, ctx, club):
        """Join a club. (alias)"""
        return await self._join(ctx, club)

    @commands.command(name="join", aliases=["joinclub"])
    @commands.guild_only()
    async def top_join(self, ctx, club):
        """Join a club. Ie. `[p]join pcmasterrace`"""
        return await self._join(ctx, club)

    async def _leave(self, ctx, club):
        club = club.lower()
        if self.club_manager.link_exists(club, str(ctx.author.id)):
            return_message, leave_success = await self.leave_helper(
                ctx.guild, club, str(ctx.author.id)
            )
            if leave_success:
                await ctx.message.delete()
            await ctx.send(return_message, delete_after=5)
        else:
            return await ctx.send(
                "You're not part of that club, or the club doesn't exist."
            )

    @club.command(name="leave")
    async def club_leave(self, ctx, club):
        """Leave a club. (alias)"""
        return await self._leave(ctx, club)

    @commands.command(name="leave", aliases=["leaveclub"])
    @commands.guild_only()
    async def top_leave(self, ctx, club):
        """Leave a club. Ie. `[p]leave pcmasterrace`"""
        return await self._leave(ctx, club)

    @club.group(aliases=["e"])
    async def edit(self, ctx):
        """Functionality related to editing clubs. (ratelimit, description, banner, thumbnail, colour, access)"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def ratelimit(self, ctx, club, length: str):
        """Edits the rate limit (time between pings) of the club. Ie. `[p]club edit ratelimit club 10s`"""
        seconds = time_string_to_seconds(length)
        if seconds is not None:
            if seconds > MAX_RATE_LIMIT_TIME:
                await ctx.send("Rate limit cannot be longer than 7 days.")
            else:
                await self.edit_club_metadata(
                    ctx, club, "rate limit", {RATE_LIMIT_STRING: seconds}
                )
        else:
            await ctx.send(
                "Could not parse rate limit length. Are you sure you're giving it the right format?"
            )

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def description(self, ctx, club, *, txt):
        """Edits the description for a club. [Club mods/president only] Ie. `[p]club edit description pcmasterrace something something`"""
        if len(txt) > MAX_DESCRIPTION_LEN:
            await ctx.send(
                f"Description is too long. Please limit it to under {MAX_DESCRIPTION_LEN} characters."
            )
        else:
            await self.edit_club_metadata(
                ctx, club, "description", {DESCRIPTION_STRING: txt}
            )

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def banner(self, ctx, club, banner: str):
        """Edits the banner for a club. [Club mods/president only] Ie. `[p]club edit banner pcmasterrace <bannerurl>` or `[p]club edit banner pcmasterrace remove`"""
        if banner == "remove":
            await self.edit_club_metadata(
                ctx, club, "banner (remove)", {BANNER_STRING: None}
            )
        elif await is_url_image_of_ratio(banner, 3 / 1):
            await self.edit_club_metadata(
                ctx, club, "banner (add)", {BANNER_STRING: banner}
            )
        else:
            await ctx.send(
                "The image isn't valid, try again. The banner has to be an image URL that has an aspect ratio of at least 3:1."
            )

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def thumbnail(self, ctx, club, thumbnail: str):
        """Edits the thumbnail for a club. [Club mods/president only] Ie. `[p]club edit thumbnail pcmasterrace <thumbnailurl>` or `[p]club edit thumbnail pcmasterrace remove`"""
        if thumbnail == "remove":
            await self.edit_club_metadata(
                ctx, club, "thumbnail (remove)", {THUMBNAIL_STRING: None}
            )
        elif await is_url_image(thumbnail):
            await self.edit_club_metadata(
                ctx, club, "thumbnail (add)", {THUMBNAIL_STRING: thumbnail}
            )
        else:
            await ctx.send(
                "The image isn't valid, try again. The thumbnail has to be an image URL."
            )

    @edit.command(aliases=["color"])
    @permissions_check(club_name_position=3, requires_president=False)
    async def colour(self, ctx, club, colour: str):
        """Edits the colour for a club. [Club mods/president only] Ie. `[p]club edit colour pcmasterrace <colour hex string>` or `[p]club edit colour pcmasterrace remove`
        This is a useful tool: [colour-picker](https://htmlcolorcodes.com/color-picker/)
        """
        if colour == "remove":
            await self.edit_club_metadata(
                ctx,
                club,
                "colour (remove)",
                {COLOUR_INT_STRING: CLUB_METADATA_DEFAULTS[COLOUR_INT_STRING]},
            )
        if "#" in colour:
            colour = colour.replace("#", "")
        if len(colour) <= 6 and set(colour).issubset(hexdigits):
            await self.edit_club_metadata(
                ctx, club, "colour (add)", {COLOUR_INT_STRING: int(colour, 16)}
            )
        else:
            return await ctx.send(
                f"`{colour}` isn't a valid colour. Try https://htmlcolorcodes.com/color-picker/"
            )

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def access(self, ctx, club, level: str):
        """Edits the access level for a club. Available options are: public, standard, and strict. [Club mods/president only] Ie. `[p]club edit access pcmasterrace public`"""
        modes = {
            "public": AccessLevel.PUBLIC,
            "standard": AccessLevel.STANDARD,
            "strict": AccessLevel.STRICT,
        }
        if level not in modes:
            return await ctx.send(
                "Invalid level for ping security. Available levels: `public` (everybody), `standard` (club members), `strict` (club president/mods only)."
            )
        await self.edit_club_metadata(
            ctx, club, "access level", {ACCESS_LEVEL_STRING: modes[level]}
        )

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def disableping(self, ctx, club, user: discord.Member):
        """Removes a user's ability to ping this club. [Club mods/president only] Ie. `[p]club edit disableping pcmasterrace @user`"""
        club = club.lower()
        club_metadata = self.club_manager.get_club_metadata(club)
        if club_metadata:
            if str(user.id) in club_metadata[NOPING_LIST_STRING]:
                return await ctx.send("They're already denied from pinging.")
            else:
                return await self.edit_club_metadata(
                    ctx,
                    club,
                    f"disableping: {user}",
                    {
                        NOPING_LIST_STRING: [
                            *club_metadata[NOPING_LIST_STRING],
                            str(user.id),
                        ]
                    },
                )
        else:
            await self.closest_club(ctx, club)

    @edit.command()
    @permissions_check(club_name_position=3, requires_president=False)
    async def enableping(self, ctx, club, user: discord.Member):
        """Reinstates a user's ability to ping this club. [Club mods/president only] Ie. `[p]club edit enableping pcmasterrace @user`"""
        club = club.lower()
        club_metadata = self.club_manager.get_club_metadata(club)
        if club_metadata:
            if str(user.id) in club_metadata[NOPING_LIST_STRING]:
                club_metadata[NOPING_LIST_STRING].remove(str(user.id))
                return await self.edit_club_metadata(
                    ctx,
                    club,
                    f"enableping: {user}",
                    {NOPING_LIST_STRING: club_metadata[NOPING_LIST_STRING]},
                )
            else:
                return await ctx.send("This user wasn't denied from pinging.")
        else:
            await self.closest_club(ctx, club)

    @edit.command()
    @permissions_check(club_name_position=3)
    async def addmod(self, ctx, club, user: discord.Member):
        """Adds a user as a moderator for a club. [President only] Ie. `[p]club edit addmod pcmasterrace @user`"""
        club = club.lower()
        link = self.club_manager.get_link_metadata(club, user.id)
        if link:
            if link[PERMISSIONS_STRING] == Permissions.PRESIDENT:
                await ctx.send("The president can't also be a mod.")
            else:
                await self.edit_link_metadata(
                    ctx,
                    club,
                    str(user.id),
                    f"`mod: {user}`",
                    {PERMISSIONS_STRING: Permissions.MODERATOR},
                )
        else:
            await ctx.send("That user isn't in the club.")

    @edit.command()
    @permissions_check(club_name_position=3)
    async def removemod(self, ctx, club, user: discord.Member):
        """Removes moderator status from a club member. [President only] Ie. `[p]club edit removemod pcmasterrace @user`"""
        club = club.lower()
        link = self.club_manager.get_link_metadata(club, user.id)
        if link and link[PERMISSIONS_STRING] == Permissions.MODERATOR:
            await self.edit_link_metadata(
                ctx,
                club,
                str(user.id),
                f"`demod: {user}`",
                {PERMISSIONS_STRING: Permissions.USER},
            )
        else:
            await ctx.send("That user isn't a moderator.")

    @edit.command()
    @permissions_check(club_name_position=3)
    async def changepresident(self, ctx, club, user: discord.Member):
        """Hand over the club presidency to another member of the club. [President only] Ie. `[p]club edit changepresident pcmasterrace @user`"""
        club = club.lower()
        members = self.club_manager.get_club_users(club)
        club_president = None
        for member, md in members.items():
            if md[LINK_METADATA_STRING][PERMISSIONS_STRING] == Permissions.PRESIDENT:
                club_president = member
                break
        success = await self.edit_link_metadata(
            ctx,
            club,
            str(user.id),
            f"`president: {user}`",
            {PERMISSIONS_STRING: Permissions.PRESIDENT},
        )
        if success:
            if club_president and club_president != str(user.id):
                await self.edit_link_metadata(
                    ctx,
                    club,
                    club_president,
                    "",
                    {PERMISSIONS_STRING: Permissions.USER},
                    silent=True,
                )
        else:
            await self.edit_link_metadata(
                ctx,
                club,
                str(user.id),
                "",
                {PERMISSIONS_STRING: Permissions.USER},
                silent=True,
            )

    @edit.command()
    @commands.check(ban_members_check)
    async def rolify(self, ctx, club: str):
        """Mods only. Makes a club into a role."""
        club = club.lower()
        club_metadata = self.club_manager.get_club_metadata(club)
        if club_metadata and not club_metadata[ROLE_STRING]:
            role = await ctx.guild.create_role(name=f"club: {club}")
            self.club_manager.edit_club_metadata(club, **{ROLE_STRING: str(role.id)})
            club_users = self.club_manager.get_club_users(club)
            await self.role_add_helper(
                ctx.guild, role.id, *club_users.keys(), role=role
            )
            return await ctx.send(
                f"Done converting `{club}` into role! {ctx.author.mention}"
            )
        else:
            if not club_metadata:
                return await ctx.send("Club doesn't exist.")
            else:
                return await ctx.send("Club already has a role.")

    @edit.command()
    @commands.check(ban_members_check)
    async def derolify(self, ctx, club):
        """Mods only. Remove a club from role status."""
        club = club.lower()
        club_metadata = self.club_manager.get_club_metadata(club)
        if club_metadata and club_metadata[ROLE_STRING]:
            self.club_manager.edit_club_metadata(club, **{ROLE_STRING: None})
            role = ctx.guild.get_role(int(club_metadata[ROLE_STRING]))
            club_users = self.club_manager.get_club_users(club)
            if role:
                await self.role_delete_helper(ctx.guild, role.id)
            return await ctx.send(
                f"Done removing role status for `{club}`! {ctx.author.mention}"
            )
        else:
            if not club_metadata:
                return await ctx.send("Club doesn't exist.")
            else:
                return await ctx.send("Club doesn't have a role.")

    # async def _roomify(self, ctx, club):
    #     club = club.lower()
    #     club_metadata = self.club_manager.get_club_metadata(club)
    #     if club_metadata:
    #         club_json = dataIOa.load_json(CLUB_JSON)
    #         if (
    #             not club_metadata[CHANNEL_ID_STRING]
    #             and CLUB_JSON_CATEGORY in club_json
    #             and CLUB_JSON_ACCESS_ROLE in club_json
    #         ):
    #             category = ctx.guild.get_channel(club_json[CLUB_JSON_CATEGORY])
    #             overwrites = category.overwrites
    #             # We'll only use read_messages because mutes/lock rely on send_messages
    #             overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(
    #                 read_messages=False
    #             )
    #             channel = await ctx.guild.create_text_channel(
    #                 "placeholder",
    #                 category=category,
    #                 overwrites=overwrites,
    #             )
    #             await self.channel_init_helper(
    #                 ctx.guild,
    #                 club,
    #                 channel,
    #                 club_json[CLUB_JSON_CATEGORY],
    #                 club_json[CLUB_JSON_ACCESS_ROLE],
    #             )
    #             self.club_logger.info(
    #                 f"Roomified {club} with {len(overwrites)} overwrites"
    #             )
    #             await ctx.send(f"Done! Check it out here: {channel.mention}")
    #         elif club_metadata[CHANNEL_ID_STRING]:
    #             channel = ctx.guild.get_channel(int(club_metadata[CHANNEL_ID_STRING]))
    #             raise InvalidCommandUsage(
    #                 f"This club already has a room: {channel.mention}. Transaction cancelled."
    #             )
    #         else:
    #             raise InvalidCommandUsage(
    #                 "Club rooms isn't set up yet. Transaction cancelled."
    #             )
    #     else:
    #         raise InvalidCommandUsage("Couldn't find this club. Transaction cancelled.")

    # @edit.command()
    # @permissions_check(club_name_position=3)
    # async def roomify(self, ctx, club: str):
    #     """President only. Creates a club room."""
    #     await self._roomify(ctx, club)

    # @edit.command()
    # @permissions_check(club_name_position=3)
    # async def deroomify(self, ctx, club: str):
    #     """President only. Deletes a club room."""
    #     club = club.lower()
    #     club_metadata = self.club_manager.get_club_metadata(club)
    #     if club_metadata:
    #         if club_metadata[CHANNEL_ID_STRING]:
    #             await ctx.send("Are you sure? This **cannot** be reversed. (y/n)")
    #             reply = await ctx.bot.wait_for(
    #                 "message",
    #                 check=lambda m: m.channel == ctx.channel and m.author == ctx.author,
    #                 timeout=30,
    #             )
    #             if not reply or reply.content.lower() != "y":
    #                 await ctx.send("Deletion cancelled.")
    #             else:
    #                 await self.room_delete_helper(
    #                     ctx.guild, club_metadata[CHANNEL_ID_STRING], club
    #                 )
    #                 self.club_manager.edit_club_metadata(
    #                     club, **{CHANNEL_ID_STRING: None}
    #                 )
    #                 self.club_logger.info(f"De-roomified {club} by {ctx.author}")
    #                 await ctx.send(
    #                     f"Done! Deleted room for `{club_metadata[DISPLAY_NAME_STRING]}`"
    #                 )
    #     else:
    #         await self.closest_club(ctx, club)

    @commands.group()
    @commands.guild_only()
    async def usersettings(self, ctx):
        """Functionality related to creating and editing club user settings."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @usersettings.command()
    async def ignore(self, ctx, user_ignore: discord.Member):
        """Users can block club pings from specific users."""
        await ctx.message.delete()
        user_metadata = self.club_manager.get_user_metadata(str(ctx.author.id))
        if str(user_ignore.id) not in user_metadata[IGNORED_USER_STRING]:
            await self.edit_user_metadata(
                ctx,
                str(ctx.author.id),
                "",
                {
                    IGNORED_USER_STRING: [
                        *user_metadata[IGNORED_USER_STRING],
                        str(user_ignore.id),
                    ]
                },
                silent=True,
            )
            await ctx.send("Done.", delete_after=3)

    @usersettings.command()
    async def unignore(self, ctx, user_unignore: discord.Member):
        """Stop ignoring a user's club pings."""
        await ctx.message.delete()
        user_metadata = self.club_manager.get_user_metadata(str(ctx.author.id))
        if str(user_unignore.id) in user_metadata[IGNORED_USER_STRING]:
            user_metadata[IGNORED_USER_STRING].remove(str(user_unignore.id))
            await self.edit_user_metadata(
                ctx,
                str(ctx.author.id),
                "",
                {IGNORED_USER_STRING: user_metadata[IGNORED_USER_STRING]},
                silent=True,
            )
            await ctx.send("Done.", delete_after=3)

    async def club_list_printer(
            self,
            ctx,
            title,
            clubs,
            *,
            compact=False,
            sort_string=MEMBERCOUNT_STRING,
    ):
        sort_functions = {
            PINGCOUNT_STRING: lambda lst: lst.sort(
                key=lambda m: int(clubs[m][PINGCOUNT_STRING]), reverse=True
            ),
            MEMBERCOUNT_STRING: lambda lst: lst.sort(
                key=lambda m: int(clubs[m][MEMBERCOUNT_STRING]), reverse=True
            ),
            LAST_PING_TIMESTAMP_STRING: lambda lst: lst.sort(
                key=lambda m: int(clubs[m][LAST_PING_TIMESTAMP_STRING]), reverse=True
            ),
            DISPLAY_NAME_STRING: lambda lst: lst.sort(
                key=lambda m: str(clubs[m][DISPLAY_NAME_STRING])
            ),
        }
        clubs_iterator = [club for club in clubs]
        sort_functions[sort_string](clubs_iterator)
        clubs_length = len(clubs)
        embeds = []
        items_per_page = 8 * (3 if compact else 1)
        page_count = (clubs_length // items_per_page) + bool(
            clubs_length % items_per_page
        )
        for page, index in enumerate(range(0, clubs_length, items_per_page)):
            em = discord.Embed(
                color=0x6600FF, title=title + f", page {page + 1} of {page_count}"
            )
            desc = []
            footer = ["Available sorting options: pings, recent, members, alphabetical"]
            for club in clubs_iterator[index: index + items_per_page]:
                if compact:
                    max_length = 60 - len(club)
                    club_desc = clubs[club][DESCRIPTION_STRING].splitlines()[0]
                    desc.append(
                        f"**{club}** - {self.sanitize_string(club_desc[:max_length] + ('...' if len(club_desc) > max_length else ''))}"
                    )
                else:
                    em.add_field(
                        name=club,
                        value=f"Members: {clubs[club][MEMBERCOUNT_STRING]} | Pings: {clubs[club][PINGCOUNT_STRING]}\n>>> {clubs[club][DESCRIPTION_STRING][:200] + ('...' if len(clubs[club][DESCRIPTION_STRING]) > 200 else '')}",
                        inline=False,
                    )
            if desc:
                footer.append(
                    "To list clubs with full descriptions, use the full option."
                )
                em.description = "\n".join(desc)
            em.set_footer(text="\n".join(footer))
            embeds.append(em)
        if len(embeds) > 1:
            await SimplePaginator(extras=embeds).paginate(ctx)
        elif len(embeds) == 1:
            await ctx.send(content=None, embed=embeds[0])
        else:
            await ctx.send("No results.")

    @staticmethod
    def extract_options(ctx, raw_str, default_sort="members", default_compact=True):
        sort = {
            "pings": PINGCOUNT_STRING,
            "members": MEMBERCOUNT_STRING,
            "recent": LAST_PING_TIMESTAMP_STRING,
            "alphabetical": DISPLAY_NAME_STRING,
        }
        raw_str = raw_str.split()
        user = ctx.message.raw_mentions
        if not user:
            for potential_user in raw_str:
                try:
                    potential_user = ctx.guild.get_member(int(potential_user))
                    if potential_user:
                        user = potential_user.id
                        break
                except ValueError:
                    continue
        else:
            user = user[0]
        compact = False if "full" in raw_str else default_compact
        rooms = "rooms" in raw_str
        raw_str = filter(lambda k: k in sort.keys(), raw_str)
        mapping = set()
        for s in raw_str:
            if s in sort.keys() and s not in mapping:
                mapping.add((s, sort[s]))
        return {
            "sort": [(default_sort, sort[default_sort])]
            if not len(mapping)
            else list(mapping),
            "compact": compact,
            "rooms": rooms,
            "user": user,
        }

    @club.command(aliases=["l"])
    async def list(self, ctx, *, options: str = ""):
        """Catch-all for listing clubs. More info under [p]help club list

        The available options are:
        - `full` - show full details of the clubs
        - `@user` - show the club a particular user is in
        - `pings` - sort by number of pings
        - `recent` - sort by last pinged
        - `members` - sort by member count (default)
        - `alphabetical` - sort by name
        - `rooms` - show clubs with rooms only

        Note that the options order does not matter.

        Examples:
        `[p]club list full recent` will show recently pinged clubs, with full descriptions
        `[p]club list pings @user` will show @user's clubs, sorted by pings
        `[p]club list rooms` will show clubs with rooms only
        """
        options = self.extract_options(ctx, options)
        sort = options["sort"]
        compact = options["compact"]
        rooms_func = (lambda c: c[CHANNEL_ID_STRING]) if options["rooms"] else None
        if len(sort) > 1:
            return await ctx.send(
                "You can only specify one of `pings`, `members`, or `recent`."
            )
        # TODO rewrite this entire function, it blows
        if options["user"]:
            clubs = self.club_manager.get_user_clubs(str(options["user"]))
            if rooms_func:
                clubs = {c: md for c, md in clubs.items() if rooms_func(md)}
            modified_club_dict = {}
            for md in clubs.values():
                parameters = []
                if md[METADATA_STRING][ACCESS_LEVEL_STRING] != AccessLevel.STANDARD:
                    parameters.append(
                        f"`ping:{ACCESS_LEVEL_MAP[md[METADATA_STRING][ACCESS_LEVEL_STRING]]}`"
                    )
                if md[METADATA_STRING][CHANNEL_ID_STRING]:
                    parameters.append(
                        f"`room:{ACCESS_LEVEL_MAP[md[METADATA_STRING][ROOM_ACCESS_LEVEL_STRING]]}`"
                    )
                if (
                        md[LINK_METADATA_STRING][PERMISSIONS_STRING]
                        == Permissions.PRESIDENT
                ):
                    parameters.append("`president`")
                elif (
                        md[LINK_METADATA_STRING][PERMISSIONS_STRING]
                        == Permissions.MODERATOR
                ):
                    parameters.append("`moderator`")
                modified_club_dict[
                    f"{md[METADATA_STRING][DISPLAY_NAME_STRING]} {' - '.join(parameters)}"
                ] = md[METADATA_STRING]
            return await self.club_list_printer(
                ctx,
                f"All {len(modified_club_dict)} clubs {ctx.guild.get_member(options['user'])} is in (sort: `{sort[0][0]}`)",
                modified_club_dict,
                compact=compact,
                sort_string=sort[0][1],
            )
        else:
            clubs = self.club_manager.get_all_clubs()
            if rooms_func:
                clubs = {c: md for c, md in clubs.items() if rooms_func(md)}
            modified_club_dict = {}
            for md in clubs.values():
                parameters = []
                if md[ACCESS_LEVEL_STRING] != AccessLevel.STANDARD:
                    parameters.append(
                        f"`ping:{ACCESS_LEVEL_MAP[md[ACCESS_LEVEL_STRING]]}`"
                    )
                if md[CHANNEL_ID_STRING]:
                    parameters.append(
                        f"`room:{ACCESS_LEVEL_MAP[md[ROOM_ACCESS_LEVEL_STRING]]}`"
                    )
                modified_club_dict[
                    f"{md[DISPLAY_NAME_STRING]} {' - '.join(parameters)}"
                ] = md
            return await self.club_list_printer(
                ctx,
                f"All {len(clubs)} clubs users can join (sort: `{sort[0][0]}`)",
                modified_club_dict,
                compact=compact,
                sort_string=sort[0][1],
            )

    @club.command(aliases=["s"])
    async def search(self, ctx, *, keywords: str):
        """Search for clubs. Ie. `[p]club search wholesome things`

        Note that you can specify the same sort parameters as list, but enclosed in `[]`.
        Ie. `[p]club search wholesome [full recent]`
        """
        match = re.findall("\[([\d\D]+?)\]", keywords)
        options = match[0] if len(match) else ""
        keywords = keywords.replace(options, "").replace("[]", "")
        options = self.extract_options(ctx, options)
        sort = options["sort"]
        compact = options["compact"]
        if len(sort) > 1:
            return await ctx.send(
                "You can only specify one of `pings`, `members`, or `recent`."
            )
        if len(keywords) < 3:
            return await ctx.send("Try longer keywords.")
        keywords = keywords.lower().strip().split()
        clubs = self.club_manager.get_all_clubs()
        results = {}
        for club, md in clubs.items():
            if any(
                    [
                        keyword in club.lower() or keyword in md[DESCRIPTION_STRING].lower()
                        for keyword in keywords
                    ]
            ):
                parameters = []
                if md[ACCESS_LEVEL_STRING] != AccessLevel.STANDARD:
                    parameters.append(f"`{ACCESS_LEVEL_MAP[md[ACCESS_LEVEL_STRING]]}`")
                results[f"{md[DISPLAY_NAME_STRING]} {' - '.join(parameters)}"] = md
        return await self.club_list_printer(
            ctx,
            f"Results for [{', '.join(keywords)}], (sort: `{sort[0][0]}`)",
            results,
            compact=compact,
            sort_string=sort[0][1],
        )

    @club.command(aliases=["rec"])
    async def recommend(self, ctx):
        """[EXPERIMENTAL] Get a list of club recommendations.

        The recommendation engine is loosely based on an association rule learning model.
        Given the club membership dataset, users that share a greater number of clubs with the target user will contribute more weight to whether a club should be recommended.

        For example, given this set of data, where the first column is the user and the other colums are club membership:

        ```
        user | art | ecchi | kaguya
        1       0       1       1
        2       0       1       0
        3       1       1       0
        ```

        If `user_1` calls the recommendation engine, `user_3` will contribute weight to the art club as a recommendation, since they share the ecchi club.
        """
        clubs = None
        results = {}

        # We throw it in a task for an executor to run since it's a really IO heavy command
        # I don't expect many people will use this so I'm not going to bother memoizing the calls
        # for now, but this might be an improvement for the future
        def task():
            clubs = self.club_manager.get_all_clubs()
            target_user = str(ctx.author.id)
            bitfield = {target_user: {}}
            for club in clubs:
                members = self.club_manager.get_club_users(club)
                for member in members:
                    if member not in bitfield:
                        bitfield[member] = {}
                    bitfield[member][club] = 1

            joined_clubs = set(bitfield[target_user])

            recommendations = {}

            for user in bitfield:
                if user != target_user:
                    common_clubs = joined_clubs.intersection(set(bitfield[user]))
                    for candidate_club in bitfield[user]:
                        if candidate_club not in joined_clubs:
                            if candidate_club in recommendations:
                                recommendations[candidate_club].append(
                                    len(common_clubs)
                                )
                            else:
                                recommendations[candidate_club] = [len(common_clubs)]

            recommendations = {
                rec: (sum(val) / len(val)) for rec, val in recommendations.items()
            }

            club_list = list(recommendations)
            club_list.sort(reverse=True, key=lambda k: recommendations[k])

            for i in range(8):
                current_club = clubs[club_list[i]]
                parameters = []
                if current_club[ACCESS_LEVEL_STRING] != AccessLevel.STANDARD:
                    parameters.append(
                        f"`{ACCESS_LEVEL_MAP[current_club[ACCESS_LEVEL_STRING]]}`"
                    )
                results[
                    f"{current_club[DISPLAY_NAME_STRING]} {' - '.join(parameters)}"
                ] = current_club

        await self.bot.loop.run_in_executor(None, task)
        return await self.club_list_printer(ctx, f"Recommendations", results)

    @club.command(aliases=["i"])
    async def info(self, ctx, club):
        """Show information about a club. Ie. `[p]club info pcmasterrace`"""
        club = club.lower()
        club_metadata = self.club_manager.get_club_metadata(club)
        if club_metadata:
            club_users = self.club_manager.get_club_users(club)
            club_president = 0
            club_mods = []
            for member, md in club_users.items():
                if (
                        md[LINK_METADATA_STRING][PERMISSIONS_STRING]
                        == Permissions.PRESIDENT
                ):
                    club_president = member
                elif (
                        md[LINK_METADATA_STRING][PERMISSIONS_STRING]
                        == Permissions.MODERATOR
                ):
                    club_mods.append(member)
            em = discord.Embed(
                color=club_metadata[COLOUR_INT_STRING],
                title=f"Club info for {club_metadata[DISPLAY_NAME_STRING]}",
            )
            club_president_user = ctx.guild.get_member(int(club_president))
            em.add_field(
                name="President",
                value=f"{getattr(club_president_user, 'mention', 'None')} `{club_president_user}`",
                inline=False,
            )
            if club_metadata[THUMBNAIL_STRING]:
                em.set_thumbnail(url=club_metadata[THUMBNAIL_STRING])
            if club_metadata[BANNER_STRING]:
                em.set_image(url=club_metadata[BANNER_STRING])
            if len(club_mods):
                club_mods_user = [
                    ctx.guild.get_member(int(member)) for member in club_mods
                ]
                em.add_field(
                    name="Mods",
                    value="\n".join(
                        [
                            f"{mod.mention} `{mod}`"
                            for mod in filter(bool, club_mods_user)
                        ]
                    ),
                    inline=False,
                )
            em.add_field(
                name="Description",
                value=club_metadata[DESCRIPTION_STRING],
                inline=False,
            )
            if club_metadata[CHANNEL_ID_STRING]:
                room_channel = ctx.guild.get_channel(
                    int(club_metadata[CHANNEL_ID_STRING])
                ).mention
                room_visibility = f" (visibility: {ACCESS_LEVEL_MAP[club_metadata[ROOM_ACCESS_LEVEL_STRING]]})"
                em.add_field(
                    name="Room",
                    value=room_channel + room_visibility,
                    inline=False,
                )
            em.add_field(
                name="Created On",
                value=(
                    datetime.fromtimestamp(
                        club_metadata[CREATION_TIMESTAMP_STRING]
                    ).strftime("%b %d, %Y")
                ),
                inline=True,
            )
            em.add_field(
                name="Role-Based",
                value="Yes" if club_metadata[ROLE_STRING] else "No",
                inline=True,
            )
            em.add_field(
                name="Ping Permission",
                value=ACCESS_LEVEL_MAP[club_metadata[ACCESS_LEVEL_STRING]].capitalize(),
                inline=True,
            )
            em.add_field(name="Members", value=len(club_users), inline=True)
            em.add_field(
                name="Ping Count", value=club_metadata[PINGCOUNT_STRING], inline=True
            )
            em.add_field(
                name="Approved?",
                value=("Not yet" if club_metadata[APPROVAL_LISTENER_STRING] else "Yes"),
                inline=True,
            )
            em.add_field(
                name="Sentiment",
                value=str(self.get_club_sentiment(club_metadata)),
                inline=True,
            )
            em.add_field(
                name="Rate Limit",
                value=time_seconds_to_string(club_metadata[RATE_LIMIT_STRING])
                if club_metadata[RATE_LIMIT_STRING] > 0
                else "None",
                inline=True,
            )
            embeds = [em]
            users = [user for user in club_users if ctx.guild.get_member(int(user))]
            users_length = len(users)
            members_per_page = 20
            page_count = (users_length // members_per_page) + bool(
                users_length % members_per_page
            )
            for page, index in enumerate(range(0, users_length, members_per_page)):
                embeds.append(
                    discord.Embed(
                        color=club_metadata[COLOUR_INT_STRING],
                        title=f"Members of {club}, page {page + 1} of {page_count}",
                        description="\n".join(
                            [
                                str(ctx.guild.get_member(int(user)))
                                for user in users[index: index + members_per_page]
                            ]
                        ),
                    )
                )
            await SimplePaginator(extras=embeds).paginate(ctx)
        else:
            await self.closest_club(ctx, club)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        user_clubs = self.club_manager.get_user_clubs(str(member.id))
        if user_clubs:
            for club in user_clubs.keys():
                await self.leave_helper(member.guild, club, str(member.id))
        self.club_manager.delete_user(str(member.id))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.bot.wait_until_ready()
        # Handles approvals of clubs
        if (
                event.message_id in self.approvals
                and event.emoji.name in ["✅", "❌"]
        ):
            channel = self.bot.get_channel(event.channel_id)
            user = channel.guild.get_member(event.user_id)
            if (
                    channel.permissions_for(user).manage_roles
                    and user.id != channel.guild.me.id
            ):
                msg = await self.bot.get_channel(event.channel_id).fetch_message(
                    event.message_id
                )
                club = self.approvals[event.message_id]
                del self.approvals[event.message_id]
                if event.emoji.name == "✅":
                    self.club_manager.edit_club_metadata(
                        club, **{APPROVAL_LISTENER_STRING: None}
                    )
                else:
                    club = club.lower()
                    club_metadata = self.club_manager.get_club_metadata(club)
                    await self.delete_helper(
                        self.bot.get_guild(event.guild_id), club_metadata, club
                    )
                await msg.add_reaction("👌")
        # Handles reactions to pings
        if (
                event.message_id in self.react_listeners
                and event.user_id != self.bot.user.id
                and event.user_id not in self.react_listeners[event.message_id][0]
        ):
            reacted_users, clubs, _ = self.react_listeners[event.message_id]
            reacted_users.add(event.user_id)
            for c in clubs:
                club_metadata = self.club_manager.get_club_metadata(c)
                self.club_manager.edit_club_metadata(
                    c,
                    **{
                        REACTS_COUNT_STRING: club_metadata[REACTS_COUNT_STRING] + 1,
                    },
                )
        # Instead of creating a task, we'll just prune here
        current_time = int(datetime.now().timestamp())
        copied_react_listeners = self.react_listeners.copy()
        for message_id, [_, _, timestamp] in copied_react_listeners.items():
            if current_time - timestamp > MAX_PING_REACT_TIME:
                del self.react_listeners[message_id]

    @commands.command(aliases=["pingclub"])
    @commands.guild_only()
    async def ping(self, ctx, club, *, message: str = ""):
        """Ping all members of a club (with optional message). Ie `[p]ping pcmasterrace hey guys check out my new rig.`"""
        club = club.lower()
        return await self.ping_helper(ctx, [club])

    @commands.command(aliases=["pingmulti", "multiping", "pa", "pm"])
    async def pingall(self, ctx, *, clubs: str):
        """Ping all members of multiple clubs. Ie `[p]pingall pcmasterrace fancomics`"""
        clubs = clubs.split()
        return await self.ping_helper(ctx, clubs)

    async def ping_helper(self, ctx, clubs: list):
        metadata_dict = {}
        member_dict = {}
        club_json = dataIOa.load_json(CLUB_JSON)
        for club in clubs:
            club = club.lower()
            allowed_club = club_json.get(CLUB_JSON_CHANNEL_PING_OVERRIDES, {}).get(
                str(ctx.channel.id)
            )
            if allowed_club and allowed_club != club:
                return await ctx.send(
                    f"This channel restricts pings. Only the club `{allowed_club}` can be pinged in this channel."
                )
            metadata_dict[club] = self.club_manager.get_club_metadata(club)
            if metadata_dict[club]:
                member_dict[club] = self.club_manager.get_club_users(club)
                if (
                        str(ctx.author.id) not in member_dict[club]
                        and metadata_dict[club][ACCESS_LEVEL_STRING] != AccessLevel.PUBLIC
                ):
                    return await ctx.send(
                        f"`{club}` doesn't allow public pings and you're not a member; cannot ping.",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                if str(ctx.author.id) in metadata_dict[club][NOPING_LIST_STRING]:
                    return await ctx.send(
                        f"You're blacklisted from pinging `{club}`.",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                if metadata_dict[club][
                    ACCESS_LEVEL_STRING
                ] == AccessLevel.STRICT and member_dict[club][str(ctx.author.id)][
                    LINK_METADATA_STRING
                ][
                    PERMISSIONS_STRING
                ] not in [
                    Permissions.PRESIDENT,
                    Permissions.MODERATOR,
                ]:
                    return await ctx.send(
                        f"`{club}` only accepts pings from mods and the president.",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                if (
                        datetime.now().timestamp()
                        - int(metadata_dict[club][LAST_PING_TIMESTAMP_STRING])
                ) < metadata_dict[club][RATE_LIMIT_STRING]:
                    time_left = (
                            int(metadata_dict[club][LAST_PING_TIMESTAMP_STRING])
                            + metadata_dict[club][RATE_LIMIT_STRING]
                            - int(datetime.now().timestamp())
                    )
                    return await ctx.send(
                        f"`{club}` is rate-limited. Please wait `{time_seconds_to_string(time_left)}`.",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            else:
                return await self.closest_club(ctx, club)
        ping_str_list = self.get_ping_club_string(ctx, member_dict, metadata_dict)
        for ping_str in ping_str_list:
            ping_msg = await ctx.send(content=ping_str)
        haya_thumbs_up = discord.utils.get(ctx.guild.emojis, name="HayaThumbsUp")
        discord_emoji = haya_thumbs_up if haya_thumbs_up else "👍"
        await ping_msg.add_reaction(discord_emoji)
        self.react_listeners[ping_msg.id] = [
            set(),
            clubs,
            int(datetime.now().timestamp()),
        ]

    @commands.group()
    @commands.guild_only()
    async def clubutils(self, ctx):
        """Functionality related to clubs administration for mods. You won't need this if you're reading this."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    # @clubutils.command()
    # @commands.check(ban_members_check)
    # async def claim_room(self, ctx, club: str, channel: discord.TextChannel):
    #     """Claims a channel for a club.
    #     The channel must be in the right category and the club must exist.
    #     """
    #     club = club.lower()
    #     club_json = dataIOa.load_json(CLUB_JSON)
    #     club_metadata = self.club_manager.get_club_metadata(club)
    #     if CLUB_JSON_CATEGORY in club_json and club_metadata:
    #         if club_metadata[CHANNEL_ID_STRING]:
    #             channel = ctx.guild.get_channel(int(club_metadata[CHANNEL_ID_STRING]))
    #             channel = channel.mention if channel else "`failed to get channel`"
    #             return await ctx.send(f"This club already has a channel: {channel}")

    #         all_clubs = self.club_manager.get_all_clubs()
    #         for c, md in all_clubs.items():
    #             if md[CHANNEL_ID_STRING] and int(md[CHANNEL_ID_STRING]) == channel.id:
    #                 return await ctx.send(
    #                     f"I can't claim this channel since `{c}` already owns it."
    #                 )

    #         if channel.category_id != int(club_json[CLUB_JSON_CATEGORY]):
    #             return await ctx.send("Channel isn't in the right category. Try again.")

    #         await ctx.send(
    #             f"Are you sure? I'll be claiming {channel.mention} for `{club}` (y/n)"
    #         )
    #         reply = await ctx.bot.wait_for(
    #             "message",
    #             check=lambda m: m.channel == ctx.channel and m.author == ctx.author,
    #             timeout=30,
    #         )
    #         if not reply or reply.content.lower() != "y":
    #             await ctx.send("Cancelled.")
    #         else:
    #             await self.channel_init_helper(
    #                 ctx.guild,
    #                 club,
    #                 channel,
    #                 club_json[CLUB_JSON_CATEGORY],
    #                 club_json[CLUB_JSON_ACCESS_ROLE],
    #             )
    #             await ctx.send(f"Success. Check it out here: {channel.mention}")
    #     else:
    #         await ctx.send(
    #             "Club either doesn't exist or the club JSON isn't set up yet."
    #         )

    @clubutils.group()
    async def backup(self, ctx):
        """Functionality related to backups."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @backup.command(name="create")
    @commands.check(ban_members_check)
    async def backup_create(self, ctx):
        """Create a backup."""
        if not os.path.exists(BACKUP_DIR):
            os.mkdir(BACKUP_DIR)
        db = sqlite3.connect(DB)
        fn = datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
        backup = sqlite3.connect(f"{BACKUP_DIR}/{fn}")
        db.backup(backup)
        backup.close()
        db.close()
        await ctx.send(f"Backup saved as `{fn}`.")

    @backup.command(name="list")
    async def backup_list(self, ctx):
        """List all available backups."""
        if not os.path.exists(BACKUP_DIR):
            os.mkdir(BACKUP_DIR)
        newline = "\n"
        backups = os.listdir(BACKUP_DIR)
        if backups:
            await result_printer(
                ctx, f"Available backups:```\n{newline.join(os.listdir(BACKUP_DIR))}```"
            )
        else:
            await ctx.send("No backups available.")

    @backup.command(name="restore")
    @commands.check(ban_members_check)
    async def backup_restore(self, ctx, backup):
        """Restore a club backup. This should only be used in emergencies."""
        if not os.path.exists(f"{BACKUP_DIR}/{backup}"):
            return await ctx.send(
                f"Backup with name `{backup}` doesn't exist. Try `[p]clubutils backup list`"
            )
        await ctx.send(
            "Are you sure? (y/n) Make sure you create a backup before restoring because the database CANNOT be restored."
        )
        reply = await ctx.bot.wait_for(
            "message",
            check=lambda m: m.channel == ctx.channel and m.author == ctx.author,
            timeout=30,
        )
        if not reply or reply.content.lower() != "y":
            await ctx.send("Restore cancelled.")
        else:
            db = sqlite3.connect(f"{BACKUP_DIR}/{backup}")
            target = sqlite3.connect(DB)
            db.backup(target)
            target.close()
            db.close()
            await ctx.send("Successfully restored.")

    @clubutils.command()
    @commands.check(ban_members_check)
    async def csck(self, ctx, option):
        """Club system consistency check.
        Cleans dangling users and manages clubs.
        """

        # I could split this one out into a subgroup but this'll be so rarely used that I didn't bother
        async def clean_users():
            all_users = self.club_manager.get_all_users()
            prunable_users = set()
            for user in all_users.keys():
                if not ctx.guild.get_member(int(user)):
                    prunable_users.add(user)
            await ctx.send(
                f"Prunable users: `{len(prunable_users)}` out of `{len(all_users)}`. Would you like to continue? (y/n)"
            )
            reply = await ctx.bot.wait_for(
                "message",
                check=lambda m: m.channel == ctx.channel and m.author == ctx.author,
                timeout=30,
            )
            if not reply or reply.content.lower() != "y":
                return await ctx.send("Consistency check cancelled.")

            async def prune_task():
                for user in prunable_users:
                    await asyncio.sleep(0)
                    for club in self.club_manager.get_user_clubs(user):
                        await self.leave_helper(ctx.guild, club, user)
                        await asyncio.sleep(0)
                    self.club_manager.delete_user(str(user))

            async def user_count_consistency_task():
                # The above task should've handled it but we'll run this just in case
                all_clubs = self.club_manager.get_all_clubs()
                for club, md in all_clubs.items():
                    club = club.lower()
                    members = self.club_manager.get_club_users(club)
                    real_count = sum(1 for m in members if ctx.guild.get_member(int(m)))
                    if real_count != md[MEMBERCOUNT_STRING]:
                        self.club_manager.edit_club_metadata(
                            club, **{MEMBERCOUNT_STRING: real_count}
                        )

            status_msg = await ctx.send("Starting prune task..")
            await self.bot.loop.create_task(prune_task())
            await status_msg.edit(
                content="Starting prune task.. **Done**. Starting user count task.."
            )
            await self.bot.loop.create_task(user_count_consistency_task())
            await status_msg.edit(
                content=f"Starting prune task.. **Done**. Starting user count task.. **Done**. {ctx.author.mention}"
            )

        async def clean_roles():
            all_clubs = self.club_manager.get_all_clubs()
            log = []
            for club, metadata in all_clubs.items():
                club = club.lower()
                if (
                        metadata[ROLE_STRING]
                        and ctx.guild.get_role(int(metadata[ROLE_STRING])) is None
                ):
                    log.append(f"Cleaned role metadata for: '{club}'")
                    self.club_manager.edit_club_metadata(club, **{ROLE_STRING: None})
            if log:
                log = "\n".join(log)
                await result_printer(ctx, f"```\n{log}```")
            else:
                await ctx.send("No dangling roles, no action taken.")

        async def clean_channels():
            all_clubs = self.club_manager.get_all_clubs()
            log = []
            for club, metadata in all_clubs.items():
                club = club.lower()
                if (
                        metadata[CHANNEL_ID_STRING]
                        and ctx.guild.get_channel(int(metadata[CHANNEL_ID_STRING])) is None
                ):
                    log.append(f"Cleaned channel metadata for: '{club}'")
                    self.club_manager.edit_club_metadata(
                        club, **{CHANNEL_ID_STRING: None}
                    )
            if log:
                log = "\n".join(log)
                await result_printer(ctx, f"```\n{log}```")
            else:
                await ctx.send(
                    "No dangling channels, no action taken. Note that deprecated channels will not be cleaned by this."
                )

        async def sync_perms():
            roomified_clubs = [
                (club, metadata)
                for club, metadata in self.club_manager.get_all_clubs().items()
                if metadata[CHANNEL_ID_STRING]
            ]
            club_json = dataIOa.load_json(CLUB_JSON)
            log = []
            if CLUB_JSON_CATEGORY in club_json and CLUB_JSON_ACCESS_ROLE in club_json:
                for club, metadata in roomified_clubs:
                    channel = ctx.guild.get_channel(int(metadata[CHANNEL_ID_STRING]))

                    if channel.category_id != int(club_json[CLUB_JSON_CATEGORY]):
                        log.append(
                            f"[WARN] {club} channel {channel.id} isn't in the right category"
                        )
                        continue

                    await self.channel_init_helper(
                        ctx.guild,
                        club.lower(),
                        channel,
                        club_json[CLUB_JSON_CATEGORY],
                        club_json[CLUB_JSON_ACCESS_ROLE],
                    )
                    log.append(f"[SYNC] Synchronized '{club}' permissions")
            else:
                await ctx.send("Malformed club JSON. Are rooms properly set up?")

            if log:
                log = "\n".join(log)
                await result_printer(ctx, f"```\n{log}```")
            else:
                await ctx.send(
                    "No dangling channels, no action taken. Note that deprecated channels will not be cleaned by this."
                )

        options_map = {
            "clean_users": clean_users,
            "clean_roles": clean_roles,
            "clean_channels": clean_channels,
            "sync_perms": sync_perms,
        }

        if option in options_map:
            await options_map[option]()
        else:
            await ctx.send(
                f"Invalid option. Options are: {', '.join([f'`{opt}`' for opt in options_map.keys()])}"
            )

    @clubutils.group()
    async def softdelete(self, ctx):
        """Functionality related to soft delete management."""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    def get_soft_deleted_clubs(self):
        clubs = self.club_manager.get_all_clubs(check_deleted=True)
        return [c for c, md in clubs.items() if md[SOFT_DELETED_STRING]]

    @softdelete.command(name="list")
    @commands.check(ban_members_check)
    async def softdelete_list(self, ctx):
        """List soft deleted clubs."""
        clubs = self.get_soft_deleted_clubs()
        if clubs:
            output = "\n".join(clubs)
            await result_printer(ctx, f"Clubs pending deletion:\n```\n{output}```")
        else:
            await ctx.send("No clubs pending deletion.")

    @softdelete.command(name="prune")
    @commands.check(ban_members_check)
    async def softdelete_prune(self, ctx):
        """Prune soft-deleted clubs."""
        clubs = self.get_soft_deleted_clubs()
        for club in clubs:
            club = club.lower()
            self.club_manager.prune_club(club)
        await ctx.send(f"Successfully pruned `{len(clubs)}` clubs.")

    @softdelete.command(name="restore")
    @commands.check(ban_members_check)
    async def softdelete_restore(self, ctx, club):
        """Restores a soft-deleted club."""
        clubs = self.get_soft_deleted_clubs()
        club = club.lower()
        if club in clubs:
            self.club_manager.restore_club(club)
            await ctx.send(f"Successfully restored `{club}`.")
        else:
            await ctx.send(f"`{club}` isn't in the soft-delete list.")

    @clubutils.command(aliases=["create"])
    @commands.check(ban_members_check)
    async def modcreate(self, ctx, club, *, txt):
        """Create a club. Admins only."""
        await self._create(ctx, club, txt)

    # @clubutils.command(aliases=["roomify"])
    # @commands.check(ban_members_check)
    # async def modroomify(self, ctx, club):
    #     """Roomify a club. Admins only."""
    #     await self._roomify(ctx, club)

    @clubutils.command()
    async def choose(self, ctx, club, choices: int = 1):
        """Choose `k` members from a club. Ie. `[p]clubutils choose pcmasterrace 2`"""
        club = club.lower()
        users = self.club_manager.get_club_users(club)
        if users:
            try:
                users = [
                    ctx.guild.get_member(int(u))
                    for u in users
                    if ctx.guild.get_member(int(u))
                ]
                sampled_users_str = "\n".join(
                    [str(u) for u in random.sample(list(users), choices)]
                )
                await ctx.send(f"Your choice(s) are:```{sampled_users_str}```")
            except ValueError:
                await ctx.send(
                    f"You can't choose `{choices}` people from a club has `{len(users)}` active member(s)."
                )
        else:
            await self.closest_club(ctx, club)

    # @clubutils.command()
    # @commands.check(ban_members_check)
    # async def set_room_category(self, ctx, category_id: int):
    #     """Set the room category. Takes a category ID."""
    #     club_json = dataIOa.load_json(CLUB_JSON)
    #     club_json[CLUB_JSON_CATEGORY] = category_id
    #     dataIOa.save_json(CLUB_JSON, club_json)
    #     await ctx.send("Successfully set cateogry.")

    # @clubutils.command()
    # @commands.check(ban_members_check)
    # async def set_category_access_role(self, ctx, role_id: int):
    #     """Set the role given to users to gain access to all public access channels in the category. Takes a role ID."""
    #     club_json = dataIOa.load_json(CLUB_JSON)
    #     club_json[CLUB_JSON_ACCESS_ROLE] = role_id
    #     dataIOa.save_json(CLUB_JSON, club_json)
    #     await ctx.send("Successfully set category access role.")

    @clubutils.command()
    @commands.check(ban_members_check)
    async def set_ping_restriction(self, ctx, channel: discord.TextChannel, club: str):
        """Restrict a channel to only allow a certain club's pings."""
        club = club.lower()
        if self.club_manager.club_exists(club):
            club_json = dataIOa.load_json(CLUB_JSON)
            if CLUB_JSON_CHANNEL_PING_OVERRIDES not in club_json:
                club_json[CLUB_JSON_CHANNEL_PING_OVERRIDES] = {}
            club_json[CLUB_JSON_CHANNEL_PING_OVERRIDES][str(channel.id)] = club
            dataIOa.save_json(CLUB_JSON, club_json)
            await ctx.send(
                f"Successfully restricted {channel.mention} to only allow pings for club `{club}`."
            )
        else:
            await self.closest_club(ctx, club)

    @clubutils.command()
    @commands.check(ban_members_check)
    async def remove_ping_restriction(self, ctx, channel: discord.TextChannel):
        """Remove an existing restriction on a channel's club pings."""
        club_json = dataIOa.load_json(CLUB_JSON)
        if CLUB_JSON_CHANNEL_PING_OVERRIDES not in club_json:
            club_json[CLUB_JSON_CHANNEL_PING_OVERRIDES] = {}
        club_json[CLUB_JSON_CHANNEL_PING_OVERRIDES].pop(str(channel.id), None)
        dataIOa.save_json(CLUB_JSON, club_json)
        await ctx.send(
            f"Successfully removed restriction for club pings in {channel.mention}."
        )

    @clubutils.command()
    @commands.check(ban_members_check)
    async def approvals(self, ctx):
        """Show pending approvals."""
        clubs = []
        for club in self.approvals.values():
            clubs.append(club)
        joined = "\n".join(clubs)
        await ctx.send(f"```Clubs waiting to be approved:\n{joined}```")

    @clubutils.command()
    @commands.check(ban_members_check)
    async def debug(self, ctx, club: str = ""):
        """Dump all clubs and users."""

        def prettify(raw):
            if type(raw) != dict:
                return raw
            pretty = {}
            for key in raw:
                pretty[STRING_MAP.get(key, key)] = prettify(raw[key])
            return pretty

        if club:
            await result_printer(
                ctx,
                f"```{club}\n{pformat(prettify(self.club_manager.get_club_metadata(club.lower(), check_deleted=True)))}```",
            )
        else:
            await result_printer(
                ctx,
                f"```---- clubs ----\n{prettify(self.club_manager.get_all_clubs())}\n\n---- users ----\n{prettify(self.club_manager.get_all_users())}```",
            )

    # @commands.max_concurrency(4)
    # @clubutils.command()
    # async def graph(self, ctx, chosen_club: str):
    #     """[EXPERIMENTAL] View a relational graph of clubs. Ie. `[p]clubutils graph fancomics`"""
    #     chosen_club = chosen_club.lower()
    #     if not self.club_manager.club_exists(chosen_club):
    #         return await self.closest_club(ctx, chosen_club)

    #     filename = "tmp/graph.png"

    #     def task():
    #         # Tuning settings
    #         RAW_THRESHOLD = 2  # The relation threshold between two nodes
    #         WEIGHT_BIAS = (
    #             1 / 5
    #         )  # This controls the inverse graph; the smaller the number, the more biased toward closer clubs
    #         FIG_SIZE = 16  # Size of the plot
    #         FUZ = lambda a: a  # Fuz the final numbers. For now, nothing
    #         DIST_BETWEEN_CHOSEN_AND_CLOSEST = 0.005
    #         LAYOUT_ITERATIONS = 38  # This controls how often the layout is iterated; the higher the closer things will bias

    #         BASE_NODE_FACTOR = 1.4
    #         BASE_NODE_SIZE = 500
    #         BASE_NODE_ALPHA = 0.8

    #         clubs = self.club_manager.get_all_clubs()
    #         graph = nx.Graph()
    #         club_user_sets = {}
    #         for club in clubs:
    #             graph.add_node(club)
    #             members = self.club_manager.get_club_users(club)
    #             club_user_sets[club] = set(members.keys())

    #         processed_clubs = set()

    #         sets = []

    #         for club, userset in club_user_sets.items():
    #             for nested_club, nested_userset in club_user_sets.items():
    #                 if nested_club not in processed_clubs and club != nested_club:
    #                     common_users = len(userset.intersection(nested_userset))
    #                     sets.append([club, nested_club, common_users])
    #             processed_clubs.add(club)

    #         upper_weight = max([u[2] for u in sets])

    #         for club, nested_club, raw_weight in sets:
    #             if raw_weight > RAW_THRESHOLD:
    #                 # We inverse the weight so that we can use Dijkstra's to calculate shortest path
    #                 graph.add_edge(
    #                     club,
    #                     nested_club,
    #                     # Bias the weight as lowest toward the closest then sharply drop off
    #                     weight=1 - (raw_weight / upper_weight) ** WEIGHT_BIAS,
    #                 )

    #         plt.figure(figsize=(FIG_SIZE, FIG_SIZE))

    #         p = dict(nx.single_source_dijkstra_path_length(graph, chosen_club))

    #         max_val = FUZ(max([u for u in p.values()]))
    #         if max_val == 0:
    #             max_val = 1
    #         try:
    #             min_val = (
    #                 FUZ(min([u for u in p.values() if u > 0]))
    #                 + DIST_BETWEEN_CHOSEN_AND_CLOSEST
    #             )
    #         except ValueError:
    #             min_val = 0

    #         # Shift the values down so we don't have large closest deltas
    #         max_val -= min_val
    #         p = {
    #             k: FUZ(v) - min_val if (FUZ(v) - min_val) > 0 else 0
    #             for k, v in p.items()
    #         }

    #         pos = nx.spring_layout(
    #             graph, k=1, scale=2**16, iterations=LAYOUT_ITERATIONS
    #         )
    #         nx.draw_networkx_edges(graph, pos, nodelist=[chosen_club], alpha=0.015)
    #         nx.draw_networkx_nodes(
    #             graph,
    #             pos,
    #             nodelist=list(p.keys()),
    #             node_size=list(
    #                 (
    #                     (math.e ** (BASE_NODE_FACTOR * (1 - (u / max_val))) - 1)
    #                     * BASE_NODE_SIZE
    #                     for u in p.values()
    #                 )
    #             ),
    #             alpha=list((1 - (u / max_val)) * BASE_NODE_ALPHA for u in p.values()),
    #             node_color=list((1 - (u / max_val)) for u in p.values()),
    #             cmap=plt.cm.summer,
    #         )
    #         nx.draw_networkx_labels(
    #             graph,
    #             pos,
    #             font_size=10,
    #         )
    #         plt.savefig(filename, bbox_inches="tight")

    #     await self.bot.loop.run_in_executor(None, task)
    #     with open(filename, "rb") as f:
    #         await ctx.send(content=None, file=discord.File(f))
    #     os.remove(filename)

    @clubutils.command()
    @commands.check(ban_members_check)
    async def rename(self, ctx, club, rename_to):
        """Rename a club. `[p]clubutils rename <club> <rename_to>`"""
        club = club.lower()
        new_club = rename_to.lower()
        new_club_display_name = rename_to
        if self.club_manager.club_exists(club):
            if not self.club_manager.club_exists(new_club):
                success = False
                try:
                    Club.update(ident=new_club).where(Club.ident == club).execute()
                    success = self.club_manager.edit_club_metadata(
                        new_club, **{DISPLAY_NAME_STRING: new_club_display_name}
                    )
                    if not success:
                        Club.update(ident=club).where(Club.ident == new_club).execute()
                except:
                    return await ctx.send("Failed to rename, database issue.")
                if success:
                    return await ctx.send(
                        f"Successfully renamed `{club}` to `{rename_to}`."
                    )
                else:
                    return await ctx.send(
                        f"Failed to rename when trying to update display name of `{club}`."
                    )
            else:
                return await ctx.send(f"Another club is already named `{rename_to}`.")
        else:
            return await ctx.send(f"The specified club, `{club}`, doesn't exist.")


async def setup(
        bot: commands.Bot
):
    clubs = Clubs(bot)
    await bot.add_cog(clubs)
    # await bot.loop.create_task(clubs.time_mute_check())

# def pre_setup(bot):
#     try:
#         # Fallback is to still monkeypatch the check, but only allow users with guild-perms to pass.
#         # This will obviously be a problem if the patching fails, but it's safer for instances where
#         # the club JSON isn't set up yet; we can't guarantee we'll remember users with perms from
#         # club rooms so it's better to be safe than sorry.
#         #
#         # Realistically, this pre-setup assumes that clubs are set up and running for this bot. This
#         # entire cog should be deleted if the bot doesn't intend to use the clubs feature.

#         dataIOa.init_json(CLUB_MODERATION_JSON)
#         dataIOa.init_json(CLUB_JSON)
#         club_json = dataIOa.load_json(CLUB_JSON)
#         if CLUB_JSON_CATEGORY in club_json:

#             async def patched_manage_messages_check(ctx):
#                 return ctx.author.id == ctx.bot.config["OWNER_ID"] or (
#                     isinstance(ctx.author, discord.Member)
#                     and (
#                         ctx.author.guild_permissions.manage_messages
#                         or (
#                             ctx.channel.permissions_for(ctx.author).manage_messages
#                             and ctx.channel.category_id
#                             != int(club_json[CLUB_JSON_CATEGORY])
#                         )
#                     )
#                 )

#         else:

#             async def patched_manage_messages_check(ctx):
#                 return ctx.author.id == ctx.bot.config["OWNER_ID"] or (
#                     isinstance(ctx.author, discord.Member)
#                     and (ctx.author.guild_permissions.manage_messages)
#                 )

#         from utils import checks

#         checks.manage_messages_check = patched_manage_messages_check
#     except Exception as e:
#         print("Failed to monkey-patch checks", e)
