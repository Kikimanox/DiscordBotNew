from dataclasses import dataclass
from typing import Optional
from discord import Message, Reaction, Member
from discord.ext import commands


@dataclass
class CommandOwner:
    message: Message

    guild_id: Optional[int] = 0
    channel_id: Optional[int] = 0
    message_id: Optional[int] = 0
    author_id: Optional[int] = 0

    def __post_init__(self):
        self.guild_id = self.message.guild.id
        self.channel_id = self.message.channel.id
        self.message_id = self.message.id

    def check_if_delete(
            self,
            member: Member,
            bot: commands.Bot,
            reaction: Reaction
    ) -> bool:
        if reaction.message.author.id == bot.user.id:
            message_id = reaction.message.id
            guild_id = reaction.message.guild.id
            channel_id = reaction.message.channel.id
            author_id = member.id

            if self.message_id == message_id and \
                    self.guild_id == guild_id and \
                    self.channel_id == channel_id and \
                    self.author_id == author_id:
                return True
            else:
                return False
        else:
            return False
