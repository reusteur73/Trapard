from typing import Literal, List, Tuple
from discord.ext import commands
from youtube_search import YoutubeSearch
from discord import app_commands
from pytube import YouTube
import discord
from discord.ui import Modal, TextInput
from time import perf_counter
from asyncio import sleep
from bot import Trapard
from .utils.functions import LogErrorInWebhook, command_counter, create_embed, convert_str_to_emojis, printFormat, convert_int_to_emojis, is_url, convert_txt_to_colored
from .utils.path import PLAYLIST_LIST, MUSICS_FOLDER, SOUNDBOARD
from .utils.context import Context as CustomContext
import traceback, re, random, os, asyncio, threading, base64, io
from asqlite import Pool
from PIL import Image, ImageDraw, ImageFont

def is_comma_separated(index_string):
    """Check if there is a `,` or `-` in given string, return True or False"""
    try:
        if isinstance(index_string, str):
            parts = index_string.split(",")
            if len(parts) > 1:
                return True
            else:
                parts = index_string.split("-")
                if len(parts) > 1:
                    return True
            return False
        else:
            return False
    except Exception as e:
        LogErrorInWebhook()
        return False

def convert_to_minutes_seconds(music_len_sec: str, just_int:bool=False):
    try:
        if not str(music_len_sec).isdigit():
            return ""
        music_len_sec = int(music_len_sec)
        minutes = music_len_sec // 60
        seconds = music_len_sec % 60
        if just_int:
            return f'{minutes} {seconds}'
        else:
            return f'{minutes}m{seconds}s'
    except Exception as e:
        LogErrorInWebhook()

async def getMusicQueue(server_id, bot: Trapard, music_list_handler, current_song_time=0):
    try:
        if server_id not in bot.music_queues:
            return "Il n'y a pas de musiques dans la file d'attente."
        queue = bot.music_queues[server_id]
        if len(queue) == 0:
            return "Il n'y a pas de musiques dans la file d'attente."

        output = []
        field = ""
        queue_limit = 10
        total_pages = (len(queue) + queue_limit - 1) // queue_limit

        for page in range(total_pages):
            embed = discord.Embed(title="File d'attente de musiques")
            if server_id in bot.current_track:
                track = bot.current_track[server_id]
                index, dler = await music_list_handler.get_index_by_music_name(str(track))
                track_duration = await music_list_handler.get_song_duration_by_index(index)
                pbar = create_progress_bar(current_song_time, int(track_duration))
                field = f"```🎵 {track}\nTéléchargé par: {dler}\nNuméro de piste: {convert_str_to_emojis(index)}\nProgression: [{pbar}] - {convert_int_to_emojis(current_song_time)}/{convert_str_to_emojis(str(track_duration))}s```"
                embed.add_field(name='- Musique actuel:', value=field, inline=False)
            start_index = page * queue_limit
            end_index = min(start_index + queue_limit, len(queue))
            for i in range(start_index, end_index):
                try:
                    try:
                        index1, dler  = await music_list_handler.get_index_by_music_name(str(queue[i]))
                        dler = bot.unique_downloader_display_names[int(dler)]
                    except:
                        index1 = "?"
                        dler = "?"
                    field = f"```🎵 {printFormat(str(queue[i]), 33)}" + f"\nTéléchargé par: {printFormat(dler, 20)}\nNuméro de piste: {convert_str_to_emojis(printFormat(index1, 4))}```"
                    embed.add_field(name=f'`{convert_str_to_emojis(printFormat(str(i + 1), 3))}:`', value=field, inline=False)
                except:
                    traceback.print_exc()
                    pass
            embed.add_field(name="", value=f"```                    Page {convert_str_to_emojis(str(page+1))}/{convert_str_to_emojis(str(total_pages))}```", inline=False)
            output.append(embed)
        return output

    except Exception as e:
        traceback.print_exc()

def rename(filename: str):
    """Rename music name. Use this before saving name in music list"""
    try:
        filename = re.sub(r'\.mp3$', '', filename)
        ob = list(filename)
        out = []
        if len(ob) > 30:
            index = 0
            for o in ob:
                if index == 30:
                    break
                out.append(o)
                index += 1

            out2 = ""
            for u in out:
                out2 += str(u)

            out2 += ".mp3"
            clean_text = re.sub(r'\.mp3$', '', out2)
            clean_text = re.sub("[\"\(\)\[\]\|\-\/., ]", "", out2).strip()
            clean_text += ".mp3"

        else:
            clean_text = re.sub(r'\.mp3$', '', filename)
            clean_text = re.sub("[\"\(\)\[\]\|\-\/., ]", "", clean_text).strip()
            clean_text += '.mp3'

        return clean_text
    except Exception as e:
        LogErrorInWebhook()

def parse_user_indexs(chaine: str):
    """
        transform user index input to string


        return tuple:

        `valeur` `erreur` 
        both can be none
    """
    try:
        ALLOWED = ["1","2","3","4","5","6","7","8","9","0", "*", '-']
        while chaine.endswith(","):
            chaine = chaine[::-1].replace(",", "", 1)[::-1]
        
        if ' ' in chaine:
            chaine = chaine.replace(" ", "")

        if "-" in chaine:
            nombre = []
            if chaine.count("-") > 1:
                return None, f"- Il ne peut y avoir qu'un seul `-` dans la chaine d'entrée (`{chaine}`)"
            if chaine.startswith("-") or chaine.endswith("-"):
                return None, f"- Il faut un nombre avant et après le `-` dans la chaine d'entrée (`{chaine}`)"
            if "," in chaine:
                return None, f"- Il ne peut pas y avoir de `,` dans la chaine d'entrée (`{chaine}`)"
            n1 = chaine.split("-")[0]
            n2 = chaine.split('-')[1]
            for char in n1:
                if char not in ALLOWED:
                    return None, f"- Le caractère {char} n'est pas autorisé dans la chaine d'entrée (`{chaine}`)"
            for char in n2:
                if char not in ALLOWED:
                    return None, f"- Le caractère {char} n'est pas autorisé dans la chaine d'entrée (`{chaine}`)"

            for i in range(int(n1), int(n2)+1):
                nombre.append(str(i))
            return nombre, None
        if ',' in chaine:
            nombres = chaine.split(',')
        nombres_propres = []

        try:
            for nombre in nombres:
                if '*' in nombre:
                
                    multiplicateur = int(nombre.split('*')[0])
                    valeur = int(nombre.split('*')[1])
                    nombres_propres.extend([str(valeur)] * multiplicateur)
                else:
                    for char in nombre:
                        if char not in ALLOWED:
                            suggestions = [nombre for nombre in nombres if nombre.isdigit()]
                            text = f"- Le caractère {char} n'est pas autorisé dans la chaine d'entrée (`{chaine}`)"
                            if suggestions:
                                suggestions_chaine = ','.join(suggestions)
                                return None, f"**{text}**, as-tu essayé `{suggestions_chaine}` ?"
                            else:
                                return None, f"**{text}**, as-tu essayé `{','.join(nombres)}` ?"
                    nombres_propres.append(nombre)
            resultat = ','.join(nombres_propres)
            if resultat.endswith(","):
                resultat = resultat[::-1].replace(",", "", 1)[::-1]
            liste = resultat.split(",")
            return liste, None

        except ValueError:
            suggestions = [nombre for nombre in nombres if nombre.isdigit()]
            if suggestions:
                suggestions_chaine = ','.join(suggestions)
                return None, f"- Erreur dans `{chaine}`, as-tu essayé `{suggestions_chaine}` ?"
            else:
                return None, f"- Erreur dans `{chaine}`, as-tu essayé `{','.join(nombres)}` ?"
    except:
        LogErrorInWebhook()

def create_progress_bar(current_time: int, total_time: int, bar_length=20):
    progress = current_time / total_time
    num_bar_filled = int(bar_length * progress)
    num_bar_empty = bar_length - num_bar_filled
    progress_bar = '🟩' * num_bar_filled + '⬛' * num_bar_empty
    return str(progress_bar)

def getMusicList(playlistname):
    try:
        lines = open(PLAYLIST_LIST, "r").readlines()
        for line in lines:
            lineF = line.split("=")[0]
            if lineF == playlistname:
                musicList = line.split("=")[1]
                musicList = musicList.split(",")
                musicList.pop()
                return musicList
    except Exception as e:
        LogErrorInWebhook()

def draw_music(
        music_name: str,
        downloader: str,
        pbar_percent: int,
        track_duration: str,
        current_track_time: str,
        next_musics: list,
        queue_len: str,
        serverid: int
    ):
    
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

    FONT = "/home/debian/trapard/files/Retron2000.ttf"
    img = Image.open("/home/debian/trapard/files/music_img.png")

    # Defining draw
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 18)

    fontLarge = ImageFont.truetype(FONT, 64)
    fontSmall = ImageFont.truetype(FONT, 44)

    draw_text(draw, music_name, (900, 55), (155, 28), fontLarge, "white")

    draw_text(draw, downloader, (1100, 205), (0, 0), fontLarge, "white")

    draw_text(draw, f"{track_duration} / {current_track_time}", (960, 550), (0, 0), fontLarge, "white")

    draw_text(draw, f"{queue_len}", (1300, 695), (0, 0), fontSmall, "white")

    for i, music in enumerate(next_musics):
        draw_text(draw, music, (960, 800 + 70 * i), (0, 0), fontSmall, "white")

    MAX = 1780
    MIN = 139

    if pbar_percent > 100:
        pbar_percent = 100

    width = (MAX - MIN) * pbar_percent / 100

    draw.rounded_rectangle([(MIN, 360), (MIN + width, 497)], fill="green", outline="green", radius=25)

    draw_text(draw, f"{pbar_percent}%", (960, 400), (0, 0), fontLarge, "black")

    fp = io.BytesIO()
    img.convert("RGBA").save(fp, "PNG")
    img.save(f"/home/debian/trapard/files/{serverid}_music_player.png")
    return

def getVideoId(title):
    try:
        results = YoutubeSearch(title, max_results=1).to_dict()
        id = results[0]["id"]
        url = 'https://www.youtube.com/watch?v=' + id
        return url
    except Exception as e:
        LogErrorInWebhook()

async def storeSkippedSong(pool: Pool, songname: str, userid:str):
    """Store the skipped song in the database."""
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetchone("SELECT * FROM SkippedSongs WHERE songName = ? AND userId = ?", (songname, userid,))
                if data is None:
                    await conn.execute("INSERT INTO SkippedSongs (songName, userId, count) VALUES (?, ?, 1)", (songname, userid,))
                    return True
                else:
                    await conn.execute("UPDATE SkippedSongs SET count = ? WHERE songName = ? AND userId = ?", (data[3] + 1, songname, userid,))
                    return True
    except Exception as e:
        LogErrorInWebhook()

async def FavSongsDbHandler(pool: Pool, song_name, user_id):
    """Count the number of time a song is played by a user and add it to the db."""
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if song_name:
                    # try get userid and song name from db
                    data = await conn.fetchone("SELECT * FROM FavSongs WHERE songName = ? AND userId = ?", (song_name, user_id,))
                    if data is None:
                        await conn.execute("INSERT INTO FavSongs (songName, userId, count) VALUES (?, ?, 1)", (song_name, user_id,))
                        return True
                    else:
                        await conn.execute("UPDATE FavSongs SET count = ? WHERE songName = ? AND userId = ?", (data[3] + 1, song_name, user_id,))
                        return True
    except Exception as e:
        LogErrorInWebhook()

async def IncrementMusicPlayed(TrackName, pool: Pool):
    """Increment the number of times a song has been played"""
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                data = await conn.fetchone("SELECT * FROM SongPlayedCount WHERE songName=?", (TrackName,))
                if data is None:
                    await conn.execute("INSERT INTO SongPlayedCount (songName, count) VALUES (?, ?)", (TrackName, 1,))
                else:
                    await conn.execute("UPDATE SongPlayedCount SET count=? WHERE songName=?", (data[2] + 1, TrackName,))
    except Exception as e:
        LogErrorInWebhook()

async def get_latest_message_from_channel(channel: discord.TextChannel) -> discord.Message:
    """
    Return last message from a given discord channel.
    """
    async for message in channel.history(limit=1, oldest_first=False):
        return message
    return None

async def check_voice_state(vc: discord.VoiceClient):
    # Récupérer les membres connectés au canal vocal
    members = vc.channel.members
    
    # Vérifier si le bot est le seul membre connecté
    if len(members) == 1 and members[0].id == vc.user.id:
        # Arrêter la musique si personne n'est connecté
        return True
    return False

def get_all_playlists_names():
    try:
        lines = open(PLAYLIST_LIST, 'r').readlines()
        out = []
        for line in lines:
            if line != "" or line != "\n":
                name = line.split("=")[0]
                out.append(name)
        return out
    except Exception as e:
        LogErrorInWebhook()

class Url:
    url: str

class get_artist_from_title():
    def __init__(self, title: str, bot: Trapard):
        self.bot = bot
        token = asyncio.run(self.get_access_token())
        self.artists = asyncio.run(self.main(title=title, access_token=token))

    async def get_access_token(self):
        client_id = os.environ.get("SPOTIFY_CLIENT")
        client_secret = os.environ.get("SPOTIFY_SECRET")
        # Définir les paramètres de la requête d'obtention du jeton d'accès
        data = {
            'grant_type': 'client_credentials'
        }
        
        # Ajouter le client ID et le client secret aux en-têtes de la requête
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
        }
        
        # Envoyer la requête d'obtention du jeton d'accès à l'API de Spotify
        response = await self.bot.session.post('https://accounts.spotify.com/api/token', data=data, headers=headers)
        # response = requests.post()
        
        # Analyser la réponse JSON
        data = await response.json()
        
        # Vérifier si le jeton d'accès a été retourné avec succès
        if 'access_token' in data:
            return data['access_token']
        else:
            return None
            
    async def main(self, title, access_token):
        params = {
            'q': title,
            'type': 'track',
            'limit': 50
        }
        
        headers = {
            'Authorization': 'Bearer ' + access_token
        }
        
        response = await self.bot.session.get('https://api.spotify.com/v1/search', params=params, headers=headers)        
        data = await response.json()

        if 'tracks' in data and 'items' in data['tracks'] and len(data['tracks']['items']) > 0:
            artists = []  # Liste pour stocker les artistes
            for track in data['tracks']['items']:
                for artist in track['artists']:
                    artists.append(artist['name'])
            return artists
        else:
            return None

