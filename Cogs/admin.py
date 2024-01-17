import discord
from discord.ext import commands
from bot import Trapard
from .utils.functions import LogErrorInWebhook, write_item, trapcoins_handler, load_json_data
from typing import Optional, Literal

class Admin(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
    
    @commands.command(name="add-trapcoins", hidden=True)
    @commands.is_owner()
    async def add_trapcoins(self, ctx: commands.Context, userid: discord.Member, nb: int):
        try:
            if ctx.author.id != self.bot.owner_id:
                return await ctx.send("Tu n'es pas autorisé à utiliser cette commande !")
            existing_data = load_json_data(item="trapcoins", userid=str(userid))
            if existing_data == "UserNotFound":
                new_user_data = {"trapcoins": nb, "epargne": 0}
                write_item(item="trapcoins", userid=str(userid), values=new_user_data)
            else:
                trapcoins_handler(type="add", userid=str(userid), trapcoins_val=nb)
            return await ctx.send("points ajouté !", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await self.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await self.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.is_owner()
    async def pm(self, ctx: commands.Context, membre: discord.Member, *,message: str, ):
        try:
            if ctx.author.id != 311013099719360512:
                return await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
            user = await self.bot.fetch_user(membre.id)
            await user.send(message)
            return await ctx.send("Le message a été envoyé !", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

    @commands.command()
    @commands.is_owner()
    async def fetch(self, ctx: commands.Context, user: discord.User):
        try:
            if ctx.author.id != 311013099719360512:
                return await ctx.send("This command is only available for the bot owner.")
            channel = user.dm_channel or await user.create_dm()
            messages = []
            await ctx.send('a')
            async for message in channel.history(limit=100):
                    messages.append(f"Auteur: {message.author} - `{message.content}`")
                    await ctx.send(f"Auteur: {message.author} - `{message.content}`")
        except Exception as e:
            LogErrorInWebhook()

async def setup(bot: Trapard):
    await bot.add_cog(Admin(bot))