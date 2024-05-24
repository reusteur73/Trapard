from typing import Literal, List, Tuple, cast, TYPE_CHECKING
from discord.ext import commands
from youtube_search import YoutubeSearch
from discord import app_commands
from pytube import YouTube
from time import perf_counter
from asyncio import sleep
from .utils.functions import LogErrorInWebhook, command_counter, create_embed, convert_str_to_emojis, printFormat, convert_int_to_emojis, is_url, convert_to_minutes_seconds, rename, getMList, save_song_stats
from .utils.path import PLAYLIST_LIST, MUSICS_FOLDER, SOUNDBOARD
from .utils.context import Context as CustomContext
import traceback, random, os, asyncio, threading, base64, io, discord, wavelink
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

async def getMusicQueue(server_id, bot, music_list_handler, current_song_time=0):
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
        serverid: int,
        avatar: str = None,
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
    def add_corners(im, rad):
        circle = Image.new('L', (rad * 2, rad * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)
        alpha = Image.new('L', im.size, 255)
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im
    
    FONT = "/home/debian/trapard/files/Retron2000.ttf"
    img = Image.open("/home/debian/trapard/files/music_img.png")

    # Defining draw
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 18)

    fontLarge = ImageFont.truetype(FONT, 64)
    fontSmall = ImageFont.truetype(FONT, 44)
    if avatar is not None:
        augm = len(downloader) * 20
        _avatar = Image.open(avatar).convert("RGBA")
        _avatar = add_corners(_avatar, 100)
        _avatar = _avatar.resize((165, 165), Image.LANCZOS)
        img.paste(_avatar, (1150 + augm, 166), _avatar)
    else: print("avatar is None")
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
    def __init__(self, title: str, bot):
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
    def __init__(self, bot, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot

    @discord.ui.button(label="play all", custom_id="play_all", style=discord.ButtonStyle.green, emoji="🎲")
    async def play_all(self, interaction: discord.Interaction, button: discord.Button):
        try:
            try: await interaction.response.defer()
            except: pass
            await command_counter(user_id=str(interaction.user.id), bot=self.bot)
            if interaction.channel.name != "musique":
                embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
                return await interaction.channel.send(embed=embed)
            out = []
            mlist_handler = MusicList_Handler(bot=self.bot)
            try:
                vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            except discord.errors.ClientException:
                vc: wavelink.Player = interaction.guild.voice_client
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT name FROM musiques")
                for d in data:
                    out.append(d[0])
            zic_chann = discord.utils.get(interaction.guild.channels, name="musique", type=discord.ChannelType.text)
            tracks = []
            for track in out:
                _track: wavelink.Search = await wavelink.Playable.search(f"{MUSICS_FOLDER}{track}.mp3", source=None)
                if len(_track) > 0:
                    index, downloader = await mlist_handler.get_index_by_music_name(track)
                    duration = await mlist_handler.get_song_duration_by_index(str(index))
                    _track[0].extras = {"_downloader": downloader, "_index": index, "_name": track, "_duration": duration, "_txt_chann": zic_chann.id}
                    tracks.append(_track[0])
            random.shuffle(tracks)
            await vc.queue.put_wait(tracks)
            try:
                if not vc.playing:
                    await vc.play(vc.queue.get(), volume=100)
            except Exception as e:
                print(e)
            embed = create_embed(title="Musique", description=f"Toutes les musiques (**{len(tracks)}**) ont été ajoutées à la queue en mode aléatoire par <@{interaction.user.id}> !")
            try:
                return await interaction.followup.send(embed=embed)
            except discord.errors.NotFound:
                return await interaction.channel.send(embed=embed)
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
            mlist_handler = MusicList_Handler(bot=self.bot)
            zic_chann = discord.utils.get(interaction.guild.channels, name="musique", type=discord.ChannelType.text)
            for d in data:
                id, userId, songName = d
                _track = await wavelink.Playable.search(f"{MUSICS_FOLDER}{songName}.mp3", source=None)
                if len(_track) > 0:
                    index, downloader = await mlist_handler.get_index_by_music_name(songName)
                    duration = await mlist_handler.get_song_duration_by_index(str(index))
                    _track[0].extras = {"_downloader": downloader, "_index": index, "_name": songName, "_duration": duration, "_txt_chann": zic_chann.id}
                    music_list.append(_track[0])
        random.shuffle(music_list)
        
        try:
            vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        except discord.errors.ClientException:
            vc: wavelink.Player = interaction.guild.voice_client

        await vc.queue.put_wait(music_list)
        embed = create_embed(title="Musique", description=f"`{len(music_list)} musique` ajouté à la queue. (titres likés de {user.display_name})", suggestions=["queue","mlist","playlist-play"])
        await interaction.followup.send(embed=embed)
        try:
            if not vc.playing:
                await vc.play(vc.queue.get(), volume=100)
        except Exception as e:
            pass
        return 

class MusicList_Handler():
    """
    Class pour controler la db musiques
    """
    def __init__(self, bot):
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

class SuggestionPlay(discord.ui.View):
    def __init__(self, server_id, ctx: commands.Context, bot,music_list_handler: MusicList_Handler, index_list: list=None, index: int=None):
        super().__init__(timeout=None)
        self.bot = bot
        if index:
            self.index = index
        elif index_list:
            self.index_list = index_list
        self.serverid = server_id
        self.ctx = ctx
        self.music_list_handler = music_list_handler

        if index:
            self.playnext_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play-next {self.index}', custom_id=f"playnext_{index}", disabled=False)
            self.add_item(self.playnext_btn)
            self.playnext_btn.callback = lambda interaction=self.ctx, button=self.playnext_btn: self.on_button_click(interaction, button, index=self.index)
        
        elif index_list:
            for index in index_list:
                self.playnext_btn = discord.ui.Button(style=discord.ButtonStyle.green, label=f'play-next {index}', custom_id=f"playnext_{index}", disabled=False)
                self.add_item(self.playnext_btn)
                self.playnext_btn.callback = lambda interaction=self.ctx, button=self.playnext_btn: self.on_button_click(interaction, button, index=index)            

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button, index):
        try:
            try:await interaction.response.defer()
            except:pass
            _, name = button.custom_id.split("_")
            if interaction.guild.voice_client: vc: wavelink.Player = interaction.guild.voice_client
            else: vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            track = await wavelink.Playable.search(f"{MUSICS_FOLDER}{name}.mp3", source=None)
            if len(track) > 0:
                index, downloader = await self.music_list_handler.get_index_by_music_name(name)
                duration = await self.music_list_handler.get_song_duration_by_index(str(index))
                track[0].extras = {"_downloader": downloader, "_index": index, "_name": name, "_duration": duration, "_txt_chann": interaction.channel.id}
                await vc.queue.put_wait(track)
                if not vc.playing:
                    await vc.play(vc.queue.get(), volume=100)
                embed = create_embed(title="Musique", description=f"`{name}` ajouté à la queue.", suggestions=["queue","mlist","playlist-play"])
                await interaction.followup.send(embed=embed)
            return
        except Exception as e:
            print(e)
            LogErrorInWebhook()