class EndSessionBtn(discord.ui.View):
    def __init__(self, bot: Trapard, music_list_handler, music_controler, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.music_list_handler = music_list_handler
        self.music_controler = music_controler

        # self.all_btn = discord.ui.Button(label="play all", custom_id="play_all")
        # self.add_item(self.all_btn)
        # self.all_btn.callback = lambda interaction=self.ctx, button=self.all_btn: self.on_button_click(interaction, button, index=self.index)

    # async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button, index):
    #     if button.custom_id == "play_all":
    #         await command_counter(user_id=str(interaction.user.id), bot=self.bot)
    #         if interaction.channel.name != "musique":
    #             embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
    #             return await interaction.channel.send(embed=embed)
    #         return await NewPlayAll(ctx=interaction, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler)
    #     elif button.custom_id == "play_liked":
    #         pass
        
    @discord.ui.button(label="play all", custom_id="play_all", style=discord.ButtonStyle.green, emoji="🎲")
    async def play_all(self, interaction: discord.Interaction, button: discord.Button):
        try:
            try: await interaction.response.defer()
            except: pass
            await command_counter(user_id=str(interaction.user.id), bot=self.bot)
            if interaction.channel.name != "musique":
                embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
                return await interaction.channel.send(embed=embed)
            return await NewPlayAll(ctx=interaction, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler)
        except Exception as e:
            print(e)
            LogErrorInWebhook()

    @discord.ui.button(label="play liked", custom_id="play_liked", style=discord.ButtonStyle.green, emoji="⭐")
    async def play_liked(self, interaction: discord.Interaction, button: discord.Button):
        try: await interaction.response.defer()
        except: pass
        await command_counter(user_id=str(interaction.user.id), bot=self.bot)
        if interaction.channel.name != "musique":
            embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
            return await interaction.followup.send(embed=embed, ephemeral=True)
        user = interaction.user
        if interaction.user.voice is None: # Si le user nest dans aucun voocal
            embed = create_embed(title="Erreur", description="Vous n'êtes pas dans un channel vocal, **BUICON**.", suggestions=["queue","mlist","playlist-play"])
            return await interaction.followup.send(embed=embed)
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall("SELECT * FROM LikedSongs WHERE userId = ?", (str(user.id),))
        if len(data) == 0:
            embed = create_embed(title="Erreur", description=f"<@{user.id}> n'a pas de musiques likés.")
            return await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            music_list = []
            for d in data:
                id, userId, songName = d
                music_list.append(songName)
        random.shuffle(music_list)
        if not self.music_controler.is_vc(server_id=interaction.guild.id):
            await self.music_controler.join_vc(server_id=interaction.guild.id, channel=interaction.user.voice.channel)
        vc: discord.VoiceClient = self.music_controler.voice_clients[interaction.guild.id]
        for i in music_list:
            if i is not None:
                await self.music_controler.add_to_queue(interaction.guild.id, i)
            else:
                continue
        embed = create_embed(title="Musique", description=f"`{len(music_list)} musique` ajouté à la queue. (titres likés de {user.display_name})", suggestions=["queue","mlist","playlist-play"])
        await interaction.followup.send(embed=embed)
        if not vc.is_playing():
            await self.music_controler.play_music(server_id=interaction.guild.id)
        return

class MusicList_Handler():
    """
    Class pour controler la db musiques
    """
    def __init__(self, bot: Trapard):
        self.bot = bot

    async def getAllMusicPath(self):
        """
        return path of all music
        """
        out = []
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall("SELECT name FROM musiques")
            for d in data:
                out.append(d[0])
        return out

    async def get_musique_size(self):
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall('SELECT * FROM musiques')
        return len(data)

    async def remove_from_music_list(self, index: str):
        """
        Remove a song from mlist by index
        """
        name = await self.getName(index)
        
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM musiques WHERE name=? AND pos=?", (name, index))
                
                # Obtenez la taille de la liste une seule fois
                musique_size = await self.get_musique_size()
                
                for i in range(int(index) + 1, musique_size+10):
                    await conn.execute("UPDATE musiques SET pos = ? WHERE pos = ?", (i - 1, i))
        return

    async def get_all_music_name(self):
        """Return all music name in a dict where `key is music` name and `value is index`"""
        try:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT name, pos FROM musiques")
            if data:
                out = {}
                for item in data:
                    out[item[0]] = item[1]
                return out
        except Exception as e:
            LogErrorInWebhook()

    async def get_index_by_music_name(self, name: str):
        """
        return `index`, `user_downloader` of song by music_name
        """
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone("SELECT pos, downloader FROM musiques WHERE name = ?", (name,))
        if data:
            pos, downloader = data
            return str(pos), str(downloader)
        else: 
            return None, None

    async def find_song_by_name(self, name: str):

        """
        return list of music name, index by a part name
        """
        t = f"Les trouvailles pour la recherche `{name}`:\n\n"
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall("SELECT name, pos FROM musiques")
            found = []
            for item in data:
                if name.lower() in str(item[0]).lower():
                    t += f'`{item[0]}` **N°{item[1]}**\n'
                    found.append(item[0])
        if t == f"Les trouvailles pour la recherche `{name}`:\n\n":
            return f"Aucune musique portant ou contenant le texte {name} n'a été trouvée.😭", found
        return t, found

    async def Get_Total_Musics_Len(self):
        """
        return string of total time of the music list
        """
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall("SELECT duree FROM musiques")
        total_seconds = 0
        for item in data:
            total_seconds += int(item[0])
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        duration_str = f"{hours}h {minutes:02d}m {seconds:02d}s"
        return duration_str

    async def get_next_index(self):
        """
        return the next index that should be in mlist.
        """
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone("SELECT pos FROM musiques ORDER BY id DESC LIMIT 1")
        return int(data[0]) + 1

    async def add_music_to_list(self, new_music: list):
        """
        add music to db.
            ``new_music`` = ["music_name", 120, 267439803786723329, "artist"]
        """
        next_index = await self.get_next_index()
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO musiques (name, pos, duree, downloader, artiste) VALUES (?,?,?,?,?)", (new_music[0], next_index, new_music[1],new_music[2],new_music[3]))
        return

    async def getName(self, index: str):
        """return song name by index"""
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone("SELECT name FROM musiques WHERE pos = ?", int(index))
        if data:
            return data[0]
        return "Unknown index."

    async def get_song_duration_by_index(self, index:str):
        """return int(song) duration by index"""
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone("SELECT duree FROM musiques WHERE pos = ?", int(index))
        if data:
            return int(data[0])
        else:
            return "Unknown index."

    async def get_unique_downloader(self):
        """
        return list of unique userid music downloader.
        """
        async with self.bot.pool.acquire() as conn:
            downloaders = await conn.fetchall("SELECT DISTINCT downloader FROM musiques")
        out = []
        for downloader in downloaders:
            out.append(downloader[0])
        return set(out)

    async def get_all_index_in_playlists(self):
        """
            return list of index that are in a created playlist.
        """
        with open(PLAYLIST_LIST, "r", encoding="utf-8") as f:
            lines = f.readlines()
            data = []
            for line in lines:
                _, musiques = line.split("=", maxsplit=1)
                musiques_list = musiques.split(',')
                for musique in musiques_list:
                    index, _ = await self.get_index_by_music_name(musique.strip())
                    data.append(index)
        return data

    async def getMList(self, userid:int=None):
        """return int(song) duration by index"""

        async with self.bot.pool.acquire() as conn:
            out = await conn.fetchall("SELECT name, duree, downloader, artiste, pos FROM musiques")

        self.data = {}
        for musique in out:
            name, duree, downloader, artiste, pos = musique
            self.data[str(pos)] = [name, duree, downloader, artiste]
        output = []
        page_limit = 25  # Nombre d'éléments par page
        total_pages = (len(self.data) + page_limit - 1) // page_limit  # Calcul du nombre total de pages
        
        uniques_id = [1065781211219370104]

        if userid:
            self.data2 =  []
            taille = 0

        for i, (key, val) in enumerate(self.data.items()):
            if userid:
                if val[2] == userid:
                    val.append(key)
                    self.data2.append(val)
                    if int(val[2]) > 1000000000:
                        uniques_id.append(val[2])
                    taille+=1
            else:
                if int(val[2]) > 1000000000:
                    uniques_id.append(val[2])
        uniques_id = set(uniques_id)

        dicto = {}
        for unique_id in uniques_id:
            _ = await self.bot.fetch_user(int(unique_id))
            dicto[unique_id] = _.display_name
        if userid is None:
            for page in range(total_pages):
                embed = discord.Embed(title=f"Liste des musiques")
                embed.add_field(name="", value=f"- téléchargées par Tous ({await self.Get_Total_Musics_Len()}) - Page {page+1}/{total_pages}", inline=False)
                field = "```" + printFormat("N°", 4) + "|" + printFormat("Nom", 30) + "|" + printFormat("Artiste", 14) + "|" + printFormat("Durée", 6) + "|" + printFormat("Téléchargé par", 12) +"\n\n"
                field += '-' * 4 +  "|" + '-' * 33 + '|' + '-' * 6 + '|' + '-' * 11 + "\n"

                start_index = page * page_limit
                end_index = min(start_index + page_limit, len(self.data))
                for i in range(start_index, end_index):
                    music_info = self.data[str(i + 1)]
                    if len(music_info) == 4:
                        artist = music_info[3]
                    else:
                        artist = "Inconnu"
                    if artist in music_info[0]:
                        music_info[0] = music_info[0].replace(artist, "")
                    time2 = convert_to_minutes_seconds(str(music_info[1]))
                    if str(time2).strip() == "0m 0":
                        time2 = "N/A"
                    try:
                        username = self.bot.unique_downloader_display_names[int(music_info[2])]
                    except:
                        username = "Unknown"
                    if username == "FeskooDesLacs":
                        username = "Feskoo"
                    line = f"{printFormat(str(i + 1), 4)}|{printFormat(music_info[0], 30)}|{printFormat(str(artist), 14)}|{printFormat(time2, 5)}|{printFormat(str(username), 12)}\n"

                    if len(field) + len(line) > 1000:
                        field += "```"
                        embed.add_field(name="", value=field, inline=False)
                        field = "```"
                    field += line
                if field.strip() != "```":
                    field += "```"
                    embed.add_field(name="", value=field, inline=False)

                output.append(embed)
        else:
            page_limit = 20
            if taille == 0:
                em = "<:skullcry:1124350948958031956>"
                return create_embed(title="Liste des musiques", description=f"- L'utilisateur <@!{userid}> ne semble avoir téléchargé aucune musique {em}")
            total_pages = (len(self.data2) + page_limit - 1) // page_limit
            for page in range(total_pages):
                embed = discord.Embed(title=f"Liste des musiques")
                embed.add_field(name="", value=f"- téléchargées par <@!{userid}> ({taille} musiques) - Page {page+1}/{total_pages}", inline=False)
                field = "```" + printFormat("N°", 4) + "|" + printFormat("Nom", 30) + "|" + printFormat("Artiste", 14) + "|" + printFormat("Durée", 6) + "|" + printFormat("Téléchargé par", 12) +"\n\n"
                field += '-' * 4 +  "|" + '-' * 33 + '|' + '-' * 6 + '|' + '-' * 11 + "\n"

                start_index = page * page_limit
                end_index = min(start_index + page_limit, len(self.data2))
                for i in range(start_index, end_index):
                    music_info = self.data2[i]
                    if len(music_info) == 4:
                        artist = rename(music_info[3])
                    else:
                        artist = "Inconnu"
                    if artist in music_info[0]:
                        music_info[0] = music_info[0].replace(artist, "")
                    time2 = convert_to_minutes_seconds(str(music_info[1]))
                    if str(time2).strip() == "0m 0":
                        time2 = "N/A"
                    username = self.bot.unique_downloader_display_names[int(music_info[2])]
                    if username == "FeskooDesLacs":
                        username = "Feskoo"
                    line = f"{printFormat(str(music_info[-1]), 4)}|{printFormat(music_info[0], 30)}|{printFormat(str(artist), 14)}|{printFormat(time2, 5)}|{printFormat(str(username), 12)}\n"
                    if len(field) + len(line) > 1000:
                        field += "```"
                        embed.add_field(name="", value=field, inline=False)
                        field = "```"
                    field += line
                if field.strip() != "```":
                    field += "```"
                    embed.add_field(name="", value=field, inline=False)

                output.append(embed)
        return output

class SuggestionPlay(discord.ui.View):
    try:
        def __init__(self, server_id, ctx: commands.Context, bot:Trapard,music_list_handler: MusicList_Handler, music_controler, index_list: list=None, index: int=None):
            super().__init__(timeout=None)
            self.bot = bot
            if index:
                self.index = index
            elif index_list:
                self.index_list = index_list
            self.serverid = server_id
            self.ctx = ctx
            self.music_list_handler = music_list_handler
            self.music_controler = music_controler

            if index:
                self.play_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play {self.index}', custom_id=f"play_{index}", disabled=False)
                if int(self.serverid) in self.bot.music_queues: 
                    self.playnext_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play-next {self.index}', custom_id=f"playnext_{index}", disabled=False)
                else:
                    self.playnext_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play-next {self.index}', custom_id=f"playnext_{index}", disabled=True)
                self.add_item(self.play_btn)
                self.play_btn.callback = lambda interaction=self.ctx, button=self.play_btn: self.on_button_click(interaction, button, index=self.index)
                self.add_item(self.playnext_btn)
                self.playnext_btn.callback = lambda interaction=self.ctx, button=self.playnext_btn: self.on_button_click(interaction, button, index=self.index)
            
            elif index_list:
                for i, index in enumerate(index_list):
                    self.play_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play {index}', custom_id=f"play_{index}", disabled=False)
                    if int(self.serverid) in self.bot.music_queues:
                        self.playnext_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play-next {index}', custom_id=f"playnext_{index}", disabled=False)
                    else:
                        self.playnext_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play-next {index}', custom_id=f"playnext_{index}", disabled=True)
                    self.add_item(self.play_btn)
                    self.play_btn.callback = lambda interaction=self.ctx, button=self.play_btn: self.on_button_click(interaction, button, index=index)
                    self.add_item(self.playnext_btn)
                    self.playnext_btn.callback = lambda interaction=self.ctx, button=self.playnext_btn: self.on_button_click(interaction, button, index=index)            

        async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button, index):
            try:await interaction.response.defer()
            except:pass
            cmd, idx = button.custom_id.split("_")
            name = await self.music_list_handler.getName(index=idx)
            if cmd == "play":
                if interaction.guild.voice_client:
                    await self.music_controler.add_to_queue(interaction.guild.id, name)
                else:
                    user_vocal = interaction.user.voice.channel
                    vc = await user_vocal.connect()
                    self.music_controler.voice_clients[interaction.guild.id] = vc
                    await self.music_controler.add_to_queue(interaction.guild.id, name)
                    await self.music_controler.play_music(interaction.guild.id)
                embed = create_embed(title="Musique", description=f"`{name}` ajouté à la queue.", suggestions=["queue","mlist","playlist-play"])
                return await interaction.followup.send(embed=embed)
            elif cmd == "playnext":
                if interaction.guild.voice_client:
                    await self.music_controler.add_next_to_queue(interaction.guild.id, name)
                    embed = create_embed(title="Musique", description=f"`{name}` ajouté à la queue.", suggestions=["queue","mlist","playlist-play"])
                else:
                    embed = create_embed(title="Musique", description=f"Il semble que le bot ne soit pas connecté.", suggestions=["queue","mlist","playlist-play"])
                return await interaction.followup.send(embed=embed)
    except Exception as e:
        LogErrorInWebhook()

async def download_from_url(url, user, channel_id, userid, serverid, cmd, music_list_handler: MusicList_Handler,music_controler,music_session, bot: Trapard, ctx: commands.Context=None):
    """Download youtube video from url."""
    def check_file(name:str):
        """Check if file exists and is not empty"""
        path = MUSICS_FOLDER
        if name in os.listdir(path):
            # Check file size
            size = os.path.getsize(path + name)
            if size > 0:
                return True
            else:
                return False
        else:
            return False
    
    try:
        video_url = url
        video = YouTube(video_url)

        music_artist = video.author
        duration = video.length
        file_name = rename(video.title)

        formatMention = "<@" + str(userid) + ">"
        if file_name in await music_list_handler.get_all_music_name():
            name = file_name.replace(".mp3", "")
            index, dler = await music_list_handler.get_index_by_music_name(name=name)
            embed = create_embed(title="Erreur", description=f"- {formatMention}, il semble que la musique `{name}` ({convert_str_to_emojis(f'n {index}')}), ait déjà été téléchargée.\n\n- Le téléchargement a été annulé.")
            if ctx is not None:
                await ctx.send(embed=embed)
            else:
                await chann.send(embed=embed)
            return False

        url = video_url
        if duration > 1500:
            embed = create_embed(title="Erreur", description=f"- {formatMention}, la musique fait plus de **25 minutes**.\n\n- Le téléchargement a été annulé.")
            if ctx is not None:
                await ctx.send(embed=embed)
            else:
                await chann.send(embed=embed)
            return False
        

        async def download_thread(url, channel_id):
            # Code for downloading the video


            video_url = url
            
            video = YouTube(video_url)

            videoName = rename(video.title)
            stream = video.streams.filter(only_audio=True).first()

            stream.download(output_path=MUSICS_FOLDER, filename=f'{videoName}')

        def run_thread(coro):
            asyncio.run(coro)

        # Start the download in a separate thread
        thread = threading.Thread(target=run_thread, args=(download_thread(url, channel_id),))
        thread.start()

        # Wait for the thread to finish
        thread.join()
        index = await music_list_handler.get_next_index()
        # Check if there was an exception in the thread
        if thread.is_alive():
            # The thread is still running, which means there was an exception
            # Handle the exception here
            return False
        else:
            if check_file(file_name) is False:
                embed = create_embed(title="Erreur", description=f"- {formatMention}, il semble que la musique `{video.title}` n'ait pas été téléchargée.\n\n- La musique est peut-être soumise à une restriction d'âge ou n'existe pas.\n\n- Le téléchargement a été annulé.")
                if ctx is not None:
                    await ctx.send(embed=embed)
                else:
                    await chann.send(embed=embed)
                return False
            view = SuggestionPlay(server_id=serverid, ctx=ctx, bot=bot, index=index, music_controler=music_controler, music_list_handler=music_list_handler)
            message = formatMention + f" La musique `{video.title}` **N°{index}** est téléchargée !"
            chann = bot.get_channel(int(channel_id))
            embed = create_embed(title="Musique", description=message)
            if cmd != "DL":
                if ctx is not None:
                    await ctx.send(embed=embed, view=view)
                else:
                    await chann.send(embed=embed, view=view)
            else:
                if ctx is not None:
                    await ctx.send(embed=embed, view=view)
                else:
                    await chann.send(embed=embed, view=view)
        if music_artist is None or music_artist == "Inconnu":
            music_artist = get_artist_from_title(title=video.title).artists[0]
        file_name = str(file_name).split(".")[0]
        await music_list_handler.add_music_to_list([str(file_name), int(duration), int(userid), str(music_artist)])
        return True
    except Exception as e:
        LogErrorInWebhook()

