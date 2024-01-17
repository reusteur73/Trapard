from .utils.functions import LogErrorInWebhook, afficher_nombre_fr, format_duration, load_json_data, trapcoins_handler, create_embed, seconds_until, write_item, convert_txt_to_colored
from .utils.data import interests_indexs, interests_infos
from asyncio import sleep
from bs4 import BeautifulSoup
import discord, time, datetime, os
from discord.ext import tasks, commands
from .utils.classes import Trapardeur
from bot import Trapard

APIKEY = os.environ.get("CRYPTO_API")

async def xp_calculation(user_id: str, conn, cursor):
    """
        Calculate the xp of the user
        Xp needed per level = 500
        10 minutes of voice = 2 xp
        1 message sent = 1 xp
        1 command used = 1 xp
    """
    try:
        handler = Trapardeur(conn=conn, cursor=cursor, userId=user_id)
        data = await handler.get()
        xp = (data[0][2] * 2 / 600) + data[0][3] + data[0][4]
        return xp
    except Exception as e:
        LogErrorInWebhook(error=f"[XP CALCULATION] {e} DATA={data}")

def calculate_level(xp_total):
    xp_needed_per_level = 500
    return xp_total // xp_needed_per_level

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
        self.cryptoRapport.start()
        self.cpas_bien.start()
        self.check_users_xp.start()

    @tasks.loop(minutes=1)
    async def update_status(self):
        try:
            data = load_json_data(item="song-stats")
            duration = data['time']
            numPlayed = data['number-played']
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
                user_epergne = load_json_data(item="trapcoins", userid=str(key), opt_val="epargne")
                if isinstance(user_epergne, int):
                    interest_mult1 = self.interests_indexs[int(val["tier"])]
                    interest_mult = self.interests_infos[interest_mult1]["interet"]
                    wins_tot = calculer_pourcentage(float(user_epergne), float(interest_mult)) + float(user_epergne)
                    winned = wins_tot - int(user_epergne)
                    if int(calculer_pourcentage(float(user_epergne), float(interest_mult))) != 0:
                        print(f"<@{key}> : {int(calculer_pourcentage(float(user_epergne), float(interest_mult)))} Trapcoins ajoutés\n")
                        trapcoins_handler(type="add", userid=str(key), trapcoins_val=int(winned))
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
                    await self.bot.cursor.execute(f'INSERT INTO cpasbien (title_name) VALUES ("{title}")')
                    await self.bot.db_conn.commit()
                
                async def get_titles():
                    await self.bot.cursor.execute("SELECT title_name from cpasbien")
                    return await self.bot.cursor.fetchall()
                    
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
                    await self.bot.db_conn.commit()
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

    @tasks.loop(minutes=1)
    async def check_users_xp(self):
            # data = load_json_data(item="trapeur")
            data = await Trapardeur(conn=self.bot.db_conn, cursor=self.bot.cursor).get_all()
            for i in data:
                try:
                    xp = await xp_calculation(user_id=i[1], cursor=self.bot.cursor, conn=self.bot.db_conn)
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

async def setup(bot: Trapard):
    await bot.add_cog(Tasks(bot))