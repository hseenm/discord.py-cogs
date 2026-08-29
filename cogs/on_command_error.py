# cogs/on_command_error.py
import os
import traceback
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

class CommandErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 註冊斜線指令的全域錯誤監聽
        bot.tree.on_error = self.on_app_command_error

    def log_error(self, user: discord.User | discord.Member, guild_str: str, channel_str: str, content: str, error: Exception):
        """共用日誌寫入函式"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        original = getattr(error, "original", error)
        tb_lines = traceback.format_exception(type(original), original, original.__traceback__)
        tb_str = ''.join(tb_lines)

        log_entry = (
            f"[{now}] {user} ({user.id}) in {guild_str}#{channel_str}:\n"
            f"Content: {content}\n"
            f"{tb_str}\n"
            f"{'-'*60}\n"
        )
        
        os.makedirs("./data", exist_ok=True)
        with open("./data/error.log", "a", encoding="utf-8") as f:
            f.write(log_entry)

    # 1. 監聽傳統前綴指令錯誤
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 忽略找不到指令的錯誤
        if isinstance(error, commands.CommandNotFound):
            return

        guild_str = f"{ctx.guild.name}({ctx.guild.id})" if ctx.guild else "DirectMessage"
        channel_str = str(ctx.channel)
        content_str = ctx.message.content if ctx.message else "None"

        # 寫入日誌
        self.log_error(ctx.author, guild_str, channel_str, content_str, error)

        # 組合回覆 Embed
        description = f"```py\n{repr(error)}\n```"
        if isinstance(error, commands.MissingRequiredArgument):
            cmd_name = ctx.command.name if ctx.command else "未知指令"
            params = " ".join([
                f"<{k}>" if p.default == p.empty else f"[{k}]"
                for k, p in ctx.command.clean_params.items()
            ])
            usage = f"{ctx.prefix}{cmd_name} {params}"
            description = f"```py\n{repr(error)}\n{usage}\n```"

        embed = discord.Embed(color=0xFF3C3C, title='🛑 | 錯誤 Error', description=description)
        await ctx.send(embed=embed)

    # 2. 監聽斜線指令錯誤
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        guild_str = f"{interaction.guild.name}({interaction.guild.id})" if interaction.guild else "DirectMessage"
        channel_str = str(interaction.channel)
        cmd_name = interaction.command.name if interaction.command else "SlashCommand"

        # 寫入日誌
        self.log_error(interaction.user, guild_str, channel_str, f"/{cmd_name}", error)

        embed = discord.Embed(color=0xFF3C3C, title='🛑 | 斜線指令錯誤 Error', description=f"```py\n{repr(error)}\n```")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CommandErrorHandler(bot))