# cogs/check_all_the_commands.py
import discord
from discord import app_commands
from discord.ext import commands

class CACs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def commandss(self, ctx):
        cmd_list = []
        owner = []
        for cmd in self.bot.commands:
            # 檢查是否是 owner 限定
            is_owner_only = any(
                getattr(check, "__qualname__", "") == "is_owner.<locals>.predicate"
                for check in cmd.checks
            )
            if is_owner_only:
                owner.append(f"*{cmd.name} (owner)")
            else:
                cmd_list.append(f"*{cmd.name}")
        description = "\n".join(cmd_list + owner)
        embed = discord.Embed(description=description, color=0x00BFFF)
        await ctx.send(embed=embed)

# 每個 Cog 檔案底部一定要有這個 setup 函式
async def setup(bot: commands.Bot):
    await bot.add_cog(CACs(bot))