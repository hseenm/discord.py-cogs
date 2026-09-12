# cogs/example.py
import discord
from discord import app_commands
from discord.ext import commands
import random

class Example(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name='keepbadge', description='繼續保持活躍開發者')
    async def keepbadge(self, interaction: discord.Interaction):
        if interaction.guild != None:
            guild = interaction.guild
        else:
            guild = self.bot.get_guild(880829629143842857)
        list = [emoji for emoji in guild.emojis]
        emoji = random.choice(list)
        while emoji.available == False:
            emoji = random.choice(list)
        a = ''
        if emoji.animated == True: a ='a'
        await interaction.response.send_message(content=f'神啊千分萬分感謝您的大恩大德，主的徽章又活了起來<{a}:{emoji.name}:{emoji.id}>\n哦話說徽章已經被discord拔掉了，這個指令目前0意義')

async def setup(bot: commands.Bot):
    await bot.add_cog(Example(bot))