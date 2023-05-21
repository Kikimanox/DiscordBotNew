from __future__ import annotations
from typing import TYPE_CHECKING

import os
import asyncio
import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio
import yt_dlp
import shutil
from fuzzywuzzy import fuzz, process
import threading
from utils import checks
from utils.SimplePaginator import SimplePaginator

if TYPE_CHECKING:
    from bot import KanaIsTheBest
    from utils.context import Context


def run_coroutine_in_new_loop(coroutine):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coroutine)
    loop.close()


class Music(commands.Cog):
    def __init__(
            self,
            bot: KanaIsTheBest
    ):
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

    async def play_next_song(self, guild_id):
        # for guild_id in self.queues:
        voice_client = self.voice_clients[guild_id]
        if len(self.queues[guild_id]) > 0 and not (voice_client.is_playing() or voice_client.is_paused()):
            song_path = self.queues[guild_id][0]["local_path"]
            source = FFmpegPCMAudio(song_path, options='-vn')
            voice_client.play(source, after=lambda error: threading.Thread(target=run_coroutine_in_new_loop, args=(
                self.song_finished_playing(guild_id, song_path, error),)).start())
            voice_client.source.start_time = discord.utils.utcnow()  # Store start time

    async def song_finished_playing(self, guild_id, song_path, error=None):
        if error:
            print(f"Error while playing song: {error}")

        # Delay the deletion of the file
        loop = asyncio.get_running_loop()
        loop.call_later(10, self.delete_song_file, guild_id, song_path)

        if self.queues[guild_id]:  # Check if the list is not empty
            self.queues[guild_id].pop(0)
            loop.create_task(self.play_next_song(guild_id))

    def delete_song_file(self, guild_id, song_path):
        try:
            os.remove(song_path)
            print(f"Deleted file: {song_path}")
        except Exception as e:
            print(f"Error deleting file: {song_path}\n{e}")

    async def download_song(self, url, guild_id, playlist=False):
        ydl_opts = {
            'format': '251/250/bestaudio',  # Opus format
            'outtmpl': f"{self.get_song_path(guild_id)}/%(title)s.%(ext)s",
            "noplaylist": not playlist,  # Handle playlists
            "source_address": "0.0.0.0",  # For IPv6 issues
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '320',
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
                            filename = os.path.join(self.get_song_path(guild_id), f"{entry['title']}.opus")
                            song_paths.append(filename)

                        return song_paths, entries

                    if info.get("duration") and info["duration"] > 10800:  # 3 hours
                        raise Exception("Song is too long. [Max 3 hours]")

                    info = ydl.extract_info(url, download=True)
                    if info.get('entries'):
                        info_entry0 = info['entries'][0]
                    else:
                        info_entry0 = info
                    filename = os.path.join(self.get_song_path(guild_id), f"{info_entry0['title']}.opus")
                    return filename, info

            except Exception as ex:
                raise Exception(ex)

        try:
            return await loop.run_in_executor(None, _download_song_blocking)
        except Exception as ex:
            raise Exception(ex)

    @commands.check(checks.owner_check)
    @commands.command(aliases=['pm'])
    async def playmultiple(self, ctx: Context, *, query):
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

    @commands.check(checks.owner_check)
    @commands.command(aliases=['p', 'enque'])
    async def play(self, ctx: Context, *, query):
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

        # Connect to the voice channel if not connected
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_connected():
            voice_channel = ctx.author.voice.channel
            self.voice_clients[ctx.guild.id] = await voice_channel.connect(self_deaf=True)

        # Download the song and store its info
        async with ctx.typing():
            m = await ctx.send(f"🔃 Adding `{query}` to queue...".replace('@', '@\u200b'))

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
                    await m.edit(content=f"🔎 Adding `{query}` to queue..."
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
                print(ex)
                await m.edit(content=f"❌ Failed to add `{query}` to queue.".replace('@', '@\u200b'))

    @commands.check(checks.owner_check)
    @commands.command(aliases=['pp'])
    async def playplaylist(self, ctx: Context, *, query):
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

    @commands.check(checks.owner_check)
    @commands.command(aliases=['que'])
    async def queue(self, ctx: Context):
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

    @commands.check(checks.owner_check)
    @commands.command()
    async def stop(self, ctx: Context):
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

    @commands.check(checks.owner_check)
    @commands.command()
    async def pause(self, ctx: Context):
        """
        Pause currenty playback. Will not purge queue.
        """
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_playing():
            await ctx.send("There is no song currently playing.")
            return

        self.voice_clients[ctx.guild.id].pause()

    @commands.check(checks.owner_check)
    @commands.command()
    async def resume(self, ctx: Context):
        """
        Resume song if paused.
        """
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_paused():
            await ctx.send("There is no song currently paused.")
            return

        self.voice_clients[ctx.guild.id].resume()

    @commands.check(checks.owner_check)
    @commands.command()
    async def skip(self, ctx: Context):
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
            await ctx.send("Skipped last song. Goodbye.")
        else:
            await ctx.send("Skipping to the next song.")

    @commands.check(checks.owner_check)
    @commands.command(aliases=['np', 'nowplaying'])
    async def playing(self, ctx: Context):
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

        # Calculate elapsed time since the song started playing
        elapsed_time = (discord.utils.utcnow() - self.voice_clients[ctx.guild.id].source.start_time).total_seconds()

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


async def setup(bot: KanaIsTheBest):
    ext = Music(bot)
    await bot.add_cog(ext)
