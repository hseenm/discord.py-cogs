# cogs/calendar.py
import discord
from discord import app_commands
from discord.ext import commands

class calendar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='calendar', description='詳細請自己做做看')
    @app_commands.describe(year = '指定的年份', month = '指定的月份', day='指定的日期')
    async def calendarhaha(self, interaction: discord.Interaction, year:int=None, month:int=None, day:int=None):
        calendar.setfirstweekday(6)
        message = None
        if year==None and month==None and day==None:
            nowyear = datetime.now().year
            nowmonth = datetime.now().month
            description = calendar.month(nowyear, nowmonth)
        elif year!=None:
            print(month)
            if month==None:
                description = calendar.calendar(year, c=2)
                if day!=None:
                    message = f'老哥，自己找你要的{day}號'
            elif month != None:
                if day == None:
                    description = calendar.month(year, month)
                elif day != None:
                    day_of_week = calendar.weekday(year, month, day)
                    day_of_week = day_of_week + 1
                    num_to_chinese = {
                        1: '一',
                        2: '二',
                        3: '三',
                        4: '四',
                        5: '五',
                        6: '六',
                        7: '七'
                    }
                    description = f'{year}/{month}/{day} 是 禮拜{num_to_chinese(day_of_week)}'
        else:
            await interaction.response.send_message(content='看不懂啊')
        await interaction.response.send_message(content=f'```\n{description}\n```')
        if message != None:
            await interaction.channel.send(f'老哥，自己找你要的{day}號')

    # 斜線指令 (/ping)
    #@app_commands.command(name="ping", description="測試機器人延遲")
    #async def ping_slash(self, interaction: discord.Interaction):
    #    latency = round(self.bot.latency * 1000)
    #    await interaction.response.send_message(f"Pong! 延遲：{latency}ms")

# 每個 Cog 檔案底部一定要有這個 setup 函式
async def setup(bot: commands.Bot):
    await bot.add_cog(calendar(bot))