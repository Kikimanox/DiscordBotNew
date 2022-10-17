import asyncio
import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
from models.reactionroles import ReactionRolesModel, RRManager

TEST_EMOTES_MSG_PENDING = "Testing emotes for the reactions. Status: Pending ❔"
TEST_EMOTES_MSG_PASSED = "Testing emotes for the reactions. Status: Passed ✅"
TEST_EMOTES_MSG_FAILED = "Testing emotes for the reactions. Status: Failed ❌"


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @commands.group(invoke_without_command=True, aliases=["rr"])
    async def reactionrole(self, ctx, channel: discord.TextChannel, msgID: int):
        """Just init reaction roles, for everything else use subcommands.

        This command will initialize the channel and message id into
        the save file so it can be tampered with later. Example:

        `[p]rr #info 3243253453`
        `[p]rr info 3243253453`
        `[p]rr 234532534 3243253453`"""
        ch = channel
        try:
            msg = await ch.fetch_message(msgID)
        except:
            return await ctx.send(f"❌ No message with that id found in the channel {ch.mention}")

        reactionData = ReactionRolesModel.get_or_none(msgid=msgID)
        if reactionData:
            return await ctx.send("❌ This message has already been initialized")

        ReactionRolesModel.insert(gid=ctx.guild.id, chid=channel.id, msgid=msgID, msg_link=msg.jump_url).execute()

        RRManager.add_or_update_rrs_bot(ctx.bot, ctx.guild.id, channel.id, msgID, msg.jump_url, [])
        await ctx.send(f"✅ Message with the id {msg.id} and in the "
                       f"channel {ch.mention} has been added to the save.")

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @reactionrole.command(aliases=['cur'])
    async def current(self, ctx, msg_id: int = 0):
        """Display current info, can check all or just one (by msg id)"""
        if msg_id == 0:
            confirm = await dutils.prompt(ctx, "Are you sure you want to check **all** the rrs?")
            if not confirm:
                return await ctx.send("Cancelled.")
        if msg_id != 0:
            r: ReactionRolesModel = ReactionRolesModel.get_or_none(msgid=msg_id)
            if not r:
                return await ctx.send("This message doesn't have any rrs initialized on it.")
            grrs = {r.chid: {r.msgid: [r.meta.split(' '), r.msg_link]}}
        else:
            b = ctx.bot.reaction_roles
            if ctx.guild.id in b:
                r2: ReactionRolesModel = ReactionRolesModel.get_or_none(gid=ctx.guild.id)
                if not r2:
                    return await ctx.send("No rrs initialized")
                grrs = ctx.bot.reaction_roles[ctx.guild.id]
            else:
                return await ctx.send("No rrs initialized")

        embeds = []
        if msg_id == 0:
            mm = await ctx.send("Preparing rr current...")
        for kk, vv in grrs.items():  # ch_id, [[
            for k, v in vv.items():  # msg_id, [{ch, rrs}, jump]
                chan = ctx.guild.get_channel(kk)
                titlee = f'**{k}**'
                jumpMsg = ''
                try:
                    msg = await chan.fetch_message(int(k))  # check if it still exists
                    if not msg: raise Exception('aaa')
                    clr = 0xea7938
                    jumpMsg = msg.jump_url
                except:
                    titlee += ' (deleted message)'
                    clr = 0x9a1217
                desc = f"**Channel:** {chan.mention if chan else f'No ch found ({kk})'}\n**Reaction roles:**\n"
                if len(v[0]) > 1:
                    ar = []
                    for i in range(0, len(v[0]), 2):
                        ar.append(f'{v[0][i]} <@&{v[0][i + 1]}>')
                    desc += "\n".join(ar)
                else:
                    desc += "\n⚠ No reactions added to this msg.\nTry adding them with:\n" \
                            f"`{dutils.bot_pfx_by_ctx(ctx)}rr add`\n"
                desc += '' if not jumpMsg else f"\n[Jump to message]({jumpMsg})"
                E = Embed(description=desc, color=clr, title=titlee)
                if clr == 0x9a1217:
                    E.set_footer(text=f'{dutils.bot_pfx_by_ctx(ctx)}rr remove {k}')
                embeds.append(E)
        for e in embeds: await ctx.channel.send(embed=e)
        if msg_id == 0:
            await mm.delete()

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @reactionrole.command()
    async def add(self, ctx, msgID: int, *, emotesAndReactions):
        """Add new reactions to an existing reaction message

        Format for adding the emotes and binding them to roles is as follows:

        `[p]rr add msg_id EMOTE ROLE_ID`
        (you can also use ROLE_NAME instead of ROLE_ID
        but be careful of duplicate roles!!! (id safer))
        Or for multiple at once you can do for example:
        `[p]rr add msg_id
        EMOTE ROLE_ID
        EMOTE2 ROLE_ID2
        EMOTE3 ROLE_ID3`
        Or also like this, but the one above is more intuitive
        `[p]rr add msg_id EMOTE ROLE_ID EMOTE2 ROLE_ID2`"""
        await self.do_rr_stuff(ctx, msgID, emotesAndReactions)

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.admin_check)
    @reactionrole.command()
    async def refresh(self, ctx, msgID: int, *, emotesAndReactions):
        """Change which roles are tracked (use `[p]help rr refresh` please)

        This command is a hack/workaround when this use case:
        **I wantto change up some stuff in the `rr current msgID`
        output. I only want to change the roles**
        (THE EMOTES HAVE TO BE THE SAME!!!!)

        Just do: `rr current msgID` and copy the entire thing,
        keep the emotes as they are, and replace the role ids
        where needed.
        """
        confirm = await dutils.prompt(ctx, "Are you sure that you want to do this? Did you read the "
                                           "help output for this command? Do you know what you're doing?")
        if not confirm:
            return await ctx.send("Cancelled.")
        await self.do_rr_stuff(ctx, msgID, emotesAndReactions, True)

    @commands.check(checks.admin_check)
    @reactionrole.command()
    async def remove(self, ctx, msgID: int):
        """Remove message id and tracking from save

        `[p]rr remove MSG_ID`"""
        confirm = await dutils.prompt(ctx, "https://tenor.com/view/are-you-sure"
                                           "-john-cena-ru-sure-about-dat-gif-14258954")
        if not confirm:
            return await ctx.send("Cancelled.")

        r: ReactionRolesModel = ReactionRolesModel.get_or_none(msgid=msgID)
        if not r:
            return await ctx.send("This message doesn't have any rrs initialized on it.")
        try:
            g = r.gid
            c = r.chid
            # r.delete_instance() actually I already do this in the method below.. heh
            RRManager.remove_from_rrs(ctx.bot, g, c, msgID)
            return await ctx.send(f"Removed, the message with the id `{msgID}` will no longer be tracked.")
        except:
            await ctx.send('Failed to remove, something went wrong')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        await self.reactionAndRole(event, True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        await self.reactionAndRole(event, False)

    async def reactionAndRole(self, event, addIt=True):
        try:
            rrs = self.bot.reaction_roles[event.guild_id][event.channel_id][event.message_id][0]
        except:
            return
        try:
            emote = str(event.emoji)
            guild = self.bot.get_guild(int(event.guild_id))
            user = guild.get_member(event.user_id)
            rrs = rrs[::-1]
            for i in range(1, len(rrs), 2):
                if rrs[i].replace('<a:', '<:') == emote.replace('<a:', '<:'):
                    role = discord.utils.get(guild.roles, id=int(rrs[i - 1]))
                    if addIt:
                        for retry in range(10):
                            if role not in user.roles:
                                await user.add_roles(role)
                            else:
                                break
                            await asyncio.sleep(0.5)

                        return  # don't add multiple
                    else:
                        for retry in range(10):
                            if role in user.roles:
                                await user.remove_roles(role)
                            else:
                                break
                            await asyncio.sleep(0.5)

                        return  # don't remove multiple
        except:
            pass

    async def do_rr_stuff(self, ctx, msgID, emotesAndReactions, refreshing=False):
        if ctx.guild.id not in ctx.bot.reaction_roles:
            return await ctx.send("No rrs initialized")

        r: ReactionRolesModel = ReactionRolesModel.get_or_none(msgid=msgID)
        if not r:
            return await ctx.send("This message doesn't have any rrs initialized on it.")

        old_meta = r.meta.split(' ')
        if r.meta == '' or refreshing:
            old_meta = []

        try:
            emotesAndReactions = emotesAndReactions.replace('\n', ' ')
            emotesAndReactions = ' '.join(emotesAndReactions.split())
            emotesAndReactions = emotesAndReactions.strip()
            if len(emotesAndReactions.split(' ')) % 2 != 0:
                raise Exception("You didn't use a even number of emotes:roles")
            ems = emotesAndReactions.split(' ')

            testMsg = await ctx.send(TEST_EMOTES_MSG_PENDING)
            for i in range(0, len(ems), 2):
                testRole = await dutils.try_if_role_exists(ctx.guild, ems[i + 1])
                if not testRole[0]:
                    try:
                        await testMsg.edit(content=TEST_EMOTES_MSG_FAILED)
                    except:
                        pass
                    return await ctx.send(f"Role with the id or name: `{testRole[1]}` doesn't exist")
                testEmote = await dutils.try_to_react(testMsg, [ems[i]])
                if not testEmote[0]:
                    try:
                        await testMsg.edit(content=TEST_EMOTES_MSG_FAILED)
                    except:
                        pass
                    return await ctx.send(f"I can not use the emote `{testEmote[1]}`")

                if testRole[2].id:
                    ems[i + 1] = testRole[2].id
                else:
                    return await ctx.send("Something went wrong...")

                # old_meta.append(f'{ems[i]} {ems[i + 1]}')
                old_meta.append(f'{ems[i]}')
                old_meta.append(f'{ems[i + 1]}')
                if len(old_meta) > 40:
                    return await ctx.send("Maximum reactionsI can save for one message is 20!")
            try:
                await testMsg.edit(content=TEST_EMOTES_MSG_PASSED)
            except:
                pass

            await ctx.send("Adding reactions to the specified message.")
            try:
                chan = ctx.guild.get_channel(r.chid)
                if not chan:
                    return await ctx.send(f"This ({r.chid}) channel doesn't eixst anymore...")
                msg = await chan.fetch_message(msgID)
                for i in range(0, len(ems), 2):
                    await msg.add_reaction(ems[i])
                await ctx.send(f"Done, you can check the message status here: {msg.jump_url}")
            except:
                traceback.print_exc()
                return await ctx.send("Something went wrong...")

            r.meta = ' '.join(old_meta)
            r.save()
            RRManager.add_or_update_rrs_bot(ctx.bot, ctx.guild.id, chan.id, msgID, msg.jump_url, old_meta)
        except Exception as e:
            return await ctx.send("Something went wrong. Please check `.help rr add` if needed.\n"
                                  f"Extra info: `{str(e)}`")


async def setup(
        bot: commands.Bot
):
    ext = ReactionRoles(bot)
    await bot.add_cog(ext)
