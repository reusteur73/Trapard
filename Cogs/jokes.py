from discord.ext import commands
from typing import Literal
from .utils.functions import LogErrorInWebhook, command_counter, getVar
from bot import Trapard
import aiohttp

async def get_joke(session: aiohttp.ClientSession, wanted: Literal["joke", "dark", "beauf"]):
    try:
        headers = {"Authorization": f"Bearer {getVar('JOKE_API')}"}
        
        if wanted == "beauf":
            params = {"type": "beauf"}
        elif wanted == "dark":
            params = {"type": "dark"}
        else:
            params = None
        
        async with session.get("https://www.blagues-api.fr/api/random", headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                blague = data["joke"]
                answer = data["answer"]
                formatedJoke = blague + "\n" + "||" + answer + "||"
                return formatedJoke
            else:
                print("Erreur dans la récupération des données")
    except Exception as e:
        LogErrorInWebhook()

class Jokes(commands.Cog):
    def __init__(self, bot: Trapard):
        self.bot: Trapard = bot
    @commands.hybrid_command(name='joke', description="Petite blagounette")
    async def joke(self, ctx: commands.Context):
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            jokes = await get_joke(session=self.bot.session,wanted="joke")
            await ctx.reply(jokes)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name='beauf', description="Blagounette")
    async def beauf(self, ctx: commands.Context):
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            jokes_b = await get_joke(session=self.bot.session, wanted="beauf")
            await ctx.reply(jokes_b)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name='dark', description="Blagounette")
    async def dark(self, ctx: commands.Context):
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            jokes_d = await get_joke(session=self.bot.session, wanted="dark")
            await ctx.reply(jokes_d)
        except Exception as e:
            LogErrorInWebhook()

async def setup(bot: Trapard):
    await bot.add_cog(Jokes(bot))
    