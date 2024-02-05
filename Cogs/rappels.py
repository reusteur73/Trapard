# from typing import TYPE_CHECKING, Optional
from discord.ext import commands, tasks
from discord import app_commands
import datetime, asqlite, re, asyncio, discord

# if TYPE_CHECKING:
from bot import Trapard
from .utils.functions import create_embed, LogErrorInWebhook

def is_past(timestamp: int):
    """Retourne True si le timestamp est dans le passé, False sinon."""
    return timestamp < datetime.datetime.now().timestamp()

def convert_to_timestamp(time_string: str):
    """
        Retourne un timestamp à partir d'une date ou d'une durée.
    
        Formats acceptés:
    

        Format date: `JJ/MM/AA` ou `JJ/MM`. 
    
        Format durée: `5s` ou `5m` ou `5h` ou `5j` ou `5w` ou `5M` ou `5a` ou `5h 3m` ou `5j 3h` ou `5.5j`

        (liste non exhaustive)
    """
    ERROR_MSG = """
        # Format de temps invalide...\n
        ## Voici une liste de format de temps autorisé et pris en charge:\n\n
        ### - Par date:\n
        - - `24/12` ___Le 24/12/2023 à 00h00m___\n
        - - `24/12/23` ___Le 24/12/2023 à 00h00m___\n
        - - `24/12/2023` ___Le 24/12/2023 à 00h00m___\n
        - - `24/12/2023à18h36m` ___Le 24/12/2023 à 18h36m___\n
        - - `24/12/2023à18h36` ___Le 24/12/2023 à 18h36m___\n
        - - `24/12/2023à18h` ___Le 24/12/2023 à 18h36m___\n
        - - `24/12/2023à18` ___Le 24/12/2023 à 18h36m___\n
        - - ...\n\n
        ### - Par durée:\n
        - - `5s` ou `5m` ou `5h` ou `5j` ou `5w` ou `5M` ou `5a` ou `5h 3m` ou `5j 3h` ou `5.5j` ...
    """
    data = re.match(r'^(\d{2})\/(\d{2})(?:\/?(\d{4}|\d{2})?(?:à)?(\d{1}|\d{2})?(?:h)?(\d{2}|\d{4})?m?)?$', time_string)
    if data:
        day, month, year, hour, minute = data.groups()

        if day is None or month is None:
            return ERROR_MSG
        day, month = map(int, (day, month))

        if year is None:
            year = datetime.datetime.now().year
        else:
            if len(year) == 2:
                year = 2000 + int(year)
            elif len(year) == 4:
                year = int(year)

        if hour:
            hour = int(hour)
        else: 
            hour = 0
        
        if minute:
            minute = int(minute)
        else:
            minute = 0

        target_date = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute)
        return int(target_date.timestamp())
    date_format = re.match(r'^(\d{2})/(\d{2})(?:/(\d{2}))?$', time_string)
    if date_format: # Vérification du format date (JJ/MM/AA)
        day, month, year = date_format.groups()
        day, month = map(int, (day, month))
        current_year = datetime.datetime.now().year
        if year is None:
            year = current_year
        else:
            if len(year) == 2:
                year = 2000 + int(year)
            elif len(year) == 4:
                year = int(year)
        target_date = datetime.datetime(year=year, month=month, day=day)
        return int(target_date.timestamp())

    match = re.match(r'^(\d+(?:\.\d+)?)\s*([smhdjwayMS]+)(?:\s*(\d+(?:\.\d+)?)\s*([smhdjwayMS]+))?$', time_string)
    if match: # Vérification des formats de durées (5s, 5m, 5h, 5j, 5w, 5M, 5a, 5h 3m, 5j 3h, 5.5j)
        value_1 = float(match.group(1))
        unit_1 = match.group(2)

        value_2 = float(match.group(3)) if match.group(3) else 0
        unit_2 = match.group(4) if match.group(4) else ""

        time_units = {
            's': 1,
            'm': 60,
            'h': 60 * 60,
            'd': 60 * 60 * 24,
            'j': 60 * 60 * 24,
            'w': 60 * 60 * 24 * 7,
            'M': 60 * 60 * 24 * 30,
            'a': 60 * 60 * 24 * 365,
        }

        to = (value_1 + value_2 / 24) * time_units[unit_1]
        reminder_time = datetime.datetime.now() + datetime.timedelta(seconds=to)
        return int(reminder_time.timestamp())
    else: return ERROR_MSG

