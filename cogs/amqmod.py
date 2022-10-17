import asyncio
import datetime
import glob
import json
import logging
import os
import re
import subprocess
import traceback

import aiohttp
import discord
import requests
from discord import Embed
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils.checks as checks
import utils.discordUtils as dutils
from utils.dataIOa import dataIOa

logger = logging.getLogger(f"info")
error_logger = logging.getLogger(f"error")


def get_valid_filename(s):
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


class AmqMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ignored_ann_ids = [7429]
        self._gib_code = """```js\n
    // DONT FORGET TO UPDATE MAL FIRST BEFORE ENTERING EXPAND!!
    var copyToClipboard = str => {
    // https://www.30secondsofcode.org/js/s/copy-to-clipboard
    const el = document.createElement('textarea');
    el.value = str;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    const selected =
        document.getSelection().rangeCount > 0 ?
        document.getSelection().getRangeAt(0) :
        false;
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    if (selected) {
        document.getSelection().removeAllRanges();
        document.getSelection().addRange(selected);
    }
};

let ret_7 = []
let ret_4 = []
expandLibrary.questionListHandler.animeEntries.forEach(e => {
    let cont = false
    e.songList.forEach( s=> {
        if(s.versionStatus.open.catbox["mp3"] == 3 && (s.versionStatus.open.catbox[720] == 1 || s.versionStatus.open.catbox[480] == 1)) {
            if (s.versionStatus.open.catbox[720] == 1) {
                ret_7.push({"annID": s.animeId, "annSongId": s.annSongId, "songName": s.name, "artist": s.artist, "type": s.typeName, "link_7": s.videoExamples[720]})
            } else {
                ret_4.push({"annID": s.animeId, "annSongId": s.annSongId, "songName": s.name, "artist": s.artist, "type": s.typeName, "link_4": s.videoExamples[480]})
            }            
        }
    });
});
ret_7.push(...ret_4)
let ret7 = JSON.stringify(ret_7)
copyToClipboard(ret7)```
                """
        self.gib_code = """```js
// DONT FORGET TO UPDATE MAL FIRST BEFORE ENTERING EXPAND!!
var copyToClipboard=str=>{const el=document.createElement('textarea');el.value=str;el.setAttribute('readonly','');el.style.position='absolute';el.style.left='-9999px';document.body.appendChild(el);const selected=document.getSelection().rangeCount>0?document.getSelection().getRangeAt(0):!1;el.select();document.execCommand('copy');document.body.removeChild(el);if(selected){document.getSelection().removeAllRanges();document.getSelection().addRange(selected)}};let ret_7=[]
let ret_4=[]
expandLibrary.questionListHandler.animeEntries.forEach(e=>{let cont=!1
e.songList.forEach(s=>{if(s.versionStatus.open.catbox.mp3==3&&(s.versionStatus.open.catbox[720]==1||s.versionStatus.open.catbox[480]==1)){if(s.versionStatus.open.catbox[720]==1){ret_7.push({"annID":s.animeId,"annSongId":s.annSongId,"songName":s.name,"artist":s.artist,"type":s.typeName,"link_7":s.videoExamples[720]})}else{ret_4.push({"annID":s.animeId,"annSongId":s.annSongId,"songName":s.name,"artist":s.artist,"type":s.typeName,"link_4":s.videoExamples[480]})}}})});ret_7.push(...ret_4)
let ret7=JSON.stringify(ret_7)
copyToClipboard(ret7) ```
"""
        self.gib_code2 = """
// DONT FORGET TO UPDATE MAL FIRST BEFORE ENTERING EXPAND!!
var copyToClipboard=str=>{const el=document.createElement('textarea');el.value=str;el.setAttribute('readonly','');el.style.position='absolute';el.style.left='-9999px';document.body.appendChild(el);const selected=document.getSelection().rangeCount>0?document.getSelection().getRangeAt(0):!1;el.select();document.execCommand('copy');document.body.removeChild(el);if(selected){document.getSelection().removeAllRanges();document.getSelection().addRange(selected)}};let ret_7=[]
let ret_4=[]
expandLibrary.questionListHandler.animeEntries.forEach(e=>{let cont=!1
e.songList.forEach(s=>{if(s.versionStatus.open.catbox.mp3==3&&(s.versionStatus.open.catbox[720]==1||s.versionStatus.open.catbox[480]==1)){if(s.versionStatus.open.catbox[720]==1){ret_7.push({"annID":s.animeId,"annSongId":s.annSongId,"songName":s.name,"artist":s.artist,"type":s.typeName,"link_7":s.videoExamples[720]})}else{ret_4.push({"annID":s.animeId,"annSongId":s.annSongId,"songName":s.name,"artist":s.artist,"type":s.typeName,"link_4":s.videoExamples[480]})}}})});ret_7.push(...ret_4)
let ret7=JSON.stringify(ret_7)
return ret_7
"""

    @commands.check(checks.owner_check)
    @commands.command(aliases=['amqcleanup', 'amqc'])
    async def amqclean(self, ctx):
        """Empty uploaded_links and uploaded_name json files"""
        with open('data/_amq/uploaded_links.json', 'w') as f:
            f.write("[]")
        with open('data/_amq/uploaded_name.json', 'w') as f:
            f.write("[]")
        with open('data/_amq/toProcessNoMp3.json', 'w') as f:
            f.write("[]")
        with open('data/_amq/BACKUP_toProcessNoMp3.json', 'w') as f:
            f.write("[]")
        for f in glob.glob('tmp/amq/*.mp3'):
            os.remove(f)

        await ctx.send("Done. Jsons now empty. Removed all mp3 files from `tmp/amq/` too.")

    @commands.check(checks.manage_roles_check)
    @commands.cooldown(3, 5, commands.BucketType.user)
    @commands.command(aliases=['gr'])
    async def giveroles(self, ctx, *, role_and_users):
        """Use this command to give roles to users.
        Usage:
        `[p]gr @Slot1D4dj @User1 @User2 @User3`
        
        - Go to a public channel, like general or something and **first** ping the slot role
        - Then ping all members that are in that PR (__don't send the message tho__)
        - Press CTRL+A, CTRL+X to copy (cut) the message
        - Go to #bot-duingeon, do `[p]gr` *CTRL+V* and you're done


        THIS COMMAND CAN ONLY BE USED IN THE BOT-DUNGEON"""

        # first go to some channel and prepare a ping message of all users
        # copy that and add them to users
        # ping the role in role_to_give

        if ctx.guild.id != 920092394945384508 and ctx.channel.id != 920101901339602944:
            return await ctx.send("You can not use this command here")

        argv = role_and_users.split(" ")

        users = " ".join(argv[0:])

        ids = users.replace("><", "> <").replace("<@", "").replace("<@!", "").replace(">", "").replace("!", "").split(" ")

        role_to_give = argv[0]
        ret = ""

        r = discord.utils.get(ctx.guild.roles, id=int(role_to_give.replace("<@&", "").replace(">", "")))
        m = await ctx.channel.send("Giving roles")
        for u in ids:
            if not u or not u.isnumeric(): continue
            user = ctx.guild.get_member(int(u))
            if user:
                try:
                    await user.add_roles(r)
                    ret += f"Added {r} to {user.mention} ✅\n"
                except:
                    ret += f"FAILED to add {r} to {user.mention} ❌\n"
        try:
            await m.delete()
        except:
            pass

        await ctx.send(ret)
        
        

    @commands.check(checks.owner_check)
    @commands.command()
    async def amqmp3(self, ctx, start_from_page: int = -999, up_to_id: int = -999):
        """Crawl (start_from_page), parse (up_to_id) from #komugi & upload
        -1 -1 = Catbox process only
        -2 X = Skip table parse ; Parse messages up to including X, Skip MAL update
        X <-1 = Parse tables from page X ; Skip #Komugi parse and skip MAL update
        [] [] = Parse tables from page 1 ; Parse messages automatically, add to MAL
        X [] = Parse tables from page X ; Parse messages automatically, add to MAL
        -1 [] = Skip tables parse ; Parse messages automatically, add to MAL
        """
        try:
            options = Options()
            options.headless = False
            options.headless = True  # mainheadmainheadless
            options.add_argument('window-size=1920x1080')
            options.binary_location = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            c = r"A:\\Unsorted\\old-desktop-junk\\chromedriver_win32\\chromedriver.exe"
            driver = webdriver.Chrome(c, chrome_options=options)

            if start_from_page < 0 and start_from_page != -999:
                await ctx.send("🔸 Skipping crawl")
            else:
                await ctx.send("🔹 Starting crawl process")
                if start_from_page == -999:
                    start_from_page = 1
                await self.el_crawl(ctx, start_from_page, driver)
            if up_to_id < 0 and up_to_id != -999:
                await ctx.send("🔸 Skipping parse")
            else:
                doListUpdate = True
                if start_from_page < -1:
                    await ctx.send("🔸 Skipping adding to MAL")
                else:
                    await ctx.send("🔹 Starting to add shows to MAL")
                    doListUpdate = await self.el_mal(ctx, up_to_id, driver)

                if start_from_page < -1 and start_from_page != -444:
                    await ctx.send("🔸 Skipping list update process")
                else:
                    if doListUpdate:
                        await ctx.send("🔹 Starting list update process")
                        await self.el_get_no_mp3(ctx, driver)
                    else:
                        await ctx.send("🔸 Skipping list update process")

            await ctx.send("🔹 Starting catbox process")
            d_code = await self.el_catboxpls(ctx, True)
            if not d_code:
                return await ctx.send("🔸 Skipping final socket command (nothing new to add) (this also means "
                                      "the list wasn't reverted back to `kikimanox2`)")
            else:
                await ctx.send("🔹 Running the final socket command")
                await self.el_get_no_mp3(ctx, driver, True, d_code)

            await ctx.send(f'{ctx.author.mention} we are done!')
        except:
            await ctx.send(embed=Embed(description="Somethign odd went wrong [(maybe rate "
                                                   "limit on the login page?)](https://animemusicquiz.com/)"))
            await dutils.print_hastebin_or_file(ctx, f'```\n{traceback.format_exc()}```')
            traceback.print_exc()
            ctx.error_logger.error(traceback.format_exc())
        finally:
            try:
                driver.close()
            except:
                pass

    @commands.check(checks.owner_check)
    @commands.command()
    async def gibcode(self, ctx):
        """Get the code"""
        await ctx.send(self.gib_code)

    @commands.check(checks.owner_check)
    @commands.command()
    async def docrawl(self, ctx, start_from_page=1):
        """Crawl and map ann mal ids [RUN ONLY LOCALLY]"""
        await self.el_crawl(ctx, start_from_page)

    @commands.check(checks.owner_check)
    @commands.command()
    async def catboxpls(self, ctx):
        """testing"""
        await self.el_catboxpls(ctx)

    @commands.check(checks.owner_check)
    @commands.command(aliases=["pmmal"])
    async def parsemsgsandaddtomal(self, ctx, up_to_id: int):
        """From newest up to including the one"""
        await self.el_mal(ctx, up_to_id)

    async def add_anime_to_list(self, animeID: int, driver):
        try:
            try:
                driver.set_page_load_timeout(4)
                driver.get(f"https://myanimelist.net/anime/{animeID}")
            except:
                pass
            __ = WebDriverWait(driver, 5).until(
                expected_conditions.presence_of_element_located((By.ID, "myinfo_status")))
            ad = driver.find_element_by_xpath(
                """//*[@id="content"]/table/tbody/tr/td[2]/div[1]
                 /table/tbody/tr[1]/td/div[1]/div[1]/div[1]/div[2]/a[1]""")
            ad.click()
            return True
        except:
            return False
        finally:
            driver.set_page_load_timeout(60)

    @staticmethod
    async def get_anime_list_ids(username="kikimanox"):
        off = 0
        ret = ""
        while True:
            async with aiohttp.ClientSession() as session:
                await asyncio.sleep(0.5)
                async with session.get(
                        f"https://myanimelist.net/animelist/{username}/load.json?offset={off}&status=7") as r:
                    a = await r.text()
                    if a == '[]':
                        return ret
                    # return await r.text()
                    d = 0
                    ret += a
                    off += 300
        # return ret

    async def upload_file_to_catbox(self, file, ctx):
        # https://github.com/amq-script-project/AMQ-Scripts/blob/master/programs/old-expand-but-better/catbox.py
        origname = file
        if re.match(r"^.*\.webm$", file):
            mime_type = "video/webm"
            ext = ".webm"
        elif re.match(r"^.*\.mp3$", file):
            mime_type = "audio/mpeg"
            ext = ".mp3"
        else:
            return None

        payload = {'reqtype': 'fileupload', 'userhash': self.bot.config['CATBOX_USERHASH']}
        timestamp = str(int(datetime.datetime.now().timestamp()))
        file = "tmp/amq/tmp" + timestamp + ext
        os.rename(origname, file)  # fixes special character errors
        f = open(file, 'rb')
        files = {'fileToUpload': (file, f, mime_type)}
        # await ctx.send(f"Uploading **{origname}**")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.do_request, payload, files)
            was_ok = True
            if response.ok:
                await ctx.send(f"✅ {origname}: " + f'<{response.text}>')
                rett_2 = response.text
            else:
                await ctx.send(f"❌ {origname}:\n" + f'```\n{response.text}```')
                was_ok = False
                rett_2 = response.text
        except:
            was_ok = False
            rett_2 = traceback.format_exc()

        f.close()
        os.rename(file, origname)
        return was_ok, rett_2

    @staticmethod
    def do_request(p, f):
        return requests.post("https://catbox.moe/user/api.php", data=p, files=f)

    @staticmethod
    async def is_catbox_alive():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://catbox.moe/", headers={'user-agent': '"Mozilla/5.0 '
                                                                                     '(Windows NT 6.1; WOW64; '
                                                                                     'Trident/7.0; '
                                                                                     'rv:11.0) like Gecko"'}) as r:
                    if r.status == 200:
                        return True
                    else:
                        print('--Catbox not alive?')
                        print(r.status)
                        print('--Content:\n')
                        print(r.content)
                        print('--Reson:\n')
                        print(r.reason)
                        return False
        except:
            print('--Catbox not alive??')
            import ssl

            try:
                _create_unverified_https_context = ssl._create_unverified_context
            except AttributeError:
                # Legacy Python that doesn't verify HTTPS certificates by default
                pass
            else:
                # Handle target environment that doesn't support HTTPS verification
                ssl._create_default_https_context = _create_unverified_https_context
            traceback.print_exc()
            return False

    async def el_crawl(self, ctx, start_from_page: int, _driver=None):
        # if not await dutils.prompt(ctx, "Are you running this locally?"):
        #    return await ctx.send("Cancelled")
        await ctx.send("Starting to crawl")
        options = Options()
        options.headless = True
        options.add_argument('window-size=1920x1080')
        options.binary_location = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        c = r"A:\\Unsorted\\old-desktop-junk\\chromedriver_win32\\chromedriver.exe"
        if not _driver:
            driver = webdriver.Chrome(c, chrome_options=options)
        else:
            driver = _driver
        print('strating...')
        # driver.minimize_window()
        driver.get("https://animemusicquiz.com/?forceLogin=True")
        driver.implicitly_wait(10)
        eee = driver.find_element_by_xpath("""/html/body/div[1]/div/a""")
        eee.click()
        await asyncio.sleep(2)
        driver.implicitly_wait(3)

        for i in range(5):
            try:
                driver.get(f"https://animemusicquiz.com/")
                driver.find_element_by_xpath("""//*[@id="adminPage"]/div/table/tbody""")  # this is wrong btw
                break
            except:
                await asyncio.sleep(1)
                un = driver.find_element_by_xpath("""//*[@id="loginUsername"]""")
                un.click()
                un.send_keys(ctx.bot.config['AMQ_USERNAME'])

                pw = driver.find_element_by_xpath("""//*[@id="loginPassword"]""")
                pw.click()
                pw.send_keys(ctx.bot.config['AMQ_PASSWORD'])

                signIn = driver.find_element_by_xpath("""//*[@id="loginButton"]""")
                signIn.click()
                print("Login")
                await asyncio.sleep(1)
                bbreak = True
                try:
                    contLog = driver.find_element_by_xpath("""//*[@id="alreadyOnlineContinueButton"]""")
                    contLog.click()
                    break
                except:
                    pass
                try:
                    test = driver.find_element_by_xpath("""//*[@id="mpPlayButton"]""")
                except:
                    bbreak = False
                if bbreak:
                    break

        driver.implicitly_wait(10)
        driver.get(f"https://animemusicquiz.com/admin/fixIds?known=true&page=1")

        cur_data = dataIOa.load_json('data/_amq/annMal.json')

        lp = 0
        for i in range(start_from_page, 200):
            driver.get(f"https://animemusicquiz.com/admin/fixIds?known=true&page={i}")
            print(f"page {i}")
            await asyncio.sleep(0.3)
            lastPage = False
            try:
                driver.find_element_by_xpath("""//*[@id="adminPage"]/div/table/tbody/tr[2]""")
            except:
                lastPage = True
            if lastPage:
                print("Reached last page")
                break
            lp = i
            tbl2 = driver.find_elements_by_xpath("""//*[@id="adminPage"]/div/table/tbody/tr[position() > 1]""")
            for t in tbl2:
                mID = t.get_attribute("data-malid")
                aID = t.get_attribute("data-annid")
                # print(f'{aID} {t.text}')
                cur_data[str(aID)] = t.text

        dataIOa.save_json('data/_amq/annMal.json', cur_data)
        await ctx.send(f"Done. (Last page that worked was `{lp}` (for `docrawl`))")
        if not _driver:
            driver.close()

    async def el_mal(self, ctx, up_to_id: int, _driver=None):
        try:
            chid = 784815078041583638  # KOMUGI
            ch = ctx.guild.get_channel(chid)
            if not ch:
                return await ctx.send("Not in the right guild")
            if up_to_id != -999:
                up_to = await ch.fetch_message(up_to_id)
            else:
                up_to = None
                async for ms in ch.history(limit=None).filter(lambda mm: mm.author.id == 593889007750873138):
                    up_to = ms
                    if '⬆' in [str(r.emoji) for r in ms.reactions]:
                        await ctx.send(f"Id of last message: `{ms.id}` (next time you need to do `;amqmp3 -1 {ms.id}`")
                        break

            if not up_to:
                raise Exception("No messages found?")

            messages = await ch.history(limit=None,
                                        after=up_to.created_at - datetime.timedelta(microseconds=1)).flatten()

            await messages[0].add_reaction('⬇')
            await messages[-1].add_reaction('⬆')
            try:
                await messages[-1].pin()
            except:
                pass  # couldn't pin the pinned pin message

            await ctx.send(f"Fetching existing list for `{ctx.bot.config['MAL_USERNAME']}`")
            annToMal = dataIOa.load_json('data/_amq/annMal.json')
            my_list = await self.get_anime_list_ids()
            pattern = r"anime_id\":(\d+),"
            malIds = list(set(re.findall(pattern, my_list)))

            to_add_to_mall = []
            for m in messages:
                try:
                    cnts = m.content.split('\n')
                    aid = cnts[7].split('ID:** ')[-1]
                except:
                    continue  # probably pin message
                if aid not in annToMal:
                    await m.add_reaction('⚠')
                    await ctx.send(embed=Embed(description=f'[ANN **{aid}**]'
                                                           f'(https://www.animenewsnetwork.com/encyclopedia/'
                                                           f'anime.php?id={aid}) not in annToMal. '
                                                           f'Please run `docrawl PAGE_NUM` or add it manuallyy'))
                    continue
                mid = annToMal[aid].split(' ')[0]
                if mid not in malIds:
                    to_add_to_mall.append(mid)

            if not to_add_to_mall:
                await ctx.send("No new shows needed to be added ot MAL.")
                return False
            await ctx.send("There are shows to add. Starting adding process now.")
            options = Options()
            options.headless = True
            options.add_argument('window-size=1920x1080')
            options.binary_location = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            c = r"A:\\Unsorted\\old-desktop-junk\\chromedriver_win32\\chromedriver.exe"
            if not _driver:
                driver = webdriver.Chrome(c, chrome_options=options)
            else:
                driver = _driver
            print('strating...')
            didnt_work = []
            if to_add_to_mall:
                driver.set_page_load_timeout(8)
                try:
                    driver.get("https://myanimelist.net/login.php")
                except:
                    pass
                driver.set_page_load_timeout(60)
                driver.implicitly_wait(10)
                # https://selenium-python.readthedocs.io/waits.html

                try:
                    driver.find_element_by_xpath("""//*[@id="loginUserName"]""")
                except:
                    pass

                print("Got login page MAL")

                async def check_for_dmca_shiz():
                    driver.implicitly_wait(2)
                    try:
                        await asyncio.sleep(1)  # waiting a bit
                        privAgg = driver.find_element_by_xpath("""//*[@id="qc-cmp2-ui"]/div[2]/div/button[3]""")
                        privAgg.click()
                    except:
                        pass
                    try:
                        await asyncio.sleep(1)
                        reeee = driver.find_element_by_xpath("""//*[@id="gdpr-modal-bottom"]/div/div/div[2]/button""")
                        reeee.click()
                    except:
                        pass
                    driver.implicitly_wait(10)

                ded = 0
                exx = ""
                for pls in range(3):
                    try:
                        await asyncio.sleep(1)
                        await check_for_dmca_shiz()
                        un = driver.find_element_by_xpath("""//*[@id="loginUserName"]""")
                        un.click()
                        un.send_keys(Keys.CONTROL, "a")
                        un.clear()
                        un.send_keys(self.bot.config['MAL_USERNAME'])
                        await check_for_dmca_shiz()
                        pw = driver.find_element_by_xpath("""//*[@id="login-password"]""")
                        pw.click()
                        pw.send_keys(Keys.CONTROL, "a")
                        pw.clear()
                        pw.send_keys(self.bot.config['MAL_PASSWORD'])
                        await check_for_dmca_shiz()
                        signIn = driver.find_element_by_xpath("""//*[@id="dialog"]/tbody/tr/td/form/div/p[6]/input""")
                        signIn.click()
                        print("Clicked sign in on MAL")
                        await asyncio.sleep(3)
                        break
                    except:
                        driver.save_screenshot('tmp/NANDEKOREWA_ExceptionAtLogin.png')
                        ded += 1
                        exx = traceback.format_exc()
                        print("Trying again zzzzzzzzzzzzzzzzzz")
                        pass
                if ded == 3:
                    print(exx)
                    raise
                to_add_to_mall = list(set(to_add_to_mall))
                await check_for_dmca_shiz()
                for mid in to_add_to_mall:
                    ok = await self.add_anime_to_list(mid, driver)
                    if not ok:
                        didnt_work.append(f'<https://myanimelist.net/anime/{mid}>')
                        print(f'Failed to add {mid}')
                    else:
                        print(f'Added {mid}')
                    await asyncio.sleep(0.5)
                if not _driver:
                    driver.close()
            if didnt_work:
                driver.save_screenshot('tmp/NANDEKOREWA_DidntWork.png')
                jo = '\n'.join(didnt_work)
                await dutils.print_hastebin_or_file(ctx, f"These shows weren't added to mal for some reason:\n{jo}")
            else:
                await ctx.send("All parsed shows added to mal.\nIt's time for")
                if not _driver:
                    await ctx.send(self.gib_code)
                    # await ctx.send(f"copy the content to `toProcessNoMp3.json`\n"
                    #               f"then run `{dutils.bot_pfx_by_ctx(ctx)}catboxpls`")
            return True
        except:
            traceback.print_exc()
            await ctx.send("Something went wrong in el_mal!!")
            return False
            raise

    async def el_get_no_mp3(self, ctx, driver, just_last_invoke=False, d_scripts=None):
        driver.get("https://animemusicquiz.com/?forceLogin=True")
        driver.implicitly_wait(10)

        # in case I was logged out
        try:
            driver.implicitly_wait(5)
            try:
                eee = driver.find_element_by_xpath("""/html/body/div[1]/div/a""")
                eee.click()
            except:
                pass
            await asyncio.sleep(2)
            try:
                driver.find_element_by_xpath("""//*[@id="mpPlayButton"]""")
                isOK = True
            except:
                isOK = False
            if isOK:
                raise
            for i in range(5):
                try:
                    driver.get(f"https://animemusicquiz.com/?forceLogin=True")
                    driver.find_element_by_xpath("""//*[@id="mpPlayButton"]""")
                    break
                except:
                    await asyncio.sleep(1)
                    un = driver.find_element_by_xpath("""//*[@id="loginUsername"]""")
                    un.click()
                    un.send_keys(ctx.bot.config['AMQ_USERNAME'])

                    pw = driver.find_element_by_xpath("""//*[@id="loginPassword"]""")
                    pw.click()
                    pw.send_keys(ctx.bot.config['AMQ_PASSWORD'])

                    signIn = driver.find_element_by_xpath("""//*[@id="loginButton"]""")
                    signIn.click()
                    print("Login")
                    await asyncio.sleep(1)
                    bbreak = True
                    try:
                        contLog = driver.find_element_by_xpath("""//*[@id="alreadyOnlineContinueButton"]""")
                        contLog.click()
                        break
                    except:
                        pass
                    try:
                        test = driver.find_element_by_xpath("""//*[@id="mpPlayButton"]""")
                    except:
                        bbreak = False
                    if bbreak:
                        break
        except:
            pass

        if not just_last_invoke:
            driver.implicitly_wait(10)
            await asyncio.sleep(5)
            opt = driver.find_element_by_xpath("""//*[@id="optionGlyphIcon"]""")
            opt.click()
            await asyncio.sleep(2)
            sett = driver.find_element_by_xpath("""//*[@id="optionsContainer"]/ul/li[3]""")
            sett.click()
            mmm = driver.find_element_by_xpath("""//*[@id="settingModal"]/div/div/div[2]/div[2]""")
            mmm.click()
            mn = driver.find_element_by_xpath("""//*[@id="malUserNameInput"]""")
            mn.click()
            mn.send_keys(Keys.CONTROL, "a")
            mn.clear()
            mn.send_keys("kikimanox")
            getMal = driver.find_element_by_xpath("""//*[@id="malUpdateButton"]""")
            getMal.click()
            await ctx.send("Trying to update MAL")
            driver.implicitly_wait(90)
            succ = driver.find_element_by_xpath("""//*[@id="swal2-title"]""")
            print(succ.text)
            if succ.text == "Update Successful":
                await ctx.send("MAL Updated.")
            else:
                await ctx.send("MAL Update failed.")
                raise
            # kk = driver.find_element_by_xpath("""/html/body/div[4]/div/div[3]/button[1]""")
            # kk.click()
            # cls = driver.find_element_by_xpath("""//*[@id="settingModal"]/div/div/div[1]/div/button""")
            # cls.click()

        # GO TO EXPAND
        driver.get("https://animemusicquiz.com/?forceLogin=True")
        driver.implicitly_wait(30)
        ex = driver.find_element_by_xpath("""//*[@id="mpExpandButton"]""")
        ex.click()
        await asyncio.sleep(3)
        first = driver.find_element_by_xpath("""//*[@id="elQuestionList"]/div[4]/div[1]/div[1]""")

        if not just_last_invoke:
            stuff = driver.execute_script(self.gib_code2)
            # print(stuff)
            dataIOa.save_json('data/_amq/toProcessNoMp3.json', json.loads(json.dumps(stuff)))
            await ctx.send("Saved data to parse.")

        if just_last_invoke:
            await ctx.send("Invoking sockets.")

            i = 1
            for scr in d_scripts:
                val = driver.execute_script(scr)
                await ctx.send(f"[{i}/{len(d_scripts)}] Done. ({val} added)")
                i += 1

            try:
                await asyncio.sleep(2)
                opt = driver.find_element_by_xpath("""//*[@id="optionGlyphIcon"]""")
                opt.click()
                await asyncio.sleep(2)
                sett = driver.find_element_by_xpath("""//*[@id="optionsContainer"]/ul/li[3]""")
                sett.click()
                mmm = driver.find_element_by_xpath("""//*[@id="settingModal"]/div/div/div[2]/div[2]""")
                mmm.click()
                mn = driver.find_element_by_xpath("""//*[@id="malUserNameInput"]""")
                mn.click()
                mn.send_keys(Keys.CONTROL, "a")
                mn.clear()
                mn.send_keys("kikimanox2")
                getMal = driver.find_element_by_xpath("""//*[@id="malUpdateButton"]""")
                getMal.click()
                await ctx.send("Trying to update MAL back to kikimanox2")
                driver.implicitly_wait(60)
                succ = driver.find_element_by_xpath("""//*[@id="swal2-title"]""")
                # print(succ.text)
                if succ.text == "Updated Successful":
                    await ctx.send("MAL Updated.")
                else:
                    await ctx.send("MAL Update failed.")
            except:
                await ctx.send("Something went wrong when updagint MAL list back to kikimanox2")

    async def el_catboxpls(self, ctx, auto=False):
        rets = []
        ret = ""
        to_ret = """
        socket.sendCommand({
            type: "library",
            command: "expandLibrary answer",
            data: {
                annId: [ANNID],
                annSongId: [ANNSONGID],
                url: "[URL]",
                resolution: 0    
            }
        })
                """
        data = dataIOa.load_json('data/_amq/toProcessNoMp3.json')
        dataIOa.save_json('data/_amq/BACKUP_toProcessNoMp3.json', data)
        # print("Saving temporary data, you'll need this later (in case of a crash)"
        #      " in order to make the final output btw.")
        uploaded = dataIOa.load_json('data/_amq/uploaded_name.json')
        uploaded_l = dataIOa.load_json('data/_amq/uploaded_links.json')
        cnt = 0
        while len(data) > 0:
            upl = data.pop()
            if int(upl["annID"]) in self.ignored_ann_ids:
                continue
            loop = asyncio.get_event_loop()
            ll = 'link_7'
            if 'link_4' in upl:
                ll = 'link_4'

            ee = get_valid_filename(upl["songName"])
            out = f'tmp/amq/{upl["annID"]}_{upl["annSongId"]}_{ee}.mp3'

            if not os.path.exists(out) or (os.path.exists(out) and (out not in uploaded)):
                fil = upl[ll].replace('files.', 'nl.') # actually just use NL now that it's active
                await ctx.send(f"Creating **{out}** from <{fil}>")
                if os.path.exists(out):
                    os.remove(out)  # we go agane
                # fil = upl[ll]  # better safe than sorry zzzzzzzzzzzzzz
                # panic for no log basically | info
                LOGLEVEL = "panic"
                process = subprocess.Popen(
                    ["ffmpeg", "-hide_banner", "-loglevel", LOGLEVEL, "-i", fil,
                     "-b:a", "320k",
                     "-ac", "2", "-map", "a:0", out, "-y"],
                    stdout=subprocess.PIPE)
                await loop.run_in_executor(None, process.communicate)
                await asyncio.sleep(0.1)
                if not os.path.exists(out):
                    process = subprocess.Popen(
                        ["ffmpeg", "-hide_banner", "-loglevel", LOGLEVEL, "-i", fil, "-b:a", "320k",
                         "-ac", "2", "-map", "a:0", out, "-y"],
                        stdout=subprocess.PIPE)
                    await loop.run_in_executor(None, process.communicate)
                    await asyncio.sleep(0.1)

            feedback = True
            if out not in uploaded:
                if not await self.is_catbox_alive():
                    await ctx.send("❗❗Catbox ded rn. Continue later..")
                    raise
                await ctx.send(f"Uploading **{out}**")
                ok, link = await self.upload_file_to_catbox(out, ctx)
            else:
                feedback = False
                ok = True
                link = uploaded_l[uploaded.index(out)]
            link = str(link).replace('\n', '').replace(' ', '')
            if not ok:
                await ctx.send("Something went wrong... Details:")
                print(link)
                await dutils.print_hastebin_or_file(ctx, f'```\n{link}```')
                raise

            uploaded.append(out)
            uploaded_l.append(link)
            dataIOa.save_json('data/_amq/uploaded_name.json', uploaded)
            dataIOa.save_json('data/_amq/uploaded_links.json', uploaded_l)
            ret += to_ret.replace('[ANNID]', str(upl["annID"])).replace('[ANNSONGID]', str(upl["annSongId"])). \
                replace('[URL]', str(link)). \
                replace('socket.sendCommand(', '').replace('})', '}')
            if feedback:
                await ctx.send(to_ret.replace('[ANNID]', str(upl["annID"])).
                               replace('[ANNSONGID]', str(upl["annSongId"])).replace('[URL]', str(link)))
            if cnt < 20:
                ret += ','
                cnt += 1
            else:
                rets.append(ret)
                ret = ""
                cnt = 0
            if len(data) == 0 and ret:
                rets.append(ret)

            # dataIOa.save_json('data/_amq/toProcessNoMp3.json', data)  # NVM: wait why do you keep overwriting this?

        # await ctx.send("""```js
        # socket.sendCommand({
        #    type: "library",
        #    command: "expandLibrary questions"
        # })
        #        ```""")
        LB = "{"
        RB = "}"
        if not auto:
            await ctx.send(f"{ctx.author.mention} **All:**")

        deff = """function _sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }"""
        rr = "{socket.sendCommand(ex[ii]);\nconsole.log(ex[ii]);\nawait _sleep(700);}"
        rett = []
        for r in rets:
            rett.append(f'{deff}\n\nvar ex=[{r}]\nasync '
                        f'function doIT(){LB}for(let ii=0;ii<ex.length;ii++){LB}{rr}{RB}return ex.length;{RB}'
                        f'\nreturn await doIT();')
        if rett:
            await dutils.print_hastebin_or_file(ctx, '\n'.join(rett), just_file=True)  # for some reason hastebin sux
        return rett


async def setup(
        bot: commands.Bot
):
    ext = AmqMod(bot)
    await bot.add_cog(ext)
