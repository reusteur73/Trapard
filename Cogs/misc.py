import os, discord, random, asyncio, datetime, torch, inspect
from discord.ui import UserSelect
from discord import app_commands
from .utils.functions import LogErrorInWebhook, format_duration, load_json_data, create_embed, command_counter, printFormat, convert_str_to_emojis, trapcoins_handler, getDriver, lol_player_in_game, afficher_nombre_fr, calc_usr_gain_by_tier, convert_k_m_to_int
from .utils.data import LANGUAGES
from .utils.classes import Trapardeur
from .utils.context import Context
from .utils.path import TRAPARDEUR_IMG, LOL_FONT, FILES_PATH
from discord.ext import commands
from typing_extensions import Annotated
from typing import Optional, NamedTuple, TypedDict, Tuple, Literal
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from discord_webhook import DiscordWebhook
from PIL import Image, ImageDraw, ImageFont
from base64 import b64decode
from io import BytesIO
from pyvirtualdisplay import Display
from asyncio import sleep
from bot import Trapard, DB_PATH
from aiohttp import ClientSession
from datetime import datetime
from TTS.api import TTS
import pytz

def get_local_time(country_code):
    try:
        timezone = pytz.country_timezones.get(country_code.upper())
        
        if timezone:
            tz = pytz.timezone(timezone[0])
            local_time = datetime.now(tz)
            return local_time
        else:
            return "Code de pays non reconnu"
    except Exception as e:
        return f"Une erreur s'est produite : {e}"

async def get_avatar(member: discord.Member, session: ClientSession) -> BytesIO:
    async with session.get(member.display_avatar.url) as resp:
        avatar = Image.open(BytesIO(await resp.read())).convert("RGBA")
    return avatar

def format_duration2(duration_in_seconds):
    try:
        days = duration_in_seconds // 86400
        hours = (duration_in_seconds % 86400) // 3600
        minutes = (duration_in_seconds % 3600) // 60
        seconds = duration_in_seconds % 60

        if days > 0:
            return f'{days}j {hours:02}h {minutes:02}m'
        elif hours > 0:
            return f'{hours:02}h {minutes:02}m {seconds:02}s'
        else:
            return f'{minutes:02}m {seconds:02}s'
    except Exception as e:
        LogErrorInWebhook()

class SelectFavSongUser(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=2000)
        self.selected = None
        

    @discord.ui.select(cls=UserSelect, placeholder="Voir les musiques favorites de", min_values=1, max_values=1)
    async def my_user_select(self, interaction: discord.Interaction, select: UserSelect):
        try: await interaction.response.defer()
        except: pass
        users = [
            user.id for user in select.values
        ]
        self.selected = users
        self.stop()
        return

class SelectSkipSongUser(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=2000)
        self.selected = None
        

    @discord.ui.select(cls=UserSelect, placeholder="Voir les musiques skip de", min_values=1, max_values=1)
    async def my_user_select(self, interaction: discord.Interaction, select: UserSelect):
        try: await interaction.response.defer()
        except: pass
        users = [
            user.id for user in select.values
        ]
        self.selected = users
        self.stop()
        return