def get_snooze_time(t1, t2):
    """Return timestamp in 10% of rappel time"""
    timestamp1 = datetime.datetime.fromtimestamp(t1)
    timestamp2 = datetime.datetime.fromtimestamp(t2)
    difference = timestamp2 - timestamp1
    difference_en_minutes = difference.total_seconds() / 60
    dix_percent = round((difference_en_minutes * 10) / 100)
    if dix_percent < 2:
        dix_percent = 5
    elif dix_percent > 20000:
        dix_percent = 20000
    return (datetime.datetime.now() + datetime.timedelta(minutes=dix_percent)).timestamp()

class RappelsHandler:
    def __init__(self, pool: asqlite.Pool):
        self.pool = pool

    async def add(self, rappel_timestamp: int, rappel_texte: str, rappel_auteur: int, rappel_notifié: bool, rappel_channel: int):
        """Ajoute un rappel à la base de données."""
        now = datetime.datetime.now().timestamp()
        rappel_data = (rappel_timestamp, rappel_texte, rappel_auteur, rappel_notifié, rappel_channel, now)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO rappels (timestamp, texte, auteur, notified, channel, created_at) VALUES (?, ?, ?, ?, ?, ?)", rappel_data)
        return

    async def delete(self, rappel_id: int):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM rappels WHERE id = ?", (rappel_id,))
        return

    async def get_all(self, auteur: int=None):
        """Renvoie les rappels de l'auteur: `data[0][1] = timestamp`, `data[0][2] = texte`, `data[0][3] = auteur`, `data[0][4] = notified`, `data[0][5] = channel`"""
        async with self.pool.acquire() as conn:
            if auteur:
                rows = await conn.fetchall("SELECT * FROM rappels WHERE auteur = ?", (auteur,))
            else:
                rows = await conn.fetchall("SELECT * FROM rappels")
        return rows

class SnoozeView(discord.ui.View):
    def __init__(self, rappel_owner_id: int, snooze_time, rappel_texte: str, channel: int, pool: asqlite.Pool):
        super().__init__(timeout=1500)
        self.owner = rappel_owner_id
        self.time = int(snooze_time)
        self.texte = rappel_texte
        self.channel = channel
        self.pool = pool

    @discord.ui.button(label='Snooze', style=discord.ButtonStyle.green, custom_id="snooze", emoji="⏰")
    async def snooze(self, interaction: discord.Interaction, button: discord.ui.Button):
        try: await interaction.response.defer()
        except: pass
        if int(self.owner) == interaction.user.id:
            now = int(datetime.datetime.now().timestamp())
            rappel_data = (self.time, f"snooze du rappel: `{self.texte}`", self.owner, 0, self.channel, now)
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("INSERT INTO rappels (timestamp, texte, auteur, notified, channel, created_at) VALUES (?, ?, ?, ?, ?, ?)", rappel_data)
            embed = create_embed(title="Rappel", description=f"Ok {interaction.user.mention}, tu as activé le snooze du rappel `{self.texte}` il se déclanchera le <t:{self.time}:F> <t:{self.time}:R>!")
            return await interaction.followup.send(embed=embed)
        return

