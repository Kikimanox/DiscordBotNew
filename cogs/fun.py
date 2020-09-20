import asyncio
import datetime
import json
import random

import discord
from discord.ext import commands
from discord import Member, Embed, File, utils
import os
import traceback
from models.claims import ClaimsManager, Claimed, UserSettings, History
from utils.dataIOa import dataIOa
import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # _ in channel names is not allowed!!
        # if you want an - instead of a space prefix ch name with _
        self.data = {}
        self.config = dataIOa.load_json('settings/claims_settings.json')
        bot.loop.create_task(self.set_setup())
        self.just_claimed = {}
        self.possible = ['bride', 'vtuber']  # THESE TWO HAVE TO BE THE SAME

    async def set_setup(self):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
        try:
            self.data = await ClaimsManager.get_data_from_server(self.bot, self.config)
        except:
            print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            print("Claims data not loaded")
            traceback.print_exc()
            self.data = {'-1-1-1': '-1-1-1'}
            return
        print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
        print("Claims data loaded")

    @commands.group(aliases=['bride', 'vtuber'])  # THESE TWO HAVE TO BE THE SAME
    async def claim(self, ctx, *, subcmd=""):
        """Get your daily claim for a certain theme

        Command usages:
        `[p]claim` - shows this output
        `[p]bride` - get your bride
        `[p]vtuber` - get your daily vtuber

        Use subcommands for other functionalities
        """
        # return await ctx.send("Currently disabled unti the bot is oficially live.")
        cmd = ctx.invoked_with
        if cmd == 'claim' and not subcmd:
            raise commands.errors.BadArgument

        async def exec_cmd(name):
            if not subcmd:
                return await self.do_claim(ctx, name)
            first_arg = subcmd.split(' ')[0]
            if first_arg in ctx.command.all_commands:
                c = ctx.command.all_commands[first_arg]
                if subcmd:
                    argz = subcmd.split(' ')[1:]
                    try:
                        if len(c.clean_params) < len(argz):
                            return await ctx.invoke(c, ' '.join(argz))
                        else:
                            return await ctx.invoke(c, *argz)
                    except:
                        traceback.print_exc()
                        return await ctx.send("Something went wrong because of incorrect command usage.")
                else:
                    return await ctx.invoke(c)  # unsafe, becareful where you use this
            else:
                raise commands.errors.BadArgument

        if ctx.subcommand_passed and ctx.subcommand_passed not in [*ctx.command.all_commands]:
            raise commands.errors.BadArgument

        await exec_cmd(cmd)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @claim.command()
    async def current(self, ctx, *user):
        """See currently claimed claim"""
        users = ' '.join(user)
        if not self.data:
            return await ctx.send("Hold up a little bit, I'm still loading the data.")
        if '-1-1-1' in self.data and self.data['-1-1-1'] == '-1-1-1':
            return await ctx.send("Something went wrong when loading data, please contact the bot owner.")
        if user:
            member = await dutils.try_get_member(ctx, user)
        else:
            member = ctx.author
        if not member:
            return await ctx.send("Can't find this member")
        idd = ctx.author.id
        if member: idd = member.id
        claim_type = ctx.invoked_with
        if claim_type not in self.possible: return await ctx.send("cmd_type has to be one of: "
                                                                  f"{', '.join(self.possible)}")
        usr = Claimed.select().where(Claimed.user == idd,
                                     Claimed.type == claim_type,
                                     Claimed.expires_on > datetime.datetime.utcnow())
        if usr:
            usr = usr.get()
            em = Embed(title=f'**{usr.char_name}**', color=int(usr.color_string, 16))
            cnt = ""
            if usr.is_nsfw:
                em.set_footer(text='⚠ potentially nsfw image')
                cnt = f'||{usr.img_url} ||'
            else:
                em.set_image(url=usr.img_url)
            if idd == ctx.author.id:
                await ctx.send(embed=em, content=f'{ctx.author.mention} your {claim_type} for the day is:')
            else:
                await ctx.send(embed=em, content=f'{ctx.author.mention} `{member}` currently has this {claim_type} '
                                                 f'for the day:')
            if cnt:
                await ctx.send(cnt)
        else:
            if idd == ctx.author.id:
                await ctx.send(f"{ctx.author.mention} you have no `{claim_type}` claimed currently.")
            else:
                await ctx.send(f"{ctx.author.mention} `{member}` has no `{claim_type}` claimed currently.")

    @commands.cooldown(1, 5, commands.BucketType.user)
    @claim.command()
    async def history(self, ctx, *user):
        """See claim history"""
        users = ' '.join(user)
        if not self.data:
            return await ctx.send("Hold up a little bit, I'm still loading the data.")
        if '-1-1-1' in self.data and self.data['-1-1-1'] == '-1-1-1':
            return await ctx.send("Something went wrong when loading data, please contact the bot owner.")
        if user:
            member = await dutils.try_get_member(ctx, user)
        else:
            member = ctx.author
        if not member:
            return await ctx.send("Can't find this member")
        idd = ctx.author.id
        if member: idd = member.id
        claim_type = ctx.invoked_with
        if claim_type not in self.possible: return await ctx.send("cmd_type has to be one of: "
                                                                  f"{', '.join(self.possible)}")

        h, _ = History.get_or_create(user=idd, type=claim_type)
        his = json.loads(h.meta)
        if not his:
            his = self.prepare_for_history(self.data[claim_type])
        if idd == ctx.author.id:
            pass  # ret for the invoked user
        else:
            pass  # ret for the target user
        # await ctx.send(json.dumps(his, indent=4, sort_keys=False))
        hiss = {'last_3_claims': his['last_3_claims']}
        del his['last_3_claims']
        his = ({k: v for k, v in sorted(his.items(), key=lambda item: item[1], reverse=True)[:10]})
        his['last_3_claims'] = hiss['last_3_claims']
        his['last_3_claims'][0] += ' (last claim)'

        color = None
        url = None
        usr = Claimed.select().where(Claimed.user == idd,
                                     Claimed.type == claim_type,
                                     Claimed.expires_on > datetime.datetime.utcnow())
        if usr:
            usr = usr.get()
            color = usr.color_string
            if not usr.is_nsfw:
                url = usr.img_url

        if color:
            color = int(color, 16)
        aa = '\n'.join(his['last_3_claims'])
        del his['last_3_claims']
        bb = '\n'.join([f'{k} - {v}' for k, v in his.items()])
        desc = f"**Last 3 {claim_type} claims:**\n{aa}\n\n**Claim statistic:**\n{bb}"
        em = Embed(title=f"History for {ctx.author.display_name}", description=desc)
        if color:
            em.colour = color
            if url:
                em.set_thumbnail(url=url)
            else:
                em.set_footer(text='⚠ potentially nsfw pic claim thumbnail ignored')
        if idd == ctx.author.id:
            await ctx.send(content=f'{ctx.author.mention} your {claim_type} claim history:', embed=em)
        else:
            await ctx.send(content=f'{ctx.author.mention} {claim_type} claim history for {member}:', embed=em)

    @commands.cooldown(1, 10, commands.BucketType.user)
    @claim.command()
    async def nsfw(self, ctx, cmd_type="", setting: str = ""):
        """Nsfw [off|default]
        If you want to for example turn off nsfw for the vtuber command use:
        `[p]claim nsfw vtuber TYPE`

        TYPE has to be one of `off`, `default`
        """
        if setting not in ['off', 'default']: return await ctx.send(f"Invalid cmd usage, check "
                                                                    f"`{dutils.bot_pfx_by_gid(self.bot, ctx.guild.id)}"
                                                                    f"help claim nsfw`")
        if cmd_type not in self.possible: return await ctx.send("cmd_type has to be one of: "
                                                                f"{', '.join(self.possible)}")
        u, _ = UserSettings.get_or_create(user=ctx.author.id, type=cmd_type)
        u.nsfw = setting
        u.save()
        await ctx.send(f"Your nsfw setting for `{cmd_type}` has ben set to `{setting}`")

    async def do_claim(self, ctx, c_type, claim_cd=20):
        if not self.data:
            return await ctx.send("Hold up a little bit, I'm still loading the data.")
        if '-1-1-1' in self.data and self.data['-1-1-1'] == '-1-1-1':
            return await ctx.send("Something went wrong when loading data, please contact the bot owner.")
        utcnow = datetime.datetime.utcnow()
        now = utcnow.timestamp()
        d_key = f"{ctx.author.id}_{c_type}"
        anti_spam_cd = 15
        # [invoked_times, invoked_at]
        if d_key in self.just_claimed:
            if now - self.just_claimed[d_key][1] < anti_spam_cd:
                self.just_claimed[d_key][0] += 1
                if self.just_claimed[d_key][0] > 2:  # the 3rd spam is nuke
                    out = f'[spamming {c_type} | {ctx.message.content}]({ctx.message.jump_url})'
                    await dutils.blacklist_from_bot(self.bot, ctx.message.author, out,
                                                    ctx.message.guild.id,
                                                    ch_to_reply_at=ctx.message.channel, arl=0)
                else:
                    await ctx.send(f"💢 {ctx.author.mention} stop spamming the "
                                   f"`{c_type}` command, or else!", delete_after=10)
            else:
                del self.just_claimed[d_key]
        else:
            self.just_claimed[d_key] = [0, now]

        if d_key in self.just_claimed and self.just_claimed[d_key][0] == 0:
            d = self.data[c_type]
            u = UserSettings.get_or_none(user=ctx.author.id, type=c_type)
            while True:
                orig_key = random.choice(list(d))
                orig_key_split = orig_key.split('_')
                color = int(orig_key_split[1], 16)
                got = random.choice(d[orig_key][0])  # attachements list on index 0
                attachement = got[0]  # urls
                is_nsfw = got[1]
                if not u:
                    break
                if u.nsfw == 'off' and not is_nsfw:
                    break
                if u.nsfw == 'default':
                    break
                if u.nsfw == 'off' and is_nsfw:
                    continue

            usr = Claimed.select().where(Claimed.user == ctx.author.id,
                                         Claimed.type == c_type,
                                         Claimed.expires_on > utcnow)
            if usr:
                usr.get()
                await ctx.send(f"{ctx.author.mention} you already have a claimed {c_type}. Please try again in "
                               f"**{tutils.convert_sec_to_smh((usr.expires_on - utcnow).total_seconds())}**")
                if d_key in self.just_claimed:
                    del self.just_claimed[d_key]
            else:
                claim, created = Claimed.get_or_create(user=ctx.author.id, type=c_type)
                claim.expires_on = utcnow + datetime.timedelta(hours=claim_cd)
                claim.char_name = orig_key_split[0]
                claim.color_string = orig_key_split[1]
                claim.is_nsfw = is_nsfw
                claim.img_url = attachement.url
                claim.save()
                file = None
                em = Embed(title=f'**{orig_key_split[0]}**', color=color)
                if is_nsfw:
                    file = await attachement.to_file(spoiler=True, use_cached=True)
                    em.set_footer(text='⚠ potentially nsfw image')
                    # em.set_image(url=f'attachment://{file.filename}')
                else:
                    em.set_image(url=attachement.url)
                await ctx.send(embed=em, content=f'\nYou can check claim history by using '
                                                 f'`{dutils.bot_pfx_by_gid(self.bot, ctx.guild.id)}'
                                                 f'{c_type} history`\n'
                                                 f'{ctx.author.mention} your {c_type} for the day is:', file=file)
                h, _ = History.get_or_create(user=ctx.author.id, type=c_type)
                his = json.loads(h.meta)
                if not his:
                    his = self.prepare_for_history(d)
                his[orig_key_split[0]] += 1
                his['last_3_claims'] = his['last_3_claims'][:2]
                his['last_3_claims'].insert(0, orig_key_split[0])
                h.meta = json.dumps(his)
                h.save()

            # when done remove them if they aren't spamming anymore
            await asyncio.sleep(anti_spam_cd + 1)
            if d_key in self.just_claimed:
                del self.just_claimed[d_key]

    @staticmethod
    def prepare_for_history(d):
        ret = {}
        for k in [*d]:
            ret[k.split('_')[0]] = 0
        ret['last_3_claims'] = []
        return ret

    async def delete_old_records(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                dd = Claimed.delete().where(Claimed.expires_on < datetime.datetime.utcnow()).execute()
                if dd > 0:
                    # print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
                    # print(f'Deleted {dd} expired claim data from the db')
                    self.bot.logger.info(f'Deleted {dd} expired claim data from the db')
            except:
                pass
            await asyncio.sleep(86400 * 3)  # every 3 days


def setup(bot):
    ext = Fun(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.delete_old_records()))
    bot.add_cog(ext)
