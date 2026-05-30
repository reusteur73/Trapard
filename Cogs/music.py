from typing import Literal, List, Tuple, cast, Optional
from discord.ext import commands #type: ignore
from .utils.classes import VideoDB
from youtube_search import YoutubeSearch # type: ignore
from discord import app_commands, ui, Interaction #type: ignore
from pytube import YouTube # type: ignore
from .utils.functions import LogErrorInWebhook, command_counter, create_embed, convert_str_to_emojis, printFormat, convert_int_to_emojis, is_url, convert_to_minutes_seconds, rename, getMList, display_big_nums, get_next_index, getVar, parse_name_tuple, save_song_stats, format_duration, get_latest_message_from_channel, iso_to_eslapsed_time
from .utils.path import PLAYLIST_LIST, MUSICS_FOLDER, SOUNDBOARD, MLIST_FOLDER, MAIN_DIR
from .utils.context import Context as CustomContext
import traceback, random, os, asyncio, threading, base64, io, discord, lavalink, isodate , html, datetime, re, ast # type: ignore
from asqlite import Pool #type: ignore
from PIL import Image, ImageDraw, ImageFont
from aiohttp import ClientSession #type: ignore
from asyncio import sleep

music_table = "musiquesV3"

class LavalinkVoiceClient(discord.VoiceProtocol):
    """
    This is the preferred way to handle external voice sending
    This client will be created via a cls in the connect method of the channel
    see the following documentation:
    https://discordpy.readthedocs.io/en/latest/api.html#voiceprotocol
    """

    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        if not hasattr(self.client, 'lavalink'):
            # Instantiate a client if one doesn't exist.
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(
                host='127.0.0.1',
                port=2333,
                password=getVar("LAVALINK_PWD"),
                region='us',
                name='default-node'
            )

        # Create a shortcut to the Lavalink client here.
        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
            't': 'VOICE_SERVER_UPDATE',
            'd': data
        }
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        channel_id = data['channel_id']

        if not channel_id:
            await self._destroy()
            return

        self.channel = self.client.get_channel(int(channel_id))

        # the data needs to be transformed before being handed down to
        # voice_update_handler
        lavalink_data = {
            't': 'VOICE_STATE_UPDATE',
            'd': data
        }

        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = False, self_mute: bool = False) -> None:
        """
        Connect the bot to the voice channel and create a player_manager
        if it doesn't exist yet.
        """
        # ensure there is a player_manager when creating a new voice_client
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Handles the disconnect.
        Cleans up running player and leaves the voice client.
        """
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        # no need to disconnect if we are not connected
        if not force and not player.is_connected:
            return

        # None means disconnect
        await self.channel.guild.change_voice_state(channel=None)

        # update the channel_id of the player to None
        # this must be done because the on_voice_state_update that would set channel_id
        # to None doesn't get dispatched after the disconnect
        player.channel_id = None
        await self._destroy()

    async def _destroy(self):
        self.cleanup()

        if self._destroyed:
            # Idempotency handling, if `disconnect()` is called, the changed voice state
            # could cause this to run a second time.
            return

        self._destroyed = True

        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except Exception:
            pass

class ServerUI:
    def __init__(self, bot, player, downloader_id, track_name, track_index, track_duration, txt_channel_id, auto_queue: Optional[List[VideoDB]], _video=None):
        self.bot = bot
        self.player = player
        self.downloader_id = downloader_id
        self.avatar = None
        self.track_name = track_name
        self.track_index = track_index
        self.track_duration = track_duration
        self.txt_channel_id = txt_channel_id
        self._running = False
        self.loop = asyncio.get_event_loop()
        self._task = None
        self.guild_id = None
        self.played_time = 0
        self.ui_message = None
        self._video=_video
        self.auto_queue = auto_queue if auto_queue is not None else []

    async def start(self):
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== ServerUI.start() for", self.track_name, "=====")
            self._running = True
            last_message = None
            if self.txt_channel_id:
                txt_channel: discord.TextChannel = await self.bot.fetch_channel(self.txt_channel_id)
            else:
                guild = self.bot.get_guild(self.player.guild_id)
                txt_channel = discord.utils.get(guild.channels, name="musique", type=discord.ChannelType.text) if guild else None
                if txt_channel is None:
                    self._running = False
                    return
            
            self.guild_id = txt_channel.guild.id
            if self.guild_id not in self.bot.server_music_session:
                self.bot.server_music_session[self.guild_id] = {'time': 0, 'nb': 0}

            if not self._video:
                if self.player.current is None:
                    self._running = False
                    return
                try:
                    self.video = VideoDB.from_row(dict(self.player.current.extra))
                except Exception:
                    if self.player.current is None:
                        self._running = False
                        return
                    result = await download(pool=self.bot.pool, session=self.bot.session, video_id=self.player.current.identifier, downloader=1065781211219370104, is_autoplay=True)
                    if isinstance(result, VideoDB):
                        self.video = result
                        self.player.current.extra = result.to_dict()
                    else:
                        raise
            else:
                self.video = self._video

            waiting_layout = MusicWaitingView(bot=self.bot, ctx=discord.Interaction, serverid=self.guild_id)

            file = discord.File(f"{MAIN_DIR}/files/waiting.png", filename=f"Waiting.png")
            self.ui_message = await txt_channel.send(file=file, view=waiting_layout)

            iteration = 0
            while self.player.is_playing and self._running:
                iteration += 1
                self.played_time = self.player.position / 1000
                try:
                    self.next_musics = []
                    for music in self.player.queue[:8]:
                        try:
                            self.next_musics.append(VideoDB.from_row(music.extra))
                        except Exception:
                            continue
                    if self.player.is_playing and len(self.auto_queue) > 0 and len(self.next_musics) < 5:
                        for i in range(min(3, len(self.auto_queue))):
                            self.next_musics.append(self.auto_queue[i])
                    try:
                        await asyncio.wait_for(asyncio.to_thread(draw_music, self.guild_id, int(self.played_time), self.video, self.next_musics), timeout=8)
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        traceback.print_exc()
                    file = discord.File(f"{MAIN_DIR}/files/{self.guild_id}_music_player.png", filename=f"Music.png")
                    
                    parsed = parse_name_tuple(f"{self.video.name} ({self.video.pos})")
                    if self.track_index is not None:
                        if parsed is True:
                            title = f"Musique {html.unescape(self.video.name)} ({self.video.pos})"
                        elif parsed is False:
                            title = f"Musique {html.escape(self.video.name)} (autoplay)"
                        elif isinstance(parsed, list):
                            title = f"Musique {parsed[0]} ({parsed[1]})"
                    else:
                        title = f"Musique {html.unescape(self.video.name)} (autoplay)"
                    embed = discord.Embed(title=title, description=f" ", color=0x2F3136)

                    embed.set_image(url=f"attachment://Music.png")
                    try: # check if the message is still the last message in the channel
                        try:
                            last_message = await asyncio.wait_for(get_latest_message_from_channel(txt_channel), timeout=5)
                        except asyncio.TimeoutError:
                            print("Timeout while fetching latest message from channel, using current UI message as last_message.")
                            last_message = self.ui_message
                        except Exception as e:
                            print("Error while fetching latest message from channel:", e)
                            traceback.print_exc()
                            last_message = self.ui_message
                        view = MusicMessageView(bot=self.bot, ctx=discord.Interaction, serverid=self.guild_id, player=self.player, music_title=title)
                        if self.ui_message.id != last_message.id and last_message.created_at < datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5):
                            await asyncio.shield(asyncio.wait_for(self.ui_message.delete(), timeout=8))
                            self.ui_message = await asyncio.shield(asyncio.wait_for(txt_channel.send(view=view, file=file), timeout=8))
                            last_message = self.ui_message
                        elif self.ui_message.id == last_message.id:
                            try:
                                self.ui_message = await asyncio.wait_for(self.ui_message.edit(view=view, content=None, embed=None, attachments=[file]), timeout=5)
                            except asyncio.TimeoutError:
                                print("Timeout while editing music player message.(2)")
                            except Exception as e:
                                print("Error while editing music player message:", e)
                                traceback.print_exc()
                    except discord.errors.HTTPException:
                        # LogErrorInWebhook(f"Music {self.video.name} ({self.video.pos}) cannot be edited, message not found.")
                        pass
                    if isinstance(self.video.duree, tuple):
                        _, _duree = self.video.duree
                        duree = int(str(_duree).split(".")[0])
                    elif isinstance(self.video.duree, float):
                        duree = int(int(str(self.video.duree).split(".")[0]))
                    else:
                        duree = int(self.video.duree)
                    if int(self.played_time) > (duree * 1.02):# If current time is 2% bigger than song time, cancel the task
                        LogErrorInWebhook(f"Music {self.video.name} ({self.video.pos}) has overplayed.")
                        try:
                            await self.stop()
                        finally:
                            return
                    if self.ui_message is not None:
                        if self.ui_message.edited_at is not None:
                            sleep_time = (self.ui_message.edited_at + datetime.timedelta(seconds=8) - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                        elif self.ui_message.edited_at is None and self.ui_message.created_at is not None:
                            sleep_time = (self.ui_message.created_at + datetime.timedelta(seconds=8) - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                    else:
                        sleep_time = datetime.timedelta(seconds=8).total_seconds()    

                    await asyncio.sleep(max(0, sleep_time))
                except Exception as e:
                    traceback.print_exc()
                    await sleep(3)
        except Exception as e:
            print("Music UI start error:", e)
            LogErrorInWebhook(f"Music UI start error for {self.track_name} ({self.track_index}) in guild {self.guild_id}.\n```{e}```")
            traceback.print_exc()

    async def stop(self):
        if not self._running:
            return
        self._running = False
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}][F] ServerUI.stop() for", self.track_name)
        if self.played_time > 4:
            await save_song_stats(time=int(self.played_time), number=1, pool=self.bot.pool)
        if self.guild_id in self.bot.server_music_session:
            self.bot.server_music_session[self.guild_id]['nb'] +=  1
            self.bot.server_music_session[self.guild_id]['time'] +=  int(self.played_time)
        if self.ui_message:
            try:
                await asyncio.to_thread(draw_music, self.guild_id, 0, self.video, self.next_musics, True)
                try:
                    raw_txt = f"{self.video.name} ({self.video.pos})"
                    pattern = r"\('name', '([^']*)'\)\s*\(\('pos', (\d+)\)\)"
                    match = re.search(pattern, raw_txt)
                    if match:
                        name = match.group(1)
                        pos = match.group(2)
                    title = f"Musique {html.unescape(name)} ({pos})"
                except:
                    title = f"Musique {html.unescape(self.video.name)} (autoplay)"
                file = discord.File(f"{MAIN_DIR}/files/{self.guild_id}_end_music_player.png", filename=f"End.png")
                view = MusicEndView(bot=self.bot, ctx=discord.Interaction, serverid=self.guild_id, music_title=title)
                await self.ui_message.edit(attachments=[file], view=view)
            except Exception:
                pass

    @property
    def task(self):
        return self._task

    @task.setter
    def task(self, __value):
        self._task = __value

class MusicWaitingView(ui.LayoutView):
    def __init__(self, *, bot, ctx, serverid: int, timeout: Optional[float] = 180) -> None:
        super().__init__(timeout=timeout)
        try:
            self.bot = bot
            self.ctx = ctx
            self.thumb_file = discord.File(f"{MAIN_DIR}/files/waiting.png", filename=f"Waiting.png")
            self.text = ui.TextDisplay('## Chargement de la musique en cours...')
            gallery = ui.MediaGallery(
                discord.MediaGalleryItem(media=self.thumb_file, description="Chargement de la musique en cours...")
            )
            container = ui.Container(self.text, gallery)
            self.add_item(container)
        except Exception as e:
            traceback.print_exc()
            LogErrorInWebhook(f"Error in MusicWaitingView initialization: {e}")

class MusicEndView(ui.LayoutView):
    def __init__(self, *, bot, ctx, serverid: int, music_title: str, timeout: Optional[float] = 180) -> None:
        super().__init__(timeout=timeout)
        try:
            self.bot = bot
            self.ctx = ctx
            self.thumb_file = discord.File(f"{MAIN_DIR}/files/{serverid}_end_music_player.png", filename=f"End.png")
            self.text = ui.TextDisplay(f'## {music_title}')
            gallery = ui.MediaGallery(
                discord.MediaGalleryItem(media=self.thumb_file, description=f"{music_title}")
            )
            container = ui.Container(self.text, gallery)
            self.add_item(container)
        except Exception as e:
            traceback.print_exc()
            LogErrorInWebhook(f"Error in MusicEndView initialization: {e}")

class MusicMessageView(ui.LayoutView):
    """View principale affichée pendant la lecture d'une musique, avec les boutons d'interaction et l'image youtube de la musique."""
    def __init__(self, *, bot, ctx, serverid: int, player=None, timeout: Optional[float] = 180, music_title: str="") -> None:
        super().__init__(timeout=timeout)
        try:
            self.bot = bot
            self.ctx = ctx
            if player is None:
                player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            self.player = player
            self.thumb_file = discord.File(f"{MAIN_DIR}/files/{serverid}_music_player.png", filename=f"Music.png")
            self.text = ui.TextDisplay(f'## {music_title if music_title else "Musique en cours..."}')
            gallery = ui.MediaGallery(
                discord.MediaGalleryItem(media=self.thumb_file, description=f"{music_title if music_title else 'Musique en cours...'}")
            )
            
            separator = ui.Separator(
                spacing = discord.SeparatorSpacing.large, # can be small or large
                visible = True, # whether to visually display a line
            )

            row1 = ui.ActionRow()

            # Previous Button
            prev_song_btn = ui.Button(label="Musique d'avant", style=discord.ButtonStyle.primary, emoji="⬅", custom_id="prev", row=0, disabled=True)
            if serverid in self.bot.last_music:
                prev_song_btn.disabled = False
            row1.add_item(prev_song_btn)
            prev_song_btn.callback = lambda interaction=self.ctx, button=prev_song_btn: self.button_callback(interaction, button)
            
            # AutoPlay Button - simplified for lavalink.py
            autoplay_is_on = getattr(self.bot, 'autoplay_enabled', {}).get(serverid, True)
            autoplay_button = ui.Button(
                label=f"AutoPlay: {'ON' if autoplay_is_on else 'OFF'}",
                style=discord.ButtonStyle.success if autoplay_is_on else discord.ButtonStyle.secondary,
                emoji="🎲" if autoplay_is_on else "⛔",
                custom_id="autoplay",
                row=0,
                disabled=False,
            )
            row1.add_item(autoplay_button)
            autoplay_button.callback = lambda interaction=self.ctx, button=autoplay_button: self.button_callback(interaction, button)

            # Skip Button - simplified for lavalink.py
            if len(player.queue) > 0:
                next_button = ui.Button(label="Musique d'après", style=discord.ButtonStyle.primary, emoji="➡", custom_id="skip", row=0)
            else:
                next_button = ui.Button(label="Musique d'après", style=discord.ButtonStyle.primary, emoji="➡", custom_id="skip", row=0, disabled=True)
            row1.add_item(next_button)
            next_button.callback = lambda interaction=self.ctx, button=next_button: self.button_callback(interaction, button)

            row2 = ui.ActionRow()
            if self.player.is_playing and self.player.current.duration and self.player.current.duration > 20000:
                back_time = ui.Button(label="<< 20s", style=discord.ButtonStyle.secondary, emoji="⏪", custom_id="back_time", row=1)
            else:
                back_time = ui.Button(label="<< 20s", style=discord.ButtonStyle.secondary, emoji="⏪", custom_id="back_time", row=1, disabled=True)
            row2.add_item(back_time)
            back_time.callback = lambda interaction=self.ctx, button=back_time: self.button_callback(interaction, button)

            if self.player.is_playing:
                pause_button = ui.Button(label="Pause", style=discord.ButtonStyle.secondary, emoji="⏯", custom_id="pause_resume", row=1)
            else:
                pause_button = ui.Button(label="Resume", style=discord.ButtonStyle.secondary, emoji="⏯", custom_id="pause_resume", row=1)
            row2.add_item(pause_button)
            pause_button.callback = lambda interaction=self.ctx, button=pause_button: self.button_callback(interaction, button)

            if self.player.is_playing and self.player.current.duration and self.player.current.duration - self.player.position >= 20000:
                forward_time = ui.Button(label="20s >>", style=discord.ButtonStyle.secondary, emoji="⏩", custom_id="forward_time", row=1)
            else:
                forward_time = ui.Button(label="20s >>", style=discord.ButtonStyle.secondary, emoji="⏩", custom_id="forward_time", row=1, disabled=True)
            row2.add_item(forward_time)
            forward_time.callback = lambda interaction=self.ctx, button=forward_time: self.button_callback(interaction, button)

            row3 = ui.ActionRow()
            like_btn = ui.Button(label="Like", style=discord.ButtonStyle.primary, emoji="👍", custom_id="like", row=1)
            row3.add_item(like_btn)
            like_btn.callback = lambda interaction=self.ctx, button=like_btn: self.button_callback(interaction, button)

            disco_btn = ui.Button(label="Disconnect", style=discord.ButtonStyle.danger, emoji="🔌", custom_id="disconnect", row=1)
            row3.add_item(disco_btn)
            disco_btn.callback = lambda interaction=self.ctx, button=disco_btn: self.button_callback(interaction, button)

            container = ui.Container(self.text, separator, gallery, separator, row1, row2, row3)
            self.add_item(container)
        except Exception as e:
            traceback.print_exc()
            LogErrorInWebhook(f"Error in MusicMessageView initialization: {e}")

    async def button_callback(self, interaction: Interaction, button: discord.ui.Button):
        try: await interaction.response.defer()
        except: pass
        if button.custom_id == "pause_resume":
            if self.player.is_playing:
                await self.player.set_pause(True)
                button.label = "Resume"
                button.style = discord.ButtonStyle.success
            else:
                await self.player.set_pause(False)
                button.label = "Pause"
                print("resuming")
                button.style = discord.ButtonStyle.secondary
            try:
                await interaction.edit_original_response(view=self)
            except discord.errors.NotFound:
                return await interaction.followup.send(view=self)
        elif button.custom_id == "back_time":
            new_position = max(0, self.player.position - 20000)
            await self.player.seek(new_position)
        elif button.custom_id == "forward_time":
            if self.player.current and self.player.current.duration:
                new_position = min(self.player.current.duration, self.player.position + 20000)
                await self.player.seek(new_position)
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
            self.player._skip_by_command = True  # Ajout du flag pour différencier skip manuel
            await self.player.skip()
            if track is not None:
                if self.player.guild_id in self.bot.server_music_session:
                    self.bot.server_music_session[self.player.guild_id]['nb'] +=  1
                data = dict(track.extra)
                try:
                    embed = create_embed(title="Musique", description=f"La musique `{data['name']}` (**{data['pos']}**) a été passé par <@{interaction.user.id}>.", suggestions=["mlist","play", "search"])
                except KeyError: # this is from autoplay
                    embed = create_embed(title="Musique", description=f"La musique `{track.title}` a été passé par <@{interaction.user.id}>.", suggestions=["mlist","play", "search"])
                await interaction.followup.send(embed=embed)
                try:
                    await storeSkippedSong(pool=self.bot.pool, songname=data['name'], userid=str(interaction.user.id))
                    return
                except KeyError:
                    await storeSkippedSong(pool=self.bot.pool, songname=track.title, userid=str(interaction.user.id))
                    return 
        elif button.custom_id == "disconnect":
            self.player.queue.clear()
            await self.player.stop()
            await self.ctx.voice_client.disconnect(force=True)
            try:
                if interaction.guild.id in self.bot.ui_V2:
                    await self.bot.ui_V2[interaction.guild.id].stop()
                    self.bot.ui_V2[interaction.guild.id].task.cancel()
                    self.bot.ui_V2.pop(interaction.guild.id, None)
            except Exception as e:
                print("X02:", e)
                pass
            if interaction.guild.id in self.bot.server_music_session:
                played_time = convert_to_minutes_seconds(str(self.bot.server_music_session[interaction.guild.id]['time']))
                embed = create_embed(title="Musique", description=f"Bot déconnecté du vocal par <@{interaction.user.id}>\nJ'ai joué {self.bot.server_music_session[interaction.guild.id]['nb']} musiques, pour une durée de **{played_time}**!")
            else: embed = create_embed(title="Musique", description=f"Trapard déconnecté du vocal par <@{interaction.user.id}>.")
            await interaction.followup.send(embed=embed,view=EndSessionBtn(bot=self.bot))
            if self.player.guild_id in self.bot.server_music_session:
                self.bot.server_music_session[self.player.guild_id] = {'nb': 0, 'time': 0}
        elif button.custom_id == "like":
            songData = VideoDB.from_row(self.player.current.extra)
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.fetchall("SELECT songId FROM LikedSongsV2 WHERE userId = ?", (str(interaction.user.id),))
                    if result:
                        # check if the song is already liked
                        for song in result:
                            print(song[0], songData.video_id)
                            if str(song[0]).strip() == str(songData.video_id).strip():
                                embed = create_embed(title="Musique", description=f"<@{interaction.user.id}>, tu as déjà liké cette musique.")
                                return await interaction.followup.send(embed=embed)
                    await conn.execute("INSERT INTO LikedSongsV2 (userId, songId, songName) VALUES (?, ?, ?)", (int(interaction.user.id), str(songData.video_id), str(songData.name)))
                    embed = create_embed(title="Musique", description=f"<@{interaction.user.id}>, la musique `{songData.name}` a été ajoutée à tes musiques likées.")
                return await interaction.followup.send(embed=embed)
        elif button.custom_id == "prev":
            pass
        elif button.custom_id == "autoplay":
            current = getattr(self.bot, 'autoplay_enabled', {}).get(interaction.guild.id, True)
            new_value = not current
            self.bot.autoplay_enabled[interaction.guild.id] = new_value

            button.label = f"AutoPlay: {'ON' if new_value else 'OFF'}"
            button.style = discord.ButtonStyle.success if new_value else discord.ButtonStyle.secondary
            button.emoji = "🎲" if new_value else "⛔"

            embed = create_embed(title="Musique", description=f"AutoPlay est maintenant **{'activé' if new_value else 'désactivé'}**.")
            try:
                await interaction.edit_original_response(view=self)
            except discord.errors.NotFound:
                await interaction.followup.send(view=self)
            await interaction.followup.send(embed=embed)
        return
    
    async def on_timeout(self):
        try: return await self.ctx.edit_original_response(view=None)
        except: pass

