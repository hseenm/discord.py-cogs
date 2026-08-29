# cogs/ping.py
import discord
from discord import app_commands
from discord.ext import commands

class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 傳統前綴指令 (!ping)
    @commands.command(name="ping")
    async def ping_cmd(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! 延遲：{latency}ms")

    # 斜線指令 (/ping)
    @app_commands.command(name="ping", description="測試機器人延遲")
    async def ping_slash(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 延遲：{latency}ms")

async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))