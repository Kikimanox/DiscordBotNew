import datetime

import discord
from discord import Embed
from discord.ext import commands

import utils.checks as checks


class Personal(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot

    @commands.command(aliases=["ava", "pfp", "profile"])
    async def avatar(self, ctx, user: discord.Member = None):
        """
        Get a user's avatar.

        `[p]avatar` - will display your avatar
        `[p]avatar @user` will display user's avatar
        `[p]avatar 174406433603846145` will display user's avatar by their id
        """
        """Get user avatar. Usage:\n.avatar or \n.avatar @user"""
        if not user: user = ctx.author
        if 'gif' in str(user.display_avatar.url).split('.')[-1]:
            desc = f"[Gif link]({user.display_avatar.url})"
        else:
            desc = f"Links: [png]({user.avatar.replace(format='png').url}) | " \
                   f"[jpg]({user.avatar.replace(format='jpg').url}) | " \
                   f"[webp]({user.avatar.replace(format='webp').url})"
        em = Embed(color=user.color,
                   description=desc,
                   title=f'Avatar for {str(user)}')
        em.set_image(url=user.display_avatar.url)
        await ctx.send(embed=em)

    @commands.command()
    async def whois(self, ctx, member: discord.Member = None):
        """Check a users information.

        `[p]whois` - will check info for yourself
        `[p]whois @user` - will check info for @user (mention)
        `[p]whois Bob` - will check info for bob
        `[p]whos user_id` (Ex: [p]whois 124543645455421)"""

        if not member: member = ctx.author

        embed = Embed(color=member.color, description=member.mention,
                      timestamp=datetime.datetime.utcfromtimestamp(datetime.datetime.utcnow().timestamp()))

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=member.name,
                         icon_url=member.display_avatar.url)
        embed.set_footer(text=f'Id: {member.id}')
        embed.add_field(name="Status", value=member.status, inline=True)
        embed.add_field(name="Joined", value=member.joined_at.strftime('%c'), inline=True)
        smembs = [[m.id, m.joined_at.timestamp()] for m in ctx.guild.members]
        sortedMems = sorted(smembs, key=lambda x: x[1], reverse=False)
        idx = [m[0] for m in sortedMems].index(member.id)
        embed.add_field(name="Join Position", value=str(idx + 1), inline=True)
        embed.add_field(name="Registered on", value=member.created_at.strftime('%c'), inline=True)
        roles = [r for r in member.roles if r.name != '@everyone']
        rolesstr = ' '.join([r.mention for r in roles][::-1]) if len(roles) > 0 else 'None'
        if len(rolesstr) > 1000: rolesstr = "Too many roles to display in the embed."
        embed.add_field(name=f'Roles [{len(roles)}]', inline=False,
                        value=rolesstr)
        gp = member.guild_permissions
        ps = ''
        # if gp.administrator: ps += 'Administrator, '
        if gp.manage_channels: ps += 'Manage Channels, '
        if gp.manage_emojis: ps += 'Manage Emojis, '
        if gp.manage_guild: ps += 'Manage Guild, '
        if gp.manage_messages: ps += 'Manage Messages, '
        if gp.manage_nicknames: ps += 'Manage Nicknames, '
        if gp.manage_roles: ps += 'Manage Roles, '
        if gp.ban_members: ps += 'Ban Members, '
        if gp.kick_members: ps += 'Kick Members, '
        if gp.manage_webhooks: ps += 'Manage Webhooks, '
        if gp.mention_everyone: ps += 'Mention Everyone, '
        if gp.create_instant_invite: ps += 'Create Instant Invites, '
        if gp.view_audit_log: ps += 'View Audit Log, '

        embed.add_field(name=f'Key Permissions', inline=False,
                        value=f'{"None" if not ps else ps[:-2]}')

        ack = ''
        if ctx.guild.id in self.bot.from_serversetup and self.bot.from_serversetup[ctx.guild.id]['modrole']:
            if self.bot.from_serversetup[ctx.guild.id]['modrole'] in [r.id for r in member.roles]:
                ack = 'Moderator'
        if gp.administrator: ack = 'Administrator'
        if member.id == ctx.guild.owner_id: ack = 'Owner'
        if ack:
            embed.add_field(inline=False, name='Acknowledgements', value=ack)
        await ctx.send(embed=embed)

    @commands.command(aliases=["sava", "spfp", "serveravatar", "savatar"])
    async def serverpfp(self, ctx):
        """Get the server icon"""
        if 'gif' in str(ctx.guild.icon_url).split('.')[-1]:
            desc = f"[Gif link]({ctx.guild.icon_url})"
        else:
            desc = f"Links: [png]({ctx.guild.icon_url_as(format='png')}) | " \
                   f"[jpg]({ctx.guild.icon_url_as(format='jpg')}) | " \
                   f"[webp]({ctx.guild.icon_url_as(format='webp')})"
        em = Embed(description=desc,
                   title=f'Avatar for {str(ctx.guild)}')
        em.set_image(
            url=ctx.guild.icon_url if 'gif' in str(ctx.guild.icon_url).split('.')[-1] else ctx.guild.icon_url_as(
                format='png'))
        await ctx.send(embed=em)

    @commands.command()
    async def banner(self, ctx):
        """Display current server's banner."""
        if hasattr(ctx.guild, 'banner_url') and ctx.guild.banner_url:
            em = Embed(color=self.bot.config['BOT_DEFAULT_EMBED_COLOR'])
            em.set_image(url=ctx.guild.banner_url)
            await ctx.send(embed=em)
        else:
            await ctx.send("No banner found.")

    @commands.command()
    async def roles(self, ctx):
        """See how many users are in each hoisted role."""
        roles_dict = {}
        for role in ctx.guild.roles:
            if role.hoist:
                roles_dict[role] = 0
        for member in ctx.guild.members:
            for role in member.roles:
                if role in roles_dict:
                    roles_dict[role] += 1

        sorted_roles = ""
        for role in sorted([[key.name, roles_dict[key]] for key in roles_dict], key=lambda x: x[1], reverse=True):
            sorted_roles += "{} | {}\n".format(*role)

        em = Embed(title="Role ranking", description=sorted_roles, color=0xea7938)
        em.set_thumbnail(url=ctx.guild.icon_url)
        await ctx.send(content=None, embed=em)

    @commands.check(checks.manage_emojis_check)
    @commands.command(aliases=["emojis"])
    async def emotes(self, ctx):
        """Display all emotes on the server"""
        normal = [str(e) for e in ctx.guild.emojis if not e.animated]
        animated = [str(e) for e in ctx.guild.emojis if e.animated]

        li = [[normal, "Non animated emotes", 0x5972ea], [animated, "Animated emotes", 0xf0b562]]
        for l in li:
            txt = ' '.join(l[0])
            desc = []
            if len(txt) > 2000:
                prevTest = 2000
                while len(txt) > 0:
                    test = prevTest
                    if not len(txt) > test - 2:
                        desc.append(txt)
                        break
                    while txt[test - 1] != ' ':
                        test -= 1
                    desc.append(txt[:test])
                    txt = txt[test:]
                    prevTest = test
            else:
                desc.append(txt)
            for i in range(len(desc)):
                if i == 0: await ctx.send(f'**{l[1]}**')
                await ctx.send(embed=Embed(description=desc[i], color=l[2]))


async def setup(
        bot: commands.Bot
):
    ext = Personal(bot)
    await bot.add_cog(ext)
