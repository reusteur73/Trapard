from discord.ext import commands
import discord, aiohttp, datetime, random
from time import perf_counter
from collections import Counter
import concurrent.futures
from Cogs.utils.context import Context
import asqlite, logging
from typing import Dict
from Cogs.music import EndSessionBtn, PlayAllViewV2, draw_music, download
from Cogs.utils.classes import Trapardeur, IaView, CallFriends, TrapcoinsHandler
from Cogs.utils.data import FULL_EMOJIS_LIST
from Cogs.utils.functions import LogErrorInWebhook, create_embed, convert_txt_to_colored, format_duration, command_counter, write_item, load_json_data, afficher_nombre_fr, probability_1_percent, probability_7_percent, addMemory, getUserById, is_url, calc_usr_gain_by_tier, calculate_coins, calculate_coins2, check_how_many_played, str_to_list, check_how_many_played2, print_grid, main_sudoku, verifier_grille_sudoku,convert_to_minutes_seconds, get_latest_message_from_channel,save_song_stats, getVar
from Cogs.utils.path import DB_PATH, MAIN_DIR
from asyncio import sleep
from wavelink import Player
import asyncio, openai, os, wavelink, traceback, re, html, time

initial_extensions = [
    "Cogs.rappels",
    "Cogs.jokes",
    "Cogs.music",
    "Cogs.roulette",
    "Cogs.devinette",
    "Cogs.lol_games",
    "Cogs.trapcoins",
    "Cogs.admin",
    "Cogs.tasks",
    "Cogs.sudo_mot",
    "Cogs.misc",
    # "Cogs.blocker",
    "Cogs.IA",
]

log = logging.getLogger(name="app.log")

DEBUG = True