class QueueBtn(discord.ui.View): # Queue List Buttons
    try:
        def __init__(self, messages: list, page_count, ctx: discord.Interaction):
            super().__init__(timeout=None)
            self.current_page = 0
            self.ctx = ctx
            self.page_count = page_count
            self.messages = messages
            self.first_run = True

            self.boutton_last = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="▶️", custom_id="next")
            self.boutton_first = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="last")
            if self.current_page == 0:
                self.boutton_previous = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="◀️", disabled=True, custom_id="prev")
                self.boutton_suivant = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏮️", disabled=True, custom_id="first")
            else:
                self.boutton_suivant = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏮️", disabled=False, custom_id="first")
                self.boutton_previous = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="◀️", disabled=False, custom_id="prev")


            self.add_item(self.boutton_suivant)
            self.add_item(self.boutton_previous)
            self.add_item(self.boutton_last)
            self.add_item(self.boutton_first)


            self.boutton_suivant.callback = lambda interaction=self.ctx, button=self.boutton_suivant: self.go_to_first_page(interaction, button)
            self.boutton_previous.callback = lambda interaction=self.ctx, button=self.boutton_previous: self.go_to_previous_page(interaction, button)
            self.boutton_last.callback = lambda interaction=self.ctx, button=self.boutton_last: self.go_to_next_page(interaction, button)
            self.boutton_first.callback = lambda interaction=self.ctx, button=self.boutton_first: self.go_to_last_page(interaction, button)



        async def show_current_page(self, button: discord.Interaction, direction: int):
            self.current_page += direction
            if self.current_page < 0:
                self.current_page = 0
            elif self.current_page >= len(self.messages):
                self.current_page = len(self.messages) - 1
            elif self.current_page == len(self.messages):
                self.current_page = len(self.messages)

            first = discord.utils.get(self.children, custom_id="first")
            prev = discord.utils.get(self.children, custom_id="prev")
            next = discord.utils.get(self.children, custom_id="next")
            last = discord.utils.get(self.children, custom_id="last")

            if self.current_page < 2:
                first.disabled = True
            else: 
                first.disabled = False
            if self.current_page < 1:
                prev.disabled = True
            else: 
                prev.disabled = False
            if self.current_page >= len(self.messages) - 1:
                next.disabled = True
            else: 
                next.disabled = False
            if self.current_page >= len(self.messages) - 2:
                last.disabled = True
            else: 
                last.disabled = False

            await button.message.edit(embed=self.messages[self.current_page], view=self)
            try:
                await button.response.defer()
            except:
                pass
            
        async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.show_current_page(interaction, -self.current_page)

        async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.show_current_page(interaction, -1)

        async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.current_page < self.page_count - 1:
                await self.show_current_page(interaction, 1)
            else:
                await self.show_current_page(interaction, 0)
        async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.show_current_page(interaction, len(self.messages) - 1 - self.current_page)

    except Exception as e:
        LogErrorInWebhook()

class MusicController:
    try:
        def __init__(self, bot: Trapard, music_list_handler: MusicList_Handler,unique_downloader, music_session):
            self.bot = bot
            self.music_list_handler = music_list_handler
            self.voice_clients = {}
            self.current_song_pbar = None
            self.unique_downloader = unique_downloader
            self.music_session = music_session
            self.current_song = {}
            self.current_song_status = {}
            self.curent_timecode = 0

            self.hypno_emoji = "<a:hypnotise:1126218362649858078>"
            self.rave_emoji = "<a:rave:1124099238163394632>"
            self.cool_emoji = "<a:cooldoge:1124120143648260126>"
            self.jam_emoji = "<a:pepeJam:1124371017402429460>"
            self.pourcent_em = "<:percent:1125746991247409202>"



        async def play_music(self, server_id: int):
            try:
                time_old, reducer = 0, 0
                messages = await getMusicQueue(server_id=server_id, music_list_handler=self.music_list_handler, bot=self.bot)
                view = PlayAllView(messages, server_id, ctx=discord.Interaction, music_controler=self,music_session = self.music_session, bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.unique_downloader)
                song_infos = await self._setup_current_song_info(server_id=server_id)
                
                if self.is_vc(server_id):
                    vc: discord.VoiceClient = song_infos['vc']
                else:
                    guild = self.bot.get_guild(server_id)
                    zic_chann = discord.utils.get(guild.channels, name="musique", type=discord.ChannelType.text)
                    await self.join_vc(server_id, zic_chann)
                    vc = self.voice_clients[server_id]
                try:
                    vc.play(song_infos['source'])
                except discord.errors.ClientException as e:
                    error_message = str(e)
                    if error_message == "Not connected to voice.":
                        guild = self.bot.get_guild(server_id)
                        zic_chann = discord.utils.get(guild.channels, name="musique", type=discord.ChannelType.text)
                        await self.join_vc(server_id, zic_chann)
                        vc = self.voice_clients[server_id]
                        vc.play(song_infos['source'])
                vc.source = discord.PCMVolumeTransformer(vc.source)
                start_time = perf_counter()
                response = await self._display_current_song_info(server_id=server_id, view=view)
                if isinstance(response, tuple):
                    track, dler, index, field, track_duration, zic_chann = response
                else: return "Erreur..."
                
                # Song start playing
                while vc.is_playing():
                    track_duration = await self._check_soundboard_status(server_id=server_id, track=track, dler=dler, index=index, reducer=reducer, view=view, field=field, track_duration=track_duration)
                    time_old = await self._update_playing_status(server_id=server_id, track=track, dler=dler, index=index, start_time=start_time, messages=messages,reducer=reducer,track_duration=track_duration,zic_chann=zic_chann,vc=vc,time_old=time_old, field=field)

                # Song is ended
                await self._end_playing_song(server_id=server_id, track_duration=track_duration, track=track,index=index,dler=dler,vc=vc)
            except Exception as e:
                print(e)
                LogErrorInWebhook()

        async def _setup_current_song_info(self, server_id):
            songs_info = {"error": False}
            if server_id not in self.voice_clients:
                songs_info['error'] = True
                # return "Je ne suis pas connecté à un canal vocal pour ce serveur."
            vc: discord.VoiceClient = self.voice_clients[server_id]
            songs_info['vc'] = self.voice_clients[server_id]
            if len(self.bot.music_queues[server_id]) == 0:
                songs_info['error'] = True
                # return "Il n'y a pas de musique dans la file d'attente."
            songs_info['name'] = self.bot.music_queues[server_id].pop(0)
            if songs_info['name'] is not False:
                songs_info['music_path'] = MUSICS_FOLDER + songs_info['name'] + ".mp3"
            else:
                songs_info['error'] = True
                # return "La musique n'existe pas."
            
            if server_id not in self.bot.current_track:
                self.bot.current_track[server_id] = songs_info['name']
            else:
                self.bot.current_track[server_id] = songs_info['name']
            if server_id not in self.music_session:
                self.music_session[server_id] = {'music_played': 0, 'time': 0, 'paused': {'status': False, 'sound_time': 0}}

            self.current_song[server_id] = songs_info['music_path']

            songs_info['source'] = discord.FFmpegPCMAudio(songs_info['music_path'])
            return songs_info

        async def _display_current_song_info(self, server_id, view):
            guild = self.bot.get_guild(server_id)
            zic_chann = discord.utils.get(guild.channels, name="musique", type=discord.ChannelType.text)
            if zic_chann is None:
                return None
            track = self.bot.current_track[server_id]
            index = await self.music_list_handler.get_index_by_music_name(track)
            if index[0] is None:
                return await self._end_playing_song(server_id=server_id, track_duration=None, track=None,index=None,dler=None,vc=None)
            try:
                dler = self.bot.unique_downloader_display_names[(int(index[1]))]
            except:
                dler = "Inconnu"
                try:
                    user = self.bot.get_user(int(index[1]))
                    dler = user.display_name
                except:
                    dler = "Inconnu2"
            track_duration = await self.music_list_handler.get_song_duration_by_index(str(index[0]))
            self.current_song_status[server_id] = {'c_time': 0, 't_time': int(track_duration)}
            pbar = create_progress_bar(self.curent_timecode, int(track_duration), bar_length=30)
            dur = convert_to_minutes_seconds(str(self.curent_timecode)) + " /" + convert_to_minutes_seconds(str(track_duration))
            
            if server_id in self.bot.music_queues and len(self.bot.music_queues[server_id]) > 0:
                queue_len = f'( {len(self.bot.music_queues[server_id])} musiques en queue )'
                next_musics = []

            else:
                queue_len = "( Aucune musique en queue )"
            
            await asyncio.to_thread(draw_music, track, dler, int(0), str(convert_to_minutes_seconds(str(self.curent_timecode))), convert_to_minutes_seconds(track_duration), [], queue_len, int(server_id))
            file = discord.File(f"/home/debian/trapard/files/{server_id}_music_player.png", filename=f"Music.png")
            embed = discord.Embed(title=f"Musique", description=f" ", color=0x2F3136)
            embed.set_image(url=f"attachment://Music.png")            
            self.current_song_pbar = await zic_chann.send(embed=embed, view=view, file=file)
            self.last_message = self.current_song_pbar
            next_musics = None
            field = ""
            if server_id in self.bot.music_queues and len(self.bot.music_queues[server_id]) > 0:
                next_musics = self.bot.music_queues[server_id]
                field += f"\n\n**3 prochaines musiques** : ({len(self.bot.music_queues[server_id])} musiques en queue)\n"
                for i, next_music in enumerate(next_musics):
                    if i == 0:
                        c = 'green'
                    elif i == 1:
                        c = 'pink'
                    else:
                        c = 'white'
                    field += f'{convert_txt_to_colored(text=next_music, color=c, background="dark")}'
                    if i == 2: break
            else:
                field += "\n\nAucune musique à venir. </play:1103411566558322753>"
            return track, dler, index, field, track_duration, zic_chann

        async def _check_soundboard_status(self, server_id, track, dler, index, view, reducer,field, track_duration):
            while self.music_session[server_id]['paused']['status'] == True:
                txt = f"Lecture en pause par la SoundBoard pour {self.music_session[server_id]['paused']['sound_time']} secondes!"
                embed = create_embed(title=f"Musique actuelle 🎜 {self.rave_emoji}", description=f"**{track}** (`🇳 {convert_int_to_emojis(int(index[0]))}`)\n\nTéléchargé par **{dler}** {self.hypno_emoji}\n\n{convert_txt_to_colored(text=txt, color='red', background='dark')}{field}")    
                await self.current_song_pbar.edit(embed=embed, view=view)
                self.music_session[server_id]['paused']['sound_time'] -= 1
                await asyncio.sleep(1)
                reducer += 1
                track_duration -= 1
                if reducer >= 30:
                    self.music_session[server_id]['paused']['status'] == False
                    break
            return track_duration

        async def _update_playing_status(self, server_id, track, dler, index, start_time,messages,reducer,track_duration,zic_chann: discord.TextChannel,vc:discord.VoiceClient,time_old, field):
            view = PlayAllView(messages, server_id, ctx=discord.Interaction, music_controler=self,music_session = self.music_session, bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.unique_downloader)
            time_old += 1
            current_time = perf_counter() - start_time
            if reducer > 0:
                current_time -= reducer
            self.current_song_status[server_id]['c_time'] = int(current_time)
            pourcent =  str(int(current_time * 100 / int(track_duration)))
            if int(pourcent) > 100:
                return await self._end_playing_song(server_id=server_id, track_duration=track_duration, track=track,index=index,dler=dler,vc=vc)
            self.curent_timecode = int(current_time)
            if self.curent_timecode > int(track_duration):
                self.curent_timecode = int(track_duration)
            pbar = create_progress_bar(self.curent_timecode, int(track_duration), bar_length=30)
            dur = convert_to_minutes_seconds(str(self.curent_timecode)) + " /" + convert_to_minutes_seconds(track_duration)
            if time_old % 4 == 0:
                try:
                    activity = discord.CustomActivity(
                        name = "Custom Status", # leave this like this
                        state = f"{pourcent}% - {track}", # edit this
                    )
                    await self.bot.change_presence(activity=activity)
                except:
                    pass
            field = ""
            next_musics = []
            queue_len = 0
            if server_id in self.bot.music_queues and len(self.bot.music_queues[server_id]) > 0:
                queue_len = f'( {len(self.bot.music_queues[server_id])} musiques en queue )'
                field += f"\n\n**3 prochaines musiques** : ({len(self.bot.music_queues[server_id])} musiques en queue)\n"
                for i, next_music in enumerate(self.bot.music_queues[server_id]):
                    if i == 0:
                        c = 'green'
                    elif i == 1:
                        c = 'pink'
                    else:
                        c = 'white'
                    field += f'{convert_txt_to_colored(text=next_music, color=c, background="dark")}'
                    next_musics.append(next_music)
                    if i == 3: break
            else:
                next_musics.append("Aucune musique à venir.")
                queue_len = "Aucune musique en queue."
                field += "\n\n**Aucune musique à venir**. </play:1103411566558322753>"
            self.last_message = await get_latest_message_from_channel(zic_chann)
            latency = vc.latency
            if latency == float('inf'):
                latency = "N/A"
            else:
                latency = f"{int(round(latency*1000, 2))}ms"
            # if time_old % 2 == 0:
            #     embed = create_embed(title=f"Musique actuelle 🎝 {self.rave_emoji}", description=f"**{track}** (`🇳 {convert_int_to_emojis(int(index[0]))}`)\n\nTéléchargé par **{dler}** {self.hypno_emoji}\n\n- `{pbar}`\n- {self.jam_emoji}              `{convert_str_to_emojis(dur)}`       {convert_str_to_emojis(str(pourcent))} {self.pourcent_em}          {self.cool_emoji}{field}\n\n                _Ping: {latency}_")
            # else:
            #     embed = create_embed(title=f"Musique actuelle 🎜 {self.rave_emoji}", description=f"**{track}** (`🇳 {convert_int_to_emojis(int(index[0]))}`)\n\nTéléchargé par **{dler}** {self.hypno_emoji}\n\n- `{pbar}`\n- {self.cool_emoji}              `{convert_str_to_emojis(dur)}`       {convert_str_to_emojis(str(pourcent))} {self.pourcent_em}          {self.jam_emoji}{field}\n\n                _Ping: {latency}_")    

            await asyncio.to_thread(draw_music, track, dler, int(pourcent), str(convert_to_minutes_seconds(str(self.curent_timecode))), convert_to_minutes_seconds(track_duration), next_musics, queue_len, int(server_id))
            file = discord.File(f"/home/debian/trapard/files/{server_id}_music_player.png", filename=f"Music.png")
            embed = discord.Embed(title=f"Musique", description=f" ", color=0x2F3136)
            embed.set_image(url=f"attachment://Music.png")
            if self.current_song_pbar.id !=  self.last_message.id:
                if time_old % 10 == 0:
                    await self.current_song_pbar.delete()
                    self.current_song_pbar = await zic_chann.send(embed=embed, view=view,file=file)
                    self.last_message = self.current_song_pbar
                else:
                    await self.current_song_pbar.edit(embed=embed, view=view, attachments=[file])
            else:
                await self.current_song_pbar.edit(embed=embed, view=view, attachments=[file])
            await sleep(3)
            return time_old

        async def _end_playing_song(self,server_id,track_duration,track,index,dler,vc:discord.VoiceClient):
            try:
                if (track_duration is None) and (track is None) and (index is None) and (dler is None) and (vc is None):
                    return await self.play_next(server_id)
                pbar = create_progress_bar(int(track_duration), int(track_duration), bar_length=30)
                dur = convert_to_minutes_seconds(track_duration) + " /" + convert_to_minutes_seconds(track_duration)
                
                await asyncio.to_thread(draw_music, track, dler, 100, convert_to_minutes_seconds(track_duration), convert_to_minutes_seconds(track_duration), [], "", int(server_id))
                file = discord.File(f"/home/debian/trapard/files/{server_id}_music_player.png", filename=f"Music.png")
                embed = discord.Embed(title=f"Musique", description=f" ", color=0x2F3136)
                embed.set_image(url=f"attachment://Music.png")
                
                await self.current_song_pbar.edit(embed=embed, view=None, attachments=[file])
                self.bot.last_music[server_id] = track
                if self.curent_timecode > 8:
                    await self.save_song_stats(self.curent_timecode, 1)
                    await IncrementMusicPlayed(TrackName=track, pool=self.bot.pool)
                # Add stats to server session
                if server_id in self.music_session:
                    self.music_session[server_id]['music_played'] += 1
                    self.music_session[server_id]['time'] += self.curent_timecode

                # Check if there is still user in vc:
                activity = discord.CustomActivity(
                    name = "Custom Status", # leave this like this
                    state = f"Bonne nuit", # edit this
                )
                if await check_voice_state(vc=vc) is True:
                    del self.bot.music_queues[server_id]
                    del self.voice_clients[server_id]
                    await vc.disconnect()
                    chann = self.bot.get_channel(server_id)
                    await self.bot.change_presence(activity=activity)
                    txt = f"Tout le monde est parti... La file d'attente a été réinitialisée.\n\nCette session, j'ai joué **{self.music_session[server_id]['music_played']} musiques**, pour un total de **{convert_to_minutes_seconds(self.music_session[server_id]['time'])}**."
                    embed = create_embed(title="Fin de session", description=txt)
                    try: del self.music_session[server_id]
                    except: pass
                    guild = self.bot.get_guild(server_id)
                    if guild:
                        zic_chann = discord.utils.get(guild.channels, name="musique", type=discord.ChannelType.text)
                        if zic_chann:
                            view = EndSessionBtn(bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self, timeout=None)
                            return await zic_chann.send(embed=embed, view=view)
                    return
                if (server_id in self.bot.music_queues):
                    if len(self.bot.music_queues[server_id]) == 0:
                        # Clear the music queue and disconnect from the voice channel if there are no more songs in the queue
                        del self.bot.music_queues[server_id]
                        await self.bot.change_presence(activity=activity)
                        try: del self.voice_clients[server_id]
                        except: pass
                        try: del self.music_session[server_id]
                        except: pass
                        await vc.disconnect()
                    else:
                        # Play the next song in the queue
                        await self.play_next(server_id)
                else:
                    await vc.disconnect()
                    await self.bot.change_presence(activity=activity)
                    try: del self.voice_clients[server_id]
                    except: pass
                    try: del self.music_session[server_id]
                    except: pass
            except Exception as e:
                LogErrorInWebhook()

        def get_current_playing_song(self, server_id):
            return self.current_song[server_id], self.current_song_status[server_id]['c_time']

        async def play_next(self, server_id):
            if server_id not in self.voice_clients:
                # Return an error message or raise an exception if the bot is not connected to a voice channel for this server
                return "Je ne suis pas connecté à un canal vocal pour ce serveur."
            await self.play_music(server_id)

        async def add_to_queue(self, server_id, name):
            if server_id not in self.bot.music_queues:
                self.bot.music_queues[server_id] = []
            if name == "Queue":
                return
            self.bot.music_queues[server_id].append(name)
            return True

        async def add_next_to_queue(self, server_id, name):
            if server_id not in self.bot.music_queues:
                self.bot.music_queues[server_id] = []
            if name == "Queue":
                return
            self.bot.music_queues[server_id].insert(0, name)
            return True
    
        def is_vc(self, server_id):
            """Check if bot is already in a VoiceChannel."""
            return server_id in self.voice_clients

        async def join_vc(self, server_id: int, channel: discord.VoiceChannel):
            """Join vc."""
            if not self.is_vc(server_id):
                vc = await channel.connect()
                self.voice_clients[server_id] = vc
        
        async def save_song_stats(self, time: int, number: int):
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("UPDATE songs_stats SET time = time + ?, number = number + ? WHERE id = 1", (time, number,))
            return

        async def get_song_stats(self):
            """Return `tuple` time, number"""
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchone("SELECT time, number FROM songs_stats WHERE id = 1")
            if data:
                return int(data[0]), int(data[1])
            return "Error"
    
    except Exception as e:
        LogErrorInWebhook()