async def download_from_url(url, user, channel_id, userid, serverid, cmd, music_list_handler: MusicList_Handler,music_session, bot, ctx: commands.Context=None):
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
            view = SuggestionPlay(server_id=serverid, ctx=ctx, bot=bot, index=index, music_list_handler=music_list_handler)
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

class QueueBtnV2(discord.ui.View): # Queue List Buttons
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

class PlayAllViewV2(discord.ui.View): #Les trois buttons du play-all 
    try:
        def __init__(self, serverid, ctx: commands.Context, bot, player: wavelink.Player=None): 
            super().__init__(timeout=300)
            self.bot = bot
            self.serverid = serverid
            self.ctx = ctx
            self.unique_downloader = bot.unique_downloader
            if player is None:
                player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
            self.player = player

            # Previous song BTN
            if self.serverid in self.bot.last_music:
                self.prev_song_btn = discord.ui.Button(label="Musique d'avant", style=discord.ButtonStyle.primary, emoji="⬅", custom_id="prev", row=0, disabled=True) # temp disabled
            else:
                self.prev_song_btn = discord.ui.Button(label="Musique d'avant", style=discord.ButtonStyle.primary, emoji="⬅", custom_id="prev", row=0, disabled=True)
            self.add_item(self.prev_song_btn)
            self.prev_song_btn.callback = lambda interaction=self.ctx, button=self.prev_song_btn: self.on_button_click(interaction, button)

            self.sb_btn = discord.ui.Button(label="SoundBoard", style=discord.ButtonStyle.green, emoji="🔊", custom_id="sb", row=0)
            self.add_item(self.sb_btn)
            self.sb_btn.callback = lambda interaction=self.ctx, button=self.sb_btn: self.on_button_click(interaction, button)

            # Skip BTN
            if (len(player.queue) > 0):
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
                messages = await getMusicQueue(self.serverid, bot=self.bot)
                queue_view = QueueBtnV2(messages, len(messages), ctx=self.ctx)
                await interaction.channel.send(embed=messages[0], view=queue_view)
                view = PlayAllViewV2(interaction.guild_id, interaction, self.bot)
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
                    drop = DropDownMlist(ctx=interaction, options=options, bot=self.bot)
                    mlist = await getMList(bot=self.bot)
                    view = QueueBtnV2(mlist, len(mlist), interaction)
                    view.add_item(drop)
                    await interaction.followup.send(embed=mlist[0], view=view)
            elif button.custom_id == "skip":
                track = self.player.current
                await self.player.skip(force=True)
                if track is not None:
                    if self.player.guild.id in self.bot.server_music_session:
                        self.bot.server_music_session[self.player.guild.id]['nb'] +=  1
                    mu = track.extras._name
                    embed = create_embed(title="Musique", description=f"La musique `{mu}` a été passé par <@{interaction.user.id}>.", suggestions=["mlist","play", "search"])
                    await interaction.followup.send(embed=embed)
                    return await storeSkippedSong(pool=self.bot.pool, songname=mu, userid=str(interaction.user.id))
            elif button.custom_id == "disconnect":
                await self.player.disconnect()
                self.player.queue.clear()
                try:
                    if interaction.guild.id in self.bot.ui_V2:
                        await self.bot.ui_V2[interaction.guild.id].stop()
                        self.bot.ui_V2[interaction.guild.id].task.cancel()
                except Exception as e:
                    print("X02:", e)
                    pass
                if interaction.guild.id in self.bot.server_music_session:
                    played_time = convert_to_minutes_seconds(str(self.bot.server_music_session[interaction.guild.id]['time']))
                    embed = create_embed(title="Musique", description=f"Fin de session, j'ai joué {self.bot.server_music_session[interaction.guild.id]['nb']} musiques, pour une durée de **{played_time}**!")
                else: embed = create_embed(title="Musique", description=f"Trapard déconnecté du vocal par <@{interaction.user.id}>.", suggestions=["mlist","play", "search"])
                await interaction.followup.send(embed=embed,view=EndSessionBtn(bot=self.bot))
                if self.player.guild.id in self.bot.server_music_session:
                    self.bot.server_music_session[self.player.guild.id] = {'nb': 0, 'time': 0}
            elif button.custom_id == "like":
                current = self.player.current.extras._name
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
                pass
            elif button.custom_id == "sb":
                pass
                # return await handle_sb(ctx=interaction, bot=self.bot, music_controler=self.music_controler, userId=interaction.user.id)
        async def on_timeout(self):
            try: return await self.ctx.edit_original_response(view=None)
            except: pass
        
    except Exception as e:
        LogErrorInWebhook()

