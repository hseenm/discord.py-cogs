# cogs/guessanumber.py
import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone

class guessanumber(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='guess', description='玩一個猜數字的遊戲')
    @app_commands.describe(number='從1-10猜一個數字')
    async def guess(self, interaction: discord.Interaction, number:int):
        guild = interaction.guild
        ans = random.randint(1, 10)
        bot_member = await guild.fetch_member(int(896959002292920331))
        bot_top = bot_member.top_role
        member = await guild.fetch_member(int(interaction.user.id))
        member_top = member.top_role
        #ans = 5
        if number == ans:
            await interaction.response.send_message(content=f'恭喜你猜對了，正確答案就是{ans}!')
            await interaction.channel.send('`已取消成員禁言程序`')
        elif number != ans:
            await interaction.response.send_message(content=f'超級可憐，你沒有答對\n你的答案是{number}，正確答案是{ans}，就差{abs(int(number - ans))}了')
            if (bot_top.permissions.mute_members == True) and (bot_top > member_top):
                await interaction.channel.send('即將開始執行懲罰')
                member = interaction.guild.get_member(interaction.user.id)
                now = datetime.now()
                now = now + timedelta(hours=1)
                localnow = now.astimezone()
                await member.timeout(localnow)
                embed = discord.Embed(color=0xfeccdc, title='<:aa01:1005429572583559178> MUTE | 看來今天手氣不好啊')
                embed.add_field(name='禁言者', value=f'```\n{bot_member.display_name}\n```')
                embed.add_field(name='被禁言者', value=f'```\n{member.display_name}\n```')
                embed.add_field(name='禁言時間', value=f'```\n1 Hour\n```')
                await interaction.channel.send(embed=embed)
            else:
                await interaction.channel.send('`已取消成員禁言程序`')
                embed = discord.Embed(color=0x7ef7b9, title='<:aa10:1005430382759526450> Mute Failed | 看來有天神在保佑你')
                embed.add_field(name='禁言者', value=f'~~```\n{bot_member.display_name}\n```~~')
                embed.add_field(name='被禁言者', value=f'~~```\n{member.display_name}\n```~~')
                embed.add_field(name='禁言時間', value=f'~~```\n1 Hour\n```~~')
                await interaction.channel.send(embed=embed)

    # 斜線指令 (/ping)
    #@app_commands.command(name="ping", description="測試機器人延遲")
    #async def ping_slash(self, interaction: discord.Interaction):
    #    latency = round(self.bot.latency * 1000)
    #    await interaction.response.send_message(f"Pong! 延遲：{latency}ms")

async def setup(bot: commands.Bot):
    await bot.add_cog(guessanumber(bot))