class QuestionnaireMusicPlay(Modal, title='Jouer une/des musiques'):
    """
    Inputs:
    ---------

    """
    def __init__(self, *, bot: Trapard, music_list_handler: MusicList_Handler, music_controler: MusicController, custom_id: str) -> None:
        self.bot = bot
        self.music_list_handler = music_list_handler
        self.music_controler = music_controler
        self.custom_id = custom_id

    feedback = TextInput(
        label='La ou les musiques à jouer',
        style=discord.TextStyle.short,
        placeholder='Exemple: 1,2,5,3,125 ou 5',
        required=True,
        max_length=300,
    )
    async def on_submit(self, interaction: commands.Context):
        self.user_input = self.feedback.value
        em_error = create_embed(title="Erreur", description="- Le numéro que tu as donné n'est pas bon !!\n\n- Voila comment utiliser `/play`\n\n- `/play 5`\n\n- `/play 12,3,5,25,25,3,1`", suggestions=["queue","mlist","playlist-play"])
        messages = await getMusicQueue(server_id=interaction.guild.id, music_list_handler=self.music_list_handler, bot=self.bot)
        view = PlayAllView(messages, interaction.guild.id, interaction, music_controler=self.music_controler, bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.music_controler.unique_downloader)
        if is_comma_separated(self.user_input) is True:
            wantedList, erreur = parse_user_indexs(self.user_input)
            if erreur is not None:
                em_error = create_embed(title="Erreur", description=f"- Le numéro que tu as donné n'est pas bon.\n{erreur}", suggestions=["play","play-next","mlist"])
                return await interaction.send(embed=em_error)
            out = []
            for i in wantedList:
                out.append(await self.music_list_handler.getName(str(i)))
            music_name = "Queue"
        else:
            try:
                music_name = await self.music_list_handler.getName(str(self.user_input))
            except ValueError:
                return await interaction.send(embed=em_error)
            if music_name == "Song not found.":
                return await interaction.send(embed=em_error)

        if interaction.guild.id in self.music_controler.voice_clients: # Trapard is playing 
            if is_comma_separated(self.user_input) is True: # Add multiple songs
                if len(out) != 0:
                    if self.custom_id == "play-next":
                        out = list(reversed(out))
                    for i in out:
                        if self.custom_id == "play-next":
                            await self.music_controler.add_next_to_queue(interaction.guild.id, i)
                        else:
                            await self.music_controler.add_to_queue(interaction.guild.id, i)
                    embed = create_embed(title="Musique", description=f"`{out}` ajouté à la queue.", suggestions=["queue","mlist","playlist-play"])
                    return await interaction.send(embed=embed, view=view)
            if self.custom_id == "play-next":
                await self.music_controler.add_next_to_queue(interaction.guild.id, music_name) # Add the only song
            else:
                await self.music_controler.add_to_queue(interaction.guild.id, music_name) # Add the only song
            if self.custom_id == "play":
                if len(self.bot.music_queues[interaction.guild.id]) < 1:
                    await self.music_controler.play_music(server_id=interaction.guild.id)
            embed = create_embed(title="Musique", description=f"`{music_name}` ajouté à la queue.", suggestions=["queue","mlist","playlist-play"])
            return await interaction.send(embed=embed, view=view)

        else:
            user_vocal = interaction.author.voice.channel
            vc = await user_vocal.connect()
            self.music_controler.voice_clients[interaction.guild.id] = vc
            if is_comma_separated(self.user_input) is True:
                if out is not None:
                    cleanList = "`"
                    for i in out:
                        await self.music_controler.add_to_queue(interaction.guild.id, i)
                        cleanList += i + " | "
                    cleanList += "`"
                    embed = create_embed(title="Musique", description=f"Ajouté à la file : {cleanList}", suggestions=["queue","mlist","playlist-play"])
                    await interaction.send(embed=embed, view=view)
                    return await self.music_controler.play_music(interaction.guild.id)
            await self.music_controler.add_to_queue(interaction.guild.id, music_name)
            embed = create_embed(title="Musique", description=f"Joue : {music_name}", suggestions=["queue","mlist","playlist-play"])
            await interaction.send(embed=embed, view=view)
            return await self.music_controler.play_music(interaction.guild.id)
        
    async def on_error(self, interaction: commands.Context, error: Exception) -> None:
        await interaction.send('Une erreur est survenue.', ephemeral=True)
        traceback.print_exception(type(error), error, error.__traceback__)

class PlayAllView(discord.ui.View): #Les trois buttons du play-all 
    try:
        def __init__(self, queue_messages, serverid, ctx: commands.Context, bot: Trapard, music_controler: MusicController, music_list_handler: MusicList_Handler,unique_downloader, music_session=None,row:int=None): 
            super().__init__(timeout=300)
            self.bot = bot
            self.music_controler = music_controler
            self.music_list_handler=music_list_handler
            self.queue_messages = queue_messages
            self.serverid = serverid
            self.ctx = ctx
            self.row = row
            self.unique_downloader = unique_downloader
            self.music_session = music_session

            # Previous song BTN
            if self.serverid in self.bot.last_music:
                self.prev_song_btn = discord.ui.Button(label="Musique d'avant", style=discord.ButtonStyle.primary, emoji="⬅", custom_id="prev", row=0)
            else:
                self.prev_song_btn = discord.ui.Button(label="Musique d'avant", style=discord.ButtonStyle.primary, emoji="⬅", custom_id="prev", row=0, disabled=True)
            self.add_item(self.prev_song_btn)
            self.prev_song_btn.callback = lambda interaction=self.ctx, button=self.prev_song_btn: self.on_button_click(interaction, button)

            self.sb_btn = discord.ui.Button(label="SoundBoard", style=discord.ButtonStyle.green, emoji="🔊", custom_id="sb", row=0)
            self.add_item(self.sb_btn)
            self.sb_btn.callback = lambda interaction=self.ctx, button=self.sb_btn: self.on_button_click(interaction, button)

            # Skip BTN
            if (self.serverid in self.bot.music_queues) and (len(self.bot.music_queues[self.serverid]) >= 1):
                self.skip_btn = discord.ui.Button(label="Musique d'après", style=discord.ButtonStyle.primary, emoji="➡", custom_id="skip", row=0)
            else:
                self.skip_btn = discord.ui.Button(label="Musique d'après", style=discord.ButtonStyle.primary, emoji="➡", custom_id="skip", row=0, disabled=True)
            self.add_item(self.skip_btn)
            self.skip_btn.callback = lambda interaction=self.ctx, button=self.skip_btn: self.on_button_click(interaction, button)

            self.afficher_queue_btn = discord.ui.Button(label="Afficher la queue", style=discord.ButtonStyle.primary, emoji="🎵", custom_id="afficher_queue", row=1)
            self.add_item(self.afficher_queue_btn)
            self.afficher_queue_btn.callback = lambda interaction=self.ctx, button=self.afficher_queue_btn: self.on_button_click(interaction, button)

            self.mlist_btn = discord.ui.Button(label="mlist", style=discord.ButtonStyle.primary, emoji="📊", custom_id="mlist", row=1)
            self.add_item(self.mlist_btn)
            self.mlist_btn.callback = lambda interaction=self.ctx, button=self.mlist_btn: self.on_button_click(interaction, button)

            self.like_btn = discord.ui.Button(label="Like", style=discord.ButtonStyle.primary, emoji="👍", custom_id="like", row=1)
            self.add_item(self.like_btn)
            self.like_btn.callback = lambda interaction=self.ctx, button=self.like_btn: self.on_button_click(interaction, button)

            self.disco_btn = discord.ui.Button(label="Disconnect", style=discord.ButtonStyle.danger, emoji="🔌", custom_id="disconnect", row=1)
            self.add_item(self.disco_btn)
            self.disco_btn.callback = lambda interaction=self.ctx, button=self.disco_btn: self.on_button_click(interaction, button)

        async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
            try: await interaction.response.defer()
            except: pass
            if button.custom_id == "afficher_queue":
                messages = await getMusicQueue(self.serverid, music_list_handler=self.music_list_handler, bot=self.bot)
                queue_view = QueueBtn(messages, len(messages), ctx=self.ctx)
                await interaction.channel.send(embed=messages[0], view=queue_view)
                messages = await getMusicQueue(interaction.guild_id, music_list_handler=self.music_list_handler, bot=self.bot)
                view = PlayAllView(messages, interaction.guild_id, interaction, music_controler=self.music_controler,music_session = self.music_session, bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.unique_downloader)
                await interaction.channel.send(view=view)
            elif button.custom_id == "mlist":
                await command_counter(user_id=str(interaction.user.id), bot=self.bot)
                options = [discord.SelectOption(label="Téléchargé par : Tous", value=f"tous", default=True, emoji="🦈")]
                for unique in self.bot.unique_downloader:
                    user = await self.bot.fetch_user(int(unique))
                    if user:
                        name = user.display_name
                        options.append(discord.SelectOption(label=name, value=f"{unique}", default=False))
                else:
                    drop = DropDownMlist(ctx=interaction, options=options, bot=self.bot, music_controler=self.music_controler)
                    mlist = await self.music_list_handler.getMList()
                    view = QueueBtn(mlist, len(mlist), interaction)
                    view.add_item(drop)
                    await interaction.followup.send(embed=mlist[0], view=view)
            elif button.custom_id == "skip":
                if self.music_controler.voice_clients[self.serverid] is None:
                    return await interaction.followup.send("Trapard est dans aucun vocal, tu es one head ou quoi ?", ephemeral=True)
                vc = self.music_controler.voice_clients[self.serverid]
                vc.stop()
                if self.serverid in self.bot.current_track:
                    mu = self.bot.current_track[self.serverid]
                else:
                    mu = ""
                embed = create_embed(title="Musique", description=f"La musique `{mu}` a été passé par <@{interaction.user.id}>.", suggestions=["mlist","play", "search"])
                await interaction.followup.send(embed=embed)
                return await storeSkippedSong(pool=self.bot.pool, songname=mu, userid=str(interaction.user.id))
            elif button.custom_id == "disconnect":
                del self.bot.music_queues[self.serverid]
                del self.music_controler.voice_clients[self.serverid]
                if interaction.guild:
                    vc = interaction.guild.voice_client
                    if vc:
                        await vc.disconnect()
                        self.bot.music_queues[interaction.guild.id] = []
                        txt = f"Le bot a été déconnecté et la file d'attente réinitialisée par {interaction.user.mention}.\n\nCette session, j'ai joué **{self.music_session[interaction.guild_id]['music_played']}** musiques, pour un total de **{convert_to_minutes_seconds(self.music_session[interaction.guild_id]['time'])}**."
                        embed = create_embed(title="Fin de session", description=txt)
                        try: del self.music_session[interaction.guild.id]
                        except: pass
                        view = EndSessionBtn(bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler, timeout=None)
                        await interaction.followup.send(embed=embed, view=view)
                        return
                    else:
                        await interaction.followup.send("Trapard est dans aucun vocal, tu es one head ou quoi ?", ephemeral=True)
                        return
                else:
                    await interaction.followup.send("Là tu es cringe frérot.", ephemeral=True)
                    return
            elif button.custom_id == "like":
                current = self.bot.current_track[self.serverid]
                if current:
                    async with self.bot.pool.acquire() as conn:
                        async with conn.transaction():
                            result = await conn.fetchall("SELECT * FROM LikedSongs WHERE userId = ?", (str(interaction.user.id),))
                            if result:
                                # check if the song is already liked
                                for song in result:
                                    if song[2] == current:
                                        embed = create_embed(title="Musique", description=f"<@{interaction.user.id}>, tu as déjà liké cette musique.", suggestions=["mlist","play", "search"])
                                        return await interaction.followup.send(embed=embed)
                            await conn.execute("INSERT INTO LikedSongs (userId, songName) VALUES (?, ?)", (str(interaction.user.id), current))
                            embed = create_embed(title="Musique", description=f"<@{interaction.user.id}>, la musique `{current}` a été ajoutée à tes musiques likées.", suggestions=["mlist","play", "search"])
                    return await interaction.followup.send(embed=embed)
            elif button.custom_id == "prev":
                if self.music_controler.voice_clients[self.serverid] is None:
                    return await interaction.followup.send("Trapard est dans aucun vocal, tu es one head ou quoi ?", ephemeral=True)
                vc = self.music_controler.voice_clients[self.serverid]
                if self.serverid in self.bot.current_track:
                    mu = self.bot.current_track[self.serverid]
                else:
                    mu = ""
                await self.music_controler.add_next_to_queue(self.serverid, self.bot.last_music[self.serverid])
                vc.stop()
                embed = create_embed(title="Musique", description=f"La musique `{mu}` a été passé par <@{interaction.user.id}>, afin de jouer la musique précédente `{self.bot.last_music[self.serverid]}`.", suggestions=["mlist","play", "search"])
                view = EndSessionBtn(bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler, timeout=None)
                return await interaction.followup.send(embed=embed,view=view)
            elif button.custom_id == "sb":
                return await handle_sb(ctx=interaction, bot=self.bot, music_controler=self.music_controler, userId=interaction.user.id)
        async def on_timeout(self):
            try: return await self.ctx.edit_original_response(view=None)
            except: pass
        
    except Exception as e:
        LogErrorInWebhook()

