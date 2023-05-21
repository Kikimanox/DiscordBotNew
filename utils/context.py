from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Optional, Any, Sequence, Union, TYPE_CHECKING, Callable, List, Tuple

from discord import (
    Message,
    Embed,
    File,
    GuildSticker,
    StickerItem,
    AllowedMentions,
    MessageReference,
    PartialMessage,
    utils,
    User,
    Member,
)
from discord.ext import commands
from discord.ui import View

from utils.views import DynamicButtonView, ConfirmCancelView

if TYPE_CHECKING:
    from bot import KanaIsTheBest

    from discord import (
        TextChannel,
        VoiceChannel,
        DMChannel,
        GroupChannel,
        PartialMessageable,
        Thread,
    )

    PartialMessageableChannel = Union[
        TextChannel, VoiceChannel, Thread, DMChannel, PartialMessageable
    ]
    MessageableChannel = Union[PartialMessageableChannel, GroupChannel]

MISSING: Any = utils.MISSING

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class Context(commands.Context):
    bot: KanaIsTheBest

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def channel_send(
            self,
            channel: Optional[MessageableChannel] = None,
            content: Optional[str] = None,
            *,
            tts: bool = False,
            embed: Optional[Embed] = None,
            file: Optional[File] = None,
            stickers: Optional[Sequence[Union[GuildSticker, StickerItem]]] = None,
            delete_after: Optional[float] = None,
            nonce: Optional[Union[str, int]] = None,
            allowed_mentions: Optional[AllowedMentions] = None,
            reference: Optional[Union[Message, MessageReference, PartialMessage]] = None,
            mention_author: Optional[bool] = None,
            view: Optional[View] = None,
            suppress_embeds: bool = False,
    ):
        """
        Used for the new way to send messages that can be reacted
        :param channel:

        :param content:
            The content of the message to send.
        :param tts:
            Indicates if the message should be sent using text-to-speech.
        :param embed:
            The rich embed for the content.
        :param file:
            The file to upload.
        :param stickers:
        :param delete_after:
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.
        :param nonce:
            The nonce to use for sending this message. If the message was successfully 
            sent, then the message will have a nonce with this value.
        :param allowed_mentions:
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with 
            :attr:`~discord.Client.allowed_mentions`.
            The merging behaviour only overrides attributes that have been explicitly 
            passed to the object, otherwise it uses the attributes set in 
            :attr:`~discord.Client.allowed_mentions`. If no object is passed at all then 
            the defaults given by :attr:`~discord.Client.allowed_mentions`
            are used instead.
        :param reference:
            A reference to the :class:`~discord.Message` to which you are replying, 
            this can be created using
            :meth:`~discord.Message.to_reference` or passed directly as a 
            :class:`~discord.Message`. You can control
            whether this mentions the author of the referenced message using the
            :attr:`~discord.AllowedMentions.replied_user`
            attribute of ``allowed_mentions`` or by setting ``mention_author``.
        :param mention_author:
            If set, overrides the :attr:`~discord.AllowedMentions.replied_user` 
            attribute of ``allowed_mentions``.
            This is ignored for interaction based contexts.
        :param view:
            A Discord UI View to add to the message.
        :param suppress_embeds:
        Whether to suppress embeds for the message. This sends the message without any 
        embeds if set to ``True``.


        :return:  The message that was sent.
        """
        if channel is None:
            channel = self.channel
        message = await channel.send(
            content,
            tts=tts,
            embed=embed,
            file=file,
            stickers=stickers,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference,
            mention_author=mention_author,
            view=view,
            suppress_embeds=suppress_embeds,
        )
        await self.save_info_to_react_delete(message)
        return message

    async def send(
            self,
            content: Optional[str] = None,
            *,
            tts: bool = False,
            embed: Optional[Embed] = None,
            embeds: Optional[Sequence[Embed]] = None,
            file: Optional[File] = None,
            files: Optional[Sequence[File]] = None,
            stickers: Optional[Sequence[Union[GuildSticker, StickerItem]]] = None,
            delete_after: Optional[float] = None,
            nonce: Optional[Union[str, int]] = None,
            allowed_mentions: Optional[AllowedMentions] = None,
            reference: Optional[Union[Message, MessageReference, PartialMessage]] = None,
            mention_author: Optional[bool] = None,
            view: Optional[View] = None,
            suppress_embeds: bool = False,
            ephemeral: bool = False,
    ) -> Message:
        """
        Intercepts the original context send command to get the Message ID and the author ID, afterwards save it to
        be able to access later. This enables to be deleted via reacting :x: by the user.
        """
        message = await super().send(
            content,
            tts=tts,
            embed=embed,
            embeds=embeds,
            file=file,
            files=files,
            stickers=stickers,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference,
            mention_author=mention_author,
            view=view,
            suppress_embeds=suppress_embeds,
            ephemeral=ephemeral,
        )
        await self.save_info_to_react_delete(message)
        return message

    async def save_info_to_react_delete(self, message):
        author_id = self.author.id
        message_id = message.id
        new_value = {message_id: author_id}
        self.bot.react_delete.update(new_value)

    async def wait_for_message(
            self,
            custom_check: Optional[Callable[..., bool]] = None,
            check_same_user: bool = False,
            check_same_channel: bool = True,
            check_same_guild: bool = True,
            check_if_message_starts_with: Optional[str] = None,
            sent_timeout_message: bool = False,
            timeout: Optional[int] = None,
    ) -> Optional[Message]:
        """
        wait for the return message

        :param custom_check: add custom check
        :param check_same_user:
        :param check_same_channel:
        :param check_same_guild:
        :param check_if_message_starts_with:
        :param sent_timeout_message: if it will send a timeout message
        :param timeout: Float, time to wait
        :return:
        """

        def check(message: Message) -> bool:
            if check_same_guild and message.guild != self.guild:
                return False
            if check_same_channel and message.channel != self.channel:
                return False
            if check_same_user and message.author != self.author:
                return False
            if (
                    check_if_message_starts_with is not None
                    and not message.content.startswith(check_if_message_starts_with)
            ):
                return False
            return True

        try:
            check_function = check if custom_check is None else custom_check
            result = await self.bot.wait_for(
                "message", timeout=timeout, check=check_function
            )
            return result
        except asyncio.TimeoutError:
            if sent_timeout_message:
                await self.channel.send("Timeout", delete_after=30)
            return None
        except Exception as ex:
            error_message = "".join(
                traceback.format_exception(None, ex, ex.__traceback__)
            )
            error_logger.error(error_message)
            return None

    async def prompt(
            self,
            channel: Optional[MessageableChannel] = None,
            content: Optional[str] = None,
            embed: Optional[Embed] = None,
            file: Optional[File] = None,
            timeout: Optional[float] = None,
    ) -> Optional[bool]:
        view = ConfirmCancelView(author=self.author, timeout=timeout)
        if channel is not None:
            result = await channel.send(
                content=content, view=view, embed=embed, file=file
            )
        else:
            result = await self.send(content=content, view=view, embed=embed, file=file)
        await view.wait()
        await result.delete()

        return view.value

    async def prompt_with_author_response(
            self,
            channel: Optional[MessageableChannel] = None,
            content: Optional[str] = None,
            embed: Optional[Embed] = None,
            file: Optional[File] = None,
            timeout: Optional[float] = None,
    ) -> Tuple[Optional[bool], Optional[Union[User, Member]]]:
        view = ConfirmCancelView(author=self.author, timeout=timeout)
        if channel is not None:
            result = await channel.send(
                content=content, view=view, embed=embed, file=file
            )
        else:
            result = await self.send(content=content, view=view, embed=embed, file=file)
        await view.wait()
        await result.delete()

        return view.value, view.author

    async def choose_value_with_button(
            self,
            entries: List[Union[str, float, int]],
            content: Optional[str] = None,
            embed: Optional[Embed] = None,
            file: Optional[File] = None,
            timeout: Optional[float] = None,
    ) -> Optional[Union[str, float, int]]:
        view = DynamicButtonView(author=self.author, entries=entries, timeout=timeout)
        result = await self.send(content=content, view=view, embed=embed, file=file)
        await view.wait()
        await result.delete()
        return view.value
