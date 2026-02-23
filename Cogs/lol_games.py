import discord, os, io, traceback, asyncio, difflib
from discord.ext import commands, tasks
from discord import ui
from .utils.functions import afficher_nombre_fr, LogErrorInWebhook, getVar
from .utils.path import FILES_PATH
from .utils.RiotCore import RiotAPI, RiotAssetsAPI, LolGameDrawer
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

class GameLink(discord.ui.View):
    def __init__(self, link: str="N/A", embed=None):
        super().__init__(timeout=None)
        self.embed = embed
        self.add_item(discord.ui.Button(label="Voir plus", url=link))

class LolGameMessage(ui.LayoutView):
    """Custom view for displaying League of Legends game details with an image and buttons."""
    def __init__(self, *,image_path:str, footer_text:str, match_id:str, region: str, name_tagline: str, timeout: float = 180, image_path2:str=None) -> None:
        super().__init__(timeout=timeout)
        file = discord.File(image_path, filename="Game.png")
        gallery = ui.MediaGallery(
            discord.MediaGalleryItem(media=file, description="Image de la partie League of Legends")
        )
        
        if image_path2 is not None:
            file2 = discord.File(image_path2, filename="Player.png")
            gallery2 = ui.MediaGallery(
                discord.MediaGalleryItem(media=file2, description="Image du joueur")
            )

        text = ui.TextDisplay("Voici les détails de ta partie League of Legends !")
        separator = ui.Separator(
            spacing = discord.SeparatorSpacing.large,
            visible = True,
        )
        footer = ui.TextDisplay(f"-# {footer_text}")

        container = ui.Container(gallery)
        
        buttons_row = ui.ActionRow().add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="Voir la game sur League of Graphs", url=f"https://www.leagueofgraphs.com/match/{region}/{match_id}")).add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="Voir le profil du joueur", url=f"https://www.leagueofgraphs.com/summoner/{region}/{name_tagline.replace(' ','%20')}"))
        if image_path2 is not None:
            container1 = ui.Container(gallery2, text, buttons_row, separator, footer)
        else: 
            container1 = ui.Container(text, buttons_row, separator, footer)
    
        self.add_item(container)
        self.add_item(container1)