async def NewPlayAll(ctx: commands.Context, bot: Trapard, music_controler: MusicController, music_list_handler: MusicList_Handler, options: dict = None):
    """Options:
    - include: list of users to include
    - exclude: list of users to exclude
    - shuffle: True or False
    - `Default: shuffle=True and include=None and exclude=None`

    `{"include": None, "exclude": None, "shuffle": True}`
    """
    try:
        if options is not None:
            include : list = options["include"]
            exclude : list = options["exclude"]
            shuffle = options["shuffle"]
        else:
            include = None
            exclude = None
            shuffle = True
        try:
            if isinstance(ctx, commands.Context):
                voice = ctx.author.voice
            elif isinstance(ctx, discord.Interaction):
                voice = ctx.user.voice
            if voice is None: # Si le user nest dans aucun voocal
                embed = create_embed(title="Erreur", description="Vous n'êtes pas dans un channel vocal, **BUICON**.", suggestions=["queue","mlist","playlist-play"])
                if isinstance(ctx, commands.Context):
                    return await ctx.send(embed=embed, ephemeral=True)
                elif isinstance(ctx, discord.Interaction):
                    return await ctx.channel.send(embed=embed)
            if isinstance(ctx, commands.Context):
                user_vocal = ctx.author.voice.channel
            elif isinstance(ctx, discord.Interaction):
                user_vocal = ctx.user.voice.channel
            server_id = ctx.guild.id
            musicList = await music_list_handler.getAllMusicPath()
            total_musics_len = await music_list_handler.Get_Total_Musics_Len()

            added_musics_len = 0

            if ctx.guild.id not in music_controler.voice_clients:
                await music_controler.join_vc(server_id=ctx.guild.id, channel=user_vocal)
            vc: discord.VoiceClient = music_controler.voice_clients[server_id]
            if shuffle:
                random.shuffle(musicList)
            for music in musicList:
                if include is not None:
                    ___, dler = await music_list_handler.get_index_by_music_name(music)
                    if int(dler) in include:
                        continue
                if exclude is not None:
                    ___, dler = await music_list_handler.get_index_by_music_name(music)
                    if int(dler) in exclude:
                        continue
                await music_controler.add_to_queue(server_id, music)
                added_musics_len += 1
            t = len(musicList)
            if shuffle:
                embed = create_embed(title="Musique", description=f"{added_musics_len} musiques ont été ajouté à la queue aléatoirement ! `{t} musiques` pour une durée de `{total_musics_len}`.", suggestions=["queue","mlist","playlist-play"])
            else: 
                embed = create_embed(title="Musique", description=f"{added_musics_len} musiques ont été ajouté à la queue dans l'ordre ! `{t} musiques` pour une durée de `{total_musics_len}`.", suggestions=["queue","mlist","playlist-play"])
            messages = await getMusicQueue(server_id, bot, music_list_handler)
            view = PlayAllView(queue_messages=messages, serverid=server_id, ctx=ctx, bot=bot, music_controler=music_controler, music_list_handler=music_list_handler, unique_downloader=music_controler.unique_downloader)
            if isinstance(ctx, commands.Context):
                await ctx.send(embed=embed, view=view)
            elif isinstance(ctx, discord.Interaction):
                await ctx.channel.send(embed=embed, view=view)
            if not vc.is_playing():
                await music_controler.play_music(server_id=ctx.guild.id)
            return
        except Exception as e:
            print(e)
    except Exception as e:
        LogErrorInWebhook()

class PlayAllSelectUsersInclude(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=2000)
        self.selected = None
        

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Inclure des utilisateurs", min_values=1, max_values=6)
    async def my_user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        try: await interaction.response.defer()
        except: pass
        select.disabled = True
        users = [
            user.id for user in select.values
        ]
        self.selected = users
        self.stop()
        return

class PlayAllSelectUsersExclude(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.selected = None

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Exclure des utilisateurs", min_values=1, max_values=6)
    async def my_user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        try: await interaction.response.defer()
        except: pass
        select.disabled = True
        users = [
            user.id for user in select.values
        ]
        self.selected = users
        self.stop()
        return

class PlayAllChangeOrderBtn(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__()
        self.ctx = ctx

        self.btn = discord.ui.Button(label=f"Mélangé", custom_id=f"shuffle", style=discord.ButtonStyle.blurple, emoji="🔀", disabled=True)
        self.add_item(self.btn)
        self.btn.callback = lambda interaction=self.ctx, button=self.btn: self.on_button_click(interaction, button)

        self.btn1 = discord.ui.Button(label=f"Ordre d'ajout", custom_id=f"order", style=discord.ButtonStyle.blurple, emoji="🔢")
        self.add_item(self.btn1)
        self.btn1.callback = lambda interaction=self.ctx, button=self.btn1: self.on_button_click(interaction, button)

    async def on_button_click(self, ctx: discord.Interaction, button: discord.ui.Button):
        try: await ctx.response.defer()
        except: pass

        if button.custom_id == "shuffle":
            return await NewPlayAll(ctx=ctx, options={"include": None, "exclude": None, "shuffle": True})
        elif button.custom_id == "order":
            return await NewPlayAll(ctx=ctx, options={"include": None, "exclude": None, "shuffle": False})

class PlayAllMoreOptions(discord.ui.View):
    def __init__(self, ctx: commands.Context, bot: Trapard, music_controler: MusicController, music_list_handler: MusicList_Handler):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.music_list_handler = music_list_handler
        self.music_controler = music_controler
        
        self.btn = discord.ui.Button(label=f"Inclure des utilisateurs", custom_id=f"include", style=discord.ButtonStyle.green)
        self.add_item(self.btn)
        self.btn.callback = lambda interaction=self.ctx, button=self.btn: self.on_button_click(interaction, button)

        self.btn1 = discord.ui.Button(label=f"Exclure des utilisateurs", custom_id=f"exclude", style=discord.ButtonStyle.red)
        self.add_item(self.btn1)
        self.btn1.callback = lambda interaction=self.ctx, button=self.btn1: self.on_button_click(interaction, button)

        self.btn2 = discord.ui.Button(label=f"Changer l'ordre des musiques", custom_id=f"change", style=discord.ButtonStyle.blurple)
        self.add_item(self.btn2)
        self.btn2.callback = lambda interaction=self.ctx, button=self.btn2: self.on_button_click(interaction, button)

    async def on_button_click(self, ctx: discord.Interaction, button: discord.ui.Button):
        try: await ctx.response.defer()
        except: pass

        if button.custom_id == "include":
            view = PlayAllSelectUsersInclude()
            message = await ctx.followup.send(view=view, ephemeral=True)
            trys = 0
            while view.selected is None:
                if trys == 10000:
                    return await ctx.followup.send("Vous avez mit trop de temps à répondre !", ephemeral=True)
                await sleep(0.1)
            try: await message.delete()
            except: LogErrorInWebhook()
            return await NewPlayAll(ctx=ctx, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler, options={"include": view.selected, "exclude": None, "shuffle": True})
        elif button.custom_id == "exclude":
            view = PlayAllSelectUsersExclude()
            message = await ctx.followup.send(view=view, ephemeral=True)
            trys = 0
            while view.selected is None:
                if trys == 10000:
                    return await ctx.followup.send("Vous avez mit trop de temps à répondre !", ephemeral=True)
                await sleep(0.1)
            try: await message.delete()
            except: LogErrorInWebhook()
            return await NewPlayAll(ctx=ctx, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler, options={"exclude": view.selected, "include": None, "shuffle": True})
        elif button.custom_id == "change":
            view = PlayAllChangeOrderBtn(ctx=ctx)
            return await ctx.followup.send(view=view, ephemeral=True)

class DropDownMlist(discord.ui.Select): # Youtube Select
    try:
        def __init__(self, ctx: commands.Context, options: list[discord.SelectOption], bot: Trapard, music_controler: MusicController):
            super().__init__(placeholder='Choisis une des musiques 🦈', options=options, max_values=1, min_values=1)
            self.ctx = ctx
            self.bot = bot
            self.music_controler = music_controler
            self.user_id = None
        async def callback(self, interaction: discord.Interaction):
            try:
                await interaction.response.defer()
            except:
                pass
            val = str(self.values[0])
            self.user_id = str(val)
            if val == "tous":
                options = [discord.SelectOption(label="Tous", value=f"tous", default=True, emoji="🦈")]
            else:
                options = [discord.SelectOption(label="Tous", value=f"tous", default=False, emoji="🦈")]
            for unique in self.music_controler.unique_downloader:
                user = await self.bot.fetch_user(int(unique))
                if str(val) == str(unique):
                    options.append(discord.SelectOption(label=user.display_name, value=f"{unique}", default=True))
                else:
                    options.append(discord.SelectOption(label=user.display_name, value=f"{unique}", default=False))

            # Par exemple :
            if val != 'tous':
                mlist = await self.music_controler.music_list_handler.getMList(userid=int(self.user_id))
            else:
                mlist = await self.music_controler.music_list_handler.getMList()
            view = QueueBtn(mlist, len(mlist), self.ctx)
            drop = DropDownMlist(ctx=self.ctx, options=options, bot=self.bot, music_controler=self.music_controler)
            view.add_item(drop)

            try:
                await interaction.message.edit(embed=mlist[0], view=view)
            except:
                await interaction.message.edit(embed=mlist)

    except Exception as e:
        LogErrorInWebhook()

class DropDown(discord.ui.Select):
    try:
        def __init__(self, options, ctx, bot: Trapard, music_list_handler: MusicList_Handler, music_controler: MusicController, music_session: dict):
            super().__init__(placeholder='Choisis une des musiques 🦈', options=options, max_values=1, min_values=1)
            self.ctx = ctx
            self.bot = bot
            self.music_list_handler = music_list_handler
            self.music_controler = music_controler
            self.music_session=music_session
        async def callback(self, interaction: discord.Interaction):
            val = self.values[0]
            url = getVideoId(val)
            userid = interaction.user.id
            channel = interaction.channel_id
            serverid = interaction.guild_id
            user = interaction.user
            await interaction.response.send_message(f"La musique {val} est en cours de téléchargement ! 🦈")
            user = str(user).split("#")[0]
            if await download_from_url(url=url, user=user, channel_id=channel, userid=userid, serverid=serverid,cmd="search", ctx=self.ctx, bot=self.bot, music_list_handler=self.music_list_handler,music_controler=self.music_controler,music_session=self.music_session) == True:
                return
            else:
                return await interaction.channel.send("Erreur lors du téléchargement ! 🦈")
                
    except Exception as e:
        LogErrorInWebhook()

class DropDownView(discord.ui.View):
    try:
        def __init__(self, ctx):
            super().__init__()
            self.ctx = ctx
    except Exception as e:
        LogErrorInWebhook()

class SoundBoardManage:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    async def save_sound(self, sound_name: str, downloader: int, duration: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO soundboard (name, downloader, duration) VALUES (?,?,?)", (sound_name, downloader, duration,))
        return 
    
    async def get_all_sounds_name(self):
        async with self.pool.acquire() as conn:
            data = await conn.fetchall("SELECT name FROM soundboard")
        if data:
            out = []
            for sound in data:
                out.append(f"{sound[0]}")
            return out
        else: return None

    async def get_sound_id(self, name:str):
        async with self.pool.acquire() as conn:
            data = await conn.fetchone("SELECT id FROM soundboard WHERE name = ?", (name,))
        if data: return data[0]
        return None

    async def delete_sound(self, id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM soundboard WHERE id = ?", (id,))
        return True
    
    async def get_sound_duration(self, sound_name: str):
        async with self.pool.acquire() as conn:
            data = await conn.fetchone("SELECT duration FROM soundboard WHERE name = ?", (sound_name, ))
        if data:
            return data[0]
        return 0

class SoundBoardView(discord.ui.View):
    """`sounds`: page_num list of a list """
    def __init__(self, *, sounds: List[List[discord.ui.Button]], ctx: commands.Context, music_controler: MusicController, bot: Trapard, sb_manage: SoundBoardManage):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.music_controler = music_controler
        self.sounds = sounds
        self.page_count = len(sounds)
        self.current_page = 0
        self.bot = bot
        self.sb_manage = sb_manage
        if self.sounds is not None:
            for button in self.sounds[self.current_page]:
                self.add_item(button)
                button.callback = lambda interaction=self.ctx, button=button: self.play_sound(interaction, button,button.custom_id)
            self.add_control_btns()

    def add_control_btns(self):
        self.boutton_last = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="▶️", custom_id="next", row=4)
        self.boutton_first = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="last", row=4)
        self.button_stg = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="🔷", custom_id="setting", row=4, disabled=True)
        if self.current_page == 0:
            self.boutton_previous = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="◀️", disabled=True, custom_id="prev", row=4)
            self.boutton_suivant = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏮️", disabled=True, custom_id="first", row=4)
        else:
            self.boutton_suivant = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏮️", disabled=False, custom_id="first", row=4)
            self.boutton_previous = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="◀️", disabled=False, custom_id="prev", row=4)


        self.add_item(self.boutton_suivant)
        self.add_item(self.boutton_previous)
        self.add_item(self.button_stg)
        self.add_item(self.boutton_last)
        self.add_item(self.boutton_first)


        self.boutton_suivant.callback = lambda interaction=self.ctx, button=self.boutton_suivant: self.go_to_first_page(interaction, button)
        self.boutton_previous.callback = lambda interaction=self.ctx, button=self.boutton_previous: self.go_to_previous_page(interaction, button)
        # self.boutton_stg.callback = lambda interaction=self.ctx, button=self.button_stg: self.(interaction, button)
        self.boutton_last.callback = lambda interaction=self.ctx, button=self.boutton_last: self.go_to_next_page(interaction, button)
        self.boutton_first.callback = lambda interaction=self.ctx, button=self.boutton_first: self.go_to_last_page(interaction, button)

    async def show_current_page(self, interaction: discord.Interaction, direction: int):
        self.current_page += direction
        if self.current_page < 0:
            self.current_page = 0
        elif self.current_page >= self.page_count:
            self.current_page = self.page_count - 1
        elif self.current_page == self.page_count:
            self.current_page = self.page_count
        self.clear_items() # Remove all btns
        for button in self.sounds[self.current_page]:
            self.add_item(button)
            button.callback = lambda interaction=self.ctx, button=button: self.play_sound(interaction, button,button.custom_id)
        self.add_control_btns()
        first = discord.utils.get(self.children, custom_id="first")
        prev = discord.utils.get(self.children, custom_id="prev")
        next = discord.utils.get(self.children, custom_id="next")
        last = discord.utils.get(self.children, custom_id="last")

        if self.current_page < 2:
            first.disabled = True
        else: 
            first.disabled = False
        if self.current_page < 1:
            prev.disabled = True
        else: 
            prev.disabled = False
        if self.current_page >= self.page_count - 1:
            next.disabled = True
        else: 
            next.disabled = False
        if self.current_page >= self.page_count - 2:
            last.disabled = True
        else: 
            last.disabled = False

        embed = create_embed(title="SoundBoard", description=f"Page {self.current_page+1}/{self.page_count}")
        await interaction.message.edit(embed=embed,view=self)
        try:
            await interaction.response.defer()
        except:
            pass
        
    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_current_page(interaction, -self.current_page)

    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_current_page(interaction, -1)

    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.page_count - 1:
            await self.show_current_page(interaction, 1)
        else:
            await self.show_current_page(interaction, 0)
    
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_current_page(interaction, self.page_count - 1 - self.current_page)

    async def play_sound(self, interaction: discord.Interaction, button: discord.ui.Button, btn_name: str):
        try:
            await interaction.response.defer()
        except:
            pass
        if not self.music_controler.is_vc(server_id=self.ctx.guild.id):
            if self.ctx.author.voice is None:
                embed = create_embed(title="SoundBoard", description="Il semble que tu n'es pas connecté à un vocal...")
                return await interaction.followup.send(embed=embed, ephemeral=True)
            await self.music_controler.join_vc(server_id=self.ctx.guild.id, channel=self.ctx.author.voice.channel)
        vc: discord.VoiceClient = self.music_controler.voice_clients[self.ctx.guild.id]
        if (interaction.guild.id in self.music_controler.music_session) and (self.music_controler.music_session[interaction.guild.id]['paused']['status'] is False):
            sound_time = await self.sb_manage.get_sound_duration(sound_name=btn_name)
            self.music_controler.music_session[interaction.guild.id]['paused']['status'] = True
            self.music_controler.music_session[interaction.guild.id]['paused']['sound_time'] = sound_time
        if vc.is_playing():
            previous_source, time = self.music_controler.get_current_playing_song(server_id=self.ctx.guild.id)
            hours, remainder = divmod(time, 3600)
            minutes, seconds = divmod(remainder, 60)
            time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            vc.pause()
            source = discord.FFmpegPCMAudio(f"{SOUNDBOARD}{btn_name}.mp3")
            vc.play(source)
            while vc.is_playing():
                await asyncio.sleep(0.2)
            if (interaction.guild.id in self.music_controler.music_session):
                self.music_controler.music_session[interaction.guild.id]['paused']['status'] = False
            source = discord.FFmpegPCMAudio(previous_source, before_options=f'-ss {time}')
            vc.play(source)
        else:
            source = discord.FFmpegPCMAudio(f"{SOUNDBOARD}{btn_name}.mp3")
            vc.play(source)
            while vc.is_playing:
                await asyncio.sleep(0.2)
            if (interaction.guild.id in self.music_controler.music_session):
                self.music_controler.music_session[interaction.guild.id]['paused']['status'] = False
        return

