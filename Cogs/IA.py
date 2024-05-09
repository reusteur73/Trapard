from discord.ext import commands
from bot import Trapard
from .utils.IaModelsRencontres import get_gen
from .utils.functions import LogErrorInWebhook, command_counter, create_embed

class IA(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot

    @commands.hybrid_group()
    async def ia(self, ctx: commands.Context):
        pass

    @ia.command(aliases=["rencontresnc", "rencontre"])
    async def rencontres(self, ctx: commands.Context, taille: int = 300):
        try:
            await command_counter(ctx.author.id, self.bot)
            if taille > 1950:
                await ctx.send("La taille doit être inférieure à 1950")
                return
            mess = await ctx.send(embed=create_embed("Rencontres NC IA", "Génération en cours..."))
            resp = get_gen(taille)
            return await mess.edit(embed=create_embed("Rencontres NC IA", resp))
        except Exception as e:
            await LogErrorInWebhook(e)

async def setup(bot: Trapard):
    await bot.add_cog(IA(bot))