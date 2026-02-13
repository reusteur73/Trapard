import io
from aiohttp import ClientSession
from .functions import getVar, LogErrorInWebhook, afficher_nombre_fr
from .classes import APIResponse
from .path import LOL_IMAGE, LOL_FONT, FILES_PATH, LOL_IMAGE_ARENA, LOL_DRAFT_PLAYER_IMG
from typing import Literal, Tuple, List
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

class RiotAssetsAPI:
    """Riot Games Assets API wrapper."""
    def __init__(self, session: ClientSession):
        self.session = session

    async def get_rune_icon(self, runeId: int, api_version: str) -> Image.Image | None:
        """Fetches the icon image for a given rune ID."""
        RUNES_BASE_URL = 'http://ddragon.leagueoflegends.com/cdn/img/'
        async with self.session.get(f'http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/runesReforged.json') as response:
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
            async with self.session.get(url) as data:
                data.raise_for_status
                content = await data.read()
            return Image.open(BytesIO(content))
        return None

    async def get_champion_icon_by_id(self, champion_id: int, api_version, url=False) -> BytesIO | str | None:
        """Fetches the champion icon URL or image for a given champion ID.

        If `url` is True this returns a URL (str), otherwise it returns a PIL.Image via
        `get_champion_icon` (or None if not found).
        """
        json_url = f"http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/champion.json"
        async with self.session.get(json_url) as response:
            data = await response.json()
            for champ in data["data"]:
                if data["data"][champ]["key"] == str(champion_id):
                    if url:
                        return f"http://ddragon.leagueoflegends.com/cdn/{api_version}/img/champion/{data['data'][champ]['image']['full']}"
                    # Return PIL Image from get_champion_icon
                    return await self.get_champion_icon(data["data"][champ]["image"]["full"].replace(".png", ""), api_version)
        return None

    async def get_champion_name_by_id(self, champion_id: int, api_version) -> str | None:
        """Fetches the champion name(id) for a given champion ID."""
        json_url = f"http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/champion.json"
        async with self.session.get(json_url) as response:
            data = await response.json()
            for champ in data["data"]:
                if data["data"][champ]["key"] == str(champion_id):
                    return data["data"][champ]["id"]
        return None

    async def get_champion_icon(self, championName: str, api_version) -> BytesIO | None:
        """Fetches the champion icon image for a given champion name."""
        async with self.session.get(f'http://ddragon.leagueoflegends.com/cdn/{api_version}/img/champion/{championName}.png', ssl=False) as response:
            response.raise_for_status()
            champion_icon_data = await response.read()
            return Image.open(BytesIO(champion_icon_data)).convert("RGBA")
        return None

    async def get_champions_list(self, api_version: str) -> dict:
        """Fetches the list of champions."""
        async with self.session.get(f"http://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/champion.json") as response:
            data = await response.json()
            return data["data"]

    async def get_item_icon(self, item_id: int, api_version) -> BytesIO:
        """Fetches the item icon image for a given item ID."""
        if item_id == 0: return None
        ITEMS_BASE_URL = f'http://ddragon.leagueoflegends.com/cdn/{api_version}/img/item/'
        async with self.session.get(f"{ITEMS_BASE_URL}{item_id}.png", ssl=False) as response:
            response.raise_for_status()
            data = await response.read()
        return Image.open(BytesIO(data))
    
    async def get_summoner_spell_icon(self, summoner_spell_id: int, api_version: str) -> BytesIO:
        """Fetches the summoner spell icon image for a given summoner spell ID."""
        async with self.session.get(f"https://ddragon.leagueoflegends.com/cdn/{api_version}/data/en_US/summoner.json") as response:
            data = await response.json()
            for summ in data["data"]:
                if data["data"][summ]["key"] == str(summoner_spell_id):
                    async with self.session.get(f"http://ddragon.leagueoflegends.com/cdn/{api_version}/img/spell/{data['data'][summ]['image']['full']}") as response2:
                        response2.raise_for_status()
                        data2 = await response2.read()
                    return Image.open(io.BytesIO(data2))
    
    def get_profile_icon_url(self, icon_id: int, api_version: str) -> str:
        return f"http://ddragon.leagueoflegends.com/cdn/{api_version}/img/profileicon/{icon_id}.png"
    
    async def get_queue_by_id(self, id: int):
        """Fetches the game mode description for a given queue ID."""
        match id:
            case 4250 | 4210: return "Doom Bots"
            case 480: return "Quick Play Draft"
        async with self.session.get(f"https://static.developer.riotgames.com/docs/lol/queues.json") as response:
            data = await response.json()
            for queue in data:
                if queue["queueId"] == id:
                    return queue["description"]
            LogErrorInWebhook(error=f"[LOL] Erreur lors de la récupération du mode de jeu {id} | réponse code : {response.status}")
            return "Mode de jeu inconnu"

    async def get_mastery_icon(self, mastery_level: int) -> Image.Image | None:
        """Fetches the champion mastery icon image for a given mastery level."""
        if mastery_level > 10:
            mastery_level = 10
        url = f"https://raw.communitydragon.org/latest/game/assets/ux/mastery/legendarychampionmastery/masterycrest_level{mastery_level}.cm_updates.png"
        async with self.session.get(url) as response:
            response.raise_for_status()
            data = await response.read()
            return Image.open(BytesIO(data)).convert("RGBA")
        return None

