# cogs/log.py
import discord
import json
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo #pip install tzdata

class Log(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def load_log(self):
        with open("./data/voicelog.json", "r", encoding="utf-8") as f:
            return json.load(f)
        
    def save_log(self, data: dict):
        with open("./data/voicelog.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        log = self.load_log()
        timestamp = int(datetime.now(ZoneInfo("Asia/Taipei")).timestamp())

        if before.channel == after.channel:
            if (after.deaf == True) and (before.deaf == False): action = '被拒聽'
            elif (after.deaf == False) and (before.deaf == True): action = '被解除拒聽'
            elif (after.mute == True) and (before.mute == False): action = '被靜音'
            elif (after.mute == False) and (before.mute == True): action = '被解除靜音'
            elif (after.self_deaf == True) and (before.self_deaf == False): action = '拒聽'
            elif (after.self_deaf == False) and (before.self_deaf == True): action = '解除拒聽'
            elif (after.self_mute == True) and (before.self_mute == False): action = '靜音'
            elif (after.self_mute == False) and (before.self_mute == True): action = '解除靜音'
            elif (after.self_stream == True) and (before.self_stream == False): action = '開啟直播'
            elif (after.self_stream == False) and (before.self_stream == True): action = '關閉直播'
            elif (after.self_video == True) and (before.self_video == False): action = '開啟視訊'
            elif (after.self_video == False) and (before.self_video == True): action = '關閉視訊'

            if str(after.channel.id) not in log:
                log[str(after.channel.id)] = []
            new_entry = {
                "user_id": member.id,
                "action": action,
                "time": timestamp
            }
            log[str(after.channel.id)].append(new_entry)
            if len(log[str(after.channel.id)]) > 10:
                log[str(after.channel.id)].pop(0)
            self.save_log(log)
        else:
            if (before.channel is None) and (after.channel is not None):
                actiona = '加入頻道'
                actionb = None
            elif (before.channel is not None) and (after.channel is None):
                actionb = '離開頻道'
                actiona = None
            elif (before.channel != after.channel) and ((before.channel is not None) and (after.channel is not None)):
                actionb = '離開頻道'
                actiona = '加入頻道'
            if before.channel:
                if str(before.channel.id) not in log:
                    log[str(before.channel.id)] = []
            if after.channel:
                if str(after.channel.id) not in log:
                    log[str(after.channel.id)] = []
            if actionb is not None:
                new_entryb = {
                                "user_id": member.id,
                                "action": actionb,
                                "time": timestamp
                            }
                log[str(before.channel.id)].append(new_entryb)
            if actiona is not None:
                new_entrya = {
                                "user_id": member.id,
                                "action": actiona,
                                "time": timestamp
                            }
                log[str(after.channel.id)].append(new_entrya)
            if before.channel is not None:    
                if len(log[str(before.channel.id)]) > 10:
                    log[str(before.channel.id)].pop(0)
            if after.channel is not None:
                if len(log[str(after.channel.id)]) > 10:
                    log[str(after.channel.id)].pop(0)
            self.save_log(log)

    @commands.command()
    async def log(self, ctx: commands.Context):
        log = self.load_log()
        channelID = str(ctx.channel.id)
        container = discord.ui.Container()
        if channelID not in log:
            container.add_item(discord.ui.TextDisplay('## <:mutsumix:1555501058816479342> | 該頻道無記錄'))
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)
        else:
            container.add_item(discord.ui.TextDisplay('## <:ksmnote:1555489708245786684> | 語音頻道記錄'))
            container.add_item(discord.ui.Separator())
            textList = []
            for entry in reversed(log[channelID]):
                member = await ctx.guild.fetch_member(int(entry["user_id"]))
                textList.append(f'**#{member.display_name}** {entry["action"]} <t:{entry["time"]}:T>')
            text = '\n'.join(textList)
            container.add_item(discord.ui.TextDisplay(text))
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view) 

    #@app_commands.command(name="log", description="語音頻道記錄")
    #async def ping_slash(self, interaction: discord.Interaction):
    #    container = discord.ui.Container()
    #    container.add_item(discord.ui.TextDisplay('Hello World!!!!!'))
    #    view = discord.ui.LayoutView()
    #    view.add_item(container)
    #    await interaction.response.send_message(view=view)
    #    latency = round(self.bot.latency * 1000)
    #    await interaction.response.send_message(f"Pong! 延遲：{latency}ms")

async def setup(bot: commands.Bot):
    await bot.add_cog(Log(bot))