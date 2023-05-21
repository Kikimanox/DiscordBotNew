from __future__ import annotations
from typing import TYPE_CHECKING

import asyncio
import datetime
import itertools
import json
import logging
import random
import traceback

import discord
from discord import Embed
from discord.ext import commands

import utils.checks as checks
import utils.discordUtils as dutils
import utils.timeStuff as tutils
from models.claims import ClaimsManager, Claimed, UserSettings, History
from utils.dataIOa import dataIOa

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context


conf = dataIOa.load_json('settings/claims_settings.json')
possible_for_bot = conf['use_these']

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")


class Fun(commands.Cog):
    def __init__(
            self,
            bot: KanaIsTheBest
    ):
        self.bot = bot
        # _ in channel names is not allowed!!
        # if you want an - instead of a space prefix ch name with _
        self.data = {}
        bot.loop.create_task(self.set_setup())
        self.just_claimed = {}
        self.possible = possible_for_bot  # THESE TWO HAVE TO BE THE SAME

    async def set_setup(self):
        if not self.bot.is_ready():
            await self.bot.wait_until_ready()
        try:
            self.data = await ClaimsManager.get_data_from_server(self.bot, conf)
        except:
            # print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
            error_logger.error(f"Claims data not loaded\n{traceback.format_exc()}")
            # traceback.print_exc()
            self.data = {'-1-1-1': '-1-1-1'}
            return
        # print(f'---{datetime.datetime.utcnow().strftime("%c")}---')
        logger.info("Claims data loaded")

    @commands.group(aliases=possible_for_bot)  # THESE TWO HAVE TO BE THE SAME (also update help desc when adding)
    async def claim(self, ctx: Context, *, subcmd=""):
        """Get your daily claim for a certain theme

        Command usages:
        `[p]claim` - shows this output

        `[p]any_of_the_possible_above_listed_subcommands`
        (See the part right from `Syntax:` at the top)
        Example: `[p]bride`

        Use subcommands for other functionalities
        """
        cmd = ctx.invoked_with
        if cmd == 'claim' and not subcmd:
            raise commands.errors.BadArgument

        async def exec_cmd(name):
            if not subcmd:
                return await self.do_claim(ctx, name)
            first_arg = subcmd.split(' ')[0]
            if first_arg in ctx.command.all_commands or first_arg in ['multi']:  # multi can still execute normally
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

    @commands.cooldown(1, 120, commands.BucketType.user)
    @claim.command()
    async def multi(self, ctx: Context, *claim_types):
        """Claim multiple at once, ex: `[p]claim multi bride spirit vtuber`"""
        if str(claim_types[0]) == 'all':
            ar = possible_for_bot
        else:
            ar = str(claim_types[0]).split(' ')
        to_claim = list(set(ar) & set(possible_for_bot))
        if not to_claim:
            return await ctx.send(f"None of your claim_types were valid.\nYou can do `{dutils.bot_pfx_by_ctx(ctx)}"
                                  f"claim multi {' '.join(possible_for_bot)}` (leaving out those that you don't want"
                                  f" to claim")
        if len(to_claim) == 1:
            return await ctx.send("Why are you using only one type in **multi** claim? 🤔")

        ch: discord.TextChannel = ctx.channel
        hook = None

        try:
            hooks = await ch.webhooks()
            for h in hooks:
                if h.user.id == self.bot.user.id and h.name.startswith('Multi claim'):
                    hook = h
                    break
            if not hook:
                hook = await ch.create_webhook(name="Multi claim")
        except:
            return await ctx.send("Something went wrong, maybe I'm missing manage webhook perms?")

        embeds = []
        cds = []
        for claim in to_claim:
            e = await self.do_claim(ctx, claim, claim_cd=20, multi_claim=True)

            if e and not isinstance(e, str):
                embeds.append(e)
            if e and isinstance(e, str):
                cds.append(f"{claim} - {e}")

        if embeds and isinstance(hook, discord.Webhook):
            await hook.send(avatar_url=ctx.author.display_avatar.url,
                            username=f'Multi claim for {ctx.author.name}'[:32],
                            wait=False, embeds=embeds, content=f'{ctx.author.mention} your multi claim:\n' +
                                                               '\n'.join(cds))
        else:
            await ctx.send("Nothing out of these is available to claim at the moment.\n" + '\n'.join(cds))

    @commands.cooldown(1, 5, commands.BucketType.user)
    @claim.command()
    async def current(self, ctx: Context, *user):
        """Display currently claimed claim"""
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
                cnt = f'|| {usr.img_url} ||'
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
    async def history(self, ctx: Context, *user):
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
        if not his['last_3_claims']:
            if member.id == ctx.author.id:
                return await ctx.send(f"{member.mention} you have no claim history for the "
                                      f"**{claim_type}** command")
            else:
                return await ctx.send(f"{member.display_name} has no claim history for the "
                                      f"**{claim_type}** command")
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
        em = Embed(title=f"History for {member.display_name}", description=desc)
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
    async def nsfw(self, ctx: Context, cmd_type="", setting: str = ""):
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

    async def do_claim(self, ctx: Context, c_type, claim_cd=20, multi_claim=False):
        if not self.data:
            if multi_claim: return "Hold up a little bit, I'm still loading the data."
            return await ctx.send("Hold up a little bit, I'm still loading the data.")
        if '-1-1-1' in self.data and self.data['-1-1-1'] == '-1-1-1':
            if multi_claim: return ""
            return await ctx.send("Something went wrong when loading data, please contact the bot owner.")

        utcnow = datetime.datetime.utcnow()
        now = utcnow.timestamp()
        d_key = f"{ctx.author.id}_{c_type}"
        anti_spam_cd = 15
        # [invoked_times, invoked_at]

        if d_key in self.just_claimed and ctx.guild.id != 202845295158099980:
            if now - self.just_claimed[d_key][1] < anti_spam_cd:
                self.just_claimed[d_key][0] += 1
                if self.just_claimed[d_key][0] > 2 and not multi_claim:  # the 3rd spam is nuke
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

        if ctx.guild.id == 202845295158099980:
            self.just_claimed[d_key][0] = 0

        if d_key in self.just_claimed and self.just_claimed[d_key][0] == 0:
            d = self.data[c_type]
            ######################## extra for raiha only
            if ctx.guild.id in [599963725352534027, 202845295158099980]:  # raiha, pastebin
                dabs = ["Hibiki Higoromo",
                        "Tsuan",
                        "Rinemu Kirari",
                        "Mizuha Banouin",
                        "Carte Á Jouer",
                        "White Queen",
                        "Kareha Banoui",
                        "Retsumi Jugasak",
                        "Ariadne Foxro",
                        "Yuri Sagakure",
                        "Yui Sagaku",
                        "Oka Miyafuj",
                        "Maya Yukish",
                        "Cistus",
                        "Panie Ibusu",
                        "Isami Hijika",
                        "Haraka Kagar"
                        ]
                for dab in dabs:
                    d = {k: v for k, v in d.items() if not k.startswith(dab)}
            ######################## / extra for raiha only
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

            em = None

            usr = Claimed.select().where(Claimed.user == ctx.author.id,
                                         Claimed.type == c_type,
                                         Claimed.expires_on > utcnow)
            if usr:
                usr = usr.get()
                if not multi_claim:
                    await ctx.send(f"{ctx.author.mention} you already have a claimed {c_type}. Please try again in "
                                   f"**{tutils.convert_sec_to_smhd((usr.expires_on - utcnow).total_seconds())}**")
                if d_key in self.just_claimed:
                    del self.just_claimed[d_key]

                if multi_claim:
                    em = f"**{tutils.convert_sec_to_smhd((usr.expires_on - utcnow).total_seconds())}** (cooldown)"
            else:
                claim, created = Claimed.get_or_create(user=ctx.author.id, type=c_type)
                claim.expires_on = utcnow + datetime.timedelta(hours=claim_cd)
                claim.char_name = orig_key_split[0]
                claim.color_string = orig_key_split[1]

                is_nsfw = False
                claim.is_nsfw = is_nsfw

                april_fools_gifs = [
                    "https://media.tenor.com/0i1iYtef-E8AAAAC/senator-armstrong-mgr.gif",
                    "https://media.tenor.com/y1n4lM9lR_kAAAAC/take-no.gif",
                    "https://media.tenor.com/_OjhUydgpewAAAAC/knight-crusade.gif",
                    "https://media.tenor.com/zH8163kZuGYAAAAC/cat-troll.gif",
                    "https://media.tenor.com/y4y_imPQW_EAAAAC/hayao-miyazaki.gif",
                    "https://media.tenor.com/tWDStldeFzoAAAAC/mirage-c-sgo.gif",
                    "https://media.tenor.com/HEIXykQDLEYAAAAC/interrogate-interrogation.gif",
                    "https://media.tenor.com/Pk681SQt0doAAAAC/who-tf-asked-nasas-radar-dish.gif",
                    "https://media.tenor.com/LC6PUN1zDEEAAAAC/master-chef-gordon-ramsey.gif",
                    "https://media.tenor.com/8r8fQirM2J0AAAAC/cope.gif",
                    "https://media.tenor.com/dAAYNxTXxNcAAAAC/yu-gi-oh-kaiba.gif",
                    "https://media.tenor.com/DlXfjL9WEHYAAAAC/ight-imma-head-out-meme.gif",
                    "https://media.tenor.com/cg1qeOdO7iIAAAAC/skull.gif",
                    "https://media.tenor.com/baKBrVTtR64AAAAC/zyzz-fistpump.gif",
                    "https://media.tenor.com/3Kay6k6K8goAAAAC/garnidelia-jpop.gif",
                    "https://media.tenor.com/AuVGD785SdgAAAAC/tyunsmol-argue.gif",
                    "https://media.tenor.com/b9x_ATvAhTUAAAAC/ya-boy-kongming-kongming-zhuge.gif",
                    "https://media.tenor.com/wU0tRu7W-7AAAAAC/close-laptop-throw-laptop.gif",
                    "https://media.tenor.com/uQH5B9R0dUYAAAAC/john-wick.gif",
                    "https://media.tenor.com/3vxOt6Xi_AEAAAAC/will-smith-chris-rock.gif",
                    "https://media.tenor.com/nLqcQPtAKoQAAAAC/thor-avenger.gif",
                    "https://media.discordapp.net/attachments/927908401818787890/1010264301975642244/ezgif.com-gif-maker_1.gif",
                    "https://media.tenor.com/58sFGy5a_DwAAAAC/crunk-aint-dead-duke.gif",
                    "https://media.discordapp.net/attachments/409481404913811476/775262070916251658/image0-2.gif",
                    "https://media.tenor.com/_h_1fcwEkHYAAAAC/studying-windy.gif",
                    "https://media.discordapp.net/attachments/312415940291854337/896167232890077256/image0-69.gif",
                    "https://media.tenor.com/bVOjfxYAE4UAAAAC/fire-extinguisher.gif",
                    "https://media.tenor.com/PLmdD2lWZ-IAAAAC/kaguya-miyuki.gif",
                    "https://media.tenor.com/2qWOttPCjfEAAAAC/maxverstappen-max.gif",
                    "https://media.tenor.com/W3wUoMhulrwAAAAC/lycoris-recoil-lycoris.gif",
                    "https://media.tenor.com/e-gxOAhgKrMAAAAd/lycoris-recoil-lycoris.gif",
                    "https://media.tenor.com/DF19lPBGFS4AAAAd/anime-yui-hirasawa.gif",
                    "https://media.tenor.com/s-Z9_lAMMwIAAAAC/several-several-people.gif",
                    "https://media.tenor.com/WiYcd_3un5gAAAAC/dont-care-didnt-ask.gif",
                    "https://cdn.discordapp.com/emojis/959313721103097918.gif?size=128&quality=lossless",
                    "https://media.tenor.com/34KwHfjQCeEAAAAC/diagnosis-skill.gif",
                    "https://media.tenor.com/uGN34orccIEAAAAC/skillissue-skill.gif",
                    "https://media.tenor.com/PyOaueYQxWkAAAAC/excited-run.gif",
                    "https://media.tenor.com/Bu5E2PUPVa0AAAAC/one-punch-man-anime-girl.gif",
                    "https://media.tenor.com/dnl9edCif_cAAAAC/your-memes-have-no-effect-ignore.gif",
                    "https://media.tenor.com/_-VchEviX_QAAAAC/meme-memes.gif",
                    "https://media.tenor.com/G_p24OxHrC8AAAAC/my-honest-reaction-my-reactioj.gif",
                    "https://media.tenor.com/r47fIhy7dGMAAAAC/anime-meme.gif",
                    "https://media.tenor.com/PabY48tHpbUAAAAC/who-asked-k-on.gif",
                    "https://media.tenor.com/8darUV8MNfUAAAAC/jarvis-iron-man.gif",
                    "https://media.tenor.com/aUIi6J19OlcAAAAC/ohio-roblox.gif",
                    "https://media.tenor.com/l1pzwy1cNWAAAAAC/memes.gif",
                    "https://media.tenor.com/aAyJOCQWUKMAAAAC/cat-meme.gif",
                    "https://media.tenor.com/fgMEV-0EbzMAAAAC/ohio-average.gif",
                ]
                # claim.img_url = random.choice(april_fools_gifs)
                claim.img_url = attachement.url
                if ctx.guild.id != 202845295158099980:
                    claim.save()
                file = None
                em = Embed(title=f'**{orig_key_split[0]}**', color=color)
                if is_nsfw:
                    file = await attachement.to_file(spoiler=True, use_cached=True)
                    em.set_footer(text='⚠ potentially nsfw image')
                    # em.set_image(url=f'attachment://{file.filename}')
                else:
                    em.set_image(url=claim.img_url)
                if not multi_claim:
                    await ctx.send(embed=em, content=f'\nYou can check claim history by using '
                                                     f'`{dutils.bot_pfx_by_gid(self.bot, ctx.guild.id)}'
                                                     f'{c_type} history`\n'
                                                     f'{ctx.author.mention} your {c_type} for the day is:', file=file)
                if ctx.guild.id != 202845295158099980:
                    h, _ = History.get_or_create(user=ctx.author.id, type=c_type)
                    his = json.loads(h.meta)
                    if not his:
                        his = self.prepare_for_history(d)
                    if orig_key_split[0] not in his:
                        his[orig_key_split[0]] = 0
                    his[orig_key_split[0]] += 1
                    his['last_3_claims'] = his['last_3_claims'][:2]
                    his['last_3_claims'].insert(0, orig_key_split[0])
                    h.meta = json.dumps(his)
                    h.save()

            if multi_claim:
                if d_key in self.just_claimed:
                    del self.just_claimed[d_key]
                if is_nsfw:
                    return f"|| {attachement.url} || ⚠ potentially nsfw image for **{orig_key_split[0]}**"
                return em

            # when done remove them if they aren't spamming anymore
            await asyncio.sleep(anti_spam_cd + 1)
            if d_key in self.just_claimed:
                del self.just_claimed[d_key]

    @commands.command(hidden=True, aliases=['m'])
    async def mood(self, ctx: Context):
        """Will be back soonTM"""
        await ctx.send("Command will be back soon™")

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
                    logger.info(f'Deleted {dd} expired claim data from the db')
            except:
                pass
            await asyncio.sleep(86400 * 3)  # every 3 days

    @commands.check(checks.owner_check)
    @commands.command(hidden=True, aliases=["g_r"])
    async def g_roulette(self, ctx: Context, num_winners: int, msg_id: int, channel: discord.TextChannel,
                         num_options: int, lines_in_font: int = 0, role_for_extra: discord.Role = None,
                         num_of_extra_opts: int = 0):
        """Leggo 1. stuff 2. stuff [for b only]3. stuff extra
        Be sure that the roulette message's first line starts off with 1. right away.
        Or else just adjust lines_in_front.
        Always start extra options with one extra line before them!
        """
        if num_of_extra_opts != 0: num_of_extra_opts = num_of_extra_opts + num_options
        msg = await channel.fetch_message(msg_id)
        usrs = []
        for r in msg.reactions:
            async for user in r.users():
                usrs.append(user)
        usrs = list(set(usrs))
        u_all = [u for u in usrs]
        if role_for_extra:
            u_extra = [u for u in usrs if role_for_extra.id in u._roles]
            u_extra_minus = [u for u in usrs if role_for_extra.id not in u._roles]
        else:
            u_extra = u_all
            u_extra_minus = u_all
        only_one_type_extra = False
        only_one_type = False
        if not u_extra:
            only_one_type = True
            await ctx.send('No users with the extra role reacted to the message, defaulting to all users')
            u_extra = u_all
        if not u_extra_minus:
            only_one_type_extra = True
            await ctx.send('No users without the extra role reacted to the message, defaulting to all users')
            u_extra_minus = u_all

        random.shuffle(u_all)
        random.shuffle(u_extra)
        random.shuffle(u_extra_minus)

        a = msg.content.split('\n')
        options = [l for l in msg.content.split('\n')][lines_in_font:num_options + lines_in_font]
        options_extra = [l for l in msg.content.split('\n')][
                        (num_options + 1 + lines_in_font):num_of_extra_opts + lines_in_font]
        options_both = options + options_extra

        if len(u_all) < num_winners: return await ctx.send(f"Max num winners should be **{len(u_all)}**")

        rets_o = []
        rets_u = []
        if only_one_type:
            for i in range(num_winners): rets_o.append(random.choice(options))
            rets_u.extend(u_extra_minus[:num_winners])
        elif only_one_type_extra:
            for i in range(num_winners): rets_o.append(random.choice(options_both))
            rets_u.extend(u_extra[:num_winners])
        else:
            i_e = 0
            i_reg = 0
            i = num_winners
            while True:
                u_ = random.choice(u_all)
                if (u_ in u_extra and role_for_extra) and i_e < len(u_extra):
                    rets_o.append(random.choice(options_both))
                    rets_u.append(u_extra[i_e])
                    i_e += 1
                    i -= 1
                elif (u_ in u_extra_minus or not role_for_extra) and i_reg < len(u_extra_minus):
                    rets_o.append(random.choice(options))
                    rets_u.append(u_extra_minus[i_reg])
                    i_reg += 1
                    i -= 1
                if (i_e == len(u_extra) and i_reg == len(u_extra_minus)) or i == 0: break

        await ctx.send("🎉 **TIME TO ROLL THE ROULETTE** 🎉")
        dr = await ctx.send("🥁 🥁 🥁 *que drumroll* 🥁 🥁 🥁")
        await asyncio.sleep(5)
        for i in range(len(rets_o)):
            await ctx.send(f"{rets_u[i].mention} has won ||{rets_o[i]}||")
            await asyncio.sleep(3)

        await dr.delete()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(hidden=True)
    async def cclaims(self, ctx: Context, claim_type: str, limit: int):
        CT = claim_type
        idd = ctx.author.id
        from discord import Embed
        from models.claims import Claimed, History
        h, _ = History.get_or_create(user=idd, type=CT)
        his = json.loads(h.meta)
        if not his: return await ctx.send("no history")
        hiss = {'last_3_claims': his['last_3_claims']}
        del his['last_3_claims']
        his = ({k: v for k, v in sorted(his.items(), key=lambda item: item[1], reverse=True)[:limit]})
        his['last_3_claims'] = hiss['last_3_claims']
        if not his['last_3_claims']: return await ctx.send(f"{ctx.author.mention} you have no claim history for the "
                                                           f"**{CT}** command")
        his['last_3_claims'][0] += ' (last claim)'
        color = None
        url = None
        usr = Claimed.select().where(Claimed.user == idd,
                                     Claimed.type == CT,
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
        desc = f"**Last 3 {CT} claims:**\n{aa}\n\n**Claim statistic:**\n{bb}"
        em = Embed(title=f"History for {ctx.author.display_name}", description=desc)
        if color:
            em.colour = color
            if url:
                em.set_thumbnail(url=url)
            else:
                em.set_footer(text=':warning: potentially nsfw pic claim thumbnail ignored')

        await ctx.channel.send(content=f'{ctx.author.mention} your {CT} claim history:', embed=em)


async def setup(
        bot: KanaIsTheBest
):
    ext = Fun(bot)
    bot.running_tasks.append(bot.loop.create_task(ext.delete_old_records()))
    await bot.add_cog(ext)