class RiotAPI:
    """Riot Games API wrapper."""
    def __init__(self, session: ClientSession):
        self.session = session
        self.request_count = 0
    
    def _get_headers(self):
        return {
            "Accept": "application/json",
            "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Charset": "application/x-www-form-urlencoded; charset=UTF-8",
            "Content-Type": "application/json",
            "X-Riot-Token": getVar("RIOT_API")
        }

    def _get_region_mapping(self, type: Literal["platform", "regional", "continental"], region):
        if region == "euw": region = "euw1"
        region_mapping = {
            "oc1": {
                "platform": "oc1",
                "continental": "sea",
                "regional": "americas"
            },
            "na1": {
                "platform": "na1",
                "continental": "americas",
                "regional": "americas"
            },
            "br1": {
                "platform": "br1",
                "continental": "americas",
                "regional": "americas"
            },
            "la1": {
                "platform": "la1",
                "continental": "americas",
                "regional": "americas"
            },
            "la2": {
                "platform": "la2",
                "continental": "americas",
                "regional": "americas"
            },
            "euw1": {
                "platform": "euw1",
                "continental": "europe",
                "regional": "europe"
            },
            "eun1": {
                "platform": "eun1",
                "continental": "europe",
                "regional": "europe"
            },
            "tr1": {
                "platform": "tr1",
                "continental": "europe",
                "regional": "europe"
            },
            "ru1": {
                "platform": "ru1",
                "continental": "europe",
                "regional": "europe"
            },
            "kr": {
                "platform": "kr",
                "continental": "asia",
                "regional": "asia"
            },
            "jp1": {
                "platform": "jp1",
                "continental": "asia",
                "regional": "asia"
            }
        }
        return region_mapping[region][type]

    async def _make_request(self, region: str, endpoint: str) -> APIResponse:
        self.request_count += 1
        url = f"https://{region}.api.riotgames.com{endpoint}"
        async with self.session.get(url, headers=self._get_headers()) as response:
            try:
                response.raise_for_status()
                return APIResponse(
                    status=response.status,
                    data=await response.json(),
                    headers=response.headers
                )
            except Exception as e:
                # LogErrorInWebhook(error=f"[RIOT API] Erreur lors de la requête vers {url} | réponse code : {response.status} | erreur : {e}")
                return APIResponse(
                    status=response.status,
                    data=None,
                    headers=response.headers
                )

    async def get_api_version(self) -> str:
        """Fetches the latest Riot API version."""
        async with self.session.get(f"https://ddragon.leagueoflegends.com/api/versions.json") as response:
            data = await response.json()
            return str(data[0])

    async def get_puuid_by_summoner_name(self, summoner_name: str, tagline: str, region: str) -> APIResponse:
        region = self._get_region_mapping("regional", region)
        url = self._make_request(
            region,
            f"/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}"
        )
        return await self._make_request(region, url)["puuid"]
    
    async def get_match_data(self, match_id: str, region: str) -> APIResponse:
        region = self._get_region_mapping("continental", region)
        url = f"/lol/match/v5/matches/{match_id}"
        return await self._make_request(region, url)
    
    async def get_current_game(self, puuid: str, region: str) -> APIResponse:
        region = self._get_region_mapping("platform", region)
        url = f"/lol/spectator/v5/active-games/by-summoner/{puuid}"
        return await self._make_request(region, url)
    
    async def get_player_league(self, puuid: str, region: str) -> APIResponse:
        """Fetches the ranked league entries for a player by their PUUID."""
        region = self._get_region_mapping("platform", region)
        url = f"/lol/league/v4/entries/by-puuid/{puuid}"
        return await self._make_request(region, url)

    async def get_account_by_puuid(self, puuid: str, region: str) -> APIResponse:
        region = self._get_region_mapping("regional", region)
        url = f"/riot/account/v1/accounts/by-puuid/{puuid}"
        return await self._make_request(region, url)

    async def get_player_champion_mastery(self, puuid: str, region: str, champion_id: int) -> APIResponse:
        """Fetches the champion mastery details for a specific champion for a player by their PUUID."""
        region = self._get_region_mapping("platform", region)
        url = f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}"
        return await self._make_request(region, url)
    
    async def get_all_champion_masteries(self, puuid: str, region: str) -> APIResponse:
        """Fetches all champion mastery details for a player by their PUUID."""
        region = self._get_region_mapping("platform", region)
        url = f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
        return await self._make_request(region, url)
    
    async def get_last_match_id(self, puuid: str, region: str) -> str:
        """Fetches the most recent match ID for a player by their PUUID."""
        region = self._get_region_mapping("continental", region)
        url = f"/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
        matches = await self._make_request(region, url)
        if matches.data is None:
            return "0"
        return matches.data[0] if matches.data else "0"

