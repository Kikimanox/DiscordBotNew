"""
Paginator class, credit goes to: appu1232
"""

import discord
import asyncio


async def pager(entries, chunk: int):
    for x in range(0, len(entries), chunk):
        yield entries[x:x + chunk]


class SimplePaginator:
    __slots__ = ('entries', 'extras', 'title', 'description', 'colour', 'footer', 'length', 'prepend', 'append',
                 'fmt', 'timeout', 'ordered', 'controls', 'controller', 'pages', 'current', 'previous', 'eof', 'base',
                 'names', 'other_target')

    def __init__(self, **kwargs):
        self.entries = kwargs.get('entries', None)
        self.extras = kwargs.get('extras', None)

        self.title = kwargs.get('title', None)
        self.description = kwargs.get('description', None)
        self.colour = kwargs.get('colour', 0xffd4d4)
        self.footer = kwargs.get('footer', None)

        self.length = kwargs.get('length', 10)
        self.prepend = kwargs.get('prepend', '')
        self.append = kwargs.get('append', '')
        self.fmt = kwargs.get('fmt', '')
        self.timeout = kwargs.get('timeout', 90)
        self.ordered = kwargs.get('ordered', False)

        self.other_target = kwargs.get('other_target', None)

        self.controller = None
        self.pages = []
        self.names = []
        self.base = None

        self.current = 0
        self.previous = 0
        self.eof = 0

        self.controls = {'⏮': 0.0, '◀': -1, '⏹': 'stop',
                         '▶': +1, '⏭': None}

    async def indexer(self, ctx, ctrl):
        if ctrl == 'stop':
            ctx.bot.loop.create_task(self.stop_controller(self.base))

        elif isinstance(ctrl, int):
            self.current += ctrl
            if self.current > self.eof or self.current < 0:
                self.current -= ctrl
        else:
            self.current = int(ctrl)

    async def reaction_controller(self, ctx):
        bot = ctx.bot
        author = ctx.author

        if self.other_target:
            self.base = await self.other_target.send(embed=self.pages[0])
        else:
            self.base = await ctx.send(embed=self.pages[0])

        if len(self.pages) == 1:
            await self.base.add_reaction('⏹')
        else:
            for reaction in self.controls:
                try:
                    await self.base.add_reaction(reaction)
                except discord.HTTPException:
                    return

        def norm(emoji):
            return str(emoji).replace('\ufe0f', '')

        controls = {norm(k): v for k, v in self.controls.items()}

        # Use raw reaction events: the normal reaction_add event is only dispatched when the
        # reacting user is in the bot's cache, which often isn't the case in DMs, so page
        # switching silently did nothing there.
        def check(payload):
            return (payload.message_id == self.base.id
                    and payload.user_id == author.id
                    and payload.user_id != bot.user.id
                    and norm(payload.emoji) in controls)

        # In DMs (or when we lack Manage Messages) the bot can't remove the user's reaction,
        # so we also listen for reaction removal to let the user just toggle the reaction.
        listen_remove = self.base.guild is None

        while True:
            events = ['raw_reaction_add'] + (['raw_reaction_remove'] if listen_remove else [])
            waiters = [asyncio.ensure_future(bot.wait_for(e, check=check)) for e in events]
            try:
                done, _ = await asyncio.wait(waiters, timeout=self.timeout, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for w in waiters:
                    if not w.done():
                        w.cancel()
            if not done:
                return ctx.bot.loop.create_task(self.stop_controller(self.base))

            payload = done.pop().result()
            control = controls.get(norm(payload.emoji))

            if payload.event_type == 'REACTION_ADD' and not listen_remove:
                try:
                    await self.base.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
                except discord.HTTPException:
                    listen_remove = True

            self.previous = self.current
            await self.indexer(ctx, control)

            if self.previous == self.current:
                continue

            try:
                await self.base.edit(embed=self.pages[int(self.current)])
            except (KeyError, IndexError, discord.HTTPException):
                pass

    async def stop_controller(self, message):
        # try:
        #     await message.delete()
        # except discord.HTTPException:
        #     pass

        try:
            self.controller.cancel()
        except Exception:
            pass

    def formmater(self, chunk):
        return '\n'.join(f'{self.prepend}{self.fmt}{value}{self.fmt[::-1]}{self.append}' for value in chunk)

    async def paginate(self, ctx):
        if self.extras:
            self.pages = [p for p in self.extras if isinstance(p, discord.Embed)]

        if self.entries:
            chunks = [c async for c in pager(self.entries, self.length)]

            for index, chunk in enumerate(chunks):
                page = discord.Embed(title=f'{self.title} - {index + 1}/{len(chunks)}', color=self.colour)
                page.description = self.formmater(chunk)

                if self.footer:
                    page.set_footer(text=self.footer)
                self.pages.append(page)

        if not self.pages:
            raise Exception('There must be enough data to create at least 1 page for pagination.')

        self.eof = float(len(self.pages) - 1)
        self.controls['⏭'] = self.eof
        self.controller = ctx.bot.loop.create_task(self.reaction_controller(ctx))
