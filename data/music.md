# 🎵 `cogs/music.py` 音樂機器人模組完整功能說明

本文件詳細介紹 `cogs/music.py` 的所有功能、指令列表、互動式介面（Components V2 無色 Container UI）以及底層技術架構。

---

## ✨ 核心特色總覽

1. **全平台音源支援**：
   - **Bilibili 原音直連播放**：支援標準網址（`bilibili.com/video/BV...`、`av...`）、手機短網址（`b23.tv/...`）、純 `BV` 號、App 分享文字（如 `【標題】 https://b23.tv/...`）以及分 P 指定（`?p=2`）。
   - **YouTube / YouTube Music / SoundCloud / Spotify**：支援關鍵字搜尋、單曲網址與播放清單（Playlist）批次匯入。
2. **純淨無色 Container UI（Discord Components V2）**：
   - 全面採用 `discord.ui.LayoutView` 與 `discord.ui.Container`（無側邊顏色條、無 `@mention` 標記干擾），搭配 `Section`、`Thumbnail`、`Separator` 與 `ActionRow` 呈現現代化排版。
3. **前綴與斜線雙棲指令（Hybrid Commands）**：
   - 所有指令皆同時支援前綴指令（`*`、`#`、`下巴`）與 Discord 斜線指令（`/play`、`/skip` 等）。
4. **高可用性節點與自動容錯機制**：
   - 支援 `*reload music` 熱重載不斷線（原位升級語音中的 `MusicPlayer` 實例，不踢出語音頻道）。
   - 當 Lavalink Session 發生 `HTTP 404` 或殭屍連線時，自動於背景重建全新 `wavelink.Node` 並重綁語音狀態，不會反覆進出語音頻道。
   - 若節點異常且連續重試 3 次仍無法播放，自動回傳與 `gemini.py` 相同風格的錯誤 Container（`因為劉東鑫超可憐叫Gemini寫程式碼所以導致的錯誤` + 錯誤訊息區塊）。

---

## ⌨️ 指令一覽表

> 所有指令皆可使用前綴（例如 `*play`、`#play`、`下巴play`）或斜線指令（例如 `/play`）。

| 指令名稱 | 別名 (Aliases) | 參數 | 功能說明 |
| :--- | :--- | :--- | :--- |
| **`play`** | `p` | `<query>` | 播放音樂或將歌曲／播放清單加入待播佇列（支援關鍵字、YouTube、Bilibili、b23.tv、BV號、Spotify、SoundCloud） |
| **`search`** | `find` | `<query>` | 搜尋關鍵字並顯示前 10 筆結果的下拉選單（`SearchSelect`），點選後立即播放或加入佇列 |
| **`join`** | `connect`, `j` | 無 | 讓機器人加入你目前所在的語音頻道 |
| **`pause`** | 無 | 無 | 暫停目前正在播放的音樂 |
| **`resume`** | `unpause` | 無 | 繼續播放已暫停的音樂 |
| **`skip`** | `s`, `next` | 無 | 強制跳過目前正在播放的歌曲，立即播放佇列中的下一首 |
| **`stop`** | `leave`, `disconnect`, `dc` | 無 | 停止播放、清空待播佇列並讓機器人離開語音頻道 |
| **`queue`** | `q`, `playlist` | 無 | 開啟分頁式待播清單面板（每頁 10 首，顯示總曲數與總時長） |
| **`nowplaying`** | `np`, `current` | 無 | 重新發送目前播放曲目的資訊卡與互動控制面板 |
| **`volume`** | `vol`, `v` | `[level]` | 查看目前音量，或將播放器音量調整為 `1` ~ `100`% |
| **`loop`** | `repeat` | `[mode]` | 切換循環模式：`off`（關閉循環）、`track`（單曲循環）、`queue`（整個清單循環） |
| **`shuffle`** | `random` | 無 | 隨機打亂待播清單中的所有歌曲順序（需至少 2 首待播歌曲） |
| **`remove`** | `rm`, `delete` | `<index>` | 從待播清單中移除指定編號（`1 ~ N`）的歌曲 |
| **`clear`** | 無 | 無 | 一鍵清空待播清單中的所有排隊歌曲 |
| **`seek`** | 無 | `<position>` | 跳轉至目前歌曲的指定時間點（支援秒數如 `90`，或時間格式如 `1:30`、`01:02:30`） |
| **`nodes`** | `lavalink` | 無 | 查看目前 Lavalink 音樂節點的連線狀態、URI 與播放器負載數量 |

---

## 🎛️ 互動式 UI 元件架構

