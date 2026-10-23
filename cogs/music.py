import asyncio
import logging
import re
from typing import Optional
import urllib.parse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import yarl
import time

logger = logging.getLogger(__name__)

# 公開可用的 Lavalink v4 節點池（僅保留單一穩定 SSL 節點，避免同伺服器雙連線互搶 Session 造成語音斷線）
PUBLIC_LAVALINK_NODES = [
    {
        "identifier": "Serenetia-SSL",
        "uri": "https://lavalinkv4.serenetia.com:443",
        "password": "https://dsc.gg/ajidevserver",
    },
]

URL_REGEX = re.compile(r"^https?://", re.IGNORECASE)
BILIBILI_URL_EXTRACT_REGEX = re.compile(
    r"(https?://(?:www\.|m\.)?(?:bilibili\.com/(?:video|audio)/[^\s]+|b23\.tv/[^\s]+)|(?:www\.|m\.)?bilibili\.com/(?:video|audio)/[^\s]+|b23\.tv/[^\s]+)",
    re.IGNORECASE,
)
BV_EXTRACT_REGEX = re.compile(r"(BV[a-zA-Z0-9]{10})", re.IGNORECASE)
AV_EXTRACT_REGEX = re.compile(r"(?:^|/)(av\d+)(?:[/?#&]|$)", re.IGNORECASE)


def is_bilibili_query(query: str) -> bool:
    """判斷輸入是否包含 Bilibili 網址、b23.tv 短網址或 BV 號"""
    q = query.strip()
    if "bilibili.com" in q.lower() or "b23.tv/" in q.lower():
        return True
    if re.match(r"^BV[a-zA-Z0-9]{10}$", q, re.IGNORECASE):
        return True
    if BILIBILI_URL_EXTRACT_REGEX.search(q):
        return True
    return False


def clean_bilibili_title(raw_title: str) -> str:
    """清理 Bilibili 影片標題中的雜訊標籤（如【4K】、【搬運】、【中字】等），保留核心歌名與歌手"""
    title = raw_title
    noise_patterns = [
        r"【[^】]*(?:4K|8K|1080[pP]|60[fF][pP][sS]|120[fF][pP][sS]|Hi-?Res|無損|无损|純享|纯享|搬運|搬运|字幕|中字|中日|雙語|双语|官方|MV|PV|完整版|自製|自制|精选|精選|高音質|高音质|現場|现场|熟肉|生肉|合集|作業用|作业用|BGM)[^】]*】",
        r"\[[^\]]*(?:4K|8K|1080[pP]|60[fF][pP][sS]|120[fF][pP][sS]|Hi-?Res|無損|无损|純享|纯享|搬運|搬运|字幕|中字|中日|雙語|双语|官方|MV|PV|完整版|高音質|高音质)[^\]]*\]",
        r"\([^\)]*(?:4K|8K|1080[pP]|60[fF][pP][sS]|Hi-?Res|無損|无损|中字|雙語|双语)[^\)]*\)",
        r"（[^）]*(?:4K|8K|1080[pP]|60[fF][pP][sS]|Hi-?Res|無損|无损|中字|雙語|双语)[^）]*）",
    ]
    for pat in noise_patterns:
        title = re.sub(pat, " ", title, flags=re.IGNORECASE)

    for ch in ("《", "》", "「", "」", "『", "』", "【", "】", "|", "｜", "/"):
        title = title.replace(ch, " ")

    title = re.sub(r"\s+", " ", title).strip()
    return title if title else raw_title.strip()


def format_duration(milliseconds: Optional[int], *, is_stream: bool = False) -> str:
    """將毫秒轉換為 mm:ss 或 hh:mm:ss 格式"""
    if is_stream:
        return "🔴 直播中"
    if not milliseconds or milliseconds <= 0:
        return "00:00"
    total_seconds = int(milliseconds // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def build_progress_bar(position_ms: int, length_ms: int, bar_length: int = 14) -> str:
    """產生播放進度條"""
    if length_ms <= 0:
        return "🔴 LIVE"
    ratio = max(0.0, min(1.0, position_ms / length_ms))
    pointer = int(ratio * (bar_length - 1))
    bar = "▬" * pointer + "🔘" + "▬" * (bar_length - 1 - pointer)
    return f"`[{bar}]`"


def parse_time_to_ms(time_str: str) -> Optional[int]:
    """解析秒數 (90) 或時間格式 (1:30 / 01:02:03) 為毫秒"""
    time_str = time_str.strip()
    if time_str.isdigit():
        return int(time_str) * 1000
    parts = time_str.split(":")
    if not all(p.isdigit() for p in parts):
        return None
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return (minutes * 60 + seconds) * 1000
    if len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return (hours * 3600 + minutes * 60 + seconds) * 1000
    return None


def is_valid_media_url(url: Optional[str]) -> bool:
    """檢查是否為有效的圖片網址（排除防盜鏈會導致 Discord 報錯的網址）"""
    if not url or not isinstance(url, str):
        return False
    return url.startswith(("http://", "https://"))


def create_container_view(
    title: str,
    description: Optional[str] = None,
    *,
    thumbnail_url: Optional[str] = None,
    footer: Optional[str] = None,
) -> discord.ui.LayoutView:
    """建立無邊框顏色的 discord.ui.Container 標準 LayoutView 卡片"""
    container = discord.ui.Container()

    container.add_item(discord.ui.TextDisplay(f"## {title}"))
    if description or footer:
        container.add_item(discord.ui.Separator())

    if description:
        if is_valid_media_url(thumbnail_url):
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(description),
                    accessory=discord.ui.Thumbnail(media=thumbnail_url),
                )
            )
        else:
            container.add_item(discord.ui.TextDisplay(description))

    if footer:
        if description:
            container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"-# {footer}"))

    view = discord.ui.LayoutView()
    view.add_item(container)
    return view


def create_gemini_error_view(error: object) -> discord.ui.LayoutView:
    """建立與 gemini.py 相同報錯文案的無色 Container 錯誤訊息"""
    err_str = str(error).strip() if error else "Lavalink 音樂節點無回應，重試 3 次後仍無法播放"
    container = discord.ui.Container()
    container.add_item(discord.ui.TextDisplay("因為劉東鑫超可憐叫Gemini寫程式碼所以導致的錯誤"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"```\n{err_str[:3800]}\n```"))
    view = discord.ui.LayoutView()
    view.add_item(container)
    return view


def is_node_healthy(node: Optional[wavelink.Node]) -> bool:
    """檢查 Lavalink 節點是否真正處於健康的 WebSocket 連線狀態（排除假性 CONNECTED 殭屍節點）"""
    if node is None or node.status is not wavelink.NodeStatus.CONNECTED or not node.session_id:
        return False
    ws = getattr(node, "_websocket", None)
    if ws is None or not ws.is_connected():
        return False
    ka = getattr(ws, "keep_alive_task", None)
    if ka is not None and ka.done():
        return False
    return True


