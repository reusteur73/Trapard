from .utils.functions import LogErrorInWebhook, afficher_nombre_fr, format_duration, load_json_data, create_embed, seconds_until, write_item, convert_txt_to_colored,getVar
from .utils.data import interests_indexs, interests_infos
from .utils.path import ANNONCE_AVATAR_PATH
from asyncio import sleep
from bs4 import BeautifulSoup
import discord, time, datetime, json, re
from io import BytesIO
from PIL import Image
from aiohttp import ClientSession
from discord.ext import tasks, commands
from .utils.classes import Trapardeur
from bot import Trapard
from zoneinfo import ZoneInfo
from asqlite import Pool

APIKEY = getVar("CRYPTO_API")

async def xp_calculation(user_id: str, pool: Pool):
    """
        Calculate the xp of the user
        Xp needed per level = 500
        10 minutes of voice = 2 xp
        1 message sent = 1 xp
        1 command used = 1 xp
    """
    try:
        handler = Trapardeur(pool=pool, userId=user_id)
        data = await handler.get()
        xp = (int(data[0][2]) * 2 / 600) + int(data[0][3]) + int(data[0][4])
        return xp
    except Exception as e:
        LogErrorInWebhook(error=f"[XP CALCULATION] {e} DATA={data}")

def calculate_level(xp_total):
    xp_needed_per_level = 500
    return xp_total // xp_needed_per_level

class RencontreNc:
    def __init__(self, pool: Pool, session: ClientSession) -> None:
        self.pool = pool
        self.session = session
    def is_image_downloaded(self, userid: str) -> bool:
        try:
            with open(f"{ANNONCE_AVATAR_PATH}/{userid}.webp", "rb") as f:
                return True
        except FileNotFoundError:
            return False
        
    async def download_image(self, userid: str) -> bool:
        try:
            async with self.session.get("https://thispersondoesnotexist.com/") as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
                    image = Image.open(BytesIO(image_bytes))
                    if image.format not in ['JPEG', 'PNG']:
                        print("Downloaded content is not a valid image format.")
                        return False
                    
                    image.save(f"{ANNONCE_AVATAR_PATH}/{userid}.webp", format="WEBP")
                    return True
                else:
                    return False
            re
        except Exception as e:
            LogErrorInWebhook(error=f"[IMAGE DOWNLOAD] {e} USER={userid}")
    
    async def save(self, id:int, text:str, title: str, category: str):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO rencontresNC (annonce_id, titre, texte, category) VALUES (?,?,?,?)", (id,title, text, category,))

    async def is_in(self, id:int):
        async with self.pool.acquire() as conn:
            data = await conn.fetchone("SELECT annonce_id FROM rencontresNC WHERE annonce_id = ?", (id,))
        return bool(data)

class Informatique:
    def __init__(self, pool: Pool, session: ClientSession) -> None:
        self.pool = pool
        self.session = session

    def is_image_downloaded(self, userid: str) -> bool:
        try:
            with open(f"{ANNONCE_AVATAR_PATH}/{userid}.webp", "rb") as f:
                return True
        except FileNotFoundError:
            return False
        
    async def download_image(self, userid: str) -> bool:
        try:
            async with self.session.get("https://thispersondoesnotexist.com/") as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
                    image = Image.open(BytesIO(image_bytes))
                    if image.format not in ['JPEG', 'PNG']:
                        print("Downloaded content is not a valid image format.")
                        return False
                    image.save(f"{ANNONCE_AVATAR_PATH}/{userid}.webp", format="WEBP")
                    return True
            return False
        except Exception as e:
            LogErrorInWebhook(error=f"[IMAGE DOWNLOAD] {e} USER={userid}")

    async def save(self, id:int, user_id: int,text:str, title: str, medias: list, created_at: str):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                medias_json = json.dumps(medias)
                await conn.execute("INSERT INTO Annonces_nc_Informatique (annonce_id, user_id, titre, texte, medias, created_at) VALUES (?,?,?,?,?,?)", (id,user_id,title, text, medias_json, created_at,))

    async def is_in(self, id:int):
        async with self.pool.acquire() as conn:
            data = await conn.fetchone("SELECT annonce_id FROM Annonces_nc_Informatique WHERE annonce_id = ?", (id,))
        return bool(data)
    