class SoundBoardDropDown(discord.ui.Select):
    try:
        def __init__(self, options, ctx, bot: Trapard, soundboard_manager: SoundBoardManage):
            super().__init__(placeholder='Choisis un des sons :', options=options, max_values=1, min_values=1)
            self.ctx = ctx
            self.bot = bot
            self.soundboard_manager = soundboard_manager

        async def callback(self, interaction: discord.Interaction):
            val = self.values[0]
            url = getVideoId(val)
            await interaction.response.send_message(f"Le son {val} est en cours de téléchargement !")
            if await download_from_urlV2(
                url=url, 
                channel_id=interaction.channel.id, 
                userid=interaction.user.id,
                cmd="search", 
                ctx=self.ctx, 
                bot=self.bot,
                soundboard_manager=self.soundboard_manager
            ) == True:
                return
            else:
                return await interaction.channel.send(f"Erreur lors du téléchargement du son {val} !")
                
    except Exception as e:
        LogErrorInWebhook()

async def download_from_urlV2(url, channel_id, userid, cmd, soundboard_manager: SoundBoardManage , bot: Trapard, ctx: commands.Context=None):
    """Download youtube video from url."""
    def check_file(name:str):
        """Check if file exists and is not empty"""
        path = SOUNDBOARD
        if name in os.listdir(path):
            # Check file size
            size = os.path.getsize(path + name)
            if size > 0:
                return True
            else:
                return False
        else:
            return False
    
    try:
        video_url = url
        video = YouTube(video_url)

        duration = video.length
        file_name = rename(video.title)

        formatMention = "<@" + str(userid) + ">"
        saved_names = await soundboard_manager.get_all_sounds_name()
        if saved_names:
            if file_name in saved_names:
                embed = create_embed(title="Erreur", description=f"- {formatMention}, il semble que le son `{file_name}` ait déjà été téléchargée.\n\n- Le téléchargement a été annulé.")
                if ctx is not None:
                    await ctx.send(embed=embed)
                else:
                    await chann.send(embed=embed)
                return False

        url = video_url
        if duration > 30:
            embed = create_embed(title="Erreur", description=f"- {formatMention}, le son fait plus de **30 secondes**.\n\n- Le téléchargement a été annulé.")
            if ctx is not None:
                await ctx.send(embed=embed)
            else:
                await chann.send(embed=embed)
            return False
        
        async def download_thread(url, channel_id):
            # Code for downloading the video


            video_url = url
            
            video = YouTube(video_url)

            videoName = rename(video.title)
            stream = video.streams.filter(only_audio=True).first()

            stream.download(output_path=SOUNDBOARD, filename=f'{videoName}')

        def run_thread(coro):
            asyncio.run(coro)

        # Start the download in a separate thread
        thread = threading.Thread(target=run_thread, args=(download_thread(url, channel_id),))
        thread.start()

        # Wait for the thread to finish
        thread.join()
        # Check if there was an exception in the thread
        if thread.is_alive():
            # The thread is still running, which means there was an exception
            # Handle the exception here
            return False
        else:
            if check_file(file_name) is False:
                embed = create_embed(title="Erreur", description=f"- {formatMention}, il semble que la musique `{video.title}` n'ait pas été téléchargée.\n\n- La musique est peut-être soumise à une restriction d'âge ou n'existe pas.\n\n- Le téléchargement a été annulé.")
                if ctx is not None:
                    await ctx.send(embed=embed)
                else:
                    await chann.send(embed=embed)
                return False
            message = formatMention + f" Le son `{video.title}` est téléchargé !"
            chann = bot.get_channel(int(channel_id))
            embed = create_embed(title="Musique", description=message)
            if cmd != "DL":
                if ctx is not None:
                    await ctx.send(embed=embed)
                else:
                    await chann.send(embed=embed)
            else:
                if ctx is not None:
                    await ctx.send(embed=embed)
                else:
                    await chann.send(embed=embed)

        file_name = str(file_name).split(".")[0]
        await soundboard_manager.save_sound(str(file_name), int(userid), duration=duration)
        return True
    except Exception as e:
        LogErrorInWebhook()

playlist_data = []
playlist_names = get_all_playlists_names()

class Music(commands.Cog):
    """Music related cog."""
    def __init__(self, bot: Trapard) -> None:
        self.bot: Trapard = bot
        self.music_list_handler = MusicList_Handler(bot=self.bot)
        self.music_session = {}
        self.music_controler = MusicController(bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.bot.unique_downloader, music_session=self.music_session)
    
    async def handler_music_input(self, index: str, musique_name:str, channel_name:str, author_voice: bool, author_id:int):
        if not index and not musique_name:
            return QuestionnaireMusicPlay(bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler, custom_id="play-next")
        if musique_name is not None:
            index = musique_name
        if channel_name != "musique":
            return create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
        if author_voice is None: # Si le user nest dans aucun voocal
            return create_embed(title="Erreur", description="Vous n'êtes pas dans un channel vocal, **BUICON**.", suggestions=["queue","mlist","playlist-play"])
        output_musics = []
        if is_comma_separated(index):
            wantedList, erreur = parse_user_indexs(index)
            if erreur is not None:
                return create_embed(title="Erreur", description=f"- Le numéro que tu as donné n'est pas bon.\n{erreur}", suggestions=["play","play-next","mlist"])
            for i in wantedList:
                if i is not None:
                    output_musics.append(await self.music_list_handler.getName(str(i)))
            music_name = "Queue"
        else: # pas de virgule
            if "*" in index:
                tmp = []
                multiplicateur = int(index.split('*')[0])
                valeur = int(index.split('*')[1])
                tmp.extend([str(valeur)] * multiplicateur)
                for t in tmp:
                    output_musics.append(await self.music_list_handler.getName(str(t)))
            else:
                output_musics.append(await self.music_list_handler.getName(index))
                try:
                    music_name = await self.music_list_handler.getName(str(index))
                except ValueError:
                    return create_embed(title="Erreur", description=f"- Le numéro que tu as donné n'est pas bon.\n{erreur}", suggestions=["play","play-next","mlist"])
                if music_name == "Song not found.":
                    return create_embed(title="Erreur", description=f"- Le numéro que tu as donné n'est pas bon.\n{erreur}", suggestions=["play","play-next","mlist"])
        for songName in output_musics:
            await FavSongsDbHandler(pool=self.bot.pool, song_name=songName, user_id=str(author_id))
        return output_musics

