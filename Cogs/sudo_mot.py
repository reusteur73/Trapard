import discord,base64, json
from bs4 import BeautifulSoup
from discord.ext import commands
from bot import Trapard
from uuid import uuid4
from .utils.functions import create_embed, LogErrorInWebhook, command_counter, load_json_data, format_duration, getVar
from .utils.sudoku import main as sudoku_generator
from typing import Literal
from aiohttp import ClientSession
from .utils.mot_mels import mains as motMels

class LinkView(discord.ui.View):
    def __init__(self, ctx, sudoku_url):
        super().__init__()
        self.ctx = ctx
        self.sudoku_url = sudoku_url

        self.btn_url = discord.ui.Button(style=discord.ButtonStyle.green, label="Jouer", emoji="🔗", disabled=False, url=self.sudoku_url)
        self.add_item(self.btn_url)

class SudoMots(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot

    @commands.hybrid_command(name="sudoku")
    async def sudoku(self, ctx: commands.Context, difficulte: Literal["Easy", "Medium", "Hard", "Insane"]):
        "Jouer au jeu du sudoku"
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            embed = create_embed(title="Sudoku",description=f"Génération de la grille... (en {difficulte})")
            await ctx.send(embed=embed)
            username = ctx.author.id
            sudoku_dict = sudoku_generator(difficulte)
            init_chann = ctx.channel.id
            ancient_url = sudoku_dict['url']
            game_id = uuid4()
            new_url = f"{ancient_url}&id={game_id}&userid={username}"
            view = LinkView(ctx, new_url)
            await ctx.send(view=view, ephemeral=True)
            # store game data in channel 
            msg = f"Game ID = {game_id}\n\nGame URL = {sudoku_dict['url']}\nGame DATA = {sudoku_dict['list']}\nUserID = {username}\nDifficultée = {difficulte}\ninit chann = {init_chann}"
            async with ClientSession() as session:
                webhook = discord.Webhook.from_url(getVar("SUDOKU_WEBHOOK"), session=session)
                await webhook.send(content=msg)
            return
        except Exception as e:
            LogErrorInWebhook()   

    @commands.hybrid_command(name="sudoku-ladder")
    async def sudoku_ladder(self, ctx: commands.Context):
        """Voir les points des joueurs dans le jeu du sudoku !"""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            data = load_json_data(item="sudoku-points")
            users = {}

            for key, vals in data.items():
                user = await self.bot.fetch_user(int(key))
                username = user.name
                users[username] = {"total": vals['points'], "easy": vals['easy'], "medium": vals['medium'], "hard": vals['hard'], "insane": vals['insane'], "temps": vals['temps']}


            sorted_users = sorted(users.items(), key=lambda user: user[1]['total'], reverse=True)
            embed = discord.Embed(title="Classement & Stats des Sudokus")
            for username, data in sorted_users:
                tot = data["total"]
                easy = data.get("easy", 0)
                medium = data.get("medium", 0)
                hard = data.get("hard", 0)
                insane = data.get("insane", 0)
                tmps = data.get("temps")
                tmps = format_duration(int(tmps))
                value = f"Total points : {tot} - Easy: {easy} - Medium: {medium} - Hard: {hard} - Insane: {insane}\nMeilleur temps: {tmps}"
                embed.add_field(name=username, value=value, inline=False)
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name="mot-mêlés")
    async def PlayMotsMels(self, ctx: commands.Context):
        """Jouer une grille de mot-mêlés."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            embed = create_embed(title="Mot-mêlés", description="Génération de la grille...")
            await ctx.send(embed=embed)
            userid = ctx.author.id
            gameid = uuid4()
            init_channel = ctx.channel.id
            wanted_words, liste_grille = motMels()
            wanted_words_encoded = base64.b64encode(json.dumps(wanted_words).encode('utf-8')).decode('utf-8')
            liste_grille_encoded = base64.b64encode(json.dumps(liste_grille).encode('utf-8')).decode('utf-8')
            msg_webhook = f"Game ID: {gameid}\nUser ID: {userid}\nInit chann: {init_channel}\nMots voulue: {wanted_words}\nGrille: {liste_grille}"
            async with ClientSession() as session:
                webhook = discord.Webhook.from_url(getVar("MOTMEL_WEBHOOK"), session=session)
                await webhook.send(content=msg_webhook)
            url = f"http://www.reusteur.org/mot-meles/jeu.php?grille={liste_grille_encoded}&words={wanted_words_encoded}&userid={userid}&gameid={gameid}"
            # short the link
            encoded_url = base64.b64encode(url.encode('utf-8')).decode('utf-8')
            u = f"http://reusteur.org/shortner/shortner.php?base64encoded={encoded_url}"
            response = await self.bot.session.get(u)
            code = await response.text()
            soup = BeautifulSoup(code, 'html.parser')
            a_tag = soup.find('a', {'class': 'lelien'})
            real_url = a_tag.get('href')
            view = LinkView(ctx, real_url)
            embed = create_embed(title="Mot-mêlés", description="Voila le lien:")
            return await ctx.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()   

    @commands.hybrid_command(name="mot-mêlés-ladder")
    async def MotsMelsLadder(self, ctx: commands.Context):
        """Ladder des mots-mêlés."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            data = load_json_data(item="mots-meles")
            embed = discord.Embed(title="Stats des mot-mêlés")
            for key, val in data.items():
                user = await self.bot.fetch_user(int(key))
                embed.add_field(name=user, value=f"Points: {val['points']}\nMeilleur temps: {format_duration(int(val['temps']))}", inline=False)
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()   

async def setup(bot: Trapard):
    await bot.add_cog(SudoMots(bot))