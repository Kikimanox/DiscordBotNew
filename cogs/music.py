import logging
import os
import asyncio
import re
import subprocess
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import shlex
import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio, Embed
import yt_dlp
import shutil
from fuzzywuzzy import fuzz, process
import threading
from utils import checks
from utils.SimplePaginator import SimplePaginator

logger = logging.getLogger(f"info")
error_logger = logging.getLogger(f"error")


class CustomFFmpegPCMAudio(FFmpegPCMAudio):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None
        self.total_paused_time = 0
        self.last_pause_time = None


def run_coroutine_in_new_loop(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coroutine)
    loop.close()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tmp_folder = "tmp"
        self.queues = {}
        self.voice_clients = {}
        # self.check_queue.start()
        self.cleanup_tmp_folder()

    def get_song_path(self, guild_id):
        return f"{self.tmp_folder}/music_{guild_id}"

    def cleanup_tmp_folder(self):
        tmp_path = os.path.join(os.getcwd(), self.tmp_folder)
        if os.path.exists(tmp_path):
            for folder in os.listdir(tmp_path):
                if folder.startswith('music_'):
                    folder_path = os.path.join(tmp_path, folder)
                    shutil.rmtree(folder_path)

    async def dc_from_vc(self, gid):
        try:
            voice_client = self.voice_clients.get(gid)
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
        except:
            pass

    async def play_next_song(self, guild_id, start_time=None):
        voice_client = self.voice_clients[guild_id]
        if (guild_id in self.queues and len(self.queues[guild_id]) > 0 and not (
                voice_client.is_playing() or voice_client.is_paused())) or (start_time and voice_client.is_paused()):
            song_path = self.queues[guild_id][0]["local_path"]

            # Get the audio change value
            logger.info(f"Adjusting volume for {song_path}")
            audio_change = await self.adjust_volume(song_path)
            logger.info(f"Audio change for {song_path} was {audio_change}")
            # audio_change = 0

            # Add the volume change to the FFmpeg options
            options = f'-vn -b:a 320k -af volume={audio_change}dB'
            before_options = ""
            if start_time:
                before_options += f'-ss {start_time}'

            # options = options.split(' ')
            source = CustomFFmpegPCMAudio(song_path, options=options, before_options=before_options)
            if guild_id not in self.voice_clients:
                self.queues.pop(guild_id, None)
                return

            # Play the audio with the adjusted volume
            voice_client.play(source, after=lambda error: threading.Thread(target=run_coroutine_in_new_loop, args=(
                self.song_finished_playing(guild_id, song_path, error),)).start())
            voice_client.source.start_time = discord.utils.utcnow()  # Store start time
            if start_time:
                source.start_time = discord.utils.utcnow() - timedelta(seconds=int(start_time))
        else:
            await self.dc_from_vc(guild_id)

    async def song_finished_playing(self, guild_id, song_path, error=None):
        if error:
            print(f"Error while playing song: {error}")

        # Delay the deletion of the file
        loop = asyncio.get_running_loop()
        loop.call_later(10, self.delete_song_file, guild_id, song_path)

        if self.queues[guild_id]:  # Check if the list is not empty
            self.queues[guild_id].pop(0)
            loop.create_task(self.play_next_song(guild_id))
        if not self.queues[guild_id]:
            await self.dc_from_vc(guild_id)

    def delete_song_file(self, guild_id, song_path):
        try:
            os.remove(song_path)
            print(f"Deleted file: {song_path}")
        except Exception as e:
            print(f"Error deleting file: {song_path}\n{e}")

    async def download_song(self, url, guild_id, playlist=False):
        ydl_opts = {
            'format': '251/250/bestaudio',  # Opus format
            'outtmpl': f"{self.get_song_path(guild_id)}/{int(time.time())}.%(ext)s",
            "noplaylist": not playlist,  # Handle playlists
            "source_address": "0.0.0.0",  # For IPv6 issues
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '320k',
            }],
            'quiet': True,
            'no_warnings': True
            # 'verbose': True
        }

        loop = asyncio.get_event_loop()

        def _download_song_blocking():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if playlist and info.get('entries') and len(info.get('entries')):
                        entries = info['entries']
                        if len(entries) > 10:
                            raise Exception("Playlist is too long. [Max 10 songs]")

                        song_paths = []
                        for entry in entries:
                            if entry.get("duration") and entry["duration"] > 10800:  # 3 hours
                                raise Exception("Song is too long. [Max 3 hours]")
                            info_entry = ydl.extract_info(entry['url'], download=True)
                            filename = 'tmp' + ''.join(
                                info_entry.get('requested_downloads')[0].get('filepath').split('tmp')[1:])
                            song_paths.append(filename)

                        return song_paths, entries

                    if info.get("duration") and info["duration"] > 10800:  # 3 hours
                        raise Exception("Song is too long. [Max 3 hours]")

                    info = ydl.extract_info(url, download=True)
                    if info.get('entries'):
                        info_entry0 = info['entries'][0]
                    else:
                        info_entry0 = info
                    filename = 'tmp' + ''.join(
                        info_entry0.get('requested_downloads')[0].get('filepath').split('tmp')[1:])
                    return filename, info

            except Exception as ex:
                raise Exception(ex)

        try:
            return await loop.run_in_executor(None, _download_song_blocking)
        except Exception as ex:
            raise Exception(ex)

    @commands.cooldown(1, 25, commands.BucketType.user)
    @commands.command(aliases=['pm'])
    async def playmultiple(self, ctx, *, query):
        """
        Add multiple songs to the queue (delimiter: `|`)
        Example:
        `[p]playmultiple epic sax guy | Bakemonogatari OP5 | PEbD3rIvais`
        """
        queries = [q.strip() for q in query.split('|')]
        if len(queries) > 5:
            return await ctx.send("Max 5 songs can be added at once.")
        for q in queries:
            await self.play(ctx, query=q)
            await asyncio.sleep(2)

    def cleaned_query(self, query):
        # Remove "<" from the start and ">" from the end, if present
        if query.startswith("<"):
            query = query[1:]
        if query.endswith(">"):
            query = query[:-1]

        # Remove "||" from the start and the end, if present
        if query.startswith("||"):
            query = query[2:]
        if query.endswith("||"):
            query = query[:-2]

        if query.startswith("||<"):
            query = query[3:]
        if query.endswith(">||"):
            query = query[:-3]

        return query

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.command(aliases=['p', 'enque'])
    async def play(self, ctx, *, query):
        """
        Add song to the playing queue. Input can be yt link/id or search string.
        Examples:
        `[p]play epic sax guy`
        `[p]play https://www.youtube.com/watch?v=04kMy7HhWtQ`
        `[p]play PEbD3rIvais` (<--- youtube id)

        """
        # Check if user is in a voice channel
        if ctx.author.voice is None:
            await ctx.send("You must be in a voice channel to use this command.")
            return

        query = self.cleaned_query(query)

        # Connect to the voice channel if not connected
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_connected():
            voice_channel = ctx.author.voice.channel
            self.voice_clients[ctx.guild.id] = await voice_channel.connect(self_deaf=True)

        # Download the song and store its info
        async with ctx.typing():
            m = await ctx.send(f"🔃 Adding `{query}` to the queue...".replace('@', '@\u200b'))

            try:
                song_path = None
                if "youtube.com" in query or "youtu.be" in query or len(query) == 11:
                    # If it's a link or ID, pass it directly to the download_song function
                    try:
                        song_path, info = await self.download_song(query, ctx.guild.id)
                    except:
                        song_path = None
                        pass
                if song_path is None:
                    await m.edit(content=f"🔎 Adding `{query}` to the queue..."
                                         f"\nProvided query was not a youtube id or link. Trying search..."
                                 .replace('@', '@\u200b'))
                    # Otherwise, search for the song using yt-dlp
                    search_query = f"ytsearch1:{query}"
                    song_path, info = await self.download_song(search_query, ctx.guild.id)
                    if info.get('entries') and len(info.get('entries')):
                        info = info['entries'][0]  # first one
                    else:
                        raise Exception("Nothing found")

                    # Perform fuzzy search to correct typos in the query
                    song_title = f'{info.get("title")} by {info.get("artist")}'
                    title_conbos = [song_title, info.get('title'), info.get('description'), info.get('artist')]
                    best_match = process.extractOne(query, title_conbos, scorer=fuzz.token_set_ratio)
                    if best_match[1] < 50:  # Threshold for fuzzy search
                        await m.edit(content=f"❌ Could not find anything for `{query}`.")
                        return

                if info.get("artist"):
                    song_title = f'{info.get("title")} by {info.get("artist")}'
                else:
                    song_title = f'{info.get("title")}'

                if ctx.guild.id not in self.queues:
                    self.queues[ctx.guild.id] = []

                if ctx.guild.id not in self.voice_clients:
                    self.queues.pop(ctx.guild.id, None)
                    return await ctx.send("Bot left vc before song could be added.")

                self.queues[ctx.guild.id].append({
                    "title": song_title,
                    "thumbnail": info['thumbnail'],
                    "url": info['webpage_url'],
                    "duration": info['duration'],
                    "requester": ctx.author,
                    "song_title": song_title,
                    "local_path": song_path
                })

                await self.play_next_song(ctx.guild.id)

                # await m.edit(content=f"✅ Added `{song_title}` to the queue.".replace('@', '@\u200b'))
                em = Embed(color=discord.Color.green(),
                           description=f"✅ Added [**{song_title}**]({info['webpage_url']})"
                                       f" to the queue.".replace('@', '@\u200b'))
                em.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
                await m.edit(content="", embed=em)

            except Exception as ex:
                # print(ex)
                error_logger.error(f"❌ Failed to add `{query}` to queue: {ex}")
                await m.edit(content=f"❌ Failed to add `{query}` to queue. Try again maybe?".replace('@', '@\u200b'))

    @commands.check(checks.owner_check)
    @commands.command(aliases=['pp'])
    async def playplaylist(self, ctx, *, query):
        """
        Same as play but only accepts playlist links/ids
        Currently not enabled publicly
        """
        # Check if user is in a voice channel
        if ctx.author.voice is None:
            await ctx.send("You must be in a voice channel to use this command.")
            return

        # Connect to the voice channel if not connected
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_connected():
            voice_channel = ctx.author.voice.channel
            self.voice_clients[ctx.guild.id] = await voice_channel.connect(self_deaf=True)

        # Download the songs and store their info
        async with ctx.typing():
            m = await ctx.send(f"🔃 Adding `{query}` playlist to queue...".replace('@', '@\u200b'))

            try:
                song_paths, info_entries = await self.download_song(query, ctx.guild.id, playlist=True)

                for song_path, info in zip(song_paths, info_entries):
                    song_title = f'{info.get("title")} by {info.get("artist")}'

                    if ctx.guild.id not in self.queues:
                        self.queues[ctx.guild.id] = []

                    self.queues[ctx.guild.id].append({
                        "title": song_title,
                        "thumbnail": info['thumbnail'],
                        "url": info['webpage_url'],
                        "duration": info['duration'],
                        "requester": ctx.author,
                        "song_title": song_title,
                        "local_path": song_path
                    })

                    await m.edit(content=f"✅ Added `{song_title}` to queue.".replace('@', '@\u200b'))
                await self.play_next_song(ctx.guild.id)

            except Exception as ex:
                await m.edit(content=f"❌ Failed to add `{query}` playlist to queue.".replace('@', '@\u200b'))
                print(ex)

    @commands.command(aliases=['que'])
    async def queue(self, ctx):
        """
        Check the current queue/order of songs.
        """
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) == 0:
            await ctx.send("The queue is empty.")
            return

        queue_embeds = []
        current_embed = discord.Embed(title="Song queue", color=discord.Color.blue())
        current_length = 0

        for idx, song_info in enumerate(self.queues[ctx.guild.id]):
            song_title = song_info["song_title"]
            song_title_length = len(song_title)

            if idx == 0:
                if self.voice_clients[ctx.guild.id].is_paused():
                    song_title = f"[🎵 (paused)] {song_title}"
                else:
                    song_title = f"[🎵] {song_title}"
                current_embed.add_field(name=f"{idx + 1}. {song_title}",
                                        value=f"[requested by: {song_info['requester'].mention}]",
                                        inline=False)
            else:
                if current_length + song_title_length > 500:
                    queue_embeds.append(current_embed)
                    current_embed = discord.Embed(title="Queue", color=discord.Color.blue())
                    current_length = 0

                current_embed.add_field(name=f"{idx + 1}. {song_title}",
                                        value=f"[requested by: {song_info['requester'].mention}]",
                                        inline=False)
            current_length += song_title_length

        queue_embeds.append(current_embed)

        await SimplePaginator(extras=queue_embeds).paginate(ctx)

    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.check(checks.owner_check)
    @commands.command()
    async def stop(self, ctx):
        """
        Stops music playback in this channel. Will purge the queue too.
        """
        if ctx.guild.id not in self.voice_clients:
            await ctx.send("The bot is not in a voice channel.")
            return

        self.voice_clients[ctx.guild.id].stop()
        self.queues[ctx.guild.id] = []
        await self.voice_clients[ctx.guild.id].disconnect()
        self.voice_clients.pop(ctx.guild.id, None)
        await ctx.send("Stopped")

    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command()
    async def pause(self, ctx):
        """
        Pause currenty playback. Will not purge queue.
        """
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_playing():
            await ctx.send("There is no song currently playing.")
            return

        voice_client = self.voice_clients[ctx.guild.id]
        voice_client.pause()
        voice_client.source.last_pause_time = discord.utils.utcnow()
        await ctx.send("Paused")

    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command()
    async def resume(self, ctx):
        """
        Resume song if paused.
        """
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_paused():
            await ctx.send("No song is currently paused.")
            return

        voice_client = self.voice_clients[ctx.guild.id]
        source = voice_client.source
        if source.last_pause_time:
            source.total_paused_time = 0
            source.last_pause_time = None

        voice_client.resume()
        await ctx.send("Resumed")

    @commands.cooldown(1, 20, commands.BucketType.guild)
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.command()
    async def seek(self, ctx, time_str):
        """
        Seek to a specific position in the current song.
        Format: `[p]seek MM:SS`
        """
        # Check if a song is currently playing
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_playing():
            await ctx.send("There is no song currently playing.")
            return

        # Convert time_str (MM:SS) to seconds
        try:
            minutes, seconds = time_str.split(':')
            seek_time = int(minutes) * 60 + int(seconds)
        except ValueError:
            await ctx.send("Invalid time format. Please use MM:SS format.")
            return

        song = self.queues[ctx.guild.id][0]
        if seek_time < 0 or seek_time >= song['duration'] - 2:
            await ctx.send("Invalid seek time. Please provide a time within the song's duration.")
            return

        # Pause the current playback
        self.voice_clients[ctx.guild.id].pause()

        # Play the song from the specified position
        await self.play_next_song(ctx.guild.id, start_time=f'{seek_time}')
        await ctx.send(f"Seeking to {time_str}.".replace('@', '@\u200b'))
        await self.playing(ctx)

    @commands.command()
    async def skip(self, ctx):
        """
        Skip currently playing song.
        """
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_playing():
            await ctx.send("There is no song currently playing.")
            return

        voice_client = self.voice_clients[ctx.guild.id]
        voice_client.stop()

        # Check if there are any songs in the queue before accessing the first element
        if self.queues[ctx.guild.id]:
            await self.song_finished_playing(ctx.guild.id, self.queues[ctx.guild.id][0]["local_path"])

        # Check if it was the last song in the queue
        if not self.queues[ctx.guild.id]:
            await ctx.send(f"{ctx.author.mention} skipped last song. Goodbye.")
        else:
            await ctx.send(f"{ctx.author.mention} skipped to the next song.")

    @commands.command(aliases=['np', 'nowplaying'])
    async def playing(self, ctx):
        """
        Check currently playing song info
        """
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) == 0:
            await ctx.send("No song is currently playing.")
            return

        song = self.queues[ctx.guild.id][0]  # Get the currently playing song
        embed = discord.Embed(title=song["title"], url=song["url"], color=discord.Color.blue())
        embed.set_author(name=f'Requested by: {song["requester"].display_name}',
                         icon_url=song["requester"].display_avatar.url)
        embed.set_thumbnail(url=song["thumbnail"])

        voice_client = self.voice_clients[ctx.guild.id]
        source = voice_client.source
        if source.last_pause_time:
            source.total_paused_time = (discord.utils.utcnow() - source.last_pause_time).total_seconds()
        elapsed_time = (discord.utils.utcnow() - source.start_time).total_seconds() - source.total_paused_time

        # Create a progress bar for the song's duration
        progress_bar = self.create_progress_bar(elapsed_time, song["duration"], 20)

        # Format elapsed time and duration in mm:ss format
        elapsed_str = f"{int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}"
        duration_str = f"{int(song['duration'] // 60)}:{int(song['duration'] % 60):02d}"

        embed.add_field(name="Progress", value=f"{progress_bar}\n{elapsed_str} / {duration_str}",
                        inline=False)

        await ctx.send(embed=embed)

    def create_progress_bar(self, progress, total, length):
        filled_length = int(length * progress // total)
        bar = '▰' * filled_length + '▱' * (length - filled_length)
        return bar

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Check if the bot got disconnected from a voice channel
        if member.id == self.bot.user.id and before.channel and not after.channel:
            guild_id = before.channel.guild.id
            # Clear the queue and song info for the guild
            self.queues.pop(guild_id, None)

    async def adjust_volume(self, audio):
        def get_audio_change(audio):
            try:
                maxpeak, maxmean = -1, -12.0  # people can adjust the volume on their own on the actual bot
                findaudiomean = re.compile(
                    r"\[Parsed_volumedetect_\d+ @ [0-9a-zA-Z]+\] " + r"mean_volume: (\-?\d+\.\d) dB")
                findaudiopeak = re.compile(
                    r"\[Parsed_volumedetect_\d+ @ [0-9a-zA-Z]+\] " + r"max_volume: (\-?\d+\.\d) dB")
                audiochange, peak, mean = 0.0, 0.0, 0.0

                while peak > maxpeak or mean > maxmean:
                    command = f'ffmpeg -loglevel info -t 360 -i {audio} -vn -ac 2 -map 0:a:0 -af ' \
                              f'"volume={audiochange}dB:precision=fixed,volumedetect" -sn ' \
                              f'-hide_banner -nostats -max_muxing_queue_size 4096 -f null -'
                    process = subprocess.run(command, stderr=subprocess.PIPE, shell=True)
                    string = str(process.stderr.decode())
                    mean, peak = float(findaudiomean.search(string).group(1)), float(
                        findaudiopeak.search(string).group(1))
                    audiochange += -10.0 if peak == 0.0 else min(maxpeak - peak, maxmean - mean)

                return round(audiochange, 1)  # .1 precision
            except Exception as ex:
                error_logger.error(f"Exception in adjust_volume: {ex} | {traceback.print_exc()}")
                return 0

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, get_audio_change, audio)


async def setup(bot: commands.Bot):
    ext = Music(bot)
    await bot.add_cog(ext)