class Tasks(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
        self.status_iterations = 0
        self.interests_indexs = interests_indexs
        self.interests_infos = interests_infos
        self.trapeur_xp = {}

        self.update_status.start()
        self.interests.start()
        self.check_streak.start()
        # self.cryptoRapport.start()
        # self.cpas_bien.start()
        self.check_users_xp.start()
        self.rencontres_nc.start()
        self.informatique.start()
        self.lol_patch_notes.start()

    @tasks.loop(minutes=1)
    async def update_status(self):
        try:
            async with self.bot.pool.acquire() as conn:
                data = await conn.fetchone("SELECT time, number FROM songs_stats WHERE id = 1")
            duration = data[0]
            numPlayed = data[1]
            duration = format_duration(duration)
            if self.status_iterations == 0:
                wanted = f"{afficher_nombre_fr(numPlayed)} musiques jouées !"
            else:
                wanted = f"{duration} playtime !"
            activity = discord.CustomActivity(
                name = "Custom Status", # leave this like this
                state = wanted # edit this
            )
            try: await self.bot.change_presence(activity=activity)
            except: pass
            self.status_iterations += 1
            if self.status_iterations == 2:
                self.status_iterations = 0
        except:
            LogErrorInWebhook()

    @tasks.loop(hours=25)
    async def interests(self):
        def calculer_pourcentage(nombre, pourcentage):
            resultat = nombre * (pourcentage / 100)
            return resultat

        async def check_interests():
            data_tiers = load_json_data(item="interets")
            trapcoins_emoji = "<:trapcoins:1108725845339672597>"
            field = ""
            added = 0
            for key, val in data_tiers.items():
                _, user_epergne = await self.bot.trapcoin_handler.get(userid=int(key))
                if isinstance(user_epergne, int):
                    interest_mult1 = self.interests_indexs[int(val["tier"])]
                    interest_mult = self.interests_infos[interest_mult1]["interet"]
                    wins_tot = calculer_pourcentage(float(user_epergne), float(interest_mult)) + float(user_epergne)
                    winned = wins_tot - int(user_epergne)
                    if int(calculer_pourcentage(float(user_epergne), float(interest_mult))) != 0:
                        print(f"<@{key}> : {int(calculer_pourcentage(float(user_epergne), float(interest_mult)))} Trapcoins ajoutés\n")
                        await self.bot.trapcoin_handler.add(userid=int(key), amount=int(winned), wallet='trapcoins')
                        mention = f"- **<@{key}>** :"
                        field += f"{mention}`{afficher_nombre_fr(int(calculer_pourcentage(float(user_epergne), float(interest_mult))))}` {str(trapcoins_emoji)}\n"
                        added += 1
            field += ""
            
            if added == 0:
                return
            elif added == 1:
                embed = create_embed(title="intérêts", description=f"Les intérêts ont été ajoutés à l'utilisateur suivant :\n\n{field}")
            else:
                embed = create_embed(title="intérêts", description=f"Les intérêts ont été ajoutés aux utilisateurs suivants :\n\n{field}")


            # tading trap : 
            trading_chann = self.bot.get_channel(1066378588896624650)
            await trading_chann.send(embed=embed)
            
            # Malo général:
            malo_gen = self.bot.get_channel(925940799693283390)
            await malo_gen.send(embed=embed)

            #dev = bot.get_channel(1065324352851148803)
            # await dev.send(embed=embed)

        to_wait = seconds_until(7, 0)
        await sleep(to_wait)
        
        await check_interests()

    @tasks.loop(hours=25)
    async def check_streak(self):
        try:
            async def get_streak_file():
                data = load_json_data(item="streak")
                losers = []
                time2 = int(time.time())
                new = {}
                for key, vals in data.items():
                    time1 = vals["timestamp"]
                    streak = vals['streak']
                    userid = key
                    spend = (time2 - int(time1)) / 3600
                    if spend <= 24:
                        new[str(userid)] = {'streak': streak, 'timestamp': time1}
                    else:
                        new[str(userid)] = {'streak': 0, 'timestamp': time1}
                        losers.append(userid)

                write_item(item="streak", values=new)
                
                if len(losers) > 0:
                    fields = []
                    for loser in losers:
                        fields.append({"name": f"", "value": f"<@{loser}>, `tu as perdu ta streak de daily-claim.`", "inline": False})
                    embed = create_embed(title="Daily-claim streak losers", description="", fields=fields)
                    chann = self.bot.get_channel(1066378588896624650)
                    return await chann.send(embed=embed)
                else: return None

            to_wait = seconds_until(5, 55)
            await sleep(to_wait)
            losers = await get_streak_file()
            self.bot.day_vocal_time = {} # reset daily vocal time
        except Exception as e:
            LogErrorInWebhook()

    @tasks.loop(hours=25)
    async def cryptoRapport(self):
        try:
            async def getPrice():
                try:
                    maintenant = datetime.datetime.now()
                    format_date = maintenant.strftime("%d/%m/%y à %Hh%M")
                    date= f'Rapport du {format_date}'
                    async with self.bot.session.get(f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?start=1&limit=5000&convert=EUR&CMC_PRO_API_KEY={APIKEY}") as response:
                        data = await response.json()
                    WANTED = ["Bitcoin", "Monero", "Ethereum", "BNB", "XRP", "Cardano", "Dogecoin", "Litecoin", "Stellar"]
                    chann = self.bot.get_channel(1174058782821728367)
                    fields = []
                    for i in data["data"]:
                        if i["name"] in WANTED:
                            change_24h_percent = round(i["quote"]["EUR"]["percent_change_24h"], 2)
                            change_24h_percent_color = "blue" if change_24h_percent >=0 else "red"

                            change_1h_percent = round(i["quote"]["EUR"]["percent_change_1h"], 2)
                            change_1h_percent_color = "blue" if change_1h_percent >=0 else "red"

                            change_7d_percent = round(i["quote"]["EUR"]["percent_change_7d"], 2)
                            change_7d_percent_color = "blue" if change_7d_percent >=0 else "red"
                            
                            change_30d_percent = round(i["quote"]["EUR"]["percent_change_30d"], 2)
                            change_30d_percent_color = "blue" if change_30d_percent >=0 else "red"
                            
                            current_price = round(i["quote"]["EUR"]["price"], 2)
                            current_price_color = "blue" if current_price >=0 else "red"

                            volume_24h = round(i["quote"]["EUR"]["volume_24h"], 2)

                            volume_change_percent = round(i["quote"]["EUR"]["volume_change_24h"], 2)
                            volume_change_percent_color = "blue" if volume_change_percent >=0 else "red"

                            name = i["name"]
                            fields.append({"name": name, "value": f" - Prix:\n{convert_txt_to_colored(text=str(current_price), color=current_price_color)}\n - 1h % change:\n{convert_txt_to_colored(text=str(change_1h_percent), color=change_1h_percent_color)}\n - 24h % change:\n{convert_txt_to_colored(text=str(change_24h_percent), color=change_24h_percent_color)}\n - 7j % change:\n{convert_txt_to_colored(text=str(change_7d_percent), color=change_7d_percent_color)}\n - 30j % change:\n{convert_txt_to_colored(text=str(change_30d_percent), color=change_30d_percent_color)}\n - Volume 24h:\n{convert_txt_to_colored(text=str(volume_24h), color='blue')}\n - Volume % change 24h:\n{convert_txt_to_colored(text=str(volume_change_percent), color=volume_change_percent_color)}\n----------------", "inline": True})
                    embed = create_embed(title="Crypto", description="", fields=fields)
                    await chann.create_thread(name=date, embed=embed)
                except:
                    LogErrorInWebhook()
            to_wait = seconds_until(7, 0)
            await sleep(to_wait)
            await getPrice()

            to_wait = seconds_until(19, 0)
            await sleep(to_wait)
            await getPrice()

            # do task
        except:
            LogErrorInWebhook()

    @tasks.loop(hours=3)
    async def cpas_bien(self):
        try:
            async def scrape_cpasbien():
                async def insert_in_db(title: str):
                    async with self.bot.pool.acquire() as conn:
                        async with conn.transaction():
                            await conn.execute(f'INSERT INTO cpasbien (title_name) VALUES ("{title}")')
                    return
                
                async def get_titles():
                    async with self.bot.pool.acquire() as conn:
                        return await conn.fetchall("SELECT title_name from cpasbien")
                    
                maintenant = datetime.datetime.now()
                format_date = maintenant.strftime("%d/%m/%y à %Hh%M")
                date = f'Nouveautées du {format_date}'
                url_base = 'https://www.cpasbien.biz'
                try:
                        async with self.bot.session.get(f'{url_base}/derniers') as res:
                            source_code = await res.text()
                except Exception as e: return LogErrorInWebhook(error=f"Erreur reaching cpasbien code 2 : {e}")
                
                soup = BeautifulSoup(source_code, 'html.parser')
                table = soup.find('table', class_='table-corps')

                data = {}
                returned_data= {}
                saved_titles = await get_titles()
                clean_list = []
                for n in saved_titles:
                    clean_list.append(n[0])
                if table:
                    for index, row in enumerate(table.find_all('tr')):
                        row_text = ' '.join(cell.get_text(strip=True) for cell in row.find_all(['td', 'th']))
                        link = row.find('a')
                        href = link.get('href') if link else None
                        data[index] = {'text': row_text, 'lien': f'{url_base}{href}'}
                    found = 0
                    for i, (key, val) in enumerate(data.items()):
                        if val["text"] in clean_list:
                            continue
                        returned_data[i] = {"text": val["text"], "lien": val["lien"]}
                        await insert_in_db(val["text"])
                        found += 1
                    blocks = []
                    if found == 0:
                        return
                    txt = ""
                    for i, (key, val) in enumerate(returned_data.items()):
                        txt += f"- {i+1}. [{val['text']}]({val['lien']})\n"
                        if i % 10 == 0:
                            blocks.append(txt)
                            txt = ""
                    txt += "Fin des nouveautées :)"
                    blocks.append(txt)
                    chann = self.bot.get_channel(1176327641943515186)
                    if chann:
                        thread = await chann.create_thread(name=date, content=blocks[0], suppress_embeds=True)
                        for z, block in enumerate(blocks):
                            if z != 0:
                                await thread[0].send(content=block, suppress_embeds=True)
                        return
                    else:
                        await sleep(30)
                        chann = self.bot.get_channel(1176327641943515186)
                        thread = await chann.create_thread(name=date, content=blocks[0], suppress_embeds=True)
                        for z, block in enumerate(blocks):
                            if z != 0:
                                await thread[0].send(content=block, suppress_embeds=True)
                        return
                else: return LogErrorInWebhook(error=f"Aucun données dans cpasbien trouvé ??")
            await scrape_cpasbien()
        except: LogErrorInWebhook()

    @tasks.loop(minutes=5)
    async def check_users_xp(self):
            data = await Trapardeur(pool=self.bot.pool).get_all()
            for i in data:
                try:
                    xp = await xp_calculation(user_id=i[1], pool=self.bot.pool)
                    if i[1] not in self.trapeur_xp:
                        self.trapeur_xp[i[1]] = xp
                    else:
                        previous_xp = self.trapeur_xp[i[1]]
                        current_level = calculate_level(xp)
                        previous_level = calculate_level(previous_xp)
                        if current_level > previous_level:
                            embed = create_embed(title="Trapardeur", description=f"- <@{i[1]}> est passé niveau de trapardeur {int(current_level)}, bravo !\n\n- </trapardeur:1129953267187716117> pour voir tes stats !")
                            await self.bot.get_channel(1166803796769394729).send(embed=embed)

                    self.trapeur_xp[i[1]] = xp  # Mettre à jour l'XP de l'utilisateur dans le dictionnaire
                
                except Exception as e:
                    print(f"Erreur lors de la vérification des XP des utilisateurs : {e} USER={i[1]}, XP={xp}")

    @tasks.loop(minutes=30)
    async def rencontres_nc(self):
        POSTS_URLS = ["homme-femme-5", "femme-homme-5", "transexuels-5", "homme-homme-5","plan-q-5", "travesti-5"]
        POST_ENDP = "https://api.annonces.nc/posts"
        handler = RencontreNc(pool=self.bot.pool, session=self.bot.session)
        nums_found = []
        channel = await self.bot.fetch_channel(1211607454400651264)
        sent = 0
        pattern = re.compile(r'\b(\d{2})[ ,.]?(\d{2})[ ,.]?(\d{2})\b')
        if channel:
            for post_url in POSTS_URLS:
                async with self.bot.session.get(f'https://api.annonces.nc/posts?by_category={post_url}&per=40&sort=-published_at&by_locality=nouvelle-caledonie&page=1') as resp:
                    data = await resp.json()
                if data:
                    for post in data:
                        async with self.bot.session.get(f'{POST_ENDP}/{post["slug"]}') as post_resp:
                            post_data = await post_resp.json()
                        if post_data:
                            texte = post_data["description"]
                            titre = post_data["title"]
                            idx = post_data["id"]
                            user_id = post_data["user_id"]
                            cat = post_data['category']['name']
                            is_in = await handler.is_in(idx)

                            attempts = 0
                            while not handler.is_image_downloaded(userid=str(user_id)) and attempts < 3:
                                status = await handler.download_image(user_id)
                                if status:
                                    break
                                else:
                                    print(f"Image not downloaded for user {user_id}, attempt {attempts + 1}")
                                    await sleep(1)
                                attempts += 1

                            
                            if not is_in:
                                if len(texte) < 4096:
                                    embed = create_embed(title="", description=f"# {titre}\n\n{texte}\n\n## Catégorie: {cat}")
                                    local_icon_path = f"{ANNONCE_AVATAR_PATH}/{user_id}.webp"
                                    if handler.is_image_downloaded(userid=str(user_id)):
                                        embed.set_author(name=f"Annonce n°{post_data['id']} par l'utilisateur n°{user_id}", url=post_data["link_url"], icon_url=f"attachment://{user_id}.webp")
                                        with open(local_icon_path, "rb") as f:
                                            file = discord.File(f, filename=f"{user_id}.webp")
                                    else:
                                        file = None
                                        embed.set_author(name=f"Annonce n°{post_data['id']} par l'utilisateur n°{user_id}", url=post_data["link_url"], icon_url="https://annonces.nc/assets/images/sites/annonces.png")
                                    medias = []
                                    if post_data.get("medias"):
                                        for media in post_data["medias"]:
                                            if 'large' in media['versions']:
                                                embed.set_image(url=media['versions']['large']['url'])
                                                medias.append(media['versions']['large']['url'])
                                                break
                                    if file:
                                        await channel.send(embed=embed, file=file)
                                    else:
                                        await channel.send(embed=embed)
                                await handler.save(idx, texte, titre, cat)
                                nums_found += pattern.findall(texte)
                                sent += 1

    @tasks.loop(minutes=20)
    async def informatique(self):
        handler = Informatique(pool=self.bot.pool, session=self.bot.session)
        channel = await self.bot.fetch_channel(1336339577757106276)
        async with self.bot.session.get("https://api.annonces.nc/posts?by_category=informatique-1&per=40&sort=-published_at&by_locality=nouvelle-caledonie&page=1") as resp:
            data = await resp.json()
        if data:
            for post in data:
                async with self.bot.session.get(f'https://api.annonces.nc/posts/{post["slug"]}') as post_resp:
                    post_data = await post_resp.json()
                if post_data:
                    texte = post_data["description"]
                    titre = post_data["title"]
                    idx = post_data["id"]
                    user_id = post_data["user_id"]
                    prix = post_data["price"]
                    if prix: prix = f"{afficher_nombre_fr(int(prix))} XPF"
                    else : prix = "non renseigné"
                    is_in = await handler.is_in(idx)

                    attempts = 0
                    while not handler.is_image_downloaded(userid=str(user_id)) and attempts < 5:
                        status = await handler.download_image(user_id)
                        if status:
                            break
                        attempts += 1

                    raw_field = f"# {titre}\n\n{texte}\n\n## Prix: {prix}"
                    if not is_in:
                        if len(raw_field) < 4096:
                            embed = create_embed(title="", description=raw_field)
                            local_icon_path = f"{ANNONCE_AVATAR_PATH}/{user_id}.webp"
                            if handler.is_image_downloaded(userid=str(user_id)):
                                embed.set_author(name=f"Annonce n°{post_data['id']} par l'utilisateur n°{user_id}", url=post_data["link_url"], icon_url=f"attachment://{user_id}.webp")
                                with open(local_icon_path, "rb") as f:
                                    file = discord.File(f, filename=f"{user_id}.webp")
                            else:
                                file = None
                                embed.set_author(name=f"Annonce n°{post_data['id']} par l'utilisateur n°{user_id}", url=post_data["link_url"], icon_url="https://annonces.nc/assets/images/sites/annonces.png")
                            medias = []
                            if post_data.get("medias"):
                                for media in post_data["medias"]:
                                    if 'large' in media['versions']:
                                        embed.set_image(url=media['versions']['large']['url'])
                                        medias.append(media['versions']['large']['url'])
                                        break
                            if file:
                                await channel.send(embed=embed, file=file)
                            else:
                                await channel.send(embed=embed)
                        await handler.save(idx, user_id, texte, titre, medias, post_data["created_at"])

    @tasks.loop(time=datetime.time(10, 0, 0, tzinfo=ZoneInfo("Europe/Paris")))
    async def lol_patch_notes(self):
        try:
            url = 'https://www.leagueoflegends.com/fr-fr/news/tags/patch-notes/'
            headers ={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            async with self.bot.session.get(url, headers=headers) as response:
                if response.status == 200:
                    text = await response.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    titles = soup.find_all('div', {'data-testid': 'card-title'})
                    last_title = titles[0].text.strip() if titles else None
                    if titles:
                        async with self.bot.pool.acquire() as conn:
                            data = await conn.fetchone("SELECT value FROM PATCH_NOTES WHERE game = 'lol'")
                        if data:
                            last_title_db = data[0]
                            if last_title_db.strip() != last_title.strip():
                                await conn.execute("UPDATE PATCH_NOTES SET value = ? WHERE game = 'lol'", (last_title,))
                                a_tag = titles[0].find_previous('a')
                                if a_tag:
                                    href = a_tag.get('href')
                                    if href:
                                        embed = create_embed(title="Patch notes LoL", description=f"<@&1044302003486077028>, nouveau patch notes LoL\n\n**{last_title}**\n\n[Voir le patch notes en entier](https://www.leagueoflegends.com{href})")
                                        chann = self.bot.get_channel(1078804935996608584)
                                        await chann.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook(error=f"[LOL PATCH NOTES] {e}")

async def setup(bot: Trapard):
    await bot.add_cog(Tasks(bot))