async def download(pool: Pool, session: ClientSession, video_id: str, downloader: int, is_autoplay: bool = False) -> VideoDB | None:
    """Télécharge les informations d'une vidéo YouTube et les enregistre dans la base de données. Si la vidéo existe déjà, elle est récupérée depuis la base de données."""
    if is_autoplay:
        music_table = "autoplay"
    else:
        music_table = "musiquesV3"
    async def save_to_db(video: VideoDB, dler:int, pool:Pool, index:int):
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"INSERT INTO {music_table} (pos, duree, name, artiste, downloader, thumbnail, channel_avatar, likes, views, video_id, upload_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (index, video.duree, video.name, video.artiste, dler, video.thumbnail, video.channel_avatar, video.likes, video.views, video.video_id, video.upload_date))
        return
    
    async def download_image(url: str, _type: Literal["thumb","avatar"], video_id: str) -> str:
        if url == "N/A": return "N/A"
        path = f"/home/dreus/trapard/files/mlist_images/{video_id}_{_type}.jpg"
        if os.path.exists(path): return path
        else:
            async with session.get(url) as response:
                data = await response.read()
            with open(path, "wb") as f:
                f.write(data)
            return path

    async def get_info(_id: str, dler, i) -> VideoDB:
        url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": _id,
            "key": getVar('YOUTUBE_API')
        }

        async with session.get(url, params=params) as resp:
            data = await resp.json()

        if "items" not in data or not data["items"]:
            print(f"❌ Vidéo introuvable : {_id}", data)
            return None  # Vidéo introuvable

        video = data["items"][0]

        title = video["snippet"]["title"]
        channel = video["snippet"]["channelTitle"]
        likes = int(video["statistics"].get("likeCount", 666))
        views = int(video["statistics"].get("viewCount", 666))
        duration = int(isodate.parse_duration(video["contentDetails"]["duration"]).total_seconds())
        thumb = await download_image(video["snippet"]["thumbnails"]["high"]["url"], "thumb", _id)
        upload_date = video["snippet"]["publishedAt"]
        channel_avatar_url = await get_channel_avatar(video["snippet"]["channelId"])
        channel_avatar = await download_image(channel_avatar_url, "avatar", _id)

        v = VideoDB(
            id=0, pos=i, duree=duration, name=title, artiste=channel,
            downloader=dler, thumbnail=thumb, channel_avatar=channel_avatar,
            likes=likes, views=views, video_id=_id, upload_date=upload_date
        )

        await save_to_db(v, dler, pool, index=i)

        return v

    async def get_channel_avatar(channel_id):
        """Récupère l'avatar de la chaîne."""
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "snippet",
            "id": channel_id,
            "key": getVar('YOUTUBE_API')
        }

        async with session.get(url, params=params) as resp:
            data = await resp.json()

        if "items" in data and data["items"]:
            return data["items"][0]["snippet"]["thumbnails"]["high"]["url"]
        
        return "https://www.example.com/default-avatar.jpg"

    # First of all check if the video is already in the db
    async with pool.acquire() as conn:
        data = await conn.fetchone(f"SELECT * FROM {music_table} WHERE video_id = ?", (video_id,))
    if data:
        data_list = list(data)
        if 'debian' in str(data_list[6]):
            data_list[6] = str(data_list[6]).replace("debian", "dreus")
        if 'debian' in str(data_list[7]):
            data_list[7] = str(data_list[7]).replace("debian", "dreus")
        if data_list[11] is None:
            data_list[11] = ""
        return VideoDB(id=data_list[0], pos=data_list[1], duree=data_list[2], name=data_list[3], artiste=data_list[4], downloader=data_list[5], thumbnail=data_list[6], channel_avatar=data_list[7], likes=data_list[8], views=data_list[9], video_id=data_list[10], upload_date=data_list[11])
    next_index = await get_next_index(pool)
    video = await get_info(video_id, downloader, next_index)
    if isinstance(video, VideoDB):
        return video
    return None

