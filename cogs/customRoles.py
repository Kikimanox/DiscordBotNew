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


class CustomRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gettingRoles = {}

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.group(invoke_without_command=True)
    async def getrole(self, ctx):
        """This command is only used for verification

        For the rest of the functionalities use subcommands,
        if you are a server booster/supporter you may use:

        For boosters see: `[p]help getrole booster`/`[p]getrole booster`"""
        b = await checks.custom_role_is_booster_check(ctx)
        await ctx.send(f"{ctx.author.mention} you can {' ' if b else 'not '}get custom roles. {'✅' if b else '❌'}")
        if b: await ctx.send(f"(use `{dutils.bot_pfx_by_ctx(ctx)}help getrole` to see help)")

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.check(checks.custom_role_is_booster_check)
    @getrole.command()
    async def booster(self, ctx, roleHexColor, *, roleName):
        """Get yourself a custom role or change it's name or color

        Example, arguments are:
        [- hex color code](https://htmlcolorcodes.com/color-picker/)
        **the hex color has to have 6 hex digits to represent it**
        - rolename

        `[p]getrole booster F1B2C3 MyRoleName` """
        if str(ctx.guild.id) in self.gettingRoles and self.gettingRoles[str(ctx.guild.id)]: return await ctx.send(
            "Someone is already getting/removing their role, please wait a little bit.")
        await self.getRoleFunction(ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][str(ctx.guild.id)]['ANCHOR_TOP'],
                                   ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][str(ctx.guild.id)]['ANCHOR_BOTTOM'],
                                   ctx, roleName, roleHexColor[:6])

    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.check(checks.custom_role_is_booster_check)
    @getrole.command()
    async def reset(self, ctx):
        """Remove your custom role"""
        if str(ctx.guild.id) in self.gettingRoles and self.gettingRoles[str(ctx.guild.id)]: return await ctx.send(
            "Someone is already getting/removing their role, please wait a little bit.")
        self.gettingRoles[str(ctx.guild.id)] = 1
        try:
            b = await self.removeCustomRoleBetweenAnchors(ctx.author, ctx.guild,
                                                          ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][
                                                              str(ctx.guild.id)]['ANCHOR_TOP'],
                                                          ctx.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][
                                                              str(ctx.guild.id)]['ANCHOR_BOTTOM']
                                                          )
            if b:
                try:
                    await dutils.log(ctx.bot, "Custom booster role removed", f"For: {ctx.author.id}", ctx.author,
                                     colorr=0x33d8f0, this_hook_type='reg')
                    await ctx.send(f"Your custom booster role on the **{ctx.guild.name}** server has been removed.")
                except:
                    pass
            else:
                await ctx.send("You don't have a custom role.")
        finally:
            self.gettingRoles[str(ctx.guild.id)] = 0

    async def getRoleFunction(self, ancohrID1, anchorID2, ctx, roleName, roleHexColor):

        if str(ctx.guild.id) in self.gettingRoles and self.gettingRoles[str(ctx.guild.id)]: return await ctx.send(
            "Someone is already getting/removing their role, please wait a little bit.")

        try:
            self.gettingRoles[str(ctx.guild.id)] = 1
            roleHexColor = roleHexColor.strip()
            if len(roleHexColor) < 6: return await ctx.send("Hex code should be 6 digits")
            roleHexColor = f'0x{roleHexColor}'
            try:
                color = int(roleHexColor, 16)
                if len(roleName) > 32: return await ctx.send('Role name too long, max 32 chars')
            except:
                return await ctx.send("Error, something went wrong")

            m = await ctx.send("Creating custom role...")

            await self.removeCustomRoleBetweenAnchors(ctx.author, ctx.guild, ancohrID1, anchorID2)
            newR = await ctx.guild.create_role(reason=f"Custom assigned role {ancohrID1}", name=roleName,
                                               color=discord.Colour(color))
            await self.insertRoleUnderRole(ctx, newR, ancohrID1)
            await ctx.author.add_roles(newR)
            await m.delete()
            await ctx.send(embed=Embed(description=f"New role created and applied", color=discord.Colour(color)))
            await dutils.log(ctx.bot, f"Booster {ctx.author.name} ({ctx.author.id}) created their own role",
                             f"Role name: **{roleName}**", ctx.author,
                             colorr=discord.Colour(color), this_hook_type='modlog')
        finally:
            self.gettingRoles[str(ctx.guild.id)] = 0

    async def removeCustomRoleBetweenAnchors(self, author, guild, an1id, an2id):
        rolesB = await self.getRolesBetweenAnchors(guild, an1id, an2id)
        ret = False
        for r in rolesB:
            if r in author.roles:
                await author.remove_roles(r)
                await r.delete(reason="Deleted booster role because they either changed it or unboosted")
                ret = True
        return ret

    @staticmethod
    async def getRolesBetweenAnchors(guild, anchorID1, anchorID2):
        # rolesAll = guild.roles
        a1 = discord.utils.get(guild.roles, id=int(anchorID1))
        a2 = discord.utils.get(guild.roles, id=int(anchorID2))
        if a1.position < a2.position:
            tmp = a1
            a1 = a2
            a2 = tmp
        return [r for r in guild.roles if a1.position > r.position > a2.position]

    @staticmethod
    async def insertRoleUnderRole(ctx, newRole, anchorID):
        aa = 11
        while True:
            # print('----')
            a = discord.utils.get(ctx.guild.roles, id=int(anchorID))
            ddd = a.position
            # print(f'A pos: {a.position}')
            p = a.position - 1
            # print(f'new role should get: {p}')
            await newRole.edit(position=p)
            # print(f'new role got: {newRole.position}')
            if newRole.position != p:
                # print("Problem 1")
                aa -= 1
                if aa == 0: return await ctx.send("Please contact a mod sicne "
                                                  "discord's api isn't allowing automatization, "
                                                  "or try again a little"
                                                  "bit later")
                await newRole.edit(position=1)
                await asyncio.sleep(1.5)
                continue
            a = discord.utils.get(ctx.guild.roles, id=int(anchorID))
            # print(f'A pos after: {a.position}')
            if a.position != ddd:
                if newRole.position != p:
                    # print("Problem 2")
                    aa -= 1
                    if aa == 0: return await ctx.send("Please contact a mod sicne "
                                                      "discord's api isn't allowing automatization, "
                                                      "or try again a little"
                                                      "bit later")
                    await newRole.edit(position=1)
                    await asyncio.sleep(1.5)
                    continue
            if newRole.position == 1:
                # print("Problem 3")
                aa -= 1
                if aa == 0: return await ctx.send("Please contact a mod sicne "
                                                  "discord's api isn't allowing automatization, "
                                                  "or try again a little"
                                                  "bit later")
                await asyncio.sleep(1.5)
                continue
            else:
                break

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if 'BOOSTER_CUSTOM_ROLES_GETTER' in self.bot.config and str(after.guild.id) in self.bot.config[
            'BOOSTER_CUSTOM_ROLES_GETTER'] and 'BOOSTER_ROLE_ID' in self.bot.config[
            'BOOSTER_CUSTOM_ROLES_GETTER'][str(after.guild.id)]:
            lost = await self.checkIfLostBoosterRole(self.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][
                                                         str(after.guild.id)]['BOOSTER_ROLE_ID'],
                                                     before, after)
            if lost:
                b = await self.removeCustomRoleBetweenAnchors(after, after.guild,
                                                              self.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][
                                                                  str(after.guild.id)]['ANCHOR_TOP'],
                                                              self.bot.config['BOOSTER_CUSTOM_ROLES_GETTER'][
                                                                  str(after.guild.id)]['ANCHOR_BOTTOM']
                                                              )
                if b:
                    try:
                        await dutils.log(self.bot, title="Custom booster role removed", txt=f"For: {after.id}",
                                         author=after, colorr=0x33d8f0, this_hook_type='reg')
                        await after.send(
                            f"Your custom booster role on the **{after.guild.name}** server has been removed.")
                    except:
                        pass

    @staticmethod
    async def checkIfLostBoosterRole(boosterRoleID, before, after):
        try:
            booster_role = discord.utils.get(before.guild.roles, id=int(boosterRoleID))
            if booster_role in [r for r in before.roles] and booster_role not in [r for r in after.roles]:
                return True
        except:
            pass
        return False


def setup(bot):
    ext = CustomRoles(bot)
    # bot.running_tasks.append(bot.loop.create_task(ext.if_you_need_loop()))
    bot.add_cog(ext)
