# cogs/freeze.py
import discord
from discord import app_commands
from discord.ext import commands

class freeze(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='冰凍', description='你快被豆腐貓咪溫暖死了嗎')
    async def freeze(self, interantion: discord.Interaction, member:discord.Member = None):
        if member == None:
            freezer = interantion.user
        else:
            freezer = member
        embed = discord.Embed(color=0x665732, title='❄️ | 冰凍', description=f'<@{freezer.id}> 感到很涼爽')
        embed.set_footer(text='還好沒被豆腐貓咪燙死，下次看好 *warn 再送出')
        await interantion.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(freeze(bot))