class LolGames(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
        self.riot_api = RiotAPI(bot.session)
        self.riot_assets_api = RiotAssetsAPI(bot.session)
        self.lol_game_drawer = LolGameDrawer()

        self.ongoing_games = {}

        self.check_lol_games.start()
        self.current_game_lol_tracker.start()

    @tasks.loop(seconds=300)
    async def check_lol_games(self):
        try:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT id, userId, ign, puuid, region, last_game_id FROM LoLGamesTracker")

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
                ranking_data = await self.riot_api.get_player_league(puuid, region)
                if ranking_data.status == 200:
                    ranks = []
                    for i in ranking_data.data:
                        if "tier" in i and "rank" in i:
                            ranks.append(f"{i['tier'].lower()} {i['rank']}")
                    if len(ranks) > 1:
                        return rang_le_plus_eleve(ranks)
                    elif len(ranks) == 0:
                        return "Non classé"
                    else: 
                        parts = str(ranks[0]).split()
                        return f"{parts[0].title()} {parts[1].capitalize()}"
                return "Non classé"

            async def get_match_data(matchid, player_uuid, region):
                if matchid is None:
                    LogErrorInWebhook(error=f"[LOL 0x02] matchid est None pour le joueur {player_uuid}")
                    return None
                
                data = await self.riot_api.get_match_data(matchid, region)
                if data.data is None:
                    LogErrorInWebhook(error=f"[LOL 0x03] Erreur lors de la récupération des données de la partie {matchid} | réponse code : {reponse.status}")
                    return None

                try: participants = data.data["info"]["participants"]
                except: return None
                player_position = None
                for index, p in enumerate(participants):
                    if player_uuid == p["puuid"]:
                        player_position = index
                        break
                if player_position is None:
                    LogErrorInWebhook(error=f"[LOL 0x05] Impossible de trouver le joueur {player_uuid} dans la partie {matchid}")
                    return None
                player_data = participants[player_position]
                game_duartion = data.data["info"]["gameDuration"]
                game_creation = data.data["info"]["gameCreation"]
                summoner_icon_id = player_data["profileIcon"]
                long_name = f"{player_data['riotIdGameName']}#{player_data['riotIdTagline']}"
                champion_id = player_data["championId"]
                game_version = data.data["info"]["gameVersion"]
                return player_data, game_duartion, game_creation, data.data["info"]["queueId"], data.data, summoner_icon_id, long_name, champion_id, game_version

            async def get_drawing_data(game_data, game_duartion, userid, queuetype, raw_data, puuid, region, api_version):
                pseudo = game_data["riotIdGameName"]
                rank = await get_user_rank(puuid, region)

                if game_data["win"] == True:
                    games_status = "Victoire"
                else:
                    games_status = "Défaite"
                game_duartion_to_min = f'{game_duartion // 60} minute{"s" if game_duartion // 60 > 1 else ""}'
                
                kda = f'{game_data["kills"]}/{game_data["deaths"]}/{game_data["assists"]}'
                

                champion_icon = await self.riot_assets_api.get_champion_icon_by_id(game_data["championId"], api_version)
                
                lvl = game_data["champLevel"]
                
                rune = await self.riot_assets_api.get_rune_icon(game_data["perks"]["styles"][0]["selections"][0]["perk"], api_version)
                
                sum1 = await self.riot_assets_api.get_summoner_spell_icon(game_data["summoner1Id"], api_version)
                sum2 = await self.riot_assets_api.get_summoner_spell_icon(game_data["summoner2Id"], api_version)
                
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
                    items.append(await self.riot_assets_api.get_item_icon(game_data[f"item{i}"], api_version))
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
                        items.append(await self.riot_assets_api.get_item_icon(participant[f"item{i}"], api_version))

                    player["items"] = items
                    player["pseudo"] = participant["riotIdGameName"]
                    player["rank"] = await get_user_rank(participant["puuid"], raw_data["metadata"]["matchId"].split("_")[0].lower())
                    player["championIcon"] = await self.riot_assets_api.get_champion_icon_by_id(participant["championId"], api_version)
                    player["lvl"] = participant["champLevel"]
                    player["rune"] = await self.riot_assets_api.get_rune_icon(participant["perks"]["styles"][0]["selections"][0]["perk"], api_version)
                    player["kda"] = f'{participant["kills"]}/{participant["deaths"]}/{participant["assists"]}'
                    player["text1"] = f'{participant["totalMinionsKilled"]}cs - {round(participant["goldEarned"] / 1000, 1)}{"k" if participant["goldEarned"] / 1000 > 1 else ""} G'
                    kp = (participant["kills"] + participant["assists"]) * 100
                    if teamkills == 0:
                        player["text2"] = f"0%KP - {participant['visionScore']} V"
                    else:
                        player["text2"] = f"{round( kp / teamkills, 1)}%KP - {participant['visionScore']} V"
                    player["sums"] = [await self.riot_assets_api.get_summoner_spell_icon(participant["summoner1Id"], api_version), await self.riot_assets_api.get_summoner_spell_icon(participant["summoner2Id"], api_version)]
                    output.append(player)

                results = ["Victoire" if raw_data["info"]["teams"][0]["win"] else "Défaite", "Victoire" if raw_data["info"]["teams"][1]["win"] else "Défaite"]
                bans = []
                for team in raw_data["info"]["teams"]:
                    for ban in team["bans"]:
                        bans.append(await self.riot_assets_api.get_champion_icon_by_id(ban["championId"], api_version))
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

            async def save_champion_mastery(champion_id: int, puuid: str, region: str):
                """Save or update the champion mastery for a player and return the points gained since last check."""
                async with self.bot.pool.acquire() as conn:
                    async with conn.transaction():
                        data = await conn.fetchone("SELECT mastery_points FROM LoLChampionsMastery WHERE puuid = ? AND champion_id = ?", (puuid, champion_id))
                        if data is None:
                            await conn.execute("INSERT INTO LoLChampionsMastery (champion_id, puuid, mastery_level, mastery_points, points_since_last_level, points_until_next_level) VALUES (?, ?, ?, ?, ?, ?)", (champion_id, puuid, 0, 0, 0, 0))
                            data = 0
                        else: 
                            data = data['mastery_points']
                        new_data = await self.riot_api.get_player_champion_mastery(puuid, region, champion_id)
                        if new_data.data is not None:
                            await conn.execute("UPDATE LoLChampionsMastery SET mastery_level = ?, mastery_points = ?, points_since_last_level = ?, points_until_next_level = ? WHERE puuid = ? AND champion_id = ?", (new_data.data['championLevel'], new_data.data['championPoints'], new_data.data['championPointsSinceLastLevel'], new_data.data['championPointsUntilNextLevel'], puuid, champion_id))
                        image_level = new_data.data['championLevel'] if new_data.data is not None else 0
                        if image_level > 10:
                            image_level = 10
                        elif image_level in [1, 2, 3]:
                            image_level = 4
                        output = {
                            "gained_points": (new_data.data['championPoints'] - data) if new_data.data is not None else 0,
                            "current_progression": f"{new_data.data['championPointsSinceLastLevel']} / {new_data.data['championPointsUntilNextLevel']}" if new_data.data is not None else "0 / 0",
                            "current_level": new_data.data['championLevel'] if new_data.data is not None else 0,
                            "mastery_image_url": f"https://raw.communitydragon.org/latest/game/assets/ux/mastery/legendarychampionmastery/masterycrest_level{image_level}.cm_updates.png" if new_data.data is not None else None
                        }
                        return output

            async def track_ranked_progression(puuid: str, region: str):
                """Track and update the ranked progression for a player and return the LP change since last check."""

                def _process_lp_change(old_data: tuple, new_data: tuple) -> int:
                    """olddata = (rank, rank_tier, league_points) | newdata = (rank, rank_tier, league_points)"""
                    old_rank, old_tier, old_lp = old_data
                    new_rank, new_tier, new_lp = new_data
                    TIER_ORDER = {
                        "IRON": 0,
                        "BRONZE": 4,
                        "SILVER": 8,
                        "GOLD": 12,
                        "PLATINUM": 16,
                        "EMERALD": 20,
                        "DIAMOND": 24,
                        "MASTER": 28,
                        "GRANDMASTER": 29,
                        "CHALLENGER": 30,
                    }
                    DIVISION_ORDER = {
                        "IV": 0,
                        "III": 1,
                        "II": 2,
                        "I": 3,
                    }
                    
                    def to_linear_lp(tier: str, division: str, lp: int) -> int:
                        base = TIER_ORDER[tier] * 400

                        if tier in ("MASTER", "GRANDMASTER", "CHALLENGER"):
                            return base + lp

                        return base + DIVISION_ORDER[division] * 100 + lp
                    old_total_lp = to_linear_lp(old_rank, old_tier, old_lp)
                    new_total_lp = to_linear_lp(new_rank, new_tier, new_lp)
                    return new_total_lp - old_total_lp

                async with self.bot.pool.acquire() as conn:
                    async with conn.transaction():
                        row = await conn.fetchone("SELECT rank, rank_tier, league_points FROM LoLGamesTracker WHERE puuid = ?", (puuid,))
                        if row is None:
                            await conn.execute("INSERT INTO LoLGamesTracker (puuid, rank, rank_tier, league_points) VALUES (?, ?, ?, ?)", (puuid, "Unranked", "Unranked", 0))
                            row = {"rank": "Unranked", "rank_tier": "Unranked", "league_points": 0}
                        api_rank = await self.riot_api.get_player_league(puuid, region)
                        new_rank = None
                        if api_rank.data is not None:
                            for _ in api_rank.data:
                                if _["queueType"] == "RANKED_SOLO_5x5":
                                    new_rank = _
                                    break
                            if new_rank is not None:
                                old_data = (row["rank"], row["rank_tier"], row["league_points"])
                                new_data = (new_rank["tier"], new_rank.get("rank", "N/A"), new_rank["leaguePoints"])
                                await conn.execute("UPDATE LoLGamesTracker SET rank = ?, rank_tier = ?, league_points = ? WHERE puuid = ?", (new_rank["tier"], new_rank.get("rank", "N/A"), new_rank["leaguePoints"], puuid))
                                if old_data == ("Unranked", "Unranked", 0): return 0
                                lp_change = _process_lp_change(old_data, new_data)
                                return lp_change, new_rank["tier"], new_rank.get("rank", "N/A"), new_rank["leaguePoints"] # return lp_change, new_rank_tier, new_rank_division, new_rank_lp
                        return 0, None, None, None

            async def task(data):
                try:
                    trapcoins_emoji = "<:trapcoins:1108725845339672597>"
                    for row in data:
                            try:
                                id,mentions,ign,puuid,region,last_stored_match = row
                            except ValueError:
                                LogErrorInWebhook()
                                return
                            last_match = await self.riot_api.get_last_match_id(puuid, region)
                            if self.bot.debug:
                                print(last_match, last_stored_match)
                            if (last_stored_match != last_match) and (last_match != "0"): # If the last match is different from the last stored match
                                if last_match is None:
                                    LogErrorInWebhook(f"[LOL 0x04] Erreur lors de la récupération du dernier match pour le joueur `{ign}` ({puuid}).\nMatch None sauvegardé comme dernier match.")
                                    await save_new_match(last_match, puuid)
                                    continue
                                if mentions == "None":
                                    mentions = "?"
                                    tier_bonus = 0
                                api_version = await self.riot_api.get_api_version()
                                try:
                                    match_data, game_duration, game_creation, queuetype, raw_data, summoner_icon_id, long_name, champion_id, game_version = await get_match_data(last_match, puuid, region)
                                except TypeError:
                                    await save_new_match(last_match, puuid)
                                    continue
                                summoner_icon_url = self.riot_assets_api.get_profile_icon_url(summoner_icon_id, api_version)
                                champion_icon_url = await self.riot_assets_api.get_champion_icon_by_id(champion_id, api_version, url=True)
                                isStored = await check_if_stored(last_match)
                                if not isStored:
                                    async with self.bot.pool.acquire() as conn:
                                        async with conn.transaction():
                                            await conn.execute("INSERT INTO lol_match_data (match_id, data) VALUES (?, ?)", (last_match, raw_data))
                                queuetype = await self.riot_assets_api.get_queue_by_id(queuetype)
                                saison, patch, patch2 = api_version.split(".")
                                footer = f'Match {last_match.split("_")[1]} · {raw_data["info"]["platformId"]} · Patch {patch}.{patch2} · Saison {saison} · Game Version {game_version} · Powered by Riot API · Generated by reusreus'
                                ranked_text = None
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
                                            player["championIcon"] = await self.riot_assets_api.get_champion_icon(str(participant["championName"]).replace("Strawberry_",""), api_version)
                                            player["unit_killed"] = participant["totalMinionsKilled"]
                                            player["gold_earned"] = participant["goldEarned"]
                                            player["deaths"] = participant["deaths"]
                                            player["ig_lvl"] = participant["champLevel"]
                                            player["dmg_taken"] = participant["totalDamageTaken"]
                                            player["dmg_dealt"] = participant["totalDamageDealt"]
                                            player["heal"] = participant["totalHeal"]
                                            player["items"] = [await self.riot_assets_api.get_item_icon(participant[f'item{i}'], api_version) for i in range(0, 7)]
                                            players.append(player)
                                        
                                        await asyncio.to_thread(self.lol_game_drawer.draw_swarm, players, game_info)
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
                                    arena_player["championIcon"] = await self.riot_assets_api.get_champion_icon_by_id(match_data["championId"], api_version)
                                    arena_player["mate_championIcon"] = await self.riot_assets_api.get_champion_icon_by_id(arena_player["mate_championIcon"], api_version)
                                    arena_player["kills"] = match_data["kills"]
                                    arena_player["deaths"] = match_data["deaths"]
                                    arena_player["assists"] = match_data["assists"]
                                    arena_player["riotIdGameName"] = match_data["riotIdGameName"]
                                    arena_player["dmg_dealt"] = match_data["totalDamageDealtToChampions"]
                                    arena_player["PlayerScore0"] = match_data["PlayerScore0"]
                                    arena_player["items"] = [await self.riot_assets_api.get_item_icon(match_data[f'item{i}'], api_version) for i in range(0, 7)]
                                    await asyncio.to_thread(self.lol_game_drawer.draw_arena, arena_player)
                                    await asyncio.sleep(1.9)
                                    file = discord.File(f"{FILES_PATH}arena_output.png", filename=f"Arena.png")
                                    embed = discord.Embed(title=f"LoL Game", description=f"<@{mentions}>", color=0x2F3136)
                                    embed.set_footer(text=footer)
                                    embed.set_thumbnail(url=summoner_icon_url)
                                    embed.set_author(name=long_name, icon_url=summoner_icon_url)
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
                                elif raw_data["info"]["queueId"] == 420: # Ranked Solo/Duo
                                    lp_change, new_rank_tier, new_rank_division, new_rank_lp = await track_ranked_progression(puuid, region)
                                    ranked_text = f"{new_rank_tier.title()} {new_rank_division} - {new_rank_lp} LP (+{lp_change})" if new_rank_tier is not None else ""
                                try:
                                    mastery_data = await save_champion_mastery(int(champion_id), puuid, region)
                                    mastery_image = await self.riot_assets_api.get_mastery_icon(mastery_data['current_level'])
                                    channel = self.bot.get_channel(1112233401286672394)
                                    pseudo, rank, queuetype, champion_icon, lvl, rune, sum1, sum2, games_status, game_duartion_to_min, kda, text1, text2, items = await get_drawing_data(match_data, game_duration, mentions, queuetype, raw_data, puuid, region, api_version)
                                    player_list, results, bans = await get_game_data(raw_data, api_version)
                                    if raw_data["info"]["gameMode"] in ["RUBY_TRIAL_2", "RUBY"]: # DoomBot mode only
                                        for n, participant in enumerate(raw_data["info"]["participants"]):
                                            if participant["summonerId"] == "BOT":
                                                player_list[n]["pseudo"] = str(participant["riotIdGameName"]).replace("Ruby_","").title().strip()
                                                player_list[n]["championIcon"] = await self.riot_assets_api.get_champion_icon(str(participant["championName"]).replace("Ruby_",""), api_version)
                                    if ranked_text is not None:
                                        rank = ranked_text
                                    await asyncio.to_thread(self.lol_game_drawer.draw_game, queuetype, player_list, results, bans, mentions)
                                    await asyncio.to_thread(self.lol_game_drawer.draw_player, discordId=mentions, pseudo=pseudo, rank=rank, gameMode=queuetype, championIcon=champion_icon, lvl=lvl, rune=rune, sums1=sum1, sums2=sum2, status=games_status, time=game_duartion_to_min, kda=kda, text1=text1, text2=text2, mastery_level=mastery_data['current_level'], mastery_points=mastery_data['current_progression'],mastery_gained=mastery_data['gained_points'], mastery_image=mastery_image, items=items)
                                    file = discord.File(f"{FILES_PATH}{mentions}-game.png", filename=f"Game.png")
                                    file2 = discord.File(f"{FILES_PATH}{mentions}-player.png", filename=f"Player.png")
                                    gameID = raw_data["metadata"]["matchId"].split("_")[1]
                                    if raw_data["info"]["platformId"] == "OC1": _region = "oce"
                                    elif raw_data["info"]["platformId"].upper() == "EUW1": _region = "euw"
                                    else: _region = raw_data["info"]["platformId"].lower()
                                    layout = LolGameMessage(image_path=f"{FILES_PATH}{mentions}-game.png", image_path2=f"{FILES_PATH}{mentions}-player.png", footer_text=footer, match_id=gameID, region=_region, name_tagline=pseudo)
                                    await channel.send(files=[file,file2], view=layout)
                                    await save_new_match(last_match, puuid)
                                    await asyncio.sleep(1)
                                    # os.remove(f"{FILES_PATH}{mentions}-game.png")
                                    # os.remove(f"{FILES_PATH}{mentions}-player.png")
                                    continue
                                except Exception as e:
                                    LogErrorInWebhook(f"[LOL 0x05] Erreur sur le match `{last_match}`\npuuid: `{puuid}`\n{e}\n{traceback.format_exc()}")
                                    await save_new_match(last_match, puuid)
                                    continue
                            
                except Exception as e:
                    LogErrorInWebhook()
                return

            await task(data)

        except Exception as e:
            LogErrorInWebhook()

    @tasks.loop(minutes=1)
    async def current_game_lol_tracker(self):
        try:
            # self.checheck_lol_games()
            api_version = await self.riot_api.get_api_version()
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchall("SELECT puuid, region, userId FROM LoLGamesTracker")
            for row in data:
                puuid = row[0]
                region = row[1]
                discord_user_id = row[2]
                current_game = await self.riot_api.get_current_game(puuid, region)
                if (current_game.status == 200) and (current_game.data is not None):
                    try:
                        if puuid in self.ongoing_games:
                            if self.ongoing_games[puuid] == current_game.data["gameId"]:
                                continue
                        self.ongoing_games[puuid] = current_game.data["gameId"]
                        players = []
                        for participant in current_game.data["participants"]:
                            rank_data = await self.riot_api.get_player_league(participant["puuid"], region)
                            rank_tier = "Unranked"
                            lp = 0
                            if rank_data.data:
                                entry = rank_data.data[0]
                                if 'tier' in entry and 'rank' in entry and 'leaguePoints' in entry:
                                    rank_tier = f"{entry['tier'].title()} {entry['rank'].upper()} ({entry['leaguePoints']} LP)"
                            if rank_tier == "Unranked (0 LP)" or rank_tier == "Unranked":
                                rank_tier = "Non classé"

                            team_id = participant["teamId"]
                            player_data = await self.riot_api.get_account_by_puuid(participant["puuid"], region)
                            username = f"{player_data.data['gameName']}#{player_data.data['tagLine']}" if player_data.data and 'gameName' in player_data.data else "Mode Streamer"

                            champions_name = await self.riot_assets_api.get_champion_name_by_id(participant["championId"], api_version)
                            champions_name_clean = champions_name.lower().replace("'", "").replace(".", "").replace(" ", "_")
                            champions_emoji = None
                            for guild_id in [1464341094769885186,1464341347564781824,1464341600682377411,1464341853473345579]:
                                guild = self.bot.get_guild(guild_id)
                                if guild is not None:
                                    champions_emoji = discord.utils.get(guild.emojis, name=champions_name_clean)
                                    if champions_emoji and champions_emoji.id and champions_emoji.name:
                                        print(f"[LOL TRACKER] Emoji trouvé pour le champion {champions_name_clean} dans la guilde {guild.name}.")
                                        champions_emoji = f"<:{champions_emoji.name}:{champions_emoji.id}>"
                                        break
                            if champions_emoji is None:
                                print(f"[LOL TRACKER] Aucun emoji trouvé pour le champion {champions_name_clean}, utilisation du nom du champion à la place.")
                                champions_emoji = champions_name
                            
                            players.append({
                                "username": username,
                                "championId": participant["championId"],
                                "champions_emoji": champions_emoji,
                                "rank_tier": rank_tier,
                                "team_id": team_id
                            })
                        user = await self.bot.fetch_user(discord_user_id)
                        embed = discord.Embed(title="Partie en cours détectée", description=f"Une partie en cours a été détectée voici quelques informations...", color=0x2F3136)
                        
                        filed_team_1 =""
                        filed_team_2 =""
                        for p in players:
                            if p["team_id"] == 100:
                                filed_team_1 += f"\n- {p['champions_emoji']} **{p['username']}** - {p['rank_tier']}"
                            else:
                                filed_team_2 += f"\n- {p['champions_emoji']} **{p['username']}** - {p['rank_tier']}"
                        embed.add_field(name="Équipe 1", value=filed_team_1, inline=True)
                        embed.add_field(name="Équipe 2", value=filed_team_2, inline=True)
                        await user.send(embed=embed)
                    except Exception as e:
                        traceback.print_exc()
                        LogErrorInWebhook(f"[CURRENT GAME TRACKER] Erreur lors de l'envoi du message pour le joueur `{puuid}` et l'utilisateur Discord `{discord_user_id}`.\n {e}")
        except Exception as e:
            traceback.print_exc()
            LogErrorInWebhook(f"[CURRENT GAME TRACKER] Erreur lors de la vérification des parties en cours.\n {e}")

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
            puuid = await self.riot_api.get_puuid_by_summoner_name(ign.split("#")[0], tagLine, region)
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
                puuid = await self.riot_api.get_puuid_by_summoner_name(pseudo, tagLine, region)
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
    
