from discord.ext import commands
from bot import Trapard
from .utils.functions import LogErrorInWebhook, create_embed, command_counter, calc_usr_gain_by_tier, afficher_nombre_fr, write_item, load_json_data
from .utils.path import DEVINETTE_WORDS_LIST, FILES_PATH
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import base64, asyncio,requests, random, discord

MAX = 22730

async def async_download(word, userid):
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('start-maximized')
        options.add_argument('--headless')
        options.add_argument('disable-infobars')

        service = Service('/usr/local/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)

        if driver is not None:
            driver.get("https://images.google.com/imghp?hl=fr&gl=fr")
            await asyncio.sleep(0.2)
            coockie = driver.find_element(By.XPATH, '//*[@id="L2AGLb"]').click()
            await asyncio.sleep(0.2)
            # Find the search box and enter the search query
            search_box = driver.find_element(By.CSS_SELECTOR, '.gLFyf')
            search_box.send_keys(word)
            search_box.send_keys(Keys.RETURN)
            # Find all image thumbnails on the page
            try:
                thumbnails = driver.find_elements(By.XPATH, "//img[@class='rg_i Q4LuWd']")
                print("Found", len(thumbnails), "thumbnails")
                nb = len(thumbnails)
            except Exception as e:
                print(e)

            # Download the first 10 images
            count = 0
            tasks = []
            for thumbnail in thumbnails[:10]:
                try:
                    img_src = thumbnail.get_attribute("src")
                    if img_src.startswith("data:image/"):
                        # Decode the base64-encoded image data
                        img_data = base64.b64decode(img_src.split(",")[1])
                        img_ext = img_src.split(";")[0].split("/")[-1]
                        img_path = f"{FILES_PATH}image{count}_{userid}.jpg"
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                    else:
                        # Download the image from the URL
                        task = asyncio.ensure_future(async_request(img_src, count, userid))
                        tasks.append(task)
                    print(f"Downloaded {word}_{count}.{img_ext}")
                    count += 1
                except Exception as e:
                    print(e)

            await asyncio.gather(*tasks)
            driver.quit()
            return nb
    except Exception as e:
        print(e)

async def async_request(img_src, count, userid):
    response = await asyncio.get_event_loop().run_in_executor(None, requests.get, img_src)
    img_ext = response.headers.get("content-type").split("/")[-1]
    img_path = f"{FILES_PATH}image{count}_{userid}.jpg"
    with open(img_path, "wb") as f:
        f.write(response.content)

async def main_async(userid):
    loop = asyncio.get_event_loop()
    f = open(DEVINETTE_WORDS_LIST, "r", encoding='UTF-8').readlines()
    randint = random.randint(1, MAX)
    word = str(f[randint]).strip()
    nb = await async_download(word, userid)
    return word, nb

def check(word, answer):
    try:
        result = ''
        word = str(word).lower()
        for i in range(min(len(word), len(answer))):
            if answer[i] == word[i]:
                result += answer[i]
            else:
                result += '*'
        result = '```'+ result + '```'
        return result
    except Exception as e:
        LogErrorInWebhook()

def getDevRank(pts):
    try:
        if pts < 25:
            rank = "Noobie Soldat Trapard"
        elif pts >= 25 and pts <= 49:
            rank = "Caporal Trapard"
        elif pts >= 50 and pts <= 99:
            rank = "Sergent Trapard"
        elif pts >= 100 and pts <= 199:
            rank = "Adjudant Trapard"
        elif pts >= 200 and pts <= 399:
            rank = "Lieutenant Trapard"
        elif pts >= 400 and pts <= 499:
            rank = "Capitaine Trapard"
        elif pts >= 500 and pts <= 599:
            rank = "Commandant Trapard"
        elif pts >= 600 and pts <= 749:
            rank = "Colonel Trapard"
        elif pts >= 750 and pts <= 999:
            rank = "Général de brigade Trapard"
        elif pts >= 1000 and pts <= 1999:
            rank = "Général de division Trapard"
        elif pts >= 2000 and pts <= 2999:
            rank = "Roi Trapard"
        elif pts >= 3000:
            rank = "Dieu Trapard"
        else:
            rank = "Error"
        return rank
    except Exception as e:
        LogErrorInWebhook()

class Devinette(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
        self.points = {}
        self.devinette_daily = {}

    @commands.hybrid_command(name='devinette', description="Devine le mot")
    async def devinette(self, ctx: commands.Context):
        """Devine le mot en fonction des images."""
        return await devinette_command(ctx, self, self.bot)


class DevinetteRejouer(discord.ui.View):
    def __init__(self, player, ctx: commands.Context, devinette: Devinette, bot: Trapard):
        super().__init__()
        self.bot = bot
        self.userid = player
        self.ctx = ctx
        self.devinette = devinette

        self.rejouer_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Rejouer", emoji="🔄", custom_id="rejouer")
        self.add_item(self.rejouer_button)
        self.rejouer_button.callback = lambda interaction=self.ctx, button=self.rejouer_button: self.action(interaction, button)

        self.ladderbtn = discord.ui.Button(style=discord.ButtonStyle.blurple, label="Ladder", emoji="📈", custom_id="ladder")
        self.add_item(self.ladderbtn)
        self.ladderbtn.callback = lambda interaction=self.ctx, button=self.ladderbtn: self.action(interaction, button)
        
    async def action(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except Exception:
            pass
        if button.custom_id == "rejouer":
            if interaction.user.id == self.userid:
                await devinette_command(self.ctx, self.devinette, self.bot)
            else:
                return

async def devinette_command(interaction: commands.Context, devinette: Devinette, bot: Trapard):
    try:
        await command_counter(user_id=str(interaction.author.id), bot=bot)
        user = str(interaction.author.name)
        userid = interaction.author.id
        points1 = 0
        if user not in devinette.points:
            devinette.points[user] = 0
        embed = create_embed(title="Devinette", description="Séléction du mot & récupération des images...")
        await interaction.send(embed=embed)
        answer, nb = await main_async(userid)
        rejouer = DevinetteRejouer(player=userid, ctx=interaction, devinette=devinette, bot=bot)
        if nb == 0:
            embed = create_embed(title="Devinette erreur", description="Une erreur est survenue lors de la récupération des images...")
            return await interaction.send(embed=embed, view=rejouer)
        answer = str(answer).lower()
        test = 'https://fr.wiktionary.org/wiki/' + answer
        embed = create_embed(title="Devinette", description="Devine le mot clé de cette image:")

        await interaction.channel.send(embed=embed)
        for i in range(0, 10):
            try:
                with open(f"{FILES_PATH}image" + str(i) + f"_{userid}.jpg", "rb") as f:
                    await interaction.channel.send(file=discord.File(f))
            except FileNotFoundError:
                embed = create_embed(title="Devinette erreur", description="Une erreur est survenue... Désolé :'(")
                return await interaction.channel.send(embed=embed, view=rejouer)
            try:
                guess = await bot.wait_for('message', check=lambda message: message.author == interaction.author, timeout=100)
            except asyncio.TimeoutError:
                embed = create_embed(title="Devinette", description="Trop lent! Temps écoulé! le mot clé était **__{}__**".format(answer))
                await interaction.channel.send(embed=embed, view=rejouer)
                deef = "{}".format(test)
                if len(deef) > 2000:
                    deef1 = deef[:1000]
                    deef2 = deef[1000:]
                    await interaction.channel.send(deef1)
                    await interaction.channel.send(deef2)
                else:
                    deef1 = deef
                    await interaction.channel.send("<" + deef1 + ">")
                return
            guess.content = str(guess.content).lower()
            if guess.content == answer:
                deviniette_bonus = None
                if interaction.author.id not in devinette.devinette_daily:
                    devinette.devinette_daily[interaction.author.id] = 1
                    deviniette_bonus = 25000
                    pts_bonus = 10
                else:
                    __ = devinette.devinette_daily[interaction.author.id]
                    __ += 1
                    if __ <= 4:
                        deviniette_bonus = 25000
                        pts_bonus = 10
                        devinette.devinette_daily[interaction.author.id] = __
                if i == 0:
                    points1 += 5
                    trapcoins = 10000
                elif i == 1:
                    points1 += 4
                    trapcoins = 7500
                elif i == 2:
                    points1 += 3
                    trapcoins = 5000
                elif i == 3:
                    points1 += 2
                    trapcoins = 2500
                elif i >= 4:
                    points1 += 1
                    trapcoins = 1000
                if i + 1 > 1:
                    s = 's'
                else:
                    s = ""
                if points1 == 1:
                    ss = ""
                else:
                    ss = "s"
                tier_bonus = calc_usr_gain_by_tier(userid)
                await bot.trapcoin_handler.add(userid=userid, amount=int(tier_bonus), wallet="trapcoins")
                if deviniette_bonus:
                    await bot.trapcoin_handler.add(userid=userid, amount=deviniette_bonus, wallet="trapcoins")
                    msg = "Bravo ! tu as deviné le bon mot clé en " + str(i + 1 ) + f" essaie{s}. Tu as gagné {afficher_nombre_fr(points1 + pts_bonus)} points ainsi que **{afficher_nombre_fr(trapcoins)}** (gain de base) + **{afficher_nombre_fr(deviniette_bonus)}** (grâce aux daily: {devinette.devinette_daily[interaction.author.id]}/4) et {afficher_nombre_fr(tier_bonus)}, c'est à dire **{afficher_nombre_fr(trapcoins + deviniette_bonus + tier_bonus)} Trapcoins**!"
                    tot = points1 + pts_bonus
                    prev_score = load_json_data(item="devinette", userid=str(userid))
                    if prev_score == "UserNotFound":
                        write_item(item="devinette", userid=str(userid), values={'points': 0, 'total_games': 0})
                    tot = tot + prev_score["points"]
                    total_games = prev_score['total_games'] + 1
                    write_item(item="devinette", userid=str(userid), values={'points': tot, 'total_games': total_games})
                else:
                    msg = "Bravo ! tu as deviné le bon mot clé en " + str(i + 1 ) + f" essaie{s}. Tu as gagné **" + str(points1) + f"** point{ss} ainsi que **{afficher_nombre_fr(trapcoins)}** Trapcoins!"
                    prev_score = load_json_data(item="devinette", userid=str(userid))
                    if prev_score == "UserNotFound":
                        write_item(item="devinette", userid=str(userid), values={'points': 0, 'total_games': 0})
                    tot = points1 + prev_score["points"]
                    total_games = prev_score['total_games'] + 1
                    write_item(item="devinette", userid=str(userid), values={'points': tot, 'total_games': total_games})
                embed = create_embed(title="Devinette", description=msg)
                await interaction.channel.send(embed=embed, view=rejouer)
                deef = "{}".format(test)
                if len(deef) > 2000:
                    deef1 = deef[:1000]
                    deef2 = deef[1000:]
                    await interaction.channel.send(deef1)
                    await interaction.channel.send(deef2)
                else:
                    deef1 = deef
                    await interaction.channel.send("<" + deef1 + ">")
                await bot.trapcoin_handler.add(userid=userid, amount=trapcoins, wallet="trapcoins")
                return
            elif guess.content == "jsp":
                embed = create_embed(title="Devinette", description="Noob, tu as abandonné! le mot clé était **__{}__**".format(answer))
                await interaction.channel.send(embed=embed, view=rejouer)
                prev_score = load_json_data(item="devinette", userid=str(userid))
                if prev_score == "UserNotFound":
                    write_item(item="devinette", userid=str(userid), values={'points': 0, 'total_games': 0})
                tot = prev_score["points"]
                total_games = prev_score['total_games'] + 1
                write_item(item="devinette", userid=str(userid), values={'points': tot, 'total_games': total_games})

                deef = "{}".format(test)
                if len(deef) > 2000:
                    deef1 = deef[:1000]
                    deef2 = deef[1000:]
                    await interaction.channel.send(deef1)
                    await interaction.channel.send(deef2)
                else:
                    deef1 = deef
                    await interaction.channel.send("<" + deef1 + ">")
                return
            else:
                correct_letters = check(guess.content, answer)
                embed = create_embed(title="Devinette", description="Lettres correctes: {}{}/10 essaies".format(correct_letters, i + 1))
                await interaction.channel.send(embed=embed)
        embed = create_embed(title="Devinette", description="Nul, tu n'as pas deviné le bon mot clé en 10 essaies. Le mot clé était **__{}__**.".format(answer))
        await interaction.channel.send(embed=embed, view=rejouer)
        prev_score = load_json_data(item="devinette", userid=str(userid))
        if prev_score == "UserNotFound":
            write_item(item="devinette", userid=str(userid), values={'points': 0, 'total_games': 0})
        tot = prev_score["points"]
        total_games = prev_score['total_games'] + 1
        write_item(item="devinette", userid=str(userid), values={'points': tot, 'total_games': total_games})

        deef = "{}".format(test)
        if len(deef) > 2000:
            deef1 = deef[:1000]
            deef2 = deef[1000:]
            await interaction.channel.send(deef1)
            await interaction.channel.send(deef2)
        else:
            deef1 = deef
            await interaction.channel.send("<" + deef1 + ">")
    except Exception as e:
        LogErrorInWebhook()

async def setup(bot: Trapard):
    await bot.add_cog(Devinette(bot))