class LolGameDrawer:
    """Class for drawing League of Legends game images."""
    def __init__(self):
        self.fontSmall = ImageFont.truetype(LOL_FONT, 15)
        self.fontSmall2 = ImageFont.truetype(LOL_FONT, 12)
        self.fontSmall3 = ImageFont.truetype(LOL_FONT, 42)
        self.smalll = ImageFont.truetype(LOL_FONT, 55)
        self.smalll2 = ImageFont.truetype(LOL_FONT, 64)
        self.font_medium = ImageFont.truetype(LOL_FONT, 30)
        self.font_medium2 = ImageFont.truetype(LOL_FONT, 23)
        self.font_medium3 = ImageFont.truetype(LOL_FONT, 22)
        self.font = ImageFont.truetype(LOL_FONT, 70)

    def _draw_text_center(self, draw: ImageDraw.ImageDraw, text: str, coordinates: Tuple[int, int], box_size: Tuple[int, int], font: ImageFont.FreeTypeFont, fill: str,) -> None:
        """Draws centered text within a specified box size."""
        if not isinstance(text, str):
            text = str(text)
        text_width, text_height = draw.textlength(text, font=font), 24
        coordinates = (
            int(coordinates[0] + (box_size[0] - text_width) // 2),
            int(coordinates[1] + (box_size[1] - text_height) // 2),
        )
        draw.text(coordinates, text, font=font, fill=fill)

    def _draw_text_left(self, draw: ImageDraw.ImageDraw, text: str, coordinates: Tuple[int, int], box_size: Tuple[int, int], font: ImageFont.FreeTypeFont, fill: str) -> None:
        """Draws left-aligned text within a specified box size."""
        if not isinstance(text, str):
            text = str(text)
        _, text_height = draw.textlength(text, font=font), 24
        x = coordinates[0] # Fixer la coordonnée x à celle de départ de la boîte pour aligner le texte à gauche
        # Calculer la coordonnée y pour centrer verticalement le texte
        y = int(coordinates[1] + (box_size[1] - text_height) // 2)
        draw.text((x, y),text,font=font,fill=fill)

    def _remove_white_background(self, image: Image.Image):
        """Removes white background from an image and makes it transparent."""
        image = image.convert("RGBA")
        data = image.getdata()
        new_data = []
        for item in data:
            if item[:3] == (255, 255, 255): # Si le pixel est blanc, le rendre transparent (alpha = 0)
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        image.putdata(new_data)
        return image

    def _add_corners(self, im: Image.Image, rad) -> Image.Image:
        """Adds rounded corners to an image."""
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

    def draw_game(self, gameMode: str, players: list, results: list, bans: list, mentions: str):
        """Draws the League of Legends game image."""
        img = Image.open(LOL_IMAGE)

        # # Defining draw
        draw = ImageDraw.Draw(img)

        if gameMode:
            self._draw_text_center(draw, gameMode, (1467, 40), (754, 98), self.font, "white")

        # Images
        if results[0] and results[1]:
            self._draw_text_center(draw, results[0], (165, 60), (754, 98), self.font, "green" if results[0] == 'Victoire' else 'red')
            self._draw_text_center(draw, results[1], (2776, 60), (754, 98), self.font, "green" if results[1] == 'Victoire' else 'red')

        h_step = 510
        players_pos_mapping = {
            "left": {
                "avatar": (168, 272),
                "sums0": (228, 592),
                "sums1": (350, 592),
                "rune": (115, 588),
                "item0": (1177, 270),
                "item1": (1177+125, 270),
                "item2": (1177+125+125, 270),
                "item3": (1177, 270+120),
                "item4": (1177+125, 270+120),
                "item5": (1177+125+125, 270+120),
                "item6": (1177+125+125+125, 270+120),
                "pseudo": (494, 245),
                "rank": (490, 370),
                "lvl": (127, 510),
                "kda": (1400, 520),
                "text1": (490, 500)
            },
            "right": {
                "avatar": (3232, 272),
                "sums0": (3240, 593),
                "sums1": (3360, 592),
                "rune": (3472, 588),
                "item0": (2415, 270),
                "item1": (2415-125, 270),
                "item2": (2415-125-125, 270),
                "item3": (2415, 270+120),
                "item4": (2415-125, 270+120),
                "item5": (2415-125-125, 270+120),
                "item6": (2415-125-125-125, 270+120),
                "pseudo": (2542, 245),
                "rank": (2540, 370),
                "lvl": (3550, 512),
                "kda": (2250, 520),
                "text1": (2540, 500)
            }
        }
        
        # process all players list
        for i, player in enumerate(players):
            side = "left" if i < 5 else "right"
            pos = players_pos_mapping[side]
            idx = i if i < 5 else i - 5

            if player["championIcon"]:
                avatar = self._add_corners(player["championIcon"], 10).resize((298, 298))
                img.paste(avatar, (pos["avatar"][0], pos["avatar"][1] + (h_step * idx)), avatar) # Champion Icon

            if player["sums"][0]:
                summoner1 = self._add_corners(player["sums"][0], 10).resize((100, 100))
                img.paste(summoner1, (pos["sums0"][0], pos["sums0"][1] + (h_step * idx)), summoner1) # Summoner 1
            
            if player["sums"][1]:
                summoner2 = self._add_corners(player["sums"][1], 10).resize((100, 100))
                img.paste(summoner2, (pos["sums1"][0], pos["sums1"][1] + (h_step * idx)), summoner2) # Summoner 2

            if player["rune"]:
                rune = self._remove_white_background(player["rune"]).resize((100,100))
                img.paste(rune, (pos["rune"][0], pos["rune"][1] + (h_step * idx)), rune) # Rune

            for j in range(7):
                if player["items"][j]:
                    item = self._add_corners(player["items"][j], 10).resize((100, 100))
                    item_x = pos[f"item{j}"][0]
                    item_y = pos[f"item{j}"][1] + (h_step * idx)
                    img.paste(item, (item_x, item_y), item) # Item j

            # Pseudo
            if len(player["pseudo"]) > 7:
                self._draw_text_center(draw, player["pseudo"], (pos["pseudo"][0], pos["pseudo"][1] + (h_step * idx)), (664, 100), self.smalll2, "white")
            else:
                self._draw_text_center(draw, player["pseudo"], (pos["pseudo"][0], pos["pseudo"][1] + (h_step * idx)), (664, 100), self.smalll, "white")
            # Rank
            if player["rank"]:
                division, tier = player["rank"].strip().split(" ")
                _rank = f"{division} {tier.capitalize()}"
                self._draw_text_center(draw, _rank, (pos["rank"][0], pos["rank"][1] + (h_step * idx)), (664, 100), self.smalll, "white")
            # Level
            if player["lvl"]:
                self._draw_text_center(draw, str(player["lvl"]), (pos["lvl"][0], pos["lvl"][1] + (h_step * idx)), (30, 30), self.smalll2, "white")
            # KDA
            if player["kda"]:
                self._draw_text_center(draw, player["kda"], (pos["kda"][0], pos["kda"][1] + (h_step * idx)), (30, 30), self.font, "white")
            # Text1
            if player["text1"] and player["text2"]:
                self._draw_text_center(draw, f"{player['text1']} - {player['text2']}", (pos["text1"][0], pos["text1"][1] + (h_step * idx)), (664, 100), self.fontSmall3, "white")
        
        l_step = 177
        sep = 108
        for i, ban in enumerate(bans):
            if i < 5:
                if ban:
                    try:
                        ban = ban.resize((150, 150))
                        img.paste(ban, (555+(l_step*i), 2787), ban)
                    except: continue
            else:
                if ban:
                    try:
                        ban = ban.resize((150, 150))
                        img.paste(ban, (2538+(l_step*(i-5)), 2787), ban)
                    except: continue
        # Saving image
        fp = io.BytesIO()
        img.convert("RGBA").save(fp, "PNG")
        img.save(f"{FILES_PATH}{mentions}-game.png")
        return
    
    def draw_player(self, discordId: int, pseudo: str, rank: str, gameMode: str, championIcon: io.BytesIO, lvl: str, rune, sums1, sums2, status: str, time: int, kda: str, text1: str, text2: str, mastery_gained: str, mastery_level: str, mastery_points: str, mastery_image: Image.Image, items: list):
        """Draws the League of Legends player image."""
        img = Image.open(LOL_DRAFT_PLAYER_IMG).convert("RGBA")

        if championIcon:
            avatar = self._add_corners(championIcon, 10).resize((212, 212))
            img.paste(avatar, (85, 315), avatar) # Champion Icon
            img.paste(avatar, (800, 44), avatar)
        
        
        if mastery_image:
            if isinstance(mastery_image, Image.Image):
                mastery_image = mastery_image.resize((212, 212)).convert("RGBA")
                img.paste(mastery_image, (802, 265), mastery_image)
        
        if rune:
            rune = self._remove_white_background(rune).resize((70, 70))
            img.paste(rune, (77, 550), rune) # Rune

        if sums1:
            summoner1 = self._add_corners(sums1, 10).resize((70, 70))
            img.paste(summoner1, (152, 547), summoner1) # Summoner 1
        
        if sums2:
            summoner2 = self._add_corners(sums2, 10).resize((70, 70))
            img.paste(summoner2, (227, 547), summoner2) # Summoner 2

        items_pos_mapping = { 
            0: (418, 458),
            1: (418+94, 458),
            2: (418+94+94, 458),
            3: (418, 560),
            4: (418+94, 560),
            5: (418+94+94, 560),
            6: (418-94, 560)
            
        }
        for i in range(7): # Main Player Items
            if items[i]:
                item = self._add_corners(items[i], 10).resize((90, 90))
                item_x = items_pos_mapping[i][0]
                item_y = items_pos_mapping[i][1]
                img.paste(item, (item_x, item_y), item) # Item i

        draw = ImageDraw.Draw(img)
        if pseudo:
            self._draw_text_center(draw, pseudo, (37, 60), (311, 58), self.font_medium, "white")

        if rank:
            self._draw_text_center(draw, rank, (37, 147), (311, 58), self.font_medium2, "white")

        if gameMode:
            self._draw_text_center(draw, gameMode, (37, 222), (311, 58), self.font_medium2, "white")

        if lvl:
            self._draw_text_center(draw, str(lvl), (46, 517), (40, 40), self.font_medium2, "white")

        if status:
            self._draw_text_center(draw, status, (400, 50), (307, 38), self.fontSmall3, f'green' if status == 'Victoire' else 'red')

        if time:
            self._draw_text_center(draw, f"{time}", (400, 128), (307, 38), self.fontSmall3, "white")

        if kda:
            self._draw_text_center(draw, kda, (400, 205), (307, 38), self.fontSmall3, "white")

        if text1:
            self._draw_text_center(draw, f"{text1}", (400, 292), (307, 38), self.font_medium, "white")
        
        if text2:
            self._draw_text_center(draw, f"{text2}", (400, 370), (307, 38), self.font_medium, "white")
        
        if mastery_level:
            self._draw_text_center(draw, f"Mastery {mastery_level}", (780, 478), (249, 52), self.font_medium, "white")

        if mastery_points:
            self._draw_text_center(draw, mastery_points, (780, 542), (249, 52), self.font_medium3, "white")

        if mastery_gained:
            self._draw_text_center(draw, mastery_gained, (845, 602), (121, 52), self.font_medium2, "white")

        img.save(f"{FILES_PATH}{discordId}-player.png")

    def draw_swarm(self, players: List[dict], gamedata: dict):
        def minutes_to_time(minutes: int) -> str:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours:02}:{mins:02}"        
        try:
            FONT = ImageFont.truetype(LOL_FONT)
            img = Image.open(f"{FILES_PATH}swarm{len(players)}.png")
            draw = ImageDraw.Draw(img)

            vert_decay = 202

            # draw game info
            if gamedata["winned"]:
                self._draw_text_left(draw, "Victoire", (220, 22), (0, 40), ImageFont.truetype(FONT, 40), "green")
            else:
                self._draw_text_left(draw, "Défaite", (220, 22), (0, 40), ImageFont.truetype(FONT, 40), "red")

            self._draw_text_left(draw, f"Durée: {minutes_to_time(gamedata['duration'])}", (425, 22), (0, 40), ImageFont.truetype(FONT, 40), "white")
            self._draw_text_left(draw, f"Map: {gamedata['map']}", (725, 22), (0, 40), ImageFont.truetype(FONT, 40), "white")

            # draw players
            for p_i, player in enumerate(players):
                player["championIcon"] = player["championIcon"].convert("RGBA")
                player["championIcon"] = self._add_corners(player["championIcon"], 15)
                player["championIcon"] = player["championIcon"].resize((115, 115), Image.LANCZOS)
                img.paste(player["championIcon"], (57, 125+(vert_decay*p_i)), player["championIcon"])
                self._draw_text_left(draw, player["pseudo"], (200, 122+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")
                self._draw_text_left(draw, f"{player['ig_lvl']}", (23, 216+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 29), "white")
                self._draw_text_left(draw, f"{afficher_nombre_fr(player['gold_earned'])}", (265, 171+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")
                self._draw_text_left(draw, f"{afficher_nombre_fr(player['unit_killed'])}", (495, 120+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")
                self._draw_text_left(draw, f"{afficher_nombre_fr(player['dmg_dealt'])}", (710, 119+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")
                self._draw_text_left(draw, f"{afficher_nombre_fr(player['dmg_taken'])}", (710, 170+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")
                self._draw_text_left(draw, f"{player['deaths']}", (525, 170+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")
                self._draw_text_left(draw, f"{afficher_nombre_fr(player['heal'])}", (710, 221+(vert_decay*p_i)), (0, 40), ImageFont.truetype(FONT, 25), "white")

                print(player["items"])
                for i, item in enumerate(player["items"]):
                    if item:
                        item = item.convert("RGBA")
                        item = self._add_corners(item, 15)
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

    def draw_arena(self,player: dict):
        """Draws the League of Legends arena image for a player."""
        img = Image.open(LOL_IMAGE_ARENA)
        draw = ImageDraw.Draw(img)

        # draw player name
        if player["riotIdGameName"]:
            self._draw_text_left(draw, player["riotIdGameName"], (53, 79), (0, 40), ImageFont.truetype(LOL_FONT, 22), "white")

        # draw kda
        if player["kills"] and player["deaths"] and player["assists"]:
            self._draw_text_left(draw, f"{player['kills']}/{player['deaths']}/{player['assists']}", (385, 80), (0, 40), ImageFont.truetype(LOL_FONT, 22), "white")
            ratio = round((player["kills"] + player["assists"]) / max(1, player["deaths"]), 2)
            self._draw_text_left(draw, f"{ratio} KDA", (375, 80+38), (0, 40), ImageFont.truetype(LOL_FONT, 22), "white")

        # draw damage dealt
        if player["dmg_dealt"]:
            self._draw_text_left(draw, f"{afficher_nombre_fr(player['dmg_dealt'])} DMG", (355, 80+76), (0, 40), ImageFont.truetype(LOL_FONT, 22), "white")

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
            self._draw_text_left(draw, f"{player['PlayerScore0']}{suffix}", (103, 268), (0, 40), ImageFont.truetype(LOL_FONT, 48), color)

        # draw items
        for i, item in enumerate(player["items"]):
            if not item:
                continue
            item = item.convert("RGBA")
            if i == 6:
                item = self._add_corners(item, 35)
            else:
                item = self._add_corners(item, 15)
            item = item.resize((40, 40), Image.LANCZOS)
            if i < 3:
                img.paste(item, (335 + 47 * i, 230), item)
            else:
                img.paste(item, (335 + 47 * (i-4)+46, 281), item)

        # draw champion icon
        if player["championIcon"]:
            player["championIcon"] = player["championIcon"].convert("RGBA")
            player["championIcon"] = self._add_corners(player["championIcon"], 15)
            player["championIcon"] = player["championIcon"].resize((115, 115), Image.LANCZOS)
            img.paste(player["championIcon"], (57, 141), player["championIcon"])

        if player["mate_championIcon"]:
            player["mate_championIcon"] = player["mate_championIcon"].convert("RGBA")
            player["mate_championIcon"] = self._add_corners(player["mate_championIcon"], 15)
            player["mate_championIcon"] = player["mate_championIcon"].resize((55, 55), Image.LANCZOS)
            img.paste(player["mate_championIcon"], (179, 187), player["mate_championIcon"])

        # save image
        fp = io.BytesIO()
        img.convert("RGBA").save(fp, "PNG")
        img.save(f"{FILES_PATH}arena_output.png")
        return f"{FILES_PATH}arena_output.png"