async def get_thumb(session: ClientSession, video_id:str):
    url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    async with session.get(url) as response:
        data = await response.read()
    with open(f"/home/dreus/trapard/files/mlist_images/{video_id}_thumb.jpg", "wb") as f:
        f.write(data)
    return f"/home/dreus/trapard/files/mlist_images/{video_id}_thumb.jpg"

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

def draw_music(serverid: int, current_track_time: int, video: VideoDB, next_musics: List[VideoDB], ended=False):
    
    def minutes_to_time(minutes: int) -> str:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02}:{mins:02}"

    def draw_text(draw: ImageDraw.ImageDraw, text: str, coordinates: Tuple[int, int], box_size: Tuple[int, int], font: ImageFont.FreeTypeFont, fill: str) -> None:
        text_width, text_height = draw.textlength(text, font=font), 24
        
        # Fixer la coordonnée x à celle de départ de la boîte pour aligner le texte à gauche
        x = coordinates[0]
        
        # Calculer la coordonnée y pour centrer verticalement le texte
        y = int(coordinates[1] + (box_size[1] - text_height) // 2)
        
        draw.text(
            (x, y),
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

    def draw_textV2(draw: ImageDraw.ImageDraw, text: str, coordinates: Tuple[int, int], box_size: Tuple[int, int], font: ImageFont.FreeTypeFont, fill: str) -> None:
        """Helper function to split text into lines based on box width"""
        def split_text_into_lines(text: str, max_width: int, font: ImageFont.FreeTypeFont):
            words = text.split()
            lines = []
            current_line = ""
            returned = 0
            for word in words:
                test_line = f"{current_line} {word}".strip()
                test_width = draw.textlength(test_line, font=font)
                if test_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
                    returned += 1
                    if returned == 4:
                        break
            
            lines.append(current_line)
            return lines
        
        lines = split_text_into_lines(text, box_size[0], font)
        line_height = 30
        
        x, y = coordinates
        for line in lines:
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height

    red = "#ee2408"
    grey = "#808080"
    PATH = "/home/dreus/trapard/files"
    FONT = PATH + "/Roboto-Regular.ttf"

    try:
        _, duree = video.duree
        _, thumbnail = video.thumbnail
        _, channel_avatar = video.channel_avatar
        _, name = video.name
        _, likes = video.likes
        _, views = video.views
        _, artiste = video.artiste
        _, upload_date = video.upload_date
    except TypeError:
        duree = video.duree
        thumbnail = video.thumbnail
        channel_avatar = video.channel_avatar
        name = video.name
        likes = video.likes
        views = video.views
        artiste = video.artiste
        upload_date = video.upload_date

    pbar_percent = current_track_time * 100 / int(duree)
    img = Image.open(f"{PATH}/new_yt.png")
    draw = ImageDraw.Draw(img)

    thumb = Image.open(thumbnail).convert("RGBA")
    thumb = add_corners(thumb, 15)
    thumb = thumb.resize((1350, 757), Image.LANCZOS)
    img.paste(thumb, (30, 93), thumb)

    channel_avatar = Image.open(channel_avatar).convert("RGBA")
    channel_avatar = add_corners(channel_avatar, 80)
    channel_avatar = channel_avatar.resize((80, 80), Image.LANCZOS) # 
    img.paste(channel_avatar, (50, 906), channel_avatar) #

    draw_text(draw, name, (31, 850), (0, 40), ImageFont.truetype(FONT, 40), "white")

    draw_text(draw, artiste, (140, 910), (0, 40), ImageFont.truetype(FONT, 30), "white") #

    draw_text(draw, f"{display_big_nums(likes)}", (1125, 907), (0, 40), ImageFont.truetype(FONT, 35), "white")

    if upload_date is not None and upload_date != "":
        elapsed_value, elapsed_unit, elapsed_year = iso_to_eslapsed_time(upload_date)
        draw_text(draw, f"{display_big_nums(views)} vues - Il y a {elapsed_value} {elapsed_unit} ({elapsed_year})", (50, 1000), (0, 40), ImageFont.truetype(FONT, 35), "white")
    else:
        draw_text(draw, f"{display_big_nums(views)} vues", (50, 1000), (0, 40), ImageFont.truetype(FONT, 35), "white")

    for i, _video in enumerate(next_musics):
        try:
            _, _thumbnail = _video.thumbnail
            _, _name = _video.name
        except TypeError:
            _thumbnail = _video.thumbnail
            _name = _video.name
        except ValueError:
            _thumbnail = _video.thumbnail
            _name = _video.name
        if i == 8:
            break
        thumb = Image.open(_thumbnail).convert("RGBA")
        thumb = add_corners(thumb, 10)
        thumb = thumb.resize((175, 110), Image.LANCZOS)
        img.paste(thumb, (1420, 200 + 125 * i), thumb)

        draw_textV2(draw, _name, (1610, 200 + 125 * i), (285, 100), ImageFont.truetype(FONT, 28), "white")

    controls = Image.open(f"{PATH}/bottom_controls.png").convert("RGBA")
    img.paste(controls, (30, 755), controls)

    if ended:
        pbar_percent = 100
        draw_text(draw, f"{minutes_to_time(int(duree))} / {minutes_to_time(int(duree))}", (355, 792), (0, 40), ImageFont.truetype(FONT, 30), "white")
        path = f"{PATH}/{serverid}_end_music_player.png"
    else:
        path = f"{PATH}/{serverid}_music_player.png"
        draw_text(draw, f"{minutes_to_time(current_track_time)} / {minutes_to_time(int(duree))}", (355, 792), (0, 40), ImageFont.truetype(FONT, 30), "white")

    MAX = 1377
    MIN = 28
    width = (MAX - MIN) * pbar_percent / 100
    _pbar = pbar_percent + random.randint(2, 18)
    if _pbar > 100:
        _pbar = 100
    width2 = (MAX - MIN) * _pbar / 100

    draw.rectangle([(MIN, 755), (MIN + width2, 784)], fill=grey, outline=grey)
    draw.rectangle([(MIN, 755), (MIN + width, 784)], fill=red, outline=red)

    fp = io.BytesIO()
    img.convert("RGBA").save(fp, "PNG")
    img.save(path)

def getVideoId(title):
    try:
        results = YoutubeSearch(title, max_results=1).to_dict()
        id = results[0]["id"]
        return id
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
        # LogErrorInWebhook()
        return False

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

class get_artist_from_title():
    def __init__(self, title: str, bot):
        self.bot = bot
        token = asyncio.run(self.get_access_token())
        self.artists = asyncio.run(self.main(title=title, access_token=token))

    async def get_access_token(self):
        client_id = getVar("SPOTIFY_CLIENT")
        client_secret = getVar("SPOTIFY_SECRET")
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
                vc = await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient)
            except discord.errors.ClientException:
                vc = interaction.guild.voice_client
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall(f"SELECT name FROM {music_table}")
                for d in data:
                    out.append(d[0])
            zic_chann = discord.utils.get(interaction.guild.channels, name="musique", type=discord.ChannelType.text)
            tracks = []
            for track in out:
                results = await interaction.bot.lavalink.get_tracks(f"{MUSICS_FOLDER}{track}.mp3")
                if results.tracks:
                    index, downloader = await mlist_handler.get_index_by_music_name(track)
                    duration = await mlist_handler.get_song_duration_by_index(str(index))
                    results.tracks[0].extra = {"downloader": downloader, "pos": index, "name": track, "duree": duration, "txt_channel_id": zic_chann.id}
                    tracks.append(results.tracks[0])
            random.shuffle(tracks)
            player = interaction.bot.lavalink.player_manager.get(interaction.guild.id)
            for track in tracks:
                player.add(track)
            try:
                if not player.is_playing:
                    await player.play()
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
                results = await interaction.bot.lavalink.get_tracks(f"{MUSICS_FOLDER}{songName}.mp3")
                if results.tracks:
                    index, downloader = await mlist_handler.get_index_by_music_name(songName)
                    duration = await mlist_handler.get_song_duration_by_index(str(index))
                    results.tracks[0].extra = {"downloader": downloader, "pos": index, "name": songName, "duree": duration, "txt_channel_id": zic_chann.id}
                    music_list.append(results.tracks[0])
        random.shuffle(music_list)
        
        try:
            vc = await interaction.user.voice.channel.connect(cls=LavalinkVoiceClient)
        except discord.errors.ClientException:
            vc = interaction.guild.voice_client

        player = interaction.bot.lavalink.player_manager.get(interaction.guild.id)
        for track in music_list:
            player.add(track)
        embed = create_embed(title="Musique", description=f"`{len(music_list)} musique` ajouté à la queue. (titres likés de {user.display_name})", suggestions=["queue","mlist","playlist-play"])
        await interaction.followup.send(embed=embed)
        try:
            if not player.is_playing:
                await player.play()
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
            data = await conn.fetchall(f"SELECT name FROM {music_table}")
            for d in data:
                out.append(d[0])
        return out

    async def get_musique_size(self):
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall(f'SELECT * FROM {music_table}')
        return len(data)

    async def remove_from_music_list(self, index: str):
        """
        Remove a song from mlist by index
        """
        name = await self.getName(index)
        
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"DELETE FROM {music_table} WHERE name=? AND pos=?", (name, index))
                
                # Obtenez la taille de la liste une seule fois
                musique_size = await self.get_musique_size()
                
                for i in range(int(index) + 1, musique_size+10):
                    await conn.execute(f"UPDATE {music_table} SET pos = ? WHERE pos = ?", (i - 1, i))
        return

    async def get_all_music_name(self):
        """Return all music name in a dict where `key is video_id` and `value is [index, name]`"""
        try:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall(f"SELECT video_id, pos, name FROM {music_table}")
            if data:
                out = {}
                for item in data:
                    out[item[0]] = [item[1], item[2]]
                return out
        except Exception as e:
            LogErrorInWebhook()

    async def get_index_by_music_name(self, name: str):
        """
        return `index`, `user_downloader` of song by music_name
        """
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone(f"SELECT pos, downloader FROM {music_table} WHERE name = ?", (name,))
        if data:
            pos, downloader = data
            return str(pos), str(downloader)
        else: 
            return None, None

    async def find_song_by_name(self, name: str):
        """return dict of music name, index by a part name"""
        output = {}
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchall(f"SELECT name, pos FROM {music_table}")
            for i, item in enumerate(data):
                if name.lower() in str(item[0]).lower():
                    output[i] = {"index": item[1], "name": item[0]}
        if len(output) == 0:
            t = f"Aucune musique trouvée pour la recherche `{name}`."
        elif len(output) == 1:
            t = f"Une seule musique trouvée pour la recherche `{name}`:"
        else:
            t = f"Les trouvailles pour la recherche `{name}`:"
        return t, output

    async def get_next_index(self):
        """
        return the next index that should be in mlist.
        """
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone(f"SELECT pos FROM {music_table} ORDER BY id DESC LIMIT 1")
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
            data = await conn.fetchone(f"SELECT name FROM {music_table} WHERE pos = ?", int(index))
        if data:
            return data[0]
        return "Unknown index."

    async def get_song_duration_by_index(self, index:str):
        """return int(song) duration by index"""
        async with self.bot.pool.acquire() as conn:
            data = await conn.fetchone(f"SELECT duree FROM {music_table} WHERE pos = ?", int(index))
        if data:
            return int(data[0])
        else:
            return "Unknown index."

    async def get_unique_downloader(self):
        """
        return list of unique userid music downloader.
        """
        async with self.bot.pool.acquire() as conn:
            downloaders = await conn.fetchall(f"SELECT DISTINCT downloader FROM {music_table}")
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
        def __init__(self, options, pool: Pool, session: ClientSession, play_after: bool, bot: commands.Bot, ctx: commands.Context):
            super().__init__(placeholder='Choisis une des musiques 🦈', options=options, max_values=1, min_values=1)
            self.session = session
            self.pool = pool
            self.play_after = play_after
            self.bot = bot
            self.ctx = ctx
        async def callback(self, interaction: discord.Interaction):
            try: await interaction.response.defer()
            except: pass
            val = self.values[0]
            video_id = getVideoId(val)
            zic_chann = discord.utils.get(interaction.guild.channels, name="musique", type=discord.ChannelType.text)
            response = await interaction.channel.send(embed=create_embed("Musique", f"La musique {val} est en cours de téléchargement ! 🦈"))
            video = await download(pool=self.pool, session=self.session, video_id=video_id, downloader=interaction.user.id)
            if self.play_after:
                if self.ctx.author.voice is None:
                    embed = create_embed(title="Erreur", description="Vous n'êtes pas dans un channel vocal, **BUICON**.", suggestions=["queue","mlist","playlist-play"])
                    return await interaction.channel.send(embed=embed)
                try:
                    vc = (self.ctx.voice_client or await self.ctx.author.voice.channel.connect(cls=LavalinkVoiceClient))
                    results = await self.ctx.bot.lavalink.get_tracks(f"https://youtube.com/watch?v={video_id}")
                    if results.tracks:
                        _r = video.to_dict()
                        _r['txt_channel_id'] = zic_chann.id
                        results.tracks[0].extra = _r
                        player = self.ctx.bot.lavalink.player_manager.get(self.ctx.guild.id)
                        player.add(results.tracks[0])
                        if not player.is_playing:
                            await player.play()
                        embed = create_embed(title="Musique", description=f"La musique `{video.name}` (N°{video.pos}) a été ajoutée à la queue par <@{interaction.user.id}> ! 🦈", suggestions=["queue","mlist","playlist-play"])
                        await response.edit(embed=embed)
                        try: await interaction.delete_original_response()
                        except: pass
                except Exception as e:
                    LogErrorInWebhook()
            return await response.edit(embed=create_embed("Musique",f"La musique `{video.name}` (N°{video.pos}) a été téléchargée avec succès ! 🦈"))
    except Exception as e:
        LogErrorInWebhook()

