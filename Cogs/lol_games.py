import discord, os, datetime, io, traceback, asyncio, difflib
from discord.ext import commands, tasks
from typing import TYPE_CHECKING, Tuple, List
from PIL import ImageDraw, ImageFont, Image
from .utils.functions import afficher_nombre_fr, display_big_nums, LogErrorInWebhook, calc_usr_gain_by_tier, getVar, command_counter
from .utils.path import LOL_IMAGE, LOL_FONT, FILES_PATH, LOL_IMAGE_ARENA 
from bot import Trapard

def get_riot_api_headers():
    """Returns the headers for the HTTP request to the League of Legends API."""
    return {
        "Accept": "application/json",
        "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Charset": "application/x-www-form-urlencoded; charset=UTF-8",
        "Content-Type": "application/json",
        "X-Riot-Token": getVar("RIOT_API")
    }

async def get_puuid_by_name(ign: str, gameTag:str, bot: Trapard):
    """Fetches the PUUID of a League of Legends summoner using their in-game name and game tag.
        gameTag (str): The game tag associated with the summoner.
        bot (Trapard): The bot instance containing the HTTP session.
    Returns:
        str or None: The PUUID of the summoner if found, otherwise None.
    Raises:
        Logs exceptions internally and returns None if an error occurs during the request or response parsing.
    """
    try:
        summoner_url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{ign}/{gameTag}"
        async with bot.session.get(summoner_url, headers=get_riot_api_headers()) as summoner_response:
            summoner_data = await summoner_response.json()
        if "puuid" not in summoner_data:
            print(summoner_data, "No puuid", ign, gameTag, summoner_url)
            return None
        return summoner_data["puuid"]
    except Exception as e:
        LogErrorInWebhook(error=f"[GET PUUID BY NAME] {e} NAME={ign}, response = {summoner_data}, url = {summoner_url}")
        return None

class Mastery:
    async def get_all_mastery(puuid: str, region: str, bot: Trapard):
        """
        Get all the mastery of a user from a **puuid** and a region from the **database**
        """
        try:
            if region == "euw": region += "1"
            summoner_url = f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
            async with bot.session.get(summoner_url, headers=get_riot_api_headers()) as summoner_response:
                summoner_data = await summoner_response.json()
            return summoner_data
        except Exception as e:
            LogErrorInWebhook(error=f"[GET ALL MASTERY] {e} NAME={puuid}, response = {summoner_data}, url = {summoner_url}")
            return None

    async def update_user_mastery(mastery: dict, bot: Trapard):
        """
            Update the mastery of a user in the **database** from a **mastery** dictionary
        """
        try:
            async with bot.pool.acquire() as conn:
                await conn.execute("UPDATE LoLGamesTracker SET champions_mastery = ? WHERE puuid = ?", str(mastery), mastery[0]["puuid"])
        except Exception as e:
            LogErrorInWebhook(error=f"[UPDATE USER MASTERY] {e} NAME={mastery[0]['puuid']}")
            return None

    async def get_champion_mastery(puuid: str, region: str, champion_id: int, bot: Trapard):
        """
        Get the mastery of a **specific champion** for a user from a **puuid** and a region from the **database**
        """
        try:
            async with bot.pool.acquire() as conn:
                data = await conn.fetchone("SELECT champions_mastery FROM LoLGamesTracker WHERE puuid = ?", puuid)
            if not data:
                return None
            print(data)
            mastery = eval(data[0])
            for champ in mastery:
                if champ["championId"] == champion_id:
                    return dict(champ)
            return None
        except Exception as e:
            LogErrorInWebhook(error=f"[GET CHAMPION MASTERY] {e} NAME={puuid}")
            return None

