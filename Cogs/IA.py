from discord.ext import commands
from discord import app_commands
import discord
from bot import Trapard
from .utils.IaModelsRencontres import get_gen
from .utils.functions import LogErrorInWebhook, command_counter, create_embed

class IA(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ask", with_app_command=True, description="Pose une question à l'IA")
    @app_commands.describe(question="La question à poser à l'IA", model="Le modèle d'IA à utiliser")
    @app_commands.choices(model=[
        app_commands.Choice(name="gpt-5 ($1.25)", value="gpt-5"),
        app_commands.Choice(name="gpt-5-mini ($0.25)", value="gpt-5-mini"),
        app_commands.Choice(name="gpt-5-nano ($0.05)", value="gpt-5-nano"),
        app_commands.Choice(name="gpt-4.1-mini ($0.40)", value="gpt-4.1-mini"),
    ])
    async def ask(self, ctx: commands.Context, *, question: str, model: app_commands.Choice[str]=None):
        try:
            await command_counter(ctx.author.id, self.bot)
            try: await ctx.defer()
            except: pass
            model_val = model.value if model else "gpt-3.5-turbo"
            formatted_question = question if isinstance(question, list) else [{"role": "user", "content": question}]
            response = await self.bot.IAclient.chat.completions.create(
                model=model_val,
                messages=formatted_question,
                temperature=0,
                max_tokens=1000
            )
            content = response.choices[0].message.content
            max_length = 4096 
            if len(content) > max_length:
                chunks = [content[i:i+max_length] for i in range(0, len(content), max_length)]
                for idx, chunk in enumerate(chunks):
                    title = f"Ask {model_val} (part {idx+1}/{len(chunks)})" if len(chunks) > 1 else f"Ask {model_val}"
                    await ctx.reply(embed=create_embed(title, chunk))
            else:
                await ctx.reply(embed=create_embed(f"Ask {model_val}", content))
        except Exception as e:
            await LogErrorInWebhook(e)

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