class DropDownMlist(discord.ui.Select): # Youtube Select
    try:
        def __init__(self, ctx: commands.Context, options: list[discord.SelectOption], bot):
            super().__init__(placeholder='Choisis une des musiques 🦈', options=options, max_values=1, min_values=1)
            self.ctx = ctx
            self.bot = bot
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
            for unique in self.bot.unique_downloader:
                user = await self.bot.fetch_user(int(unique))
                if str(val) == str(unique):
                    options.append(discord.SelectOption(label=user.display_name, value=f"{unique}", default=True))
                else:
                    options.append(discord.SelectOption(label=user.display_name, value=f"{unique}", default=False))

            # Par exemple :
            if val != 'tous':
                mlist = await getMList(self.bot,userid=int(self.user_id))
            else:
                mlist = await getMList(self.bot)
            view = QueueBtnV2(mlist, len(mlist), self.ctx)
            drop = DropDownMlist(ctx=self.ctx, options=options, bot=self.bot)
            view.add_item(drop)

            try:
                await interaction.message.edit(embed=mlist[0], view=view)
            except:
                await interaction.message.edit(embed=mlist)

    except Exception as e:
        LogErrorInWebhook()

class DropDown(discord.ui.Select):
    try:
        def __init__(self, options, ctx, bot, music_list_handler: MusicList_Handler, music_session: dict):
            super().__init__(placeholder='Choisis une des musiques 🦈', options=options, max_values=1, min_values=1)
            self.ctx = ctx
            self.bot = bot
            self.music_list_handler = music_list_handler
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
            if await download_from_url(url=url, user=user, channel_id=channel, userid=userid, serverid=serverid,cmd="search", ctx=self.ctx, bot=self.bot, music_list_handler=self.music_list_handler,music_session=self.music_session) == True:
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
    def __init__(self, *, sounds: List[List[discord.ui.Button]], ctx: commands.Context, bot, sb_manage: SoundBoardManage):
        super().__init__(timeout=None)
        self.ctx = ctx
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
        def __init__(self, options, ctx, bot, soundboard_manager: SoundBoardManage):
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