class MusicPlayer(wavelink.Player):
    """自訂 Wavelink Player，修復語音連線競態條件並支援 Session 404 無縫重建（不退出語音頻道）"""

    def __init__(self, *args, **kwargs):
        valid_ids = {cfg["identifier"] for cfg in PUBLIC_LAVALINK_NODES}
        valid_nodes = [
            n
            for nid, n in wavelink.Pool.nodes.items()
            if nid in valid_ids and is_node_healthy(n)
        ]
        if valid_nodes and "nodes" not in kwargs:
            kwargs["nodes"] = valid_nodes
        super().__init__(*args, **kwargs)
        self.home_channel: Optional[discord.abc.Messageable] = None
        self.now_playing_message: Optional[discord.Message] = None
        self._voice_dispatch_lock: asyncio.Lock = asyncio.Lock()
        self._last_dispatched_voice: Optional[tuple[str, str, str, Optional[str]]] = None
        # 預設啟用 partial 自動播放（自動從 queue 取下一首並支援單曲/清單循環）
        self.autoplay = wavelink.AutoPlayMode.partial

    async def refresh_node_session(self) -> bool:
        """當 Lavalink Session 過期 (HTTP 404) 時，在背景重建全新 Node 實例並重新綁定語音狀態，絕不離開語音頻道"""
        internal_nodes: dict[str, wavelink.Node] = getattr(wavelink.Pool, "_Pool__nodes", {})
        for nid in list(internal_nodes.keys()):
            old_n = internal_nodes.pop(nid, None)
            if old_n:
                try:
                    old_n._retries = 0
                    old_n._players.clear()
                    if old_n._websocket is not None:
                        if old_n._websocket.keep_alive_task:
                            old_n._websocket.keep_alive_task.cancel()
                        if old_n._websocket.socket:
                            await old_n._websocket.socket.close()
                    if old_n._session and not old_n._session.closed:
                        await old_n._session.close()
                except Exception:
                    pass

        cfg = PUBLIC_LAVALINK_NODES[0]
        new_node = wavelink.Node(
            identifier=cfg["identifier"],
            uri=cfg["uri"],
            password=cfg["password"],
            inactive_player_timeout=300,
            retries=2,
        )
        try:
            await wavelink.Pool.connect(client=self.client, nodes=[new_node])
            for _ in range(16):
                if is_node_healthy(new_node):
                    break
                await asyncio.sleep(0.25)
        except Exception as e:
            logger.warning("重建節點 %s 失敗: %s", cfg["identifier"], e)
            return False

        self._node = new_node
        if self.guild:
            new_node._players[self.guild.id] = self
        self._last_dispatched_voice = None
        await self._dispatch_voice_update(force=True)
        return is_node_healthy(new_node)

    async def on_voice_state_update(self, data, /) -> None:
        channel_id = data.get("channel_id")
        if not channel_id:
            self._last_dispatched_voice = None
            await self._destroy()
            return

        self._connected = True
        self._voice_state["voice"]["session_id"] = data["session_id"]
        self._voice_state["channel_id"] = str(channel_id)
        self.channel = self.client.get_channel(int(channel_id))  # type: ignore

        await self._dispatch_voice_update()

    async def _dispatch_voice_update(self, *, force: bool = False) -> None:
        if not self.guild:
            return

        if not hasattr(self, "_voice_dispatch_lock") or self._voice_dispatch_lock is None:
            self._voice_dispatch_lock = asyncio.Lock()

        async with self._voice_dispatch_lock:
            data = self._voice_state["voice"]
            session_id: Optional[str] = data.get("session_id")
            token: Optional[str] = data.get("token")
            endpoint: Optional[str] = data.get("endpoint")
            channel_id: Optional[str] = self._voice_state.get("channel_id")

            if not session_id or not token or not endpoint:
                return

            valid_ids = {cfg["identifier"] for cfg in PUBLIC_LAVALINK_NODES}
            valid_nodes = [
                n
                for nid, n in wavelink.Pool.nodes.items()
                if nid in valid_ids and is_node_healthy(n)
            ]
            # 注意：wavelink.Node.__eq__ 僅比對 identifier，因此必須使用 is not 比對物件實體！
            if valid_nodes and all(self._node is not vn for vn in valid_nodes):
                self._node = valid_nodes[0]
                self._last_dispatched_voice = None
            self.node._players[self.guild.id] = self

            state_key = (session_id, token, endpoint, channel_id, self.node.session_id)
            if not force and self._connection_event.is_set() and getattr(self, "_last_dispatched_voice", None) == state_key:
                return

            request_with_channel = {
                "voice": {
                    "sessionId": session_id,
                    "token": token,
                    "endpoint": endpoint,
                    "channelId": channel_id,
                }
            }
            request_legacy = {
                "voice": {
                    "sessionId": session_id,
                    "token": token,
                    "endpoint": endpoint,
                }
            }

            connected_ok = False
            for attempt in range(2):
                try:
                    await self.node._update_player(self.guild.id, data=request_with_channel)
                    connected_ok = True
                    break
                except wavelink.LavalinkException as le:
                    if getattr(le, "status", None) == 404 and attempt == 0:
                        logger.warning("節點 %s Session 404，正在背景重建全新節點...", self.node.identifier)
                        try:
                            internal_nodes: dict[str, wavelink.Node] = getattr(wavelink.Pool, "_Pool__nodes", {})
                            for nid in list(internal_nodes.keys()):
                                old_n = internal_nodes.pop(nid, None)
                                if old_n:
                                    old_n._retries = 0
                                    old_n._players.clear()
                                    if old_n._websocket and old_n._websocket.keep_alive_task:
                                        old_n._websocket.keep_alive_task.cancel()
                                    if old_n._websocket and old_n._websocket.socket:
                                        await old_n._websocket.socket.close()
                                    if old_n._session and not old_n._session.closed:
                                        await old_n._session.close()
                            cfg = PUBLIC_LAVALINK_NODES[0]
                            new_node = wavelink.Node(
                                identifier=cfg["identifier"],
                                uri=cfg["uri"],
                                password=cfg["password"],
                                inactive_player_timeout=300,
                                retries=2,
                            )
                            await wavelink.Pool.connect(client=self.client, nodes=[new_node])
                            for _ in range(16):
                                if is_node_healthy(new_node):
                                    break
                                await asyncio.sleep(0.25)
                            self._node = new_node
                            self.node._players[self.guild.id] = self
                            state_key = (session_id, token, endpoint, channel_id, self.node.session_id)
                            continue
                        except Exception as re_err:
                            logger.warning("重建節點失敗: %s", re_err)
                    try:
                        await self.node._update_player(self.guild.id, data=request_legacy)
                        connected_ok = True
                        break
                    except Exception as inner_exc:
                        logger.warning("節點 %s 更新語音狀態失敗: %s", self.node.identifier, inner_exc)
                except Exception as exc:
                    logger.warning("節點 %s 語音連線發生例外: %s", self.node.identifier, exc)
                    break

            if connected_ok:
                self._last_dispatched_voice = state_key
            # 重要：絕不在 _dispatch_voice_update 內呼叫 self.disconnect()，避免機器人反覆進出語音頻道
            self._connected = True
            self._connection_event.set()


class SearchSelect(discord.ui.Select):
    """搜尋結果下拉選單（內嵌於 Container 中）"""

    def __init__(self, cog: "Music", ctx: commands.Context, tracks: list[wavelink.Playable]):
        self.cog = cog
        self.ctx = ctx
        self.tracks = tracks[:10]

        options = []
        for idx, track in enumerate(self.tracks):
            title = track.title[:95] if track.title else "未知標題"
            author = track.author[:50] if track.author else "未知作者"
            duration = format_duration(track.length, is_stream=track.is_stream)
            options.append(
                discord.SelectOption(
                    label=f"{idx + 1}. {title}",
                    description=f"{author} • {duration}",
                    value=str(idx),
                    emoji="🎵",
                )
            )

        super().__init__(
            placeholder="🎵 請選擇要播放的歌曲...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ 只有發起搜尋的使用者可以選擇歌曲！", ephemeral=True)

        await interaction.response.defer()
        selected_idx = int(self.values[0])
        track = self.tracks[selected_idx]

        player = await self.cog.ensure_voice(self.ctx, interaction=interaction)
        if not player:
            return

        setattr(track, "requester", interaction.user)
        await player.queue.put_wait(track)

        try:
            if not player.playing and not player.paused:
                next_track = await player.queue.get_wait()
                await self.cog.safe_play(player, next_track)
                np_view = MusicControlView(self.cog, player, next_track)
                await interaction.edit_original_response(view=np_view)
            else:
                added_view = create_container_view(
                    "📋 | 已加入待播清單",
                    (
                        f"### [{track.title}]({track.uri or 'https://youtube.com'})\n"
                        f"👤 作者：`{track.author}`\n"
                        f"⏱️ 時長：`{format_duration(track.length, is_stream=track.is_stream)}`\n"
                        f"🔢 佇列位置：`#{len(player.queue)}`"
                    ),
                    thumbnail_url=track.artwork,
                )
                await interaction.edit_original_response(view=added_view)
        except Exception as e:
            await interaction.edit_original_response(view=create_gemini_error_view(e))


class SearchView(discord.ui.LayoutView):
    """使用無色 Container 包裝的搜尋結果與下拉選單介面"""

    def __init__(self, cog: "Music", ctx: commands.Context, query: str, tracks: list[wavelink.Playable]):
        super().__init__(timeout=60)
        self.cog = cog
        self.ctx = ctx
        self.query = query
        self.tracks = tracks[:10]

        lines = []
        for idx, t in enumerate(self.tracks, start=1):
            dur = format_duration(t.length, is_stream=t.is_stream)
            lines.append(f"`{idx:02d}.` **[{t.title[:55]}]({t.uri or 'https://youtube.com'})** `[{dur}]` - *{t.author}*")

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"## 🔎 | 搜尋結果：{query}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("\n".join(lines)))
        container.add_item(discord.ui.Separator())

        row = discord.ui.ActionRow()
        row.add_item(SearchSelect(cog, ctx, self.tracks))
        container.add_item(row)
        container.add_item(discord.ui.TextDisplay("-# 請在 60 秒內從選單選擇要播放的歌曲"))

        self.add_item(container)