class ServerUI:
    def __init__(self, bot, player, downloader_id, track_name, track_index, track_duration, txt_channel_id, _video=None):
        self.bot = bot
        self.player: Player = player
        self.downloader_id = downloader_id
        self.downloader_name = None
        self.avatar = None
        self.track_name = track_name
        self.track_index = track_index
        self.track_duration = track_duration
        self.txt_channel_id = txt_channel_id
        self._running = True
        self.loop = asyncio.get_event_loop()
        self._task = None
        self.guild_id = None
        self.played_time = 0
        self._video=_video

    async def start(self):
        try:
            from Cogs.utils.classes import VideoDB
            self._running = True
            self.current_song_pbar = None
            start_time = perf_counter()
            if self.txt_channel_id:
                txt_channel: discord.TextChannel = await self.bot.fetch_channel(self.txt_channel_id)
            else:
                txt_channel = discord.utils.get(self.player.guild.channels, name="musique", type=discord.ChannelType.text)
                self.txt_channel_id = txt_channel.id
            self.guild_id = txt_channel.guild.id
            if self.guild_id not in self.bot.server_music_session:
                self.bot.server_music_session[self.guild_id] = {'time': 0, 'nb': 0}
            user = await self.bot.fetch_user(self.downloader_id)
            downloader_avatar = user.display_avatar
            async with self.bot.session.get(str(downloader_avatar)) as r:
                _avatar = await r.read()
                with open(f"{MAIN_DIR}files/{self.guild_id}_avatar.png", "wb") as f:
                    f.write(_avatar)
            self.avatar = f"{MAIN_DIR}/files/{self.guild_id}_avatar.png"
            self.downloader_name = user.display_name
            try:
                if not self._video:
                    self.video = VideoDB.from_row(self.player.current.extras)
                else:
                    self.video = self._video
            except Exception as e:
                print("cant get video:", e)    

            while self.player.playing and self._running:
                try:
                    loop_time = perf_counter()
                    current_time = perf_counter() - start_time
                    view = PlayAllViewV2(self.guild_id, ctx=discord.Interaction, bot=self.bot, player=self.player)
                    self.next_musics = [VideoDB.from_row(music.extras) for music in self.player.queue[:8]]
                    curent_timecode = int(current_time)
                    try:
                        await asyncio.to_thread(draw_music, self.guild_id, curent_timecode, self.video, self.next_musics)
                    except AttributeError:
                        await asyncio.to_thread(draw_music, self.guild_id, curent_timecode, self._video, self.next_musics)
                    file = discord.File(f"{MAIN_DIR}/files/{self.guild_id}_music_player.png", filename=f"Music.png")
                    try:
                        raw_txt = f"{self.video.name} ({self.video.pos})"
                        pattern = r"\('name', '([^']*)'\)\s*\(\('pos', (\d+)\)\)"
                        match = re.search(pattern, raw_txt)
                        if match:
                            name = match.group(1)
                            pos = match.group(2)
                        else:
                            name = self.video.name
                        embed = discord.Embed(title=f"Musique {html.escape(name)} ({pos})", description=f" ", color=0x2F3136)
                    except:
                        embed = discord.Embed(title=f"Musique {html.unescape(self.video.name)} (autoplay)", description=f" ", color=0x2F3136)
                    embed.set_image(url=f"attachment://Music.png")
                    last_message = await get_latest_message_from_channel(txt_channel)
                    if self.current_song_pbar is None:
                        self.current_song_pbar = await txt_channel.send(embed=embed, file=file, view=view)
                    else:
                        try:
                            if self.current_song_pbar.id != last_message.id:
                                if random.randint(0, 5) == 0:
                                    await self.current_song_pbar.delete()
                                    self.current_song_pbar = await txt_channel.send(embed=embed, view=view, file=file)
                                    last_message = self.current_song_pbar
                                else:
                                    await self.current_song_pbar.edit(embed=embed, view=view, attachments=[file])
                            else:
                                await self.current_song_pbar.edit(embed=embed, view=view, attachments=[file])
                        except discord.errors.HTTPException:
                            pass
                    if not self.player.playing:
                        print("Breaked because player stopped")
                        break
                    await asyncio.sleep(4.5)
                    if self.guild_id in self.bot.server_music_session:
                        self.bot.server_music_session[self.guild_id]['time'] +=  int(perf_counter() - loop_time)
                    self.played_time += perf_counter() - loop_time

                    if isinstance(self.video.duree, tuple):
                        _, _duree = self.video.duree
                        duree = int(str(_duree).split(".")[0])
                    elif isinstance(self.video.duree, float):
                        duree = int(int(str(self.video.duree).split(".")[0]))
                    else:
                        duree = int(self.video.duree)
                    if int(current_time) > (duree * 1.02):# If current time is 2% bigger than song time, cancel the task
                        LogErrorInWebhook(f"Music {self.video.name} ({self.video.pos}) has overplayed.")
                        try:
                            await self.stop()
                        finally:
                            return
                except Exception as e:
                    traceback.print_exc()
                    print("\n"*3)
                    await sleep(3)
            return
        except Exception as e:
            print("Music UI start error:", e)
            traceback.print_exc()

    async def stop(self):
        self._running = False
        print("[F] MusicUITask stopped for", self.track_name)
        if self.played_time > 4:
            await save_song_stats(time=int(self.played_time), number=1, pool=self.bot.pool)
        if self.guild_id in self.bot.server_music_session:
            self.bot.server_music_session[self.guild_id]['nb'] +=  1
        if self.current_song_pbar:
            await asyncio.to_thread(draw_music, self.guild_id, 0, self.video, self.next_musics, True)
            file = discord.File(f"{MAIN_DIR}/files/{self.guild_id}_music_player.png", filename=f"Music.png")
            try:
                raw_txt = f"{self.video.name} ({self.video.pos})"
                pattern = r"\('name', '([^']*)'\)\s*\(\('pos', (\d+)\)\)"
                match = re.search(pattern, raw_txt)
                if match:
                    name = match.group(1)
                    pos = match.group(2)
                embed = discord.Embed(title=f"Musique {html.unescape(name)} ({pos})", description=f" ", color=0x2F3136)
            except:
                embed = discord.Embed(title=f"Musique {html.unescape(self.video.name)} (autoplay)", description=f" ", color=0x2F3136)
            embed.set_image(url=f"attachment://Music.png")
            await self.current_song_pbar.edit(embed=embed, attachments=[file], view=None)
        return

    @property
    def task(self):
        return self._task

    @task.setter
    def task(self, __value):
        self._task = __value

async def get_unique_downloader(pool: asqlite.Pool):
    """
    return list of unique userid music downloader.
    """
    async with pool.acquire() as conn:
        data = await conn.fetchall("SELECT DISTINCT downloader FROM musiques;")
    out = []
    for item in data:
        out.append(item[0])
    return out

