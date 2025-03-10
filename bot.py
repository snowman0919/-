import asyncio
import discord
import yt_dlp as youtube_dl
from discord.ext import commands
from collections import deque
import yt_dlp

discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

def get_video_title(url):
       ydl_opts = {
           'quiet': True,
           'extract_flat': 'in_playlist' # 플래트하게 메타데이터만 추출
       }

       with yt_dlp.YoutubeDL(ydl_opts) as ydl:
           info_dict = ydl.extract_info(url, download=False)
           video_title = info_dict.get('title', None)
           return video_title

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.songs = deque()  # 대기열
        self.current_song = None
    
    @commands.command()
    async def join(self, ctx):
        """음성채널에 참가해요!"""
        channel = ctx.author.voice.channel
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
        await channel.connect()

    @commands.command()
    async def play(self, ctx, *, url):
        """노래를 재생하는 명령어에요! 이미 재생중이라면 대기열에 추가해요! !p ytsearch:{검색어}를 이용해 평문으로 재생도 가능해요!"""
        self.songs.append(url)
        await ctx.send(f'노래🎵를 대기열에 추가했어요: {get_video_title(url)}')

        # 현재 음성 클라이언트 상태 확인
        voice_client = ctx.voice_client

        # 음성 채널에 연결되어 있지 않을 때
        if voice_client is None:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                await channel.connect()
                voice_client = ctx.voice_client
            else:
                await ctx.send("음성 채널에 아무도 없어요.")
                return

        # 만약 노래가 재생 중이면 추가 곡이 대기열에 그대로 있도록 함
        if not voice_client.is_playing() or  self.current_song == None:
            await self.play_next(ctx)

    async def play_next(self, ctx):
        if self.songs:
            self.current_song = self.songs.popleft()
            player = await YTDLSource.from_url(self.current_song, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            await ctx.send(f'지금 재생중🎧: {player.title}')

    @commands.command()
    async def p(self, ctx, *, url):
        """노래를 재생하는 명령어에요! 이미 재생중이라면 대기열에 추가해요! !p ytsearch:{검색어}를 이용해 평문으로 재생도 가능해요!-단축명령어"""
        self.songs.append(url)
        await ctx.send(f'노래🎵를 대기열에 추가했어요: {get_video_title(url)}')

        # 현재 음성 클라이언트 상태 확인
        voice_client = ctx.voice_client

        # 음성 채널에 연결되어 있지 않을 때
        if voice_client is None:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                await channel.connect()
                voice_client = ctx.voice_client
            else:
                await ctx.send("음성 채널에 아무도 없어요.")
                return

        # 만약 노래가 재생 중이면 추가 곡이 대기열에 그대로 있도록 함
        if not voice_client.is_playing() or  self.current_song == None:
            await self.play_next(ctx)

    async def play_next(self, ctx):
        if self.songs:
            self.current_song = self.songs.popleft()
            player = await YTDLSource.from_url(self.current_song, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            await ctx.send(f'지금 재생중🎧: {player.title}')

    @commands.command()
    async def next(self, ctx):
        """대기열에 있는 다음 노래를 재생해요!(동작안함)"""
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        await self.play_next(ctx)

    @commands.command()
    async def n(self, ctx):
        """대기열에 있는 다음 노래를 재생해요!(동작안함)-단축명령어"""
        if self.songs:
            self.current_song = self.songs.popleft()
            player = await YTDLSource.from_url(self.current_song, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            await ctx.send(f'지금 재생중🎧: {player.title}')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """음량을 조절해요!(버그있음)"""
 
        if ctx.voice_client is None:
            return await ctx.send("음성 채널에 아무도 없어요...")
 
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"음량🔊을 {volume}%로 변경했어요!!!")

    @commands.command()
    async def v(self, ctx, volume: int):
        """음량을 조절해요!(버그있음)-단축명령어"""
 
        if ctx.voice_client is None:
            return await ctx.send("음성 채널에 아무도 없어요...")
 
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"음량🔊을 {volume}%로 변경했어요!!!")

    @commands.command()
    async def playlist(self, ctx):
        """현재 대기열을 보여줘요!"""
        if not self.songs:
            return await ctx.send("대기열에 노래가 없어요.")
        
        playlist_info = "\n".join(f"{idx+1}. {get_video_title(url)}" for idx, url in enumerate(self.songs))
        await ctx.send(f"현재 대기열:\n{playlist_info}")

    @commands.command()
    async def pl(self, ctx):
        """현재 대기열을 보여줘요!-단축명령어"""
        if not self.songs:
            return await ctx.send("대기열에 노래가 없어요.")
        
        playlist_info = "\n".join(f"{idx+1}. {get_video_title(url)}" for idx, url in enumerate(self.songs))
        await ctx.send(f"현재 대기열:\n{playlist_info}")

    @commands.command()
    async def stop(self, ctx):
        """노래를 멈추고 대기열을 초기화해요!"""
        self.songs.clear()
        await ctx.voice_client.disconnect()

    @commands.command()
    async def pause(self, ctx):
        """얼음!!!!🧊(현재 재생하고 있는 음악을 잠시 멈춰요.⏯️)"""
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("음악을 일시정지했어요!")

    @commands.command()
    async def resume(self, ctx):
        """멈춘 음악을 다시 재생해요!▶️"""
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("음악을 다시 재생했어요!")

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("음성 채널에 아무도 없어요.")
                raise commands.CommandError("음성 채널에 아무도 없어요...")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description='🎵해방과 음악 봇 설명🎵',
    intents=intents,
)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await bot.add_cog(Music(bot))
    print('Music cog loaded')

bot.run('')
