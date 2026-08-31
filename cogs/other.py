# cogs/other.py
import discord
from discord import app_commands
from discord.ext import commands

class Other(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def embedex(self, ctx):
        file = discord.File("./data/first-bot-embed-example.png", filename="first-bot-embed-example.png")
        await ctx.send(file = file)

    @commands.command()
    @commands.is_owner()
    async def say(self, ctx, *, message:str):
        await ctx.message.delete();
        await ctx.send(message);

    @commands.command(aliases=["addEmoji"])
    @commands.is_owner()
    async def add_emoji(self, ctx, emoji: discord.Emoji | str, message_id:int, channel_id:int = None):
        if not channel_id:
            message = await ctx.channel.fetch_message(int(message_id));
        else:
            channel = await self.bot.fetch_channel(int(channel_id));
            message = await channel.fetch_message(int(message_id));
        await message.add_reaction(emoji);
    
    # 傳統前綴指令 (!ping)
    #@commands.command(name="ping")
    #async def ping_cmd(self, ctx: commands.Context):
    #    latency = round(self.bot.latency * 1000)
    #    await ctx.send(f"Pong! 延遲：{latency}ms")

    # 斜線指令 (/ping)
    #@app_commands.command(name="ping", description="測試機器人延遲")
    #async def ping_slash(self, interaction: discord.Interaction):
    #    latency = round(self.bot.latency * 1000)
    #    await interaction.response.send_message(f"Pong! 延遲：{latency}ms")

async def setup(bot: commands.Bot):
    await bot.add_cog(Other(bot))