### 1. 正在播放控制面板 (`MusicControlView`)
當歌曲開始播放或輸入 `*np` 時顯示，內含：
- **歌曲資訊區 (`Section` + `Thumbnail`)**：顯示可點擊的歌曲標題連結、作者／UP 主名稱、即時時間進度（`mm:ss / mm:ss`）、視覺化進度條（`[───🔘──────]`）與高清縮圖。
- **第一排控制按鈕**：
  - `⏯️ 暫停` / `▶️ 繼續`：即時切換播放與暫停狀態並更新面板。
  - `⏭️ 跳過`：跳過當前歌曲。
  - `🔁 循環`：在「關閉 ➡️ 單曲循環 🔂 ➡️ 清單循環 🔁」三種模式間循環切換。
  - `🔀 打亂`：隨機打亂待播清單。
  - `📋 待播清單`：以僅自己可見（Ephemeral）方式彈出分頁式待播清單。
- **第二排控制按鈕**：
  - `⏹️ 停止並離開`：清空佇列、停用舊面板按鈕並讓機器人離開語音頻道。
- **底部狀態列**：顯示目前音量、循環模式、待播歌曲數量與節點名稱。
- **同頻道權限保護 (`_check_same_voice`)**：僅允許與機器人處於同一個語音頻道的成員操作控制面板。

### 2. 搜尋選單面板 (`SearchView` + `SearchSelect`)
- 輸入 `*search <關鍵字>` 時顯示前 10 筆搜尋結果。
- 透過下拉選單選擇曲目後，若目前無音樂則立即開始播放並切換為控制面板；若已有音樂播放中則自動加入待播清單。
- 僅限發起搜尋指令的使用者本人可以操作選單。

### 3. 待播清單分頁面板 (`QueuePaginationView`)
- 輸入 `*queue` 或點擊控制面板上的「📋 待播清單」按鈕時顯示。
- 顯示目前正在播放的曲目、待播清單（每頁 10 首）、總歌曲數、總時長以及目前循環模式。
- 提供 `⬅️ 上一頁` 與 `➡️ 下一頁` 按鈕翻頁。

---

## 📺 Bilibili 原音直連解析機制

為了確保 Bilibili 影片能夠**原音播放**且**顯示與 B 站完全一致的標題與 UP 主名稱**，`music.py` 採用了以下四階段解析流程（`fetch_bilibili_metadata` & `resolve_bilibili_tracks`）：

1. **網址與分 P 解析**：
   - 自動從分享文字中擷取 `bilibili.com` 或 `b23.tv` 網址，並跟隨 `b23.tv` 重定向取得真實 `BV` 號／`av` 號與 `?p=` 分 P 編號。
2. **免 412 攔截取得完整標題與 UP 主資訊**：
   - 使用非瀏覽器指紋 Header 呼叫 `/x/web-interface/view`，繞過 B 站對無 JS Cookie 瀏覽器 UA 的 `HTTP 412` 攔截，直接取得與 B 站網頁一致的**主標題 (`title`)**、**UP 主名稱 (`owner.name`)**、**高清封面 (`pic`)** 與各分 P 的 `cid`。
   - 自動過濾創作者後台原始上傳檔名（如 `studio_video_xxx.mp4`），避免顯示亂碼檔名。
3. **HTML5 MP4 直連串流提取與海外 CDN 鏡像轉換**：
   - 呼叫 `/x/player/playurl?...&qn=16&fnval=1&platform=html5&high_quality=1` 取得免 `Referer` 防盜鏈驗證的 `durl` 直連音訊串流。
   - 自動將串流網址優先轉換為海外機房可直連的國際 CDN 鏡像（`upos-sz-mirrorcosov.bilivideo.com` 等），解決台灣 IP 取得的 `akamaized`／境內 `mirrorali` 節點被海外 Lavalink 伺服器拒絕（HTTP 422）的問題。
4. **純原音載入（不誤搜同名歌曲）**：
   - 透過 `_load_url_on_node` 將完整簽名網址進行百分比編碼後直連 Lavalink `/v4/loadtracks`，並將超過 1 小時的待播串流於播放前自動刷新簽名。
   - **絕不退回 YouTube 搜尋同名歌曲**，避免播放出毫不相干的影片。

---

## 🛡️ 自動離開與錯誤處理機制

- **60 秒無人自動退房 (`on_voice_state_update` & `_auto_leave_empty_channel`)**：
  - 當語音頻道內所有真人成員離開、只剩機器人時，啟動 60 秒倒數計時；若 60 秒內有人重新加入則自動取消倒數，否則清空佇列並離開頻道。
- **閒置自動退房 (`on_wavelink_inactive_player`)**：
  - 當播放器長時間（預設 300 秒）無播放活動時自動斷開語音連線並發送通知。
- **3 次重試與 Gemini 風格報錯 (`create_gemini_error_view`)**：
  - 無論是語音連線、搜尋載入、開始播放（`safe_play`）或播放途中發生 `loadFailed`（`on_wavelink_track_end`），皆具備最多 **3 次自動重試與節點重建機制**。
  - 若連續重試 3 次仍失敗，即發送包含 `因為劉東鑫超可憐叫Gemini寫程式碼所以導致的錯誤` 與完整錯誤資訊代碼區塊的無色 Container。
