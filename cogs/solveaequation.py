# cogs/solveaequation.py
import discord
from discord import app_commands
from discord.ext import commands
import math

class solveaequation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def formula(self, a:int, b:int, c:int, float:bool = None):
        D = (b**2)-4*a*c
        if not float:
            ans = f'{(0-b+ math.sqrt(D))/2} or {(0-b- math.sqrt(D))/2}'
        else:
            print(D)
            if D < 0:
                ans = f'({str(0-b)} ± √{str(abs(D))}𝓲)/{str(2*a)}'
            #    await interaction.response.send_message(content='x 無實數解')
            if D >= 0:
                if (D**0.5)%1 == 0:
                    gcd = int(math.gcd(int((0-b)+(D**0.5)), int(2*a)))
                    gcd2 = int(math.gcd(int((0-b)-(D**0.5)), int(2*a)))
                    #print(gcd, gcd2)
                    if int((0-b)+(D**0.5)) == int((0-b)-(D**0.5)):
                        ans = ((((0-b)+(D**0.5))/gcd)/int((2*a)/gcd))
                        if ans%1 == 0: ans = int(ans)
                        else: ans = f'{str(int(((0-b)+(D**0.5))/gcd))}/{str(int((2*a)/gcd))}'
                    else:
                        ans = (((0-b)+(D**0.5))/gcd)/int((2*a)/gcd)
                        ans2 = (((0-b)-(D**0.5))/gcd2)/int((2*a)/gcd2)
                        if ans%1 == 0: ans = int(ans)
                        else: ans = f'{str(int(((0-b)+(D**0.5))/gcd))}/{str(int((2*a)/gcd))}'
                        if ans2%1 == 0: ans2 = int(ans2)
                        else: ans2 = f'{str(int(((0-b)-(D**0.5))/gcd2))}/{str(int((2*a)/gcd2))}'
                        ans = f'{ans} or {ans2}'
                else:
                    ans = f'({str(0-b)} ± √{str(D)})/{str(2*a)}'
        return ans

    @app_commands.command(name='solveequation', description='解一元二次方程式(ax²+bx+c=0)')
    async def solve(self, interaction: discord.Interaction, a:int, b:int, c:int, float:bool = None):
            await interaction.response.send_message(content=f'x = {self.formula(a, b, c, float)}')

    @commands.command()
    async def solve(self, ctx: commands.Context, a:int, b:int, c:int, float:bool = True):
            await ctx.send(f'x = {self.formula(a, b, c, float)}')

# 每個 Cog 檔案底部一定要有這個 setup 函式
async def setup(bot: commands.Bot):
    await bot.add_cog(solveaequation(bot))