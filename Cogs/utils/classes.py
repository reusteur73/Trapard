import asqlite, discord, random
# from bot import Trapard
from .functions import LogErrorInWebhook, getUserById
from typing import Literal
from asqlite import Pool

class Trapardeur:
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
            rows = await conn.fetchall("SELECT * FROM Trapardeur WHERE userId = ?", (self.userId,))
        return rows
    
    async def get_all(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetchall("SELECT * FROM Trapardeur")
        return rows
    
    async def is_in(self):
        """Renvoie True si l'utilisateur est dans la base de données, False sinon."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetchall("SELECT * FROM Trapardeur WHERE userId = ?", (self.userId,))
        if len(rows) == 0:
            return False
        return True

    def __str__(self):
        return f"userId: {self.userId}, vocalTime: {self.vocalTime}, messageSent: {self.messageSent}, commandSent: {self.commandSent}"

class IaView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.val = None

        self.rejouer_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Oui", custom_id="oui")
        self.add_item(self.rejouer_button)
        self.rejouer_button.callback = lambda interaction=None, button=self.rejouer_button: self.action(interaction, button)

        self.nope_button = discord.ui.Button(style=discord.ButtonStyle.red, label="Non", custom_id="non")
        self.add_item(self.nope_button)
        self.nope_button.callback = lambda interaction=None, button=self.nope_button: self.action(interaction, button)


    async def action(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except Exception:
            pass
        if button.custom_id == "oui":
            self.rejouer_button.disable = True
            self.val = 1
        elif button.custom_id == "non":
            self.nope_button.disable = True
            self.val = 0

class CallFriends(discord.ui.View):
    try:
        def __init__(self, userId, bot):
            super().__init__(timeout=60)
            self.bot = bot
            self.userid = userId
            self.phrase = ["Hey les filles, si vous pensez que vous êtes bonnes en multi-tasking, venez jouer à League of Legends avec moi et prouvez-le en gérant votre personnage tout en insultant les ennemis !",
                            "Vous voulez voir mes talents de danseur ? Venez sur Discord et regardez-moi danser de joie après avoir gagné une partie de League of Legends !",
                            "Je sais que vous avez toujours voulu voir à quoi ressemble une équipe de filles badass qui peut vaincre tous ses adversaires. Rejoignez-moi sur League of Legends pour réaliser ce rêve !",
                            "Si vous avez déjà joué à Mario Kart et pensé que c'était la compétition la plus intense de votre vie, attendez de voir ce que League of Legends a à offrir !",
                            "Vous voulez savoir comment je me détends après une journée de travail stressante ? En insultant mes ennemis sur League of Legends, bien sûr ! Rejoignez-moi pour cette expérience apaisante.",
                            "Qui a besoin d'un cours de gym quand on peut se défouler en jouant à League of Legends ? Faites travailler vos doigts et votre cerveau en même temps !",
                            "Si vous pensez que les films d'action sont géniaux, attendez de voir les moments de tension incroyables que League of Legends peut offrir. Rejoignez-nous pour une soirée d'adrénaline pure !",
                            "Je suis tellement douée à League of Legends que je pourrais facilement être une professionnelle. Mais je préfère jouer avec mes amies, alors venez jouer avec moi et faites partie de ma team !",
                            "Si vous cherchez un moyen de vous rapprocher de vos amies, il n'y a rien de mieux que de les insulter ensemble sur League of Legends. Rejoignez-nous pour cette expérience de camaraderie unique !",
                            "Je sais que vous êtes déjà des princesses, mais il est temps de devenir des reines. Rejoignez-moi sur League of Legends et dominons le champ de bataille ensemble !"
                        ]

        @discord.ui.button(label="Appeler la bande", style=discord.ButtonStyle.success, emoji="☎️")
        async def playS(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            copains = [500247249154998273, 548195565653983232, 311013099719360512, 267439803786723329]
            for copain in copains:
                if int(self.userid) != copain:
                    user = await self.bot.fetch_user(copain)
                    fromu = getUserById(self.userid)
                    msg = f"||Message de {fromu}||\n" + str(random.choice(self.phrase)) + "\n\n En gros, go vocal."
                    await user.send(msg)
            await interaction.followup.send("La bande a été prévenu !", ephemeral=True)
            button.disabled = True
            return
    except Exception as e:
        LogErrorInWebhook()

class TrapcoinsHandler:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    async def create_user(self, userid: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO (trapcoins userid, trapcoins, epargne) VALUES (?,?,?)", (userid, 0, 0,))
        return True
    async def get(self, userid: int):
        """Return `trapcoins`, `epargne`."""
        async with self.pool.acquire() as conn:
            data = await conn.fetchone("SELECT trapcoins, epargne FROM trapcoins WHERE userid = ?", (userid,))
        if data:
            return data[0], data[1]
        return "Unknown user", "Unknown user"

    async def add(self, userid: int, amount: int, wallet: Literal["epargne", "trapcoins"]):
        """Add trapcoins to given wallet"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if wallet == "epargne":
                    await conn.execute("UPDATE trapcoins SET epargne = epargne + ? WHERE userid = ?", (amount, userid,))
                elif wallet == "trapcoins":
                    await conn.execute("UPDATE trapcoins SET trapcoins = trapcoins + ? WHERE userid = ?", (amount, userid,))
        return True
    
    async def remove(self, userid: int, amount: int, wallet: Literal["epargne", "trapcoins"]):
        """Remove trapcoins to given wallet"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if wallet == "epargne":
                    await conn.execute("UPDATE trapcoins SET epargne = epargne - ? WHERE userid = ?", (amount, userid,))
                elif wallet == "trapcoins":
                    await conn.execute("UPDATE trapcoins SET trapcoins = trapcoins - ? WHERE userid = ?", (amount, userid,))
        return True

    async def transfer(self, userid: int, amount: int, operation: Literal["ep_to_tr", "tr_to_ep"]):
        """Move trapcoins from epargne or trapcoins to the other one."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if operation == "ep_to_tr":
                    await conn.execute("UPDATE trapcoins SET epargne = epargne - ? WHERE userid = ?", (amount, userid,))
                    await conn.execute("UPDATE trapcoins SET trapcoins = trapcoins + ? WHERE userid = ?", (amount, userid,))
                elif operation == "tr_to_ep":
                    await conn.execute("UPDATE trapcoins SET trapcoins = trapcoins - ? WHERE userid = ?", (amount, userid,))
                    await conn.execute("UPDATE trapcoins SET epargne = epargne + ? WHERE userid = ?", (amount, userid,))
        return True

    async def baltop(self):
        """Return `list`: `[[user1, trap, ep], [user2, trap, ep]]`"""
        async with self.pool.acquire() as conn:
            data = await conn.fetchall("SELECT userid, trapcoins, epargne FROM ( SELECT userid, trapcoins, 0 AS epargne FROM trapcoins UNION SELECT userid, 0 AS trapcoins, epargne FROM trapcoins ) AS combined ORDER BY trapcoins + epargne DESC LIMIT 25;")
        return data