class DropDownView(discord.ui.View):
    try:
        def __init__(self):
            super().__init__()
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

class AlreadyDownloadedDropdown(discord.ui.Select):
    def __init__(self, options_dl, _options, pool: Pool, session: ClientSession, ctx: commands.Context):
        self.ctx = ctx
        self.pool = pool
        self.session = session
        self._options = _options
        super().__init__(
            placeholder="Choisis une musique déjà téléchargée",
            options=options_dl,
            max_values=1,
            min_values=1
        )
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] != "new":
            try: await interaction.response.defer()
            except: pass
            print("Playing already downloaded song")
            await handle_play(ctx=self.ctx, _type="music", from_web=None, from_mlist=self.values[0])
            await interaction.delete_original_response()
        else:
            print("Downloading new song")
            drop_down = DropDown(options=self._options, pool=self.pool, session=self.session, play_after=True, ctx=self.ctx, bot=self.ctx.bot)
            view = DropDownView()
            view.add_item(drop_down)
            await interaction.response.edit_message(embed=create_embed(title="Musique", description="Résultats de ta recherche :"), view=view)

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

async def get_Video_from_input(from_web: str,downloader: int, pool:Pool, session: ClientSession, ctx: commands.Context) -> VideoDB:
    """Handle user input to return video id."""
    if from_web.isdigit():
        async with pool.acquire() as conn:
            data = await conn.fetchone(f"SELECT * FROM {music_table} WHERE pos = ?", (int(from_web),))
        if data is None:
            print("No data found")
            return
        video = VideoDB.from_row(data)
        from_web = video.video_id
    elif "http" in from_web: # youtube url try to get video id
        if 'youtu.be' in from_web:
            from_web = from_web.split("youtu.be/")[1]
        elif "v=" in from_web:
            from_web = from_web.split("v=")[1].split("&")[0]
        video = await download(pool=pool, session=session, video_id=from_web, downloader=downloader)
    elif (len(from_web) == 11) and (not " " in from_web): # seems like an id
        video = await download(pool=pool, session=session, video_id=from_web, downloader=downloader)
    else: # search for the video
        print("searching for", from_web)
        string = from_web.strip()
        results = YoutubeSearch(string, max_results=15).to_dict()
        global videos
        videos = {}
        try:
            unique_titles = set()
            index = 0
            for result in results:
                if index == 5:
                    break
                title, channel, id, durr = result["title"], result["channel"], result["id"], result["duration"]
                if title not in unique_titles:  # Check if the title is already present
                    unique_titles.add(title)
                    videos[f"video{index}"] = [title, channel, id, durr]
                    index += 1
            descriptions = [
                f"Chaine: {videos[f'video{i}'][1]} | Durée: {videos[f'video{i}'][3]}"
                for i in range(5)
            ]
            options = [
                discord.SelectOption(label=videos[f'video{i}'][0], description=descriptions[i])
                for i in range(5)
            ]
            # Check if any of the 5 videos are already in the musiquesV3 table
            already_downloaded = []
            async with pool.acquire() as conn:
                for i in range(5):
                    vid_id = videos[f'video{i}'][2]
                    data = await conn.fetchone(f"SELECT name, video_id, pos FROM musiquesV3 WHERE video_id = ?", (vid_id,))
                    if data:
                        already_downloaded.append({"index": i, "name": data[0], "video_id": data[1], "pos": data[2]})

            if already_downloaded and len(already_downloaded) > 0:
                desc = "\n".join(
                    [f"{i+1}. `{v['name']}` ([YouTube](https://www.youtube.com/watch?v={v['video_id']}))" for i, v in enumerate(already_downloaded)]
                )
                embed = create_embed(
                    title="Déjà téléchargé ??",
                    description=f"Parmi les résultat(s), {len(already_downloaded)} musique(s) sont/est déjà dans la Mlist :\n{desc}\n\nVeux-tu jouer l'une d'elle(s) ?\n- Si oui, la prochaine fois, utilise son index dans la Mlist pour la jouer directement 😉​",
                )
                options_dl = [
                    discord.SelectOption(
                        label=f"{v['name']}", 
                        value=f"{v['pos']}", 
                        description="Déjà téléchargée"
                    ) for v in already_downloaded
                ]
                options_dl.append(discord.SelectOption(label="❌ Non je soushaite en télécharger une nouvelle ❌", value="new", description="Télécharger une nouvelle musique"))

                drop_down = AlreadyDownloadedDropdown(options_dl=options_dl, _options=options, pool=pool, session=session, ctx=ctx)
                view = DropDownView()
                view.add_item(drop_down)
                await ctx.channel.send(embed=embed, view=view)
                return view
            else:
                drop_down = DropDown(options=options, pool=pool, session=session, play_after=True, ctx=ctx, bot=ctx.bot)
                view = DropDownView()
                view.add_item(drop_down)
                await ctx.channel.send(embed=create_embed(title="Musique", description=f"Résultats de la recherche `{string}` :"), view=view)
                return view

        except Exception as e:
            traceback.print_exc()
            LogErrorInWebhook()
    return video

