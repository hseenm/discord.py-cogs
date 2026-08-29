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

detecting = False

# 從 brown 詞庫建立一份詞表（轉小寫、去重）
brown_words = set(word.lower() for word in nltk_words.words())

class ezwordle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.answer = None
        #detecting = False
        self.answercount = 0
        self.wordlechannel = None
        self.hint = 0
        self.damn1 = self.damn2 = self.damn3 = self.damn4 = self.damn5 = True
        self.enchant_dict = enchant.Dict("en_US")
        self.enchant_dictb = enchant.Dict("en_GB")

    def is_valid_word(self, word, ab):
        #global detecting
        in_enchant = self.enchant_dict.check(word)
        in_enchantb = self.enchant_dictb.check(word)
        #in_brown = word in brown_words
        if ab == 'b':
            if not (in_enchant or in_enchantb):
                print(f"❌ '{word}' 不在 enchant 字典中")
            #if not in_brown:
            #    print(f"❌ '{word}' 不在 words 詞庫中")
        return in_enchant or in_enchantb

    def load_emojimap(self):
        with open("./data/emojimap.json", "r", encoding="utf-8") as f:
            return json.load(f)

    #def save_data(self, data):
    #    with open("./data/emojimap.json", "w", encoding="utf-8") as f:
    #        json.dump(data, f, ensure_ascii=False, indent=4)

    @app_commands.command(name='ezwordle', description='wordle')
    @app_commands.describe(threads='選擇要不要使用討論串', answercount='可以指定要幾個字元')
    async def ezwordle(self, interaction: discord.Interaction, answercount:str = None, threads: bool = None):
        global detecting
        if detecting == True:
            await interaction.response.send_message(content=f'請先使用`我認輸，可以給答案了`或者將單字猜出來結束上一場遊戲\n遊戲可能位於 <#{self.wordlechannel}>')
        elif detecting == False:
            if threads == True:
                threadhint = '隨後請於機器人創立的討論串中進行猜答\n'
            else:
                threadhint = ''
            answercountlist = ['3', '4', '5', '6', '7', '8', '9', '10']
            if answercount and (answercount not in answercountlist):
                await interaction.response.send_message(content=f'請輸入 `{" ".join(answercountlist)}` 的其中一個')
                return
            chance = ''
            if not answercount:
                answercount = random.choices(answercountlist, weights=[10, 15, 20, 40, 5, 5, 3, 2])[0]
                chance = '\n字母數出現的機率如下\n`  3   4   5   6   7   8   9  10`\n`10% 15% 20% 40%  5%  5%  3%  2%`'
            #answercount = random.choice([3, 4, 5, 5, 6, 6, 6])
            embed = discord.Embed(  colour=0xf4cc3a, 
                                    title ='<:cjzcj04m3:1220986072906076170> | Wordle',
                                    description=f'''
                                                {threadhint}隨機有點久，請耐心等候，當機器人傳“**開始遊戲**”時，即開始遊戲
                                                請使用小寫字母
                                                出現的單字將是 **{answercount}** 個字母{chance}
                                                在訊息欄輸入 `我認輸，可以給答案了` 即可結束遊戲
                                                -# 因為 iOS 系統原因，正確字母之 emoji 不會正常顯示
                                                -# 建議遊玩系統為 Windows 以及 Android
                                                ''')
            await interaction.response.send_message(embed=embed)
            detecting = True
            if threads == True:
                message = interaction.channel.last_message
                threadschannel = await interaction.channel.create_thread(name='EZWordle', message=message)
            #words = words.words()
            #word_list = nltk_words.words()
            #fdist = FreqDist(word.lower() for word in word_list if word.isalpha())
            #common_words = [w for w, _ in fdist.most_common(5000)]
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
            if threads == True:
                self.wordlechannel = threadschannel.id
                await threadschannel.send(f'開始遊戲({position}/5000)')
            else:
                self.wordlechannel = interaction.channel.id
                await interaction.channel.send(f'開始遊戲({position}/5000)')

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"[{now}] \n({position}/5000)這次的答案為 {answer} \n{'-'*60}\n"
            with open("./data/wordle.log", "a", encoding="utf-8") as f:
                f.write(log_entry)

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
        if detecting:
            if message.content == '我認輸，可以給答案了' or content.lower() == self.answer:
                if content.lower() == self.answer:
                    await message.add_reaction('<:114514:1382967646902816849>')
                if message.content == '我認輸，可以給答案了':
                    await message.channel.send(f"遊戲結束，正確答案為 `{self.answer}`")
                self.answer = None
                self.answercount = 0
                self.wordlechannel = None
                self.damn1 = self.damn2 = self.damn3 = self.damn4 = self.damn5 = True
                detecting = False
                self.hint = 0
            else:
                if message.content == '/hint':
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
                                listhint[chosen_index] = f':regional_indicator_{hint}:'
                            else:
                                listhint[i] = '⬛'
                        printt = ' '.join(listhint)
                        #print(printt)
                        content = ''.join(listctx)
                        await message.delete()
                        await asyncio.sleep(1)
                        await message.channel.send(f'`{content}` → {printt} #**{message.author.display_name}**')
                elif len(content) == self.answercount and message.channel.id == self.wordlechannel:
                    await message.delete()
                    if self.is_valid_word(content, 'b'):
                        list0 = list(self.answer)
                        list1 = list(content)
                        list2 = copy.deepcopy(list1[:self.answercount])
                        for i in range(self.answercount):
                            list1[i] = list1[i].lower()
                            if list1[i] == list0[i]:
                                list2[i] = f':regional_indicator_{list1[i]}:'
                                #list2[i] = f'🟩'
                            elif list1[i] in list0:
                                #list2[i] = f'`{list1[i]}`'
                                list2[i] = emojimap[list1[i]]
                            else:
                                list2[i] = emojimap[f'{list1[i]}_']
                        printt = ' '.join(list2)
                    else:
                        printt = '❌'
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
                    await message.channel.send(f'`{content}` → {printt} #**{message.author.display_name}**', silent=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ezwordle(bot))