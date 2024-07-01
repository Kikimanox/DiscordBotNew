import json
import discord
from discord import Embed
from discord.ext import commands

import utils.checks as checks
from utils.dataIOa import dataIOa
from typing import Union, Optional

CHANNEL_MUTE_CONFIGS = "data/channel_mute_configs.json"
dataIOa.init_json(CHANNEL_MUTE_CONFIGS)


def get_parent_channel(channel):
    if isinstance(channel, discord.Thread):
        return channel.parent
    return channel

class ChannelMute(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot

    @commands.command(aliases=['cmuter', 'cmuterole'])
    @commands.check(checks.moderator_or_underground_idols_check)
    async def channelmuterole(self, ctx, role: discord.Role, *channels: Union[discord.TextChannel, discord.ForumChannel]):
        """Add a role that will be used to mute users in a channel(s).
        
        `[p]cmuter ROLE_ID CHANNEL_ID`
        `[p]channelmuterole @role #channel1 #channel2`
        """
        if channels is None:
            channels = [get_parent_channel(ctx.message.channel)]
        
        cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
        if "channel_mute_role" not in cmute_cfg.keys():
            cmute_cfg["channel_mute_role"] = {}
        
        kv_pair = cmute_cfg["channel_mute_role"].items()
        cmute_cfg["channel_mute_role"] = {int(k): v for k, v in kv_pair}
        
        success_channels = []
        
        channels = list(set(get_parent_channel(channel) for channel in channels))
        
        for channel in channels:
            if channel.id in cmute_cfg["channel_mute_role"].keys():
                await ctx.send(embed=Embed(description=f"Channel mute role already set for {channel.mention}.", color=0x753b34))
                continue
            cmute_cfg["channel_mute_role"][channel.id] = role.id
            dataIOa.save_json(CHANNEL_MUTE_CONFIGS, cmute_cfg)
            success_channels.append(channel.mention)
        
        if len(success_channels) != 0:
            await ctx.send(embed=Embed(description=f"Channel mute role set to {role.mention} for {', '.join(success_channels)}.", color=0xbbdabb))
    
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command(aliases=['cmutem', 'cmutemsg'])
    @commands.check(checks.moderator_or_underground_idols_check)
    async def channelmutemsg(self, ctx, *, message:str = ""):
        """Set the message that will be sent with the log when a channel mute is initiated."""
            
        cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)            
        cmute_cfg["log_message"] = message
        dataIOa.save_json(CHANNEL_MUTE_CONFIGS, cmute_cfg)
        
        await ctx.send(embed=Embed(description=f"Channel mute message set as: `{message}`.", color=0xbbdabb))

    @commands.command(aliases=['cmutec', 'cmutechannel'])
    @commands.check(checks.moderator_or_underground_idols_check)
    async def channelmutereportchannel(self, ctx, channel: Union[discord.TextChannel, discord.ForumChannel]):
        """Set the channel where channel mute reports will be sent."""
                    
        cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
        cmute_cfg["report_channel"] = channel.id
        dataIOa.save_json(CHANNEL_MUTE_CONFIGS, cmute_cfg)
        
        await ctx.send(embed=Embed(description=f"Channel mute report channel set to {channel.mention}.", color=0xbbdabb))
        
    @commands.command(aliases=['cmuteclear'])
    @commands.check(checks.moderator_or_underground_idols_check)
    async def channelmuteconfigclear(self, ctx, *, channel: discord.TextChannel = None):
        """Clear all channel mute configurations."""
        
        if channel is None:
            dataIOa.save_json(CHANNEL_MUTE_CONFIGS, {})
            await ctx.send(embed=Embed(description=f"Channel mute configurations have been cleared globally.", color=0xbbdabb))
        else:
            channel = get_parent_channel(channel)
            cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
            if "channel_mute_role" not in cmute_cfg.keys() or not cmute_cfg['channel_mute_role'].get(str(channel.id)):
                await ctx.send(embed=Embed(description="No channel mute configurations have been set.", color=0x753b34))
            
            cmute_cfg["channel_mute_role"].pop(str(channel.id))
            dataIOa.save_json(CHANNEL_MUTE_CONFIGS, cmute_cfg)
            
        await ctx.send(embed=Embed(description=f"Channel mute configurations have been cleared.", color=0xbbdabb))

    @commands.command(aliases=['cmuteconfig'])
    @commands.check(checks.moderator_or_underground_idols_check)
    async def channelmuteconfig(self, ctx):
        """Show the channel mute configurations."""
        
        cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
        await ctx.send(content="Channel Mute Settings:\n" + "```json\n" + json.dumps(cmute_cfg, indent=4) + "```")
        
    @commands.command(aliases=['cmute'])
    @commands.check(checks.manage_current_channel_messages_check)
    async def channelmute(
        self,
        ctx: commands.Context,
        user: Union[discord.Member, discord.User],
        channel: Optional[Union[discord.abc.GuildChannel, discord.Thread]] = None,
        *,
        reason: str = "",
    ):
        """Mute a user in a channel until further moderation action is decided.
        
        `[p]channelmute @user #channel reason`
        `[p]cmute USER_ID`
        """

        cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
        channel = get_parent_channel(channel if channel else ctx.message.channel)
        
        
        report_channel = cmute_cfg.get("report_channel")
        if report_channel is None:
            return await ctx.send(embed=Embed(description="No report channel has been configured for the server.", color=0x753b34))
        
        if "channel_mute_role" not in cmute_cfg.keys():
            return await ctx.send(embed=Embed(description="No channel mutes have been configured in the server.", color=0x753b34))
        
        channel_mute_role = cmute_cfg["channel_mute_role"].get(str(channel.id))
        if channel_mute_role is None:
            return await ctx.send(embed=Embed(description=f"No channel mutes have been configured for {channel.mention}", color=0x753b34))  
        
        
        reason = reason if len(reason) > 0 else "No reason provided."
        role = ctx.guild.get_role(channel_mute_role)
        await user.add_roles(role, reason=reason)
        
        log_msg = cmute_cfg.get("log_message")
        
        
        jump_msg = f"[Cmd invoked here]({ctx.message.jump_url}) in {ctx.message.channel.mention}"
        em = Embed(title="CHANNEL MUTE INITIATED", color=0xdf0a26, timestamp=ctx.message.created_at)
        em.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        em.add_field(name="Offender", value=f"`{user.id}` ({user.mention})", inline=True)
        em.add_field(name="Other info", value=jump_msg, inline=True)
        em.add_field(name="Reason", value=f"```{reason}```", inline=False)
        em.set_footer(text=f"channel id: {channel.id}")
        
        new_dict = {}
        for k, v in cmute_cfg["channel_mute_role"].items():
            if new_dict.get(int(v)):
                new_dict[int(v)].append(k)
            else:
                new_dict[int(v)] = [k]
        
        mute_channels = [await ctx.guild.fetch_channel(c_id) for c_id in new_dict[role.id]]
        
        await ctx.send(embed=Embed(description=f"{user.mention} has been muted in {', '.join([c.mention for c in mute_channels])}.", color=0xbbdabb))
        
        log_channel = ctx.guild.get_channel(report_channel)
        # await ctx.send(content=f"Log channel is {log_channel.mention}, log message is {log_msg}.")
        channel_mute_log = await log_channel.send(content=log_msg, embed=em)        
        await channel_mute_log.add_reaction("🧹")

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
            channel_id = int(message.embeds[0].footer.text.split()[-1])
            
            channel_id = get_parent_channel(await guild.fetch_channel(channel_id)).id
            
            cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
            channel_mute_role = cmute_cfg["channel_mute_role"].get(str(channel_id))
            
            user = guild.get_member(user_id)
            role = guild.get_role(channel_mute_role)
            await user.remove_roles(role, reason="Channel mute lifted by moderator.")
            await message.add_reaction("👌")
            


    @commands.command(aliases=['cunmute', 'uncmute'])
    @commands.check(checks.manage_current_channel_messages_check)
    async def channelunmute(
        self, 
        ctx, 
        user: discord.Member, 
        channel: Optional[Union[discord.abc.GuildChannel, discord.Thread]] = None, 
        *, 
        reason: str = ""
    ):
        """Unmute a user channel wide.
        
        `[p]channelunmute @user #channel reason`
        `[p]uncmute USER_ID`
        """
        
        cmute_cfg = dataIOa.load_json(CHANNEL_MUTE_CONFIGS)
        
        channel = get_parent_channel(channel if channel else ctx.message.channel)   
        if "channel_mute_role" not in cmute_cfg.keys():
            return await ctx.send(embed=Embed(description="No channel mutes have been configured in the server.", color=0x753b34))
        
        channel_mute_role = cmute_cfg["channel_mute_role"].get(str(channel.id))
        if channel_mute_role is None:
            return await ctx.send(embed=Embed(description=f"No channel mutes have been configured for the {channel.mention}.", color=0x753b34))         
        
        if len(user.roles) == 0 or cmute_cfg['channel_mute_role'].get(str(channel.id)) not in [role.id for role in user.roles]:
            return await ctx.send(embed=Embed(description=f"{user.mention} is not muted in this channel.", color=0x753b34))
        
        reason = reason if len(reason) > 0 else "No reason provided."
        
        role = ctx.guild.get_role(channel_mute_role)
        
        await user.remove_roles(role, reason=reason)
        await ctx.send(embed=Embed(description=f"{user.mention} has been unmuted in this channel.", color=0xbbdabb))


async def setup(
        bot: commands.Bot
):
    ext = ChannelMute(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