class Rappels(commands.Cog):
    def __init__(self, bot: Trapard):
        self.bot: Trapard = bot
        self.handler = RappelsHandler(pool=self.bot.pool)
        self.first_run = True
        self.rappel_errors = 0
        self.rappels_check.start()

    @commands.hybrid_group()
    @app_commands.describe(utilisateur="Le membre voulu.")
    async def rappel(self, ctx: commands.Context):
        pass

    @rappel.command()
    @app_commands.describe(quand="Quand le rappel doit être envoyé. Exemple: 5s ou 5m ou 5h ou 5j ou 5w ou 5M ou 5a ou 5h 3m ou 5.2j 3.5h ou 5.5j")
    @app_commands.describe(texte="Le texte du rappel.")
    async def créer(self, ctx: commands.Context, quand: str, *, texte: str=None):
        """Crée un rappel."""
        ERROR_MSG = """
            # Format de temps invalide...\n
            ## Voici une liste de format de temps autorisé et pris en charge:\n\n
            ### - Par date:\n
            - - `24/12` ___Le 24/12/2023 à 00h00m___\n
            - - `24/12/23` ___Le 24/12/2023 à 00h00m___\n
            - - `24/12/2023` ___Le 24/12/2023 à 00h00m___\n
            - - `24/12/2023à18h36m` ___Le 24/12/2023 à 18h36m___\n
            - - `24/12/2023à18h36` ___Le 24/12/2023 à 18h36m___\n
            - - `24/12/2023à18h` ___Le 24/12/2023 à 18h36m___\n
            - - `24/12/2023à18` ___Le 24/12/2023 à 18h36m___\n
            - - ...\n\n
            ### - Par durée:\n
            - - `5s` ou `5m` ou `5h` ou `5j` ou `5w` ou `5M` ou `5a` ou `5h 3m` ou `5j 3h` ou `5.5j` ...
        """
        timestamp = convert_to_timestamp(quand)
        if timestamp == ERROR_MSG:
            embed = create_embed(title="Rappel", description=timestamp) 
            return await ctx.send(embed=embed)
        if is_past(timestamp):
            embed = create_embed(title="Rappel", description="Vous ne pouvez pas créer un rappel dans le passé, cela me parait logique mais pas pour tout le monde apparemment...")
            return await ctx.send(embed=embed)
        if not texte:
            texte = 'Rappel'
        await self.handler.add(timestamp, texte, ctx.author.id, False, ctx.channel.id)
        formatted_time = f'<t:{timestamp}:F>'
        formatted_time2 = f'<t:{timestamp}:R>'
        embed = create_embed(title="Rappel", description=f"Ok {ctx.author.mention}, le rappel `{texte}` se déclanchera le {formatted_time} {formatted_time2}!")
        return await ctx.send(embed=embed)

    @rappel.command()
    async def liste(self, ctx: commands.Context):
        """Affiche la liste de tes rappels."""
        try:
            print(type(self.bot.db_conn))
            print(1)
            rappels = await self.handler.get_all(ctx.author.id)
            if len(rappels) == 0:
                return await ctx.send("Vous n'avez aucun rappel.")
            print(2)
            rappels = sorted(rappels, key=lambda rappel: rappel[1])
            print(3)
            rappels = [f"- {rappel[0]}: <t:{rappel[1]}:F> {rappel[2]}" for rappel in rappels]
            print(4)
            return await ctx.send("\n".join(rappels))
        except Exception as e:
            print(e)
    
    @rappel.command()
    @app_commands.describe(rappel_id="L'ID du rappel.")
    async def supprimer(self, ctx: commands.Context, rappel_id: int):
        """Supprime un rappel."""
        rappels = await self.handler.get_all(ctx.author.id)
        rappels = [rappel[0] for rappel in rappels]
        if rappel_id not in rappels:
            return await ctx.send("Vous n'avez pas de rappel avec cet ID.")
        await self.handler.delete(rappel_id)
        return await ctx.send("Rappel supprimé avec succès.")

    @tasks.loop(seconds=1)
    async def rappels_check(self):
        try:
            if self.first_run:
                print("sleeping")
                await asyncio.sleep(120)
                self.first_run = False
                print("end sleep")
            handler = RappelsHandler(pool=self.bot.pool)
            rappels = await handler.get_all()
            rappels = [rappel for rappel in rappels if int(rappel[1]) <= int(datetime.datetime.now().timestamp())]
            for rappel in rappels:
                if rappel[6]:
                    snooze = int(get_snooze_time(rappel[1],rappel[6]))
                else:
                    snooze = None
                channel = self.bot.get_channel(rappel[5])
                if channel:
                    user = self.bot.get_user(int(rappel[3]))
                    if user:
                        view = SnoozeView(rappel_owner_id=rappel[3], snooze_time=snooze, rappel_texte=rappel[2], channel=rappel[5], pool=self.bot.pool)
                        embed = create_embed(title="Rappel déclanché", description=f"- Rappel: **{rappel[2]}**\n- Créé <t:{int(rappel[6])}:R>.")
                        await channel.send(f"{user.mention}", view=view, embed=embed)
                        await handler.delete(rappel[0])
        except Exception as e:
            if self.rappel_errors < 20:
                LogErrorInWebhook()
                self.rappel_errors += 1

async def setup(bot: Trapard):
    await bot.add_cog(Rappels(bot))