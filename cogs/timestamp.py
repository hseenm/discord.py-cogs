# cogs/timestamp.py
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import config
#import random

class timestamp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='timestamp', description='生成Unix時間戳')
    @app_commands.describe(year = '輸入指定時間的年份(西元)', month = '輸入指定時間的月份', day = '輸入指定時間的日期', hour = '輸入指定時間的時', minute = '輸入指定時間的分')
    async def timestamp(self, interaction: discord.Interaction, year :int = None, month:int = None, day : int =None, hour : int= None, minute:int =None, title:str =None):

        if year == None and month == None and day == None and hour == None and minute == None:
            time = datetime.now()
        else:
            if year == None: year = datetime.now().year
            if month == None: month = datetime.now().month
            if day == None: day = datetime.now().day
            if hour == None: hour = datetime.now().hour
            else: hour = hour -8
            if minute == None: minute = datetime.now().minute
            time = datetime(year, month, day, hour, minute)
        timestamp = time.timestamp()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f'''`<t:{int(timestamp)}:t>`  <t:{int(timestamp)}:t>\n`<t:{int(timestamp)}:T>`  <t:{int(timestamp)}:T>\n`<t:{int(timestamp)}:d>`  <t:{int(timestamp)}:d>\n`<t:{int(timestamp)}:D>`  <t:{int(timestamp)}:D>\n`<t:{int(timestamp)}:f>`  <t:{int(timestamp)}:f>\n`<t:{int(timestamp)}:F>`  <t:{int(timestamp)}:F>\n`<t:{int(timestamp)}:R>`  <t:{int(timestamp)}:R>'''))
        view = discord.ui.LayoutView()
        view.add_item(container)
        await interaction.response.send_message(view=view)

    # 斜線指令 (/ping)
    #@app_commands.command(name="ping", description="測試機器人延遲")
    #async def ping_slash(self, interaction: discord.Interaction):
    #    latency = round(self.bot.latency * 1000)
    #    await interaction.response.send_message(f"Pong! 延遲：{latency}ms")

async def setup(bot: commands.Bot):
    await bot.add_cog(timestamp(bot))