async def download_from_urlV2(url, channel_id, userid, cmd, soundboard_manager: SoundBoardManage , bot, ctx: commands.Context=None):
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
    def __init__(self, bot) -> None:
        self.bot = bot
        self.music_list_handler = MusicList_Handler(bot=self.bot)
        self.music_session = {}
    
    async def handler_music_input(self, index: str, musique_name:str, channel_name:str, author_voice: bool, author_id:int):
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
                return await ctx.send(embed=_musiques)
            elif isinstance(_musiques, list):
                vc: wavelink.Player = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player))
                tracks = []
                zic_chann = discord.utils.get(ctx.guild.channels, name="musique", type=discord.ChannelType.text)
                for track in _musiques:
                    _track: wavelink.Search = await wavelink.Playable.search(f"{MUSICS_FOLDER}{track}.mp3", source=None)
                    index, downloader = await self.music_list_handler.get_index_by_music_name(track)
                    duration = await self.music_list_handler.get_song_duration_by_index(str(index))
                    _track[0].extras = {"_downloader": downloader, "_index": index, "_name": track, "_duration": duration, "_txt_chann": zic_chann.id}
                    tracks.append(_track[0])
                await vc.queue.put_wait(tracks)
                try:
                    if not vc.playing:
                        await vc.play(vc.queue.get(), volume=100)
                except Exception as e:
                    print(e)
                try:
                    await ctx.message.add_reaction("\u2705")
                except discord.errors.NotFound:
                    pass
                embed = create_embed(title="Musique", description = f"{'La musique' if len(_musiques) == 1 else 'Les musiques'} `{', '.join(_musiques)}` {'est' if len(_musiques) == 1 else 'sont'} ajoutée{'s' if len(_musiques)>1 else ''} à la queue.", suggestions=["queue","mlist","playlist-play"])
                return await ctx.send(embed=embed)
        except Exception as e:
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
            zic_chann = discord.utils.get(ctx.guild.channels, name="musique", type=discord.ChannelType.text)
            music_list = []
            for track in data:
                _, __, songName = track
                _track: wavelink.Search = await wavelink.Playable.search(f"{MUSICS_FOLDER}{songName}.mp3", source=None)
                if len(_track) > 0:
                    index, downloader = await self.music_list_handler.get_index_by_music_name(songName)
                    duration = await self.music_list_handler.get_song_duration_by_index(str(index))
                    _track[0].extras = {"_downloader": downloader, "_index": index, "_name": songName, "_duration": duration, "_txt_chann": zic_chann.id}
                    music_list.append(_track[0])
        random.shuffle(music_list)
        vc: wavelink.Player = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player))
        added = await vc.queue.put_wait(music_list)
        try:
            if not vc.playing:
                await vc.play(vc.queue.get(), volume=100)
        except Exception as e:
            print(e)
        try:
            await ctx.message.add_reaction("\u2705")
        except discord.errors.NotFound:
            pass
        embed = create_embed(title="Musique", description=f"Les titres likés de <@{user.id}> ({added} musiques) ont été ajoutés à la queue.")
        return await ctx.send(embed=embed)

    @play1.command(name='next') #old: /play-next
    @app_commands.describe(index="Le/les numéro(s): 1 | 1,2,3 | 1-10")
    @app_commands.describe(musique_name="Chercher la musique par texte (sans espace).")
    async def play_next(self, ctx: commands.Context, index:str=None, musique_name:str=None):
        """Play-next une musique"""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            _musiques = await self.handler_music_input(index=index, musique_name=musique_name, channel_name=ctx.channel.name, author_id=ctx.author.id, author_voice=ctx.author.voice)
            if isinstance(_musiques, discord.Embed):
                return await ctx.send(embed=_musiques)
            elif isinstance(_musiques, list):
                vc: wavelink.Player = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player))
                zic_chann = discord.utils.get(ctx.guild.channels, name="musique", type=discord.ChannelType.text)
                for track in _musiques:
                    _track: wavelink.Search = await wavelink.Playable.search(f"{MUSICS_FOLDER}{track}.mp3", source=None)
                    index, downloader = await self.music_list_handler.get_index_by_music_name(track)
                    duration = await self.music_list_handler.get_song_duration_by_index(str(index))
                    _track[0].extras = {"_downloader": downloader, "_index": index, "_name": track, "_duration": duration, "_txt_chann": zic_chann.id}
                    if len(_track) > 0:
                        print('Adding:', _track[0].extras._name, _track,_track[0])
                        print(vc.queue)
                        vc.queue.put_at(0, _track[0])
                        print('Added:', _track[0].extras._name)

                try:    
                    if not vc.playing:
                        await vc.play(vc.queue.get(), volume=100)
                except Exception as e:
                    print(e)
                try:
                    await ctx.message.add_reaction("\u2705")
                except discord.errors.NotFound:
                    pass
                embed = create_embed(title="Musique", description = f"{'La musique' if len(_musiques) == 1 else 'Les musiques'} `{', '.join(_musiques)}` {'est' if len(_musiques) == 1 else 'sont'} ajoutée{'s' if len(_musiques)>1 else ''} en haut de la queue.", suggestions=["queue","mlist","playlist-play"])
                return await ctx.send(embed=embed)
        except Exception as e:
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
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if ctx.channel.name != "musique":
                embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
                return await ctx.send(embed=embed, ephemeral=True)
            out = []
            vc: wavelink.Player = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player))
            try:
                await ctx.message.add_reaction("\u2705")
            except discord.errors.NotFound:
                pass
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT name FROM musiques")
                for d in data:
                    out.append(d[0])
            zic_chann = discord.utils.get(ctx.guild.channels, name="musique", type=discord.ChannelType.text)
            tracks = []
            for track in out:
                _track: wavelink.Search = await wavelink.Playable.search(f"{MUSICS_FOLDER}{track}.mp3", source=None)
                if len(_track) > 0:
                    index, downloader = await self.music_list_handler.get_index_by_music_name(track)
                    duration = await self.music_list_handler.get_song_duration_by_index(str(index))
                    _track[0].extras = {"_downloader": downloader, "_index": index, "_name": track, "_duration": duration, "_txt_chann": zic_chann.id}
                    tracks.append(_track[0])
            random.shuffle(tracks)
            await vc.queue.put_wait(tracks)
            try:
                if not vc.playing:
                    await vc.play(vc.queue.get(), volume=100)
            except Exception as e:
                print(e)

            embed = create_embed(title="Musique", description=f"Toutes les musiques (**{len(tracks)}**) ont été ajoutées à la queue en mode aléatoire par <@{ctx.author.id}> !")
            try:
                return await ctx.send(embed=embed)
            except discord.errors.NotFound:
                return await ctx.channel.send(embed=embed)
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
            try:
                await ctx.message.add_reaction("\u2705")
            except discord.errors.NotFound:
                pass
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            options = [discord.SelectOption(label="Téléchargé par : Tous", value=f"tous", default=True, emoji="🦈")]
            for unique in self.bot.unique_downloader:
                user = await self.bot.fetch_user(int(unique))
                if user:
                    name = user.display_name
                    options.append(discord.SelectOption(label=name, value=f"{unique}", default=False))
            else:
                drop = DropDownMlist(ctx=ctx, options=options, bot=self.bot)
                mlist = await getMList(bot=self.bot)
                view = QueueBtnV2(mlist, len(mlist), ctx)
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
                drop_down = DropDown(options=options, ctx=interaction, bot=self.bot, music_list_handler=self.music_list_handler, music_session=self.music_session)
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
    @app_commands.describe(position="La position de la musique à passer. (rien pour passer la musique actuelle)")
    async def skip(self, ctx: commands.Context, position:int=None):
        """Passer la musique actuelle."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if ctx.channel.name != "musique":
                embed = create_embed(title="Erreur", description="Merci d'utiliser le channel <#896275056089530380> **BUICON**")
                return await ctx.send(embed=embed, ephemeral=True)
            if position is not None and (position < 1 or position > 5):
                return await ctx.send(embed=create_embed(title="Erreur", description="La position doit être entre 1 et 5."))
            player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
            if not player:
                return
            if position is None:
                cur_track = f"`{player.current.extras._name}` (**{player.current.extras._index}**) a été passé par "
                await player.skip(force=True)
            else:
                _cur_track = player.queue.get_at(position - 1)
                cur_track = f"`{_cur_track.extras._name}` (**{_cur_track.extras._index}**) a été retiré de la queue par "
            if ctx.guild.id in self.bot.server_music_session:
                self.bot.server_music_session[ctx.guild.id]['nb'] +=  1
            if ctx.guild.id in self.bot.musics_ui_status:
                self.bot.musics_ui_status[ctx.guild.id] = False
            try:
                self.bot.locks[ctx.guild.id].release()
            except RuntimeError:
                pass
            try:
                await ctx.message.add_reaction("\u2705")
            except discord.errors.NotFound:
                pass
            embed = create_embed(title="Musique", description=f"La musique {cur_track}  <@{ctx.author.id}>.")
            return await ctx.send(embed=embed)
        except:
            LogErrorInWebhook()

    @commands.hybrid_command(name='dc',aliases=["disconnect", "leave", "stop"]) # old: /dc
    async def disconnect(self, ctx: commands.Context):
        """Déconnecter le bot du salon vocal et reset la queue."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
            if not player:
                embed = create_embed(title="Erreur", description="Trapard est dans aucun vocal, tu es one head ou quoi ?")
                return await ctx.send(embed=embed)
            try:
                if ctx.guild.id in self.bot.ui_V2:
                    await self.bot.ui_V2[ctx.guild.id].stop()
                    self.bot.ui_V2[ctx.guild.id].task.cancel()
            except Exception as e:
                print("X02:", e)
                pass
            if ctx.guild.id in self.bot.server_music_session:
                played_time = convert_to_minutes_seconds(str(self.bot.server_music_session[ctx.guild.id]['time']))
                embed = create_embed(title="Musique", description=f"Fin de session, j'ai joué {self.bot.server_music_session[ctx.guild.id]['nb']} musiques, pour une durée de **{played_time}**!")
                self.bot.server_music_session[ctx.guild.id] = {'nb': 0, 'time': 0}
            else: embed = create_embed(title="Musique", description="Trapard déconnecté du vocal par <@" + str(ctx.author.id) + ">.")

            await player.disconnect()
            try:
                await ctx.message.add_reaction("\u2705")
            except discord.errors.NotFound:
                pass
            
            return await ctx.send(embed=embed, view=EndSessionBtn(bot=self.bot))
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
            try:
                await ctx.message.add_reaction("\u2705")
            except discord.errors.NotFound:
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
                    suggestions = SuggestionPlay(server_id=interaction.guild.id, ctx=interaction, index=found[0], bot=self.bot, music_list_handler=self.music_list_handler)
                else:
                    suggestions = SuggestionPlay(server_id=interaction.guild.id, ctx=interaction, index_list=found, bot=self.bot, music_list_handler=self.music_list_handler)
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
            if ctx.author.voice is None:
                return await ctx.send("Vous n'êtes pas dans un channel vocal, **BUICON**.", ephemeral=True)
            musicList = getMusicList(playlistname)
            if musicList is None:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)
            vc: wavelink.Player = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player))
            if melange:
                embed = create_embed(title="Musique", description=f"La playlist `{playlistname}` a été ajouté à la queue en aléatoire !")
                random.shuffle(musicList)
            else: 
                embed = create_embed(title="Musique", description=f"La playlist `{playlistname}` a été ajouté à la queue dans l'ordre !")
            tracks = []
            for music in musicList:
                _track = await wavelink.Playable.search(f"{MUSICS_FOLDER}{music}.mp3", source=None)
                if len(_track) == 0:
                    continue
                index, downloader = await self.music_list_handler.get_index_by_music_name(music)
                duration = await self.music_list_handler.get_song_duration_by_index(str(index))
                _track[0].extras = {"_downloader": downloader, "_index": index, "_name": music, "_duration": duration, "_txt_chann": ctx.channel.id}
                tracks.append(_track[0])
            if len(tracks) == 0:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)
            await vc.queue.put_wait(tracks)
            try:
                if not vc.playing:
                    await vc.play(vc.queue.get(), volume=100)
            except Exception as e:
                print(e)
            return await ctx.send(embed=embed)
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
                batch_size = 15
                fields = []
                songs = [f'`{i[0]}`' for i in data]
                batchs = [songs[i:i + batch_size] for i in range(0, len(songs), batch_size)]
                for i, batch in enumerate(batchs):
                    fields.append({"name": f"{i+1}.", "value": " - ".join(batch), "inline": False})
                embed = create_embed(title=f"Musiques likés de {user.display_name}", fields=fields, description=f"Total de musiques likés: {len(songs)}")
                return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name="remove-liked-song", aliases=["rm-liked", "dislike"])
    @app_commands.describe(index= "Le numéro (index) de la musique à enlever de tes musiques likés.")
    @app_commands.describe(musique_name="Le nom de la musique à enlever de tes musiques likés.")
    async def remove_liked_song(self, ctx: commands.Context, index: int=None, musique_name:str=None):
        """Supprimer une musique de tes titres likées."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if index is not None:
                max_index = await self.music_list_handler.get_next_index()
                if index >= max_index :
                    return await ctx.send(embed=create_embed(title="Remove-liked-song", description=f"Le N°`{index}` n'existe pas dans la MList."))
                song_name = await self.music_list_handler.getName(str(index))
            elif musique_name is not None:
                song_name = musique_name
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.fetchall("SELECT * FROM LikedSongs WHERE userId = ?", (str(ctx.author.id),))
                    if result:
                        if song_name in [i[2] for i in result]:
                            await conn.execute("DELETE FROM LikedSongs WHERE songName = ? AND userId = ?", (song_name, str(ctx.author.id),))
                            return await ctx.send(embed=create_embed(title="Remove-liked-song", description=f"La musique `{song_name}` a bien été enlevée de tes musiques likées."))
                        else:
                            return await ctx.send(embed=create_embed(title="Remove-liked-song", description=f"La musique `{song_name}` n'est pas dans tes musiques likées."))
            return await ctx.send(embed=create_embed(title="Remove-liked-song", description=f"La musique `{song_name}` n'est pas dans tes musiques likées."))
        except Exception as e:
            LogErrorInWebhook()
    @remove_liked_song.autocomplete("musique_name")
    async def autocomplete_musique_name(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.fetchall("SELECT * FROM LikedSongs WHERE userId = ?", (str(ctx.user.id),))
                    if result:
                        for i in result:
                            if musique_name.lower() in i[2].lower():
                                liste.append(app_commands.Choice(name=f"{i[2]}", value=str(i[2])))
                            if len(liste) == 25:
                                break
                    else:
                        return [app_commands.Choice(name="Aucune musique likée.", value="Aucune musique likée.")]
            return liste
        except Exception as e:
            LogErrorInWebhook()

# SoundBoard group
    @commands.hybrid_group(name="soundboard", aliases=["sb"], fallback='menu')            
    async def soundboard(self, ctx: commands.Context):
        """Affiche les sons de la soundboard."""
        return await handle_sb(ctx=ctx, bot=self.bot)

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

async def handle_sb(ctx: commands.Context, bot, userId: int=None):
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
            view = SoundBoardView(sounds=sounds, ctx=ctx, bot=bot, sb_manage=SoundBoardManage(pool=bot.pool))
            embed = create_embed(title="SoundBoard", description=f"Page 1/{len(sounds)}")
        else:
            embed = create_embed(title="SoundBoard", description=f"Aucun son ne semble avoir été téléchargé.")
            view = None
        if isinstance(ctx, discord.Interaction):
            return await ctx.followup.send(embed=embed, view=view, ephemeral=True)
        else: 
            return await ctx.send(embed=embed, view=view, ephemeral=True)
    except: LogErrorInWebhook()

async def setup(bot):
    await bot.add_cog(Music(bot))