from discord import Member


async def owner_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID']


async def manage_roles_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_roles)


async def manage_messages_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_messages)


async def manage_channels_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_channels)


async def kick_members_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.kick_members)


async def admin_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator)


async def ban_members_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.ban_members)


async def manage_emojis_check(ctx):
    return ctx.author.id == ctx.bot.config['OWNER_ID'] or (
            isinstance(ctx.author, Member) and ctx.author.guild_permissions.manage_emojis)


async def moderator_check(ctx):
    if ctx.author.id == ctx.bot.config['OWNER_ID']: return True
    if not ctx.guild: return False
    if isinstance(ctx.author, Member) and ctx.author.guild_permissions.administrator: return True
    if ctx.bot.from_serversetup:
        if ctx.guild.id in ctx.bot.from_serversetup:
            if 'modrole' in ctx.bot.from_serversetup[ctx.guild.id]:
                mr_id = ctx.bot.from_serversetup[ctx.guild.id]['modrole']
                if mr_id in [r.id for r in ctx.author.roles]:
                    return True
    return False


async def moderator_check_no_ctx(author, guild, bot):
    if author.id == bot.config['OWNER_ID']: return True
    if not guild: return False
    if isinstance(author, Member) and author.guild_permissions.administrator: return True
    if bot.from_serversetup:
        if guild.id in bot.from_serversetup:
            if 'modrole' in bot.from_serversetup[guild.id]:
                mr_id = bot.from_serversetup[guild.id]['modrole']
                if mr_id in [r.id for r in author.roles]:
                    return True
    return False


async def custom_role_is_booster_check(ctx):
    if str(ctx.guild.id) in ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER']:
        return isinstance(ctx.author, Member) and \
               ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][str(ctx.guild.id)]['BOOSTER_ROLE_ID'] in \
               [r.id for r in ctx.author.roles]
    return False


async def light_server_check(ctx):
    if ctx.guild.id != 464231424820772866: return False
    return True
