import discord
from discord.ext import commands
import wavelink

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if wavelink.Pool.nodes:
            return

        # 可用的公開 Lavalink v4 節點清單
        nodes = [
            wavelink.Node(
                uri="http://lavalink.jirayu.net:13592",
                password="youshallnotpass",
                inactive_player_timeout=300
            )
        ]
        
        await wavelink.Pool.connect(client=self.bot, nodes=nodes)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ 公開 Lavalink 節點已成功連接：{payload.node.identifier}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if player and not player.queue.is_empty:
            next_track = await player.queue.get_wait()
            await player.play(next_track)

    @commands.command(name="join")
    async def join(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send("❌ 你必須先加入一個語音頻道！")

        channel = ctx.author.voice.channel
        player: wavelink.Player = ctx.voice_client

        if player:
            if player.channel.id == channel.id:
                return await ctx.send("🔊 機器人已經在此頻道中。")
            await player.move_to(channel)
            return await ctx.send(f"🔊 已移動至：`{channel.name}`")

        player = await channel.connect(cls=wavelink.Player, self_deaf=True)
        await ctx.send(f"🔊 成功加入：`{channel.name}`")

    @commands.command(name="play")
    async def play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ 你必須先加入一個語音頻道！")

        player: wavelink.Player = ctx.voice_client

        # 2. 如果機器人尚未連線，才執行 connect
        if not player:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
        # 3. 如果機器人已在其他語音房，則移動過去
        elif player.channel != ctx.author.voice.channel:
            await player.move_to(ctx.author.voice.channel)

        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            return await ctx.send("❌ 找不到相關歌曲。")

        is_playlist = isinstance(tracks, wavelink.Playlist) and not getattr(tracks, "is_search", False) and not tracks.name.startswith("Search results")

        if is_playlist:
            added = await player.queue.put_wait(tracks)
            await ctx.send(f"📋 已加入清單：**{tracks.name}**（共 {added} 首歌曲）")
        else:
            # 關鍵字搜尋或單曲，只取第 1 首歌
            track = tracks[0]
            await player.queue.put_wait(track)
            await ctx.send(f"📋 已加入清單：**{track.title}**")

        if not player.playing:
            next_track = await player.queue.get_wait()
            await player.play(next_track)
            await ctx.send(f"🎶 開始播放：**{next_track.title}**")

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client
        if player and player.playing:
            await player.skip(force=True)
            await ctx.send("⏭️ 已跳過當前歌曲。")
        else:
            await ctx.send("❌ 目前沒有可跳過的音樂。")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client
        if player:
            player.queue.clear()
            await player.disconnect()
            await ctx.send("⏹️ 已停止播放並退出語音頻道。")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        player: wavelink.Player = ctx.voice_client

        if not player or not player.connected:
            return await ctx.send("❌ 機器人目前尚未連線至語音頻道。")

        # 檢查是否有正在播放的歌曲以及待播清單是否有歌曲
        if not player.current and player.queue.is_empty:
            return await ctx.send("📭 目前播放清單是空的。")

        embed = discord.Embed(title="🎶 播放清單", color=discord.Color.blurple())

        # 顯示當前播放的歌曲
        if player.current:
            embed.add_field(
                name="▶️ 正在播放",
                value=f"**[{player.current.title}]({player.current.uri})**",
                inline=False
            )

        # 顯示排隊中的歌曲（最多列出前 10 首避免訊息過長）
        if not player.queue.is_empty:
            queue_list = []
            for index, track in enumerate(player.queue[:10], start=1):
                queue_list.append(f"`{index}.` [{track.title}]({track.uri})")

            embed.add_field(
                name="📋 即將播放",
                value="\n".join(queue_list),
                inline=False
            )

            # 若隊列超過 10 首歌，顯示剩餘數量
            if len(player.queue) > 10:
                embed.set_footer(text=f"還有 {len(player.queue) - 10} 首歌曲未顯示...")
        else:
            embed.add_field(name="📋 即將播放", value="佇列中無其他歌曲", inline=False)

        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))