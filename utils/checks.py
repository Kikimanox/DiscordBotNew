from discord import Member
from discord.ext import commands


async def owner_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID']


async def dev_check(
        ctx: commands.Context
):
    return ctx.author.id in [ctx.bot.config['OWNER_ID'], 124910128582361092]


async def manage_roles_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_roles)


async def manage_messages_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_messages)


async def manage_channels_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_channels)


async def kick_members_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.kick_members)


async def admin_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator)


async def ban_members_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.ban_members)


async def manage_emojis_check(
        ctx: commands.Context
):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_emojis)


async def moderator_or_underground_idols_check(ctx):
    return await moderator_check(ctx) or await moderator_check_custom(ctx, 1099400199920693248)


async def moderator_check(
        ctx: commands.Context
):
    if ctx.author.id == ctx.bot.config['OWNER_ID']:
        return True
    if not ctx.guild:
        return False
    if isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator: return True
    if ctx.bot.from_serversetup:
        if ctx.guild.id in ctx.bot.from_serversetup:
            if 'modrole' in ctx.bot.from_serversetup[ctx.guild.id]:
                mr_id = ctx.bot.from_serversetup[ctx.guild.id]['modrole']
                if mr_id in [r.id for r in ctx.author.roles]:
                    return True
    return False


# Oshi no ko specific ...
async def moderator_check_custom(
        ctx: commands.Context, role_id: int
):
    if ctx.author.id == ctx.bot.config['OWNER_ID']:
        return True
    if not ctx.guild:
        return False
    if isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator: return True
    if ctx.bot.from_serversetup:
        if ctx.guild.id in ctx.bot.from_serversetup:
            if 'modrole' in ctx.bot.from_serversetup[ctx.guild.id]:
                mr_id = role_id
                if mr_id in [r.id for r in ctx.author.roles]:
                    return True
    return False


async def moderator_check_no_ctx(author, guild, bot):
    if author.id == bot.config['OWNER_ID']:
        return True
    if not guild:
        return False
    if isinstance(author, Member) and author.guild_permissions.administrator: return True
    if bot.from_serversetup:
        if guild.id in bot.from_serversetup:
            if 'modrole' in bot.from_serversetup[guild.id]:
                mr_id = bot.from_serversetup[guild.id]['modrole']
                if mr_id in [r.id for r in author.roles]:
                    return True
    return False


async def custom_role_is_booster_check(
        ctx: commands.Context
):
    if str(ctx.guild.id) in ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER']:
        return isinstance(ctx.author, Member) and \
            ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][str(ctx.guild.id)]['BOOSTER_ROLE_ID'] in \
            [r.id for r in ctx.author.roles]
    return False


async def onk_server_check(
        ctx: commands.Context
):
    return ctx.guild.id == 695200821910044783


async def light_server_check(ctx):
    if ctx.guild and ctx.guild.id != 464231424820772866: return False
    return True


async def onk_server_check_admin(
        ctx: commands.Context
):
    # if ctx.guild.id != 695200821910044783: return False
    if ctx.author.id == ctx.bot.config['OWNER_ID']:
        return True
    if isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator:
        return True
    roles = ctx.author.get_role(695297422724694016)
    if roles is not None:
        return True
    return False


async def light_server_check_admin(ctx):
    if ctx.guild and ctx.guild.id != 464231424820772866: return False
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator)
