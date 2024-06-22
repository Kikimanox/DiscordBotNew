from discord.ext import commands
import discord
import utils.checks as checks
from discord import Embed

class ChannelMute(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot

    @commands.command(aliases=["cmute"])
    @commands.check(checks.manage_current_channel_messages_check)
    async def channelmute(self, ctx, user: discord.Member, *, reason: str = ""):
        """Mute a user channel wide until further moderation action is decided.
        
        `[p]channelmute @user`
        `[p]cmute USER_ID`
        """

        reports_channel = 1252247493811634217
        
        await ctx.message.channel.set_permissions(user, send_messages=False, add_reactions=False, reason=reason)
        
        reason = reason if len(reason) > 0 else "No reason provided."
        
        jump_msg = f"[Cmd invoked here]({ctx.message.jump_url}) in {ctx.message.channel.mention}"
        em = Embed(title="CHANNEL MUTE INITIATED", color=0xdf0a26, timestamp=ctx.message.created_at)
        em.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        em.add_field(name="Offender", value=f"`{user.id}` ({user.mention})", inline=True)
        em.add_field(name="Other info", value=jump_msg, inline=True)
        em.add_field(name="Reason", value=f"```{reason}```", inline=False)
        
        channel_mute_log = await self.bot.get_channel(reports_channel).send(embed=em)
        await channel_mute_log.add_reaction("🧹")
        await ctx.send(embed=Embed(description=f"{user.mention} has been muted in this channel.", color=0xbbdabb))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event: discord.RawReactionActionEvent) -> None:
        await self.bot.wait_until_ready()
        if not event.guild_id or event.user_id == self.bot.user.id:
            return
    
        guild = self.bot.get_guild(event.guild_id)
        channel = await guild.fetch_channel(event.channel_id)
    
        if event.emoji.name in ["🧹"]:
            if not channel.permissions_for(
                    channel.guild.get_member(event.user_id)
            ).manage_messages:
                return
            message = await channel.fetch_message(event.message_id)
            if (
                        not message.embeds
                        or not message.embeds[0].title
                        or not message.embeds[0].title.lower().startswith("channel mute")
                ):
                    return
            
            user_id = int(message.embeds[0].fields[1].value.split()[0][1:-1])
            channel_id = int(message.embeds[0].fields[2].value.split()[-1][2:-1])
            
            cmute_channel = self.bot.get_channel(channel_id)
            await cmute_channel.set_permissions(guild.get_member(user_id), overwrite=None)


    @commands.command(aliases=["cunmute", "uncmute"])
    @commands.check(checks.manage_current_channel_messages_check)
    async def channelunmute(self, ctx, user: discord.Member, *, reason: str = ""):
        """Unmute a user channel wide.
        
        `[p]channelunmute @user`
        `[p]uncmute USER_ID`
        """
        await ctx.message.channel.set_permissions(user, overwrite=None, reason=reason)
        await ctx.send(embed=Embed(description=f"{user.mention} has been unmuted in this channel.", color=0xbbdabb))


async def setup(
        bot: commands.Bot
):
    ext = ChannelMute(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
