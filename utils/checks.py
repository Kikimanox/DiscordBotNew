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