class GameLink(discord.ui.View):
    def __init__(self, link: str="N/A", embed=None):
        super().__init__(timeout=None)
        self.embed = embed
        self.add_item(discord.ui.Button(label="Voir plus", url=link))

    @discord.ui.button(label='Trapcoins', style=discord.ButtonStyle.green, custom_id="gain")
    async def gains(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.embed:
            await interaction.response.send_message(embed=self.embed, ephemeral=True)
        else:
            await interaction.response.send_message("Malheureusement, ce bouton n'est plus disponible.", ephemeral=True)

class LolGames(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
        self.check_lol_games.start()

    @tasks.loop(seconds=300)
    async def check_lol_games(self):
        try:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT id, userId, ign, puuid, region, last_game_id FROM LoLGamesTracker")

            if self.bot.debug:
                for row in data:
                    print(dict(row))

            def draw_game(pseudo: str, rank: str, gameMode: str, championIcon, lvl: str, rune, sums1, sums2, status: str, time: int, kda: str, text1: str, text2: str, items: list, players: list, results: list, bans: list, mentions: str):
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

                def remove_white_background(image: Image.Image):

                    # Convertir l'image en mode RGBA (ajoute un canal alpha pour la transparence)
                    image = image.convert("RGBA")

                    # Obtenir les données de l'image sous forme de liste de tuples (r, g, b, a)
                    data = image.getdata()

                    # Créer une nouvelle liste de données en rendant transparentes les pixels blancs
                    new_data = []
                    for item in data:
                        # Si le pixel est blanc, le rendre transparent (alpha = 0)
                        if item[:3] == (255, 255, 255):
                            new_data.append((255, 255, 255, 0))
                        else:
                            new_data.append(item)

                    # Mettre à jour les données de l'image
                    image.putdata(new_data)

                    return image

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

                img = Image.open(LOL_IMAGE)

                # Images
                if championIcon:
                    avatar = add_corners(championIcon, 10).resize((100, 100))
                    img.paste(avatar, (62, 129+72), avatar) # Champion Icon

                if sums1:
                    summoner1 = add_corners(sums1, 10).resize((31, 31))
                    img.paste(summoner1, (99, 235+72), summoner1) # Summoner 1

                if sums2:
                    summoner2 = add_corners(sums2, 10).resize((31, 31))
                    img.paste(summoner2, (132, 235+72), summoner2) # Summoner 2

                if rune:
                    rune = remove_white_background(rune).resize((35, 35))
                    img.paste(rune, (62, 234+70), rune) # Rune
                
                if items[0]:
                    item1 = add_corners(items[0], 10).resize((35, 35))
                    img.paste(item1, (241, 256), item1) # Item 1
                if items[1]:
                    item2 = add_corners(items[1], 10).resize((35, 35))
                    img.paste(item2, (281, 256), item2) # Item 2
                if items[2]:
                    item3 = add_corners(items[2], 10).resize((35, 35))
                    img.paste(item3, (321, 256), item3) # Item 3
                if items[3]:
                    item4 = add_corners(items[3], 10).resize((35, 35))
                    img.paste(item4, (241, 300), item4) # Item 4
                if items[4]:
                    item5 = add_corners(items[4], 10).resize((35, 35))
                    img.paste(item5, (281, 300), item5) # Item 5
                if items[5]:
                    item6 = add_corners(items[5], 10).resize((35, 35))
                    img.paste(item6, (321, 300), item6) # Item 6
                if items[6]:
                    item7 = add_corners(items[6], 10).resize((35, 35))
                    img.paste(item7, (361, 300), item7) # Item 7


                # Defining draw
                draw = ImageDraw.Draw(img)
                font = ImageFont.truetype(LOL_FONT, 18)
                fontSmall = ImageFont.truetype(LOL_FONT, 15)
                fontSmall2 = ImageFont.truetype(LOL_FONT, 12)
                fontSmall3 = ImageFont.truetype(LOL_FONT, 10)

                smalll = ImageFont.truetype(LOL_FONT, 8)
                smalll2 = ImageFont.truetype(LOL_FONT, 7)

                # Pseudo
                if pseudo:
                    draw_text(draw, pseudo, (35, 20+70), (155, 28), font, "white")

                # Rank
                if rank:
                    draw_text(draw, rank, (34, 34+72), (165, 80), fontSmall, "white")

                # GameMode
                if gameMode:
                    draw_text(draw, gameMode, (30, 68+71), (175, 90), fontSmall2, "white")

                # Level
                if lvl:
                    draw_text(draw, str(lvl), (36, 289), (30, 30), fontSmall2, "white")
                # draw_text(draw, lvl, (38, 217), (30, 30), fontSmall2, "white")

                # Status
                if status:
                    draw_text(draw, status, (303, 32+71), (30, 30), font, f'green' if status == 'Victoire' else 'red')

                # Time
                if time:
                    draw_text(draw, time, (303, 68+72), (30, 30), fontSmall3, "white")

                # KDA
                if kda:
                    draw_text(draw, kda, (303, 92+71), (30, 30), fontSmall3, "white")

                # Text1
                if text1:
                    draw_text(draw, text1, (303, 116+70), (30, 30), fontSmall3, "white")

                # Text2
                if text2:
                    draw_text(draw, text2, (303, 137+72), (30, 30), fontSmall3, "white")



                ###############################
                ##TEMP PLAYER1 USE LOOP LATER #
                ###############################
                # Images

                # Team 1
                if results[0]:
                    draw_text(draw, results[0], (35+422+67, 18), (155, 28), font, "green" if results[0] == 'Victoire' else 'red')
                h_step = 65
                for i, player in enumerate(players):
                    if i > 4:
                        break
                    if player["championIcon"]:
                        avatar = add_corners(player["championIcon"], 10).resize((35, 35))
                        img.paste(avatar, (464, 63+(h_step*i)), avatar) # Champion Icon
                    # avatar = add_corners(championIcon, 10).resize((100, 100))
                    # img.paste(avatar, (62, 129+72), avatar) # Champion Icon

                    if player["sums"][0]:
                        summoner1 = add_corners(player["sums"][0], 10).resize((12, 12))
                        img.paste(summoner1, (475, 101+(h_step*i)), summoner1) # Summoner 1
                    
                    if player["sums"][1]:
                        summoner2 = add_corners(player["sums"][1], 10).resize((12, 12))
                        img.paste(summoner2, (475+13, 101+(h_step*i)), summoner2) # Summoner 2

                    if player["rune"]:
                        rune = remove_white_background(player["rune"]).resize((12, 12))
                        img.paste(rune, (475-13, 101+(h_step*i)), rune) # Rune
                    if player["items"][0]:
                        item1 = add_corners(player["items"][0], 10).resize((16, 17))
                        img.paste(item1, (651, 63+(h_step*i)), item1) # Item 1
                    if player["items"][1]:
                        item2 = add_corners(player["items"][1], 10).resize((16, 17))
                        img.paste(item2, (651+19, 63+(h_step*i)), item2) # Item 2
                    if player["items"][2]:
                        item3 = add_corners(player["items"][2], 10).resize((16, 17))
                        img.paste(item3, (651+19+19, 63+(h_step*i)), item3) # Item 3
                    if player["items"][3]:
                        item4 = add_corners(player["items"][3], 10).resize((16, 17))
                        img.paste(item4, (651, 63+20+(h_step*i)), item4) # Item 4
                    if player["items"][4]:
                        item5 = add_corners(player["items"][4], 10).resize((16, 17))
                        img.paste(item5, (651+19, 63+20+(h_step*i)), item5) # Item 5
                    if player["items"][5]:
                        item6 = add_corners(player["items"][5], 10).resize((16, 17))
                        img.paste(item6, (651+19+19, 63+20+(h_step*i)), item6) # Item 6
                    if player["items"][6]:
                        item7 = add_corners(player["items"][6], 10).resize((16, 17))
                        img.paste(item7, (651+19+19+19, 63+20+(h_step*i)), item7) # Item 7

                    # Pseudo
                    if len(player["pseudo"]) > 7:
                        draw_text(draw, player["pseudo"], (35+422, 90-26+(h_step*i)), (155, 28), smalll2, "white")
                    else:
                        draw_text(draw, player["pseudo"], (35+422, 90-26+(h_step*i)), (155, 28), smalll, "white")

                    # Rank
                    if player["rank"]:
                        draw_text(draw, player["rank"], (34+420, 34+50-27+(h_step*i)), (165, 80), smalll, "white")

                    # Level
                    if player["lvl"]:
                        draw_text(draw, str(player["lvl"]), (443, 92+(h_step*i)), (30, 30), smalll2, "white")
                    # draw_text(draw, lvl, (38, 217), (30, 30), fontSmall2, "white")

                    # KDA
                    if player["kda"]:
                        draw_text(draw, player["kda"], (595, 60+(h_step*i)), (30, 30), smalll, "white")

                    # Text1
                    if player["text1"]:
                        draw_text(draw, player["text1"], (595, 74+(h_step*i)), (30, 30), smalll, "white")

                    # Text2
                    if player["text2"]:
                        draw_text(draw, player["text2"], (595, 88+(h_step*i)), (30, 30), smalll, "white")

                # Team 2
                if results[1]:
                    draw_text(draw, results[1], (35+422+67+275, 18), (155, 28), font, "green" if results[1] == 'Victoire' else 'red')
                for i, player in enumerate(players):
                    if i < 5:
                        continue
                    if player["championIcon"]:
                        avatar = add_corners(player["championIcon"], 10).resize((35, 35))
                        img.paste(avatar, (464+267+259, 63+(h_step*(i-5))), avatar) # Champion Icon
                    # avatar = add_corners(championIcon, 10).resize((100, 100))
                    # img.paste(avatar, (62, 129+72), avatar) # Champion Icon

                    if player["sums"][0]:
                        summoner1 = add_corners(player["sums"][0], 10).resize((12, 12))
                        img.paste(summoner1, (475+526, 101+(h_step*(i-5))), summoner1) # Summoner 1
                    
                    if player["sums"][1]:
                        summoner2 = add_corners(player["sums"][1], 10).resize((12, 12))
                        img.paste(summoner2, (475+526-13, 101+(h_step*(i-5))), summoner2) # Summoner 2

                    if player["rune"]:
                        rune = remove_white_background(player["rune"]).resize((12, 12))
                        img.paste(rune, (475+526+13, 101+(h_step*(i-5))), rune) # Rune

                    if player["items"][0]:
                        item1 = add_corners(player["items"][0], 10).resize((16, 17))
                        img.paste(item1, (821, 63+(h_step*(i-5))), item1) # Item 1
                    if player["items"][1]:
                        item2 = add_corners(player["items"][1], 10).resize((16, 17))
                        img.paste(item2, (821-19, 63+(h_step*(i-5))), item2) # Item 2
                    if player["items"][2]:
                        item3 = add_corners(player["items"][2], 10).resize((16, 17))
                        img.paste(item3, (821-19-19, 63+(h_step*(i-5))), item3) # Item 3
                    if player["items"][3]:
                        item4 = add_corners(player["items"][3], 10).resize((16, 17))
                        img.paste(item4, (821, 63+20+(h_step*(i-5))), item4) # Item 4
                    if player["items"][4]:
                        item5 = add_corners(player["items"][4], 10).resize((16, 17))
                        img.paste(item5, (821-19, 63+20+(h_step*(i-5))), item5) # Item 5
                    if player["items"][5]:
                        item6 = add_corners(player["items"][5], 10).resize((16, 17))
                        img.paste(item6, (821-19-19, 63+20+(h_step*(i-5))), item6) # Item 6
                    if player["items"][6]:
                        item7 = add_corners(player["items"][6], 10).resize((16, 17))
                        img.paste(item7, (821-19-19-19, 63+20+(h_step*(i-5))), item7) # Item 7

                    # Pseudo
                    if len(player["pseudo"]) > 7:
                        draw_text(draw, player["pseudo"], (35+422+267+150, 90-26+(h_step*(i-5))), (155, 28), smalll2, "white")
                    else:
                        draw_text(draw, player["pseudo"], (35+422+267+150, 90-26+(h_step*(i-5))), (155, 28), smalll, "white")

                    # Rank
                    if player["rank"]:
                        draw_text(draw, player["rank"], (34+420+267+150, 34+50-27+(h_step*(i-5))), (165, 80), smalll, "white")

                    # Level
                    if player["lvl"]:
                        draw_text(draw, str(player["lvl"]), (443+267+304, 92+(h_step*(i-5))), (30, 30), smalll2, "white")
                    # draw_text(draw, lvl, (38, 217), (30, 30), fontSmall2, "white")

                    # KDA
                    if player["kda"]:
                        draw_text(draw, player["kda"], (595+267, 60+(h_step*(i-5))), (30, 30), smalll, "white")

                    # Text1
                    if player["text1"]:
                        draw_text(draw, player["text1"], (595+267, 74+(h_step*(i-5))), (30, 30), smalll, "white")

                    # Text2
                    if player["text2"]:
                        draw_text(draw, player["text2"], (862, 88+(h_step*(i-5))), (30, 30), smalll, "white")

                l_step = 30
                sep = 108
                for i, ban in enumerate(bans):
                    if i < 5:
                        if ban:
                            try:
                                ban = ban.resize((26, 26))
                                img.paste(ban, (62+422+70+26+(l_step*i), 400-7), ban)
                            except: continue
                    else:
                        if ban:
                            try:
                                ban = ban.resize((26, 26))
                                img.paste(ban, (62+422+70+26+sep+(l_step*i), 400-7), ban)
                            except: continue
                # Saving image
                fp = io.BytesIO()
                img.convert("RGBA").save(fp, "PNG")
                img.save(f"{FILES_PATH}{mentions}-game.png")
                return
            
            def draw_swarm(players: List[dict], gamedata: dict):
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
                try:
                    FONT = ImageFont.truetype(LOL_FONT)
                    img = Image.open(f"{FILES_PATH}swarm{len(players)}.png")
                    draw = ImageDraw.Draw(img)

                    vert_decay = 202

                    # draw game info
                    if gamedata["winned"]:
                        draw_text(draw, "Victoire", (220, 22), (0, 40), ImageFont.truetype(FONT, 40), "green")
                    else:
                        draw_text(draw, "Défaite", (220, 22), (0, 40), ImageFont.truetype(FONT, 40), "red")

                    draw_text(draw, f"Durée: {minutes_to_time(gamedata['duration'])}", (425, 22), (0, 40), ImageFont.truetype(FONT, 40), "white")

                    draw_text(draw, f"Map: {gamedata['map']}", (725, 22), (0, 40), ImageFont.truetype(FONT, 40), "white")

                    # draw players
                    for p_i, player in enumerate(players):
                        player["championIcon"] = player["championIcon"].convert("RGBA")
                        player["championIcon"] = add_corners(player["championIcon"], 15)
                        player["championIcon"] = player["championIcon"].resize((115, 115), Image.LANCZOS)
                        img.paste(player["championIcon"], (57, 125+(vert_decay*p_i)), player["championIcon"])

                        draw_text(draw, player["pseudo"], (200, 122+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        draw_text(draw, f"{player['ig_lvl']}", (23, 216+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 29), "white")

                        draw_text(draw, f"{afficher_nombre_fr(player['gold_earned'])}", (265, 171+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        draw_text(draw, f"{afficher_nombre_fr(player['unit_killed'])}", (495, 120+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        draw_text(draw, f"{afficher_nombre_fr(player['dmg_dealt'])}", (710, 119+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        draw_text(draw, f"{afficher_nombre_fr(player['dmg_taken'])}", (710, 170+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        draw_text(draw, f"{player['deaths']}", (525, 170+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        draw_text(draw, f"{afficher_nombre_fr(player['heal'])}", (710, 221+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                        print(player["items"])
                        for i, item in enumerate(player["items"]):
                            if item:
                                item = item.convert("RGBA")
                                item = add_corners(item, 15)
                                item = item.resize((50, 50), Image.LANCZOS)
                                img.paste(item, (192 + 53 * i, 236+(vert_decay*p_i)), item)

                    fp = io.BytesIO()
                    img.convert("RGBA").save(fp, "PNG")
                    img.save(f"{FILES_PATH}swarm_output.png")
                    return f"{FILES_PATH}swarm_output.png"
                except Exception as e:
                    LogErrorInWebhook(error=f"[DRAW SWARM] {e}")
                    print(e)
                    return None

            def draw_arena(player: dict):
                def draw_text(draw: ImageDraw.ImageDraw, text: str, coordinates: Tuple[int, int], box_size: Tuple[int, int], font: ImageFont.FreeTypeFont, fill: str) -> None:
                    text_width, text_height = draw.textlength(text, font=font), 24
                    x = coordinates[0]
                    y = int(coordinates[1] + (box_size[1] - text_height) // 2)
                    
                    draw.text(
                        (x, y),
                        text,
                        font=font,
                        fill=fill
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
                
                FONT = LOL_FONT
                img = Image.open(LOL_IMAGE_ARENA)
                draw = ImageDraw.Draw(img)

                # draw player name
                if player["riotIdGameName"]:
                    draw_text(draw, player["riotIdGameName"], (53, 79), (0, 40), ImageFont.truetype(FONT, 22), "white")

                # draw kda
                if player["kills"] and player["deaths"] and player["assists"]:
                    draw_text(draw, f"{player['kills']}/{player['deaths']}/{player['assists']}", (385, 80), (0, 40), ImageFont.truetype(FONT, 22), "white")
                    ratio = round((player["kills"] + player["assists"]) / max(1, player["deaths"]), 2)
                    draw_text(draw, f"{ratio} KDA", (375, 80+38), (0, 40), ImageFont.truetype(FONT, 22), "white")

                # draw damage dealt
                if player["dmg_dealt"]:
                    draw_text(draw, f"{afficher_nombre_fr(player['dmg_dealt'])} DMG", (355, 80+76), (0, 40), ImageFont.truetype(FONT, 22), "white")

                # draw position
                position_data = {
                    1: ("#FFD700", "st"),
                    2: ("#C0C0C0", "nd"),
                    3: ("#CD7F32", "rd"),
                    4: ("#4CAF50", "th"),
                    5: ("#2196F3", "th"),
                    6: ("#FF9800", "th"),
                    7: ("#9C27B0", "th"),
                    8: ("#F44336", "th"),
                }
                pos = max(1, min(player["PlayerScore0"], 8))
                color, suffix = position_data[pos]
                if player["PlayerScore0"]:
                    draw_text(draw, f"{player['PlayerScore0']}{suffix}", (103, 268), (0, 40), ImageFont.truetype(FONT, 48), color)

                # draw items
                for i, item in enumerate(player["items"]):
                    if not item:
                        continue
                    item = item.convert("RGBA")
                    if i == 6:
                        item = add_corners(item, 35)
                    else:
                        item = add_corners(item, 15)
                    item = item.resize((40, 40), Image.LANCZOS)
                    if i < 3:
                        img.paste(item, (335 + 47 * i, 230), item)
                    else:
                        img.paste(item, (335 + 47 * (i-4)+46, 281), item)

                # draw champion icon
                if player["championIcon"]:
                    player["championIcon"] = player["championIcon"].convert("RGBA")
                    player["championIcon"] = add_corners(player["championIcon"], 15)
                    player["championIcon"] = player["championIcon"].resize((115, 115), Image.LANCZOS)
                    img.paste(player["championIcon"], (57, 141), player["championIcon"])

                if player["mate_championIcon"]:
                    player["mate_championIcon"] = player["mate_championIcon"].convert("RGBA")
                    player["mate_championIcon"] = add_corners(player["mate_championIcon"], 15)
                    player["mate_championIcon"] = player["mate_championIcon"].resize((55, 55), Image.LANCZOS)
                    img.paste(player["mate_championIcon"], (179, 187), player["mate_championIcon"])

                # save image
                fp = io.BytesIO()
                img.convert("RGBA").save(fp, "PNG")
                img.save(f"{FILES_PATH}arena_output.png")
                return f"{FILES_PATH}arena_output.png"

            def rang_le_plus_eleve(liste_rangs):
                rangs_possibles = [
                    'iron IV', 'iron III', 'iron II', 'iron I',
                    'bronze IV', 'bronze III', 'bronze II', 'bronze I',
                    'silver IV', 'silver III', 'silver II', 'silver I',
                    'gold IV', 'gold III', 'gold II', 'gold I',
                    'platinium IV', 'platinium III', 'platinium II', 'platinium I',
                    'emerald IV', 'emerald III', 'emerald II', 'emerald I',
                    'diamond IV', 'diamond III', 'diamond II', 'diamond I',
                    'master', 'grandmaster', 'challenger'
                ]

                if not liste_rangs:
                    return None
                rangs_possibles = sorted(rangs_possibles, key=lambda x: rangs_possibles.index(x), reverse=True)

                for rang in rangs_possibles:
                    if rang in liste_rangs:
                        return rang

                return None
            
            async def get_user_rank(puuid: str, region="euw1"):
                if region == "euw":
                    region = "euw1"
                if region != "euw1":
                    region = "oc1"
                # Requête pour obtenir les informations de classement du summoner
                ranking_url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
                async with self.bot.session.get(ranking_url, headers=get_riot_api_headers()) as ranking_response:
                    ranking_data = await ranking_response.json()
                ranks = []
                for i in ranking_data:
                    if "tier" in i and "rank" in i:
                        ranks.append(f"{i['tier'].lower()} {i['rank']}")
                if len(ranks) > 1:
                    return rang_le_plus_eleve(ranks)
                elif len(ranks) == 0:
                    return "Non classé"
                else: return ranks[0].title()

            async def get_last_matchs(player_uuid, region):
                if region == "oc1": subdom = "sea"
                else: subdom = "europe"
                resp = await self.bot.session.get(f"https://{subdom}.api.riotgames.com/lol/match/v5/matches/by-puuid/{player_uuid}/ids?start=0&count=2", headers=get_riot_api_headers())
                try: data = await resp.json()
                except Exception:
                    text = await resp.text()
                    LogErrorInWebhook(error=f"[LOL] Erreur lors de la récupération des dernières parties de {player_uuid} | réponse code : {resp.status} | réponse: {text}")
                    return None
                try: return data[0]
                except: return None

            async def getSumsByID(id: int, api_version: str):
                async with self.bot.session.get(f"https://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/summoner.json") as response:
                    data = await response.json()
                    for summ in data["data"]:
                        if data["data"][summ]["key"] == str(id):
                            async with self.bot.session.get(f"http://ddragon.leagueoflegends.com/cdn/{api_version}/img/spell/{data['data'][summ]['image']['full']}") as response2:
                                response2.raise_for_status()
                                data2 = await response2.read()
                            return Image.open(io.BytesIO(data2))
            
            async def getLastVersion():
                async with self.bot.session.get(f"https://ddragon.leagueoflegends.com/api/versions.json") as response:
                    data = await response.json()
                    return data[0]
            
            async def getQueueByID(id: int):
                async with self.bot.session.get(f"https://static.developer.riotgames.com/docs/lol/queues.json") as response:
                    data = await response.json()
                    for queue in data:
                        if queue["queueId"] == id:
                            return queue["description"]
                    return "Mode de jeu inconnu"

            async def get_match_data(matchid, player_uuid, region):
                if region == "oc1": subdom = "sea"
                else: subdom = "europe"
                reponse = await self.bot.session.get(f"https://{subdom}.api.riotgames.com/lol/match/v5/matches/{matchid}", headers=get_riot_api_headers())
                if reponse.status != 200:
                    if reponse.status != 403: # Waiting brawl returning 403, remove this later
                        LogErrorInWebhook(error=f"[LOL] Erreur lors de la récupération des données de la partie : {reponse.status}")
                    return None

                data = await reponse.json()
                
                try: participants = data["info"]["participants"]
                except: return None
                for index, p in enumerate(participants):
                    if player_uuid == p["puuid"]:
                        player_position = index
                        break
                
                player_data = participants[player_position]
                game_duartion = data["info"]["gameDuration"]
                game_creation = data["info"]["gameCreation"]
                return player_data, game_duartion, game_creation, data["info"]["queueId"], data

            def is_s(inte):
                if inte >= 2:
                    return 's'
                else:
                    return''

            async def calculate_gain(game_data, game_duartion, userid):

                text_data = ""
                texte_to_send = None
                trapcoins_emoji = "<:trapcoins:1108725845339672597>"
                user_balance, _ = await self.bot.trapcoin_handler.get(userid=int(userid))
                if game_data["win"] == True:
                    base_gain = 50000
                    text_data += f"- Victoire: 50 000 {str(trapcoins_emoji)}\n"
                    if int(userid) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(userid)] is not None:
                        if self.bot.lol_bet_dict[int(userid)][0] == "Gagner":
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                await self.bot.trapcoin_handler.add(userid=int(userid), amount=int(self.bot.lol_bet_dict[int(userid)][1]), wallet="trapcoins")
                                texte_to_send = f"- 🤑 Tu as gagné **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Victoire**!"
                            else:
                                texte_to_send = f"- Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\nTu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Victoire**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            self.bot.lol_bet_dict[int(userid)] = None
                        else:
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                await self.bot.trapcoin_handler.remove(userid=int(userid), amount=int(self.bot.lol_bet_dict[int(userid)][1]), wallet="trapcoins")
                                texte_to_send = f"💸 - Tu as perdu **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Défaite** alors que tu as gagné!\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            else:
                                texte_to_send = f"Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\nTu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Défaite**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            self.bot.lol_bet_dict[int(userid)] = None

                if game_data["win"] == False:
                    base_gain = 0
                    if int(userid) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(userid)] is not None:
                        if self.bot.lol_bet_dict[int(userid)][0] == "Perdu":
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                await self.bot.trapcoin_handler.add(userid=int(userid), amount=int(self.bot.lol_bet_dict[int(userid)][1]), wallet="trapcoins")
                                texte_to_send = f"🤑 - Tu as gagné **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Défaite**!\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            else:
                                texte_to_send = f"- Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\n- Tu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Défaite**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            self.bot.lol_bet_dict[int(userid)] = None
                        else:
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                await self.bot.trapcoin_handler.remove(userid=int(userid), amount=int(self.bot.lol_bet_dict[int(userid)][1]), wallet="trapcoins")
                                texte_to_send = f"💸 - Tu as perdu **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Victoire** alors que tu as perdu!\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            else:
                                texte_to_send = f"Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\nTu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Victoire**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            self.bot.lol_bet_dict[int(userid)] = None
                
                pings = game_data["allInPings"] + game_data ["assistMePings"] + game_data["baitPings"] + game_data["basicPings"] + game_data["commandPings"] + game_data['dangerPings'] + game_data["enemyMissingPings"] + game_data["enemyVisionPings"] + game_data["getBackPings"] + game_data["holdPings"] + game_data['needVisionPings'] + game_data["pushPings"] + game_data['visionClearedPings'] + game_data["onMyWayPings"]
                if pings > 0:
                    pings_calc = pings * 200
                    base_gain += pings
                    text_data += f"- Ping {pings} fois: {afficher_nombre_fr(pings_calc)} {str(trapcoins_emoji)}\n"
                
                if game_data["kills"] > 0:
                    kills_calc = game_data["kills"] * 3000
                    base_gain += kills_calc
                    text_data += f'- {game_data["kills"]} Kill{is_s(game_data["kills"])}: {afficher_nombre_fr(kills_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["assists"] > 0:
                    assists_calc = game_data["assists"] * 2000
                    base_gain += assists_calc
                    text_data += f"- {game_data['assists']} Assistance{is_s(game_data['assists'])}: {afficher_nombre_fr(assists_calc)} {str(trapcoins_emoji)}\n"
                if game_data["pentaKills"] > 0:
                    penta_calc = game_data["pentaKills"] * 50000
                    base_gain += penta_calc
                    text_data += f"- {game_data['pentaKills']} Penta kills: {afficher_nombre_fr(penta_calc)} {str(trapcoins_emoji)}\n"
                
                if game_data["quadraKills"] > 0:
                    quadra_calc = game_data["quadraKills"] * 40000
                    base_gain += quadra_calc
                    text_data += f'- {game_data["quadraKills"]} Quadra kills: {afficher_nombre_fr(quadra_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["tripleKills"] > 0:
                    triple_calc = game_data["tripleKills"] * 30000
                    base_gain += triple_calc
                    text_data += f'- {game_data["tripleKills"]} Triple kills: {afficher_nombre_fr(triple_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["doubleKills"] > 0:
                    double_calc = game_data["doubleKills"] * 20000
                    base_gain += double_calc
                    text_data += f'- {game_data["doubleKills"]} Double kills: {afficher_nombre_fr(double_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["visionScore"] > 0:
                    vision_calc = game_data["visionScore"] * 1500
                    base_gain += vision_calc
                    text_data += f'- {game_data["visionScore"]} Score de vision: {afficher_nombre_fr(vision_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["visionWardsBoughtInGame"] > 0:
                    control_ward_calc = game_data["visionWardsBoughtInGame"] * 1000
                    base_gain += control_ward_calc
                    text_data += f'- {game_data["visionWardsBoughtInGame"]} Control ward acheté: {afficher_nombre_fr(control_ward_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["turretTakedowns"] > 0:
                    turret_calc = game_data["turretTakedowns"] * 5000
                    base_gain += turret_calc
                    text_data += f'- {game_data["turretTakedowns"]} Tour détruites: {afficher_nombre_fr(turret_calc)} {str(trapcoins_emoji)}\n'
                
                game_duartion_to_min = game_duartion / 60
                cs_min = game_data["totalMinionsKilled"] / game_duartion_to_min
                if cs_min >= 10:
                    base_gain += 100000
                    text_data += f"- 10 Cs/min: 100 000 {str(trapcoins_emoji)}\n"
                elif cs_min < 10 and cs_min >= 9:
                    base_gain += 75000
                    text_data += f"- 9 Cs/min: 75 000 {str(trapcoins_emoji)}\n"
                elif cs_min < 9 and cs_min >= 8:
                    base_gain += 50000
                    text_data += f"- 8 Cs/min: 50 000 {str(trapcoins_emoji)}\n"
                elif cs_min < 8 and cs_min >= 7:
                    base_gain += 25000
                    text_data += f"- 7 Cs/min: 25 000 {str(trapcoins_emoji)}\n"
                
                spells_cast = game_data["spell1Casts"] + game_data["spell2Casts"] + game_data["spell3Casts"] + game_data["spell4Casts"]
                spells_cast_calc = spells_cast * 100
                base_gain += spells_cast_calc
                text_data += f"- {spells_cast} Sorts invoqués: {afficher_nombre_fr(spells_cast_calc)} {str(trapcoins_emoji)}\n"
                
                if game_data["win"] and game_data["gameEndedInEarlySurrender"]:
                    base_gain += 50000
                    text_data += f"- Ennemi early ff: 50 000 {str(trapcoins_emoji)}\n"
                
                if game_data["firstBloodKill"]:
                    base_gain += 15000
                    text_data += f"- First blood: 15 000 {str(trapcoins_emoji)}\n"
                
                if game_data["firstTowerKill"]:
                    base_gain += 10000
                    text_data += f"- First tower: 10 000 {str(trapcoins_emoji)}\n"

                base_gain += game_data["goldEarned"]
                text_data += f'- Gold gagné: {afficher_nombre_fr(game_data["goldEarned"])} {str(trapcoins_emoji)}\n'

                if game_data["objectivesStolen"] > 0:
                    obj_stole_calc = game_data["objectivesStolen"] * 50000
                    base_gain += obj_stole_calc
                    text_data += f'- {game_data["objectivesStolen"]} Objectif volé: {afficher_nombre_fr(obj_stole_calc)} {str(trapcoins_emoji)}\n'
                
                if game_data["totalEnemyJungleMinionsKilled"] > 0:
                    jg_stolen_calc = game_data["totalEnemyJungleMinionsKilled"] * 5000
                    base_gain += jg_stolen_calc
                    text_data += f'- {game_data["totalEnemyJungleMinionsKilled"]} Camps jg volé: {afficher_nombre_fr(jg_stolen_calc)} {str(trapcoins_emoji)}\n'

                champ_lvl_calc = game_data["champLevel"] * 100
                base_gain += champ_lvl_calc
                text_data += f'- Level {game_data["champLevel"]} du champion: {afficher_nombre_fr(champ_lvl_calc)} {str(trapcoins_emoji)}\n'

                if game_data["role"] == "JUNGLE":
                    base_gain += 5000
                    text_data += f"- Rôle Jungle compensation mental: 5 000 {str(trapcoins_emoji)}\n"

                if game_data["role"] == "SUPPORT":
                    base_gain += 5000
                    text_data += f"- Rôle Support compensation mental: 5 000 {str(trapcoins_emoji)}\n"
                
                if game_data["teamEarlySurrendered"]:
                    base_gain = base_gain * 0.5
                    text_data += "- Early FF: Gain divisés par deux !\n"

                return base_gain, text_data, game_data['riotIdGameName'], texte_to_send
            
            async def getRuneIcon(runeId: int, api_version: str) -> str:
                RUNES_BASE_URL = 'http://ddragon.leagueoflegends.com/cdn/img/'
                async with self.bot.session.get(f'http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/runesReforged.json') as response:
                    data = await response.json()
                url = None
                for rune_tree in data:
                    if rune_tree['id'] == runeId:
                        url = RUNES_BASE_URL + rune_tree['icon']
                        break
                    for slot in rune_tree['slots']:
                        for rune in slot['runes']:
                            if rune['id'] == runeId:
                                url = RUNES_BASE_URL + rune['icon']
                                break
                if url:
                    async with self.bot.session.get(url) as data:
                        data.raise_for_status
                        content = await data.read()
                    return Image.open(io.BytesIO(content))
                return None
            
            async def getChampionIconByID(championID: int, api_version) -> io.BytesIO:
                url = f"http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/champion.json"
                async with self.bot.session.get(url) as response:
                    data = await response.json()
                    for champ in data["data"]:
                        if data["data"][champ]["key"] == str(championID):
                            return await getChampionIcon(data["data"][champ]["image"]["full"].replace(".png", ""), api_version)
                    return None

            async def getItemIcon(itemId: int, api_version) -> io.BytesIO:
                if itemId == 0:
                    return None
                ITEMS_BASE_URL = f'http://ddragon.leagueoflegends.com/cdn/{api_version}/img/item/'
                async with self.bot.session.get(f"{ITEMS_BASE_URL}{itemId}.png", ssl=False) as response:
                    response.raise_for_status()
                    data = await response.read()
                return Image.open(io.BytesIO(data))
            
            async def getChampionIcon(championName: str, api_version) -> io.BytesIO:

                async with self.bot.session.get(f'http://ddragon.leagueoflegends.com/cdn/{api_version}/img/champion/{championName}.png', ssl=False) as response:
                    response.raise_for_status()
                    champion_icon_data = await response.read()
                return Image.open(io.BytesIO(champion_icon_data)).convert("RGBA")
            
            async def get_drawing_data(game_data, game_duartion, userid, queuetype, raw_data, puuid, region, api_version):
                pseudo = game_data["riotIdGameName"]
                rank = await get_user_rank(puuid, region)

                if game_data["win"] == True:
                    games_status = "Victoire"
                else:
                    games_status = "Défaite"
                game_duartion_to_min = f'{game_duartion // 60} minute{"s" if game_duartion // 60 > 1 else ""}'
                
                kda = f'{game_data["kills"]}/{game_data["deaths"]}/{game_data["assists"]}'
                

                champion_icon = await getChampionIconByID(game_data["championId"], api_version)
                
                lvl = game_data["champLevel"]
                
                rune = await getRuneIcon(game_data["perks"]["styles"][0]["selections"][0]["perk"], api_version)
                
                sum1 = await getSumsByID(game_data["summoner1Id"], api_version)
                sum2 = await getSumsByID(game_data["summoner2Id"], api_version)
                
                text1 = f'{game_data["totalMinionsKilled"]} cs - {round(game_data["goldEarned"] / 1000, 1)}{"k" if game_data["goldEarned"] / 1000 > 1 else ""} golds'
                
                teamID = game_data["teamId"]
                if raw_data["info"]["teams"][0]["teamId"] == teamID:
                    teamkills = raw_data["info"]["teams"][0]["objectives"]["champion"]["kills"]
                else:
                    teamkills = raw_data["info"]["teams"][1]["objectives"]["champion"]["kills"]

                if teamkills == 0:
                    kp = 0
                else:
                    kp = round((game_data["kills"] + game_data["assists"]) * 100 / teamkills, 1)
                text2 = f"{kp}% kp - {game_data['visionScore']} vision"

                items = []
                for i in range(0, 7):
                    items.append(await getItemIcon(game_data[f"item{i}"], api_version))
                return pseudo, rank, queuetype, champion_icon, lvl, rune, sum1, sum2, games_status, game_duartion_to_min, kda, text1, text2, items

            async def get_game_data(raw_data, api_version):
                output = []
                for participant in raw_data["info"]["participants"]:
                    player = {}

                    teamID = participant["teamId"]
                    if raw_data["info"]["teams"][0]["teamId"] == teamID:
                        teamkills = raw_data["info"]["teams"][0]["objectives"]["champion"]["kills"]
                    else:
                        teamkills = raw_data["info"]["teams"][1]["objectives"]["champion"]["kills"]
                    items = []
                    for i in range(0, 7):
                        items.append(await getItemIcon(participant[f"item{i}"], api_version))

                    player["items"] = items
                    player["pseudo"] = participant["riotIdGameName"]
                    player["rank"] = await get_user_rank(participant["puuid"], raw_data["metadata"]["matchId"].split("_")[0].lower())
                    player["championIcon"] = await getChampionIconByID(participant["championId"], api_version)
                    player["lvl"] = participant["champLevel"]
                    player["rune"] = await getRuneIcon(participant["perks"]["styles"][0]["selections"][0]["perk"], api_version)
                    player["kda"] = f'{participant["kills"]}/{participant["deaths"]}/{participant["assists"]}'
                    player["text1"] = f'{participant["totalMinionsKilled"]}cs - {round(participant["goldEarned"] / 1000, 1)}{"k" if participant["goldEarned"] / 1000 > 1 else ""} G'
                    kp = (participant["kills"] + participant["assists"]) * 100
                    if teamkills == 0:
                        player["text2"] = f"0%KP - {participant['visionScore']} V"
                    else:
                        player["text2"] = f"{round( kp / teamkills, 1)}%KP - {participant['visionScore']} V"
                    player["sums"] = [await getSumsByID(participant["summoner1Id"], api_version), await getSumsByID(participant["summoner2Id"], api_version)]
                    output.append(player)

                results = ["Victoire" if raw_data["info"]["teams"][0]["win"] else "Défaite", "Victoire" if raw_data["info"]["teams"][1]["win"] else "Défaite"]
                bans = []
                for team in raw_data["info"]["teams"]:
                    for ban in team["bans"]:
                        bans.append(await getChampionIconByID(ban["championId"], api_version))
                return output, results, bans

            async def check_if_stored(matchId: str):
                async with self.bot.pool.acquire() as conn:
                    async with conn.transaction():
                        data = await conn.execute("SELECT * FROM lol_match_data WHERE match_id = ?", (matchId,))
                        if data:
                            return True
                        return False

            async def save_new_match(matchId: str, puuid: str):
                if matchId is None: matchId = "None"
                async with self.bot.pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute("UPDATE LoLGamesTracker SET last_game_id = ? WHERE puuid = ?", (matchId, puuid))

            async def task(data):
                try:
                    trapcoins_emoji = "<:trapcoins:1108725845339672597>"
                    for row in data:
                            try:
                                id,mentions,ign,puuid,region,last_stored_match = row
                            except ValueError:
                                print("row Error:", dict(row))
                                LogErrorInWebhook()
                                return
                            last_match = await get_last_matchs(puuid, region)
                            if self.bot.debug:
                                print(last_match, last_stored_match)
                            if last_stored_match != last_match: # If the last match is different from the last stored match
                                if mentions == "None":
                                    mentions = "?"
                                    tier_bonus = 0
                                api_version = await getLastVersion()
                                try:
                                    match_data, game_duration, game_creation, queuetype, raw_data = await get_match_data(last_match, puuid, region)
                                except TypeError:
                                    await save_new_match(last_match, puuid)
                                    continue

                                isStored = await check_if_stored(last_match)
                                if not isStored:
                                    async with self.bot.pool.acquire() as conn:
                                        async with conn.transaction():
                                            await conn.execute("INSERT INTO lol_match_data (match_id, data) VALUES (?, ?)", (last_match, raw_data))
                                queuetype = await getQueueByID(queuetype)
                                if raw_data["info"]["gameMode"] == "STRAWBERRY": # THIS IS Straw game mode
                                    try:
                                        players = []
                                        game_info = {
                                            "duration": raw_data["info"]["gameDuration"],
                                            "winned": True if raw_data["info"]["teams"][0]["win"] else False,
                                            "map": raw_data["info"]["mapId"]
                                        }
                                        for participant in raw_data["info"]["participants"]:
                                            player = {}
                                            player["pseudo"] = participant["riotIdGameName"]
                                            player["championIcon"] = await getChampionIcon(str(participant["championName"]).replace("Strawberry_",""), api_version)
                                            player["unit_killed"] = participant["totalMinionsKilled"]
                                            player["gold_earned"] = participant["goldEarned"]
                                            player["deaths"] = participant["deaths"]
                                            player["ig_lvl"] = participant["champLevel"]
                                            player["dmg_taken"] = participant["totalDamageTaken"]
                                            player["dmg_dealt"] = participant["totalDamageDealt"]
                                            player["heal"] = participant["totalHeal"]
                                            player["items"] = [await getItemIcon(participant[f'item{i}'], api_version) for i in range(0, 7)]
                                            players.append(player)
                                        
                                        await asyncio.to_thread(draw_swarm, players, game_info)
                                        await asyncio.sleep(1.9)
                                        file = discord.File(f"{FILES_PATH}swarm_output.png", filename=f"Swarm.png")
                                        embed = discord.Embed(title=f"LoL Game", description=f"<@{mentions}>", color=0x2F3136)
                                        embed.set_image(url=f"attachment://Swarm.png")
                                        gameID = raw_data["metadata"]["matchId"].split("_")[1]
                                        channel = self.bot.get_channel(1112233401286672394)
                                        if raw_data["info"]["platformId"] == "OC1": _region = "oce"
                                        else: _region = raw_data["info"]["platformId"].lower()
                                        await channel.send(file=file, embed=embed, view=GameLink(f"https://www.leagueofgraphs.com/match/{_region}/{gameID}", embed=embed))
                                        async with self.bot.pool.acquire() as conn:
                                            async with conn.transaction():
                                                await conn.execute("UPDATE LoLGamesTracker SET last_game_id = ? WHERE puuid = ?", (last_match, puuid))
                                        return
                                    except Exception as e:
                                        print(e, "\n"*3)
                                        LogErrorInWebhook(f"LoL-Game Erreur sur le SWARM match `{last_match}`\npuuid: `{puuid}`")
                                        async with self.bot.pool.acquire() as conn:
                                            async with conn.transaction():
                                                await conn.execute("UPDATE LoLGamesTracker SET last_game_id = ? WHERE puuid = ?", (last_match, puuid))
                                        continue
                                elif raw_data["info"]["gameMode"] == "CHERRY": # Arena Mode 
                                    arena_player = {}

                                    for participant in raw_data["info"]["participants"]:
                                        if participant["PlayerScore0"] == match_data["PlayerScore0"] and participant["riotIdGameName"] != match_data["riotIdGameName"]:
                                            arena_player["mate_championIcon"] = participant["championId"]
                                            break
                                    arena_player["championIcon"] = await getChampionIconByID(match_data["championId"], api_version)
                                    arena_player["mate_championIcon"] = await getChampionIconByID(arena_player["mate_championIcon"], api_version)
                                    arena_player["kills"] = match_data["kills"]
                                    arena_player["deaths"] = match_data["deaths"]
                                    arena_player["assists"] = match_data["assists"]
                                    arena_player["riotIdGameName"] = match_data["riotIdGameName"]
                                    arena_player["dmg_dealt"] = match_data["totalDamageDealtToChampions"]
                                    arena_player["PlayerScore0"] = match_data["PlayerScore0"]
                                    arena_player["items"] = [await getItemIcon(match_data[f'item{i}'], api_version) for i in range(0, 7)]
                                    await asyncio.to_thread(draw_arena, arena_player)
                                    await asyncio.sleep(1.9)
                                    file = discord.File(f"{FILES_PATH}arena_output.png", filename=f"Arena.png")
                                    embed = discord.Embed(title=f"LoL Game", description=f"<@{mentions}>", color=0x2F3136)
                                    embed.set_image(url=f"attachment://Arena.png")
                                    gameID = raw_data["metadata"]["matchId"].split("_")[1]
                                    channel = self.bot.get_channel(1112233401286672394)
                                    if raw_data["info"]["platformId"] == "OC1": _region = "oce"
                                    else: _region = raw_data["info"]["platformId"].lower()
                                    await channel.send(file=file, embed=embed, view=GameLink(f"https://www.leagueofgraphs.com/match/{_region}/{gameID}", embed=embed))
                                    async with self.bot.pool.acquire() as conn:
                                        async with conn.transaction():
                                            await conn.execute("UPDATE LoLGamesTracker SET last_game_id = ? WHERE puuid = ?", (last_match, puuid))
                                    continue
                                try:
                                    if mentions != "?":
                                        gains, text, _, texte_to_send = await calculate_gain(match_data, game_duration, mentions)
                                        tier_bonus = calc_usr_gain_by_tier(int(mentions))
                                        await self.bot.trapcoin_handler.add(userid=int(mentions), amount=(int(gains)+tier_bonus), wallet="trapcoins")
                                except:
                                    gains = 0
                                    text = ""
                                    texte_to_send = ""
                                    tier_bonus = 0
                                    pass
                                try:
                                    # new_mastery_points = await Mastery.get_all_mastery(puuid = puuid, region = region, bot=self.bot)
                                    # last_mastery_points = await Mastery.get_champion_mastery(puuid = puuid, region = region, champion_id = match_data["championId"], bot=self.bot)
                                    # if new_mastery_points is not None:
                                    #     await Mastery.update_user_mastery(new_mastery_points, self.bot)
                                    # for champ in new_mastery_points:
                                    #     if champ["championId"] == match_data["championId"]:
                                    #         new_champ_master = champ["championPoints"]
                                    #         break
                                    timestamp = game_creation / 1000
                                    dt = datetime.datetime.fromtimestamp(timestamp)
                                    text += f'\n- **Total game: {afficher_nombre_fr(gains)} {str(trapcoins_emoji)} gagnés**'
                                    if texte_to_send is not None:
                                        text += f"\n- {texte_to_send}"
                                    text += f"\n- Bonus tier: {display_big_nums(tier_bonus)} {str(trapcoins_emoji)} || ({afficher_nombre_fr(tier_bonus)} {str(trapcoins_emoji)}) ||"                  
                                    channel = self.bot.get_channel(1112233401286672394)
                                    pseudo, rank, queuetype, champion_icon, lvl, rune, sum1, sum2, games_status, game_duartion_to_min, kda, text1, text2, items = await get_drawing_data(match_data, game_duration, mentions, queuetype, raw_data, puuid, region, api_version)
                                    output, results, bans = await get_game_data(raw_data, api_version)
                                    await asyncio.to_thread(draw_game, pseudo, rank, queuetype, champion_icon, lvl, rune, sum1, sum2, games_status, game_duartion_to_min, kda, text1, text2, items, output, results, bans, mentions)
                                    file = discord.File(f"{FILES_PATH}{mentions}-game.png", filename=f"Game.png")
                                    embed = discord.Embed(title=f"LoL Game", description=f"<@{mentions}>", color=0x2F3136)
                                    embed.set_image(url=f"attachment://Game.png")
                                    gameID = raw_data["metadata"]["matchId"].split("_")[1]
                                    if raw_data["info"]["platformId"] == "OC1": _region = "oce"
                                    else: _region = raw_data["info"]["platformId"].lower()
                                    await channel.send(file=file, embed=embed, view=GameLink(f"https://www.leagueofgraphs.com/match/{_region}/{gameID}", embed=embed))
                                    os.remove(f"{FILES_PATH}{mentions}-game.png")
                                    await save_new_match(last_match, puuid)
                                    continue
                                except Exception as e:
                                    LogErrorInWebhook(f"LoL-Game Erreur sur le match `{last_match}`\npuuid: `{puuid}`\n{e}\n{traceback.format_exc()}")
                                    await save_new_match(last_match, puuid)
                                    continue
                            
                except Exception as e:
                    LogErrorInWebhook()
                return

            await task(data)

        except Exception as e:
            LogErrorInWebhook()

    @commands.command()
    async def loltrack(self, ctx: commands.Context, *arg: str):
        if ctx.author.id != 311013099719360512:
            return
        else:
            if len(arg) < 2:
                return await ctx.send("Merci de mettre un pseudo et une région et optionnellement un userId !\n- Exemple:  `!loltrack ReuS euw1 576578654587654`")
            regions = ["BR1","EUN","EUW","JP1","KR","LA1","LA2","NA1","OC1","PH2","RU","SG2","TH2","TR1","TW2","VN2",]

        # find region offset to know if ign contains spaces
            region_offset = None
            for ar in arg:
                if ar.upper() in regions:
                    region_offset = arg.index(ar)
                    break
            if region_offset is None:
                return await ctx.send("Merci de mettre une région valide !\n- Exemple:  `!loltrack ReuS EUW1`\n- Régions disponibles: `BR1,EUN,EUW,JP1,KR,LA1,LA2,NA1,OC1,PH2,RU,SG2,TH2,TR1,TW2,VN2`")
            ign = " ".join(arg[:region_offset])

            if ign == arg[0]:
                region = arg[1].lower()
            else:
                region = arg[region_offset].lower()

            if len(arg) == region_offset + 2:
                userId = arg[region_offset + 1]
            else:
                userId = None
            tagLine = ign.split("#")[1]
            puuid = await get_puuid_by_name(ign, tagLine, self.bot)
            if puuid is None:
                return await ctx.send("Erreur lors de la récupération du puuid !")
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    data = await conn.fetchall("SELECT * FROM LoLGamesTracker WHERE puuid=?", (puuid,))
                    if len(data) == 0:
                        await conn.execute("INSERT INTO LoLGamesTracker (userId, ign, puuid, region) VALUES (?, ?, ?, ?)", (str(userId), ign, puuid, region))
                    else:
                        if any(puuid in n for n in data):
                            return await ctx.send("Ce compte est déjà track !")
                        else:
                            await conn.execute("INSERT INTO LoLGamesTracker (userId, ign, puuid, region) VALUES (?, ?, ?, ?)", (str(userId), ign, puuid, region))
            return await ctx.send(f"Le compte `{ign}` en région `{region}` au puuid `{puuid}` a été ajouté !")

    @commands.command()
    async def loluntrack(self, ctx: commands.Context, *,ign: str=None):
        if ctx.author.id != 311013099719360512:
            return
        else:
            if ign is None:
                return ctx.send("Utilise un pseudo !\nUtilise !loltracklist pour voir les pseudos trackés.")
            async with self.bot.pool.acquire() as conn:
                async with conn.transaction():
                    data = await conn.fetchall("SELECT * FROM LoLGamesTracker WHERE ign=?", (ign,))
                    if len(data) == 0:
                        return await ctx.send("Ce compte n'est pas track !")
                    await conn.execute("DELETE FROM LoLGamesTracker WHERE ign=?", (ign,))
            return await ctx.send(f"Le compte `{ign}` a été retiré !")

    @commands.command()
    async def loltracklist(self, ctx: commands.Context):
        if ctx.author.id != 311013099719360512:
            return
        else:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT * FROM LoLGamesTracker")
            if len(data) == 0:
                return await ctx.send("Aucun compte n'est track !")
            else:
                igns = []
                for i in data:
                    igns.append(i[2])
                return await ctx.send(f"Comptes trackés: `{', '.join(igns)}`")

    @commands.hybrid_command()
    async def mastery(self, ctx: commands.Context, *,champion: str):
        outerSearch = False
        if ',' in champion:
            args = champion.split(",")
            champion = str(args[0]).replace(" ", "")
            if len(args) == 1:
                return await ctx.send("Merci de mettre un pseudo et une région !\n- Exemple:  `!mastery Zac, Huge Genetic Gap#Tag, oce`")
            if len(args) > 2:
                pseudo = args[1].strip()
                region = args[2].strip()
                if region not in ["oce", "euw"]:
                    return await ctx.send("Région invalide !\n- Voici les régions disponibles: `oce, euw`")
                if '#' not in pseudo:
                    return await ctx.send("Merci de mettre un pseudo valide !")
                tagLine = pseudo.split("#")[1]
                pseudo = pseudo.split("#")[0]
                outerSearch = True
        champion = champion.strip()

        async with ctx.typing():
            if not outerSearch:
                async with self.bot.pool.acquire() as conn:
                    data = await conn.fetchall("SELECT * FROM LoLGamesTracker WHERE userId=?", (str(ctx.author.id),))
                    if len(data) == 0:
                        return await ctx.send("Tu n'as pas de compte LoL tracké !\nUtilise `!mastery Champion, Pseudo#Tag, Region` pour rechercher un autre compte.\n- Exemple: `!mastery Zac, Huge Genetic Gap#OCE, oce`")
                    else:
                        puuid = data[0][3]
                        region = data[0][4]
            else:
                puuid = await get_puuid_by_name(pseudo, tagLine, self.bot)
                if puuid is None:
                    return await ctx.send(f"Erreur lors de la récupération du profil `{pseudo}` !")
            async with self.bot.session.get(f"https://ddragon.leagueoflegends.com/api/versions.json") as response:
                data = await response.json()
            api_version = data[0]
            url = f"http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/champion.json"
            async with self.bot.session.get(url) as response:
                champions_data = await response.json()
            if champion.lower() not in [champions_data["data"][champ]["name"].lower().replace(" ", "") for champ in champions_data["data"]]:
                suggestions = difflib.get_close_matches(champion.lower(), [champions_data["data"][champ]["name"].lower().replace(" ", "") for champ in champions_data["data"]], cutoff=0.5)
                if len(suggestions) > 0:
                    return await ctx.send(f"Ce champion n'existe pas !\nSuggestions: `{', '.join(suggestions)}`")
                return await ctx.send("Ce champion n'existe pas !")
            for champ in champions_data["data"]:
                if champions_data["data"][champ]["name"].lower().replace(" ", "") == champion.lower():
                    champ_id = champions_data["data"][champ]["key"]
                    champion_clean_name = champions_data["data"][champ]["id"]
                    break
            try:
                if 'euw' in region:
                    region = 'euw1'
                url = f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champ_id}"
                print(url)
                resp = await self.bot.session.get(url, headers=get_riot_api_headers())
                api_response = await resp.json()
                async with self.bot.session.get(f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}", headers=get_riot_api_headers()) as response:
                    data = await response.json()
                    pseudo = data["gameName"]
                    game_tag = data["tagLine"]
                if "status" in api_response:
                    if api_response["status"]["message"] == "Not found":
                        return await ctx.send(f"Le champion {champion} n'a jamais été joué par {pseudo}#{game_tag} !")
                    return await ctx.send(f"Erreur lors de la récupération des données !1\n{api_response}")
                async with self.bot.session.get(f'http://ddragon.leagueoflegends.com/cdn/{api_version}/img/champion/{champion_clean_name}.png', ssl=False) as response:
                    response.raise_for_status()
                    champion_icon_data = await response.read()
                async with self.bot.session.get(f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}", headers=get_riot_api_headers()) as response:
                    data = await response.json()
                    summoner_icon = data["profileIconId"]
                
                champ_lvl = api_response["championLevel"]
                champ_points = api_response["championPoints"]
                champ_points_since = api_response["championPointsSinceLastLevel"]
                champ_points_until = api_response["championPointsUntilNextLevel"]
                champ_tokens = api_response["tokensEarned"]
                milestone = api_response["championSeasonMilestone"]
                next_milestone = api_response["nextSeasonMilestone"]
                if 'milestoneGrades' in api_response:
                    milestone_grades = ", ".join(api_response["milestoneGrades"])
                else:
                    milestone_grades = "Aucun"
                next_requirements = ", ".join([f"{grade}: {count}" for grade, count in next_milestone["requireGradeCounts"].items()])
                reward_marks = next_milestone["rewardMarks"]
                total_games_required = next_milestone["totalGamesRequires"]

                embed = discord.Embed(
                    title=f"Maîtrise du champion {champion.title()}",
                    description=f"## Niveau {champ_lvl} - {champ_points:,} points".replace(',', ' '),
                    color=0x2F3136
                )

                embed.add_field(
                    name="Progression actuelle",
                    value=(
                        f"**Points depuis le dernier niveau :** {champ_points_since:,}\n"
                        f"**Points pour le prochain niveau :** {abs(champ_points_until):,}\n"
                        f"**Jetons obtenus :** {champ_tokens}\n"
                        f"**Grades obtenus :** {milestone_grades}"
                    ).replace(',', ' '),
                    inline=False
                )

                embed.add_field(
                    name="Prochaine étape",
                    value=(
                        f"**Exigences des grades :** {next_requirements}\n"
                        f"**Marques de récompense :** {reward_marks}\n"
                        f"**Total de parties nécessaires :** {total_games_required}"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="Statut du palier actuel",
                    value=f"**Palier atteint :** {milestone}",
                    inline=True
                )
                embed.set_footer(text=f"Riot Games API v{api_version} | Fait avec ❤️ par ReuS")

                if region == "oc1":
                    region = "oce"

                file = discord.File(io.BytesIO(champion_icon_data), filename=f"{champion_clean_name}.png")
                embed.set_thumbnail(url=f"attachment://{champion_clean_name}.png")
                embed.set_author(name=f"{pseudo}#{game_tag}", icon_url=f"https://ddragon.leagueoflegends.com/cdn/{api_version}/img/profileicon/{summoner_icon}.png", url=f"https://www.leagueofgraphs.com/summoner/{region}/{str(pseudo).replace(' ', '%20')}-{game_tag}")
                return await ctx.send(file=file, embed=embed)
            except Exception as e:
                traceback.print_exc()
                return await ctx.send(f"Erreur lors de la récupération des données !2\n```{e}```")	

async def setup(bot: Trapard):
    await bot.add_cog(LolGames(bot))
    