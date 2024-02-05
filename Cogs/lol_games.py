import discord, os, datetime, io
from discord.ext import commands, tasks
from typing import TYPE_CHECKING, Tuple
from PIL import ImageDraw, ImageFont, Image
from .utils.functions import trapcoins_handler, afficher_nombre_fr, display_big_nums, LogErrorInWebhook, create_embed, calc_usr_gain_by_tier
from .utils.path import LOL_IMAGE, LOL_FONT, FILES_PATH
from bot import Trapard

async def get_puuid_by_name(name: str,bot: Trapard, region="euw1"):
    try:
        if region == "euw":
            region = "euw1"
        summoner_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{name}?api_key={os.environ.get('RIOT_API')}"
        async with bot.session.get(summoner_url) as summoner_response:
            summoner_data = await summoner_response.json()
        await bot.session.close()
        return summoner_data["puuid"]
    except Exception as e:
        LogErrorInWebhook(error=f"[GET PUUID BY NAME] {e} NAME={name}")

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

    @tasks.loop(seconds=120)
    async def check_lol_games(self):
        try:
            APIKEY = os.environ.get("RIOT_API")
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT id, userId, ign, puuid, region, last_game_id FROM LoLGamesTracker")
            # Affichez les données de la table
            for row in data:
                print(dict(row))

            def draw_game(pseudo: str, rank: str, gameMode: str, championIcon, lvl: str, rune, sums1, sums2, status: str, time: int, kda: str, text1: str, text2: str, items: list, players: list, results: list, bans: list):
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
                                print("BAN", i, ban)
                                img.paste(ban, (62+422+70+26+(l_step*i), 400-7), ban)
                            except: continue
                    else:
                        if ban:
                            try:
                                ban = ban.resize((26, 26))
                                print("BAN", i, ban)
                                img.paste(ban, (62+422+70+26+sep+(l_step*i), 400-7), ban)
                            except: continue


                # Saving image
                fp = io.BytesIO()
                img.convert("RGBA").save(fp, "PNG")
                return fp
            
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
                # Requête pour obtenir les informations du summoner

                if region == "euw":
                    region = "euw1"
                if region != "euw1":
                    region = "oc1"
                summoner_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={APIKEY}"
                async with self.bot.session.get(summoner_url) as summoner_response:
                    summoner_data = await summoner_response.json()
                    encryptedId = summoner_data["id"]

                # Requête pour obtenir les informations de classement du summoner
                ranking_url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{encryptedId}?api_key={APIKEY}"
                print(ranking_url)
                async with self.bot.session.get(ranking_url) as ranking_response:
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

            async def get_last_matchs(player_uuid):
                if player_uuid == "CgWYBiR461KCjYYZHwMLjxIKj7ZwtEl-kLmaezCYhqcOSm3iHmPR0Lb_vZtGv-pZfdxTw9aE4Zh7TA" or player_uuid == "nOIDyhRyBGJG7gjRBio0LOoBR9Lj389D1xeBYlfbymoZPt-8rzCX1058IcA5aT-4gCsWfy_2sh93DA":
                    url = f"https://sea.api.riotgames.com/lol/match/v5/matches/by-puuid/{player_uuid}/ids?start=0&count=2&api_key={APIKEY}"
                else:
                    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{player_uuid}/ids?start=0&count=2&api_key={APIKEY}"
                resp = await self.bot.session.get(url)
                data = await resp.json()
                try:
                    return data[0]
                except:
                    return None

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

            async def get_match_data(matchid, player_uuid):
                if player_uuid == "CgWYBiR461KCjYYZHwMLjxIKj7ZwtEl-kLmaezCYhqcOSm3iHmPR0Lb_vZtGv-pZfdxTw9aE4Zh7TA" or player_uuid == "nOIDyhRyBGJG7gjRBio0LOoBR9Lj389D1xeBYlfbymoZPt-8rzCX1058IcA5aT-4gCsWfy_2sh93DA":
                    url = f"https://sea.api.riotgames.com/lol/match/v5/matches/{matchid}?api_key={APIKEY}"
                else:
                    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{matchid}?api_key={APIKEY}"
                reponse = await self.bot.session.get(url)

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

            def calculate_gain(game_data, game_duartion, userid):

                text_data = ""
                texte_to_send = None
                trapcoins_emoji = "<:trapcoins:1108725845339672597>"
                if game_data["win"] == True:
                    base_gain = 50000
                    text_data += f"- Victoire: 50 000 {str(trapcoins_emoji)}\n"
                    if int(userid) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(userid)] is not None:
                        if self.bot.lol_bet_dict[int(userid)][0] == "Gagner":
                            user_balance, _ = trapcoins_handler(type="get", userid=str(userid))
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                trapcoins_handler(type="add", userid=str(userid), trapcoins_val=int(self.bot.lol_bet_dict[int(userid)][1]))
                                texte_to_send = f"- 🤑 Tu as gagné **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Victoire**!"
                            else:
                                texte_to_send = f"- Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\nTu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Victoire**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            self.bot.lol_bet_dict[int(userid)] = None
                        else:
                            user_balance, _ = trapcoins_handler(type="get", userid=str(userid))
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                trapcoins_handler(type="remove", userid=str(userid), trapcoins_val=int(self.bot.lol_bet_dict[int(userid)][1]))
                                texte_to_send = f"💸 - Tu as perdu **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Défaite** alors que tu as gagné!\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            else:
                                texte_to_send = f"Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\nTu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Défaite**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            self.bot.lol_bet_dict[int(userid)] = None


                if game_data["win"] == False:
                    base_gain = 0
                    if int(userid) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(userid)] is not None:
                        if self.bot.lol_bet_dict[int(userid)][0] == "Perdu":
                            
                            user_balance, _ = trapcoins_handler(type="get", userid=str(userid))
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                trapcoins_handler(type="add", userid=str(userid), trapcoins_val=int(self.bot.lol_bet_dict[int(userid)][1]))
                                texte_to_send = f"🤑 - Tu as gagné **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} en pariant sur une **Défaite**!\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."
                            else:
                                texte_to_send = f"- Tu as **{afficher_nombre_fr(user_balance)}** {str(trapcoins_emoji)}.\n- Tu as parié **{afficher_nombre_fr(int(self.bot.lol_bet_dict[int(userid)][1]))}** {str(trapcoins_emoji)} sur **Défaite**.\nTu n'avais donc pas les fonds requis.\nLe vote est annulé, la mise récuperée.\n\nRejoue avec la commande : </g-lol-bet:1116353246609551420>."


                            self.bot.lol_bet_dict[int(userid)] = None
                        else:
                            user_balance, _ = trapcoins_handler(type="get", userid=str(userid))
                            if user_balance >= int(self.bot.lol_bet_dict[int(userid)][1]):
                                trapcoins_handler(type="add", userid=str(userid), trapcoins_val=int(self.bot.lol_bet_dict[int(userid)][1]))
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

                return base_gain, text_data, game_data['summonerName'], texte_to_send
            
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
                pseudo = game_data["summonerName"]
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
                    player["pseudo"] = participant["summonerName"]
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
                            last_match = await get_last_matchs(puuid)
                            print(last_match, last_stored_match)
                            if last_stored_match != last_match:
                                if mentions == "None":
                                    mentions = "?"
                                    tier_bonus = 0
                                
                                match_data, game_duration, game_creation, queuetype, raw_data = await get_match_data(last_match, puuid)
                                queuetype = await getQueueByID(queuetype)
                                if queuetype == "Arena": # DO ARENA THING HERE
                                    pass
                                try:
                                    if mentions != "?":
                                        gains, text, _, texte_to_send = calculate_gain(match_data, game_duration, mentions)
                                        trapcoins_handler(type="add", userid=str(mentions), trapcoins_val=int(gains))
                                        tier_bonus = calc_usr_gain_by_tier(int(mentions))
                                        trapcoins_handler(type="add", userid=str(mentions), trapcoins_val=tier_bonus)
                                except:
                                    gains = 0
                                    text = ""
                                    texte_to_send = ""
                                    tier_bonus = 0
                                    pass
                                try:
                                    timestamp = game_creation / 1000
                                    dt = datetime.datetime.fromtimestamp(timestamp)
                                    text += f'\n- **Total game: {afficher_nombre_fr(gains)} {str(trapcoins_emoji)} gagnés**'
                                    if texte_to_send is not None:
                                        text += f"\n- {texte_to_send}"
                                    text += f"\n- Bonus tier: {display_big_nums(tier_bonus)} {str(trapcoins_emoji)} || ({afficher_nombre_fr(tier_bonus)} {str(trapcoins_emoji)}) ||"                  
                                    channel = self.bot.get_channel(1112233401286672394)
                                    embed1 = create_embed(title="LoL Trapcoins", description=text)
                                    api_version = await getLastVersion()
                                    pseudo, rank, queuetype, champion_icon, lvl, rune, sum1, sum2, games_status, game_duartion_to_min, kda, text1, text2, items = await get_drawing_data(match_data, game_duration, mentions, queuetype, raw_data, puuid, region, api_version)
                                    output, results, bans = await get_game_data(raw_data, api_version)
                                    image = draw_game(pseudo, rank, queuetype, champion_icon, lvl, rune, sum1, sum2, games_status, game_duartion_to_min, kda, text1, text2, items, output, results, bans)
                                    img = Image.open(image)
                                    img.save(f"{FILES_PATH}{mentions}-game.png")
                                    file = discord.File(f"{FILES_PATH}{mentions}-game.png", filename=f"Game.png")
                                    embed = discord.Embed(title=f"LoL Game", description=f"<@{mentions}>", color=0x2F3136)
                                    embed.set_image(url=f"attachment://Game.png")
                                    gameID = raw_data["metadata"]["matchId"].split("_")[1]
                                    await channel.send(file=file, embed=embed, view=GameLink(f"https://www.leagueofgraphs.com/match/euw/{gameID}", embed=embed))
                                    os.remove(f"{FILES_PATH}{mentions}-game.png")
                                    async with self.bot.pool.acquire() as conn:
                                        async with conn.transaction():
                                            await conn.execute("UPDATE LoLGamesTracker SET last_game_id = ? WHERE puuid = ?", (last_match, puuid))
                                    return
                                except:
                                    LogErrorInWebhook(f"LoL-Game Erreur sur le match `{last_match}`\npuuid: `{puuid}`")
                                    async with self.bot.pool.acquire() as conn:
                                        async with conn.transaction():
                                            await conn.execute("UPDATE LoLGamesTracker SET last_game_id = ? WHERE puuid = ?", (last_match, puuid))
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

            puuid = await get_puuid_by_name(ign, self.bot, region)
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

async def setup(bot: Trapard):
    await bot.add_cog(LolGames(bot))
    