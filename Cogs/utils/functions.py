import discord, datetime, traceback
from typing import TYPE_CHECKING
from .data import commands_id_dict, daily_claim_interest
from .path import JSON_DATA, G_STATS
from discord_webhook import DiscordWebhook
import json, re, inspect, os, random, asqlite
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from discord.ext import commands
if TYPE_CHECKING:
    from ...bot import Trapard

class TrapardeurV2:
    """Gestion de la DB Trapardeur. DB Structure: `userId:str`, `vocalTime:int`, `messageSent:int`, `commandSent:int`"""
    def __init__(self, pool: asqlite.Pool, userId:str=None, vocalTime:int=None, messageSent:int=None, commandSent:int=None):
        self.userId = userId
        self.vocalTime = vocalTime
        self.messageSent = messageSent
        self.commandSent = commandSent
        self.pool = pool

    async def add(self, userId:str, vocalTime:int=None, messageSent:int=None, commandSent:int=None):
        """Ajoute un utilisateur à la base de données. """
        if vocalTime is None:
            vocalTime = 0
        if messageSent is None:
            messageSent = 0
        if commandSent is None:
            commandSent = 0
        user_data = (userId, vocalTime, messageSent, commandSent)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO Trapardeur (userId, vocalTime, messageSent, commandSent) VALUES (?, ?, ?, ?)", user_data)
        return
    
    async def delete(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM Trapardeur WHERE userId = ?", (self.userId,))
        return

    async def update(self, userId:str, vocalTime:int=None, messageSent:int=None, commandSent:int=None):
        prev = await self.get()
        if vocalTime is None:
            vocalTime = prev[0][2]
        if messageSent is None:
            messageSent = prev[0][3]
        if commandSent is None:
            commandSent = prev[0][4]
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("UPDATE Trapardeur SET vocalTime = ?, messageSent = ?, commandSent = ? WHERE userId = ?", (vocalTime, messageSent, commandSent, userId))
        return

    async def get(self):
        """Renvoie les données de l'utilisateur. `data[0][2] = vocalTime`, `data[0][3] = messageSent`, `data[0][4] = commandSent`"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetchall("SELECT * FROM Trapardeur WHERE userId = ?", (self.userId,))
        return rows
    
    async def get_all(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetchall("SELECT * FROM Trapardeur")
        return rows
    
    async def is_in(self) -> bool:
        """Renvoie True si l'utilisateur est dans la base de données, False sinon."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetchall("SELECT * FROM Trapardeur WHERE userId = ?", (self.userId,))
        if len(rows) == 0:
            return False
        return True

    def __str__(self):
        return f"userId: {self.userId}, vocalTime: {self.vocalTime}, messageSent: {self.messageSent}, commandSent: {self.commandSent}"



def LogErrorInWebhook(error=""):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f = "<@311013099719360512> Erreur à **" + current_time + "** :"
    if traceback.format_exc() is not None and traceback.format_exc() != "NoneType: None":
        f += "```" + traceback.format_exc() + "```"
    if error != "":
        f += "MSG Custom: ```" + error + "```"
    DiscordWebhook(url=os.environ.get("ERROR_WEBHOOK"), content=str(f)).execute()

async def command_counter(user_id: str, bot, type:str=None):
    """
        Increment the command counter for the user
    """
    if type is None:
        handler = TrapardeurV2(pool=bot.pool, userId=user_id)
        if await handler.is_in():
            prev = await handler.get()
            await handler.update(userId=user_id, commandSent=prev[0][4]+1, messageSent=prev[0][3], vocalTime=prev[0][2])
        else:
            await handler.add(userId=user_id, commandSent=1, messageSent=0, vocalTime=0)
    else:
        handler = TrapardeurV2(userId=user_id, pool=bot.pool)
        if await handler.is_in():
            prev = await handler.get()
            await handler.update(userId=user_id, messageSent=prev[0][3]+1, commandSent=prev[0][4], vocalTime=prev[0][2])
        else:
            await handler.add(userId=user_id, messageSent=1, commandSent=0, vocalTime=0)

def create_embed(title: str, description: str, color=discord.Color.blue(), author=None, thumbnail=None, fields: list=None, footer=None, suggestions: list=None, image = None):
    """
        Fields must be :
            [
                {"name": "dataname1", "value": "datavalue1", "inline": False}
            ]
    """
    embed = discord.Embed(title=title, description=description, color=color)
    
    if author:
        embed.set_author(name=author["name"], icon_url=author["icon_url"])
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if fields:
        if len(fields) > 1:
            for i, field in enumerate(fields):
                embed.add_field(name=fields[i]["name"], value=fields[i]["value"], inline=fields[i]["inline"])
        else:
            field = fields[0]
            embed.add_field(name=fields["name"], value=fields["value"], inline=fields["inline"])
            
    if suggestions:
        txt = ""
        for i, sug in enumerate(suggestions):
            if i != len(suggestions) -1:
                txt += f"</{sug}:{commands_id_dict[sug][0]}> - "
            else:
                txt += f"</{sug}:{commands_id_dict[sug][0]}>"
        embed.add_field(name="Quelques commandes suggérées:", value=txt, inline=False)

    if footer:
        embed.set_footer(text=footer["text"], icon_url=footer["icon_url"])
    else:
        maintenant = datetime.datetime.now()
        format_date_heure = maintenant.strftime("à %H:%M le %d/%m/%y")
        embed.set_footer(text=f"Trapard © by !Reu$ - {format_date_heure}", icon_url="http://reusteur.org/trap_icon.png")
    return embed

def convert_str_to_emojis(string):
    emojis = {
        "0": "0️⃣",
        "1": "1️⃣",
        "2": "2️⃣",
        "3": "3️⃣",
        "4": "4️⃣",
        "5": "5️⃣",
        "6": "6️⃣",
        "7": "7️⃣",
        "8": "8️⃣",
        "9": "9️⃣",
        " ": " ",
        "A": "🇦",
        "B": "🇧",
        "C": "🇨",
        "D": "🇩",
        "E": "🇪",
        "F": "🇫",
        "G": "🇬",
        "H": "🇭",
        "I": "🇮",
        "J": "🇯",
        "K": "🇰",
        "L": "🇱",
        "M": "🇲",
        "N": "🇳",
        "O": "🇴",
        "P": "🇵",
        "Q": "🇶",
        "R": "🇷",
        "S": "🇸",
        "T": "🇹",
        "U": "🇺",
        "V": "🇻",
        "W": "🇼",
        "X": "🇽",
        "Y": "🇾",
        "Z": "🇿",
        "a": "🇦",
        "b": "🇧",
        "c": "🇨",
        "d": "🇩",
        "e": "🇪",
        "f": "🇫",
        "g": "🇬",
        "h": "🇭",
        "i": "🇮",
        "j": "🇯",
        "k": "🇰",
        "l": "🇱",
        "m": "🇲",
        "n": "🇳",
        "o": "🇴",
        "p": "🇵",
        "q": "🇶",
        "r": "🇷",
        "s": "🇸",
        "t": "🇹",
        "u": "🇺",
        "v": "🇻",
        "w": "🇼",
        "x": "🇽",
        "y": "🇾",
        "z": "🇿"
    }
    emoji_string = ""
    for char in string:
        emoji_char = emojis.get(char, char)
        emoji_string += emoji_char
    return emoji_string

def convert_int_to_emojis(number: int):
    emojis = {
        0: "0️⃣",
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣"
    }

    if number == 0:
        return emojis[0]

    emoji_string = ""
    while number > 0:
        digit = number % 10
        emoji = emojis[digit]
        emoji_string = emoji + emoji_string
        number //= 10

    return emoji_string

def printFormat(string, numWanted):
    try:
        if string is None:
            return ""
        spaces = " " * (numWanted - len(string))
        return string + spaces
    except Exception as e:
        LogErrorInWebhook()

def load_json_data(item: str=None, userid:str=None, opt_val: str=False, opt_val2: str=None, opt_val3: str=None, opt_val4: str=None):
    """
        Return all data as dict.

        ``*item``: optional.
                it can be: ["trapcoins", "sudoku-points", "devinette", "mots-meles",
                
                "sudoku-score", "streak", "interets", "lol-games","roulette-hist","quizz-ladder",
                
                "typeracer-scores", "song-stats", "trapeur"]
        
        ``**UserID``: ► Optional.
    """
    try:
        file = JSON_DATA
        with open(file, "r") as f:
            data = json.loads(f.read())
        
        possible_items = ["trapcoins", "sudoku-points", 
                        "devinette", "mots-meles", 
                        "sudoku-score", "streak", 
                        "interets", "lol-games",
                        "roulette-history","quizz-ladder", 
                        "typeracer-scores", "song-stats", "trapeur"]

        if item:
            if item in possible_items:
                if userid:
                    if data.get(item) and data[item].get(userid):
                        if opt_val and data[item][userid].get(opt_val):
                            return data[item][userid][opt_val]
                        else:
                            return data[item][userid]
                    else:
                        return "UserNotFound"
                else:
                    return data[item]
            else:
                return "Erreur item"
        else:
            return data
    except Exception as e:
        LogErrorInWebhook()

def write_item(item: str, userid: str=None, values: dict=None, array: list=None):
    """
        Write new data to file.

        ``*Item to write``
                possible_items = ["trapcoins", "sudoku-points", 
                      "devinette", "mots-meles", 
                      "sudoku-score", "streak", 
                      "interets", "lol-games",
                      "roulette-hist","quizz-ladder", 
                      "typeracer-scores", "song-stats", "trapeur"]

        ``**UserID`` ► Optional

        ``***Values, dict (take userid)``:

                trapcoins: {"trapcoins": val1, "epargne": val2}

                devinette: {"points": 12, "total_games": 4}

                sudoku-points: {"points": 13, "easy": 4, "medium": 1, "hard": 1, "insane": 2, "temps": 99999}\n

                streak: {"streak": 10, "timestamp": 1686466232}

                mots-meles: {"points": 44, "temps": 74}

                interets: {"tier": 10}

                lol-games: {"last-game": "EUW1_6447484106"}

                quizz-ladder: {"points": 105}

                type-racer: {"score": 3}

                trapeur: {"voice_time": 0,"message_sent": 0,"command_used": 0}

        ``***Values, dict (do not userid)``:

                roulette-history: [...25,1,13,3,9,29],

                song-stats: {"time": 5718, "number-played": 1206324}


    """    
    try:
        file_path = JSON_DATA
        data = load_json_data()
        possible_items = ["trapcoins",
                        "devinette", "mots-meles", 
                        "sudoku-points", "streak", 
                        "interets", "lol-games",
                        "roulette-history","quizz-ladder", 
                        "typeracer-scores", "song-stats", "trapeur"]
        if item in possible_items:
            if userid:
                data[item][userid] = values
            else:
                data[item] = values
            if item == 'roulette-history':
                data[item] = array
            with open(file_path, "w") as f:
                json.dump(data, f)
            f.close()
        else:
            return "Erreur item"
    except Exception as e:
        LogErrorInWebhook()

def is_url(url: str) -> bool:
    groups = re.match(r"http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", url)
    if groups:
        return True
    return False

def init_user_to_item(item:str, userid: str=None, values: dict=None):
    caller_frame = inspect.currentframe().f_back
    caller_function_name = caller_frame.f_code.co_name
    caller_file_name = caller_frame.f_code.co_filename
    caller_line_number = caller_frame.f_lineno
    txt = f"Error in {caller_function_name} at line {caller_line_number} in {caller_file_name}"
    LogErrorInWebhook(f"init_user_to_item {item} {userid} {values} {txt}")
    try:
        file_path = JSON_DATA
        data = load_json_data()
        data[item][userid] = values
        with open(file_path, "w") as f:
            json.dump(data, f)
        f.close()
    except Exception as e:
        LogErrorInWebhook()

def trapcoins_handler(type: str, userid: str=None, trapcoins_val: int=None, epargne_val: int=None):
    """
        Type : ["get", "add", "remove", "baltop"]
        Get: return tuple trap/ep
    """
    try:
        possible_type = ["get", "add", "remove", "baltop", 'baltop2']

        if type in possible_type:
            if type == "get" and userid:
                data = load_json_data(item="trapcoins", userid=str(userid))
                print(data)
                if data is None or data == "UserNotFound":
                    init_user_to_item(item="trapcoins", userid=str(userid), values={"trapcoins": 0, "epargne": 0})
                    return 0, 0
                else:
                    return data['trapcoins'], data['epargne']
            if type == "add" and userid:
                prev = load_json_data(item="trapcoins", userid=str(userid))
                if trapcoins_val:
                    prev["trapcoins"] += trapcoins_val
                if epargne_val: 
                    prev['epargne'] += epargne_val
                write_item(item="trapcoins", userid=str(userid), values=prev)
            if type == "remove" and userid:
                prev = load_json_data(item="trapcoins", userid=str(userid))
                if trapcoins_val:
                    prev["trapcoins"] -= trapcoins_val
                if epargne_val: 
                    prev['epargne'] -= epargne_val
                write_item(item="trapcoins", userid=str(userid), values=prev)
            if type == "baltop":
                data = load_json_data(item="trapcoins")
                sorted_data = sorted(data.items(), key=lambda x: x[1]['trapcoins'] + x[1]['epargne'], reverse=True)
                return sorted_data[0]
            if type == "baltop2": 
                data = load_json_data(item="trapcoins")
                sorted_data = sorted(data.items(), key=lambda x: x[1]['trapcoins'] + x[1]['epargne'], reverse=True)
                return sorted_data
    except Exception as e:
        LogErrorInWebhook()

def afficher_nombre_fr(nombre: int, decimal: int = 0):
    """Return french numbers display\n\nEx: `1000` → `1 000`"""
    format_string = "{{:,.{}f}}".format(decimal)
    nombre_formate = format_string.format(nombre).replace(",", " ").replace(".", ",")
    return nombre_formate

def load_json_data(item: str=None, userid:str=None, opt_val: str=False, opt_val2: str=None, opt_val3: str=None, opt_val4: str=None):
    """
        Return all data as dict.

        ``*item``: optional.
                it can be: ["trapcoins", "sudoku-points", "devinette", "mots-meles",
                
                "sudoku-score", "streak", "interets", "lol-games","roulette-hist","quizz-ladder",
                
                "typeracer-scores", "song-stats", "trapeur"]
        
        ``**UserID``: ► Optional.
    """
    try:
        file = JSON_DATA
        with open(file, "r") as f:
            data = json.loads(f.read())
        
        possible_items = ["trapcoins", "sudoku-points", 
                        "devinette", "mots-meles", 
                        "sudoku-score", "streak", 
                        "interets", "lol-games",
                        "roulette-history","quizz-ladder", 
                        "typeracer-scores", "song-stats", "trapeur"]

        if item:
            if item in possible_items:
                if userid:
                    if data.get(item) and data[item].get(userid):
                        if opt_val and data[item][userid].get(opt_val):
                            return data[item][userid][opt_val]
                        else:
                            return data[item][userid]
                    else:
                        return "UserNotFound"
                else:
                    return data[item]
            else:
                return "Erreur item"
        else:
            return data
    except Exception as e:
        LogErrorInWebhook()

def write_item(item: str, userid: str=None, values: dict=None, array: list=None):
    """
        Write new data to file.

        ``*Item to write``
                possible_items = ["trapcoins", "sudoku-points", 
                      "devinette", "mots-meles", 
                      "sudoku-score", "streak", 
                      "interets", "lol-games",
                      "roulette-hist","quizz-ladder", 
                      "typeracer-scores", "song-stats", "trapeur"]

        ``**UserID`` ► Optional

        ``***Values, dict (take userid)``:

                trapcoins: {"trapcoins": val1, "epargne": val2}

                devinette: {"points": 12, "total_games": 4}

                sudoku-points: {"points": 13, "easy": 4, "medium": 1, "hard": 1, "insane": 2, "temps": 99999}\n

                streak: {"streak": 10, "timestamp": 1686466232}

                mots-meles: {"points": 44, "temps": 74}

                interets: {"tier": 10}

                lol-games: {"last-game": "EUW1_6447484106"}

                quizz-ladder: {"points": 105}

                type-racer: {"score": 3}

                trapeur: {"voice_time": 0,"message_sent": 0,"command_used": 0}

        ``***Values, dict (do not userid)``:

                roulette-history: [...25,1,13,3,9,29],

                song-stats: {"time": 5718, "number-played": 1206324}


    """    
    try:
        file_path = JSON_DATA
        data = load_json_data()
        possible_items = ["trapcoins",
                        "devinette", "mots-meles", 
                        "sudoku-points", "streak", 
                        "interets", "lol-games",
                        "roulette-history","quizz-ladder", 
                        "typeracer-scores", "song-stats", "trapeur"]
        if item in possible_items:
            if userid:
                data[item][userid] = values
            else:
                data[item] = values
            if item == 'roulette-history':
                data[item] = array
            with open(file_path, "w") as f:
                json.dump(data, f)
            f.close()
        else:
            return "Erreur item"
    except Exception as e:
        LogErrorInWebhook()


async def lol_player_in_game(player, bot):
    APIKEY = os.environ.get("RIOT_API")
    zigotos_ID = {
        'ReuS': ['bOYnT0LwqqtQ-0vUNtqpP0V5Cnuf688yW-_5PRpyJXi72xy_Fkpa_yTsRw', 'uppi1LvsGJDWbwJHEaZJYNeND_227qzYA_0ce9Kqipl08fNYj7eMV2-sFA'],
        'Toto': ['R5JdltxLcVtD5dAOlHrKSWostfOuGYiFcdFCJAK5KdUesE8rBRCKeS7AiA', 'fzCP-o0Opq_vBD8SbExaKp9teELAyf--5AR_196WVRx2cI7b24mBhsxJ3Q'],
        'Fesko': ['-i9GGaXrxRXCkJ2GbqpPu-nAM4oyBWLFBrSoQqInYnWc4W2vuSCrdABVDg', 'TrfSqJwoU9MCl5b7OVpowUdWeyi_SbjZxMjeKYaOF4LGVba4u8D3_dlx9g'],
        'Virgile': ['VTHWixy5t9ZgR2bPuWRAWu1aKRwGe4qTMO1SPUe4EOjM9qL29nw0k1tUpQ'],
        'Enzo': ['CgWYBiR461KCjYYZHwMLjxIKj7ZwtEl-kLmaezCYhqcOSm3iHmPR0Lb_vZtGv-pZfdxTw9aE4Zh7TA']
    }

    to_check = zigotos_ID[player]

    user_status = False

    for check in to_check:
        resp = await bot.session.get(f"https://euw1.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/{check}?api_key={APIKEY}")
        if resp.status == 200:
            user_status = True
            return user_status
    return user_status

def display_big_nums(num: int):

    suffixes = ['', 'k', 'M', 'B', 'T']
    if num == 0:
        return '0'
    
    magnitude = 0
    while abs(num) >= 1000:
        num /= 1000.0
        magnitude += 1
    
    num_str = str(round(num, 2))  # Arrondir à deux décimales
    if num_str.endswith('.0'):
        num_str = num_str[:-2]  # Supprimer le '.0' si le nombre est un entier
    
    num_str = num_str.replace('\u202f', '')  # Supprimer les espaces insécables
    
    return f"{num_str} {suffixes[magnitude]}"

def convert_k_m_to_int(string: str):
    try:
        if "k" in string.lower():
            new_int = int(float(string.lower().replace("k", "")) * 1000)
        elif "m" in string.lower():
            new_int = int(float(string.lower().replace("m", "")) * 1000000)
        elif "b" in string.lower():
            new_int = int(float(string.lower().replace("b", "")) * 1000000000)
        elif "t" in string.lower():
            new_int = int(float(string.lower().replace("t", "")) * 1000000000000)
        else:
            new_int = int(string)
        return new_int
    except ValueError:
        return "ValueError"
    
def calc_usr_gain_by_tier(userid: int):
    user_tier = load_json_data(item="interets", userid=str(userid))
    return daily_claim_interest[user_tier["tier"]]

def convert_txt_to_colored(text: str, color: str, background: str=None, bold: bool=False, underline: bool=False):
    """Convert text to formated colored text.

    Inputs
    -----------
    color: :class:`str`
        List: grey, red, green, yellow, blue, pink, cyan, white

    background: :class:`Optional` `str` 
        List: red, dark, light-blue, white, light-grey
    """
    escape_char = "\u001b"
    close_char = "[0;0m"
    bold_char = "1"
    underline_char = "4"
    colors = {
        "grey": "30",
        "red": "31",                                       
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "pink": "35",
        "cyan": "36",
        "white": "37"
    }
    backgrounds = {
        "red": "41",
        "dark": "40",
        "light-blue": "45",
        "white": "47",
        "light-gray": "46"
    }

    color_code = colors.get(color, "37")  # Par défaut, utiliser "37" pour blanc si la couleur n'est pas trouvée
    background_code = backgrounds.get(background, "0")  # Par défaut, utiliser "40" pour fond sombre si le fond n'est pas trouvé

    # Construction de la chaîne d'échappement pour le formatage
    format_string = f"```ansi\n{escape_char}[0;{background_code};{color_code}"
    if bold:
        format_string += f";{bold_char}"
    if underline:
        format_string += f";{underline_char}"
    format_string += f"m{text}{escape_char}{close_char}```"

    return format_string

def format_duration(duration_in_seconds: int) -> str:
    """Return seconds to minutes or hours or days."""
    try:
        days = duration_in_seconds // 86400
        hours = (duration_in_seconds % 86400) // 3600
        minutes = (duration_in_seconds % 3600) // 60
        seconds = duration_in_seconds % 60

        if days > 0:
            return f'{days}d:{hours:02}h:{minutes:02}m'
        elif hours > 0:
            return f'{hours:02}h:{minutes:02}m:{seconds:02}s'
        else:
            return f'{minutes:02}m:{seconds:02}s'
    except Exception as e:
        LogErrorInWebhook()

async def get_username_from_id(user_id, bot: commands.Bot):
    """Returns the username corresponding to the given user ID."""
    try:
        user = await bot.fetch_user(user_id)
        return user.display_name
    except discord.NotFound:
        # If the user is not found, return None
        return None

def editGstats(userID, total_gains=None, total_pertes=None, transfert=None, claims=None, win_alpha=None, nb_games=None, biggest_win=None):
    try:
        with open(G_STATS, "r") as file:
            player_data = json.load(file)
        
        userID = str(userID)
        if userID in player_data:
            if total_gains is not None:
                prev1 = player_data[userID]["gains_total"]
                final = int(prev1) + int(total_gains)
                player_data[userID]["gains_total"] = final
            if total_pertes is not None:
                prev = player_data[userID]["pertes_total"]
                final = int(prev) + int(total_pertes)
                player_data[userID]["pertes_total"] = final
            if transfert is not None:
                prev = player_data[userID]["transfert"]
                final = int(prev) + int(transfert)
                player_data[userID]["transfert"] = final
            if claims is not None:
                prev = player_data[userID]["claims"]
                final = int(prev) + int(claims)
                player_data[userID]["claims"] = final
            if win_alpha is not None:
                prev = player_data[userID]["win_en_alpha"]
                final = int(prev) + int(win_alpha)
                player_data[userID]["win_en_alpha"] = final
            if nb_games is not None:
                prev = player_data[userID]["nombre_parties_jouees"]
                final = int(prev) + int(nb_games)
                player_data[userID]["nombre_parties_jouees"] = final
            if biggest_win is not None:
                prev = player_data[userID]["plus_gros_gain"]
                if int(biggest_win) > int(prev):
                    player_data[userID]["plus_gros_gain"] = int(biggest_win)
        else:
            player_data[userID] = {"gains_total": 0, "pertes_total": 0, "transfert": 0, "claims": 0, "nombre_parties_jouees": 0, "plus_gros_gain": 0, "win_en_alpha": 0}
            if total_gains is not None:
                prev1 = player_data[userID]["gains_total"]
                final = int(prev1) + int(total_gains)
                player_data[userID]["gains_total"] = final
            if total_pertes is not None:
                prev = player_data[userID]["pertes_total"]
                final = int(prev) + int(total_pertes)
                player_data[userID]["pertes_total"] = final
            if transfert is not None:
                prev = player_data[userID]["transfert"]
                final = int(prev) + int(transfert)
                player_data[userID]["transfert"] = final
            if claims is not None:
                prev = player_data[userID]["claims"]
                final = int(prev) + int(claims)
                player_data[userID]["claims"] = final
            if win_alpha is not None:
                prev = player_data[userID]["win_en_alpha"]
                final = int(prev) + int(win_alpha)
                player_data[userID]["win_en_alpha"] = final
            if nb_games is not None:
                prev = player_data[userID]["nombre_parties_jouees"]
                final = int(prev) + int(nb_games)
                player_data[userID]["nombre_parties_jouees"] = final
            if biggest_win is not None:
                prev = player_data[userID]["plus_gros_gain"]
                if int(biggest_win) > int(prev):
                    player_data[userID]["plus_gros_gain"] = int(biggest_win)
        
        with open(G_STATS, "w") as file:
            json.dump(player_data, file)
    except Exception as e:
        LogErrorInWebhook()

def seconds_until(hours, minutes):
    given_time = datetime.time(hours, minutes)
    now = datetime.datetime.now()
    future_exec = datetime.datetime.combine(now, given_time)
    if (future_exec - now).days < 0:  # If we are past the execution, it will take place tomorrow
        future_exec = datetime.datetime.combine(now + datetime.timedelta(days=1), given_time) # days always >= 0
    return (future_exec - now).total_seconds()

def probability_7_percent():
    try:
        return random.random() < 0.002
    except Exception as e:
        LogErrorInWebhook()

def probability_1_percent():
    try:
        return random.random() < 0.001
    except Exception as e:
        LogErrorInWebhook()

def getDriver():
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Firefox(options=options)
        return driver
    except Exception as e:
        LogErrorInWebhook()



def addMemory(previousMem, role, content, user):
    try:
        if user is not None:
            formatTxt = [{"role": f"{role}", "content": f"Context: L'autheur du message est {user}. Message: {content}"}]
        else:
            formatTxt = [{"role": f"{role}", "content": f"{content}"}]
        previousMem += formatTxt
        return previousMem
    except Exception as e:
        LogErrorInWebhook()

def getUserById(id: int):
    try:
        if id == 311013099719360512:
            user = "Malo"
        elif id == 500247249154998273:
            user = "Virgile"
        elif id == 267439803786723329:
            user = "TotoLeRigolo"
        elif id == 548195565653983232:
            user = "Raphaël"
        elif id == 889038773575368744 or id == 301852174605090816:
            user = "Danny"
        elif id == 602914038703194212:
            user = "Noa"
        elif id == 1082380030144946186:
            user = "La famille de Malo"
        else:
            user = "Connais pas"
        return user
    except Exception as e:
        LogErrorInWebhook()

def calculate_coins(time_elapsed, base_coins):
    if time_elapsed < 300: #moins de 5 minutes
        coins = base_coins * 2
    elif time_elapsed < 600: #moins de 10 minutes
        coins = base_coins * 1.5
    elif time_elapsed < 1200: #moins de 20 minutes
        coins = base_coins * 1.3
    elif time_elapsed < 1800: #moins de 30 minutes
        coins = base_coins * 1.25
    else: #plus de 30 minutes
        coins = base_coins * 1.05
    
    return coins

def calculate_coins2(time_elapsed, base_coins):
    if time_elapsed < 60: #moins de 5 minutes
        coins = base_coins * 5
    elif time_elapsed < 120: #moins de 10 minutes
        coins = base_coins * 4
    elif time_elapsed < 180: #moins de 20 minutes
        coins = base_coins * 3
    elif time_elapsed < 240: #moins de 30 minutes
        coins = base_coins * 2
    else: #plus de 30 minutes
        coins = base_coins * 1.5
    return coins

async def check_how_many_played(gameID, bot):
    channel = bot.get_channel(1101746866732933172)
    found = 0
    async for message in channel.history(limit=1000):
        try:
            if str(message.content).split("Game ID = ")[1].split("Grille de l'utilisateur :")[0].strip() == gameID:
                found += 1
        except:
            pass
    return found

async def check_how_many_played2(gameID, bot):
    channel = bot.get_channel(1107955398322962482)
    found = 0
    async for message in channel.history(limit=1000):
        try:
            if str(message.content).split("Game ID:")[1].split("Userid:")[0].strip() == gameID:
                found += 1
        except:
            pass
    return found



def str_to_list(strr):

    grid_list = []

    for key in strr.keys():
        grid_list.append(strr[key])
    
    return grid_list


def solve_sudoku(grid):
    # Trouver la prochaine case vide
    row, col = find_empty_cell(grid)

    # Si toutes les cases sont remplies, le sudoku est résolu
    if row is None:
        return True

    # Essayer de remplir la case vide avec les chiffres de 1 à 9
    for num in range(1, 10):
        if is_valid_move(grid, row, col, num):
            # Si le chiffre est valide, le placer dans la case
            grid[row][col] = num

            # Récursivement résoudre le reste de la grille
            if solve_sudoku(grid):
                return True

            # Si la récursivité échoue, annuler le dernier mouvement et essayer avec un autre chiffre
            grid[row][col] = 0

    # Si aucun chiffre ne fonctionne, la grille n'a pas de solution
    return False


def find_empty_cell(grid):
    # Trouver la première case vide dans la grille
    for row in range(9):
        for col in range(9):
            if grid[row][col] == 0:
                return row, col
    # Si toutes les cases sont remplies, retourner None
    return None, None


def is_valid_move(grid, row, col, num):
    # Vérifier si le chiffre peut être placé dans la case sans violer les règles du sudoku
    return (
        is_valid_row(grid, row, num)
        and is_valid_col(grid, col, num)
        and is_valid_box(grid, row - row % 3, col - col % 3, num)
    )


def is_valid_row(grid, row, num):
    # Vérifier si le chiffre n'apparaît pas déjà sur la ligne
    return num not in grid[row]


def is_valid_col(grid, col, num):
    # Vérifier si le chiffre n'apparaît pas déjà sur la colonne
    return all(grid[i][col] != num for i in range(9))


def is_valid_box(grid, row, col, num):
    # Vérifier si le chiffre n'apparaît pas déjà dans la case 3x3
    return all(
        grid[row + i][col + j] != num for i in range(3) for j in range(3)
    )

def print_grid(grid):
    # Afficher la grille
    g = "```+-------+-------+-------+\n"
    for i, row in enumerate(grid):
        # Afficher une ligne horizontale entre les blocs de 3x3
        if i % 3 == 0:
            g += "+-------+-------+-------+\n"
        # Afficher chaque case avec une barre verticale entre les blocs de 3x3
        row_str = ""
        for j, num in enumerate(row):
            if j % 3 == 0:
                g += "| "
            if num == 0:
                num = "."
            g += str(num) + " "
        g += "|\n"
        print(row_str)
    g += "+-------+-------+-------+```"
    return g

def compare_grids(solved_grid, user_grid):
    # Vérifier que les deux grilles ont la même taille
    if len(solved_grid) != len(user_grid) or len(solved_grid[0]) != len(user_grid[0]):
        print("Les grilles n'ont pas la même taille.")
        return
    # Comparer chaque case de la grille résolue avec la grille de l'utilisateur
    num_errors = 0
    for i in range(len(solved_grid)):
        for j in range(len(solved_grid[0])):
            if solved_grid[i][j] != user_grid[i][j]:
                num_errors += 1
    # Afficher le nombre d'erreurs
    if num_errors == 0:
        txt = "Bravo, la grille est correcte !"
    else:
        txt = f"Il y a {num_errors} erreurs."

    return txt


def main_sudoku(non_complete_grid, usr_grid):
    if solve_sudoku(non_complete_grid):
        print("La grille a été résolue :")

        dis = print_grid(non_complete_grid)

        txt = compare_grids(non_complete_grid, usr_grid)
        return txt, dis
    else:
        print("La grille n'a pas de solution.")

def verifier_grille_sudoku(grille):
    # Vérifier les lignes
    for ligne in grille:
        if not est_valide(ligne):
            return False

    # Vérifier les colonnes
    for colonne in range(9):
        if not est_valide([grille[ligne][colonne] for ligne in range(9)]):
            return False

    # Vérifier les régions 3x3
    for region_ligne in range(0, 9, 3):
        for region_colonne in range(0, 9, 3):
            region = [grille[i][j] for i in range(region_ligne, region_ligne + 3) for j in range(region_colonne, region_colonne + 3)]
            if not est_valide(region):
                return False

    return True

def est_valide(liste):
    # Vérifier si la liste contient tous les chiffres de 1 à 9 exactement une fois
    chiffres = set(liste)
    return len(chiffres) == 9 and all(chiffre in range(1, 10) for chiffre in chiffres)

def afficher_grille_sudoku(grille):
    lignes = []
    for i, ligne in enumerate(grille):
        if i % 3 == 0 and i != 0:
            lignes.append('- - - - - - - - - - -')
        elements_ligne = []
        for j, valeur in enumerate(ligne):
            if j % 3 == 0 and j != 0:
                elements_ligne.append('|')
            if valeur == 0:
                elements_ligne.append('_')
            else:
                elements_ligne.append(str(valeur))
        lignes.append(' '.join(elements_ligne))
    return '\n'.join(lignes)
