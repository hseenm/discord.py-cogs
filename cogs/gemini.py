# cogs/gemini.py
import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
from google.genai.errors import APIError
import config
import json
import os

AI_API = config.AI_API
gemini_client = genai.Client(api_key=AI_API)
HISTORY_FILE = "./data/chat_history.json"

class Gemini(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.history_data = self.load_history()
        self.models_to_try = [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.4-flash",
            "gemini-3.3-flash",
            "gemini-3.2-flash",
            "gemini-3.1-flash",
            "gemini-3.0-flash"
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

    def save_history(self):
        """將歷史紀錄寫回 JSON 檔案"""
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.history_data, f, ensure_ascii=False, indent=2)

    def get_chat_for_channel(self, channel_id: str):
        """根據 JSON 歷史紀錄建立 chat 實例"""
        channel_history = self.history_data.get(channel_id, [])

        # 將 JSON 轉為 SDK 接受的 Content 格式
        history_contents = [
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["text"])]
            )
            for item in channel_history
        ]
        return gemini_client.aio.chats.create(
            model='gemini-3.6-flash',
            history=history_contents,
            config=types.GenerateContentConfig(
                system_instruction="說話像2020年的AI風格"
            )
        )

    async def send_message_with_fallback(self, channel_id: str, prompt: str):
        """依序嘗試備援名單中的模型，成功即回傳，全失敗才拋出例外"""
        channel_history = self.history_data.get(channel_id, [])
        history_contents = [
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["text"])]
            )
            for item in channel_history
        ]

        last_error = None

        for model_name in self.models_to_try:
            try:
                # 建立指定模型的對話
                chat = gemini_client.aio.chats.create(
                    model=model_name,
                    history=history_contents,
                    #config=types.GenerateContentConfig(
                    #    system_instruction="說話像2020年的AI風格"
                    #)
                )
                response = await chat.send_message(prompt)
                return response.text or "（無文字回應）"

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

        if '<@896959002292920331>' in message.content:
            botmember = await message.guild.fetch_member(self.bot.user.id)
            clean_prompt = message.clean_content.replace(f'@{botmember.display_name}', '').strip()
            if not clean_prompt:
                clean_prompt = "你好"

            channel_id = str(message.channel.id)

            try:
                #async with message.channel.typing():
                # 執行帶有 fallback 機制的回應生成
                reply_text = await self.send_message_with_fallback(channel_id, clean_prompt)
                # 更新並記錄至 JSON
                if channel_id not in self.history_data:
                    self.history_data[channel_id] = []
                self.history_data[channel_id].append({"role": "user", "text": clean_prompt})
                self.history_data[channel_id].append({"role": "model", "text": reply_text})
                self.history_data[channel_id] = self.history_data[channel_id][-20:]
                self.save_history()
                await message.channel.send(reply_text[:2000])
            except Exception as e:
                print(f"Gemini API 發生錯誤: {e}")
                theErrorEmbed = discord.Embed(color=0xFF0000)
                theErrorEmbed.description = f'```\n{e}\n```'
                await message.channel.send('因為劉東鑫超可憐叫Gemini寫程式碼所以導致的錯誤', embed = theErrorEmbed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Gemini(bot))