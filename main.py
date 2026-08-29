# main.py
import asyncio
import os
import discord
from discord.ext import commands
import config
import traceback
from datetime import datetime, timedelta, timezone
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger('discord.voice_client').setLevel(logging.DEBUG)

# 設定意圖 (Intents)
#gemini_client = genai.Client(api_key=AI_API)
intents = intents = discord.Intents.all()
intents.members = True
activity = discord.Streaming(name="什麼都沒有", url="https://www.youtube.com/watch?v=YDLafQ-Rg-k")
bot = commands.Bot(command_prefix= ['#','*','下巴'],intents=intents, case_insensitive=True , activity=activity)

@bot.event
async def on_ready():
    # 同步 Slash 指令到伺服器
    try:
        synced = await bot.tree.sync()
        print(f"已同步 {len(synced)} 個 Slash 指令")
    except Exception as e:
        print(f"同步指令時發生錯誤: {e}")

    print(f"機器人已上線！登入身分：{bot.user}")

@bot.command()
@commands.is_owner()  # 限制只有機器人擁有者可以執行
async def reload(ctx: commands.Context, cog_name: str):
    await ctx.send(f"正在重新整理...")
    try:
        await bot.reload_extension(f"cogs.{cog_name}")
        await ctx.send(f"✅ 成功重新載入模組：`{cog_name}`")
    except Exception as e:
        await ctx.send(f"❌ 載入模組 `{cog_name}` 失敗：\n```{e}```")

#@bot.event
#async def on_command_error(ctx, error):
#    original = getattr(error, "original", error)
#    tb_str = ''.join(traceback.format_exception(type(original), original, original.__traceback__))
#    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#    log_entry = f"[{now}] {ctx.author} ({ctx.author.id}) in {ctx.guild.name}({ctx.guild.id})#{ctx.channel}:\n{ctx.message.content}\n{tb_str}\n{'-'*60}\n"
#    with open("./data/error.log", "a", encoding="utf-8") as f:
#        f.write(log_entry)
#    if isinstance(error, commands.CommandNotFound):
#        pass
#    else:
#        description = f"```py\n{repr(error)}\n```"
#        if isinstance(error, commands.MissingRequiredArgument):
#            cmd_name = ctx.command.name if ctx.command else "未知指令"
#            params = " ".join([
#                f"<{k}>" if p.default == p.empty else f"[{k}]"
#                for k, p in ctx.command.clean_params.items()
#            ])
#            usage = f"*{cmd_name} {params}"
#            description = f"```py\n{repr(error)}\n{usage}\n```"
#        embed = discord.Embed(color=0xFF3C3C, title='🛑 | 錯誤 Error', description=description)
#        await ctx.send(embed=embed)

# 自動載入 cogs/ 內所有的 .py 模組
async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"成功載入模組: {filename}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(main())