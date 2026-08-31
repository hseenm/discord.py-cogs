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
        # 註冊斜線指令全域錯誤監聽
        bot.tree.on_error = self.on_app_command_error

    def log_error(self, user: discord.User | discord.Member, guild_str: str, channel_str: str, content: str, error: Exception):
        """日誌寫入函式"""
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

    # 1. 處理前綴指令錯誤
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # 忽略找不到指令
        if isinstance(error, commands.CommandNotFound):
            return

        guild_str = f"{ctx.guild.name}({ctx.guild.id})" if ctx.guild else "DirectMessage"
        channel_str = str(ctx.channel)
        content_str = ctx.message.content if ctx.message else "None"

        # 寫入日誌
        self.log_error(ctx.author, guild_str, channel_str, content_str, error)

        # 錯誤分類與中文說明
        title = "🛑 | 指令執行錯誤"
        
        # 取得指令名稱與帶型態的參數用法
        cmd_name = ctx.command.name if ctx.command else "未知指令"
        if ctx.command:
            params_list = []
            for name, param in ctx.command.clean_params.items():
                # 取得型別名稱（例如 int, str, bool），若未標註則只顯示參數名
                type_name = param.annotation.__name__ if hasattr(param.annotation, "__name__") else ""
                type_str = f": {type_name}" if type_name and type_name != "_empty" else ""

                # 判斷是否為預設值/可選參數 (預設為 empty 代表必填)
                if param.default == param.empty:
                    params_list.append(f"<{name}{type_str}>")
                else:
                    params_list.append(f"[{name}{type_str}]")
            
            usage = f"{ctx.prefix}{cmd_name} {' '.join(params_list)}"
        else:
            usage = f"{ctx.prefix}{cmd_name}"

        # 1. 缺少必填參數
        if isinstance(error, commands.MissingRequiredArgument):
            title = "⚠️ | 缺少必要參數"
            description = f"你漏填了必要參數：`{error.param.name}`\n\n**正確用法：**\n`{usage}`"

        # 2. 參數型態或內容錯誤
        elif isinstance(error, commands.BadArgument):
            title = "⚠️ | 參數型態錯誤"
            description = f"輸入的參數格式或型態不正確。\n\n**正確用法：**\n`{usage}`"

        elif isinstance(error, commands.MissingPermissions):
            title = "🚫 | 權限不足"
            perms = "、".join([f"`{p}`" for p in error.missing_permissions])
            description = f"你缺乏執行此指令所需的權限：{perms}"

        elif isinstance(error, commands.BotMissingPermissions):
            title = "🤖 | 機器人權限不足"
            perms = "、".join([f"`{p}`" for p in error.missing_permissions])
            description = f"機器人在當前頻道缺少必要權限：{perms}，請聯絡管理員設定。"

        elif isinstance(error, commands.CommandOnCooldown):
            title = "⏳ | 指令冷卻中"
            description = f"指令使用太頻繁，請等待 **{error.retry_after:.1f}** 秒後再試。"

        elif isinstance(error, commands.NoPrivateMessage):
            title = "🚫 | 無法在私訊使用"
            description = "此指令僅限於伺服器頻道中使用，無法在私訊執行。"

        elif isinstance(error, commands.CheckFailure):
            title = "🔒 | 檢查未通過"
            description = "你不符合執行此指令的條件或身分組限制。"

        else:
            # 未預期錯誤，顯示原始例外訊息
            description = f"發生未預期的系統錯誤：\n```py\n{repr(error)}\n```"

        embed = discord.Embed(title=title, description=description, color=0xFF3C3C)
        await ctx.reply(embed=embed, mention_author=False)

    # 2. 處理斜線指令錯誤
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        guild_str = f"{interaction.guild.name}({interaction.guild.id})" if interaction.guild else "DirectMessage"
        channel_str = str(interaction.channel)
        cmd_name = interaction.command.name if interaction.command else "SlashCommand"

        # 寫入日誌
        self.log_error(interaction.user, guild_str, channel_str, f"/{cmd_name}", error)

        # 錯誤分類與中文說明
        title = "🛑 | 斜線指令錯誤"

        if isinstance(error, app_commands.CommandOnCooldown):
            title = "⏳ | 指令冷卻中"
            description = f"指令冷卻中，請在 **{error.retry_after:.1f}** 秒後再試。"

        elif isinstance(error, app_commands.MissingPermissions):
            title = "🚫 | 權限不足"
            perms = "、".join([f"`{p}`" for p in error.missing_permissions])
            description = f"你缺乏執行此斜線指令的權限：{perms}"

        elif isinstance(error, app_commands.BotMissingPermissions):
            title = "🤖 | 機器人權限不足"
            perms = "、".join([f"`{p}`" for p in error.missing_permissions])
            description = f"機器人缺少執行所需的權限：{perms}"

        elif isinstance(error, app_commands.CheckFailure):
            title = "🔒 | 檢查未通過"
            description = "你不符合執行此斜線指令的條件限制。"

        else:
            description = f"執行時發生未預期的錯誤：\n```py\n{repr(error)}\n```"

        embed = discord.Embed(title=title, description=description, color=0xFF3C3C)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CommandErrorHandler(bot))