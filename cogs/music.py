import os
import asyncio
import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio
import yt_dlp
import shutil
from fuzzywuzzy import fuzz, process

from utils.SimplePaginator import SimplePaginator


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tmp_folder = "tmp"
        self.queues = {}
        self.song_info = {}
        self.voice_clients = {}
        self.check_queue.start()
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

    def delete_song_file(self, guild_id, song_path):
        try:
            os.remove(song_path)
            print(f"Deleted file: {song_path}")
        except Exception as e:
            print(f"Error deleting file: {song_path}\n{e}")

    async def download_song(self, url, guild_id):
        ydl_opts = {
            'format': '251',  # Opus format
            'outtmpl': f"{self.get_song_path(guild_id)}/%(title)s.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = os.path.join(self.get_song_path(guild_id), f"{info['title']}.opus")
                return filename, info
        except Exception as ex:
            raise Exception(ex)

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query):
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
            m = await ctx.send(f"🔃 Adding `{query}` to que...".replace('@', '@\u200b'))

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
                    await m.edit(content=f"🔎 Adding `{query}` to que..."
                                         f"\nProvided query was not a youtube id or link. Trying search..."
                                 .replace('@', '@\u200b'))
                    # Otherwise, search for the song using yt-dlp
                    search_query = f"ytsearch1:{query}"
                    song_path, info = await self.download_song(search_query, ctx.guild.id)
                    if len(info.get('entries')):
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
                song_path = song_path.replace('.webm', '.opus')
                self.song_info[ctx.guild.id] = {
                    "title": song_title,
                    "thumbnail": info['thumbnail'],
                    "url": info['webpage_url'],
                    "duration": info['duration'],
                    "requester": ctx.author
                }
                await m.edit(content=f"✅ Added `{song_title}` to que.".replace('@', '@\u200b'))
                # Add the song to the queue
                if ctx.guild.id not in self.queues:
                    self.queues[ctx.guild.id] = []

                self.queues[ctx.guild.id].append(song_path)
            except Exception as ex:
                await m.edit(content=f"❌ Failed to add `{song_title}` to que. [Ex: {ex}]".replace('@', '@\u200b'))

    @tasks.loop(seconds=1)
    async def check_queue(self):
        for guild_id in self.queues:
            if len(self.queues[guild_id]) > 0 and not self.voice_clients[guild_id].is_playing():
                song_path = self.queues[guild_id].pop(0)
                source = FFmpegPCMAudio(song_path, options='-vn')
                self.voice_clients[guild_id].play(source,
                                                  after=lambda error: self.delete_song_file(guild_id, song_path))
                self.voice_clients[guild_id].source.start_time = discord.utils.utcnow()  # Store start time

    @commands.command()
    async def queue(self, ctx):
        if ctx.guild.id not in self.queues or len(self.queues[ctx.guild.id]) == 0:
            await ctx.send("The queue is empty.")
            return

        queue_embeds = []
        current_embed = discord.Embed(title="Queue", color=discord.Color.blue())
        current_length = 0

        for idx, song_path in enumerate(self.queues[ctx.guild.id]):
            song_title = os.path.splitext(os.path.basename(song_path))[0]
            song_length = len(song_title)
            if current_length + song_length > 500:
                queue_embeds.append(current_embed)
                current_embed = discord.Embed(title="Queue", color=discord.Color.blue())
                current_length = 0

            current_embed.add_field(name=f"{idx + 1}.",
                                    value=f"{song_title} [requested by: {self.song_info[ctx.guild.id]['requester'].display_name}]",
                                    inline=False)
            current_length += song_length

        queue_embeds.append(current_embed)

        await SimplePaginator(extras=queue_embeds).paginate(ctx)

    @commands.command()
    async def stop(self, ctx):
        if ctx.guild.id not in self.voice_clients:
            await ctx.send("The bot is not in a voice channel.")
            return

        self.voice_clients[ctx.guild.id].stop()
        self.queues[ctx.guild.id] = []
        self.song_info.pop(ctx.guild.id, None)
        await self.voice_clients[ctx.guild.id].disconnect()
        self.voice_clients.pop(ctx.guild.id, None)

    @commands.command()
    async def pause(self, ctx):
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_playing():
            await ctx.send("There is no song currently playing.")
            return

        self.voice_clients[ctx.guild.id].pause()

    @commands.command()
    async def resume(self, ctx):
        if ctx.guild.id not in self.voice_clients or not self.voice_clients[ctx.guild.id].is_paused():
            await ctx.send("There is no song currently paused.")
            return

        self.voice_clients[ctx.guild.id].resume()

    @commands.command(aliases=['np', 'nowplaying'])
    async def playing(self, ctx):
        if ctx.guild.id not in self.song_info:
            await ctx.send("No song is currently playing.")
            return

        song = self.song_info[ctx.guild.id]
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


async def setup(bot: commands.Bot):
    ext = Music(bot)
    await bot.add_cog(ext)
