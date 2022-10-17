from discord.ext import commands


class ClassName(commands.Cog):
    def __init__(
            self,
            bot: commands.Bot
    ):
        self.bot = bot

    @commands.command(aliases=["q"])
    async def CommandName(self, ctx, *args):
        """Desc here"""
        await ctx.send("Something")

    # async def if_you_need_loop(self):
    #     await self.bot.wait_until_ready()
    #     while True:
    #         try:
    #             print("Code here")
    #         except:
    #             pass
    #         await asyncio.sleep(10)  # sleep here


async def setup(
        bot: commands.Bot
):
    ext = ClassName(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    await bot.add_cog(ext)
