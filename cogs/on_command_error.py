# cogs/on_command_error.py
import discord
from discord import app_commands
from discord.ext import commands
import traceback
from datetime import datetime, timedelta, timezone

class on_command_error(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        original = getattr(error, "original", error)
        tb_str = ''.join(traceback.format_exception(type(original), original, original.__traceback__))
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{now}] {ctx.author} ({ctx.author.id}) in {ctx.guild.name}({ctx.guild.id})#{ctx.channel}:\n{ctx.message.content}\n{tb_str}\n{'-'*60}\n"
        with open("./data/error.log", "a", encoding="utf-8") as f:
            f.write(log_entry)
        if isinstance(error, commands.CommandNotFound):
            pass
        else:
            description = f"```py\n{repr(error)}\n```"
            if isinstance(error, commands.MissingRequiredArgument):
                cmd_name = ctx.command.name if ctx.command else "未知指令"
                params = " ".join([
                    f"<{k}>" if p.default == p.empty else f"[{k}]"
                    for k, p in ctx.command.clean_params.items()
                ])
                usage = f"*{cmd_name} {params}"
                description = f"```py\n{repr(error)}\n{usage}\n```"
            embed = discord.Embed(color=0xFF3C3C, title='🛑 | 錯誤 Error', description=description)
            await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(on_command_error(bot))