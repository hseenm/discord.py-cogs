# cogs/gemini.py
import asyncio
import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
import config

load_dotenv()
AI_API = os.getenv("AI_API")
gemini_client = genai.Client(api_key=AI_API)
HISTORY_FILE = "./data/chat_history.json"

class Gemini(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.history_data = self.load_history()
        self.models_to_try = [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-2.5-flash"
        ]

    def load_history(self) -> dict:
        """讀取 JSON 歷史紀錄"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"讀取紀錄失敗: {e}")
        return {}

    def _save_history_sync(self):
        """將歷史紀錄寫回 JSON 檔案（同步版本）"""
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.history_data, f, ensure_ascii=False, indent=2)

    async def save_history(self):
        """非同步儲存歷史紀錄，避免阻塞事件迴圈"""
        await asyncio.to_thread(self._save_history_sync)

    def _build_history_contents(self, channel_id: str) -> list[types.Content]:
        """建立符合 API 規格且以 user 開頭的 Content 列表"""
        channel_history = self.history_data.get(channel_id, [])
        # 確保歷史紀錄由 user 開始，避免 API 400 錯誤
        start_idx = 0
        while start_idx < len(channel_history) and channel_history[start_idx].get("role") != "user":
            start_idx += 1
        valid_history = channel_history[start_idx:]

        return [
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["text"])]
            )
            for item in valid_history
            if item.get("text")
        ]

    def get_chat_for_channel(self, channel_id: str, model_name: str = 'gemini-3.7-flash'):
        """根據 JSON 歷史紀錄建立 chat 實例"""
        history_contents = self._build_history_contents(channel_id)
        return gemini_client.aio.chats.create(
            model=model_name,
            history=history_contents,
            config=types.GenerateContentConfig(
                system_instruction=f"你是由 Google 開發的 Gemini 模型，當前運行的精確模型版本為 {model_name}。當使用者詢問你的身分或模型時，請如實回答。"
            )
        )

    async def send_message_with_fallback(self, channel_id: str, prompt: str) -> tuple[str, str]:
        """依序嘗試備援名單中的模型，成功即回傳 (回答內容, 模型名稱)，全失敗才拋出例外"""
        history_contents = self._build_history_contents(channel_id)
        last_error = None

        for model_name in self.models_to_try:
            try:
                # 建立指定模型的對話，並注入當前運行的模型名稱
                chat = gemini_client.aio.chats.create(
                    model=model_name,
                    history=history_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=f"你是由 Google 開發的 Gemini 模型，當前運行的精確模型版本為 {model_name}。當使用者詢問你的身分或模型時，請如實回答。"
                    )
                )
                response = await chat.send_message(prompt)
                return (response.text or "（無文字回應）"), model_name

            except APIError as e:
                print(f"模型 {model_name} 呼叫失敗 ({e.code})，嘗試下一個備用模型...")
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        # 全部模型都失敗才拋出最後的錯誤
        raise last_error

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # 透過 mentions 判斷是否提及機器人（支援私訊與暱稱 mention）
        if self.bot.user in message.mentions:
            bot_name = message.guild.me.display_name if message.guild else self.bot.user.display_name
            clean_prompt = message.clean_content.replace(f'@{bot_name}', '').strip()
            channel_id = str(message.channel.id)

            # 支援直接透過對話清除紀錄
            if clean_prompt.lower() in ["清除對話", "重置對話", "清除紀錄", "reset", "clear"]:
                self.history_data[channel_id] = []
                await self.save_history()
                container = discord.ui.Container()
                container.add_item(discord.ui.TextDisplay("🧹 已成功清除本頻道的 Gemini 對話紀錄！"))
                view = discord.ui.LayoutView().add_item(container)
                await message.channel.send(view=view)
                return

            if not clean_prompt:
                clean_prompt = "你好"

            try:
                # 顯示打字中狀態，提升使用者體驗
                async with message.channel.typing():
                    # 執行帶有 fallback 機制的回應生成，取得回應文字與使用的模型名稱
                    reply_text, used_model = await self.send_message_with_fallback(channel_id, clean_prompt)

                # 更新並記錄至 JSON
                if channel_id not in self.history_data:
                    self.history_data[channel_id] = []
                self.history_data[channel_id].append({"role": "user", "text": clean_prompt})
                self.history_data[channel_id].append({"role": "model", "text": reply_text})

                # 保留最近 20 則並確保首則由 user 開始
                trimmed_history = self.history_data[channel_id][-20:]
                while trimmed_history and trimmed_history[0]["role"] != "user":
                    trimmed_history.pop(0)
                self.history_data[channel_id] = trimmed_history

                await self.save_history()

                # 使用 Container 方式包裝回答，並在底端附加使用的模型版本標籤
                chunk_size = 3800
                chunks = [reply_text[i:i + chunk_size] for i in range(0, len(reply_text), chunk_size)] or ["（無文字回應）"]

                for idx, chunk in enumerate(chunks):
                    container = discord.ui.Container()
                    container.add_item(discord.ui.TextDisplay(chunk))
                    # 在最後一個容器底部加上分隔線與模型版本資訊
                    if idx == len(chunks) - 1:
                        container.add_item(discord.ui.Separator())
                        container.add_item(discord.ui.TextDisplay(f"-# 🤖 模型版本：`{used_model}`"))

                    view = discord.ui.LayoutView()
                    view.add_item(container)
                    await message.channel.send(view=view)

            except Exception as e:
                print(f"Gemini API 發生錯誤: {e}")
                theErrorEmbed = discord.Embed(color=config.color_error)
                theErrorEmbed.description = f'```\n{str(e)[:4000]}\n```'
                await message.channel.send('因為劉東鑫超可憐叫Gemini寫程式碼所以導致的錯誤', embed=theErrorEmbed)

    @commands.command(name="clear_gemini", aliases=["reset_gemini", "清除對話", "重置紀錄"])
    async def clear_gemini(self, ctx: commands.Context):
        """清除當前頻道的 Gemini 對話紀錄"""
        channel_id = str(ctx.channel.id)
        self.history_data[channel_id] = []
        await self.save_history()
        await ctx.send("🧹 已成功清除本頻道的 Gemini 對話紀錄！")

async def setup(bot: commands.Bot):
    await bot.add_cog(Gemini(bot))