class songsStatsView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bot: Trapard):
        super().__init__(timeout=None)
        self.bot = bot
    @discord.ui.button(label='Musiques préférées', style=discord.ButtonStyle.blurple)
    async def fav_songs(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        user_id = interaction.user.id
        await self.bot.cursor.execute(f"SELECT * FROM FavSongs WHERE userId = {user_id}")
        data = await self.bot.cursor.fetchall()
        if data == []:
            embed = create_embed(title="Musiques favorites", description=f"Tu n'as pas encore de musiques favorites.")
            return await interaction.followup.send(embed=embed)
        else:
            # Send top 25 fav songs
            fields = f"```{printFormat('N°', 4)}|{printFormat('Nom de la musique',30)}|{printFormat('Nombre de fois joué', 3)}\n"
            fields += "----|-------------------|--------------------\n"

            data = sorted(data, key=lambda x: x[3], reverse=True)
            for i in range(25):
                try:
                    fields += f"{printFormat(str(i+1), 4)}|{printFormat(data[i][2], 30)}|{printFormat(str(data[i][3]), 3)}\n"
                except IndexError:
                    pass
            fields += "```"
            view=SelectFavSongUser()
            embed = create_embed(title=f"Musiques favorites de {interaction.user.display_name}", description=fields)
            message = await interaction.followup.send(embed=embed, view=view, wait=True)
            while view.selected is None:
                await sleep(0.1)
            user_id = view.selected[0]
            await self.bot.cursor.execute(f"SELECT * FROM FavSongs WHERE userId = {user_id}")
            data = await self.bot.cursor.fetchall()
            if data == []:
                embed = create_embed(title="Musiques favorites", description=f"Tu n'as pas encore de musiques favorites.")
                await message.edit(embed=embed, view=view)
            else:
                # Send top 25 fav songs
                fields = f"```{printFormat('N°', 4)}|{printFormat('Nom de la musique',30)}|{printFormat('Nombre de fois joué', 3)}\n"
                fields += "----|-------------------|--------------------\n"
                data = sorted(data, key=lambda x: x[3], reverse=True)
                for i in range(25):
                    try:
                        fields += f"{printFormat(str(i+1), 4)}|{printFormat(data[i][2], 30)}|{printFormat(str(data[i][3]), 3)}\n"
                    except IndexError:
                        pass
                fields += "```"
                embed = create_embed(title=f"Musiques favorites de {self.bot.get_user(user_id).display_name}", description=fields)
                await message.edit(embed=embed, view=view)

    @discord.ui.button(label='Musiques les plus jouées', style=discord.ButtonStyle.blurple)
    async def most_played_songs(self, ctx: discord.Interaction, button: discord.ui.Button):
        try: await ctx.response.defer()
        except: pass
        # sqlite3 db open
        await self.bot.cursor.execute(f"SELECT songName, count FROM SongPlayedCount")
        data = await self.bot.cursor.fetchall()
        if data == []:
            embed = create_embed(title="Most-played-songs", description=f"Il n'y a pas encore de musiques favorites.")
            return await ctx.followup.send(embed=embed)
        else:
            # Send top 25 fav songs
            data = sorted(data, key=lambda x: x[1], reverse=True)
            # Display resulut in embed field with 25 songs and this format: 
            # Rang | Nom de la musique | Nombre de fois joué
            #------|-------------------|--------------------
            # 1.   | Nom de la musique | 1000 fois
            # 2.   | Nom de la musique | 1000 fois

            field = f"```{printFormat('N°', 4)}|{printFormat('Nom de la musique',30)}|{printFormat('Nombre de fois joué', 3)}\n"
            field += f"{'-'*4}|{'-'*30}|{'-'*3}\n"
            for i in range(25):
                try:
                    field += f"{printFormat(str(i+1), 4)}|{printFormat(data[i][0], 30)}|{printFormat(str(data[i][1]), 3)}\n"
                except IndexError:
                    break
            field += "```"
            embed = create_embed(title="Musiques les plus jouées", description=field)
            return await ctx.followup.send(embed=embed)
        
    @discord.ui.button(label='Musiques les plus skip', style=discord.ButtonStyle.blurple)
    async def most_skipped_songs(self, ctx: discord.Interaction, button: discord.ui.Button):
        try: await ctx.response.defer()
        except: pass
        await self.bot.cursor.execute(f"SELECT songName, count FROM SkippedSongs")
        data = await self.bot.cursor.fetchall()
        view=SelectSkipSongUser()
        message = await ctx.followup.send("Patientez...", view=view, wait=True)
        if data == []:
            embed = create_embed(title="Musiques les plus skip", description=f"{self.bot.get_user(ctx.user.id).display_name} n'a pas encore de musiques skip.")
            await message.edit(embed=embed,view=view)
        else:
            # Send top 25 fav songs
            data = sorted(data, key=lambda x: x[1], reverse=True)
            fields = f'```{printFormat("N°", 4)}|{printFormat("Nom de la musique",30)}|{printFormat("Nombre de fois skip", 3)}\n'
            fields += f'{"-"*4}|{"-"*30}|{"-"*3}\n'
            for i in range(25):
                try:
                    fields += f"{printFormat(str(i+1), 4)}|{printFormat(data[i][0], 30)}|{printFormat(str(data[i][1]), 3)}\n"
                except IndexError:
                    break
            fields += "```"
            if len(fields) == 1:
                fields.append({"name": "Aucune musique n'a été skip", "value": "Aucune musique n'a été skip", "inline": True})
            embed = create_embed(title=f"Musiques les plus skip par {self.bot.get_user(ctx.user.id).display_name}", description=fields)
            await message.edit(embed=embed, view=view)

def draw_rank(niveau: str, messages: str, temps_vocal_tot: str, temps_total_vocal_auj: str, commandes: str, experience: str, name: str, avatar: Image.Image, fill: str = "#FFFFFF") -> BytesIO:

    def draw_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        coordinates: Tuple[int, int],
        box_size: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        fill: str,
    ) -> None:
        text_width, text_height = draw.textlength(text, font=font), 24

        coordinates = (
            int(coordinates[0] + (box_size[0] - text_width) // 2),
            int(coordinates[1] + (box_size[1] - text_height) // 2),
        )

        draw.text(
            coordinates,
            text,
            font=font,
            fill=fill,
        )

    def circular_crop(image: Image.Image) -> Image.Image:
        """Crop an image into a circle with transparent background."""
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + image.size, fill=255)
        mask = mask.resize(image.size)
        # mask = mask.resize(image.size, Image.ANTIALIAS)
        result = image.copy()
        result.putalpha(mask)
        return result
    
    img = Image.open(TRAPARDEUR_IMG)
    avatar = circular_crop(avatar).resize((120, 120))
    img.paste(avatar, (50, 24), avatar)

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(LOL_FONT, 18)

    # Niveau
    draw_text(draw=draw,text=niveau,coordinates=(250, 50),box_size=(166, 40),font=font,fill=fill)

    # Messages
    draw_text(draw=draw, text=messages, coordinates=(475, 50), box_size=(166, 40), font=font, fill=fill)

    # Temps en vocal aujourd'hui
    draw_text(draw=draw,text=temps_total_vocal_auj,coordinates=(692, 50),box_size=(200, 40),font=font,fill=fill)

    # Temps total en vocal
    draw_text(draw=draw,text=temps_vocal_tot,coordinates=(692, 156),box_size=(200, 40),font=font,fill=fill)

    # Commandes
    draw_text(draw=draw,text=commandes,coordinates=(460, 156),box_size=(200, 40),font=font,fill=fill)

    # Expérience
    draw_text(draw=draw,text=experience,coordinates=(232, 156),box_size=(200, 40),font=font,fill=fill)

    # Pseudo
    draw_text(draw=draw,text=name,coordinates=(15, 162),box_size=(200, 40),font=font,fill=fill)

    def percentage(part: int, whole: int):
        return 100 * part / whole

    max_progress_width = 817
    experience_needed_lvlup = 500

    progress = percentage(int(experience), experience_needed_lvlup)
    current_progress = min(progress, 100)

    percentage_width = int(max_progress_width * (current_progress / 100))

    draw.rounded_rectangle((50, 262, 52+percentage_width, 277), radius=25, fill=fill)

    fp = BytesIO()
    img.convert("RGBA").save(fp, "PNG")
    return fp

async def xp_calculation(user_id: str, bot: Trapard):
    """
        Calculate the xp of the user
        Xp needed per level = 500
        10 minutes of voice = 2 xp
        1 message sent = 1 xp
        1 command used = 1 xp
    """
    try:
        handler = Trapardeur(pool=bot.pool, userId=user_id)
        data = await handler.get()
        xp = (data[0][2] * 2 / 600) + data[0][3] + data[0][4]
        return xp
    except Exception as e:
        LogErrorInWebhook(error=f"[XP CALCULATION] {e} DATA={data}")

def calculate_level(xp_total):
    xp_needed_per_level = 500
    return xp_total // xp_needed_per_level

def create_image_with_color(color, width=200, height=200):
    image = Image.new("RGB", (width, height), color)
    return image

class TranslateError(Exception):
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code: int = status_code
        self.text: str = text
        super().__init__(f'Google a renvoyé un code d\'état {status_code} et le texte suivant: {text}')

class TranslatedSentence(TypedDict):
    trans: str
    orig: str

class TranslateResult(NamedTuple):
    original: str
    translated: str
    source_language: str
    target_language: str

class PierreFeuilleCiseauxGame(discord.ui.View):
    def __init__(self, ctx: discord.Interaction, player1: int, player2: int, bet: int=None):
        super().__init__(timeout=500)

        self.ctx = ctx
        self.player1 = player1
        self.player2 = player2
        self.bet = bet

        self.player1_bet = None
        self.player2_bet = None

        self.winner = None

        emojis = ["<:cobble:1126135975341477899>", "<:paper:1126137485437714472>", "<:shears:1126138076071215167>"]
        for i, emoji in enumerate(emojis):
            self.button = discord.ui.Button(label="", emoji=emoji, custom_id=f"{i+1}", style=discord.ButtonStyle.blurple)
            self.add_item(self.button)
            self.button.callback = lambda interaction=self.ctx, button=self.button: self.on_button_click(interaction, button)
    def check_win(self, p1_bet: str, p2_bet: str):
        """
        input is one of this: ["pierre","feuille","ciseaux"]
        """
        print(p1_bet, p2_bet)
        if p1_bet == p2_bet:
            return None  # Il y a égalité, donc pas de gagnant
        
        if (p1_bet == "pierre" and p2_bet == "ciseaux") or (p1_bet == "feuille" and p2_bet == "pierre") or (p1_bet == "ciseaux" and p2_bet == "feuille"):
            return "Joueur 1"  # Joueur 1 gagne
        return "Joueur 2"  # Joueur 2 gagne

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        view = None
        if interaction.user.id == self.player1 or interaction.user.id == self.player2:
            if self.player2 == "trapard":
                self.trapchoice = random.randint(1,3)
                if self.trapchoice == 1: # Paris sur pierre
                    bet = "<:cobble:1126135975341477899>"
                    bet_val = "pierre"
                elif self.trapchoice == 2: # Paris sur feuille
                    bet = "<:paper:1126137485437714472>"
                    bet_val = "feuille"
                elif self.trapchoice == 3: # Paris sur ciseaux
                    bet = "<:shears:1126138076071215167>"
                    bet_val = "ciseaux"
                self.player2_bet_val = bet_val
                self.player2_bet = bet


            if button.custom_id == "1": # Paris sur pierre
                bet = "<:cobble:1126135975341477899>"
                bet_val = "pierre"
            elif button.custom_id == "2": # Paris sur feuille
                bet = "<:paper:1126137485437714472>"
                bet_val = "feuille"
            elif button.custom_id == "3": # Paris sur ciseaux
                bet = "<:shears:1126138076071215167>"
                bet_val = "ciseaux"
            
            if interaction.user.id == self.player1:
                self.player1_bet_val = bet_val
                self.player1_bet = bet
            elif interaction.user.id == self.player2:
                if self.player2 != "trapard":
                    self.player2_bet_val = bet_val
                    self.player2_bet = bet

            if self.player1_bet and self.player2_bet:
                game_result = self.check_win(self.player1_bet_val, self.player2_bet_val)
                if game_result:
                    if game_result == "Joueur 1":
                        self.winner = self.player1
                        self.winner_em = self.player1_bet

                        if self.winner == "trapard":
                            winner_mention = "<@1065781211219370104>"
                        else:
                            winner_mention = f"<@{self.player1}>"

                        self.loser = self.player2
                        self.loser_em = self.player2_bet
                        if self.loser == "trapard":
                            loser_mention = "<@1065781211219370104>"
                        else:
                            loser_mention = f"<@{self.player2}>"

                    elif game_result == "Joueur 2":
                        self.winner = self.player2
                        self.winner_em = self.player2_bet

                        if self.winner == "trapard":
                            winner_mention = "<@1065781211219370104>"
                        else:
                            winner_mention = f"<@{self.player2}>"

                        self.loser = self.player1
                        if self.loser == "trapard":
                            loser_mention = "<@1065781211219370104>"
                        else:
                            loser_mention = f"<@{self.player1}>"

                        self.loser_em = self.player1_bet
                    if self.bet:
                        trapcoins_handler(type="remove", userid=self.loser, trapcoins_val=self.bet)
                        trapcoins_handler(type="add", userid=self.winner, trapcoins_val=self.bet)
                        embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- {winner_mention} a gagné la partie ({self.winner_em}) + {convert_k_m_to_int(str(self.bet))}.\n\n- {loser_mention} a perdu la partie ({self.loser_em}) - {convert_k_m_to_int(str(self.bet))}.")
                    else:
                        embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- {winner_mention} a gagné la partie ({self.winner_em}).\n\n- {loser_mention} a perdu la partie. ({self.loser_em})")
                else: # il y a égalité
                    self.player1_bet = None
                    self.player2_bet = None
                    embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- Il a **égalité**. Vous avez tous les deux choisi {bet}.\n\n- **Aller on y retourne** :")
                    view = PierreFeuilleCiseauxGame(ctx=self.ctx, player1=self.player1, player2=self.player2, bet=self.bet)
                # Handle result
            else: # Il manque un joueur
                if interaction.user.id == self.player1:
                    to_show = self.player2
                else:
                    to_show = self.player1
                if self.bet:
                    embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- Il y a {convert_k_m_to_int(str(self.bet))} en jeu.\n\n- <@{to_show}> n'a pas encore joué.")
                else:
                    embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- <@{to_show}> n'a pas encore joué.")
                view = self
        else: # Le joueur ne fait pas partie de la partie.
            embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- <@{interaction.user.id}> a voulu joué, mais n'est pas autorisé. || FLOPPAS ||")
            view = self
        
        return await interaction.message.edit(embed=embed, view=view)
    
    async def on_timeout(self):
        return await self.ctx.edit_original_response(view=None)

class Puissance4Game(discord.ui.View):
    def __init__(self, ctx, player1, player2, bet: int=None):
        super().__init__(timeout=500)
        self.ctx = ctx
        self.interactable = [1,2,3,4,5]
        #       La grille de puissance 3
        #    1  - 2  - 3  - 4  - 5 
        #    6  - 7  - 8  - 9  - 10
        #    11 - 12 - 13 - 14 - 15
        #    16 - 17 - 18 - 19 - 20
        #    21 - 22 - 23 - 24 - 25
        self.player1 = player1
        self.player2 = player2

        self.player1_filled = []
        self.player2_filled = []

        self.clonnes = [[1,6,11,16,21],[2,7,12,17,22],[3,8,13,18,23],[4,9,14,19,24],[5,10,15,20,25]]
        self.filled_case = []
        self.round = 0
        self.trapcoins_emoji = "<:trapcoins:1108725845339672597>"

        self.bet = bet
        self.current_player = self.player1
        if self.bet:
            self.pari_head = f"Pari `ON`.\nIl y a {self.bet} Trapcoins en jeu.\n\n"
        else: self.pari_head = "Pari `OFF`\n\n"

        for i in range(1, 26):

            if i in self.interactable:
                self.button = discord.ui.Button(label="-", custom_id=f"{i}", style=discord.ButtonStyle.blurple, disabled=False)
            else:
                self.button = discord.ui.Button(label="-", custom_id=f"{i}", style=discord.ButtonStyle.blurple, disabled=True)
            self.add_item(self.button)
            self.button.callback = lambda interaction=self.ctx, button=self.button: self.on_button_click(interaction, button)

    def check_win(self, to_check: list):
        diago = [
            [3,9,15],
            [2,8,14],
            [8,14,20],
            [1,7,13],
            [7,13,19],
            [13,19,25],
            [6,12,18],
            [12,18,24],
            [11,17,23],

            [11,7,3],
            [16,12,8],
            [12,8,4],
            [21,17,13],
            [17,13,9],
            [13,9,5],
            [22,18,14],
            [18,14,10],
            [23,19,15],
        ]

        horizontal = [
            [1,2,3],
            [2,3,4],
            [3,4,5],
            [6,7,8],
            [7,8,9],
            [8,9,10],
            [11,12,13],
            [12,13,14],
            [13,14,15],
            [16,17,18],
            [17,18,19],
            [18,19,20],
            [21,22,23],
            [22,23,24],
            [23,24,25]
        ]

        verticales = [
            [1,6,11],
            [6,11,16],
            [11,16,21],
            [2,7,12],
            [7,12,17],
            [12,17,22],
            [3,8,13],
            [8,13,18],
            [13,18,23],
            [4,9,14],
            [9,14,19],
            [14,19,24],
            [5,10,15],
            [10,15,20],
            [15,20,25]
        ]
        
        for win_pattern in diago:
            count = 0  # Compteur pour suivre le nombre de correspondances dans le motif de victoire

            for button_id in win_pattern:
                if button_id in to_check:
                    count += 1
            if count >= 3:
                return True
            
        for win_pattern in horizontal:
            count = 0  # Compteur pour suivre le nombre de correspondances dans le motif de victoire

            for button_id in win_pattern:
                if button_id in to_check:
                    count += 1
            if count >= 3:
                return True

        for win_pattern in verticales:
            count = 0  # Compteur pour suivre le nombre de correspondances dans le motif de victoire

            for button_id in win_pattern:
                if button_id in to_check:
                    count += 1
            if count >= 3:
                return True
            
        return False

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        # Vérifier si c'est le tour du joueur actuel pour appuyer sur le bouton
        if self.current_player == interaction.user.id:
            btn_id = int(button.custom_id)
            last_val_to_fill = (self.clonnes[btn_id - 1][-1])
            if self.round % 2 == 0:
                self.current_player = self.player2
                embed = create_embed(title="Puissance-3", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**C'est à <@{self.player2}> de jouer.**")
                self.player1_filled.append(last_val_to_fill)
                data = self.player1_filled
            else:
                embed = create_embed(title="Puissance-3", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**C'est à <@{self.player1}> de jouer.**")
                self.current_player = self.player1
                self.player2_filled.append(last_val_to_fill)
                data = self.player2_filled

            # 🟡   🔴
            self.round += 1
            self.clonnes[btn_id - 1].pop() 
            other_button = discord.utils.get(self.children, custom_id=str(last_val_to_fill))
            if other_button:
                if interaction.user.id == self.player1:
                    other_button.emoji = "🟡"
                elif interaction.user.id == self.player2:
                    other_button.emoji = "🔴"
                other_button.disabled = True
                other_button.label = None  
            
            if self.check_win(data):
                msg = f"<@{interaction.user.id}> a gagné."
                
                if self.bet:
                    trapcoins_handler(type="add", userid=str(interaction.user.id), trapcoins_val=int(self.bet))
                    if interaction.user.id != self.player1:
                        loser = self.player1
                        trapcoins_handler(type="remove", userid=str(loser), trapcoins_val=int(self.bet))
                    elif interaction.user.id == self.player1:
                        loser = self.player2
                        trapcoins_handler(type="remove", userid=str(loser), trapcoins_val=int(self.bet))
                    trapcoins_handler(type="add", userid=str(interaction.user.id), trapcoins_val=100000)
                    msg = f"- <@{interaction.user.id}> a gagné.\n\n- Il y avait **{afficher_nombre_fr(self.bet)} {str(self.trapcoins_emoji)}** en jeu.\n\n- <@{interaction.user.id}> : **+ {self.bet} + 100 000** = **{afficher_nombre_fr(self.bet + 100000)}** {str(self.trapcoins_emoji)}.\n\n- <@{loser}> : **- {self.bet}** {str(self.trapcoins_emoji)}, et tu gagnes **50 000** {str(self.trapcoins_emoji)} pour la participation."
                else:
                    if interaction.user.id != self.player1:
                        loser = self.player1
                    elif interaction.user.id == self.player1:
                        loser = self.player2
                    trapcoins_handler(type="add", userid=str(interaction.user.id), trapcoins_val=50000)
                    msg = f"- <@{interaction.user.id}> a gagné.\n\n- Tu gagnes le gain de base victoire de 50 000 {str(self.trapcoins_emoji)} + **50 000** {str(self.trapcoins_emoji)} pour la participation.\n\n- <@{loser}> Tu gagnes 50 000 {str(self.trapcoins_emoji)} pour la participation."
                trapcoins_handler(type="add", userid=str(loser), trapcoins_val=50000)
                embed = create_embed(title="Puissance-3", description=msg)
                return await interaction.message.edit(embed=embed)


            await interaction.message.edit(embed=embed, view=self)

        else:
            embed = create_embed(title="Puissance-3", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**C'est à <@{self.current_player}> de jouer.**\n\n- ❌ <@{interaction.user.id}>, ce n'est pas à toi de jouer.")
            await interaction.message.edit(embed=embed, view=self)

class MorpionGame(discord.ui.View):
    def __init__(self, ctx, player1, player2, bet_message, bet: int=None):
        super().__init__(timeout=None)

        self.ctx = ctx
        self.message_display = "Au joueur 1 de jouer."
        self.good_nums = [1,2,3,6,7,8,11,12,13]
        self.grid = [[1,2,3],[6,7,8],[11,12,13]]
        self.to_fill_grid = [[" ", " ", " "],[" ", " "," "],[" "," "," "]]
        self.banned_index = [4,5,9,10,14,15]
        self.player1 = player1
        self.player2 = player2
        self.round = 0
        self.case_filled = 0
        self.game_ended = False
        self.button_disabled_p1 = []
        self.button_disabled_p2 = []
        self.bet_msg = bet_message
        self.bet = bet
        self.current_player = self.player1
        self.current_player_sign = "X"
        if self.bet:
            self.pari_head = f"- Pari `ON`.\n- Il y a {self.bet} Trapcoins en jeu.\n\n"
        else: self.pari_head = "- Pari `OFF`\n\n"
        self.trapcoins_emoji = "<:trapcoins:1108725845339672597>"


        # Les 9 boutons:
        
        for i in range(1, 14):
            if i in self.banned_index:
                self.button = discord.ui.Button(label="-", custom_id=f"btn_{i}", style=discord.ButtonStyle.gray, disabled=True)
            else:
                self.button = discord.ui.Button(label="-", custom_id=f"btn_{i}", style=discord.ButtonStyle.blurple)
            self.add_item(self.button)
            self.button.callback = lambda interaction=self.ctx, button=self.button: self.on_button_click(interaction, button)
        
        self.button_ = discord.ui.Button(label="-", custom_id=f"btn_", style=discord.ButtonStyle.gray, disabled=True)
        self.button__ = discord.ui.Button(label="-", custom_id=f"btn__", style=discord.ButtonStyle.gray, disabled=True)
        self.add_item(self.button_)
        self.button_.callback = lambda interaction=self.ctx, button=self.button_: self.on_button_click(interaction, button)
        self.add_item(self.button__)
        self.button__.callback = lambda interaction=self.ctx, button=self.button__: self.on_button_click(interaction, button)


        self.quit_btn = discord.ui.Button(label="Quitter", emoji="🛅",custom_id=f"btn_quit", style=discord.ButtonStyle.danger)
        self.add_item(self.quit_btn)
        self.quit_btn.callback = lambda interaction=self.ctx, button=self.quit_btn: self.on_button_click(interaction, button)

    # async def update_view(self):
    def check_win(self, to_check: list):
        win_patterns = [[1,2,3],
                       [6,7,8],
                       [11,12,13],
                       [1,7,13],
                       [1,6,11],
                       [2,7,12],
                       [3,8,13],
                       [3,7,11]]
        for win_pattern in win_patterns:
            count = 0  # Compteur pour suivre le nombre de correspondances dans le motif de victoire

            for button_id in win_pattern:
                if button_id in to_check:
                    count += 1
            if count >= 3:
                return True
        return False
    
    def check_win2(self, player):
        # Vérification des lignes
        for i in range(3):
            if self.to_fill_grid[i][0] == player and self.to_fill_grid[i][1] == player and self.to_fill_grid[i][2] == player:
                return True

        # Vérification des colonnes
        for j in range(3):
            if self.to_fill_grid[0][j] == player and self.to_fill_grid[1][j] == player and self.to_fill_grid[2][j] == player:
                return True

        # Vérification des diagonales
        if self.to_fill_grid[0][0] == player and self.to_fill_grid[1][1] == player and self.to_fill_grid[2][2] == player:
            return True
        if self.to_fill_grid[0][2] == player and self.to_fill_grid[1][1] == player and self.to_fill_grid[2][0] == player:
            return True

        return False


    def minimax(self, maximizing_player):
        if maximizing_player:
            best_score = float('-inf')
            best_move = None
            for i in range(3):
                for j in range(3):
                    if self.to_fill_grid[i][j] == ' ':
                        self.to_fill_grid[i][j] = 'X'
                        score, _ = self.minimax(False)
                        self.to_fill_grid[i][j] = ' '
                        if score > best_score:
                            best_score = score
                            best_move = (i, j)
            return best_score, best_move
        else:
            best_score = float('inf')
            best_move = None
            for i in range(3):
                for j in range(3):
                    if self.to_fill_grid[i][j] == ' ':
                        self.to_fill_grid[i][j] = 'O'
                        score, _ = self.minimax(True)
                        self.to_fill_grid[i][j] = ' '
                        if score < best_score:
                            best_score = score
                            best_move = (i, j)
            return best_score, best_move

    def bot_play(self):
        best_score, best_move = self.minimax(False)

        if best_move is not None:
            return best_move[0], best_move[1]
        else:
            blocking_move = self.find_blocking_move()
            if blocking_move is not None:
                return blocking_move[0], blocking_move[1]
            # Aucun coup valide trouvé, le bot prend une décision aléatoire
            available_moves = [(i, j) for i in range(3) for j in range(3) if self.to_fill_grid[i][j] == ' ']
            if available_moves:
                random_move = random.choice(available_moves)
                return random_move[0], random_move[1]
    def find_blocking_move(self):
        for i in range(3):
            for j in range(3):
                if self.to_fill_grid[i][j] == ' ':
                    self.to_fill_grid[i][j] = 'X'
                    if self.check_win2('X'):
                        self.to_fill_grid[i][j] = ' '
                        return (i, j)
                    self.to_fill_grid[i][j] = ' '
        return None
    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        if not self.game_ended:
            trapcoins_emoji = "<:trapcoins:1108725845339672597>"
            # Vérifier si c'est le tour du joueur actuel pour appuyer sur le bouton
            if self.current_player == interaction.user.id:
                if button.custom_id == "btn_quit":
                    embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**La partie a été annulée par <@{interaction.user.id}>**")
                    return await interaction.message.edit(embed=embed, view=None)
                if self.round % 2 == 0:
                    self.button_disabled_p1.append(int(button.custom_id.split("_")[1]))
                    self.case_filled += 1
                    embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**C'est à <@{self.player2}> de jouer.**")
                    button.emoji = "🇽"
                    button.disabled = True
                    button.label = None
                    data = self.button_disabled_p1
                    self.current_player = self.player2
                    if int(button.custom_id.split("_")[1]) <= 3:
                        _case = int(button.custom_id.split("_")[1]) - 1
                        _grid = 0
                    elif int(button.custom_id.split("_")[1]) >= 6 and int(button.custom_id.split("_")[1]) <= 8:
                        _case = int(button.custom_id.split("_")[1]) - 6
                        _grid = 1
                    elif int(button.custom_id.split("_")[1]) >= 11 and int(button.custom_id.split("_")[1]) <= 13:
                        _case = int(button.custom_id.split("_")[1]) - 11
                        _grid = 2
                    self.to_fill_grid[_grid][_case] = "X"
                    if self.player2 == "trapard":
                        move1, move2 = self.bot_play()
                        self.to_fill_grid[move1][move2] = "O"
                        if move1 == 2 and move2 == 0:
                            _val = 11
                        elif move1 == 2 and move2 == 1:
                            _val = 12
                        elif move1 == 2 and move2 == 2:
                            _val = 13

                        if move1 == 1 and move2 == 0:
                            _val = 6
                        elif move1 == 1 and move2 == 1:
                            _val = 7
                        elif move1 == 1 and move2 == 2:
                            _val = 8

                        if move1 == 0 and move2 == 0:
                            _val = 1
                        elif move1 == 0 and move2 == 1:
                            _val = 2
                        elif move1 == 0 and move2 == 2:
                            _val = 3

                        self.button_disabled_p2.append(_val)
                        self.case_filled += 1
                        other_button = discord.utils.get(self.children, custom_id=f'btn_{_val}')
                        if other_button:
                            other_button.emoji = "🇴"
                            other_button.disabled = True
                            other_button.label = None
                        self.current_player = self.player1
                        if self.check_win(self.button_disabled_p1):
                            bonus = calc_usr_gain_by_tier(self.player1)
                            embed = create_embed(title="Morpion", description=f"- <@{self.player1}> **tu as gagné** contre Trapard, bravo !!\n\n- Tu gagnes **25 000 {str(trapcoins_emoji)} + {afficher_nombre_fr(bonus)} {str(trapcoins_emoji)}** grâce à ton épargne tiers !")
                            self.game_ended = True
                            trapcoins_handler(type="add", userid=self.player1, trapcoins_val=25000+bonus)
                            await interaction.message.edit(embed=embed, view=self)
                        elif self.check_win(self.button_disabled_p2):
                            embed = create_embed(title="Morpion", description=f"- <@{self.player1}> **tu as perdu** contre Trapard, la honte !!\n\n- Tu gagnes quand même **12 500 {str(trapcoins_emoji)}** en compensation !")
                            trapcoins_handler(type="add", userid=self.player1, trapcoins_val=12500)
                            self.game_ended = True
                            await interaction.message.edit(embed=embed, view=self)
                        elif self.case_filled >= 8:
                            embed = create_embed(title="Morpion", description=f"- <@{self.player1}> **Egalité** !!")
                            self.game_ended = True
                            await interaction.message.edit(embed=embed, view=self)
                        else:
                            embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs Trapard\n\n- A toi de jouer")
                            return await interaction.message.edit(embed=embed, view=self)
                else:
                    if self.player2 != "trapard":
                        embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**C'est à <@{self.player1}> de jouer.**")
                        self.button_disabled_p2.append(int(button.custom_id.split("_")[1]))
                        button.emoji = "🇴"
                        button.label = None
                        data = self.button_disabled_p2
                        self.current_player = self.player1
                # button.label = None
                button.disabled = True
                self.round += 1
                self.case_filled += 1    
                if self.check_win(data):
                    msg = f"- <@{interaction.user.id}> a gagné."
                    
                    if self.bet:
                        trapcoins_handler(type="add", userid=str(interaction.user.id), trapcoins_val=int(self.bet))
                        if interaction.user.id != self.player1:
                            loser = self.player1
                            trapcoins_handler(type="remove", userid=str(loser), trapcoins_val=int(self.bet))
                        elif interaction.user.id == self.player1:
                            loser = self.player2
                            trapcoins_handler(type="remove", userid=str(loser), trapcoins_val=int(self.bet))
                        trapcoins_handler(type="add", userid=str(interaction.user.id), trapcoins_val=50000)
                        trapcoins_handler(type="add", userid=str(loser), trapcoins_val=25000)
                        msg = f"- <@{interaction.user.id}> a gagné.\n\n- Il y avait **{afficher_nombre_fr(self.bet)} {str(self.trapcoins_emoji)}** en jeu.\n\n- <@{interaction.user.id}> : **+ {self.bet} + 50 000** = **{afficher_nombre_fr(self.bet + 50000)}** {str(self.trapcoins_emoji)}.\n\n- <@{loser}> : **- {self.bet}** {str(self.trapcoins_emoji)}, et tu gagnes 25 000 {str(self.trapcoins_emoji)} pour la participation."
                    else:
                        trapcoins_handler(type="add", userid=str(interaction.user.id), trapcoins_val=25000)
                        msg = f"- <@{interaction.user.id}> a gagné.\n\n- Tu gagnes le gain de base de 25 000 {str(self.trapcoins_emoji)}."
                    embed = create_embed(title="Morpion", description=msg)
                    return await interaction.message.edit(embed=embed)
                
                if self.case_filled == 9:
                    embed = create_embed(title="Morpion", description=f"- Egalité !")
                    return await interaction.message.edit(embed=embed)   
                
                await interaction.message.edit(embed=embed, view=self)
            else:
                embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- {self.pari_head}**C'est à <@{self.player1}> de jouer.**\n\n- ❌ <@{interaction.user.id}>, ce n'est pas à toi de jouer.")
                await interaction.message.edit(embed=embed, view=self)
        else: return

class Parier(discord.ui.View):
    def __init__(self, ctx, player1, player2, wanted_game:str, bot:Trapard):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.bot = bot
        self.player1 = player1
        self.player2 = player2
        self.trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        self.buttonoui = discord.ui.Button(label="Oui", emoji=f"{str(self.trapcoins_emoji)}", custom_id=f"oui", style=discord.ButtonStyle.success)
        self.add_item(self.buttonoui)
        self.buttonoui.callback = lambda interaction=self.ctx, button=self.buttonoui: self.on_button_click(interaction, button)

        self.buttonnon = discord.ui.Button(label="Non", emoji="🆓", custom_id=f"non", style=discord.ButtonStyle.danger)
        self.add_item(self.buttonnon)
        self.buttonnon.callback = lambda interaction=self.ctx, button=self.buttonnon: self.on_button_click(interaction, button)
        self.wanted_game = wanted_game

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
            
        if button.custom_id == "oui":
            embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- Pari `ON`. Combien vous pariez ? :")
            await interaction.message.edit(embed=embed, view=None)
            try:
                def check(message):
                    return message.author.id == self.player1 and message.channel == self.ctx.channel

                message = await self.bot.wait_for("message", check=check)
                # Le reste du traitement pour le message du player1

                new_m = convert_k_m_to_int(message.content.strip())
                if new_m == "ValueError":
                    msg = f"**- <@{self.player1}>, Le montant est incorect."

                player1_bal, _ = trapcoins_handler(type="get", userid=str(self.player1))
                player2_bal, __ = trapcoins_handler(type="get", userid=str(self.player2))
                err = False

                if self.wanted_game == "morpion":
                    title = "Morpion"
                elif self.wanted_game == "puissance":
                    title = "Puissance-3"
                elif self.wanted_game == "pfc":
                    title = "Pierre-feuille-ciseaux"
                elif self.wanted_game == "battleship":
                    title = "BattleShip"

                if player1_bal < new_m:
                    msg = f"- **<@{self.player1}>, Tu n'as pas assez de Trapcoins !!\n\n- Tu en as actuellement {afficher_nombre_fr(player1_bal)} {str(self.trapcoins_emoji)}.**"
                    err = True
                elif player2_bal < new_m:
                    msg = f"**- <@{self.player1}>, Le joueur {self.player2} n'as pas assez de Trapcoins !!- \n\nIl en as actuellement {afficher_nombre_fr(player2_bal)} {str(self.trapcoins_emoji)}.**"
                    err = True
                if err:
                    if self.wanted_game == "morpion":
                        game_view = MorpionGame(ctx=self.ctx, player1=self.player1, player2=self.player2, bet_message=None)
                    elif self.wanted_game == "puissance":
                        game_view = Puissance4Game(ctx=self.ctx, player1=self.player1, player2=self.player2)
                    elif self.wanted_game == "pfc":
                        game_view = PierreFeuilleCiseauxGame(ctx=self.ctx, player1=self.player1, player2=self.player2)
                    msg += f"- \n\nLa partie continue avec les **paris désactivés.**\n\n- **C'est à <@{self.player1}> de jouer.**"
                    embed = create_embed(title=title, description=msg)
                    await interaction.message.edit(embed=embed,view=game_view)
                    return await message.delete()
                if self.wanted_game == "morpion":
                    game_view = MorpionGame(ctx=self.ctx, player1=self.player1, player2=self.player2, bet=new_m, bet_message=None)
                elif self.wanted_game == "puissance":
                    game_view = Puissance4Game(ctx=self.ctx, player1=self.player1, player2=self.player2, bet=new_m)
                elif self.wanted_game == "pfc":
                    game_view = PierreFeuilleCiseauxGame(ctx=self.ctx, player1=self.player1, player2=self.player2, bet=new_m)

                if self.wanted_game == "morpion" or self.wanted_game == "puissance":
                    embed = create_embed(title=title, description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- Il y a {new_m} Trapcoins en jeu.\n\n- **C'est à <@{self.player1}> de jouer.**")
                elif self.wanted_game == "pfc":
                    embed = create_embed(title=title, description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- Il y a {new_m} Trapcoins en jeu.\n\n- **À toi de choisir :**")       
                
                await interaction.message.edit(embed=embed,view=game_view)
                await message.delete()
            except asyncio.TimeoutError:
                await self.ctx.channel.send("Délai d'attente dépassé. Veuillez réessayer.")
        else:
            if self.wanted_game == "morpion":
                title = "Morpion"
                game_view = MorpionGame(ctx=self.ctx, player1=self.player1, player2=self.player2, bet_message=None)
            elif self.wanted_game == "puissance":
                title = "Puissance-3"
                game_view = Puissance4Game(ctx=self.ctx, player1=self.player1, player2=self.player2)
            elif self.wanted_game == "pfc":
                title = "Pierre-feuille-ciseaux"
                game_view = PierreFeuilleCiseauxGame(ctx=self.ctx, player1=self.player1, player2=self.player2, bet=None)

            if self.wanted_game == "morpion" or self.wanted_game == "puissance":
                embed = create_embed(title=title, description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- Pari `OFF`.\n\n- **C'est à <@{self.player1}> de jouer.**")
            elif self.wanted_game == "pfc":
                embed = create_embed(title=title, description=f"- <@{self.player1}> (`👑`) vs <@{self.player2}>\n\n- Pari `OFF`.\n\n- **À toi de choisir :**")
            await interaction.message.edit(embed=embed, view=game_view)


class AttenteJoueur(discord.ui.View):
    def __init__(self, ctx: commands.Context, player1, wanted_game: str, bot: Trapard):
        super().__init__(timeout=500)
        self.ctx = ctx
        self.bot = bot
        self.player1 = player1
        self.button = discord.ui.Button(label="Rejoindre", emoji="🕹️", custom_id=f"btn_1", style=discord.ButtonStyle.blurple)
        self.add_item(self.button)
        self.button.callback = lambda interaction=self.ctx, button=self.button: self.on_button_click(interaction, button)
        self.player_found = False
        self.player_found_id = None
        self.player1 = player1
        self.step2 = False
        self.wanted_game = wanted_game

        if self.wanted_game == "morpion" or self.wanted_game == "pfc" or self.wanted_game == "battleship":
            trapcoins_emoji = "<:trapcoins:1108725845339672597>"
            self.bot_btn = discord.ui.Button(label="Jouer contre Trapard", emoji=f"{str(trapcoins_emoji)}",custom_id=f"btn_2", style=discord.ButtonStyle.green)
            self.add_item(self.bot_btn)
            self.bot_btn.callback = lambda interaction=self.ctx, button=self.bot_btn: self.on_button_click(interaction, button)

        if self.step2:
            self.button = discord.ui.Button(label="Rejoindre2", emoji="🕹️", custom_id=f"btn_12", style=discord.ButtonStyle.blurple)
            self.add_item(self.button)
            self.button.callback = lambda interaction=self.ctx, button=self.button: self.on_button_click(interaction, button)            

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        if self.wanted_game == "morpion":
            if button.custom_id == "btn_2":
                view2 = MorpionGame(ctx=interaction, player1=self.player1, player2="trapard", bet_message=None)
                embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs Trapard")
                await interaction.message.edit(embed=embed,view=view2)
            else:
                if interaction.user.id != self.player1:
                    self.player_found = True
                    self.player_found_id = interaction.user.id
                    view2 = Parier(ctx=self.ctx, player1=self.player1, player2=interaction.user.id, wanted_game=self.wanted_game, bot=self.bot)
                    embed = create_embed(title="Morpion", description=f"- <@{self.player1}> (`👑`) vs <@{self.player_found_id}>\n\n- **Souhaites-tu créer une partie avec des Trapcoins en jeu ?**")
                    await interaction.message.edit(embed=embed,view=view2)
                else:
                    embed = create_embed(title="Morpion", description=f"- <@{self.ctx.author.id}> a lancé une partie de Morpion !\n\n- Clique sur le bouton « `Rejoindre` » pour jouer avec lui :\n\n- `❌` <@{self.ctx.author.id}> Tu ne peux pas rejoindre ta propre partie **BUICON**")
                    await interaction.message.edit(embed=embed, view=self)
        elif self.wanted_game == "puissance":
            if interaction.user.id != self.player1:
                self.player_found = True
                self.player_found_id = interaction.user.id
                view2 = Parier(ctx=self.ctx, player1=self.player1, player2=interaction.user.id, wanted_game=self.wanted_game, bot=self.bot)
                embed = create_embed(title="Puissance-3", description=f"<@{self.player1}> (`👑`) vs <@{self.player_found_id}>\n\n- **Souhaites-tu créer une partie avec des Trapcoins en jeu ?**")
                await interaction.message.edit(embed=embed,view=view2)
            else:
                embed = create_embed(title="Puissance-3", description=f"- <@{self.ctx.author.id}> a lancé une partie de Morpion !\n\n- Clique sur le bouton « `Rejoindre` » pour jouer avec lui :\n\n- `❌` <@{self.ctx.author.id}> Tu ne peux pas rejoindre ta propre partie **BUICON**")
                await interaction.message.edit(embed=embed, view=self)
        elif self.wanted_game == "pfc":
            if interaction.user.id != self.player1:
                self.player_found = True
                self.player_found_id = interaction.user.id
                view2 = Parier(ctx=self.ctx, player1=self.player1, player2=interaction.user.id, wanted_game=self.wanted_game, bot=self.bot)
                embed = create_embed(title="Pierre-feuille-ciseaux", description=f"<@{self.player1}> (`👑`) vs <@{self.player_found_id}>\n\n- **Souhaites-tu créer une partie avec des Trapcoins en jeu ?**")
                await interaction.message.edit(embed=embed,view=view2)
                pass
            else:
                if button.custom_id == "btn_2":
                    view2 = PierreFeuilleCiseauxGame(ctx=self.ctx, player1=self.player1, player2="trapard")
                    embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- <@{self.ctx.author.id}> vs Trapard Pierre-feuille-ciseaux !\n\n- **Choisi ton symbole**:")
                else:
                    view2 = self
                    embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- <@{self.ctx.author.id}> a lancé une partie de Pierre-feuille-ciseaux !\n\n- Clique sur le bouton « `Rejoindre` » pour jouer avec lui :\n\n- `❌` <@{self.ctx.author.id}> Tu ne peux pas rejoindre ta propre partie **BUICON**")
                await interaction.message.edit(embed=embed, view=view2)

async def translate1(text: str, *, src: str = 'auto', dest: str = 'fr', session: ClientSession) -> TranslateResult:
    # This was discovered by the people here:
    # https://github.com/ssut/py-googletrans/issues/268
    query = {
        'dj': '1',
        'dt': ['sp', 't', 'ld', 'bd'],
        'client': 'dict-chrome-ex',
        # Source Language
        'sl': src,
        # Target Language
        'tl': dest,
        # Query
        'q': text,
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }

    target_language = LANGUAGES.get(dest, 'Unknown')
    
    async with session.get('https://clients5.google.com/translate_a/single', params=query, headers=headers) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise TranslateError(resp.status, text)

        data = await resp.json()
        src = data.get('src', 'Unknown')
        source_language = LANGUAGES.get(src, src)
        sentences: list[TranslatedSentence] = data.get('sentences', [])
        if len(sentences) == 0:
            raise RuntimeError("Google traduction n'a pas renvoyé de phrases traduites.")

        original = ''.join(sentence.get('orig', '') for sentence in sentences)
        translated = ''.join(sentence.get('trans', '') for sentence in sentences)
        return TranslateResult(
            original=original,
            translated=translated,
            source_language=source_language,
            target_language=target_language,
        )

class hexcodleView(discord.ui.View):
    def __init__(self, reponse: str, ctx: discord.Interaction,bot:Trapard, is_color: str = None, rejouer : bool = False, original_message: int = None):
        super().__init__(timeout=500)
        self.ctx = ctx
        self.reponse = reponse
        self.color = is_color
        self.rejouer = rejouer
        self.bot = bot

        self.aide_btn = discord.ui.Button(label="Aide", style=discord.ButtonStyle.green, emoji="❓", custom_id="help")
        self.add_item(self.aide_btn)
        self.aide_btn.callback = lambda interaction=self.ctx, button=self.aide_btn: self.on_button_click(interaction, button)

        self.regle_btn = discord.ui.Button(label="Règles ", style=discord.ButtonStyle.green, emoji="📏", custom_id="regles")
        self.add_item(self.regle_btn)
        self.regle_btn.callback = lambda interaction=self.ctx, button=self.regle_btn: self.on_button_click(interaction, button)

        if self.color:
            self.color_btn = discord.ui.Button(label="Afficher la couleur générée", style=discord.ButtonStyle.green, emoji="🎨", custom_id="color")
            self.add_item(self.color_btn)
            self.color_btn.callback = lambda interaction=self.ctx, button=self.color_btn: self.on_button_click(interaction, button)
        if self.rejouer:
            self.rejouer_btn = discord.ui.Button(label="Re-jouer", style=discord.ButtonStyle.green, emoji="🔄", custom_id="rejouer")
            self.add_item(self.rejouer_btn)
            self.rejouer_btn.callback = lambda interaction=self.ctx, button=self.rejouer_btn: self.on_button_click(interaction, button)
            

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if button.custom_id == "help":
            await interaction.response.defer()
            fields = [{"name": "1.", "value": "Un code hexadécimal peut être représenté comme RRVVBB où R représente le rouge, V représente le vert et B représente les valeurs bleues. Les chiffres/lettres à ces emplacements indiquent l'intensité de cette couleur ; 0 étant le plus bas, et F étant le plus élevé.", "inline": True}, {"name": "2.",  "value": "Les chiffres de 0 à 9 représentent les dix premières valeurs et A-F peuvent être représentés comme les chiffres 10-15, où 0 est la plus basse intensité, et 15, ou F, est la plus haute intensité.", "inline": True}, {"name": "3.", "value": "Voici quelques codes hexadécimaux courants :```#FFFFFF : Blanc (intensité maximale pour toutes les composantes RVB)\n#000000 : Noir (aucune intensité pour toutes les composantes RVB)\n#FF0000 : Rouge (intensité maximale pour le rouge, aucune intensité pour le vert et le bleu)\n#00FF00 : Vert (intensité maximale pour le vert, aucune intensité pour le rouge et le bleu)\n#0000FF : Bleu (intensité maximale pour le bleu, aucune intensité pour le rouge et le vert)```", "inline": False}]
            embed = create_embed(title="Un hex code c'est quoi ?", description="", fields=fields)
            try: return await self.ctx.response.send_message(embed=embed, ephemeral=True)
            except: return await self.ctx.followup.send(embed=embed, ephemeral=True)
        elif button.custom_id == "color":
            await interaction.response.defer()
            img = create_image_with_color("#"+self.color)
            img.save(f"{FILES_PATH}img_gen{interaction.user.id}.png")
            file = discord.File(f"{FILES_PATH}img_gen{interaction.user.id}.png", filename=f"img_gen{interaction.user.id}.png")
            embed = create_embed(title="HexCodle", description="Voici la couleur que tu as générée.")
            embed.set_image(url=f"attachment://img_gen{interaction.user.id}.png")
            try: await self.ctx.response.send_message(file=file,embed=embed, ephemeral=True)
            except: await self.ctx.followup.send(file=file,embed=embed, ephemeral=True)
            os.remove(f"{FILES_PATH}img_gen{interaction.user.id}.png")
        elif button.custom_id == "regles":
            await interaction.response.defer()
            fields = [{"name": "1.", "value": "Vous aurez 5 essais pour deviner correctement le code hexadécimal de la couleur affichée à l'écran dans la zone cible. Après chaque essai, la couleur correspondant au code hexadécimal que vous avez saisi s'affichera dans la zone de votre proposition.", "inline": True}, {"name": "2.", "value": "Des symboles apparaîtront dans la section des propositions pour indiquer la proximité de votre essai. Utilisez-les pour évaluer votre prochaine proposition ! Voici la signification de chaque symbole :", "inline": True}, {"name": "3.", "value": "```✅ Vous avez trouvé !\n🔼 Proposez un nombre plus élevé (à une différence de 1 ou 2 près)*\n🔽 Proposez un nombre plus bas (à une différence de 1 ou 2 près)*\n⏫ Proposez un nombre bien plus élevé ! (à une différence de 3 ou plus)\n⏬ Proposez un nombre bien plus bas ! (à une différence de 3 ou plus)```", "inline": False}]
            embed = create_embed(title="HexCodle", description='', fields=fields)
            try: return await self.ctx.response.send_message(embed=embed, ephemeral=True)
            except: return await self.ctx.followup.send(embed=embed, ephemeral=True)
        elif button.custom_id == "rejouer":
            return await play_hexcodle(ctx=interaction, bot=self.bot)
    async def on_timeout(self):
        return await self.ctx.edit_original_response(view=None)

class Misc(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
    
    @discord.utils.cached_property
    def replied_message(self) -> Optional[discord.Message]:
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        return None

    @commands.hybrid_command(aliases=['music-stats', "statistique", "db-stats", "statistiques"])
    async def stats(self, ctx: commands.Context):
        """Affiche différentes stats sur Trapard!"""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            data = load_json_data(item="song-stats")
            duration = data['time']
            numPlayed = data['number-played']
            duration = format_duration(duration)
            async def get_database_info():
                await self.bot.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = await self.bot.cursor.fetchall()
                info_string = ""
                tot = 0
                for i, table in enumerate(tables):
                    table_name = table[0]

                    await self.bot.cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    entry_count = await self.bot.cursor.fetchone()[0]

                    info_string += f"- table {i+1}: **{entry_count}** entrées.\n"
                    tot += entry_count

                total_size = os.path.getsize(DB_PATH) / 1024.0 ** 2

                await self.bot.cursor.execute("SELECT COUNT(*) FROM (SELECT * FROM sqlite_master UNION ALL SELECT * FROM sqlite_temp_master);")

                info_string += f"\nTaille totale de la base de données: **{total_size} Mo**.\nNombre total d'entrées: **{tot}**."
                return info_string
            
            fields = []
            fields.append({"name": "La base de données", "value": await get_database_info(), "inline": True})
            fields.append({"name": "La musique", "value": f"`Nombre de musiques jouées` : **{numPlayed}**\n`Temps de musique jouée` : **{duration}**", "inline": True})
            embed = create_embed(title="Les statistiques de Trapard", description="", fields=fields)
            return await ctx.send(embed=embed,view=songsStatsView(ctx=ctx, bot=self.bot))
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name="hexcodle")
    async def hexcodle(self, ctx: discord.Interaction):
        """Trouve le bon code couleur !"""
        return await play_hexcodle(ctx=ctx, bot=self.bot)
    
    @commands.command(name="sainte-parole", description="Affiche une sainte parole.")
    async def sainteparole(self, ctx: discord.Interaction, precheur: discord.Member, parole: str):
        try:
            await command_counter(user_id=str(ctx.user.id), bot=self.bot)
            try: await ctx.response.defer()
            except: pass
            if precheur is None:
                return await ctx.followup.send("Merci de mentionner un membre.", ephemeral=True)
            if parole is None:
                return await ctx.followup.send("Merci de donner une parole.", ephemeral=True)
            dateetheure = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = create_embed(title="Sainte-parole", description=f"- **{precheur.display_name}** a dit:\n\n- {parole} 💬\n\n- Le {dateetheure}")
            return await ctx.followup.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.command(name="fortnite", description="Montrer le rank d'un joueur")
    @app_commands.describe(pseudo="Le pseudo du joueur en question.")
    @app_commands.describe(platforme="La platforme du joueur en question.")
    @app_commands.describe(temps="Le temps voulu des stats du joueur en question.")
    @app_commands.choices(platforme=[
        discord.app_commands.Choice(name="Epic Game", value="epic"),
        discord.app_commands.Choice(name="PlayStation", value="psn"),
        discord.app_commands.Choice(name="X Box", value="xbl")])
    @app_commands.choices(temps=[
        discord.app_commands.Choice(name="Depuis Toujours", value="lifetime"),
        discord.app_commands.Choice(name="Cette saison", value="season")])
    async def fortniteGet(self, ctx: discord.Interaction, pseudo:str, platforme: discord.app_commands.Choice[str], temps: discord.app_commands.Choice[str]):
        try:
            try: await ctx.response.defer()
            except:pass
            url = f"https://fortnite-api.com/v2/stats/br/v2?name={pseudo}&accountType={platforme.value}&timeWindow={temps.value}&image=all"
            headers = {
                "Authorization": os.environ.get("FORTNITE_API"),
                "Content-Type": "application/json",
            }
            async with self.bot.session.get(url, headers=headers) as response:
                data = await response.json()
            
            if response.status == 200:
                return await ctx.followup.send(data["data"]["image"])
            else:
                embed = create_embed(title="Fortnite stats", description=f"Une erreur s'est produite.\nIl semble que le joueur `{pseudo}` sur la platforme `{platforme.name}` est incorrect.\nMerci de vérifier les informations.")
                return await ctx.followup.send(embed=embed)
        except:
            LogErrorInWebhook()

    @commands.hybrid_command(name="traduction", aliases=["trad", "traduire", "translate"])
    async def trad(self, ctx: Context, *, message: Annotated[Optional[str], commands.clean_content] = None):
        """Traduire un texte en Français."""
        try:
            if message is None:
                reply = ctx.replied_message
                if reply is not None:
                    message = reply.content
                else:
                    return await ctx.send('Aucun message à traduire.')
            try:
                result = await translate1(message, session=self.bot.session)
            except Exception as e:
                return await ctx.send(f'An error occurred: {e.__class__.__name__}: {e}')

            embed = discord.Embed(title='Traduction', colour=0x4284F3)
            embed.add_field(name=f'De {result.source_language}', value=result.original, inline=False)
            embed.add_field(name=f'Vers {result.target_language}', value=result.translated, inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(hidden=True)
    async def mobitag(self, ctx: commands.Context, destinataire: str, *, message: str):
        """Envoyer un Mobitag en Nouvelle-Calédonie."""
        if len(destinataire) != 6:
            embed = create_embed(title="Mobitag", description=f"Erreur, un numéro Calédonien est composé de 6 chiffres. Et non {len(destinataire)}...")
            return await ctx.send(embed=embed)
        if len(message) > 150:
            embed = create_embed(title="Mobitag", description=f"Erreur, Mobitag autorise l'envoi de messages de 150 caractères ou moins. Et non {len(message)}...")
            return await ctx.send(embed=embed)

        driver = getDriver()
        display = Display(visible=0, size=(1024, 768))
        display.start()
        driver.get("http://www.mobitag.nc/?lang=fr")
        WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.XPATH, '/html/body/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr[1]/td[1]/table/tbody/tr[2]/td[2]/table/tbody/tr[4]/td/form/input[2]'))).click()
        cookies = driver.get_cookies()
        mbt_cook_value = None
        for cookie in cookies:
            if cookie['name'] == 'mbt_cook':
                mbt_cook_value = cookie['value']
                break
        img_element = driver.find_element(By.XPATH, "/html/body/table/tbody/tr[2]/td/table/tbody/tr/td/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[1]/table/tbody/tr[4]/td/table/tbody/tr[1]/td/img")
        img_base64 = img_element.screenshot_as_base64
        img_data = b64decode(img_base64)
        img = Image.open(BytesIO(img_data))
        img.save(f"{FILES_PATH}mobitag_code.png")

        file = discord.File(f"{FILES_PATH}mobitag_code.png", filename=f"mobitag_code.png")
        embed = create_embed(title="Mobitag", description="Écris le captcha...")
        embed.set_image(url=f"attachment://mobitag_code.png")

        captcha_msg = await ctx.send(file=file,embed=embed)

        def check(message: discord.Message):
            return ctx.author.id == message.author.id and message.channel == ctx.channel
        
        try:
            message_code = await self.bot.wait_for("message", check=check, timeout=500)
        except asyncio.TimeoutError:
            driver.close()
            display.stop()
            return
        await captcha_msg.delete()
        code = message_code.content.upper()
        await message_code.delete()
        
        url = "http://www.mobitag.nc/mbe?"
        params = f"babar={mbt_cook_value}&typsms=mbgE&lang=fr&cde=atem12&imgaleat={code}&desti_crc=6&desti={destinataire}&telexp_crc=0&telexp=&smsok=OK&message={message}&caracteres={150-len(message)}&mail_send=&msgerr=&time_reinit_max=08%3A00&time_reinit=+07%3A23"
        
        driver.get(url+params)

        try:
            error = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, '/html/body/table/tbody/tr[2]/td/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr[6]/td/table/tbody/tr[2]/td/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr/td/table/tbody/tr[1]/td'))).text
            if 'Code image non valide' in error:
                embed = create_embed(title="Mobitag", description="Captcha invalide.")
                return await ctx.send(embed=embed)
        except:
            embed = create_embed(title="Mobitag", description="Message envoyé avec succès!")
            return await ctx.send(embed=embed)
        finally:
            display.stop()
            driver.close()

    @commands.hybrid_command(aliases=['latency', "lag"])
    async def ping(self, ctx: commands.Context):
        """Affiche la latence du bot."""
        latency = round(self.bot.latency * 1000)
        embed = create_embed(title="Ping", description=f"Pong !\nLatence du bot : **{latency}** ms")
        return await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def binaire(self, ctx: Context, *,texte: str=None):
        """Convertie de texte en binaire, ou l'inverse."""
        def convert_to_binary(input_data):
            return ' '.join(format(ord(char), '08b') for char in str(input_data))
        def convert_from_binary(binary_data):
            try:
                binary_values = binary_data.split()
                return ''.join([chr(int(b, 2)) for b in binary_values])
            except ValueError:
                return 'Un code binaire doit contenir uniquement des `1` et des `0` ...'
        try:
            if texte is None:
                reply = ctx.replied_message
                if reply is not None:
                    texte = reply.content
                else:
                    return await ctx.send('Aucun message à convertir.')
            if not texte or texte == "" or texte == " ":
                return
            if set(texte.replace(" ", "")) == {"1", "0"}:
                embed = create_embed(title="Binaire en texte", description=convert_from_binary(texte))
            else:
                embed = create_embed(title="Texte en binaire", description=convert_to_binary(texte))
            return await ctx.reply(embed=embed)
        except: LogErrorInWebhook()

    @commands.hybrid_command(name="heure", aliases=["time"])
    async def heure(self, ctx: commands.Context, country_code: str):
        """Afficher l'heure d'un pays en fonction de son country code."""
        result = get_local_time(country_code)
        if isinstance(result, datetime):
            embed = create_embed(title="Heure", description=f"L'heure actuelle en {country_code.upper()} est : {result.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return await ctx.send(embed=embed)
        else:
            embed = create_embed(title="Heure", description=result)
            return await ctx.send(embed=embed)

    @commands.hybrid_command(name="morpion")
    async def morpion(self, ctx: commands.Context):
        """Jouer au jeu du morpion."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        try:
            if lol_player_in_game(self.bot.zigotos[ctx.author.id]) and int(ctx.author.id) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(ctx.author.id)] is not None:
                embed = create_embed(title="G-lol-bet", description=f"Il semble que vous êtes actuellement en game et que vous avez parié!\n\nVous ne pouvez pas parier vos {str(trapcoins_emoji)} durant la partie. **BUICON**.")
                return await ctx.send(embed=embed)
        except:
            pass
        attente_embed = create_embed(title="Morpion", description=f"- <@{ctx.author.id}> a lancé une partie de **Morpion** !\n\n- Clique sur le bouton « `Rejoindre` » pour jouer avec lui :")
        view = AttenteJoueur(ctx=ctx, player1=ctx.author.id, wanted_game="morpion", bot=self.bot)
        await ctx.send(embed=attente_embed,view=view)

    @commands.hybrid_command(name="puissance-3")
    async def puissance3(self, ctx: commands.Context):
        """Jouer au jeu du Puissance 4 mais en 3 :D."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        if lol_player_in_game(self.bot.zigotos[ctx.author.id], bot=self.bot) and int(ctx.author.id) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(ctx.author.id)] is not None:
            embed = create_embed(title="G-lol-bet", description=f"Il semble que vous êtes actuellement en game et que vous avez parié!\n\nVous ne pouvez pas parier vos {str(trapcoins_emoji)} durant la partie. **BUICON**.")
            return await ctx.send(embed=embed)
        attente_embed = create_embed(title="Puissance-3", description=f"- <@{ctx.author.id}> a lancé une partie de **Puissance-3 !**\n\n- Clique sur le bouton « `Rejoindre` » pour jouer avec lui :")
        attendre = AttenteJoueur(ctx=ctx, player1=ctx.author.id, wanted_game="puissance", bot=self.bot)
        await ctx.send(embed=attente_embed,view=attendre)

    @commands.hybrid_command(name="report-bug")
    async def report(self, ctx: commands.Context, *, bug: str):
        """Report un bug de Trapard."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        text = bug + f"\nEnvoyé par {ctx.author.name}."
        DiscordWebhook(url=os.environ.get("REPORT_BUG_WEBHOOK"), content=text).execute()
        return await ctx.send("Le message a bien été envoyé, !Reu$ va regarder cela soon ! Merci pour l'info.", ephemeral=True)

    @commands.hybrid_command(name="pierre-feuille-ciseaux", aliases=["pfc"])
    async def pierrefeuilleciseaux(self, ctx: commands.Context):
        """Jouer au jeu du pierre-feuille-ciseaux."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        attente_embed = create_embed(title="Pierre-feuille-ciseaux", description=f"- <@{ctx.author.id}> a lancé une partie de **Pierre-feuille-ciseaux** !\n\n- Clique sur le bouton « `Rejoindre` » pour jouer avec lui :")
        view = AttenteJoueur(ctx=ctx, player1=ctx.author.id, wanted_game="pfc", bot=self.bot)
        await ctx.send(embed=attente_embed,view=view)

    @commands.hybrid_command(name="trapardeur", description="")
    async def trapardeurs(self, ctx: commands.Context, user: discord.User = None):
        """Affiche tes stats de trapardeur"""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if user is None:
                userID = ctx.author.id
                user = ctx.author
            else:
                userID = user.id

            avatar_image = await get_avatar(user, self.bot.session)
            userHandler = Trapardeur(pool=self.bot.pool, userId=str(userID))
            if await userHandler.is_in():
                data = await userHandler.get()
                # data = load_json_data(item="trapeusr", userid=str(ctx.user.id))
                if userID in self.bot.day_vocal_time:
                    day_time_spent = int(self.bot.day_vocal_time[userID])
                    day_time_spent = format_duration2(day_time_spent)
                else:
                    day_time_spent = "0m"
                xp = await xp_calculation(user_id=str(userID), bot=self.bot)
                level = calculate_level(xp)
                xp = xp % 500
                if '.' in str(xp):
                    xp = str(xp).split('.')[0]
                if '.' in str(level):
                    level = str(level).split('.')[0]
                image = draw_rank(niveau=str(level), messages=str(data[0][3]), temps_vocal_tot=format_duration2(data[0][2]), temps_total_vocal_auj=day_time_spent, commandes=str(data[0][4]), experience=str(xp), name=str(user.display_name), avatar=avatar_image)
                img = Image.open(image)
                img.save(f"{FILES_PATH}{userID}.png")
                file = discord.File(f"{FILES_PATH}{userID}.png", filename=f"Rank.png")
                embed = discord.Embed(title=f"Voici les stats de trapardeur de {user.display_name} !")
                embed.set_image(url=f"attachment://Rank.png")
                await ctx.send(file=file, embed=embed)
                return os.remove(f"{FILES_PATH}{userID}.png")
            else:
                embed = create_embed(title="Trapardeur", description=f"Tu n'as pas de stats de trapardeur !")
                return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name='trapardeur-top')
    async def trapardeurtop(self, ctx: commands.Context):
        """Affiche le top 25 des trapardeurs."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        data = await Trapardeur(pool=self.bot.pool).get_all()
        data = set(data)
        sorted_data = sorted(data, key=lambda x: x[2], reverse=True)
        fields = f"```{printFormat('Pseudo', 17)}|{printFormat('Niveau', 10)}|{printFormat('XP', 10)}|{printFormat('Temps vocal', 17)}|{printFormat('Messages', 10)}|{printFormat('Commandes', 10)}\n"
        fields += f"{'-'*17}|{'-'*10}|{'-'*10}|{'-'*17}|{'-'*10}|{'-'*10}\n"
        for i in range(25):
            try:
                user_id = sorted_data[i][1]
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    user = user.display_name
                except:
                    user = "Inconnu"
                time_spent = sorted_data[i][2]
                message_sent = sorted_data[i][3]
                command_used = sorted_data[i][4]
                xp = await xp_calculation(user_id=str(user_id), bot=self.bot)
                level = calculate_level(xp)
                fields += f"{printFormat(user, 17)}|{printFormat(str(int(level)), 10)}|{printFormat(str(int(xp)), 10)}|{printFormat(str(format_duration(time_spent)), 17)}|{printFormat(str(int(message_sent)), 10)}|{printFormat(str(int(command_used)), 10)}\n"
            except IndexError:
                pass
        fields += "```"
        embed = create_embed(title="Top 25 trapardeur", description=fields)
        return await ctx.send(embed=embed)

    @commands.hybrid_command(name="tts")
    async def createTTS(self, interaction: commands.Context, *, text: str, voix: Literal["Homme", "Femme"]="Homme"):
        """Créer un text to speach !"""
        await command_counter(user_id=str(interaction.author.id), bot=self.bot)
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if voix == "Femme":
                tts = TTS("tts_models/fr/mai/tacotron2-DDC").to(device)
            else:
                tts = TTS("tts_models/fr/css10/vits").to(device)
            tts.tts_to_file(text=text, file_path=f"{FILES_PATH}tts.mp3")
            return await interaction.send(f"Voilà ton TTS {interaction.author.display_name}!", file=discord.File(f"{FILES_PATH}tts.mp3"))
        except Exception:
            LogErrorInWebhook()

    @commands.hybrid_command(name="pile-face", aliases=["coin-flip", "pile", "face", "pile-ou-face"])
    async def coin_flip(self, ctx: Context):
        if random.randint(1,2) == 1:
            return await ctx.send("https://files.reus.nc/images/100_pile.jpg")
        else:
            return await ctx.send("https://files.reus.nc/images/100_face.jpg")

    @commands.command()
    async def source(self, ctx: commands.Context, *, command: str = None):
        """Affiche le code source de la commande souhaité."""
        # Code used from https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L405-L446
        source_url = 'https://github.com/reusteur73/Trapard'
        branch = 'master'
        if command is None:
            return await ctx.send(source_url)

        obj = self.bot.get_command(command.replace('.', ' '))
        if obj is None:
            return await ctx.send('Cette commande ne semble pas exister.')

        # since we found the command we're looking for, presumably anyway, let's
        # try to access the code itself
        src = obj.callback.__code__
        module = obj.callback.__module__
        filename = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        if filename is None:
            return await ctx.send('Impossible de trouver la source de cette commande.')
        location = os.path.relpath(filename).replace('\\', '/')

        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        await ctx.send(final_url)

async def play_hexcodle(ctx: commands.Context, bot: Trapard):
    
    def generate_random_color():
        color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        return color
    
    def check_answer(answer: str, guess: str):
        """Return 6 emojis based on answer and guess."""
        emojis = ""

        hex_chars = ["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"]

        answer = answer.upper().replace("#", "")
        guess=guess.upper()

        if answer == guess:
            return ("✅ ✅ ✅ ✅ ✅ ✅")
        for g, a in zip(guess, answer):
            if g == a:
                emojis += ("✅ ")
            else:
                g_index = hex_chars.index(g)
                a_index = hex_chars.index(a)
                diff = a_index - g_index
                if diff > 0:
                    if diff >= 3:
                        emojis += ("⏫ ")
                    else:
                        emojis += ("🔼 ")
                else:
                    if diff <= -3:
                        emojis += ("⏬ ")
                    else:
                        emojis += ("🔽 ")
        return emojis

    try:
        if isinstance(ctx, commands.Context):
            user_id = ctx.author.id
            is_ctx = True
        else:
            user_id = ctx.user.id
            is_ctx = False
        random_color = generate_random_color()
        generated_image = create_image_with_color(random_color)
        generated_image.save(f"{FILES_PATH}random_color_image{user_id}.png")
        embed = create_embed(title="HexCodle", description="Aucun guess pour le moment ...")
        file = discord.File(f"{FILES_PATH}random_color_image{user_id}.png", filename=f"random_color_image{user_id}.png")
        embed.set_image(url=f"attachment://random_color_image{user_id}.png")
        view = hexcodleView(reponse=random_color, ctx=ctx, bot=bot)
        if is_ctx:
            msg = await ctx.send(file=file,embed=embed, view=view)
        else:
            await ctx.response.send_message(file=file,embed=embed, view=view)

        def check(message: discord.Message):
            return user_id == message.author.id and message.channel == ctx.channel
        guesses = []
        for essaie in range(0, 5):
            try:
                message = await bot.wait_for("message", check=check, timeout=500)
            except asyncio.TimeoutError:
                view = hexcodleView(reponse=random_color, ctx=ctx, rejouer=True, bot=bot)
                embed = create_embed(title="HexCodle", description=f"{''.join(guesses)} {essaie+1}/5 essaies\n\nTu as mis trop de temps à répondre.\n\nLa bonne réponse était **{random_color}**.")
                embed.set_image(url=f"attachment://random_color_image{user_id}.png")
                if is_ctx:
                    await msg.edit(embed=embed, view=view)
                else:
                    await ctx.edit_original_response(embed=embed, view=view)
                return os.remove(f"{FILES_PATH}random_color_image{user_id}.png")
            await message.delete()
            allowed = ["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"]
            guess = message.content.replace("#", "").upper()
            
            if len(guess) != 6:
                view = hexcodleView(reponse=random_color, ctx=ctx, bot=bot)
                guesses.append(f"{essaie+1}. ❌ ❌ ❌ ❌ ❌ ❌ | **{guess}**\n\n")
                embed = create_embed(title="HexCodle", description=f"{''.join(guesses)} {essaie+1}/5 essaies\n\n**Attention, un code hexadécimal doit contenir uniquement 6 caratères.**\n\n**Là, tu en as donné {len(guess)}...**")
                embed.set_image(url=f"attachment://random_color_image{user_id}.png")
                if is_ctx:
                    await msg.edit(embed=embed, view=view)
                else:
                    await ctx.edit_original_response(embed=embed, view=view)
                continue
            error = False
            for c in guess:
                if c not in allowed:
                    view = hexcodleView(reponse=random_color, ctx=ctx, bot=bot)
                    guesses.append(f"{essaie+1}. ❌ ❌ ❌ ❌ ❌ ❌ | **{guess}**\n\n")
                    embed = create_embed(title="HexCodle", description=f"{''.join(guesses)} {essaie+1}/5 essaies\n\n**Attention, le caractère `{c}` ne correspond pas à un caractère hexadécimal convenable. Merci de voir la page d'aide pour plus d'informations.**")
                    embed.set_image(url=f"attachment://random_color_image{user_id}.png")
                    if is_ctx:
                        await msg.edit(embed=embed, view=view)
                    else:
                        await ctx.edit_original_response(embed=embed, view=view)
                    error = True
                    break
            if error:
                continue
            result = check_answer(random_color, guess)
            # guesses.append(f"{essaie+1}. {result} | **{guess}**\n\n")
            guess =' '.join(caractere for caractere in guess)
            guesses.append(f"- {result}\n**{essaie+1}/5**\n- {convert_str_to_emojis(guess)}\n\n")
            view = hexcodleView(reponse=random_color, ctx=ctx, is_color=guess, bot=bot)
            if result == "✅ ✅ ✅ ✅ ✅ ✅":
                trapcoins_handler(type="add", userid=str(user_id), trapcoins_val=100000000)
                view = hexcodleView(reponse=random_color, ctx=ctx, is_color=guess, rejouer=True, bot=bot)
                embed = create_embed(title="HexCodle", description=f"""{''.join(guesses)} {essaie+1}/5 essaies\n\n**Bravo, tu as trouvé le bon code hexadécimal !**\n\n**Tu as gagné 100M Trapcoins!**""")
                embed.set_image(url=f"attachment://random_color_image{user_id}.png")
                if is_ctx:
                    await msg.edit(embed=embed, view=view)
                else:
                    await ctx.edit_original_response(embed=embed, view=view)
                return os.remove(f"{FILES_PATH}random_color_image{user_id}.png")
            embed = create_embed(title="HexCodle", description = f"""{''.join(guesses)} {essaie+1}/5 essaies""")
            embed.set_image(url=f"attachment://random_color_image{user_id}.png")
            if is_ctx:
                await msg.edit(embed=embed, view=view)
            else:
                await ctx.edit_original_response(embed=embed, view=view)
        view = hexcodleView(reponse=random_color, ctx=ctx, is_color=guess, rejouer=True, bot=bot)
        embed = create_embed(title="HexCodle", description=f"""{''.join(guesses)} {essaie+1}/5 essaies\n\n**Tu n'as pas trouvé le bon code hexadécimal dans les 5 essaies impartie. Réessaies !**""")
        embed.set_image(url=f"attachment://random_color_image{user_id}.png")
        if is_ctx:
            await msg.edit(embed=embed, view=view)
        else:
            await ctx.edit_original_response(embed=embed, view=view)
        return os.remove(f"{FILES_PATH}random_color_image{user_id}.png")
    except: LogErrorInWebhook()

async def setup(bot: Trapard):
    await bot.add_cog(Misc(bot))