playlist_data = []
playlist_names = get_all_playlists_names()

class Music(commands.Cog):
    """Music related cog."""
    def __init__(self, bot) -> None:
        self.bot = bot
        self.music_list_handler = MusicList_Handler(bot=self.bot)
        self.music_session = {}

        self._register_lavalink_hook()

    def _register_lavalink_hook(self):
        if not hasattr(self.bot, 'lavalink'):
            return
        if getattr(self.bot, '_music_lavalink_hook_registered', False):
            return
        self.bot.lavalink.add_event_hook(self._lavalink_event_hook)
        self.bot._music_lavalink_hook_registered = True

    async def cog_load(self):
        self._register_lavalink_hook()

    @commands.Cog.listener()
    async def on_ready(self):
        self._register_lavalink_hook()

    async def _lavalink_event_hook(self, event):
        if isinstance(event, lavalink.TrackStartEvent):
            return await self.on_track_start(event)
        if isinstance(event, lavalink.TrackEndEvent):
            return await self.on_track_end(event)
        if isinstance(event, lavalink.TrackExceptionEvent):
            return await self.on_track_exception(event)
        return
    
    # Lavalink.py events
    @lavalink.listener(lavalink.TrackStartEvent)
    async def on_track_start(self, event: lavalink.TrackStartEvent):
        try:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}][I] on_track_start: {event.track}")
            player = event.player
            if not player:
                print("[I] player was none.")
                return
            track = event.track
            guild_id = player.guild_id
            c_auto_queue = getattr(self.bot, 'autoplay_suggestions', {}).get(guild_id, [])
            data = dict(track.extra) if track.extra else {}
            # Track ALL played songs (manual + autoplay) so streak detection sees manual plays
            if not hasattr(self.bot, 'autoplay_history'):
                self.bot.autoplay_history = {}
            _h = list(self.bot.autoplay_history.get(guild_id, []))
            _vid_h = data.get('video_id', '') or getattr(track, 'identifier', '') or ''
            _artist_h = data.get('artiste', '') or getattr(track, 'author', '') or ''
            _title_h = data.get('name', '') or getattr(track, 'title', '') or ''
            if _vid_h and not any(e.get('id') == _vid_h for e in _h[-3:]):
                _h.append({'id': _vid_h, 'artist': _artist_h, 'title': _title_h})
                self.bot.autoplay_history[guild_id] = _h[-20:]
            if not hasattr(self.bot, 'autoplay_enabled'):
                self.bot.autoplay_enabled = {}
            if data:
                downloader_id = data.get('downloader', data.get('_downloader'))
                track_name = data.get('name', data.get('_name', getattr(track, 'title', None)))
                track_index = data.get('pos', data.get('_index'))
                track_duration = data.get('duree', data.get('_duration', getattr(track, 'length', None)))
                txt_channel_id = data.get('txt_channel_id', data.get('_txt_chann', data.get('_txt_channel_id')))

                if txt_channel_id is None:
                    print(f"[I] ServerUI missing txt_channel_id. track={getattr(track, 'title', track)} extra_keys={list(data.keys())}")

                music_task = ServerUI(bot=self.bot, player=player, downloader_id=downloader_id, track_name=track_name, track_index=track_index, track_duration=track_duration, txt_channel_id=txt_channel_id, auto_queue=c_auto_queue)
                music_task.task = asyncio.create_task(music_task.start())
                self.bot.ui_V2[guild_id] = music_task
            else:
                result = await download(pool=self.bot.pool, session=self.bot.session, video_id=track.identifier, downloader=1065781211219370104, is_autoplay=True)
                if isinstance(result, VideoDB):
                    music_task = ServerUI(bot=self.bot, player=player, downloader_id=1065781211219370104, track_name=result.name, track_index=None, track_duration=result.duree, txt_channel_id=result.txt_channel_id, _video=result, auto_queue=c_auto_queue)
                    music_task.task = asyncio.create_task(music_task.start())
                    self.bot.ui_V2[guild_id] = music_task

                else:
                    LogErrorInWebhook(f"[I] track is from autoplay and his id is: {track.identifier} but result was not a VideoDB, result: {result}")
        except Exception as e:
            print(e)
            LogErrorInWebhook()
            pass
    @lavalink.listener(lavalink.TrackEndEvent)
    async def on_track_end(self, event: lavalink.TrackEndEvent):
        player = event.player
        if not player:
            return
        guild_id = player.guild_id

        if hasattr(player, "_skip_by_command") and player._skip_by_command:
            print("[I] Skipped by command, not processing end event.")
            player._skip_by_command = False
            if guild_id in self.bot.ui_V2:
                await self.bot.ui_V2[guild_id].stop()
            chann = self.bot.get_channel(player.channel_id)
            if len(player.queue) > 0 and chann and len(chann.members) > 1:
                if not player.is_playing:
                    await player.play()
            return

        track = event.track
        data = dict(track.extra) if track and track.extra else {}
        chann = self.bot.get_channel(player.channel_id)
        if chann and len(chann.members) == 1:
            try:
                player.queue.clear()
                await player.stop()
                guild = self.bot.get_guild(guild_id)
                if guild and guild.voice_client:
                    await guild.voice_client.disconnect(force=True)
                played_time = format_duration(str(self.bot.server_music_session.get(guild_id, {}).get('time', 0)))
                nb = self.bot.server_music_session.get(guild_id, {}).get('nb', 0)
                embed = create_embed(title="Musique", description=f"Fin de session (plus personne en vocal), j'ai joué {nb} musiques, pour une durée de **{played_time}**!")
                self.bot.server_music_session[guild_id] = {'nb': 0, 'time': 0}
                if guild:
                    zic_chann = discord.utils.get(guild.channels, name="musique", type=discord.ChannelType.text)
                    if zic_chann is not None:
                        await zic_chann.send(embed=embed, view=EndSessionBtn(bot=self.bot))
            except Exception as e:
                print("X01:", e)
        if data:
            last_name = data.get('name', data.get('_name', None))
            if last_name is not None:
                self.bot.last_music[guild_id] = last_name
        try:
            if guild_id in self.bot.ui_V2:
                await self.bot.ui_V2[guild_id].stop()
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] STOPPED UI for guild {guild_id} and track {data.get('name', data.get('_name', 'unknown')) if data else 'unknown'}")
        except Exception as e:
            print("X0254:", e)
            traceback.print_exc()
        chann = self.bot.get_channel(player.channel_id)
        if chann and len(chann.members) <= 1:
            return

        if len(player.queue) > 0:
            if not player.is_playing:
                await player.play()
            return

        await self._maybe_autoplay(player=player, last_track=track, last_data=data)
        return

    async def _autoplay_get_spotify_token(self) -> Optional[str]:
        try:
            client_id = getVar("SPOTIFY_CLIENT")
            client_secret = getVar("SPOTIFY_SECRET")
            headers = {
                'Authorization': 'Basic ' + base64.b64encode(
                    f'{client_id}:{client_secret}'.encode()
                ).decode()
            }
            async with self.bot.session.post(
                'https://accounts.spotify.com/api/token',
                data={'grant_type': 'client_credentials'},
                headers=headers
            ) as resp:
                result = await resp.json()
            return result.get('access_token')
        except Exception:
            return None

    @staticmethod
    def _clean_artist(raw: str) -> str:
        """AviciiOfficialVEVO → Avicii, Artist - Topic → Artist"""
        return re.sub(r'(VEVO|Official|\s*-\s*Topic)+$', '', raw, flags=re.IGNORECASE).strip()

    @staticmethod
    def _clean_title(raw: str) -> str:
        """Strip YouTube title noise for better Spotify matching: '(Official Video)', '[Lyrics]', etc."""
        cleaned = re.sub(
            r'\s*[\(\[].*(official|video|lyrics|audio|hd|4k|music\s*video|clip|live|radio|edit|version|remix|fan\s*mem).*[\)\]]\s*$',
            '', raw, flags=re.IGNORECASE
        ).strip()
        return cleaned if cleaned else raw

    async def _autoplay_spotify_recs(self, title: str, artist: str, token: str, skip_same_artist: bool = False) -> Tuple[List[Tuple[str, str]], List[str]]:
        """Returns (track_list, related_artist_names). Related artists first for variety.
        /recommendations deprecated Nov 2024; uses top-tracks + related-artists instead."""
        headers = {'Authorization': f'Bearer {token}'}
        clean_artist = self._clean_artist(artist)
        clean_title = self._clean_title(title)

        # Find artist_id via seed track (try cleaned title first)
        artist_id = None
        seed_name = ''
        for q in [f'track:{clean_title} artist:{clean_artist}', clean_title]:
            async with self.bot.session.get(
                'https://api.spotify.com/v1/search',
                params={'q': q, 'type': 'track', 'limit': 1},
                headers=headers
            ) as resp:
                data = await resp.json()
            items = data.get('tracks', {}).get('items', [])
            if items and items[0].get('artists'):
                artist_id = items[0]['artists'][0]['id']
                seed_name = items[0]['name'].lower()
                break

        # Fallback: search artist directly (important when skip_same_artist=True and seed not found)
        if not artist_id and clean_artist:
            print(f'[Autoplay] Seed track not found, trying artist search for "{clean_artist}"')
            async with self.bot.session.get(
                'https://api.spotify.com/v1/search',
                params={'q': clean_artist, 'type': 'artist', 'limit': 1},
                headers=headers
            ) as resp:
                art_data = await resp.json()
            art_items = art_data.get('artists', {}).get('items', [])
            if art_items:
                artist_id = art_items[0]['id']

        if not artist_id:
            return [], []

        related_tracks: List[Tuple[str, str]] = []
        same_artist_tracks: List[Tuple[str, str]] = []
        related_artist_names: List[str] = []

        # Related artists → 2 top tracks each (always fetched for variety)
        async with self.bot.session.get(
            f'https://api.spotify.com/v1/artists/{artist_id}/related-artists',
            headers=headers
        ) as resp:
            rel_data = await resp.json()
        for rel in rel_data.get('artists', [])[:6]:
            rel_name = rel.get('name', '')
            if rel_name:
                related_artist_names.append(rel_name)
            async with self.bot.session.get(
                f'https://api.spotify.com/v1/artists/{rel["id"]}/top-tracks',
                params={'market': 'FR'},
                headers=headers
            ) as resp:
                rel_top = await resp.json()
            for track in rel_top.get('tracks', [])[:2]:
                a = track['artists'][0]['name'] if track.get('artists') else ''
                related_tracks.append((a, track['name']))

        # Same-artist top tracks — only when artist hasn't dominated recent history
        if not skip_same_artist:
            async with self.bot.session.get(
                f'https://api.spotify.com/v1/artists/{artist_id}/top-tracks',
                params={'market': 'FR'},
                headers=headers
            ) as resp:
                top = await resp.json()
            for track in top.get('tracks', []):
                if track['name'].lower() != seed_name:
                    a = track['artists'][0]['name'] if track.get('artists') else ''
                    same_artist_tracks.append((a, track['name']))

        random.shuffle(related_tracks)
        random.shuffle(same_artist_tracks)
        random.shuffle(related_artist_names)
        return related_tracks + same_artist_tracks, related_artist_names

    async def _autoplay_yt_search(self, query: str, exclude_ids: List[str]) -> Optional[str]:
        """Search YouTube Music for a track, returns video_id or None."""
        try:
            api_key = getVar('YOUTUBE_API')
            async with self.bot.session.get(
                'https://www.googleapis.com/youtube/v3/search',
                params={
                    'part': 'snippet', 'q': query, 'type': 'video',
                    'videoCategoryId': '10', 'maxResults': 8, 'key': api_key,
                }
            ) as resp:
                data = await resp.json()

            candidates = [
                item['id']['videoId']
                for item in data.get('items', [])
                if item['id'].get('videoId') and item['id']['videoId'] not in exclude_ids
            ]
            if not candidates:
                return None

            # Filter by duration: skip Shorts (<60s) and very long videos (>15min)
            async with self.bot.session.get(
                'https://www.googleapis.com/youtube/v3/videos',
                params={'part': 'contentDetails,status', 'id': ','.join(candidates[:6]), 'key': api_key}
            ) as resp:
                details = await resp.json()

            for item in details.get('items', []):
                status = item.get('status', {})
                if status.get('privacyStatus') != 'public':
                    continue
                duration = int(isodate.parse_duration(
                    item['contentDetails']['duration']
                ).total_seconds())
                if 60 <= duration <= 900:
                    return item['id']
            return candidates[0] if candidates else None
        except Exception as e:
            print(f'[Autoplay] YouTube search error for "{query}": {e}')
            return None

    async def _maybe_autoplay(self, *, player: lavalink.BasePlayer, last_track: lavalink.AudioTrack, last_data: dict):
        try:
            guild_id = player.guild_id
            if not getattr(self.bot, 'autoplay_enabled', {}).get(guild_id, True):
                print('[Autoplay] disabled for this guild')
                return
            if len(player.queue) >= 1:
                return

            if not hasattr(self.bot, 'autoplay_history'):
                self.bot.autoplay_history = {}
            # History: list of {'id': str, 'artist': str, 'title': str}
            history: List[dict] = list(self.bot.autoplay_history.get(guild_id, []))

            last_video_id = last_data.get('video_id') or getattr(last_track, 'identifier', None)
            last_artist = last_data.get('artiste', '') or ''
            last_name = last_data.get('name', '') or getattr(last_track, 'title', '') or ''
            txt_channel_id = last_data.get('txt_channel_id')

            clean_last_artist = self._clean_artist(last_artist).lower()

            # How many of the last 5 songs were by the same artist?
            recent_artists = [self._clean_artist(e.get('artist', '')).lower() for e in history[-5:]]
            same_artist_streak = sum(1 for a in recent_artists if clean_last_artist and clean_last_artist in a)
            skip_same_artist = same_artist_streak >= 2
            if skip_same_artist:
                print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] Artist "{clean_last_artist}" appeared {same_artist_streak}x recently — skipping their top tracks')

            exclude_ids: List[str] = [e['id'] for e in history] + ([last_video_id] if last_video_id else [])
            seen_titles: set = {re.sub(r'[^a-z0-9]', '', e.get('title', '').lower()) for e in history}

            video_ids_to_queue: List[str] = []
            related_artist_names: List[str] = []

            # 1. Try Spotify recommendations (related artists first, then same-artist)
            try:
                token = await self._autoplay_get_spotify_token()
                if token and last_name:
                    recs, related_artist_names = await self._autoplay_spotify_recs(last_name, last_artist, token, skip_same_artist=skip_same_artist)
                    for sp_artist, sp_title in recs:
                        norm = re.sub(r'[^a-z0-9]', '', sp_title.lower())
                        if norm in seen_titles:
                            continue
                        # Block same-artist tracks even when they appear in related-artist catalogs (collabs)
                        if clean_last_artist and self._clean_artist(sp_artist).lower() == clean_last_artist:
                            continue
                        vid = await self._autoplay_yt_search(
                            f'{sp_artist} - {sp_title}',
                            exclude_ids + video_ids_to_queue
                        )
                        if vid:
                            video_ids_to_queue.append(vid)
                            seen_titles.add(norm)
                        else:
                            print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] No YT result for "{sp_artist} - {sp_title}"')
                        if len(video_ids_to_queue) >= 3:
                            break
                    print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] Spotify gave {len(video_ids_to_queue)} suggestion(s) | related_artists={related_artist_names[:3]}')
            except Exception as e:
                print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] Spotify path failed: {e}')

            # 2. Fallback: use a related artist when same-artist dominated, else use current artist
            if not video_ids_to_queue:
                try:
                    if skip_same_artist and related_artist_names:
                        fallback_q = f'{related_artist_names[0]} songs'
                    else:
                        clean_a = self._clean_artist(last_artist)
                        fallback_q = f'{clean_a} songs' if clean_a else f'{last_name} similar'
                        if skip_same_artist:
                            print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] WARNING: skip_same_artist but related_artist_names empty — falling back to "{fallback_q}"')
                    vid = await self._autoplay_yt_search(fallback_q, exclude_ids)
                    if vid:
                        video_ids_to_queue.append(vid)
                    print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] YouTube fallback ("{fallback_q}"): {vid}')
                except Exception as e:
                    print(f'[Autoplay] YouTube fallback failed: {e}')

            # 3. Add tracks to queue, then play once
            added = 0
            for video_id in video_ids_to_queue:
                try:
                    video = await download(
                        pool=self.bot.pool, session=self.bot.session,
                        video_id=video_id, downloader=1065781211219370104,
                        is_autoplay=True
                    )
                    if not isinstance(video, VideoDB):
                        continue
                    results = await self.bot.lavalink.get_tracks(f'https://youtube.com/watch?v={video_id}')
                    if not results or not results.tracks:
                        continue
                    _r = video.to_dict()
                    _r['txt_channel_id'] = txt_channel_id
                    _r['autoplay_from'] = 'recommendation'
                    results.tracks[0].extra = _r
                    player.add(results.tracks[0])
                    history.append({
                        'id': video_id,
                        'artist': str(video.artiste or ''),
                        'title': str(video.name or ''),
                    })
                    added += 1
                    print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}][Autoplay] Queued: {video.name} ({video.artiste})')
                except Exception as e:
                    print(f'[Autoplay] Failed to add {video_id}: {e}')

            self.bot.autoplay_history[guild_id] = history[-20:]

            if added > 0 and not player.is_playing:
                await player.play()

        except Exception as e:
            print(f'[Autoplay] Error: {e}')
            LogErrorInWebhook()

    @lavalink.listener(lavalink.TrackExceptionEvent)
    async def on_track_exception(self, event: lavalink.TrackExceptionEvent):
        try:
            if event.player.guild_id in self.bot.ui_V2:
                await self.bot.ui_V2[event.player.guild_id].stop()
                self.bot.ui_V2[event.player.guild_id].task.cancel()
        except Exception as e:
            print("X03:", e)
        exc_info = (
            getattr(event, 'exception', None)
            or getattr(event, 'error', None)
            or getattr(event, 'cause', None)
            or str(event)
        )
        track_title = getattr(event.track, 'title', '?') if event.track else '?'
        print(f"[P] TrackException: {track_title} | {exc_info}")
        LogErrorInWebhook(f"Music {track_title} has crashed.\n{exc_info}")

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
    @commands.command(name="pm")
    async def pm(self, ctx: commands.Context, *, keysearch: str):
        """Joue une ou plusieurs musique(s)."""
        return await handle_play(ctx=ctx, _type="music", from_web=keysearch)
    
    @commands.hybrid_group(name="play")
    async def play1(self, ctx: commands.Context): pass

    @play1.command() # old: /play
    @app_commands.describe(from_web="Exemple: du texte | url youtube | index de la mlist.")
    @app_commands.describe(from_mlist="Chercher la musique dans la Mlist par son titre.")
    async def music(self, ctx: commands.Context, *,from_web:str=None, from_mlist:str=None):
        """Joue une ou plusieurs musique(s)."""
        return await handle_play(ctx=ctx, _type="music", from_web=from_web, from_mlist=from_mlist)

    @music.autocomplete("from_mlist")
    async def autocomplete_musique_name(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in f"{val[1].lower()} ({val[0]})":
                    liste.append(app_commands.Choice(name=f"{val[1]} ({val[0]})", value=str(key)))
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
            vc = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient))
            zic_chann = discord.utils.get(ctx.guild.channels, name="musique", type=discord.ChannelType.text)
            music_list = []
            random.shuffle(data)
            for _i, track in enumerate(data):
                songId = ast.literal_eval(track[0])[1]
                video = await get_Video_from_input(songId, ctx.author.id, ctx.bot.pool, ctx.bot.session, ctx=ctx)
                results = await ctx.bot.lavalink.get_tracks(f"https://www.youtube.com/watch?v={songId}")
                if results.tracks:
                    _r = video.to_dict()
                    _r['txt_channel_id'] = ctx.channel.id
                    results.tracks[0].extra = _r
                    player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
                    player.add(results.tracks[0])
                    if _i == 0 and not player.is_playing:
                        await player.play()
                if _i == 0:
                    pass
        try:
            await ctx.message.add_reaction("\u2705")
        except discord.errors.NotFound:
            pass
        embed = create_embed(title="Musique", description=f"Les titres likés de <@{user.id}> ({len(data)} musiques) ont été ajoutés à la queue.")
        return await ctx.send(embed=embed)

    @play1.command(name='next') #old: /play-next
    @app_commands.describe(from_web="Exemple: du texte | url youtube | index de la mlist.")
    @app_commands.describe(from_mlist="Chercher la musique dans la Mlist par son titre.")
    async def play_next(self, ctx: commands.Context, *,from_web:str=None, from_mlist:str=None):
        """Play-next une musique"""
        return await handle_play(ctx=ctx, _type="next", from_web=from_web, from_mlist=from_mlist)

    @play_next.autocomplete("from_mlist")
    async def autocomplete_musique_name(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in f"{val[1].lower()} ({val[0]})":
                    liste.append(app_commands.Choice(name=f"{val[1]} ({val[0]})", value=str(key)))
                if len(liste) == 25:
                    break
            return liste
        except Exception as e:
            LogErrorInWebhook()

    @play1.command(name="random")
    async def play_random(self, ctx: commands.Context, nombre: int=10):
        """Jouer un nombre de musique dans la Mlist aléatoire."""
        return await handle_play(ctx=ctx, _type="random", random_nb=nombre)

# END PLAY GROUP

    @commands.hybrid_command() #old: /mlist
    async def mlist(self, ctx: commands.Context):
        """Affiche la liste de toutes les musiques."""
        if ctx.channel.name != "musique":
            return await ctx.send(embed=create_embed(title="Erreur", description="Merci d'utiliser un channel nommé: **musique**, pour jouer de la musique."), ephemeral=True)
        if not isinstance(ctx, CustomContext):
            try: await ctx.interaction.response.defer()
            except: print("error defer")
        
        try:
            async with ctx.channel.typing():
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
            return
        except:
            LogErrorInWebhook()

    @commands.hybrid_command(name='download', aliases=['search', 'dl', 'sh']) #old: /search and /download
    @app_commands.describe(keysearch = "Url Youtube ou texte de recherche.")
    async def download(self, interaction: commands.Context, *, keysearch: str):
        """Télécharger une musique, par url Youtube, ou par texte de recherche."""
        return await interaction.send(embed=create_embed(title="Musique", description="Cette commande est obsolète, merci d'utiliser `/play music [nom ou url Youtube]` à la place."), ephemeral=True)

# Music controler
    @commands.hybrid_command(name='skip', aliases=["next"]) # old: /skip
    @app_commands.describe(position="La position de la musique à passer. (rien pour passer la musique actuelle)")
    async def skip(self, ctx: commands.Context, position:int=None):
        """Passer la musique actuelle."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if ctx.channel.name != "musique":
                return await ctx.send(embed=create_embed(title="Erreur", description="Merci d'utiliser un channel nommé: **musique**, pour jouer de la musique."), ephemeral=True)
            if position is not None and (position < 1 or position > 5):
                return await ctx.send(embed=create_embed(title="Erreur", description="La position doit être entre 1 et 5."))
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                return
            if player.is_playing:
                current_data = dict(player.current.extra)
                if current_data:
                    if position is None:
                        cur_track = f"`{current_data['name']}` (**{current_data['pos']}**) a été passé par "
                        name = current_data['name']
                        player._skip_by_command = True  # Ajout du flag pour différencier skip manuel
                        await player.skip()
                    else:
                        next_track = player.queue[position - 1]
                        next_track_data = dict(next_track.extra)
                        name = next_track_data['name']
                        cur_track = f"`{next_track_data['name']}` (**{next_track_data['pos']}**) a été retiré de la queue par "
                    await storeSkippedSong(pool=self.bot.pool, songname=name, userid=str(ctx.author.id))
                else:
                    cur_track = f"`{player.current}` (**autoplay**) a été passé par "
                    name = None
                    player._skip_by_command = True  # Ajout du flag pour différencier skip manuel
                    await player.skip()
            else:
                embed = create_embed(title="Erreur", description="Il n'y a pas de musique en cours de lecture.")
                return await ctx.send(embed=embed)
            
            if ctx.guild.id in self.bot.server_music_session:
                self.bot.server_music_session[ctx.guild.id]['nb'] +=  1
            # if ctx.guild.id in self.bot.ui_V2 and self.bot.ui_V2[ctx.guild.id]:
            #     try:
            #         self.bot.locks[ctx.guild.id].release()
            #     except RuntimeError:
            #         pass
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
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                embed = create_embed(title="Erreur", description="Trapard est dans aucun vocal, tu es one head ou quoi ?")
                return await ctx.send(embed=embed)
            try:
                if ctx.guild.id in self.bot.ui_V2:
                    await self.bot.ui_V2[ctx.guild.id].stop()
                    self.bot.ui_V2[ctx.guild.id].task.cancel()
                    self.bot.ui_V2.pop(ctx.guild.id, None)	
            except Exception as e:
                print("X02:", e)
                pass
            if ctx.guild.id in self.bot.server_music_session:
                played_time = convert_to_minutes_seconds(str(self.bot.server_music_session[ctx.guild.id]['time']))
                embed = create_embed(title="Musique", description=f"Fin de session, j'ai joué {self.bot.server_music_session[ctx.guild.id]['nb']} musiques, pour une durée de **{played_time}**!")
                self.bot.server_music_session[ctx.guild.id] = {'nb': 0, 'time': 0}
            else: embed = create_embed(title="Musique", description="Trapard déconnecté du vocal par <@" + str(ctx.author.id) + ">.")
            player.queue.clear()
            await player.stop()
            await ctx.voice_client.disconnect(force=True)
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
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            video_id = None
            if musique_name is not None:
                video_id = musique_name
            elif index is not None:
                async with self.bot.pool.acquire() as conn:
                    data = await conn.fetchone(f"SELECT video_id, name FROM {music_table} WHERE pos = ?", (index,))
                if data is None:
                    return await ctx.send("Aucune musique ne correspond à cet index.")
                video_id = data[0]
            if video_id is not None:
                for _type in ["thumb", "channel_avatar"]:
                    try:
                        os.remove(f"{MLIST_FOLDER}/{video_id}_{_type}.jpg")
                    except FileNotFoundError:
                        pass
                async with self.bot.pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute(f"DELETE FROM {music_table} WHERE video_id = ?", (video_id,))
                # re index each pos
                async with self.bot.pool.acquire() as conn:
                    data = await conn.fetchall(f"SELECT pos FROM {music_table} ORDER BY pos")
                for i, d in enumerate(data):
                    await conn.execute(f"UPDATE {music_table} SET pos = ? WHERE pos = ?", (i+1, d[0]))
                try:
                    await ctx.message.add_reaction("\u2705")
                except discord.errors.NotFound:
                    pass
                embed = create_embed(title="Suppression", description=f"[Musique supprimée !](https://www.youtube.com/watch?v={video_id})", suggestions=["queue","mlist","playlist-play"])
                return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @remove.autocomplete("musique_name")
    async def autocomplete_musique_nameX(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in f"{val[1].lower()} ({val[0]})":
                    liste.append(app_commands.Choice(name=f"{val[1]} ({val[0]})", value=str(key)))
                if len(liste) == 25:
                    break
            return liste
        except Exception as e:
            LogErrorInWebhook()

#End music controler
    
    @commands.hybrid_command(name='is-song', aliases=["find"])
    @app_commands.describe(nom="Nom de la musique à chercher. Cela peut-être une partie du nom. Minimum 3 caractères")
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
            embed = create_embed(title="Is-song", description=result)
            for key, value in found.items():
                embed.add_field(name=f"Musique n°{value['index']}", value=f"{str(value['name'])[:77]}", inline=False)
            return await interaction.send(embed=embed)
        except discord.HTTPException as http_err:
            if http_err.code == 50035:
                await interaction.send(embed=create_embed(title="Erreur", description="Le message est trop long, essayes de faire une recherche plus précise."), ephemeral=True)
            else:
                await interaction.send(embed=create_embed(title="Erreur", description="Une erreur est survenue lors de la recherche."), ephemeral=True)
        except Exception as e:
            await interaction.send(embed=create_embed(title="Erreur", description=f"Une erreur est survenue lors de la recherche.\n```yaml\n{e}```"), ephemeral=True)
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
            vc = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient))
            if melange:
                embed = create_embed(title="Musique", description=f"La playlist `{playlistname}` a été ajouté à la queue en aléatoire !")
                random.shuffle(musicList)
            else: 
                embed = create_embed(title="Musique", description=f"La playlist `{playlistname}` a été ajouté à la queue dans l'ordre !")
            tracks = []
            for music in musicList:
                results = await ctx.bot.lavalink.get_tracks(f"{MUSICS_FOLDER}{music}.mp3")
                if not results.tracks:
                    continue
                index, downloader = await mlist_handler.get_index_by_music_name(music)
                duration = await mlist_handler.get_song_duration_by_index(str(index))
                results.tracks[0].extra = {"downloader": downloader, "pos": index, "name": music, "duree": duration, "txt_channel_id": ctx.channel.id}
                tracks.append(results.tracks[0])
            if len(tracks) == 0:
                return await ctx.send(f"La playlist : `{playlistname}` ne semble pas exister !", ephemeral=True)
            player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
            for track in tracks:
                player.add(track)
            try:
                if not player.is_playing:
                    await player.play()
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
                data = await conn.fetchall(f"SELECT songName FROM LikedSongsV2 WHERE userId = ?", (userID,))            
            if data == []:
                embed = create_embed(title="Liked-songs", description=f"<@{userID}> n'a pas de musiques likés !")
                return await ctx.send(embed=embed)
            else:
                batch_size = 15
                fields = []
                songs = [f'`{ast.literal_eval(i[0])[1]}`' for i in data]
                batchs = [songs[i:i + batch_size] for i in range(0, len(songs), batch_size)]
                for i, batch in enumerate(batchs):
                    fields.append({"name": f"{i+1}.", "value": " - ".join(batch), "inline": False})
                embed = create_embed(title=f"Musiques likés de {user.display_name}", fields=fields, description=f"Total de musiques likés: {len(songs)}")
                return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name="remove-liked-song", aliases=["rm-liked", "dislike"])
    @app_commands.describe(musique_name="Le nom de la musique à enlever de tes musiques likées.")
    async def remove_liked_song(self, ctx: commands.Context, musique_name:str=None):
        """Supprimer une musique de tes titres likées."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            if musique_name is not None:
                song_name = musique_name
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.fetchall("SELECT * FROM LikedSongsV2 WHERE userId = ? AND songName = ?", (str(ctx.author.id), song_name,))
                    if result is not None:
                        print(result)
                        await conn.execute("DELETE FROM LikedSongsV2 WHERE songName = ? AND userId = ?", (song_name, str(ctx.author.id),))
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
                    result = await conn.fetchall("SELECT songId, songName FROM LikedSongsV2 WHERE userId = ?", (str(ctx.user.id),))
                    if result:
                        for i in result:
                            songName = ast.literal_eval(i[1])[1]
                            if musique_name.lower() in songName.lower():
                                liste.append(app_commands.Choice(name=f"{songName}", value=i[1]))
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
                drop_down = SoundBoardDropDown(options=options,ctx=interaction, bot=self.bot, soundboard_manager=SoundBoardManage(pool=self.bot.pool))
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

    @commands.hybrid_command(name="fix-thumb", aliases=["ft"])
    @app_commands.describe(musique_name="Le nom de la musique à recharcher la miniature.")
    async def fixThumb(self, ctx: commands.Context, musique_name: str=None):
        """Recharger la miniature d'une musique."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=ctx.bot)
            if musique_name is not None:
                video_id = musique_name
            else:
                player = self.bot.lavalink.player_manager.get(ctx.guild.id)
                if player is None:
                    return await ctx.send("Trapard n'est pas dans le vocal.", ephemeral=True)
                if player.current is None:
                    return await ctx.send("Trapard n'a pas de musique en cours.", ephemeral=True)
                data = dict(player.current.extra)
                video_id = data["_downloader"]
            thumb = await get_thumb(session=self.bot.session, video_id=video_id)
            embed = create_embed(title="Fix-thumb", description=f"La miniature de la musique `{video_id}` a bien été rechargée.")
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @fixThumb.autocomplete("musique_name")
    async def autocomplete_musique_name(self, ctx: discord.Interaction, musique_name: str):
        try:
            liste = []
            d = await self.music_list_handler.get_all_music_name()
            for key, val in d.items():
                if musique_name.lower() in f"{val[1].lower()} ({val[0]})":
                    liste.append(app_commands.Choice(name=f"{val[1]} ({val[0]})", value=str(key)))
                if len(liste) == 25:
                    break
            return liste
        except Exception as e:
            LogErrorInWebhook()

    @commands.command(aliases=["vol"])
    async def volume(self, ctx: commands.Context, value: int) -> None:
        """Change the volume of the player."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if value > 300 and ctx.author.id != 311013099719360512:
            return await ctx.send(embed=create_embed(title="Volume", description="Le volume ne peut pas être supérieur à 300."))
        if not player:
            return
        await player.set_volume(value)
        await ctx.message.add_reaction("\u2705")
    
    @commands.hybrid_command(name="autoplay", aliases=["ap"])
    async def autoplay(self, ctx: commands.Context, value: bool) -> None:
        """Change the autoplay of the player."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return
        if value:
            await ctx.send(embed=create_embed(title="Autoplay", description="L'autoplay a été activé."))
        else:
            await ctx.send(embed=create_embed(title="Autoplay", description="L'autoplay a été désactivé."))
        await ctx.message.add_reaction("\u2705")

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

async def handle_play(ctx: commands.Context, _type: Literal['next', 'music', 'all'], from_web:str=None, from_mlist:str=None, random_nb:int=None):
    try:
        await command_counter(user_id=str(ctx.author.id), bot=ctx.bot)
        if ctx.channel.name != "musique": return await ctx.send(embed=create_embed(title="Erreur", description="Merci d'utiliser un channel nommé: **musique**, pour jouer de la musique."), ephemeral=True)
        
        try: vc = (ctx.voice_client or await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient))
        except AttributeError: return await ctx.send(embed=create_embed(title="Erreur", description="Tu n'es pas dans un channel vocal..."), ephemeral=True)
        
        try: await ctx.defer()
        except: pass

        try: await ctx.message.add_reaction("\u2705")
        except discord.errors.NotFound: pass
        
        if (_type == "next") or (_type == "music"):
            if from_mlist is not None:
                from_web = from_mlist
            # Note: lavalink.py doesn't have autoplay mode, this would need custom implementation
            video = await get_Video_from_input(from_web, ctx.author.id, ctx.bot.pool, ctx.bot.session, ctx=ctx)
            if isinstance(video, discord.ui.View): # Prompted user to choose a video
                await sleep(120)
                player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
                if player is not None:
                    if not player.is_playing: # User didn't choose a video in time, disconnecting from vocal
                        await vc.disconnect()
                        await ctx.send(embed=create_embed(title="Musique", description="Aucune musique n'a été choisie, je me déconnecte du vocal."), ephemeral=True)
                return
            results = await ctx.bot.lavalink.get_tracks(f"https://www.youtube.com/watch?v={video.video_id}")
            if results.tracks:
                try:
                    _r = video.to_dict()
                    _r['txt_channel_id'] = ctx.channel.id
                    results.tracks[0].extra = _r
                    if _type == "next":
                        player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
                        player.add(results.tracks[0], index=0)
                    else:
                        player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
                        player.add(results.tracks[0])
                except Exception as e:
                    print(e)
            player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
            if not player.is_playing:
                await player.play()
        elif _type == "random":
            if random_nb > 50:
                return await ctx.reply(embed=create_embed(title="Erreur", description="Le nombre de musiques aléatoires ne peut pas être supérieur à 50."))
            async with ctx.bot.pool.acquire() as conn:
                data = await conn.fetchall(f"SELECT * FROM {music_table} ORDER BY RANDOM() LIMIT ?", (random_nb,))
            for i, track in enumerate(data):
                video = VideoDB.from_row(track)
                try:
                    results = await ctx.bot.lavalink.get_tracks(f"https://www.youtube.com/watch?v={video.video_id}")
                    if results.tracks:
                        _r = video.to_dict()
                        _r['txt_channel_id'] = ctx.channel.id
                        results.tracks[0].extra = _r
                        player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
                        player.add(results.tracks[0])
                        print(f"Added to queue {video.name}")
                    if i == 0:
                        player = ctx.bot.lavalink.player_manager.get(ctx.guild.id)
                        if not player.is_playing:
                            await player.play()
                except Exception as e:
                    LogErrorInWebhook(f"Can't search {video.video_id} ({video.name}) in random")
                    traceback.print_exc()
        if ctx.author.voice is None:
            return await ctx.send(embed=create_embed(title="Erreur", description="Tu n'es pas dans un channel vocal."), ephemeral=True)
        match _type:
            case "next":
                return await ctx.reply(embed=create_embed(title="Musique", description=f"La musique `{video.name}` (**{video.pos}**) été ajoutée en haut de la queue !"))
            case "music":
                return await ctx.reply(embed=create_embed(title="Musique", description=f"La musique `{video.name}` (**{video.pos}**) été ajoutée à la queue !"))
            case "random":
                return await ctx.reply(embed=create_embed(title="Musique", description=f"{random_nb} musiques aléatoires ont été ajoutées à la queue !"))
    except Exception as e:
        LogErrorInWebhook()
        print(e)

async def setup(bot):
    await bot.add_cog(Music(bot))