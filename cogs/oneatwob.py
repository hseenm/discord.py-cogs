# cogs/1a2b.py
import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone
import copy
import config

detectingfor1a2b = False

class Oneatwob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.answer = ''
        self.container = discord.ui.Container()
        self.container.add_item(discord.ui.TextDisplay('## <:cjzcj04m3:1220986072906076170> | 1A2B\n請直接與聊天欄輸入不重複的四位數字以開始遊戲\n在訊息欄輸入 `我認輸，可以給答案了` 即可結束遊戲'))
        self.view = discord.ui.LayoutView()
        self.view.add_item(self.container)
        #self.embed = discord.Embed( colour=config.color_start, 
        #                            title ='<:cjzcj04m3:1220986072906076170> | 1A2B',
        #                            description=f'''
        #                                        請直接與聊天欄輸入不重複的四位數字以開始遊戲;
        #                                        在訊息欄輸入 `我認輸，可以給答案了` 即可結束遊戲
        #                                        ''')

    def is_valid_number(self, number):
        return (len(set(str(number))) == 4)

    async def oneatwobcode(self, channel):
        global detectingfor1a2b
        detectingfor1a2b = True
        digits = random.sample("0123456789", 4)
        answer = "".join(digits)
        self.answer = answer
        self.wordlechannel = channel.id
        #await channel.send(f'開始遊戲')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{now}] \n這次的答案為 {answer} \n{'-'*60}\n"
        with open("./data/1a2b.log", "a", encoding="utf-8") as f:
            f.write(log_entry)

    @app_commands.command(name='1a2b', description='the multiplayer version')
    #@app_commands.describe(threads='選擇要不要使用討論串')
    async def oneatwob_slash(self, interaction: discord.Interaction):
        global detectingfor1a2b
        if detectingfor1a2b == True:
            await interaction.response.send_message(content=f'請先使用`我認輸，可以給答案了`或者將數字猜出來結束上一場遊戲\n遊戲可能位於 <#{self.wordlechannel}>')
        elif detectingfor1a2b == False:
            await interaction.response.send_message(view=self.view)
            await self.oneatwobcode(interaction.channel)

    @commands.command(aliases=["1a2b"])
    async def oneatwob_trad(self, ctx: commands.Context):
        global detectingfor1a2b
        if detectingfor1a2b == True:
            await ctx.send(f'請先使用`我認輸，可以給答案了`或者將數字猜出來結束上一場遊戲\n遊戲可能位於 <#{self.wordlechannel}>')
        elif detectingfor1a2b == False:
            await ctx.send(view=self.view)
            await self.oneatwobcode(ctx.channel)

    @commands.Cog.listener()
    async def on_message(self, message):
        global detectingfor1a2b
        #emojimap = self.load_emojimap()
        if message.author == self.bot.user:
            return
        # 讓指令能正常運作（因為 on_message 會阻擋 commands 的處理）
        #await self.bot.process_commands(message)
        # 偵測狀態
        content = message.content
        if detectingfor1a2b:
            if message.content == '我認輸，可以給答案了' or content == self.answer:
                if content.lower() == self.answer:
                    await message.add_reaction('<:114514:1382967646902816849>')
                if message.content == '我認輸，可以給答案了':
                    await message.channel.send(f"遊戲結束，正確答案為 `{self.answer}`")
                self.answer = ''
                self.wordlechannel = None
                detectingfor1a2b = False
            else:
                if len(content) == 4 and message.channel.id == self.wordlechannel:
                    await message.delete()
                    A=B=0
                    if self.is_valid_number(content):
                        #print(True)
                        list0 = list(self.answer)
                        list1 = list(content)
                        list2 = copy.deepcopy(list1)
                        #print(True)
                        for i in range(4):
                            if list1[i] == list0[i]:
                                A = A + 1
                            elif list1[i] in list0:
                                B = B + 1
                            else:
                                pass
                        #print(True)
                        printt = f'`{str(A)}A{str(B)}B`'
                    else:
                        printt = '❌'
                    await message.channel.send(f'`{content}` → {printt} #**{message.author.display_name}**', silent=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Oneatwob(bot))