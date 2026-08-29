# cogs/exam.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import random
from datetime import datetime, timedelta, timezone

class tof(discord.ui.View):
    def __init__(self, answer, timeout=180):
        super().__init__(timeout=timeout)
        self.answer = answer
    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji = '⭕')
    async def click1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.answer == '○':
            button.style = discord.ButtonStyle.green
            button.label = "答案正確"
            button.disabled = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
        else:
            button.style = discord.ButtonStyle.danger
            button.label = "答案錯誤"
            button.disabled = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji = '❌')
    async def click2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.answer == 'X':
            button.style = discord.ButtonStyle.green
            button.label = "答案正確"
            button.disabled = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)
        else:
            button.style = discord.ButtonStyle.danger
            button.label = "答案錯誤"
            button.disabled = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)

class opt(discord.ui.View):
    def __init__(self, answer, timeout=180):
        super().__init__(timeout=timeout)
        emoji_map = {
            '1': '1️⃣',
            '2': '2️⃣',
            '3': '3️⃣',
        }
        correct = emoji_map.get(answer, answer)
        self.answer = correct
    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji = '1️⃣')
    async def click1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.answer == '1️⃣':
            button.style = discord.ButtonStyle.green
            button.label = "答案正確"
            button.disabled = True
        else:
            button.style = discord.ButtonStyle.danger
            button.label = "答案錯誤"
            button.disabled = True
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.emoji.name == self.answer:
                    child.style = discord.ButtonStyle.green  
                    child.label = "正解"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji = '2️⃣')
    async def click2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.answer == '2️⃣':
            button.style = discord.ButtonStyle.green
            button.label = "答案正確"
            button.disabled = True
        else:
            button.style = discord.ButtonStyle.danger
            button.label = "答案錯誤"
            button.disabled = True
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.emoji.name == self.answer:
                    child.style = discord.ButtonStyle.green  
                    child.label = "正解"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji = '3️⃣')
    async def click3(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.answer == '3️⃣':
            button.style = discord.ButtonStyle.green
            button.label = "答案正確"
            button.disabled = True
        else:
            button.style = discord.ButtonStyle.danger
            button.label = "答案錯誤"
            button.disabled = True
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.emoji.name == self.answer:
                    child.style = discord.ButtonStyle.green  
                    child.label = "正解"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

class exam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def load_tof(self):
            with open("./data/output.json", "r", encoding="utf-8") as f:
                return json.load(f)
    def load_opt(self):
            with open("./data/optional.json", "r", encoding="utf-8") as f:
                return json.load(f)

    @app_commands.command(name='exam', description='考個駕照吧')
    async def exam(self, interaction: discord.Interaction):
        tiku = random.choice([self.load_tof(), self.load_opt()])
        item = random.choice(tiku)
        if tiku is self.load_tof():
            view=tof(item["answer"])
            content = '是非題'
        elif tiku is self.load_opt():
            view=opt(item["answer"])
            content = '選擇題'
        embed = discord.Embed(color=0xF27D72, title=f'📜 | 中華民國公路局-機車駕照筆試題庫(法規{content}.`{item["number"]}`)', description=f'```\n{item["question"]}\n```',timestamp=datetime.now())
        embed.set_footer(icon_url='https://cdn.discordapp.com/emojis/1329781718554775572.png?size=160',text='祝你考試順利')
        await interaction.response.send_message(embed=embed, view=view)

# 每個 Cog 檔案底部一定要有這個 setup 函式
async def setup(bot: commands.Bot):
    await bot.add_cog(exam(bot))