class QueuePaginationView(discord.ui.LayoutView):
    """使用無色 Container 的播放清單分頁檢視器"""

    def __init__(self, player: MusicPlayer, author_id: int, per_page: int = 10):
        super().__init__(timeout=120)
        self.player = player
        self.author_id = author_id
        self.per_page = per_page
        self.current_page = 0

        self.prev_btn = discord.ui.Button(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary)
        self.next_btn = discord.ui.Button(label="➡️ 下一頁", style=discord.ButtonStyle.secondary)
        self.prev_btn.callback = self._on_prev
        self.next_btn.callback = self._on_next

        self.rebuild()

    @property
    def total_pages(self) -> int:
        total = len(self.player.queue)
        return max(1, (total + self.per_page - 1) // self.per_page)

    def rebuild(self):
        self.clear_items()
        self.prev_btn.disabled = self.current_page <= 0
        self.next_btn.disabled = self.current_page >= self.total_pages - 1

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("## 🎶 | 音樂播放清單"))
        container.add_item(discord.ui.Separator())

        mode_names = {
            wavelink.QueueMode.normal: "➡️ 關閉循環",
            wavelink.QueueMode.loop: "🔂 單曲循環",
            wavelink.QueueMode.loop_all: "🔁 清單循環",
        }
        mode_str = mode_names.get(self.player.queue.mode, "➡️ 正常")

        if self.player.current:
            cur = self.player.current
            pos_str = f"{format_duration(self.player.position)} / {format_duration(cur.length, is_stream=cur.is_stream)}"
            status_icon = "⏸️ 暫停中" if self.player.paused else "▶️ 正在播放"
            cur_text = (
                f"**{status_icon}**\n"
                f"### [{cur.title}]({cur.uri or 'https://youtube.com'})\n"
                f"👤 `{cur.author}` ｜ ⏱️ `{pos_str}`\n"
                f"{build_progress_bar(self.player.position, cur.length)}"
            )
            if is_valid_media_url(cur.artwork):
                container.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(cur_text),
                        accessory=discord.ui.Thumbnail(media=cur.artwork),
                    )
                )
            else:
                container.add_item(discord.ui.TextDisplay(cur_text))
            container.add_item(discord.ui.Separator())

        if not self.player.queue.is_empty:
            start = self.current_page * self.per_page
            end = start + self.per_page
            items = list(self.player.queue)[start:end]
            lines = [f"**📋 即將播放（共 {len(self.player.queue)} 首）**"]
            for idx, track in enumerate(items, start=start + 1):
                dur = format_duration(track.length, is_stream=track.is_stream)
                lines.append(
                    f"`{idx:02d}.` [{track.title[:48]}]({track.uri or 'https://youtube.com'}) `[{dur}]`"
                )

            container.add_item(discord.ui.TextDisplay("\n".join(lines)))

            total_ms = sum(t.length for t in self.player.queue if not t.is_stream and t.length)
            footer_text = (
                f"-# 第 {self.current_page + 1}/{self.total_pages} 頁 ｜ "
                f"總時長：{format_duration(total_ms)} ｜ 模式：{mode_str} ｜ 音量：{self.player.volume}%"
            )
        else:
            container.add_item(discord.ui.TextDisplay("**📋 即將播放**\n📭 佇列中目前沒有其他歌曲"))
            footer_text = f"-# 模式：{mode_str} ｜ 音量：{self.player.volume}%"

        if self.total_pages > 1:
            container.add_item(discord.ui.Separator())
            row = discord.ui.ActionRow()
            row.add_item(self.prev_btn)
            row.add_item(self.next_btn)
            container.add_item(row)

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(footer_text))

        self.add_item(container)

    async def _on_prev(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.rebuild()
        await interaction.response.edit_message(view=self)


class MusicControlView(discord.ui.LayoutView):
    """使用無色 Container 的正在播放面板與互動控制按鈕"""

    def __init__(self, cog: "Music", player: MusicPlayer, track: Optional[wavelink.Playable] = None):
        super().__init__(timeout=300)
        self.cog = cog
        self.player = player
        self.track = track or player.current
        self._disabled_all = False

        self.pause_resume_btn = discord.ui.Button(emoji="⏯️", label="暫停/繼續", style=discord.ButtonStyle.primary)
        self.skip_btn = discord.ui.Button(emoji="⏭️", label="跳過", style=discord.ButtonStyle.secondary)
        self.loop_btn = discord.ui.Button(emoji="🔁", label="循環模式", style=discord.ButtonStyle.secondary)
        self.shuffle_btn = discord.ui.Button(emoji="🔀", label="隨機打亂", style=discord.ButtonStyle.secondary)
        self.queue_btn = discord.ui.Button(emoji="📋", label="播放清單", style=discord.ButtonStyle.secondary)
        self.stop_btn = discord.ui.Button(emoji="⏹️", label="停止並離開", style=discord.ButtonStyle.danger)

        self.pause_resume_btn.callback = self._on_pause_resume
        self.skip_btn.callback = self._on_skip
        self.loop_btn.callback = self._on_loop
        self.shuffle_btn.callback = self._on_shuffle
        self.queue_btn.callback = self._on_queue
        self.stop_btn.callback = self._on_stop

        self.rebuild()

    def rebuild(self):
        self.clear_items()
        track = self.player.current or self.track

        mode_names = {
            wavelink.QueueMode.normal: "關閉",
            wavelink.QueueMode.loop: "🔂 單曲循環",
            wavelink.QueueMode.loop_all: "🔁 清單循環",
        }
        status_title = "⏸️ | 已暫停播放" if self.player.paused else "🎶 | 正在播放"

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"## {status_title}"))
        container.add_item(discord.ui.Separator())

        if track:
            info_text = (
                f"### [{track.title}]({track.uri or 'https://youtube.com'})\n"
                f"👤 **作者 / 頻道**：`{track.author or '未知'}`\n"
                f"⏱️ **時間進度**：`{format_duration(self.player.position)} / {format_duration(track.length, is_stream=track.is_stream)}`\n"
                f"📊 **進度條**：{build_progress_bar(self.player.position, track.length)}"
            )
            if is_valid_media_url(track.artwork):
                container.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(info_text),
                        accessory=discord.ui.Thumbnail(media=track.artwork),
                    )
                )
            else:
                container.add_item(discord.ui.TextDisplay(info_text))
        else:
            container.add_item(discord.ui.TextDisplay("目前沒有正在播放的歌曲。"))

        for btn in (
            self.pause_resume_btn,
            self.skip_btn,
            self.loop_btn,
            self.shuffle_btn,
            self.queue_btn,
            self.stop_btn,
        ):
            btn.disabled = self._disabled_all

        container.add_item(discord.ui.Separator())
        row1 = discord.ui.ActionRow(
            self.pause_resume_btn,
            self.skip_btn,
            self.loop_btn,
            self.shuffle_btn,
            self.queue_btn,
        )
        row2 = discord.ui.ActionRow(self.stop_btn)
        container.add_item(row1)
        container.add_item(row2)

        footer_text = (
            f"-# 音量：{self.player.volume}% ｜ "
            f"循環：{mode_names.get(self.player.queue.mode, '關閉')} ｜ "
            f"待播：{len(self.player.queue)} 首 ｜ "
            f"節點：{self.player.node.identifier}"
        )
        container.add_item(discord.ui.TextDisplay(footer_text))
        self.add_item(container)

    async def _check_same_voice(self, interaction: discord.Interaction) -> bool:
        if not self.player or not self.player.connected:
            await interaction.response.send_message("❌ 機器人目前未連線至語音頻道。", ephemeral=True)
            return False
        user_voice = getattr(interaction.user, "voice", None)
        if not user_voice or user_voice.channel != self.player.channel:
            await interaction.response.send_message("❌ 你必須與機器人在同一個語音頻道才能操作面板！", ephemeral=True)
            return False
        return True

    async def _on_pause_resume(self, interaction: discord.Interaction):
        if not await self._check_same_voice(interaction):
            return
        if not self.player.current:
            return await interaction.response.send_message("❌ 目前沒有正在播放的音樂。", ephemeral=True)

        await self.player.pause(not self.player.paused)
        state = "⏸️ 已暫停播放" if self.player.paused else "▶️ 已繼續播放"
        self.rebuild()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(state, ephemeral=True)

    async def _on_skip(self, interaction: discord.Interaction):
        if not await self._check_same_voice(interaction):
            return
        if not self.player.current:
            return await interaction.response.send_message("❌ 目前沒有可跳過的音樂。", ephemeral=True)

        skipped_title = self.player.current.title
        try:
            await self.player.skip(force=True)
        except wavelink.LavalinkException as e:
            if getattr(e, "status", None) == 404 and hasattr(self.player, "refresh_node_session"):
                await self.player.refresh_node_session()
                self.player._current = None
                if not self.player.queue.is_empty:
                    next_t = await self.player.queue.get_wait()
                    await self.cog.safe_play(self.player, next_t)
        await interaction.response.send_message(
            view=create_container_view("⏭️ | 已跳過歌曲", f"已跳過 **{skipped_title}**")
        )

    async def _on_loop(self, interaction: discord.Interaction):
        if not await self._check_same_voice(interaction):
            return

        if self.player.queue.mode is wavelink.QueueMode.normal:
            self.player.queue.mode = wavelink.QueueMode.loop
            msg = "🔂 已切換為：**單曲循環**"
        elif self.player.queue.mode is wavelink.QueueMode.loop:
            self.player.queue.mode = wavelink.QueueMode.loop_all
            msg = "🔁 已切換為：**整個清單循環**"
        else:
            self.player.queue.mode = wavelink.QueueMode.normal
            msg = "➡️ 已切換為：**關閉循環**"

        if self.player.current:
            self.rebuild()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    async def _on_shuffle(self, interaction: discord.Interaction):
        if not await self._check_same_voice(interaction):
            return
        if len(self.player.queue) < 2:
            return await interaction.response.send_message("❌ 待播清單至少要有 2 首歌才能隨機打亂。", ephemeral=True)

        self.player.queue.shuffle()
        await interaction.response.send_message(
            f"🔀 已隨機打亂待播清單中的 **{len(self.player.queue)}** 首歌曲！",
            ephemeral=True,
        )

    async def _on_queue(self, interaction: discord.Interaction):
        if not self.player or not self.player.connected:
            return await interaction.response.send_message("❌ 機器人目前未連線至語音頻道。", ephemeral=True)
        view = QueuePaginationView(self.player, interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def _on_stop(self, interaction: discord.Interaction):
        if not await self._check_same_voice(interaction):
            return

        self.player.queue.clear()
        self.player.auto_queue.clear()
        await self.player.disconnect()
        self._disabled_all = True
        self.rebuild()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            view=create_container_view(
                "⏹️ | 已停止播放",
                "已停止播放並讓機器人離開語音頻道。",
            )
        )


