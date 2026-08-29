# cogs/gemini.py
import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
import config

AI_API = config.AI_API
gemini_client = genai.Client(api_key=AI_API)

class Gemini(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if '<@896959002292920331>' in message.content:
            try:
                async with message.channel.typing():
                    response = gemini_client.models.generate_content(
                        model='gemini-flash-latest',
                        contents=message.content,
                        config=types.GenerateContentConfig(
                            #system_instruction=(
                            #    "你現在是一個早期AI程式。"
                            #    "說話風格像機器人。"
                            #    "請嚴格遵守以下規則：\n"
                            #    "1. 語氣冰冷、機械化、鮮少情感。\n"
                            #    "2. 句子盡量生硬。"
                            #)
                        )
                    )
                    await message.channel.send(response.text[:2000])
            except Exception as e:
                print(f"Gemini API 發生錯誤: {e}")
                theErrorEmbed = discord.Embed(color=0xFF0000)
                theErrorEmbed.description = f'```\n{e}\n```'
                await message.channel.send('因為劉東鑫超可憐叫Gemini寫程式碼所以導致的錯誤', embed = theErrorEmbed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Gemini(bot))