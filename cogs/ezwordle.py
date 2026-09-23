# cogs/ezwordle.py
import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone
import json
import nltk
from nltk.corpus import words as nltk_words
from nltk.corpus import brown
from nltk.probability import FreqDist
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet as wn
import enchant
from wordfreq import top_n_list
from urllib.parse import urlparse
import asyncio
import copy
import config

detecting = False

# 從 brown 詞庫建立一份詞表（轉小寫、去重）
brown_words = set(word.lower() for word in nltk_words.words())

class ezwordle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.answer = None
        #detecting = False
        self.answercount = 0
        self.wordleguild = None
        self.wordlechannel = None
        self.hint = 0
        self.damn1 = self.damn2 = self.damn3 = self.damn4 = self.damn5 = True
        self.enchant_dict = enchant.Dict("en_US")
        self.enchant_dictb = enchant.Dict("en_GB")

    def produce_answercount(self):
            answercountlist = ['3', '4', '5', '6', '7', '8', '9', '10']
            answercount_ramdoned = random.choices(answercountlist, weights=[5, 15, 20, 50, 4, 3, 2, 1])[0]
            chance = '\n字母數出現的機率如下\n`  3   4   5   6   7   8   9  10`\n` 5% 15% 20% 50%  4%  3%  2%  1%`'
            chance_big = '\n字母數出現的機率如下\n```\n  3   4   5   6   7   8   9  10\n 5% 15% 20% 50%  4%  3%  2%  1%\n```'
            return answercount_ramdoned, chance_big

    def is_valid_word(self, word, ab):
        #global detecting
        in_enchant = self.enchant_dict.check(word)
        in_enchantb = self.enchant_dictb.check(word)
        return in_enchant or in_enchantb

    def begin_embed(self, threads, answercount):
        threadhint = '隨後請於機器人創立的討論串中進行猜答\n' if threads else ''
        if answercount:
            answercount_ramdoned = answercount
            chance = ''
        else:
            answercount_ramdoned, chance = self.produce_answercount()
        return discord.Embed(   colour=config.color_start, 
                                title ='<:cjzcj04m3:1220986072906076170> | Wordle',
                                description=f'{threadhint}隨機有點久，請耐心等候\n當機器人傳 **開始遊戲** 時，即開始遊戲\n人名地名需首字大寫(或全字大寫)\n其餘單字可以全大寫、全小寫或首字母大寫\n若大小寫混用(例如: aUDiO)就會不行\n出現的單字將是 **{answercount_ramdoned}** 個字母{chance}\n在訊息欄輸入 `我認輸，可以給答案了` 即可結束遊戲') , answercount_ramdoned

    def begin_container(self, threads, answercount):
        threadhint = '隨後請於機器人創立的討論串中進行猜答\n' if threads else ''
        if answercount:
            answercount_ramdoned = answercount
            chance = ''
        else:
            answercount_ramdoned, chance = self.produce_answercount()
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f'## <:cjzcj04m3:1220986072906076170> | Wordle\n{threadhint}當機器人傳 **開始遊戲** 時，即開始遊戲'))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay('大小寫可隨意混用\n開始遊戲後的數字為單字在列表中的先後順序\n可能伴隨著此次單字的難易度\n僅供參考'))
        container.add_item(discord.ui.TextDisplay(f'出現的單字將是 **{answercount_ramdoned}** 個字母{chance}'))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay('輸入 `我認輸，可以給答案了` 即可結束遊戲'))
        view = discord.ui.LayoutView()
        view.add_item(container)
        return view, answercount_ramdoned

    def load_emojimap(self):
        with open("./data/emojimap.json", "r", encoding="utf-8") as f:
            return json.load(f)

    #def save_data(self, data):
    #    with open("./data/emojimap.json", "w", encoding="utf-8") as f:
    #        json.dump(data, f, ensure_ascii=False, indent=4)

    async def randomtheWord(self, threads, channel, answercount):
        global detecting
        detecting = True
        if threads:
            message = channel.last_message
            threadschannel = await channel.create_thread(name='EZWordle', message=message)
        common_words = top_n_list('en', 5000, wordlist='best')
        lemmatizer = WordNetLemmatizer()
        print("1")
        filtered = [
            w for w in common_words
            if len(w) == int(answercount)
            and lemmatizer.lemmatize(w, pos='v') == w  # 過濾過去式、完成式
            and lemmatizer.lemmatize(w, pos='n') == w  # 過濾複數名詞
            #and self.is_valid_word(w, 'a')
        ]
        answer = random.choice(filtered)
        while not self.is_valid_word(answer, 'a'):
            answer = random.choice(filtered)
        #print("answer")
        damnwords = {"fish", "teacher"}
        while answer in damnwords:
            answer = random.choice(filtered)
        while "'" in list(answer):
            answer = random.choice(filtered)
        position = common_words.index(answer)
        position = position +1
        self.answercount = int(answercount)
        self.answer = answer
        self.wordleguild = channel.guild
        if threads == True:
            self.wordlechannel = threadschannel.id
            await threadschannel.send(f'開始遊戲({position}/5000)')
        else:
            self.wordlechannel = channel.id
            await channel.send(f'開始遊戲({position}/5000)')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{now}] \n({position}/5000)這次的答案為 {answer} \n{'-'*60}\n"
        with open("./data/wordle.log", "a", encoding="utf-8") as f:
            f.write(log_entry)


    @app_commands.command(name='ezwordle', description='wordle')
    @app_commands.describe(threads='選擇要不要使用討論串', answercount='可以指定要幾個字元')
    async def ezwordle_slash(self, interaction: discord.Interaction, answercount:str = None, threads: bool = None):
        global detecting 
        botmember = interaction.guild.me
        canManage = botmember.guild_permissions.manage_messages
        canEmoji = botmember.guild_permissions.use_external_emojis
        if detecting == True:
            embederror = discord.Embed(color=config.color_error, title=f'遊戲尚未關閉，請先結束遊戲', description=f'遊戲可能位於 <#{self.wordlechannel}>')
            embederror.set_footer(text=self.wordleguild.name, icon_url=self.wordleguild.icon.url)
            await interaction.response.send_message(embed = embederror)
        elif detecting == False:
            if not canEmoji:
                containerWarn = discord.ui.Container().add_item(discord.ui.TextDisplay('⚠️ | 此應用程式未含有使用外部表情符號之權限，遊戲無法正常運行'))
                view = discord.ui.LayoutView().add_item(containerWarn)
                await interaction.response.send_message(view=view)
            else:
                answercountlist = ['3', '4', '5', '6', '7', '8', '9', '10']
                if answercount and (answercount not in answercountlist):
                    await interaction.response.send_message(content=f'請輸入 `{" ".join(answercountlist)}` 的其中一個')
                    return
                view, answercount_ramdoned = self.begin_container(threads, answercount)
                await interaction.response.send_message(view=view)
                await self.randomtheWord(threads, interaction.channel, answercount_ramdoned)
                if not canManage:
                    containerWarn = discord.ui.Container().add_item(discord.ui.TextDisplay('⚠️ | 此應用程式未含有刪除訊息之權限，可能導致遊戲錯誤或凌亂'))
                    view = discord.ui.LayoutView().add_item(containerWarn)
                    await interaction.channel.send(view=view)

    #@commands.command(aliases=["ezwordle"])
    #async def ezwordle_trad(self, ctx, answercount:str = None, threads: bool = None):
    #    global detecting
    #    if detecting == True:
    #        embederror = discord.Embed(color=config.color_error, title=f'遊戲尚未關閉，請先結束遊戲', description=f'遊戲可能位於 <#{self.wordlechannel}>')
    #        embederror.set_footer(text=self.wordleguild.name, icon_url=self.wordleguild.icon.url)
    #        await ctx.reply(embed = embederror, mention_author=False)
    #    elif detecting == False:
    #        answercountlist = ['3', '4', '5', '6', '7', '8', '9', '10']
    #        if answercount and (answercount not in answercountlist):
    #            await ctx.reply(content=f'請輸入 `{" ".join(answercountlist)}` 的其中一個',mention_author=False)
    #            return
    #        embed, answercount_ramdoned = self.begin_embed(threads, answercount)
    #        await ctx.reply(embed=embed,mention_author=False)
    #        #await ctx.message.delete()
    #        await self.randomtheWord(threads, ctx.channel, answercount_ramdoned)


    @commands.Cog.listener()
    async def on_message(self, message):
        global detecting
        emojimap = self.load_emojimap()
        if message.author == self.bot.user:
            return
        # 讓指令能正常運作（因為 on_message 會阻擋 commands 的處理）
        #await self.bot.process_commands(message)
        # 偵測狀態
        content = message.content
        if detecting and message.channel.id == self.wordlechannel:
            if message.content == '我認輸，可以給答案了':# or content.lower() == self.answer:
                #if content.lower() == self.answer:
                #    await message.add_reaction('<:114514:1382967646902816849>')
                #if message.content == '我認輸，可以給答案了':
                await message.channel.send(f"遊戲結束，正確答案為 `{self.answer}`")
                self.answer = None
                self.answercount = 0
                self.wordlechannel = None
                self.damn1 = self.damn2 = self.damn3 = self.damn4 = self.damn5 = True
                detecting = False
                self.hint = 0
            elif message.content in ('/hint', '*hint'):
                if self.answercount >= 7 or self.hint <= 2:
                    if self.answercount <= 7:
                        self.hint = self.hint + 1
                    #print('hint')
                    listraw = list(self.answer)
                    listctx = []
                    for k in range(self.answercount):
                        listctx.append(' ')
                    listhint = copy.deepcopy(listctx[:self.answercount])
                    hint = random.choice(listraw)
                    all_indices = [i for i, x in enumerate(listraw) if x == hint]
                    chosen_index = random.choice(all_indices)
                    listctx[chosen_index] = hint
                    for i in range(self.answercount):
                        if i == chosen_index:
                            listhint[chosen_index] = emojimap[f"{hint.upper()}co"]
                        else:
                            listhint[i] = '⬛'
                    printt = ' '.join(listhint)
                    #print(printt)
                    content = ''.join(listctx)
                    await message.delete()
                    await asyncio.sleep(1)
                    await message.channel.send(f'`{content}` → {printt} #**{message.author.display_name}**')
            elif len(content) == self.answercount:
                if self.is_valid_word(content, 'b') or self.is_valid_word(content.lower(), 'b') or self.is_valid_word(content.lower().capitalize(), 'b'):
                    list0 = list(self.answer)
                    list1 = list(content)
                    list2 = copy.deepcopy(list1[:self.answercount])
                    for i in range(self.answercount):
                        list1[i] = list1[i].lower()
                        if list1[i] == list0[i]:
                            list2[i] = emojimap[f"{list1[i].upper()}co"]
                            #list2[i] = f'🟩'
                        elif list1[i] in list0:
                            #list2[i] = f'`{list1[i]}`'
                            list2[i] = emojimap[list1[i]]
                        else:
                            list2[i] = emojimap[f'{list1[i]}_']
                    printt = ' '.join(list2)
                else:
                    listprintt = ['❌']
                    for i in range(self.answercount-1):
                        listprintt.append(':black_large_square:')
                    printt = ' '.join(listprintt)
                guild = await self.bot.fetch_guild(1175052405776318466)
                if message.guild == guild and len(content) == self.answercount:
                    if self.damn1 == True and content == 'fish':
                        printt = '<:emoji_19:1384527296605589595>'
                        self.damn1 = False
                    #elif bot.damn2 == True and message.content == 'dick':
                    #    printt = '<:wow:978303515560656906>'
                    #    bot.damn2 = False
                    #elif bot.damn3 == True and message.content == 'damn':
                    #    printt = '<:emoji_25:1394640873291251723>'
                    #    bot.damn3 = False
                    elif self.damn4 == True  and content == 'teacher':
                        printt = '<:mr_Chen:957204698555891742>'
                        self.damn4 = False
                    #elif bot.damn5 == True and message.content == 'summer':
                    #    printt = '<:summer_:1329781718554775572>'
                    #    bot.damn5 = False
                #await asyncio.sleep(1)
                try:
                    await message.delete()
                except:
                    pass
                maybeaddemojimessage = await message.channel.send(f'`{content}` → {printt} #**{message.author.display_name}**', silent=True)
                if content.lower() == self.answer:
                    await maybeaddemojimessage.add_reaction('<:114514:1382967646902816849>' if message.guild == guild else '<:aa10:1005430382759526450>')
                    self.answer = None
                    self.answercount = 0
                    self.wordlechannel = None
                    self.damn1 = self.damn2 = self.damn3 = self.damn4 = self.damn5 = True
                    detecting = False
                    self.hint = 0

async def setup(bot: commands.Bot):
    await bot.add_cog(ezwordle(bot))