# PLAY GROUP
    @commands.hybrid_group(name="play")
    async def play1(self, ctx: commands.Context): pass

    @play1.command() # old: /play
    @app_commands.describe(index="Le/les numéro(s): 1 | 1,2,3 | 1-10")
    @app_commands.describe(musique_name="Chercher la musique par texte (sans espace).")
    async def music(self, ctx: commands.Context, index:str=None, musique_name:str=None):
        """Joue une ou plusieurs musique(s)."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            _musiques = await self.handler_music_input(index=index, musique_name=musique_name, channel_name=ctx.channel.name, author_id=ctx.author.id, author_voice=ctx.author.voice)
            if isinstance(_musiques, discord.Embed):
                return await ctx.send(embed=embed)
            elif isinstance(_musiques, list):
                messages = await getMusicQueue(server_id=ctx.guild.id, music_list_handler=self.music_list_handler, bot=self.bot)
                view = PlayAllView(queue_messages=messages, serverid=ctx.guild.id, ctx=ctx,music_session = self.music_session, music_controler=self.music_controler, bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.bot.unique_downloader)

                if not self.music_controler.is_vc(server_id=ctx.guild.id):
                    await self.music_controler.join_vc(server_id=ctx.guild.id, channel=ctx.author.voice.channel)
                vc: discord.VoiceClient = self.music_controler.voice_clients[ctx.guild.id]
                for i in _musiques:
                    if i is not None:
                        await self.music_controler.add_to_queue(ctx.guild.id, i)
                    else:
                        continue
                embed = create_embed(title="Musique", description=f"`{', '.join(_musiques)}` ajouté à la queue.", suggestions=["queue","mlist","playlist-play"])
                await ctx.send(embed=embed, view=view)
                if not vc.is_playing():
                    await self.music_controler.play_music(server_id=ctx.guild.id)
                return
            elif isinstance(_musiques, QuestionnaireMusicPlay):
                return await ctx.send(_musiques)
        except:
            LogErrorInWebhook()

    @music.autocomplete("musique_name")
    async def autocomplete_musique_name(self,ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in key.lower():
                    liste.append(app_commands.Choice(name=f"{key} ({val})", value=str(val)))
                if len(liste) == 25:
                    break
            return liste
        except Exception as e:
            LogErrorInWebhook()

    @play1.command(name="liked") # old: /play-all-liked-songs
    @app_commands.describe(user= "Jouer les musiques de cette utilisateur.")
    async def play_liked(self, ctx: commands.Context, user: discord.User = None):
        """Joue toutes les musiques likés d'un utilisateur."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        if ctx.channel.name != "musique":
            embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
            return await ctx.send(embed=embed, ephemeral=True)
        if user is None:
            user = ctx.author
        if ctx.author.voice is None: # Si le user nest dans aucun voocal
            embed = create_embed(title="Erreur", description="Vous n'êtes pas dans un channel vocal, **BUICON**.", suggestions=["queue","mlist","playlist-play"])
            return await ctx.send(embed=embed)
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall("SELECT * FROM LikedSongs WHERE userId = ?", (str(user.id),))
        if len(data) == 0:
            embed = create_embed(title="Erreur", description=f"<@{user.id}> n'a pas de musiques likés.")
            return await ctx.send(embed=embed, ephemeral=True)
        else:
            music_list = []
            for d in data:
                id, userId, songName = d
                music_list.append(songName)
        random.shuffle(music_list)
        if not self.music_controler.is_vc(server_id=ctx.guild.id):
            await self.music_controler.join_vc(server_id=ctx.guild.id, channel=ctx.author.voice.channel)
        vc: discord.VoiceClient = self.music_controler.voice_clients[ctx.guild.id]
        for i in music_list:
            if i is not None:
                await self.music_controler.add_to_queue(ctx.guild.id, i)
            else:
                continue
        embed = create_embed(title="Musique", description=f"`{len(music_list)} musique` ajouté à la queue. (titres likés de {user.display_name})", suggestions=["queue","mlist","playlist-play"])
        await ctx.send(embed=embed)
        if not vc.is_playing():
            await self.music_controler.play_music(server_id=ctx.guild.id)
        return

    @play1.command(name='next') #old: /play-next
    @app_commands.describe(index="Le/les numéro(s): 1 | 1,2,3 | 1-10")
    @app_commands.describe(musique_name="Chercher la musique par texte (sans espace).")
    async def play_next(self, ctx: commands.Context, index:str=None, musique_name:str=None):
        """Play-next une musique"""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            _musiques = await self.handler_music_input(index=index, musique_name=musique_name, channel_name=ctx.channel.name, author_id=ctx.author.id, author_voice=ctx.author.voice)
            messages = await getMusicQueue(server_id=ctx.guild.id, bot=self.bot, music_list_handler=self.music_list_handler)
            view = PlayAllView(queue_messages=messages, serverid=ctx.guild.id, ctx=ctx,music_session = self.music_session, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler, unique_downloader=self.bot.unique_downloader)
            if isinstance(_musiques, discord.Embed):
                return await ctx.send(embed=embed)
            elif isinstance(_musiques, list):
                messages = await getMusicQueue(server_id=ctx.guild.id, music_list_handler=self.music_list_handler, bot=self.bot)
                view = PlayAllView(queue_messages=messages, serverid=ctx.guild.id, ctx=ctx,music_session = self.music_session, music_controler=self.music_controler, bot=self.bot, music_list_handler=self.music_list_handler, unique_downloader=self.bot.unique_downloader)

                if not self.music_controler.is_vc(server_id=ctx.guild.id):
                    await self.music_controler.join_vc(server_id=ctx.guild.id, channel=ctx.author.voice.channel)
                vc: discord.VoiceClient = self.music_controler.voice_clients[ctx.guild.id]
                for i in _musiques:
                    if i is not None:
                        await self.music_controler.add_next_to_queue(ctx.guild.id, i)
                    else:
                        continue
                embed = create_embed(title="Musique", description=f"`{', '.join(_musiques)}` est/sont les prochaines musique à jouer.", suggestions=["queue","mlist","playlist-play"])
                await ctx.send(embed=embed, view=view)
                if not vc.is_playing():
                    await self.music_controler.play_music(server_id=ctx.guild.id)
                return
            elif isinstance(_musiques, QuestionnaireMusicPlay):
                return await ctx.send(_musiques)
        except:
            LogErrorInWebhook()

    @play_next.autocomplete("musique_name")
    async def autocomplete_musique_name(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in key.lower():
                    liste.append(app_commands.Choice(name=f"{key} ({val})", value=str(val)))
                if len(liste) == 25:
                    break
            return liste
        except Exception as e:
            LogErrorInWebhook()
    
    @play1.command(name="all") #old: /play-all
    @app_commands.describe(more_options="Inclure ou exclure des utilisateurs & changer l'ordre des musiques")
    @app_commands.choices(more_options=[
        discord.app_commands.Choice(name="Afficher plus d'options", value="True")
        ])
    async def play_all(self, ctx: commands.Context, more_options: discord.app_commands.Choice[str]=None):
        """Jouer toutes les musiques, selon vos paramètres."""
        print("called")
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if ctx.channel.name != "musique":
                embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
                return await ctx.send(embed=embed, ephemeral=True)
            if more_options is not None:
                if more_options.value == "True":
                    return await ctx.send(view=PlayAllMoreOptions(ctx=ctx, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler), ephemeral=True)
                else:
                    return await NewPlayAll(ctx=ctx, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler)
            else:
                return await NewPlayAll(ctx=ctx, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler)
        except Exception as e:
            print(e)
            LogErrorInWebhook()
# END PLAY GROUP

    @commands.hybrid_command() #old: /mlist
    async def mlist(self, ctx: commands.Context):
        """Affiche la liste de toutes les musiques."""
        if not isinstance(ctx, CustomContext):
            try: await ctx.interaction.response.defer()
            except: print("error defer")
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            options = [discord.SelectOption(label="Téléchargé par : Tous", value=f"tous", default=True, emoji="🦈")]
            for unique in self.bot.unique_downloader:
                user = await self.bot.fetch_user(int(unique))
                if user:
                    name = user.display_name
                    options.append(discord.SelectOption(label=name, value=f"{unique}", default=False))
            else:
                drop = DropDownMlist(ctx=ctx, options=options, bot=self.bot, music_controler=self.music_controler)
                mlist = await self.music_list_handler.getMList()
                view = QueueBtn(mlist, len(mlist), ctx)
                view.add_item(drop)
                await ctx.send(embed=mlist[0], view=view)
        except:
            LogErrorInWebhook()

    @commands.hybrid_command(name='download', aliases=['search', 'dl', 'sh']) #old: /search and /download
    @app_commands.describe(keysearch = "Url Youtube ou texte de recherche.")
    async def download(self, interaction: commands.Context, *, keysearch: str):
        """Télécharger une musique, par url Youtube, ou par texte de recherche."""
        try:
            await command_counter(user_id=str(interaction.author.id), bot=self.bot)
            if interaction.channel.name != "musique":
                return await interaction.send("Merci d'utiliser le channel <#896275056089530380> **BUICON**", ephemeral=True)
            if is_url(keysearch):
                url = keysearch
                if '?list=' in url:
                    new_url = url.split("?list=")[0]
                    embed = create_embed(title="Musique", description=f"L'url : `{url}` proviens d'une playlist !\n\nL'url est remplacée par : `{new_url}`.\n\nLe téléchargement est en cours...")
                    await interaction.send(embed=embed)
                    url = new_url
                else:
                    embed = create_embed(title="Musique", description=f"Téléchargement en cours...")
                    await interaction.send(embed=embed)
                user = interaction.author
                userid = interaction.author.id
                user = str(user).split("#")[0]
                cmd = "DL"
                if await download_from_url(url=url, 
                    user=user, 
                    channel_id=interaction.channel.id,
                    userid=userid, 
                    serverid=interaction.guild.id, 
                    cmd=cmd, 
                    ctx=interaction, 
                    bot=self.bot, 
                    music_list_handler=self.music_list_handler,
                    music_controler=self.music_controler,
                    music_session=self.music_session,
                ) == True:
                    pass
                return
            else:
                string = keysearch.strip()
                results = YoutubeSearch(string, max_results=15).to_dict()
                index = 0
                global videos
                videos = {}
                try:
                    for result in results:
                        if index == 5:
                            break
                        title, channel, id, durr = result["title"], result["channel"], result["id"], result["duration"]
                        if title not in [v[0] for v in videos.values()]: # Check if the title is already present in the dictionary
                            videos["video" + str(index)] = []
                            videos["video" + str(index)].append(title)
                            videos["video" + str(index)].append(channel)
                            videos["video" + str(index)].append(id)
                            videos["video" + str(index)].append(durr)
                            index += 1
                        else:
                            print("SAME VALUE !!!!")

                    desc1 = "Chaine:" + str(videos['video0'][1]) + " | Durée: " +  str(videos['video0'][3])
                    desc2 = "Chaine:" + str(videos['video1'][1]) + " | Durée: " +  str(videos['video1'][3])
                    desc3 = "Chaine:" + str(videos['video2'][1]) + " | Durée: " +  str(videos['video2'][3])
                    desc4 = "Chaine:" + str(videos['video3'][1]) + " | Durée: " +  str(videos['video3'][3])
                    desc5 = "Chaine:" + str(videos['video4'][1]) + " | Durée: " +  str(videos['video4'][3])
                except Exception as e:
                    print(e)
                    return await interaction.send(f"Une erreur est survenue lors de la récupération des résultats. | Merci de réessayer. {e}", ephemeral=True)
                options = [
                    discord.SelectOption(label=videos['video0'][0], description=desc1),
                    discord.SelectOption(label=videos['video1'][0], description=desc2),
                    discord.SelectOption(label=videos['video2'][0], description=desc3),
                    discord.SelectOption(label=videos['video3'][0], description=desc4),
                    discord.SelectOption(label=videos['video4'][0], description=desc5)
                ]
                drop_down = DropDown(options=options, ctx=interaction, bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler, music_session=self.music_session)
                view = DropDownView(ctx=interaction)
                view.add_item(drop_down)

                try:
                    await interaction.send(f"Résultat de la recherche `{string}`:", view=view)
                except Exception as e:
                    return await interaction.send(f"Une erreur est survenue lors de la récupération des résultats. | Merci de réessayer.", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

# Music controler
    @commands.hybrid_command(name='skip', aliases=["next"]) # old: /skip
    async def skip(self, ctx: commands.Context):
        """Passer la musique actuelle."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            messages = await getMusicQueue(server_id=ctx.guild.id, bot=self.bot, music_list_handler=self.music_list_handler)
            view = PlayAllView(queue_messages=messages, serverid=ctx.guild.id, ctx=ctx,music_session = self.music_session, bot=self.bot, music_controler=self.music_controler, music_list_handler=self.music_list_handler, unique_downloader=self.bot.unique_downloader)
            if ctx.channel.name != "musique":
                embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
                return await ctx.send(embed=embed, ephemeral=True)
            # Get the voice client associated with the server
            if ctx.guild.id not in self.music_controler.voice_clients:
                return await ctx.send("Trapard est dans aucun vocal, tu es one head ou quoi ?", ephemeral=True)
            cur_track = self.bot.current_track[ctx.guild.id]
            vc: discord.VoiceClient = self.music_controler.voice_clients[ctx.guild.id]
            await storeSkippedSong(pool=self.bot.pool, songname=cur_track, userid=str(ctx.author.id))
            # Stop the current player and move to the next one
            vc.stop()
            embed = create_embed(title="Musique", description=f"La musique `{cur_track}` a été passé par <@{ctx.author.id}>.")
            return await ctx.send(embed=embed,view=view)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name='dc',aliases=["disconnect", "leave", "stop"]) # old: /dc
    async def disconnect(self, interaction: commands.Context):
        """Déconnecter le bot du salon vocal et reset la queue."""
        try:
            await command_counter(user_id=str(interaction.author.id), bot=self.bot)
            try:
                del self.bot.music_queues[interaction.guild.id]
                del self.music_controler.voice_clients[interaction.guild.id]
            except KeyError:
                pass
            if interaction.guild:
                vc = interaction.guild.voice_client
                if vc:
                    await vc.disconnect()
                    self.bot.music_queues[interaction.guild.id] = []
                    txt = f"Le bot a été déconnecté et la file d'attente réinitialisée par {interaction.author.mention}.\n\nCette session, j'ai joué **{self.music_session[interaction.guild.id]['music_played']}** musiques, pour un total de **{convert_to_minutes_seconds(self.music_session[interaction.guild.id]['time'])}**."
                    embed = create_embed(title="Fin de session", description=txt)
                    try: del self.music_session[interaction.guild.id]
                    except: pass
                    view = EndSessionBtn(bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler, timeout=None)
                    await interaction.send(embed=embed, view=view)
                    return
                else:
                    await interaction.send("Trapard est dans aucun vocal, tu es one head ou quoi ?", ephemeral=True)
                    return
            else:
                await interaction.send("Là tu es cringe frérot.", ephemeral=True)
                return
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name='remove', aliases=['del','delete', "supprimer", "supp"]) #old: /remove
    @app_commands.describe(index="Le numéro exemple: 657")
    @app_commands.describe(musique_name="Supprimer la musique par son nom (sans espace).")
    async def remove(self, ctx: commands.Context, index: int=None, musique_name:str=None):
        """Enlever une musique de la liste."""
        try:
            if music_name is not None:
                index = musique_name
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            playlist_indexs = await self.music_list_handler.get_all_index_in_playlists()
            if str(index) in playlist_indexs:
                # La musique existe dans une playlist.
                embed = create_embed(title="Suppression", description=f"<@{ctx.author.id}>\n- La musique {index} est présente dans une playlist !\n\n- Merci de l'enlever avec </playlist-modify:1115881059352068176> avant.")
                return await ctx.send(embed=embed)
            music_name = await self.music_list_handler.getName(str(index))
            if music_name == "Unknown index.":
                next_index = await self.music_list_handler.get_next_index()
                embed = create_embed(title="Suppression", description=f"<@{ctx.author.id}>\n- La musique {index} semble ne pas exister !\n\n- **L'index maximal actuel dans la mlist est {next_index - 1}**.")
                return await ctx.send(embed=embed)
            path = MUSICS_FOLDER + music_name + ".mp3"
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            await self.music_list_handler.remove_from_music_list(str(index))
            embed = create_embed(title="Suppression", description=f"Musique `{music_name}` supprimée !", suggestions=["queue","mlist","playlist-play"])
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @remove.autocomplete("musique_name")
    async def autocomplete_musique_nameX(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in key.lower():
                    liste.append(app_commands.Choice(name=f"{key} ({val})", value=str(val)))
                if len(liste) == 25:
                    break
            return liste
        except Exception as e:
            LogErrorInWebhook()

#End music controler
    
    @commands.hybrid_command(name='is-song', aliases=["find"]) #old: /is-song
    @app_commands.describe(nom= "Nom de la musique à chercher. Cela peut-être une partie du nom. Minimum 3 caractères")
    async def is_song(self, interaction: commands.Context, nom: str):
        """Vérifier si une musique a déjà été téléchargée."""
        try:
            await command_counter(user_id=str(interaction.author.id), bot=self.bot)
            if interaction.channel.name != "musique":
                return await interaction.send("Merci d'utiliser le channel <#896275056089530380> **BUICON**", ephemeral=True)
            if len(nom) < 3:
                return await interaction.send("Merci d'entrer minimum 3 caractères pour effectuer la recherche.", ephemeral=True)
            if ' ' in nom:
                nom = nom.replace(' ', '')
            result, found = await self.music_list_handler.find_song_by_name(nom)
            if len(found) <= 5:
                if len(found) == 1:
                    suggestions = SuggestionPlay(server_id=interaction.guild.id, ctx=interaction, index=found[0], bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler)
                else:
                    suggestions = SuggestionPlay(server_id=interaction.guild.id, ctx=interaction, index_list=found, bot=self.bot, music_list_handler=self.music_list_handler, music_controler=self.music_controler)
                embed = create_embed(title="Is-song", description=result, suggestions=["play", "mlist", "queue"])
                return await interaction.send(embed=embed, view=suggestions)
            else:
                embed = create_embed(title="Is-song", description=result, suggestions=["play", "mlist", "queue"])
                return await interaction.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

# Playlist
    @commands.hybrid_group()
    async def playlist(self, ctx: commands.Context):
        pass
    
    @playlist.command()
    @app_commands.describe(playlistname = "Le nom que tu vas donner à ta playlist")
    @app_commands.describe(indexs = "La liste des numéros des musiques, séparés par des virgules")
    async def create(self, ctx: commands.Context, playlistname: str, indexs: str):
        """Créer une playlist, et y ajouter des musiques."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            try:
                if is_comma_separated(indexs) is True:
                    wantedList, erreur = parse_user_indexs(indexs)
                    if erreur is not None:
                        em_error = create_embed(title="Erreur", description=f"- Le numéro que tu as donné n'est pas bon.\n{erreur}", suggestions=["play","play-next","mlist"])
                        return await ctx.send(embed=em_error)
                    out = []
                    for i in wantedList:
                        out.append(await self.music_list_handler.getName(str(i)))

                    allSong = ''
                    for i in out:
                        allSong += i + ","
                    with open(PLAYLIST_LIST, "a") as f:
                        f.write(playlistname)
                        f.write("=")
                        f.write(allSong)
                        f.write('\n')
                    f.close()
                    return await ctx.send(f"La playlist `{playlistname}` a bien été créé !")
                else:
                    return await ctx.send("Veuillez entrer une liste de musique correcte.\nExemple: `/playlist-create MaPlaylist1 2,6,8,1,12,66`", ephemeral=True)
            except Exception as e:
                return await ctx.send("Veuillez entrer une liste de musique correcte.\nExemple: `/playlist-create MaPlaylist1 2,6,8,1,12,66`", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

    @playlist.command()
    async def list(self, ctx: commands.Context):
        """Affiche la liste des playlists."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            lines = open(PLAYLIST_LIST, "r").readlines()
            embed = discord.Embed(title="Playlist-list")
            for line in lines:
                playlist_name, musics_list_str = line.strip().split("=", maxsplit=1)
                playlist_text_name = ""
                if "," in musics_list_str:
                    musics_list_str = musics_list_str.strip().split(",")
                    for pos, playlist_text in enumerate(musics_list_str):
                        if playlist_text is not None and playlist_text != "" and playlist_text != "\n":
                            if pos != len(musics_list_str):
                                try:
                                    index = await self.music_list_handler.get_index_by_music_name(playlist_text)[0]
                                    playlist_text_name += f"`{playlist_text}` **({index})**, "
                                except TypeError:
                                    pass
                            else: 
                                index = await self.music_list_handler.get_index_by_music_name(playlist_text)[0]
                                playlist_text_name += f"`{playlist_text}` **({index})**"
                                break
                else:
                    playlist_text_name = "Aucune musique dans la playlist."
                
                MAX = 1024
                if len(playlist_text_name) > MAX:
                    for i in range(1, 10):
                        if len(playlist_text_name) > MAX *i:
                            break
                    for n in range(0, i+1):
                        if n == 0:
                            to_add = playlist_text_name[:MAX].rfind(',')
                            embed.add_field(name=f'{playlist_name}', value=f'{playlist_text_name[:to_add]}', inline=False)
                        else:
                            to_add = playlist_text_name[:MAX].rfind(',')
                            embed.add_field(name='', value=f'{playlist_text_name[1:to_add]}', inline=False)
                        playlist_text_name = playlist_text_name[to_add:]
                else:
                    embed.add_field(name=playlist_name, value=playlist_text_name, inline=False)
                    
            return await ctx.send(embed=embed)
            
        except Exception as e:
            LogErrorInWebhook()

    @playlist.command()
    @app_commands.describe(playlistname = "Le nom de la playlist à jouer.")
    @app_commands.describe(melange = "Mélanger la playlist ou non.")
    async def play(self, ctx: commands.Context, playlistname: str, melange: bool=True):
        """Joue la playlist souhaité."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if playlistname not in playlist_names:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)                 
            messages = await getMusicQueue(server_id=ctx.guild.id, bot=self.bot,music_list_handler=self.music_list_handler)
            view = PlayAllView(queue_messages=messages, serverid=ctx.guild.id, ctx=ctx, bot=self.bot,music_session = self.music_session, music_controler=self.music_controler, music_list_handler=self.music_list_handler, unique_downloader=self.bot.unique_downloader)
            if ctx.author.voice is None:
                return await ctx.send("Vous n'êtes pas dans un channel vocal, **BUICON**.", ephemeral=True)
            musicList = getMusicList(playlistname)
            if musicList is None:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)
            if not self.music_controler.is_vc(server_id=ctx.guild.id):
                await self.music_controler.join_vc(server_id=ctx.guild.id, channel=ctx.author.voice.channel)
            vc: discord.VoiceClient = self.music_controler.voice_clients[ctx.guild.id]
            if melange:
                embed = create_embed(title="Musique", description=f"La playlist `{playlistname}` a été ajouté à la queue en aléatoire !")
                random.shuffle(musicList)
            else: 
                embed = create_embed(title="Musique", description=f"La playlist `{playlistname}` a été ajouté à la queue dans l'ordre !")
            for music in musicList:
                await self.music_controler.add_to_queue(ctx.guild.id, music)
            if not vc.is_playing(): 
                await self.music_controler.play_music(server_id=ctx.guild.id)
            return await ctx.send(embed=embed,view=view)
        except Exception as e:
            LogErrorInWebhook()

    @playlist.command(name="remove") 
    @app_commands.describe(playlistname = "Le nom de la playlist à supprimer.")
    async def remove1(self, ctx: commands.Context, playlistname: str):
        """Supprimer une playlist."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if playlistname not in playlist_names:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)
            def remove_line_from_file(line_number):
                file_path = PLAYLIST_LIST
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                if line_number < 0 or line_number >= len(lines):
                    return False

                lines.pop(line_number)

                with open(file_path, 'w') as f:
                    f.writelines(lines)
            
            lines = open(PLAYLIST_LIST, "r").readlines()
            index = 0
            for line in lines:
                lineF = line.split('=')[0]
                if lineF == playlistname:
                    break
                index += 1
            r = remove_line_from_file(index)
            if r is False:
                text = f"Le nom de la playlist semble invalide ou ne pas exister..."
            text = f"Playlist {playlistname} a bien été supprimé !"
            return await ctx.send(embed=create_embed(title="Playlist-remove", description=text))
        except Exception as e:
            LogErrorInWebhook()

    @playlist.command()
    @app_commands.describe(playlistname = "Le nom de la playlist à modifier.")
    @app_commands.describe(action_type = "Choisir add ou remove.")
    @app_commands.describe(indexes="Les numéros: 1,2,3 | 1-10")
    async def edit(self, ctx: commands.Context, playlistname: str, action_type: Literal["add", "remove"], indexes: str):
        """Modifier une playlist. Exemple: !playlist edit BPM remove 1,2,3,4"""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            embed = None
            if playlistname not in playlist_names:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)

            lines = open(PLAYLIST_LIST, "r").readlines()
            for i, line in enumerate(lines):
                file_playlist_name, musics = line.split("=", maxsplit=1)
                if playlistname == file_playlist_name:
                    break

            musiques_list = musics.split(",") # File music list

            file_music_index = [] # File playlist music index list 
            for i, musique in  enumerate(musiques_list):
                musique = musique.strip()
                index = await self.music_list_handler.get_index_by_music_name(musique)[0]
                val = str(index)
                if val is not None and val != "None":
                    file_music_index.append(val)

            output_text = ""

            if "," in indexes:
                index_list = indexes.split(",") # User input list
                user_playlist_music_name_list = [] # User input music name list
                for index in index_list:
                    user_playlist_music_name_list.append(await self.music_list_handler.getName(str(index)))
                output_text += "Les musiques "
                if action_type == "add":
                    for user_index_input in index_list: # Ajouter les music à la playliste
                        if user_index_input not in file_music_index:
                            if user_index_input != "None" and user_index_input is not None:
                                file_music_index.append(user_index_input)
                            else: embed = create_embed(title="Playlist-modify", description=f"Une erreur est survenue. Tu es sur d'avoir entré les bons numéros ? :\n```{index_list}```")
                        else: embed = create_embed(title="Playlist-modify", description=f"Erreur !\nLa musique `{self.music_list_handler.getName(str(user_index_input))}` **({user_index_input})** existe déjà dans la playlist !") 
                    
                    nouvelle_ligne = f"{playlistname}="
                    for pos, n in enumerate(file_music_index):
                        if pos != len(file_music_index) - 1:
                            n_name = await self.music_list_handler.getName(str(n))
                            nouvelle_ligne += f'{n_name},'
                        else:
                            n_name = await self.music_list_handler.getName(str(n))
                            nouvelle_ligne += f'{n_name}'

                    for pos, val in enumerate(user_playlist_music_name_list):
                        if pos != len(user_playlist_music_name_list) - 1:
                            output_text += f" `{val}`, "
                        else:
                            output_text += f" `{val}` "
                    output_text += " ont étais ajoutés."

                elif action_type == "remove": # Ici il faut enlever les indexs du user.
                    for user_index_input in index_list: # Enlever les music à la playliste
                        if user_index_input in file_music_index:
                            if user_index_input != "None" and user_index_input is not None:
                                file_music_index.remove(user_index_input)
                            else: embed = create_embed(title="Playlist-modify", description=f"Une erreur est survenue. Tu es sur d'avoir entré les bons numéros ? :\n```{index_list}```")
                        else: embed = create_embed(title="Playlist-modify", description=f"Erreur !\nLa musique `{await self.music_list_handler.getName(str(user_index_input))}` **({user_index_input})** n'existe pas dans la playlist !") 

                    nouvelle_ligne = f"{playlistname}="
                    for pos, n in enumerate(file_music_index):
                        if pos != len(file_music_index) - 1:
                            n_name = await self.music_list_handler.getName(str(n))
                            nouvelle_ligne += f'{n_name},'
                        else:
                            n_name = await self.music_list_handler.getName(str(n))
                            nouvelle_ligne += f'{n_name}'
                    for pos, val in enumerate(user_playlist_music_name_list):
                        if pos != len(user_playlist_music_name_list) - 1:
                            output_text += f" `{val}`, "
                        else:
                            output_text += f" `{val}` "

                    output_text += "ont étais enlevées."
                    # On est bon ici
                    
            elif not ',' in indexes: # pas de virgule
                user_index_input = indexes.strip()
                output_text += "La musique "
                if action_type == "add": # Ajouter l'index          
                    if indexes not in file_music_index:
                        file_music_index.append(indexes)
                        nouvelle_ligne = f"{playlistname}="
                        for pos, n in enumerate(file_music_index):
                            if pos != len(file_music_index) - 1:
                                n_name = await self.music_list_handler.getName(str(n))
                                nouvelle_ligne += f'{n_name},'

                            else:
                                n_name = await self.music_list_handler.getName(str(n))
                                nouvelle_ligne += f'{n_name}'
                                # On est bon ici
                    else: embed = create_embed(title="Playlist-modify", description=f"Erreur !\nLa musique `{await self.music_list_handler.getName(str(user_index_input))}` **({user_index_input})** existe déjà dans la playlist !") 
                    output_text += f"`{await self.music_list_handler.getName(str(indexes))}` a été ajoutée."
                elif action_type == "remove": # Enlever un index
                    if indexes in file_music_index:
                        file_music_index.remove(indexes)
                        nouvelle_ligne = f"{playlistname}="
                        for pos, n in enumerate(file_music_index):
                            if pos != len(file_music_index) - 1:
                                n_name = await self.music_list_handler.getName(str(n))
                                nouvelle_ligne += f'`{n_name}`,'

                            else:
                                n_name = await self.music_list_handler.getName(str(n))
                                nouvelle_ligne += f'`{n_name}`'

                    else: embed = create_embed(title="Playlist-modify", description=f"Erreur !\nLa musique `{await self.music_list_handler.getName(str(user_index_input))}` **({user_index_input})** n'existe pas dans la playlist !") 
                    output_text += f"`{await self.music_list_handler.getName(str(indexes))}` a été enlevée."
            else: 
                if action_type == "add": # Ajouter l'index erreur 
                    embed = create_embed(title="Playlist-modify", description=f"Une erreur est survenue, pour ajouter une ou des musiques, merci d'utiliser ce format:\n`/g-laylist-modify add 254`\n`/g-laylist-modify add 254,255,256,257`")
                elif action_type == "remove": # Enlever un index erreur
                    embed = create_embed(title="Playlist-modify", description=f"Une erreur est survenue, pour enlever une ou des musiques, merci d'utiliser ce format:\n`/g-laylist-modify remove 254`\n`/g-laylist-modify remove 254,255,256,257`")

            if embed:
                return await ctx.send(embed=embed)
            # Il faut ecrire la new playlist ici
            for i, line in enumerate(lines):
                file_playlist_name, musics = line.split("=", maxsplit=1)
                if playlistname == file_playlist_name:
                    lines[i] = nouvelle_ligne.replace("`", "") + "\n"
                    break
            with open(PLAYLIST_LIST, "w") as w:
                for line in lines:
                    w.write(line)

            embed = create_embed(title="Playlist-modify", description=output_text)
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name="liked-songs")
    @app_commands.describe(user= "L'utilisateur dont tu veux voir les musiques likés.")
    async def likedsongs(self, ctx: commands.Context, user: discord.User = None):
        """Affiche les musiques likés d'un utilisateur."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if user is None:
                userID = str(ctx.author.id)
                user = ctx.author
            else:
                userID = str(user.id)
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall(f"SELECT songName FROM LikedSongs WHERE userId = ?", (userID,))            
            if data == []:
                embed = create_embed(title="Liked-songs", description=f"<@{userID}> n'a pas de musiques likés !")
                return await ctx.send(embed=embed)
            else:
                string = ""
                for n,i in enumerate(data):
                    likedSongs = i[0]
                    if n == len(data)-1:
                        string += f"{likedSongs}"
                    else:
                        string += f"{likedSongs}, "
                embed = create_embed(title=f"Musiques likés de {user.display_name}", description=string)
                return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

# SoundBoard group
    @commands.hybrid_group(name="soundboard", aliases=["sb"], fallback='menu')            
    async def soundboard(self, ctx: commands.Context):
        """Affiche les sons de la soundboard."""
        return await handle_sb(ctx=ctx, bot=self.bot, music_controler=self.music_controler)

    @soundboard.command(name='download', aliases=['dl'])
    @app_commands.describe(keysearch = "Url Youtube ou texte de recherche.")
    async def soundboard_download(self, interaction: commands.Context, *, keysearch: str):
        """Télécharger une musique, par url Youtube, ou par texte de recherche."""
        try:
            await command_counter(user_id=str(interaction.author.id), bot=self.bot)
            if interaction.channel.name != "musique":
                return await interaction.send("Merci d'utiliser le channel <#896275056089530380> **BUICON**", ephemeral=True)
            if is_url(keysearch):
                url = keysearch
                if '?list=' in url:
                    new_url = url.split("?list=")[0]
                    embed = create_embed(title="Musique", description=f"L'url : `{url}` proviens d'une playlist !\n\nL'url est remplacée par : `{new_url}`.\n\nLe téléchargement est en cours...")
                    await interaction.send(embed=embed)
                    url = new_url
                else:
                    embed = create_embed(title="Musique", description=f"Téléchargement en cours...")
                    await interaction.send(embed=embed)
                user = interaction.author
                userid = interaction.author.id
                user = str(user).split("#")[0]
                cmd = "DL"
                if await download_from_urlV2(
                    url=url, 
                    channel_id=interaction.channel.id,
                    userid=userid,
                    cmd=cmd, 
                    ctx=interaction, 
                    bot=self.bot,
                    soundboard_manager=SoundBoardManage(pool=self.bot.pool)
                ) == True:
                    pass
                return
            else:
                string = keysearch.strip()
                results = YoutubeSearch(string, max_results=25).to_dict()
                index = 0
                global videos
                videos = {}
                try:
                    for result in results:
                        if index == 5:
                            break
                        title, channel, id, durr = result["title"], result["channel"], result["id"], result["duration"]
                        if title not in [v[0] for v in videos.values()]: # Check if the title is already present in the dictionary
                            l = result["duration"].split(":")
                            sec = int(l[1])
                            min = int(l[0])
                            tot = (min*60) + sec
                            if int(tot) <= 20: 
                                videos["video" + str(index)] = []
                                videos["video" + str(index)].append(title)
                                videos["video" + str(index)].append(channel)
                                videos["video" + str(index)].append(id)
                                videos["video" + str(index)].append(durr)
                                index += 1
                        else:
                            print("SAME VALUE !!!!")
                    if len(videos) == 0:
                        return await interaction.send(f"Aucun résultat pour la recherche {keysearch}...\n\n**Penses à utiliser un lien Youtube à la place!**", ephemeral=True)
                    descs = []
                    for i in range(0, len(videos)):
                        descs.append(f"Chaine: {str(videos[f'video{i}'][1])} | Durée: {str(videos[f'video{i}'][3])}")
                except Exception as e:
                    traceback.print_exc()
                    print(e)
                    return await interaction.send(f"Une erreur est survenue lors de la récupération des résultats. | Merci de réessayer. {e}", ephemeral=True)
                options = [discord.SelectOption(label=videos[f'video{i}'][0], description=descs[i]) for i in range(0, len(videos))]
                drop_down = SoundBoardDropDown(options=options, ctx=interaction, bot=self.bot, soundboard_manager=SoundBoardManage(pool=self.bot.pool))
                view = DropDownView(ctx=interaction)
                view.add_item(drop_down)
                try:
                    await interaction.send(f"Résultat de la recherche `{string}`:", view=view)
                except Exception as e:
                    return await interaction.send(f"Une erreur est survenue lors de la récupération des résultats. | Merci de réessayer.", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

    @soundboard.command(name="delete", aliases=["del"])
    @app_commands.describe(id = "Le numéro du son à supprimer.")
    async def soundboard_delete(self, ctx: commands.Context, id: int=None, sound_name: str=None):
        """Supprime le son correspondant à l'id."""
        mng = SoundBoardManage(pool=self.bot.pool)
        
        if id:
            await mng.delete_sound(id)
            embed = create_embed(title="SoundBoard", description=f"Le son **N°{id}** a bien été supprimé.")
        elif sound_name:
            await mng.delete_sound(sound_name)
            embed = create_embed(title="SoundBoard", description=f"Le son **N°{sound_name}** a bien été supprimé.")
        else: 
            embed = create_embed(title="SoundBoard", description=f"Le son **N°{id}** semble ne pas exister...")
        return await ctx.send(embed=embed)

    @soundboard_delete.autocomplete("sound_name")
    async def autocomplete_soundboard_delete(self, ctx: discord.Interaction, musique_name: str):
        try:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT id, name FROM soundboard")
            choices = []
            for item in data:
                if musique_name.lower() in str(item[1]).lower():
                    choices.append(app_commands.Choice(name=f"{item[1]} ({item[0]})", value=str(item[0])))
                if len(choices) == 25:
                    break
            return choices
        except Exception as e:
            LogErrorInWebhook()
    # End SoundBoard group

async def handle_sb(ctx: commands.Context, bot: Trapard, music_controler: MusicController, userId: int=None):
    """Affiche les sons de la soundboard."""
    try:
        if isinstance(ctx, discord.Interaction): 
            if ctx.user.voice is None:
                embed = create_embed(title="Erreur", description="Bien tenté, mais tu n'es pas dans le vocal :).", suggestions=["queue","mlist","playlist-play"])
                return await ctx.followup.send(embed=embed, ephemeral=True)
        elif isinstance(ctx, commands.Context):
            if ctx.author.voice is None:
                embed = create_embed(title="Erreur", description="Bien tenté, mais tu n'es pas dans le vocal :).", suggestions=["queue","mlist","playlist-play"])
                return await ctx.send(embed=embed, ephemeral=True)
        if userId:
            user_id = userId
        else:
            user_id = ctx.author.id
        await command_counter(user_id=str(user_id), bot=bot)
        async with bot.pool.acquire() as conn:
            data = await conn.fetchall(f"SELECT name, id FROM soundboard")
        if data:
            output = []
            for sound in data: 
                output.append(discord.ui.Button(label=f'{sound[0]} ({sound[1]})', style=discord.ButtonStyle.blurple, custom_id=sound[0]))
            sounds = [output[i:i + 20] for i in range(0, len(output), 20)] # list of list of 20 btns
            view = SoundBoardView(sounds=sounds, ctx=ctx, music_controler=music_controler, bot=bot, sb_manage=SoundBoardManage(pool=bot.pool))
            embed = create_embed(title="SoundBoard", description=f"Page 1/{len(sounds)}")
        else:
            embed = create_embed(title="SoundBoard", description=f"Aucun son ne semble avoir été téléchargé.")
            view = None
        if isinstance(ctx, discord.Interaction):
            return await ctx.followup.send(embed=embed, view=view, ephemeral=True)
        else: 
            return await ctx.send(embed=embed, view=view, ephemeral=True)
    except: LogErrorInWebhook()

async def setup(bot: Trapard):
    await bot.add_cog(Music(bot))