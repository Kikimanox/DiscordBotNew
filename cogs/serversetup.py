import asyncio
import random
import traceback
import json
import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
from models.serversetup import (Guild, WelcomeMsg, Logging, Webhook, SSManager)


class ServerSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.set_setup())

    async def set_setup(self, gid=None):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
        self.bot.from_serversetup = await SSManager.get_setup_formatted(self.bot, gid)

    @commands.check(checks.admin_check)
    @commands.group(aliases=["sup"])
    async def setup(self, ctx):
        """Use the subcommands to setup server related stuff

        By itself this command doesn't do anything"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.group()
    async def everything(self, ctx,
                         logging_regular_channel: discord.TextChannel,
                         logging_leavejoin_channel: discord.TextChannel,
                         logging_modlog_channel: discord.TextChannel,
                         hook_logging_id: int,
                         hook_logging_target_ch: discord.TextChannel,
                         hook_leavejoin_id: int,
                         hook_leavejoin_target_ch: discord.TextChannel,
                         hook_modlog_id: int,
                         hook_modlog_target_ch: discord.TextChannel,
                         moderator_role: discord.Role,
                         mute_role: discord.Role):
        """Setup (almost) everything at once"""
        await self.do_setup(ctx=ctx, logging_reg=logging_regular_channel, quiet_succ=True)
        await self.do_setup(ctx=ctx, logging_leavejoin=logging_leavejoin_channel, quiet_succ=True)
        await self.do_setup(ctx=ctx, logging_modlog=logging_modlog_channel, quiet_succ=True)
        await self.do_setup(hook_reg=hook_logging_id, hook_reg_target=hook_logging_target_ch, ctx=ctx,
                            quiet_succ=True)
        await self.do_setup(hook_leavejoin=hook_leavejoin_id, hook_leavejoin_target=hook_leavejoin_target_ch, ctx=ctx,
                            quiet_succ=True)
        await self.do_setup(hook_modlog=hook_modlog_id, hook_modlog_target=hook_modlog_target_ch, ctx=ctx,
                            quiet_succ=True)
        await self.do_setup(mod_role=moderator_role, ctx=ctx, quiet_succ=True)
        await self.do_setup(mute_role=mute_role, ctx=ctx, quiet_succ=True)
        await ctx.send("--------------\n"
                       "*The following message always appears.\n"
                       "If you didn't get any errors during the setup it actually worked.\n"
                       "If you got errors ignore the following msg...*")
        await ctx.send("Done!! As for the muted role, it's stored but...\n"
                       "This doesn't mean the channel permissions are setup though.\n"
                       "If they weren't set by hand yet, you can use:\n"
                       f"`{ctx.bot.config['BOT_PREFIX']}setup muterolechperms <role_id>/<role_name>`")

    @commands.check(checks.admin_check)
    @setup.group()
    async def webhooks(self, ctx):
        """Webhook related setups, use subcommands

        By itself this command doesn't do anything

        Setup XYZ webhook by providing it's id and target ch

        **Setup X channel and target_channel should match**

        ***WARNING!!! (NEVER PASTE THE FULL WEBHOOK URL IN CHAT)***
        Do not copy more than the webhook id. DO NOT post the entire url.
        When you copy the webhook url, insert only the id as the parameter.

        Example:
        https://discordapp.com/api/webhooks/123123/Som-E-LoNgmese_a432d#@#1MessyStriNg
        For the command you should only paste 123123.

        ex: `[p]setup webhooks regularlogging 123123 #logs`"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def regularlogging(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Regular logging hook"""
        await self.do_setup(hook_reg=hook_id, hook_reg_target=target_channel, ctx=ctx)

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def leavejoin(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Leave and join logging hook"""
        await self.do_setup(hook_leavejoin=hook_id, hook_leavejoin_target=target_channel, ctx=ctx)

    @commands.check(checks.admin_check)
    @webhooks.command()
    async def modlog(self, ctx, hook_id: int, target_channel: discord.TextChannel):
        """Moderation log logging hook"""
        await self.do_setup(hook_modlog=hook_id, hook_modlog_target=target_channel, ctx=ctx)

    @commands.check(checks.admin_check)
    @setup.group()
    async def logging(self, ctx):
        """Logging channels related setups, use subcommands

        By itself this command doesn't do anything"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @logging.command()
    async def regular(self, ctx, channel: discord.TextChannel):
        """Logging for deleted/edited messages"""
        await self.do_setup(ctx=ctx, logging_reg=channel)

    @commands.check(checks.admin_check)
    @logging.command()
    async def leavejoin(self, ctx, channel: discord.TextChannel):
        """Logging for leave/join messages"""
        await self.do_setup(ctx=ctx, logging_leavejoin=channel)

    @commands.check(checks.admin_check)
    @logging.command()
    async def modlog(self, ctx, channel: discord.TextChannel):
        """Logging for moderation related actions"""
        await self.do_setup(ctx=ctx, logging_modlog=channel)

    @commands.check(checks.admin_check)
    @setup.command()
    async def muterolenew(self, ctx, role: discord.Role):
        """Setup muterole
        Note, this command may be used with any role, but it's main
        purpose/use is to setup the mute role perms on the channels."""
        await self.do_setup(mute_role=role, ctx=ctx)
        await ctx.send("Stored/updated the muted role in the database.\n"
                       "This doesn't mean the channel permissions are setup though.\n"
                       "If they weren't set by hand yet, you can use:\n"
                       f"`{ctx.bot.config['BOT_PREFIX']}setup muterolechperms <role_id>/<role_name>`\n")

    @commands.check(checks.admin_check)
    @setup.command()
    async def modrole(self, ctx, role: discord.Role):
        """Setup moderator specific role"""
        await self.do_setup(mod_role=role, ctx=ctx)

    @commands.check(checks.admin_check)
    @setup.group(aliases=['dlg'])
    async def dontlogchannel(self, ctx):
        """Add or remove channels to not log from"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.check(checks.admin_check)
    @dontlogchannel.command()
    async def add(self, ctx, channel: discord.TextChannel):
        """Add chanenl to be ignore by the bot when logging"""
        await self.do_setup(add_ignore=str(channel.id), ctx=ctx)

    @commands.check(checks.admin_check)
    @dontlogchannel.command()
    async def remove(self, ctx, channel: discord.TextChannel):
        """Remove chanenl from ignored channels when loggin"""
        await self.do_setup(remove_ignore=str(channel.id), ctx=ctx)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @setup.group()
    async def muterolechperms(self, ctx, role: discord.Role):
        """Update channel perms for the mute role"""
        msg = await ctx.send('Applying channel permissions')
        for ch in ctx.guild.text_channels:
            overwrites_muted = ch.overwrites_for(role)
            overwrites_muted.send_messages = False
            overwrites_muted.add_reactions = False
            await ch.set_permissions(role, overwrite=overwrites_muted)
        for ch in ctx.guild.voice_channels:
            overwrites_muted = ch.overwrites_for(role)
            overwrites_muted.speak = False
            overwrites_muted.connect = False
            await ch.set_permissions(role, overwrite=overwrites_muted)
        await msg.edit(content='Done, setup complete')

    @commands.check(checks.admin_check)
    @setup.group(aliases=['wm'])
    async def welcomemsg(self, ctx):
        """Main w.m. setup command, use subcommands"""
        if ctx.invoked_subcommand is None:
            raise commands.errors.BadArgument

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @welcomemsg.command(aliases=['m'])
    async def mainsetup(self, ctx, target_channel: discord.TextChannel):
        """Go trough the entire setup process

        With this command you can setup an image or more images to be randomly picked
        when the user joins the server, what the message content should be, embed title, and embed
        content. Usage examples are shown below:

        The only requiered argument is the welcome channel id, you will be querried for the rest of the data
        during this comamnd's execution. Example below will set the channel with the following id to be the welcome one.

        `[p]setup welcomemsg mainsetup 589190883857924154`"""
        db_guild = SSManager.get_or_create_and_get_guild(ctx.guild.id)
        db_wmsg = SSManager.get_or_create_and_get_welcomemsg(db_guild, target_channel.id, ctx.guild.id)

        # This code is copy pasted from the old bot code, didn't feel like it needed to be changed
        # (even though it's pretty spaghetti code)

        # --- CHECKS START

        def checkYN(m):
            return (m.content.lower() == 'y' or m.content.lower() == 'n') and \
                   m.author == ctx.author and m.channel == ctx.channel

        def checkAuthor(m):
            return m.author == ctx.author and m.channel == ctx.channel

        # --- CHECKS END

        if db_wmsg.images or db_wmsg.content or db_wmsg.desc or db_wmsg.title:
            #  Display old data

            await ctx.send('Welcome data already setup, displaying current data:')
            pics = '\n'.join([f'<{p}>' for p in db_wmsg.images.split()])
            cnt = f"**Channel:** <#{db_wmsg.target_ch}>\n" \
                  f"**Non embed msg:** {db_wmsg.content}\n" \
                  f"**Embed Title:** {db_wmsg.title}\n" \
                  f"**Embed Content** {db_wmsg.desc}\n" \
                  f"**Embed Color** {hex(db_wmsg.color)}\n" \
                  f"**\nWelcome images:**\n" \
                  f"{pics}"
            em = Embed(title=f'Data for {str(ctx.guild)}', color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                       description=cnt)
            await ctx.send(embed=em)
            # Prompt to start over
            pr = await ctx.send('Do you wish to start the setup from the start? (y/n)')
            try:
                reply = await self.bot.wait_for("message", check=checkYN, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send("Cancelled.")
            if not reply or reply.content.lower().strip() == 'n':
                return await ctx.send("Cancelled.")

        # Start prompting
        emm = Embed(description='Starting setup, please reply with the required data, careful becasue '
                                'there are no undos\n(you can start over by sending: `STOP THIS NOW` '
                                'though ... but still, be careful)')
        emm.set_image(url='http://totally-not.a-sketchy.site/7UAZyTZ.png')
        await ctx.send(embed=emm)
        await ctx.send('**▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬**')

        # QUESTION 1
        pr = await ctx.send(
            'What should the message be? (the one outside the embed, send just **$** if nothing)\n'
            'If you want to ping the user who has just joined use [username] in this message. Example:\n'
            '\n[username] welcome to the server!')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            mm = reply.content.strip()
            if mm == '$': mm = ""
            if mm: db_wmsg.content = mm
            await reply.delete()

        # QUESTION 2
        pr = await ctx.send('What should the embed title be? (send **$** if nothing)')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            rp = reply.content.strip()
            if rp == '$': rp = ""
            if rp: db_wmsg.title = rp
            await reply.delete()

        # QUESTION 3
        pr = await ctx.send('What should the embed content be? (send **$** if nothing)')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            rp2 = reply.content.strip()
            if rp2 == '$': rp2 = ""
            if rp2: db_wmsg.desc = rp2
            await reply.delete()

        # QUESTION 4
        pr = await ctx.send('What should the embed color be? (send **$** if you want to keep '
                            'the default bot embed color)\nColor format, one of:\n'
                            '0x1F2E3C | #1F2E3C | 1F2E3C')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            rp3 = reply.content.strip()
            if rp3 == '$':
                color = -100
                await reply.delete()
            else:
                color = -100
                try:
                    if len(rp3) < 6: raise Exception("fail")
                    color = int(rp3[-6:], 16)
                except:
                    await ctx.send("**(*This message* will auto delete in 20 seconds)"
                                   "\nYou failed to input a correct color format, keeping the default bot color.\n"
                                   f"Can still be changed with `{ctx.bot.config['BOT_PREFIX']}setup welcomemsg "
                                   f"color color_here`\n**"
                                   f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
                                   delete_after=20)
                    color = -100

                if color != -100: db_wmsg.color = color
                await reply.delete()

        # QUESTION 5
        pr = await ctx.send('Please provide the image or images that should be used for the welcome message '
                            'picture. (If more are provided then a random one will be chosen once '
                            'a user joins the server)\nSend the images'
                            'in the following format:\n\n- If none: just send **$**'
                            '\n- If just one: Just send the one picture link.\n'
                            '- If multiple: '
                            'link1 link2 link3 link4 link5')
        try:
            reply = await self.bot.wait_for("message", check=checkAuthor, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Setup cancelled.")
        if not reply or reply.content.lower().strip() == 'stop this now':
            return await ctx.send("Setup cancelled.")
        else:
            await pr.delete()
            if reply.content.strip() == '$':
                images = ""
            else:
                images = " ".join(reply.content.replace('\n', ' ').split())
                for i in images.split():
                    if not i.startswith('http'):
                        await ctx.send(
                            "One of the image links doesn't start with `http`...\n"
                            f"Try adding them again with `{ctx.bot.config['BOT_PREFIX']}"
                            f"setup welcomemsg images <pics>`",
                            delete_after=20)
                        images = ""
                        break
            db_wmsg.images = images
            await reply.delete()

        # DONE QUERRYING, DISPLAY FINAL PREVIEW
        await ctx.send('⚠ Setup done, preview below, if all is ok reply with **y** if not with **n** ⚠\n'
                       '**▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬**')

        pics = '\n'.join([f'<{p}>' for p in db_wmsg.images.split()])
        cnt = f"**Channel:** <#{db_wmsg.target_ch}>\n" \
              f"**Non embed msg:** {db_wmsg.content}\n" \
              f"**Embed Title:** {db_wmsg.title}\n" \
              f"**Embed Content** {db_wmsg.desc}\n" \
              f"**Embed Color** {hex(db_wmsg.color)}\n" \
              f"**\nWelcome images:**\n" \
              f"{pics}"
        em = Embed(title=f'Data for {str(ctx.guild)}', color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                   description=cnt)
        await ctx.send(embed=em)

        try:
            reply = await self.bot.wait_for("message", check=checkYN, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send("Cancelled.")
        if not reply or reply.content.lower().strip() == 'n':
            return await ctx.send("Cancelled.")
        else:
            db_wmsg.save()
            await ctx.send('Done, saved.')
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def targetch(self, ctx, target_channel: discord.TextChannel):
        """Fine tune target channel"""
        await SSManager.update_or_error_welcomemsg_target_ch(target_channel.id, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def title(self, ctx, *, title):
        """Fine tune embed title"""
        await SSManager.update_or_error_welcomemsg_title(title, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def desc(self, ctx, *, description):
        """Fine tune embed desscription"""
        await SSManager.update_or_error_welcomemsg_desc(description, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def images(self, ctx, *, images):
        """Fine tune embed image(s) (seperate with a space)"""
        images = " ".join(images.replace('\n', ' ').split())
        for i in images.split():
            if not i.startswith('http'): return await ctx.send("One of the image links doesn't start with `http`...")
        await SSManager.update_or_error_welcomemsg_images(images, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def content(self, ctx, *, cnt):
        """Fine tune message outside of the embed

        [username] will be replaced with new user ping"""
        await SSManager.update_or_error_welcomemsg_content(cnt, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def color(self, ctx, *, color):
        """Fine tune embed color

        Color format, one of:
        0x1F2E3C | #1F2E3C | 1F2E3C"""
        try:
            if len(color) < 6: raise Exception("fail")
            _color = int(color[-6:], 16)
        except:
            return await ctx.send("Invalid color format, please use one of:\n"
                                  "0x1F2E3C | #1F2E3C | 1F2E3C")

        await SSManager.update_or_error_welcomemsg_color(_color, ctx.guild.id, ctx)
        await self.set_setup(ctx.guild.id)

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def current(self, ctx):
        """Display all current information regarding welcome messages"""
        try:
            db_wmsg = WelcomeMsg.get(WelcomeMsg.guild == ctx.guild.id)
        except:
            return await ctx.send("No data setup.")

        if db_wmsg.images or db_wmsg.content or db_wmsg.desc or db_wmsg.title:
            #  Display old data

            await ctx.send('Ddisplaying current data:')
            pics = '\n'.join([f'<{p}>' for p in db_wmsg.images.split()])
            cnt = f"**Channel:** <#{db_wmsg.target_ch}>\n" \
                  f"**Non embed msg:** {db_wmsg.content}\n" \
                  f"**Embed Title:** {db_wmsg.title}\n" \
                  f"**Embed Content** {db_wmsg.desc}\n" \
                  f"**Embed Color** {hex(db_wmsg.color)}\n" \
                  f"**\nWelcome images:**\n" \
                  f"{pics}"
            em = Embed(title=f'Data for {str(ctx.guild)}', color=ctx.bot.config['BOT_DEFAULT_EMBED_COLOR'],
                       description=cnt)
            await ctx.send(embed=em)

        else:
            ctx.send("No data setup.")

    @commands.check(checks.admin_check)
    @welcomemsg.command()
    async def test(self, ctx):
        """Do a test welcome on yourself in this channel"""
        try:
            db_wmsg = WelcomeMsg.get(WelcomeMsg.guild == ctx.guild.id)
        except:
            return await ctx.send("No data setup.")

        if db_wmsg.images or db_wmsg.content or db_wmsg.desc or db_wmsg.title:
            em = Embed(title=db_wmsg.title, description=db_wmsg.desc, color=db_wmsg.color)
            em.set_footer(text=f'Member count: {len(ctx.guild.members)}')
            if db_wmsg.images:
                pic = random.choice(db_wmsg.images.split())
                if pic.startswith('http'):
                    em.set_image(url=pic)
            cnt = db_wmsg.content.replace('[username]', ctx.author.mention)
            await ctx.send(embed=em, content=cnt)

        else:
            ctx.send("No data setup.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if self.bot.from_serversetup and member.guild.id in self.bot.from_serversetup:
            if 'welcomemsg' in self.bot.from_serversetup[member.guild.id]:
                wmsg = self.bot.from_serversetup[member.guild.id]['welcomemsg']
                em = Embed(title=wmsg['title'], description=wmsg['desc'], color=wmsg['color'])
                em.set_footer(text=f'Member count: {len(member.guild.members)}')
                if wmsg.images:
                    pic = random.choice(wmsg['images'].split())
                    if pic.startswith('http'):
                        em.set_image(url=pic)
                cnt = wmsg.content.replace('[username]', member.mention)
                await wmsg['target_ch'].send(embed=em, content=cnt)
                return
        self.bot.logger.error(f"Couldn't welcome {str(member)} {member.id} in {str(member.guild)} {member.guild.id}")

    async def do_setup(self, **kwargs):
        ctx = kwargs.get('ctx', None)
        if not ctx: raise Exception("Missing ctx in do_setup")
        quiet_succ = kwargs.get('quiet_succ', False)
        hook_reg = kwargs.get('hook_reg', None)
        hook_reg_target = kwargs.get('hook_reg_target', None)
        hook_leavejoin = kwargs.get('hook_leavejoin', None)
        hook_leavejoin_target = kwargs.get('hook_leavejoin_target', None)
        hook_modlog = kwargs.get('hook_modlog', None)
        hook_modlog_target = kwargs.get('hook_modlog_target', None)

        logging_reg = kwargs.get('logging_reg', None)
        logging_leavejoin = kwargs.get('logging_leavejoin', None)
        logging_modlog = kwargs.get('logging_modlog', None)

        mute_role = kwargs.get('mute_role', None)
        mod_role = kwargs.get('mod_role', None)
        add_ignore = kwargs.get('add_ignore', None)
        remove_ignore = kwargs.get('remove_ignore', None)

        db_guild = SSManager.get_or_create_and_get_guild(ctx.guild.id)
        try:
            if logging_reg and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                SSManager.create_or_update_logging(db_guild, logging_reg.id, 'reg')
            elif logging_leavejoin and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                SSManager.create_or_update_logging(db_guild, logging_leavejoin.id, 'leavejoin')
            elif logging_modlog and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                SSManager.create_or_update_logging(db_guild, logging_modlog.id, 'modlog')
            elif hook_reg and hook_reg_target and (len(kwargs) == 3 or (len(kwargs) == 4 and quiet_succ)):
                await SSManager.create_or_update_logging_hook(db_guild, hook_reg, hook_reg_target.id, 'reg',
                                                              await ctx.bot.fetch_webhook(hook_reg), ctx)
            elif hook_leavejoin and hook_leavejoin_target and (len(kwargs) == 3 or (len(kwargs) == 4 and quiet_succ)):
                await SSManager.create_or_update_logging_hook(db_guild, hook_leavejoin, hook_leavejoin_target.id,
                                                              'leavejoin', await ctx.bot.fetch_webhook(hook_leavejoin),
                                                              ctx)
            elif hook_modlog and hook_modlog_target and (len(kwargs) == 3 or (len(kwargs) == 4 and quiet_succ)):
                await SSManager.create_or_update_logging_hook(db_guild, hook_modlog, hook_modlog_target.id, 'modlog',
                                                              await ctx.bot.fetch_webhook(hook_modlog), ctx)
            elif mute_role and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                db_guild.muterole = mute_role.id
                db_guild.save()
            elif mod_role and (len(kwargs) == 2 or (len(kwargs) == 3 and quiet_succ)):
                db_guild.modrole = mod_role.id
                db_guild.save()
            elif add_ignore and len(kwargs) == 2:
                if add_ignore not in db_guild.ignored_chs_at_log:
                    arr = db_guild.ignored_chs_at_log.split()
                    arr.append(add_ignore)
                    db_guild.ignored_chs_at_log = " ".join(arr)
                    db_guild.save()
                else:
                    await ctx.send("This channel is already being ignored")
                    raise Exception("_fail")
            elif remove_ignore and len(kwargs) == 2:
                if remove_ignore in db_guild.ignored_chs_at_log:
                    arr = db_guild.ignored_chs_at_log.split()
                    arr.remove(remove_ignore)
                    db_guild.ignored_chs_at_log = " ".join(arr)
                    db_guild.save()
                else:
                    await ctx.send("This channel is not ignored")
                    raise Exception("_fail")

            else:
                await ctx.send(f"You shouldn't have hit this. oi.. <@!{ctx.bot.config['OWNER_ID']}>")
            if not quiet_succ: await ctx.send("Done.")
            await self.set_setup(ctx.guild.id)
            return True
        except Exception as e:
            if str(e) == '_fail': return
            traceback.print_exc()
            info = ""
            if quiet_succ:
                for k, v in kwargs.items(): kwargs[k] = str(v)
                info += f" **Kwargs dump:**\n```{json.dumps(kwargs, indent=4)}```"
            await ctx.send("Something went wrong." + info)
            return False


def setup(bot):
    ext = ServerSetup(bot)
    bot.add_cog(ext)