class Music(commands.Cog):
    """完整功能的 Discord 音樂機器人模組 (無色 Container UI + 支援前綴與斜線指令)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._node_connect_lock = asyncio.Lock()
        self._startup_task: Optional[asyncio.Task] = None
        self._empty_vc_tasks: dict[int, asyncio.Task] = {}

    async def cog_load(self):
        """當模組載入或 *reload music 時自動連線節點並同步指令"""
        self._startup_task = asyncio.create_task(self._initialize_music_cog())

    async def cog_unload(self):
        """當模組卸載時取消背景任務"""
        if self._startup_task and not self._startup_task.done():
            self._startup_task.cancel()
        for task in self._empty_vc_tasks.values():
            if not task.done():
                task.cancel()
        self._empty_vc_tasks.clear()

    def _upgrade_player_instance(self, player: Optional[wavelink.Player]) -> Optional[MusicPlayer]:
        """將 *reload music 前已存在於語音頻道的舊版 Player 實例原位升級為最新 MusicPlayer 類別"""
        if player is None:
            return None
        if player.__class__ is not MusicPlayer:
            player.__class__ = MusicPlayer
        if not hasattr(player, "_voice_dispatch_lock") or getattr(player, "_voice_dispatch_lock") is None:
            setattr(player, "_voice_dispatch_lock", asyncio.Lock())
        if not hasattr(player, "_last_dispatched_voice"):
            setattr(player, "_last_dispatched_voice", None)
        if not hasattr(player, "home_channel"):
            setattr(player, "home_channel", None)
        if not hasattr(player, "now_playing_message"):
            setattr(player, "now_playing_message", None)
        return player  # type: ignore

    async def rebuild_fresh_node(self, player: Optional[wavelink.Player] = None) -> Optional[wavelink.Node]:
        """強制清除所有失效或 Session 404 的舊節點，建立全新 Node 實例並無縫重新綁定所有語音中的 Player"""
        async with self._node_connect_lock:
            internal_nodes: dict[str, wavelink.Node] = getattr(wavelink.Pool, "_Pool__nodes", {})
            for nid in list(internal_nodes.keys()):
                old_node = internal_nodes.pop(nid, None)
                if old_node:
                    try:
                        old_node._retries = 0
                        old_node._players.clear()
                        if old_node._websocket is not None:
                            if old_node._websocket.keep_alive_task:
                                old_node._websocket.keep_alive_task.cancel()
                            if old_node._websocket.socket:
                                await old_node._websocket.socket.close()
                        if old_node._session and not old_node._session.closed:
                            await old_node._session.close()
                        old_node._status = wavelink.NodeStatus.DISCONNECTED
                    except Exception:
                        pass

            cfg = PUBLIC_LAVALINK_NODES[0]
            new_node = wavelink.Node(
                identifier=cfg["identifier"],
                uri=cfg["uri"],
                password=cfg["password"],
                inactive_player_timeout=300,
                retries=2,
            )
            await wavelink.Pool.connect(client=self.bot, nodes=[new_node])
            for _ in range(16):
                if is_node_healthy(new_node):
                    break
                await asyncio.sleep(0.25)

            # 將所有伺服器中已連線的語音播放器無縫綁定至新節點
            for g in self.bot.guilds:
                vc = g.voice_client
                if vc and isinstance(vc, wavelink.Player):
                    upgraded = self._upgrade_player_instance(vc)
                    if upgraded:
                        upgraded._node = new_node
                        new_node._players[g.id] = upgraded
                        upgraded._last_dispatched_voice = None
                        try:
                            await upgraded._dispatch_voice_update(force=True)
                        except Exception:
                            pass

            return new_node if is_node_healthy(new_node) else None

    async def _initialize_music_cog(self):
        await self.bot.wait_until_ready()
        await self.ensure_nodes_connected()
        healthy = self.get_connected_nodes()
        for g in self.bot.guilds:
            vc = g.voice_client
            if vc and isinstance(vc, wavelink.Player):
                upgraded = self._upgrade_player_instance(vc)
                if upgraded and healthy:
                    if all(upgraded._node is not hn for hn in healthy):
                        upgraded._node = healthy[0]
                    upgraded.node._players[g.id] = upgraded
                    upgraded._last_dispatched_voice = None
                    try:
                        await upgraded._dispatch_voice_update(force=True)
                    except Exception:
                        pass
        try:
            await self.bot.tree.sync()
        except Exception as e:
            logger.debug("同步斜線指令略過或失敗: %s", e)

    async def ensure_nodes_connected(self) -> bool:
        """確保至少有一個設定池內的 Lavalink v4 節點處於健康連線狀態，並安全移除舊版或殭屍節點"""
        valid_ids = {cfg["identifier"] for cfg in PUBLIC_LAVALINK_NODES}
        internal_nodes: dict[str, wavelink.Node] = getattr(wavelink.Pool, "_Pool__nodes", {})
        stale_ids = [
            nid
            for nid, n in list(internal_nodes.items())
            if nid not in valid_ids or not is_node_healthy(n)
        ]

        connected_nodes = [
            n
            for nid, n in internal_nodes.items()
            if nid in valid_ids and is_node_healthy(n)
        ]
        if connected_nodes and not stale_ids:
            return True

        async with self._node_connect_lock:
            internal_nodes = getattr(wavelink.Pool, "_Pool__nodes", {})
            for nid, n in list(internal_nodes.items()):
                if nid not in valid_ids or not is_node_healthy(n):
                    old_node = internal_nodes.pop(nid, None)
                    if old_node:
                        try:
                            old_node._retries = 0
                            old_node._players.clear()
                            if old_node._websocket is not None:
                                if old_node._websocket.keep_alive_task:
                                    old_node._websocket.keep_alive_task.cancel()
                                if old_node._websocket.socket:
                                    await old_node._websocket.socket.close()
                            if old_node._session and not old_node._session.closed:
                                await old_node._session.close()
                            old_node._status = wavelink.NodeStatus.DISCONNECTED
                        except Exception:
                            pass

            connected_nodes = [
                n
                for nid, n in internal_nodes.items()
                if nid in valid_ids and is_node_healthy(n)
            ]
            if connected_nodes:
                return True

            existing_ids = set(internal_nodes.keys())
            new_nodes = []
            for cfg in PUBLIC_LAVALINK_NODES:
                if cfg["identifier"] not in existing_ids:
                    new_nodes.append(
                        wavelink.Node(
                            identifier=cfg["identifier"],
                            uri=cfg["uri"],
                            password=cfg["password"],
                            inactive_player_timeout=300,
                            retries=2,
                        )
                    )

            if new_nodes:
                await wavelink.Pool.connect(client=self.bot, nodes=new_nodes)

            for _ in range(16):
                connected_nodes = [
                    n
                    for nid, n in internal_nodes.items()
                    if nid in valid_ids and is_node_healthy(n)
                ]
                if connected_nodes:
                    return True
                await asyncio.sleep(0.3)

            return bool(
                [
                    n
                    for nid, n in internal_nodes.items()
                    if nid in valid_ids and is_node_healthy(n)
                ]
            )

    def get_connected_nodes(self) -> list[wavelink.Node]:
        """取得所有已連線且 WebSocket 健康的節點"""
        valid_ids = {cfg["identifier"] for cfg in PUBLIC_LAVALINK_NODES}
        internal_nodes: dict[str, wavelink.Node] = getattr(wavelink.Pool, "_Pool__nodes", {})
        nodes = [
            n
            for nid, n in internal_nodes.items()
            if nid in valid_ids and is_node_healthy(n)
        ]
        return sorted(nodes, key=lambda n: (0 if "SSL" in n.identifier else 1, len(n.players)))

    async def fetch_bilibili_metadata(self, raw_input: str) -> Optional[dict]:
        """取得 Bilibili 影片資訊與直連串流（網路偶發失敗時自動重試最多 3 次）"""
        for attempt in range(1, 4):
            try:
                meta = await Music._fetch_bilibili_metadata_once(self, raw_input)
            except Exception as e:
                logger.warning("[Bilibili] 第 %d 次解析發生例外: %r", attempt, e)
                meta = None
            if meta and meta.get("stream_urls"):
                return meta
            if meta and attempt == 3:
                return meta
            logger.warning("[Bilibili] 第 %d 次解析未取得完整資訊，重試中...", attempt)
            await asyncio.sleep(0.6 * attempt)
        return None

    async def _fetch_bilibili_metadata_once(self, raw_input: str) -> Optional[dict]:
        """透過免 412 的 Bilibili Player API (pagelist + playurl HTML5) 與 Web API 取得標題、封面與直連音訊串流"""
        text = raw_input.strip()

        # 從分享文字中抽出網址（例如：【標題】 https://b23.tv/xxx）
        url_match = BILIBILI_URL_EXTRACT_REGEX.search(text)
        target_url = url_match.group(1) if url_match else text
        if not target_url.lower().startswith(("http://", "https://")) and (
            "bilibili.com" in target_url.lower() or "b23.tv" in target_url.lower()
        ):
            target_url = "https://" + target_url

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        page_num = 1
        bvid: Optional[str] = None
        aid: Optional[str] = None

        main_title: Optional[str] = None
        part_title: str = ""
        uploader: str = "Bilibili"
        pic: str = ""
        duration: int = 0
        cid: Optional[int] = None
        stream_urls: list[str] = []

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                # 1. 若為 b23.tv 短網址，跟隨重定向取得真實網址
                if "b23.tv/" in target_url.lower():
                    try:
                        async with session.get(
                            target_url,
                            allow_redirects=True,
                            timeout=aiohttp.ClientTimeout(total=8),
                        ) as resp:
                            target_url = str(resp.url)
                    except Exception as e:
                        logger.debug("解析 b23.tv 失敗: %s", e)

                # 解析分 P (?p=...)
                try:
                    parsed = urllib.parse.urlsplit(target_url)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "p" in qs and qs["p"][0].isdigit():
                        page_num = max(1, int(qs["p"][0]))
                except Exception:
                    pass

                # 擷取 BV 號或 av 號
                bv_m = BV_EXTRACT_REGEX.search(target_url) or BV_EXTRACT_REGEX.search(text)
                if bv_m:
                    bvid = bv_m.group(1)
                else:
                    av_m = AV_EXTRACT_REGEX.search(target_url)
                    if av_m:
                        aid = av_m.group(1)[2:]

                if bvid or aid:
                    id_param = f"bvid={bvid}" if bvid else f"aid={aid}"

                    # 2. 優先以非瀏覽器 UA 呼叫 view 介面（避免 Chrome UA 觸發無 JS Cookie 的 412 攔截），取得與 Bilibili 完全一致的主標題、UP主與高清封面
                    try:
                        view_url = f"https://api.bilibili.com/x/web-interface/view?{id_param}"
                        async with session.get(
                            view_url,
                            headers={"User-Agent": "curl/8.0.1", "Accept": "application/json"},
                            timeout=aiohttp.ClientTimeout(total=6),
                        ) as view_resp:
                            if view_resp.status == 200:
                                v_json = await view_resp.json(content_type=None)
                                if v_json.get("code") == 0 and v_json.get("data"):
                                    v_data = v_json["data"]
                                    bvid = v_data.get("bvid") or bvid
                                    if v_data.get("title"):
                                        main_title = v_data["title"]
                                    owner_name = (v_data.get("owner") or {}).get("name")
                                    if owner_name:
                                        uploader = owner_name
                                    v_pic = v_data.get("pic") or ""
                                    if v_pic.startswith("http://"):
                                        v_pic = "https://" + v_pic[7:]
                                    if v_pic:
                                        pic = v_pic
                                    v_pages = v_data.get("pages") or []
                                    if v_pages:
                                        idx = page_num - 1 if 1 <= page_num <= len(v_pages) else 0
                                        p_info = v_pages[idx]
                                        cid = p_info.get("cid") or v_data.get("cid")
                                        part_title = p_info.get("part") or ""
                                        duration = p_info.get("duration") or v_data.get("duration") or 0
                                    else:
                                        cid = v_data.get("cid")
                                        duration = v_data.get("duration") or 0
                    except Exception as e:
                        logger.debug("Bilibili view 資訊查詢失敗: %s", e)

                    # 3. 呼叫免 412 的 pagelist 介面（若 view 未取得 cid 或分 P 資訊時作為補充）
                    if not cid:
                        try:
                            pagelist_url = f"https://api.bilibili.com/x/player/pagelist?{id_param}"
                            async with session.get(pagelist_url, timeout=aiohttp.ClientTimeout(total=6)) as pl_resp:
                                if pl_resp.status == 200:
                                    pl_json = await pl_resp.json(content_type=None)
                                    if pl_json.get("code") == 0 and pl_json.get("data"):
                                        pages = pl_json["data"]
                                        idx = page_num - 1 if 1 <= page_num <= len(pages) else 0
                                        p_info = pages[idx]
                                        cid = p_info.get("cid")
                                        if not part_title:
                                            part_title = p_info.get("part") or ""
                                        if not duration:
                                            duration = p_info.get("duration") or 0
                                        if not pic:
                                            ff = p_info.get("first_frame") or ""
                                            if ff.startswith("http://"):
                                                ff = "https://" + ff[7:]
                                            if ff:
                                                pic = ff
                        except Exception as e:
                            logger.debug("Bilibili pagelist 查詢失敗: %s", e)

                    # 4. 呼叫免 Referer 驗證的 HTML5 playurl 介面取得直連 MP4 音訊流 (durl)
                    if cid:
                        try:
                            playurl_api = (
                                f"https://api.bilibili.com/x/player/playurl?{id_param}"
                                f"&cid={cid}&qn=16&fnval=1&platform=html5&high_quality=1"
                            )
                            async with session.get(playurl_api, timeout=aiohttp.ClientTimeout(total=6)) as pu_resp:
                                if pu_resp.status == 200:
                                    pu_json = await pu_resp.json(content_type=None)
                                    durl_list = (pu_json.get("data") or {}).get("durl") or []
                                    raw_urls: list[str] = []
                                    for item in durl_list:
                                        primary_u = item.get("url")
                                        if primary_u:
                                            raw_urls.append(primary_u)
                                        for bu in item.get("backup_url") or []:
                                            if bu and bu not in raw_urls:
                                                raw_urls.append(bu)

                                    # 將海外 Lavalink 節點百分百可直連的 Bilibili 國際 CDN 鏡像排在最前面
                                    # （避免台灣 IP 取得的 akamaized / mirrorali 節點被海外機房擋 422）
                                    overseas_mirrors = (
                                        "upos-sz-mirrorcosov.bilivideo.com",
                                        "upos-sz-mirrorhw.bilivideo.com",
                                        "upos-sz-mirrorcos.bilivideo.com",
                                    )
                                    for ru in raw_urls:
                                        try:
                                            sp = urllib.parse.urlsplit(ru)
                                            if sp.path.startswith("/upgcxcode/"):
                                                for m_host in overseas_mirrors:
                                                    rewritten = urllib.parse.urlunsplit(
                                                        ("https", m_host, sp.path, sp.query, "")
                                                    )
                                                    if rewritten not in stream_urls:
                                                        stream_urls.append(rewritten)
                                        except Exception:
                                            pass
                                    for ru in raw_urls:
                                        if ru not in stream_urls:
                                            stream_urls.append(ru)
                        except Exception as e:
                            logger.debug("Bilibili playurl 查詢失敗: %s", e)

                if main_title or stream_urls:
                    is_raw_filename = bool(
                        re.search(r"(\.(mp4|flv|mkv|mov|avi|webm|m4a)$|^studio_video_)", part_title, re.IGNORECASE)
                    )
                    safe_part = "" if is_raw_filename else part_title
                    final_title = main_title or safe_part or f"Bilibili {bvid or ''}".strip()
                    webpage_url = (
                        f"https://www.bilibili.com/video/{bvid}"
                        if bvid
                        else (f"https://www.bilibili.com/video/av{aid}" if aid else target_url)
                    )
                    if page_num > 1:
                        webpage_url += f"?p={page_num}"

                    display_title = (
                        f"{final_title} (P{page_num}: {safe_part})"
                        if page_num > 1 and safe_part and safe_part != final_title
                        else final_title
                    )
                    return {
                        "title": display_title,
                        "main_title": final_title,
                        "part_title": safe_part,
                        "uploader": uploader,
                        "thumbnail": pic,
                        "webpage_url": webpage_url,
                        "duration": duration,
                        "stream_urls": stream_urls,
                    }
        except Exception as e:
            logger.warning("[Bilibili] API 整體查詢失敗: %r", e)

        return None

    async def resolve_bilibili_tracks(
        self,
        query: str,
        nodes: list[wavelink.Node],
        preferred_node: Optional[wavelink.Node] = None,
    ) -> Optional[list[wavelink.Playable]]:
        """將 Bilibili 連結解析為原音直連音軌（僅使用 Bilibili 原生串流，絕不搜尋 YouTube 同名歌曲）"""
        bili_meta = await self.fetch_bilibili_metadata(query)
        if not bili_meta:
            return None

        display_title: str = bili_meta["title"]
        uploader: str = bili_meta["uploader"]
        thumbnail: str = bili_meta["thumbnail"]
        webpage_url: str = bili_meta["webpage_url"]
        duration_sec: int = bili_meta.get("duration") or 0
        stream_urls: list[str] = bili_meta.get("stream_urls") or []

        ordered_nodes = list(nodes)
        if preferred_node and preferred_node in ordered_nodes:
            ordered_nodes.remove(preferred_node)
            ordered_nodes.insert(0, preferred_node)

        def _decorate_track(track: wavelink.Playable, loaded_node: wavelink.Node) -> wavelink.Playable:
            track._title = display_title
            track._author = uploader
            track._uri = webpage_url
            if thumbnail:
                track._artwork = thumbnail
            if duration_sec > 0 and (not track.length or track.length <= 0):
                track._length = duration_sec * 1000
            setattr(track, "preferred_node", loaded_node)
            setattr(track, "bili_source_query", query)
            setattr(track, "bili_resolved_at", time.monotonic())
            return track

        logger.info("[Bilibili] 已解析：%s ｜ 直連串流 %d 條", display_title, len(stream_urls))

        # 僅使用 Bilibili HTML5 直連音訊流 (durl) 原音播放，絕不改搜同名歌曲
        for s_url in stream_urls[:5]:
            for node in ordered_nodes:
                track_list = await self._load_url_on_node(node, s_url)
                if track_list:
                    logger.info("[Bilibili] 節點 %s 成功載入直連串流", node.identifier)
                    _decorate_track(track_list[0], node)
                    return track_list[:1]

        # 若節點本身內建 Bilibili source plugin，嘗試直接交由節點解析該網址（非關鍵字搜尋）
        for node in ordered_nodes:
            try:
                direct = await wavelink.Pool.fetch_tracks(webpage_url, node=node)
                if direct:
                    track_list = direct.tracks if isinstance(direct, wavelink.Playlist) else list(direct)
                    if track_list:
                        _decorate_track(track_list[0], node)
                        return track_list[:1]
            except Exception:
                continue

        raise RuntimeError(f"Bilibili 直連串流載入失敗（{display_title}），節點無法讀取此串流網址")

    async def _load_url_on_node(self, node: wavelink.Node, url: str) -> list[wavelink.Playable]:
        """直接呼叫 Lavalink REST /v4/loadtracks，完整編碼網址（保留串流簽名參數不被拆解）"""
        if node.status is not wavelink.NodeStatus.CONNECTED:
            return []
        try:
            encoded = urllib.parse.quote(url, safe="")
            req_url = yarl.URL(f"{node.uri}/v4/loadtracks?identifier={encoded}", encoded=True)
            session = getattr(node, "_session", None)
            own_session = session is None or session.closed
            if own_session:
                session = aiohttp.ClientSession()
            try:
                async with session.get(
                    req_url, headers=node.headers, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        logger.warning("[Bilibili] 節點 %s 載入串流回應 HTTP %s", node.identifier, resp.status)
                        return []
                    data = await resp.json(content_type=None)
            finally:
                if own_session:
                    await session.close()
        except Exception as e:
            logger.warning("[Bilibili] 節點 %s 載入串流失敗: %r", node.identifier, e)
            return []

        load_type = data.get("loadType")
        payload = data.get("data")
        try:
            if load_type == "track" and payload:
                return [wavelink.Playable(data=payload)]
            if load_type == "search" and payload:
                return [wavelink.Playable(data=t) for t in payload]
            if load_type == "playlist" and payload:
                return [wavelink.Playable(data=t) for t in payload.get("tracks", [])]
        except Exception as e:
            logger.warning("[Bilibili] 解析節點 %s 回應失敗: %r", node.identifier, e)
            return []
        if load_type == "error":
            logger.warning(
                "[Bilibili] 節點 %s 拒絕串流：%s", node.identifier, (payload or {}).get("message")
            )
        return []

    async def smart_search(
        self,
        query: str,
        *,
        preferred_node: Optional[wavelink.Node] = None,
    ) -> Optional[wavelink.Search]:
        """跨節點、跨來源智慧搜尋（若節點異常自動重試最多 3 次；全數掛掉時拋出例外以顯示報錯）"""
        query = query.strip()
        last_node_err: Optional[Exception] = None
        any_valid_empty_response = False

        for attempt in range(1, 4):
            await self.ensure_nodes_connected()
            nodes = self.get_connected_nodes()
            if not nodes:
                last_node_err = RuntimeError("Lavalink 音樂節點全數斷線或無回應")
                await asyncio.sleep(0.5 * attempt)
                continue

            if preferred_node and preferred_node in nodes:
                nodes.remove(preferred_node)
                nodes.insert(0, preferred_node)

            # 1. 優先處理 Bilibili 網址、b23.tv 短網址、BV 號或 B 站分享文字（絕不落入 YouTube 同名搜尋）
            if is_bilibili_query(query):
                try:
                    bili_tracks = await self.resolve_bilibili_tracks(query, nodes, preferred_node=preferred_node)
                    if bili_tracks:
                        return bili_tracks
                    any_valid_empty_response = True
                except Exception as e:
                    last_node_err = e
                    logger.warning("[Bilibili] 第 %d/3 次載入直連串流失敗: %s", attempt, e)
                await asyncio.sleep(0.5 * attempt)
                continue

            is_url = bool(URL_REGEX.match(query))
            has_prefix = any(
                query.lower().startswith(p)
                for p in ("ytsearch:", "ytmsearch:", "scsearch:", "spsearch:", "dzsearch:", "amsearch:")
            )

            # 2. 若為一般網址或已指定搜尋前綴，依序在所有可用節點嘗試
            if is_url or has_prefix:
                for node in nodes:
                    try:
                        result = await wavelink.Pool.fetch_tracks(query, node=node)
                        if result:
                            return result
                        any_valid_empty_response = True
                    except Exception as e:
                        last_node_err = e
                        logger.debug("節點 %s 載入 %s 失敗 (第 %d/3 次): %s", node.identifier, query, attempt, e)

                if is_url and ("youtube.com" in query or "youtu.be" in query):
                    fallback_title = await self._extract_title_with_ytdlp(query)
                    if fallback_title:
                        query = fallback_title
                        is_url = False
                    elif any_valid_empty_response:
                        return None
                elif any_valid_empty_response:
                    return None

            # 3. 關鍵字搜尋：依序嘗試 YouTube Music -> YouTube -> SoundCloud 跨節點搜尋
            if not is_url and not has_prefix:
                search_sources = [
                    wavelink.TrackSource.YouTubeMusic,
                    wavelink.TrackSource.YouTube,
                    wavelink.TrackSource.SoundCloud,
                ]
                for node in nodes:
                    for source in search_sources:
                        try:
                            result = await wavelink.Playable.search(query, source=source, node=node)
                            if result:
                                return result
                            any_valid_empty_response = True
                        except Exception as e:
                            last_node_err = e
                            logger.debug("節點 %s 搜尋 (%s) %s 失敗: %s", node.identifier, source, query, e)

                if any_valid_empty_response:
                    return None

            await asyncio.sleep(0.5 * attempt)

        if last_node_err and not any_valid_empty_response:
            raise last_node_err
        return None

    async def _extract_title_with_ytdlp(self, url: str) -> Optional[str]:
        """當公開節點封鎖直接 YouTube 網址時，使用本機 yt-dlp 擷取影片標題與作者"""
        try:
            import yt_dlp

            def _extract():
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,
                    "skip_download": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        return None
                    title = info.get("title")
                    uploader = info.get("uploader") or info.get("channel")
                    if title and uploader:
                        return f"{title} {uploader}"
                    return title

            return await asyncio.to_thread(_extract)
        except Exception as e:
            logger.debug("yt-dlp 備援解析失敗: %s", e)
            return None

    async def find_fallback_track(self, failed_track: wavelink.Playable) -> Optional[wavelink.Playable]:
        """當某首音軌發生播放錯誤或 loadFailed 時，重新取得串流或從備援音源尋找替代音軌"""
        # 若為 Bilibili 音軌，僅重新向 Bilibili 取得最新直連串流，絕不搜尋 YouTube 同名歌曲
        bili_query = getattr(failed_track, "bili_source_query", None)
        if bili_query or (failed_track.uri and "bilibili.com" in failed_track.uri.lower()):
            source_q = bili_query or failed_track.uri
            if source_q:
                try:
                    fresh_list = await self.resolve_bilibili_tracks(source_q, self.get_connected_nodes())
                    if fresh_list:
                        setattr(fresh_list[0], "requester", getattr(failed_track, "requester", None))
                        return fresh_list[0]
                except Exception as e:
                    logger.warning("[Bilibili] 重新取得直連串流失敗: %s", e)
            return None

        fallback_query = f"{failed_track.title} {failed_track.author}".strip()
        if not fallback_query:
            return None

        failed_id = getattr(failed_track, "identifier", None)

        for node in self.get_connected_nodes():
            for src in (
                wavelink.TrackSource.YouTube,
                wavelink.TrackSource.YouTubeMusic,
                wavelink.TrackSource.SoundCloud,
            ):
                try:
                    alt_tracks = await wavelink.Playable.search(fallback_query, source=src, node=node)
                    if alt_tracks and not isinstance(alt_tracks, wavelink.Playlist):
                        for candidate in alt_tracks:
                            if candidate.identifier != failed_id:
                                candidate._title = failed_track.title
                                candidate._author = failed_track.author
                                candidate._uri = failed_track.uri
                                if failed_track.artwork:
                                    candidate._artwork = failed_track.artwork
                                setattr(candidate, "preferred_node", node)
                                setattr(candidate, "requester", getattr(failed_track, "requester", None))
                                return candidate
                except Exception:
                    continue
        return None

    async def safe_play(self, player: MusicPlayer, track: wavelink.Playable) -> wavelink.Playable:
        """安全播放歌曲，若節點異常或 Session 404 則自動重建節點並重試最多 3 次（不退出語音頻道）"""
        player = self._upgrade_player_instance(player) or player
        bili_query = getattr(track, "bili_source_query", None)
        resolved_at = getattr(track, "bili_resolved_at", None)
        if bili_query and resolved_at and time.monotonic() - resolved_at > 60 * 60:
            try:
                fresh = await self.resolve_bilibili_tracks(
                    bili_query, self.get_connected_nodes(), preferred_node=player.node
                )
                if fresh:
                    setattr(fresh[0], "requester", getattr(track, "requester", None))
                    track = fresh[0]
            except Exception as e:
                logger.warning("[Bilibili] 重新取得串流網址失敗: %r", e)

        last_err: Optional[Exception] = None
        current_candidate = track

        for attempt in range(1, 4):
            try:
                await self.ensure_nodes_connected()
                healthy_nodes = self.get_connected_nodes()
                if healthy_nodes and all(player._node is not hn for hn in healthy_nodes):
                    player._node = healthy_nodes[0]
                    if player.guild:
                        player.node._players[player.guild.id] = player
                    player._last_dispatched_voice = None
                await player._dispatch_voice_update()
                return await player.play(current_candidate)
            except Exception as err:
                last_err = err
                logger.warning("第 %d/3 次播放失敗 (節點 %s): %s", attempt, player.node.identifier, err)

                # 若節點回傳 Session 404 或連線異常，由 Cog 強制重建全新 Node 實例並重綁語音狀態（絕不退出語音頻道）
                if (isinstance(err, wavelink.LavalinkException) and getattr(err, "status", None) == 404) or "404" in str(err):
                    new_node = await self.rebuild_fresh_node(player)
                    if new_node:
                        try:
                            return await player.play(current_candidate)
                        except Exception as retry_err:
                            last_err = retry_err

                # 嘗試尋找備援替代音軌後再進入下一輪重試
                alt_track = await self.find_fallback_track(current_candidate)
                if alt_track:
                    current_candidate = alt_track
                await asyncio.sleep(0.5 * attempt)

        raise last_err or RuntimeError("Lavalink 節點無回應，重試 3 次後仍無法播放")

    async def ensure_voice(
        self,
        ctx: commands.Context,
        *,
        interaction: Optional[discord.Interaction] = None,
    ) -> Optional[MusicPlayer]:
        """確保使用者在語音頻道且機器人已成功連線至該頻道（絕不反覆斷線重連導致進進出出）"""
        user = interaction.user if interaction else ctx.author
        voice_state = getattr(user, "voice", None)

        async def _send_err(msg: str):
            err_view = create_container_view("❌ | 語音連線提示", msg)
            if interaction:
                if interaction.response.is_done():
                    await interaction.followup.send(view=err_view, ephemeral=True)
                else:
                    await interaction.response.send_message(view=err_view, ephemeral=True)
            else:
                await ctx.send(view=err_view)

        async def _send_gemini_err(err: object):
            err_view = create_gemini_error_view(err)
            if interaction:
                if interaction.response.is_done():
                    await interaction.followup.send(view=err_view)
                else:
                    await interaction.response.send_message(view=err_view)
            else:
                await ctx.send(view=err_view)

        if not voice_state or not voice_state.channel:
            await _send_err("你必須先加入一個語音頻道！")
            return None

        node_ok = False
        for attempt in range(1, 4):
            if await self.ensure_nodes_connected():
                node_ok = True
                break
            await asyncio.sleep(0.6 * attempt)

        if not node_ok:
            await _send_gemini_err("Lavalink 音樂節點全數斷線或無回應（已連續重試 3 次）")
            return None

        target_channel = voice_state.channel
        raw_vc = ctx.guild.voice_client
        player: Optional[MusicPlayer] = self._upgrade_player_instance(raw_vc) if isinstance(raw_vc, wavelink.Player) else None

        # 若機器人已經在語音頻道中，直接沿用現有連線並以物件實體比對綁定健康節點，絕不 disconnect 再重連！
        healthy_nodes = self.get_connected_nodes()
        if player and getattr(player, "channel", None) is not None:
            if healthy_nodes and all(player._node is not hn for hn in healthy_nodes):
                player._node = healthy_nodes[0]
                player.node._players[ctx.guild.id] = player
                player._last_dispatched_voice = None
            await player._dispatch_voice_update()
            if player.channel != target_channel:
                try:
                    await player.move_to(target_channel, timeout=15.0)
                except Exception as e:
                    await _send_gemini_err(e)
                    return None
            player.home_channel = ctx.channel
            return player

        if player and getattr(player, "channel", None) is None:
            try:
                await player.disconnect(force=True)
            except Exception:
                pass
            player = None

        try:
            player = await target_channel.connect(cls=MusicPlayer, self_deaf=True, timeout=15.0)
        except Exception as e:
            logger.error("語音頻道連線失敗: %s", e)
            await _send_gemini_err(e)
            return None

        player.home_channel = ctx.channel
        return player

    # ==================== Wavelink 與語音事件監聽 ====================

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Lavalink 音樂節點已就緒：{payload.node.identifier} (Session: {payload.session_id})")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: Optional[MusicPlayer] = payload.player  # type: ignore
        if not player or not player.home_channel:
            return

        track = payload.original or payload.track
        if player.now_playing_message:
            try:
                await player.now_playing_message.delete()
            except Exception:
                pass
            player.now_playing_message = None

        try:
            view = MusicControlView(self, player, track)
            player.now_playing_message = await player.home_channel.send(view=view)
        except Exception as e:
            logger.debug("發送正在播放訊息失敗: %s", e)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: Optional[MusicPlayer] = payload.player  # type: ignore
        if not player:
            return

        # 當音軌在 Lavalink 端串流發生 loadFailed 時，自動重試最多 3 次；若 3 次皆失敗則發送與 gemini.py 相同的報錯訊息
        if payload.reason == "loadFailed":
            failed_track = payload.original or payload.track
            retry_count = int(getattr(failed_track, "_load_failed_retries", 0))
            if retry_count < 3:
                alt_track = await self.find_fallback_track(failed_track)
                candidate = alt_track or failed_track
                setattr(candidate, "_load_failed_retries", retry_count + 1)
                try:
                    await player.play(candidate)
                    return
                except Exception as e:
                    logger.debug("loadFailed 第 %d/3 次重試失敗: %s", retry_count + 1, e)

            if player.home_channel:
                try:
                    await player.home_channel.send(
                        view=create_gemini_error_view(
                            f"歌曲「{failed_track.title}」於節點 {player.node.identifier} 載入失敗 (loadFailed)，連續重試 3 次仍無法播放。"
                        )
                    )
                except Exception:
                    pass
            if not player.queue.is_empty:
                next_track = await player.queue.get_wait()
                try:
                    await self.safe_play(player, next_track)
                except Exception as e:
                    if player.home_channel:
                        await player.home_channel.send(view=create_gemini_error_view(e))

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        """當播放器閒置超過設定時間時自動離開語音頻道"""
        music_player: MusicPlayer = player  # type: ignore
        channel = getattr(music_player, "home_channel", None)
        try:
            await music_player.disconnect()
        except Exception:
            pass
        if channel:
            try:
                await channel.send(
                    view=create_container_view(
                        "💤 | 自動離開語音頻道",
                        "因為長時間沒有播放音樂或頻道內無人收聽，機器人已自動離開語音頻道。",
                    )
                )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """偵測語音頻道人數變化，當頻道只剩機器人時 60 秒後自動離開"""
        guild = member.guild
        player: Optional[MusicPlayer] = guild.voice_client  # type: ignore
        if not player or not player.channel:
            return

        if member.id == self.bot.user.id and after.channel is None:
            player.queue.clear()
            try:
                await player.disconnect()
            except Exception:
                pass
            return

        human_members = [m for m in player.channel.members if not m.bot]
        if len(human_members) == 0:
            if guild.id not in self._empty_vc_tasks or self._empty_vc_tasks[guild.id].done():
                self._empty_vc_tasks[guild.id] = asyncio.create_task(self._auto_leave_empty_channel(guild))
        else:
            task = self._empty_vc_tasks.pop(guild.id, None)
            if task and not task.done():
                task.cancel()

    async def _auto_leave_empty_channel(self, guild: discord.Guild):
        try:
            await asyncio.sleep(60)
            player: Optional[MusicPlayer] = guild.voice_client  # type: ignore
            if player and player.channel:
                human_members = [m for m in player.channel.members if not m.bot]
                if len(human_members) == 0:
                    home = player.home_channel
                    player.queue.clear()
                    await player.disconnect()
                    if home:
                        await home.send(
                            view=create_container_view(
                                "👋 | 自動離開語音頻道",
                                "語音頻道內已無其他成員，機器人已自動離開頻道。",
                            )
                        )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("自動離開頻道任務發生錯誤: %s", e)

    # ==================== 音樂指令 (同時支援 *前綴 與 /斜線指令) ====================

    @commands.hybrid_command(name="join", aliases=["connect", "j"], description="讓機器人加入你所在的語音頻道")
    async def join(self, ctx: commands.Context):
        await ctx.defer()
        player = await self.ensure_voice(ctx)
        if player and player.channel:
            await ctx.send(
                view=create_container_view(
                    "🔊 | 已連線至語音頻道",
                    f"成功加入頻道：`{player.channel.name}`\n目前使用節點：`{player.node.identifier}`",
                )
            )

    @commands.hybrid_command(name="play", aliases=["p"], description="播放音樂或將歌曲/播放清單加入佇列")
    @app_commands.describe(query="輸入歌曲名稱、關鍵字或 YouTube / Bilibili (含 b23.tv、BV號) / Spotify / SoundCloud 網址")
    async def play(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        player = await self.ensure_voice(ctx)
        if not player:
            return

        try:
            tracks = await self.smart_search(query, preferred_node=player.node)
        except Exception as e:
            return await ctx.send(view=create_gemini_error_view(e))

        if not tracks:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 找不到歌曲",
                    f"找不到與 `{query}` 相關的歌曲，請嘗試其他關鍵字或網址。",
                )
            )

        is_playlist = (
            isinstance(tracks, wavelink.Playlist)
            and not getattr(tracks, "is_search", False)
            and not tracks.name.startswith("Search results")
        )

        if is_playlist:
            for t in tracks.tracks:
                setattr(t, "requester", ctx.author)
            added = await player.queue.put_wait(tracks)
            await ctx.send(
                view=create_container_view(
                    "📋 | 已加入播放清單",
                    f"### {tracks.name}\n共成功加入 **{added}** 首歌曲至待播清單！",
                    thumbnail_url=tracks.artwork,
                )
            )
        else:
            track = tracks[0]
            setattr(track, "requester", ctx.author)
            await player.queue.put_wait(track)

            if player.playing or player.paused:
                await ctx.send(
                    view=create_container_view(
                        "📋 | 已加入待播清單",
                        (
                            f"### [{track.title}]({track.uri or 'https://youtube.com'})\n"
                            f"👤 **作者**：`{track.author}`\n"
                            f"⏱️ **時長**：`{format_duration(track.length, is_stream=track.is_stream)}`\n"
                            f"🔢 **佇列位置**：`#{len(player.queue)}`"
                        ),
                        thumbnail_url=track.artwork,
                    )
                )
            else:
                await ctx.send(
                    view=create_container_view(
                        "🔎 | 準備播放",
                        f"已找到：**[{track.title}]({track.uri or 'https://youtube.com'})**，準備開始播放...",
                        thumbnail_url=track.artwork,
                    )
                )

        if not player.playing and not player.paused and not player.queue.is_empty:
            next_track = await player.queue.get_wait()
            try:
                await self.safe_play(player, next_track)
            except Exception as e:
                await ctx.send(view=create_gemini_error_view(e))

    @commands.hybrid_command(name="search", aliases=["find"], description="搜尋歌曲並從選單中挑選要播放的曲目")
    @app_commands.describe(query="要搜尋的歌曲名稱或關鍵字")
    async def search(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 語音頻道限制",
                    "你必須先加入一個語音頻道！",
                )
            )

        vc_player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        try:
            tracks = await self.smart_search(query, preferred_node=getattr(vc_player, "node", None))
        except Exception as e:
            return await ctx.send(view=create_gemini_error_view(e))

        if not tracks:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 找不到搜尋結果",
                    f"找不到與 `{query}` 相關的搜尋結果。",
                )
            )

        track_list = tracks.tracks if isinstance(tracks, wavelink.Playlist) else list(tracks)
        if not track_list:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 找不到搜尋結果",
                    f"找不到與 `{query}` 相關的搜尋結果。",
                )
            )

        await ctx.send(view=SearchView(self, ctx, query, track_list[:10]))

    @commands.hybrid_command(name="pause", description="暫停目前播放的音樂")
    async def pause(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.playing:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 無法暫停",
                    "目前沒有正在播放的音樂。",
                )
            )
        if player.paused:
            return await ctx.send(
                view=create_container_view(
                    "⏸️ | 已經暫停",
                    "音樂已經處於暫停狀態，輸入 `*resume` 可繼續播放。",
                )
            )

        await player.pause(True)
        await ctx.send(view=create_container_view("⏸️ | 已暫停播放", "已暫停目前播放的音樂。"))

    @commands.hybrid_command(name="resume", aliases=["unpause"], description="繼續播放已暫停的音樂")
    async def resume(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.current:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 無法繼續播放",
                    "目前沒有可繼續播放的音樂。",
                )
            )
        if not player.paused:
            return await ctx.send(view=create_container_view("▶️ | 播放中", "音樂目前已經在播放中。"))

        await player.pause(False)
        await ctx.send(view=create_container_view("▶️ | 已繼續播放", "已繼續播放音樂。"))

    @commands.hybrid_command(name="skip", aliases=["s", "next"], description="跳過目前播放的歌曲")
    async def skip(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.current:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 無法跳過",
                    "目前沒有可跳過的音樂。",
                )
            )

        title = player.current.title
        try:
            await player.skip(force=True)
        except wavelink.LavalinkException as e:
            if getattr(e, "status", None) == 404 and hasattr(player, "refresh_node_session"):
                await player.refresh_node_session()
                player._current = None
                if not player.queue.is_empty:
                    next_t = await player.queue.get_wait()
                    await self.safe_play(player, next_t)
        await ctx.send(view=create_container_view("⏭️ | 已跳過歌曲", f"已跳過：**{title}**"))

    @commands.hybrid_command(name="stop", aliases=["leave", "disconnect", "dc"], description="停止播放、清空佇列並離開語音頻道")
    async def stop(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 未連線",
                    "機器人目前不在任何語音頻道中。",
                )
            )

        player.queue.clear()
        player.auto_queue.clear()
        await player.disconnect()
        await ctx.send(view=create_container_view("⏹️ | 已停止播放", "已清空播放清單並離開語音頻道。"))

    @commands.hybrid_command(name="queue", aliases=["q", "playlist"], description="查看目前的音樂播放清單")
    async def queue(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.connected:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 未連線",
                    "機器人目前尚未連線至語音頻道。",
                )
            )

        if not player.current and player.queue.is_empty:
            return await ctx.send(view=create_container_view("📭 | 播放清單是空的", "目前沒有正在播放或排隊中的歌曲。"))

        view = QueuePaginationView(player, ctx.author.id)
        await ctx.send(view=view)

    @commands.hybrid_command(name="nowplaying", aliases=["np", "current"], description="顯示目前正在播放的歌曲資訊與控制面板")
    async def nowplaying(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.current:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 無播放曲目",
                    "目前沒有正在播放的歌曲。",
                )
            )

        await ctx.send(view=MusicControlView(self, player, player.current))

    @commands.hybrid_command(name="volume", aliases=["vol", "v"], description="調整或查看播放器音量 (1~100)")
    @app_commands.describe(level="音量大小 (1 ~ 100)")
    async def volume(self, ctx: commands.Context, level: Optional[int] = None):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.connected:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 未連線",
                    "機器人目前尚未連線至語音頻道。",
                )
            )

        if level is None:
            return await ctx.send(view=create_container_view("🔊 | 目前音量", f"目前播放器音量為：**{player.volume}%**"))

        if not 1 <= level <= 100:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 音量範圍錯誤",
                    "音量範圍請設定在 `1` 到 `100` 之間！",
                )
            )

        await player.set_volume(level)
        await ctx.send(view=create_container_view("🔊 | 音量已調整", f"已將音量調整為：**{level}%**"))

    @commands.hybrid_command(name="loop", aliases=["repeat"], description="切換循環模式 (off / track / queue)")
    @app_commands.describe(mode="選擇循環模式：關閉 (off)、單曲循環 (track) 或清單循環 (queue)")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="➡️ 關閉循環 (off)", value="off"),
            app_commands.Choice(name="🔂 單曲循環 (track)", value="track"),
            app_commands.Choice(name="🔁 清單循環 (queue)", value="queue"),
        ]
    )
    async def loop(self, ctx: commands.Context, mode: Optional[str] = None):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.connected:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 未連線",
                    "機器人目前尚未連線至語音頻道。",
                )
            )

        if mode:
            m = mode.lower().strip()
            if m in ("off", "normal", "none", "關閉", "0"):
                player.queue.mode = wavelink.QueueMode.normal
                return await ctx.send(view=create_container_view("➡️ | 循環模式更新", "已將循環模式設為：**關閉循環**"))
            elif m in ("track", "single", "song", "單曲", "1"):
                player.queue.mode = wavelink.QueueMode.loop
                return await ctx.send(view=create_container_view("🔂 | 循環模式更新", "已將循環模式設為：**單曲循環**"))
            elif m in ("queue", "all", "清單", "2"):
                player.queue.mode = wavelink.QueueMode.loop_all
                return await ctx.send(view=create_container_view("🔁 | 循環模式更新", "已將循環模式設為：**整個清單循環**"))

        if player.queue.mode is wavelink.QueueMode.normal:
            player.queue.mode = wavelink.QueueMode.loop
            await ctx.send(view=create_container_view("🔂 | 循環模式切換", "已切換為：**單曲循環**"))
        elif player.queue.mode is wavelink.QueueMode.loop:
            player.queue.mode = wavelink.QueueMode.loop_all
            await ctx.send(view=create_container_view("🔁 | 循環模式切換", "已切換為：**整個清單循環**"))
        else:
            player.queue.mode = wavelink.QueueMode.normal
            await ctx.send(view=create_container_view("➡️ | 循環模式切換", "已切換為：**關閉循環**"))

    @commands.hybrid_command(name="shuffle", aliases=["random"], description="隨機打亂待播清單中的歌曲順序")
    async def shuffle(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or player.queue.is_empty:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 無法打亂",
                    "待播清單目前是空的。",
                )
            )
        if len(player.queue) < 2:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 歌曲數量不足",
                    "待播清單至少需要 2 首歌曲才能進行隨機打亂。",
                )
            )

        player.queue.shuffle()
        await ctx.send(
            view=create_container_view(
                "🔀 | 已隨機打亂",
                f"已成功隨機打亂待播清單中的 **{len(player.queue)}** 首歌曲！",
            )
        )

    @commands.hybrid_command(name="remove", aliases=["rm", "delete"], description="從待播清單中移除指定編號的歌曲")
    @app_commands.describe(index="要移除的歌曲編號（可透過 *queue 查看）")
    async def remove(self, ctx: commands.Context, index: int):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or player.queue.is_empty:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 待播清單為空",
                    "待播清單目前是空的。",
                )
            )

        if not 1 <= index <= len(player.queue):
            return await ctx.send(
                view=create_container_view(
                    "❌ | 編號超出範圍",
                    f"請輸入 `1` 到 `{len(player.queue)}` 之間的數字。",
                )
            )

        removed_track = player.queue[index - 1]
        del player.queue[index - 1]
        await ctx.send(
            view=create_container_view(
                "🗑️ | 已移除歌曲",
                f"已從待播清單中移除：`#{index}` **{removed_track.title}**",
            )
        )

    @commands.hybrid_command(name="clear", description="清空待播清單中的所有歌曲")
    async def clear(self, ctx: commands.Context):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or player.queue.is_empty:
            return await ctx.send(view=create_container_view("📭 | 待播清單已空", "待播清單已經是空的。"))

        count = len(player.queue)
        player.queue.clear()
        await ctx.send(view=create_container_view("🧹 | 已清空待播清單", f"已清空待播清單中的 **{count}** 首歌曲。"))

    @commands.hybrid_command(name="seek", description="跳轉至目前歌曲的指定時間 (例如 90 或 1:30)")
    @app_commands.describe(position="輸入秒數 (例如 90) 或時間格式 (例如 1:30)")
    async def seek(self, ctx: commands.Context, position: str):
        player: Optional[MusicPlayer] = ctx.voice_client  # type: ignore
        if not player or not player.current:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 無播放曲目",
                    "目前沒有正在播放的歌曲。",
                )
            )

        if not player.current.is_seekable or player.current.is_stream:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 不支援跳轉",
                    "目前播放的音源（如直播串流）不支援時間跳轉。",
                )
            )

        target_ms = parse_time_to_ms(position)
        if target_ms is None:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 時間格式錯誤",
                    "請輸入秒數（如 `90`）或 `分:秒`（如 `1:30`）。",
                )
            )

        if target_ms < 0 or target_ms > player.current.length:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 超出長度範圍",
                    f"請輸入 `00:00` ~ `{format_duration(player.current.length)}` 之間的時間！",
                )
            )

        await player.seek(target_ms)
        await ctx.send(
            view=create_container_view(
                "⏩ | 已跳轉時間",
                f"目前進度：`{format_duration(target_ms)} / {format_duration(player.current.length)}`",
            )
        )

    @commands.hybrid_command(name="nodes", aliases=["lavalink"], description="查看目前音樂節點的連線狀態")
    async def nodes(self, ctx: commands.Context):
        await ctx.defer()
        await self.ensure_nodes_connected()
        if not wavelink.Pool.nodes:
            return await ctx.send(
                view=create_container_view(
                    "❌ | 尚無節點",
                    "目前尚未註冊任何 Lavalink 節點。",
                )
            )

        lines = []
        for node in wavelink.Pool.nodes.values():
            status_emoji = "🟢" if node.status is wavelink.NodeStatus.CONNECTED else "🔴"
            lines.append(
                f"{status_emoji} **{node.identifier}** (`{node.uri}`) - 狀態：`{node.status.name}` ｜ 播放器數：`{len(node.players)}`"
            )

        await ctx.send(
            view=create_container_view(
                "🛰️ | Lavalink 音樂節點狀態",
                "\n".join(lines),
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
