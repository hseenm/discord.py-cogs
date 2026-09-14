# cogs/other.py
import discord
from discord import app_commands
from discord.ext import commands
import random
import config

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

    @commands.command(aliases=['send'])
    @commands.is_owner()
    async def sendemoji(self, ctx, name, value):
        await ctx.message.delete();
        await ctx.send(f'<:{name}:{value}>')

    @commands.command(aliases=["addEmoji"])
    @commands.is_owner()
    async def add_emoji(self, ctx, emoji: discord.Emoji | str, message_id:int, channel_id:int = None):
        if not channel_id:
            message = await ctx.channel.fetch_message(int(message_id));
        else:
            channel = await self.bot.fetch_channel(int(channel_id));
            message = await channel.fetch_message(int(message_id));
        await message.add_reaction(emoji);

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

    @commands.command(name="ping")
    async def ping_cmd(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! 延遲：{latency}ms")

    # 斜線指令 (/ping)
    @app_commands.command(name="ping", description="測試機器人延遲")
    async def ping_slash(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! 延遲：{latency}ms")
    
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

    @app_commands.command(name='冰凍', description='你快被豆腐貓咪溫暖死了嗎')
    async def freeze(self, interantion: discord.Interaction, member:discord.Member = None):
        if member == None:
            freezer = interantion.user
        else:
            freezer = member
        embed = discord.Embed(color=config.color_blue, title='❄️ | 冰凍', description=f'<@{freezer.id}> 感到很涼爽')
        embed.set_footer(text='還好沒被豆腐貓咪燙死，下次看好 *warn 再送出')
        await interantion.response.send_message(embed=embed)
    
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