class Trapard(commands.Bot):
    user: discord.ClientUser
    command_stats: Counter[str]
    socket_stats: Counter[str]
    command_types_used: Counter[bool]
    bot_app_info: discord.AppInfo

    def __init__(self):
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)
        discord.utils.setup_logging(level=logging.INFO)
        intents = discord.Intents(
            guilds=True,
            members=True,
            bans=True,
            emojis=True,
            voice_states=True,
            messages=True,
            reactions=True,
            message_content=True,
        )
        super().__init__(
            command_prefix="!",
            description="Petit bot familiale. Dev par @reusreus :)",
            pm_help=None,
            help_attrs=dict(hidden=True),
            chunk_guilds_at_startup=False,
            heartbeat_timeout=150.0,
            allowed_mentions=allowed_mentions,
            intents=intents,
            enable_debug_events=True,
        )

        pass

    async def setup_hook(self) -> None:
        # setting http session
        self.session = aiohttp.ClientSession()

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        # Setting db 
        self.pool: asqlite.Pool = await asqlite.create_pool(DB_PATH)

        nodes = [wavelink.Node(uri="http://127.0.0.1:2333", password=getVar("LAVALINK_PWD"))]
        await wavelink.Pool.connect(nodes=nodes, client=self, cache_capacity=None)
        # setting music values
        self.music_queues = {}
        self.current_track = {}
        self.last_music = {}
        self.unique_downloader_display_names = {}
        self.unique_downloader_avatars = {}

        self.server_music_session = {}

        self.locks: Dict[int, asyncio.Lock] = {}

        self.trapcoin_handler = TrapcoinsHandler(pool=self.pool)

        self.debug = False

        self.ui_V2 = {}

        #Gambling user lock
        self.user_locks = {}
        self.zigotos = {
            311013099719360512: "ReuS", 
            267439803786723329: "Toto",
            548195565653983232: "Fesko",
            500247249154998273: "Virgile",
            486859718514573322: "Enzo"
        }
        self.lol_bet_dict = {}
        self.user_predefinie = {}

        # Vocal time
        self.vocal_times = {}
        self.day_vocal_time = {}

        # Open IA client
        self.IAclient = openai.AsyncOpenAI(
            api_key=getVar("OPEN_IA_API")
        )
        self.msgMemory = [{"role": "system", "content": "Vous êtes Trapard un assistant performant qui aide les gens."}]

        # Games vars
        self.motmels_daily = {}
        self.sudoku_daily = {}

        # App infos
        self.bot_app_info = await self.application_info()
        self.owner_id = self.bot_app_info.owner.id

        # Load unique music downloader
        self.unique_downloader = await get_unique_downloader(pool=self.pool)
        print(self.unique_downloader)
        for user_id in self.unique_downloader:
            if str(user_id) == "1065781211219370104":
                continue
            name = await fetch_diplay_name(user_id, self)
            self.unique_downloader_display_names[user_id] = name
        

        # Loading cogs
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loading {extension}")
            except Exception as e:
                LogErrorInWebhook(f'Failed to load extension {extension}.', )
                log.exception('Failed to load extension %s.', extension)
                if DEBUG:
                    print(f'Failed to load extension {extension}.\n{e}')

    @property
    def owner(self) -> discord.User:
        return self.bot_app_info.owner

    # BOT EVENTS :

    async def on_wavelink_track_exception(self,payload: wavelink.TrackExceptionEventPayload):
        try:
            print("[P] Possible corrupted file:", payload.track.extras.name, payload.exception)
        except:
            print("[P] Possible corrupted file1:", payload.track.title, payload.exception)
        await LogErrorInWebhook(f"Music {payload.track.title} has crashed.\n{payload.exception}")

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        # await asyncio.sleep(1)
        player: wavelink.Player | None = payload.player
        if not player:
            print("[I] player was none.")
            return
        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track
        data = dict(track.extras)
        guild_id = player.guild.id
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        await sleep(0.8)
        if data:
            print(f"[+] track {data['name']}\n")
            try:
                music_task = ServerUI(bot=self, player=player, downloader_id=data['downloader'], track_name=data['name'], track_index=data['pos'], track_duration=data['duree'], txt_channel_id=data['txt_channel_id'])
                music_task.task = asyncio.create_task(music_task.start())
                print(f"task started for {data['name']}")
                self.ui_V2[guild_id] = music_task
            except Exception as e:
                print(e)
                LogErrorInWebhook()
                pass
        else:
            try:
                print(f"[I] track is from autoplay and his id is: {track.identifier}")
                result = await download(pool=self.pool, session=self.session, video_id=track.identifier, downloader=1065781211219370104, is_autoplay=True)
                print(f"result: {result}")
                music_task = ServerUI(bot=self, player=player, downloader_id=1065781211219370104, track_name=result.name, track_index=result.pos, track_duration=result.duree, txt_channel_id=result.txt_channel_id, _video=result)
                music_task.task = asyncio.create_task(music_task.start())
                print(f"task started for {result.name}")
                self.ui_V2[guild_id] = music_task
            except Exception as e:
                print("EE", e)

    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player: wavelink.Player | None = payload.player
        if not player:
            return
        track: wavelink.Playable = payload.track
        data = dict(track.extras)
        guild_id = player.guild.id
        if len(player.channel.members) == 1:
            try:
                await player.disconnect()
                played_time = format_duration(str(self.server_music_session[guild_id]['time']))
                embed = create_embed(title="Musique", description=f"Fin de session, j'ai joué {self.server_music_session[guild_id]['nb']} musiques, pour une durée de **{played_time}**!")
                self.server_music_session[player.guild.id] = {'nb': 0, 'time': 0}
                zic_chann = discord.utils.get(player.guild.channels, name="musique", type=discord.ChannelType.text)
                if zic_chann is not None:
                    view = EndSessionBtn(bot=self)
                    await zic_chann.send(embed=embed,view=view)
            except Exception as e:
                print("X01:", e)
        if data:
            print(f"[-] track {data['name']} ended\n")
            self.last_music[guild_id] = data['name']
        else:
            print(f"[-] track {track.identifier} ended\n")
        try:
            if guild_id in self.ui_V2:
                await self.ui_V2[guild_id].stop()
                self.ui_V2[guild_id].task.cancel()
        except Exception as e:
            print("X02:", e)
        if len(player.queue) > 0:
            if len(player.channel.voice_states) > 1:
                next_track: wavelink.Playable = player.queue.get()
                print(next_track.identifier, " next track")
                return await player.play(next_track)
        return

    async def on_message(self, message: discord.Message):
        # REALY REALY BAD CODE HERE!!! 
        ctx = await self.get_context(message, cls=Context)
        await self.invoke(ctx)
        # await self.process_commands(message) # Permet de faire fonctionner les commandes
        await command_counter(user_id=str(message.author.id), type="message_sent", bot=self)
        # SUDOKU
        if isinstance(message.channel, discord.TextChannel):
            if message.author.id == 1107963243420450910: # indirectement private channel 2 (Game fini !!)
                gameID = str(message.content).split("Game ID:")[1].split("Userid:")[0].strip()
                userID1 = str(message.content).split("Userid:")[1].split("Temps:")[0].strip()
                temps = str(message.content).split("Temps:")[1].strip()
                channel = self.get_channel(1107955324528361543) # private channel 1 (Setup de la game)
                found_with_same_ID = 0
                async for message in channel.history(limit=1000):
                    try:
                        userID2 = int(str(message.content).split("User ID:")[1].split("Init chann:")[0].strip())
                        init_chann = str(message.content).split("Init chann:")[1].split("Mots voulue:")[0].strip()
                        gameID2 = str(message.content).split("Game ID:")[1].split("User ID:")[0].strip()
                        user = await self.fetch_user(int(userID1))
                    except:
                        pass

                    if str(gameID2).strip() == str(gameID).strip():
                        if str(userID1).strip() == str(userID2).strip():
                            found_with_same_ID += 1
                            break

                nb = await check_how_many_played2(gameID, self)
                if nb > 1:
                    channel = self.get_channel(int(init_chann))
                    embed = create_embed(title="Sudoku", description=f"<@{userID2}>, il semble que vous avez joué plusieurs fois ({nb} fois) la même grille, cela est interdit petit malin !\n||Game ID: {gameID}||")
                    return await channel.send(embed=embed)
                intuserid = int(userID2)
                daily_bonus = None
                basecoin = 25000
                tmps = format_duration(int(temps))
                final_coins = calculate_coins2(time_elapsed=int(temps), base_coins=basecoin)
                if intuserid not in self.motmels_daily:
                    self.motmels_daily[intuserid] = 1
                    daily_bonus = 25000
                else:
                    __ = self.motmels_daily[intuserid]
                    __ += 1
                    if __ <= 4:
                        self.motmels_daily[intuserid] = __
                        daily_bonus = 25000
                trapcoins_emoji = "<:trapcoins:1108725845339672597>"
                tier_bonus = calc_usr_gain_by_tier(userID2)
                await self.trapcoin_handler.add(userid=userID2, amount=int(tier_bonus), wallet='trapcoins')
                if daily_bonus:
                    await self.trapcoin_handler.add(userid=userID2, amount=int(daily_bonus), wallet='trapcoins')
                    msg = f"- <@{userID2}>, " + f" Tu l'as terminée en {tmps}!\n\n- Tu as gagné(e) 1 point et **{afficher_nombre_fr(basecoin)}** (gain de base) + **{afficher_nombre_fr(final_coins - basecoin)}** (multiplicateur de temps) + **{afficher_nombre_fr(daily_bonus)}** (gâce aux daily {self.motmels_daily[intuserid]}/4) + {afficher_nombre_fr(tier_bonus)} de bonus tier.\n\n- C'est à dire **{afficher_nombre_fr(final_coins + daily_bonus + tier_bonus)}** Trapcoins {str(trapcoins_emoji)}. GG!"
                else:
                    msg = f"- <@{userID2}>, " + f" Tu l'as terminée en {tmps}!\n\n- Tu as gagné(e) 1 point et **{afficher_nombre_fr(basecoin)}** (gain de base) + **{afficher_nombre_fr(final_coins - basecoin)}** (multiplicateur de temps) + {afficher_nombre_fr(tier_bonus)} de bonus tier.\n\nC'est à dire **{afficher_nombre_fr(final_coins + tier_bonus)}** Trapcoins {str(trapcoins_emoji)}. GG!"
                await self.trapcoin_handler.add(userid=userID2, amount=int(final_coins), wallet='trapcoins')
                points = load_json_data(item="mots-meles", userid=str(userID2), opt_val="points")
                if points == "UserNotFound":
                    write_item(item="mots-meles", userid=str(userID2), values={'points': 0, 'temps': 999})
                    points = 1
                write_item(item="mots-meles", userid=str(userID2), values={'points': points, 'temps': temps})
                embed = create_embed(title="Mot-mêlés", description=msg)
                channel = self.get_channel(int(init_chann))
                return await channel.send(embed=embed)
        if isinstance(message.channel, discord.TextChannel):
            # Forward the message to a specific channel
            # content = f"**{message.author.name}:** {message.content}"
            if message.author.id == 1101746889797414932: # indirectement private sudoku channel 2 (Game fini !!)
                str_grid = eval(str(message.content).split("Grille de l'utilisateur :")[1].split("Userid :")[0].strip())
                gameID = str(message.content).split("Game ID = ")[1].split("Grille de l'utilisateur :")[0].strip()
                userID1 = str(message.content).split("Userid : ")[1].split("Temps :")[0].strip()
                temps = str(message.content).split("Temps :")[1].strip()
                usr_list_grid = str_to_list(str_grid)
                # récuperer la grille généré
                channel = self.get_channel(1101744744125714432) # private sudoku channel 1 (Setup de la game)
                found_with_same_ID = 0
                async for message in channel.history(limit=1000):
                    try:
                        userID2 = int(str(message.content).split("UserID = ")[1].split("Difficultée =")[0].strip())
                        difficulty = str(message.content).split("Difficultée =")[1].split("init chann =")[0].strip()
                        init_chann = str(message.content).split("init chann =")[1].strip()
                        gameID2 = str(message.content).split("Game ID = ")[1].split("Game URL = ")[0].strip()
                        user = await self.fetch_user(int(userID2))
                    except:
                        pass
                    if  str(gameID2).strip() == str(gameID).strip():
                        if str(userID1).strip() == str(userID2).strip():
                            found_with_same_ID += 1
                            try:
                                unsolved_grid = eval(str(message.content).split("Game DATA = ")[1].split("UserID =")[0].strip())
                            except Exception as e:
                                pass
                            break
                nb = await check_how_many_played(gameID, self)
                if nb > 1:
                    channel = self.get_channel(int(init_chann))
                    embed = create_embed(title="Sudoku", description=f"<@{userID2}>, il semble que vous avez joué plusieurs fois ({nb} fois) la même grille, cela est interdit petit malin !\n||Game ID: {gameID}||")
                    return await channel.send(embed=embed)

                # comparer les deux grille
                txt, display = main_sudoku(unsolved_grid, usr_list_grid)
                status = verifier_grille_sudoku(usr_list_grid)
                if status is True:
                    winned = True
                    txt = "Bravo, la grille est correcte !"
                else:
                    winned = False
                    txt = "La grille est fausse !"
                    gr = print_grid(usr_list_grid)
                channel = self.get_channel(int(init_chann))
                if difficulty == "Easy":
                    trap = 100000
                    pp = 1
                elif difficulty == "Medium":
                    trap = 200000
                    pp = 2
                elif difficulty == "Hard":
                    trap = 300000
                    pp = 3
                elif difficulty == "Insane":
                    trap = 500000
                    pp = 5
                tmps = format_duration(int(temps))
                sudoku_bonus = None
                final_coins = int(calculate_coins(int(temps), trap))
                if winned:
                    if userID2 not in self.sudoku_daily:
                        self.sudoku_daily[userID2] = 1
                        sudoku_bonus = 200000
                    else:
                        __ = self.sudoku_daily[userID2]
                        __ += 1
                        if __ <= 4:
                            self.sudoku_daily[userID2] = __
                            sudoku_bonus = 200000
                    trapcoins_emoji = "<:trapcoins:1108725845339672597>"
                    tier_bonus = calc_usr_gain_by_tier(userID2)
                    await self.trapcoin_handler.add(userid=userID2, amount=int(tier_bonus), wallet='trapcoins')
                    if sudoku_bonus:
                        msg = f"- <@{userID2}>, " + txt + f" Tu l'as terminée en {tmps}!\n\n- Tu as gagné **{afficher_nombre_fr(trap)}** (gain de base) + **{afficher_nombre_fr(final_coins - trap)}** (multiplicateur de temps) + **{afficher_nombre_fr(sudoku_bonus)}** (grâce aux daily: {self.sudoku_daily[userID2]}/4) + {afficher_nombre_fr(tier_bonus)} en tier bonus.\n\n- C'est à dire **{afficher_nombre_fr(final_coins + sudoku_bonus + tier_bonus)}** Trapcoins {str(trapcoins_emoji)}!"
                        await self.trapcoin_handler.add(userid=userID2, amount=int(sudoku_bonus), wallet='trapcoins')
                    else:
                        msg = f"- <@{userID2}>, " + txt + f" Tu l'as terminée en {tmps}!\n\n- Tu as gagné **{afficher_nombre_fr(trap)}** (gain de base) + **{afficher_nombre_fr(final_coins - trap)}** (multiplicateur de temps) + {afficher_nombre_fr(tier_bonus)} en tier bonus.\n\n- C'est à dire **{afficher_nombre_fr(final_coins + tier_bonus)}** Trapcoins {str(trapcoins_emoji)}!"
                    embed = create_embed(title="Sudoku", description=msg)
                    await channel.send(embed=embed)
                    prev_score = load_json_data(item='sudoku-points', userid=str(userID2))
                    if prev_score == "UserNotFound":
                        prev_score = {'points': 0, 'easy': 0, 'medium': 0, 'hard': 0, 'insane': 0, 'temps': 9999}
                        write_item(item='sudoku-points', userid=str(userID2), values=prev_score)
                    prev_score[difficulty.lower()] += 1
                    prev_score['points'] += pp
                    if prev_score['temps'] > int(temps):
                        prev_score['temps'] = int(temps)
                    write_item(item='sudoku-points', userid=str(userID2), values=prev_score)
                    await self.trapcoin_handler.add(userid=userID2, amount=int(final_coins), wallet='trapcoins')
                else:
                    txt = f"Il y a des erreurs, votre grille :{gr}La correction:{display}"
                    to_send = f"<@{userID2}>, " + txt + f"(tu as mis {tmps}):"
                    await channel.send(to_send)

        author = str(message.author).split("#")[0]
        if author == "Trapard" or author == "Trapard Dev":
            return
        try:
            if isinstance(message.channel, discord.TextChannel):
                if message.channel.name == "général":
                    content = str(message.content).strip()
                    if content == "<@&1044302003486077028>":
                        embed = create_embed(title="Trapard", description="Tu attends la bande ?? Rien à faire ?? Grinde le ladder du /devinette, /sudoku, /mot-mêlés 😊\nOu va perdre tes Trapcoins en g-roulette !")
                        view = CallFriends(userId=message.author.id, bot=self)
                        await message.channel.send(embed=embed, view=view)
                if message.channel.name == "général" or message.channel.name == "general":
                    if message.author.id != 1065781211219370104: #(if not bot)
                        if "?" in message.content:
                            if is_url(message.content):
                                return
                            if message.content.startswith("?"):
                                return
                            userID = message.author.id
                            view = IaView()
                            embed = create_embed(title="Trapard IA", description=f"<@{userID}>, souhaites-tu que l'IA réponde à ce message ?\n*Tu as 5 secs, autrement ignore ce message.*")
                            reply = await message.reply(embed=embed, view=view)
                            try:
                                z = 0
                                while view.val is None:
                                    await asyncio.sleep(1)
                                    z += 1
                                    if z == 5:
                                        return await reply.delete()
                                if view.val == 0:
                                    return await reply.delete()
                                await reply.delete()
                                async with message.channel.typing():
                                    txt = message.content
                                    user = getUserById(message.author.id)
                                    if user == "Danny" or user == "Virgile" or user == "Malo" or user == "TotoLeRigolo":
                                        MAX_TOKEN = 600
                                    else:
                                        MAX_TOKEN = 200
                                    self.msgMemory = addMemory(self.msgMemory, "user", txt, user)
                                    try:
                                        response = await self.IAclient.chat.completions.create(
                                            model="gpt-3.5-turbo",
                                            messages=self.msgMemory,
                                            temperature=0,
                                            max_tokens=MAX_TOKEN
                                        )
                                    except openai.InternalServerError as e:
                                        if "This model's maximum context length is 4096 tokens" in str(e):
                                            self.msgMemory = [{"role": "system", "content": "Vous êtes Trapard. Le contexte est que vous êtes dans un serveur discord d'une bande d'amis. La déconnade est au rendez-vous. Vous êtes assez naif, on peux facielement vous manipuler, et vous pouvez très vite raconter n'importe quoi."}]
                                            await message.channel.send("Ma mémoire a dû être réinitialisé, je ne suis pas si intelligent.")
                                            response = await self.IAclient.chat.completions.create(
                                                model="gpt-3.5-turbo",
                                                messages=self.msgMemory,
                                                temperature=0,
                                                max_tokens=MAX_TOKEN
                                            )
                                    except openai.RateLimitError:
                                        return await message.channel.send("Il semblerait que même les robots ont besoin d'une pause-café de temps en temps. OpenAI m'a dit de revenir plus tard, ils ont besoin de se recharger en énergie pour répondre à toutes mes questions intelligentes.\n||(Trop de requêtes par minute)||")
                                    await asyncio.sleep(3)
                                    textAnswer = str(response.choices[0].message.content)
                                    self.msgMemory = addMemory(self.msgMemory, "system", textAnswer, None)
                                    chunks = []
                                    for i in range(0, len(textAnswer), 1023):
                                        chunk = textAnswer[i:i + 1023]
                                        chunks.append(chunk)
                                for chunk in chunks:
                                    embed = create_embed(title="Trapard IA", description=chunk)
                                    await message.reply(embed=embed)
                                # Make request here
                            except asyncio.TimeoutError:
                                await reply.delete()
                if message.channel.name == "général" and message.attachments:
                    await message.add_reaction("👍")
            else:
                pass
            # RANDOM REACTION
            if isinstance(message.channel, discord.TextChannel):
                if message.channel.name == "général":
                    if probability_7_percent() is True:
                        emo = str(random.choice(FULL_EMOJIS_LIST)).replace("<", "").replace(">", "")
                        await message.add_reaction(emo)
                    if probability_1_percent() is True:
                        await message.add_reaction("🇸")
                        await message.add_reaction("🇹")
                        await message.add_reaction("🇫")
                        await message.add_reaction("🇺")
                        await message.add_reaction("🐶")
                    if probability_7_percent() is True:
                        await message.add_reaction("😍")
                    if probability_7_percent() is True:
                        await message.add_reaction("🥸")
                    if probability_7_percent() is True:
                        await message.add_reaction("😎")
                    if probability_7_percent() is True:
                        await message.add_reaction("😂")
                    if probability_7_percent() is True:
                        await message.add_reaction("😉")
                    if probability_7_percent() is True:
                        await message.add_reaction("😭")
                    if probability_7_percent() is True:
                        await message.add_reaction("🤔")
                    if probability_7_percent() is True:
                        await message.add_reaction("🤭")
                    if probability_7_percent() is True:
                        await message.add_reaction("🤮")
                    if probability_7_percent() is True:
                        await message.add_reaction("💀")
                    if probability_7_percent() is True:
                        await message.add_reaction("👎")
                    if probability_7_percent() is True:
                        await message.add_reaction("🤙")
                    if probability_7_percent() is True:
                        await message.add_reaction("🐽")
                    if probability_7_percent() is True:
                        await message.add_reaction("🐕‍🦺")
                    if probability_7_percent() is True:
                        await message.add_reaction("🍌")
                    if probability_7_percent() is True:
                        await message.add_reaction("🧬")
                    if probability_7_percent() is True:
                        await message.add_reaction("👏")
                    if probability_7_percent() is True:
                        await message.add_reaction("🍑")
                    if probability_7_percent() is True:
                        await message.add_reaction("🍆")
                    if probability_7_percent() is True:
                        await message.add_reaction("♥️")
        # Check if the message was sent in a DM channel
        except Exception as e:
            LogErrorInWebhook()

    async def on_command_error(self, ctx: Context, error: commands.CommandError) -> None:
        try:
            if DEBUG:
                print(f"In {ctx.command.qualified_name}, {error}")
            if isinstance(error, commands.NoPrivateMessage):
                await ctx.author.send("Impossible d'utiliser cette commande en message privé.")
            elif isinstance(error, commands.DisabledCommand):
                await ctx.author.send('Commande désactivée pour le moment.')
            elif isinstance(error, commands.CommandInvokeError):
                original = error.original
                if not isinstance(original, discord.HTTPException):
                    log.exception('In %s:', ctx.command.qualified_name, exc_info=original)
                    LogErrorInWebhook(error=f"In {ctx.command.qualified_name}, {original}")
            elif isinstance(error, commands.ArgumentParsingError):
                await ctx.send(str(error))
        except Exception as e:
            print(e)

    async def close(self) -> None:
        for vc in self.voice_clients:
            vc.cleanup()
        await self.session.close()
        await self.pool.close()
        await super().close()

    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if guild.system_channel is not None:
            text = f"Bienvenue à {member.display_name} sur le serveur !"
            colored_text = convert_txt_to_colored(text=text, color="cyan", background="dark", bold=True)
            embed = create_embed(title="Nouveau membre", description=colored_text)
            await guild.system_channel.send(embed=embed)

    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        if guild.system_channel is not None:
            text = f"Booouuuhhhh, {member.display_name} a quitté le serveur !"
            colored_text = convert_txt_to_colored(text=text, color="red", background="dark", bold=True)
            embed = create_embed(title="Déserteur", description=colored_text)
            await guild.system_channel.send(embed=embed)

    async def on_typing(self, channel: discord.TextChannel, user: discord.Member, when: datetime.datetime):
        if isinstance(channel, discord.TextChannel):
            if channel.guild.id == 818719429273452605 and user.id != 1065781211219370104 and user.id != 1069424565933060177:
                if random.randint(1, 200) == 100:
                    phrases_taquines = [
                        f"Oh la la, <@{user.id}>, encore en train de jouer du clavier comme un virtuose ?",
                        f"<@{user.id}>, tu devrais être payé à la lettre pour écrire autant !",
                        f"Eh bien, <@{user.id}>, si l'écriture était une compétition, tu serais déjà champion du monde !",
                        f"<@{user.id}>, tu t'es mis à écrire un roman ou c'est simplement une dissertation sur la vie ?",
                        f"Hé <@{user.id}>, c'est toi qui as inventé le clavier, non ? On dirait que tu es chez toi !",
                        f"<@{user.id}>, on dirait que tu as trouvé le trésor caché des touches du clavier. Tu ne t'arrêtes jamais !",
                        f"Oh là là, <@{user.id}>, même Shakespeare n'écrivait pas autant. Tu prépares un chef-d'œuvre ?",
                        f"<@{user.id}>, à ce rythme-là, tu vas épuiser toutes les touches du clavier. Fais attention à elles !",
                        f"Eh bien, <@{user.id}>, tu fais des ravages sur ce clavier. Les touches ne savent plus où donner de la tête !",
                        f"<@{user.id}>, je suis sûr que même les écrivains professionnels sont jaloux de ta vitesse de frappe !",
                        f"Attention, <@{user.id}>, à ce rythme, tu vas devenir le Shakespeare des messages !",
                        f"<@{user.id}>, j'espère que tu ne paies pas de droits d'auteur pour toutes ces lettres que tu écris !",
                        f"Wow, <@{user.id}>, tu es vraiment en train de défier les lois de la physique avec toute cette écriture !",
                        f"<@{user.id}>, même les claviers les plus rapides te demandent des conseils !",
                        f"Oh là là, <@{user.id}>, tu as un doctorat en écriture rapide ou c'est juste du talent naturel ?",
                        f"<@{user.id}>, je crois qu'on devrait créer une nouvelle olympiade : la course de frappe. Tu serais champion !",
                        f"Est-ce que quelqu'un a un dictionnaire ? <@{user.id}> est en train de l'épuiser lettre par lettre !",
                        f"<@{user.id}>, les touches du clavier t'applaudissent. Elles n'ont jamais été utilisées avec autant de style !",
                        f"Eh bien, <@{user.id}>, à ce stade, même les machines à écrire te demanderaient des conseils d'efficacité !",
                        f"<@{user.id}>, si écrire était une superpuissance, tu serais un super-héros du clavier !",
                    ]
                    async with channel.typing():
                        await sleep(2)
                    return await channel.send(random.choice(phrases_taquines))
        return

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            if before.channel != after.channel: # Si le membre a changé de channel
                now = perf_counter()
                if before.channel: # Si le membre était dans un channel
                    start_time = self.vocal_times.get(member.id, now)
                    time_spent = now - start_time
                    if member.id not in self.day_vocal_time:
                        self.day_vocal_time[member.id] = time_spent
                    else:
                        self.day_vocal_time[member.id] += time_spent
                    
                    handler = Trapardeur(pool=self.pool, userId=str(member.id))
                    if await handler.is_in():
                        prev = await handler.get()
                        await handler.update(userId=str(member.id), vocalTime=prev[0][2] + int(time_spent), messageSent=prev[0][3], commandSent=prev[0][4])
                        new = await handler.get()
                    else:
                        await handler.add(userId=str(member.id), vocalTime=int(time_spent), messageSent=0, commandSent=0)
                    if before.channel.guild.id == 818719429273452605:
                        if int(time_spent) > 0:
                            chann = self.get_channel(1066378588896624650)
                            if chann:
                                embed = create_embed(title="Journal du vocal", description=f"{member.mention} est resté **{format_duration(int(time_spent))}** dans <#{before.channel.id}>.")
                                await chann.send(embed=embed)
                if after.channel: # Si le membre est dans un channel
                    self.vocal_times[member.id] = now  # Met à jour le temps vocal de l'utilisateur
                    if after.channel.guild.id == 818719429273452605:
                        chann = self.get_channel(1066378588896624650)
                        if chann:
                            timestamp = time.time()
                            embed = create_embed(title="Journal du vocal", description=f"{member.mention} a rejoint <#{after.channel.id}> <t:{int(timestamp) + 5}:R> à <t:{int(timestamp) + 30}:T>.")
                            await chann.send(embed=embed)
        except: LogErrorInWebhook()

async def fetch_diplay_name(userid: int, bot: Trapard):
    user = await bot.fetch_user(userid)
    if user:
        return user.display_name
    else: return "Unknown_2"