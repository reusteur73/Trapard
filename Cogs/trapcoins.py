from .utils.functions import LogErrorInWebhook, command_counter, convert_k_m_to_int, editGstats, create_embed, write_item, afficher_nombre_fr, load_json_data, lol_player_in_game, display_big_nums, init_user_to_item
from discord.ext import commands
from .utils.data import interests_indexs, interests_infos, daily_claim_interest
from .utils.classes import TrapcoinsHandler
from discord import app_commands
import discord, locale, datetime, time
from bot import Trapard

class EpargneConfirm(discord.ui.View):
    def __init__(self, ctx, userid, tier, string, trapcoin_handler: TrapcoinsHandler):
        super().__init__()
        self.trapcoin_handler = trapcoin_handler
        self.ctx = ctx
        self.userid = userid
        self.tier = tier
        self.string_tier = string

        self.buttonoui = discord.ui.Button(style=discord.ButtonStyle.green, label="Oui", emoji="✅", custom_id="oui", disabled=False)
        self.add_item(self.buttonoui)
        self.buttonoui.callback = lambda interaction=self.ctx, button=self.buttonoui: self.on_button_click(interaction, button)

        self.buttonnon = discord.ui.Button(style=discord.ButtonStyle.grey, label="Non", emoji="❌", custom_id="non", disabled=False)
        self.add_item(self.buttonnon)
        self.buttonnon.callback = lambda interaction=self.ctx, button=self.buttonnon: self.on_button_click(interaction, button)

    async def on_button_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        if button.custom_id == "oui":
            if interaction.user.id == self.userid:

                cout = int(interests_infos[self.string_tier]["cout"])
                # Remove trapcoins
                usr_balance, _ = await self.trapcoin_handler.get(userid=int(self.userid))
                if usr_balance < cout:
                    embed = create_embed(title="Epargne-tiers", description=f"Vous n'avez pas assez de Trapcoins pour effectuer cette amélioration !")
                    return await self.ctx.send(embed=embed)
                write_item(item="interets", userid=str(self.userid), values={'tier': self.tier + 1})
                await self.trapcoin_handler.remove(userid=int(self.userid), amount=int(cout), wallet="trapcoins")
                pourcent = interests_infos[self.string_tier]["interet"]
                gain = locale.format_string("%d", interests_infos[self.string_tier]["gain max"], grouping=True)
                montant_max = locale.format_string("%d", interests_infos[self.string_tier]["max"], grouping=True)
                embed = create_embed(title="Epargne-tiers", description=f"Tu as amélioré ton niveau d'interet !!\n\nTu es maintenant au tier `{self.tier + 1}`.\n\nTu gagnes `{pourcent}%` chaque jours, avec un gain max de `{gain}` Trapcoins sur une épargne max de `{montant_max}` Trapcoins.")
                return await self.ctx.send(embed=embed)
            else:
                embed = create_embed(title="Epargne-tiers", description=f"<@{interaction.user.id}> tu n'es pas autorisé à utiliser le boutton de <@{self.userid}> !!")
                return await self.ctx.send(embed=embed)
        else:
            embed = create_embed(title="Epargne-tiers", description="L'amélioration a été annulé !")
            return await self.ctx.send(embed=embed)

class EpargneTier(discord.ui.View):
    def __init__(self, ctx: commands.Context, userid: int, pages: list,trapcoin_handler: TrapcoinsHandler):
        super().__init__()
        self.ctx = ctx
        self.userid = userid
        self.pages = pages
        self.page_count = len(pages)
        self.current_page = 0
        self.trapcoin_handler = trapcoin_handler

        self.current_user_tier = load_json_data(item="interets", userid=str(self.userid), opt_val="tier")
        if self.current_user_tier == "UserNotFound":
            write_item(item="interets", userid=str(self.userid), values={'tier': 1})
            self.current_user_tier = 1
        self.btn_to_enable = int(self.current_user_tier) + 1 
        self.btn1 = discord.ui.Button(style=discord.ButtonStyle.green, custom_id="unlock", label=f"Unlock Tier {self.btn_to_enable} ❌", row=1)
        self.btn_bef = discord.ui.Button(style=discord.ButtonStyle.secondary, custom_id="dis", label=f"Tier {self.btn_to_enable - 1} ☑️", row=1, disabled=True)
        self.btn_next = discord.ui.Button(style=discord.ButtonStyle.secondary, custom_id="dis1", label=f"Tier {self.btn_to_enable + 1} ❌", row=1, disabled=True)


        self.btn1.callback = lambda interaction=self.ctx, button=self.btn1: self.unlock_tier(interaction, button)

        self.boutton_last = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="▶️", custom_id="next")
        self.boutton_first = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="last")
        if self.current_page == 0:
            self.boutton_previous = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="◀️", disabled=True, custom_id="prev")
            self.boutton_suivant = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏮️", disabled=True, custom_id="first")
        else:
            self.boutton_suivant = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="⏮️", disabled=False, custom_id="first")
            self.boutton_previous = discord.ui.Button(label="", style=discord.ButtonStyle.secondary, emoji="◀️", disabled=False, custom_id="prev")


        self.add_item(self.boutton_suivant)
        self.add_item(self.boutton_previous)
        self.add_item(self.boutton_last)
        self.add_item(self.boutton_first)

        self.add_item(self.btn_bef)
        self.add_item(self.btn1)
        self.add_item(self.btn_next)

        self.boutton_suivant.callback = lambda interaction=self.ctx, button=self.boutton_suivant: self.go_to_first_page(interaction, button)
        self.boutton_previous.callback = lambda interaction=self.ctx, button=self.boutton_previous: self.go_to_previous_page(interaction, button)
        self.boutton_last.callback = lambda interaction=self.ctx, button=self.boutton_last: self.go_to_next_page(interaction, button)
        self.boutton_first.callback = lambda interaction=self.ctx, button=self.boutton_first: self.go_to_last_page(interaction, button)


    async def show_current_page(self, button: discord.Interaction, direction: int):
        self.current_page += direction
        if self.current_page < 0:
            self.current_page = 0
        elif self.current_page >= len(self.pages):
            self.current_page = len(self.pages) - 1
        elif self.current_page == len(self.pages):
            self.current_page = len(self.pages)

        first = discord.utils.get(self.children, custom_id="first")
        prev = discord.utils.get(self.children, custom_id="prev")
        next = discord.utils.get(self.children, custom_id="next")
        last = discord.utils.get(self.children, custom_id="last")

        if self.current_page < 2:
            first.disabled = True
        else: 
            first.disabled = False
        if self.current_page < 1:
            prev.disabled = True
        else: 
            prev.disabled = False
        if self.current_page >= len(self.pages) - 1:
            next.disabled = True
        else: 
            next.disabled = False
        if self.current_page >= len(self.pages) - 2:
            last.disabled = True
        else: 
            last.disabled = False

        await button.message.edit(embed=self.pages[self.current_page], view=self)
        try:
            await button.response.defer()
        except:
            pass

    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_current_page(interaction, -self.current_page)

    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_current_page(interaction, -1)

    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.page_count - 1:
            await self.show_current_page(interaction, 1)
        else:
            await self.show_current_page(interaction, 0)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_current_page(interaction, len(self.pages) - 1 - self.current_page)

    async def unlock_tier(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except:
            pass
        string = f"Tier {self.current_user_tier + 1}"
        if button.custom_id == f"unlock":
            tier = interests_indexs[self.btn_to_enable]
            formated_cout = locale.format_string("%d", interests_infos[tier]["cout"], grouping=True)
            view_comfirm = EpargneConfirm(ctx=self.ctx, userid=self.userid, tier=self.current_user_tier, string=string, trapcoin_handler=self.trapcoin_handler)
            embed = create_embed(title="Epargne-tiers", description=f"Attention, cela vous coutera {formated_cout} Trapcoins sur votre compte principal (celui avec lequelle vous jouez au g-roulette).\n\n**Etes vous sur ?**")
            await self.ctx.send(embed=embed, view=view_comfirm)


class Trapcoins(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
        self.claimed = {}

    @commands.hybrid_command(name="balance", aliases=["bal"])
    async def balance(self, ctx: commands.Context):
        """Voir ton nombre de Trapcoins."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        trapcoins, epargne = await self.bot.trapcoin_handler.get(userid=ctx.author.id)
        if isinstance(trapcoins, str):
            await self.bot.trapcoin_handler.create_user(userid=ctx.author.id)
            trapcoins, epargne = 0, 0
        sugg = ["g-roulette", "g-lol-bet", "devinette"]
        embed = create_embed(title="Balance", description=f"Tu as **{afficher_nombre_fr(trapcoins)} Trapcoins {str(trapcoins_emoji)}** sur ton compte courant.\nEt **{afficher_nombre_fr(epargne)} Trapcoins** {str(trapcoins_emoji)} en épargne.",suggestions=sugg)
        return await ctx.send(embed=embed)

    @commands.hybrid_command(name="transfer")
    @app_commands.describe(nombre= "Le montant que tu veux transferer. Exemple: 1m ou 200k ou 10000")
    async def transfer(self, ctx: commands.Context, to_user: discord.Member, nombre: str):
        """Transfère des Trapcoins à quelqu'un."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            trapcoins_emoji = "<:trapcoins:1108725845339672597>"
            if lol_player_in_game(self.bot.zigotos[ctx.author.id]) and int(ctx.author.id) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(ctx.author.id)] is not None:
                embed = create_embed(title="G-lol-bet", description=f"Il semble que vous êtes actuellement en game et que vous avez parié!\n\nVous ne pouvez pas transferer vos {str(trapcoins_emoji)} durant la partie. **BUICON**.")
                return await ctx.send(embed=embed)
            nombre = convert_k_m_to_int(nombre)
            if nombre == "ValueError":
                embed = create_embed(title="G-transfer", description="**Erreur**\n\nQuand vous utilisez le `nombre`, utilisez seulement les formats:\n`200k` (200 000)\n`2m` (2 000 000)\n`200 000`")
                return await ctx.send(embed=embed)

            # Check if the user has enough Trapcoins
            sender_id = ctx.author.id
            sender_points, _ = await self.bot.trapcoin_handler.get(userid=ctx.author.id)
            if sender_points < nombre:
                return await ctx.send("Tu n'as pas assez de Trapcoins !!")

            # Update the sender's points
            await self.bot.trapcoin_handler.remove(userid=ctx.author.id, amount=nombre, wallet="trapcoins")

            # Update the recipient's points
            await self.bot.trapcoin_handler.add(userid=to_user.id, amount=nombre, wallet="trapcoins")
            trapcoins_emoji = "<:trapcoins:1108725845339672597>"
            editGstats(userID=ctx.author.id, total_gains=None, total_pertes=None, transfert=-int(nombre), claims=None, win_alpha=None, nb_games=None, biggest_win=None)
            editGstats(userID=to_user.id, total_gains=None, total_pertes=None, transfert=int(nombre), claims=None, win_alpha=None, nb_games=None, biggest_win=None)
            embed = create_embed(title="G-transfer", description=f"{ctx.author.mention} a transferé {afficher_nombre_fr(nombre)} Trapcoins {str(trapcoins_emoji)} à {to_user.mention}.", suggestions=["g-balance","g-roulette","g-lol-bet"])
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

# EPARGNE GROUP
    @commands.hybrid_group()
    async def epargne(self, ctx: commands.Context):
        pass

    @epargne.command()
    @app_commands.choices(maximum=[discord.app_commands.Choice(name="Maxiumum", value="Maxiumum")])
    @app_commands.describe(amount= "Le montant que tu veux ajouter. Exemple: 1m ou 200k ou 10000")
    @app_commands.describe(maximum= "Retire tous les fonds de l'épargne.")
    async def add(self, ctx: commands.Context, amount: str=None, maximum: discord.app_commands.Choice[str]=None):
        """Ajouter des Trapcoins à ton épargne."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        # Vérifier que le montant est positif
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        try:
            if lol_player_in_game(self.bot.zigotos[ctx.author.id]) and int(ctx.author.id) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(ctx.author.id)] is not None:
                embed = create_embed(title="G-lol-bet", description=f"Il semble que vous êtes actuellement en game et que vous avez parié!\n\nVous ne pouvez pas épargner vos {str(trapcoins_emoji)} durant la partie. **BUICON**.")
                return await ctx.send(embed=embed)
        except:
            pass

        if amount is None and maximum is None:
            embed = create_embed(title="Epargne-in", description="Vous devez entrer une de ces deux valeurs:\n**amount** ou **maximum**")
            return await ctx.send(embed=embed)
        
        if amount and maximum:
            embed = create_embed(title="Epargne-in", description="Vous devez entrer une de ces deux valeurs:\n**amount** ou **maximum**\n\n**Mais pas les deux !! Une seul !**") 
            return await ctx.send(embed=embed)

        tier = load_json_data(item="interets", userid=str(ctx.author.id), opt_val="tier")
        if tier == "UserNotFound":
            init_user_to_item(item="interets", userid=str(ctx.author.id), values={"tier": 1})
            tier = 1
        balance, ep = await self.bot.trapcoin_handler.get(userid=ctx.author.id)
        str_tier = interests_indexs[int(tier)]
        max = interests_infos[str_tier]["max"]

        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        if amount:
            amount = convert_k_m_to_int(amount)
            if amount == "ValueError":
                embed = create_embed(title="Epargne-out", description="**Erreur**\n\nQuand vous utilisez le `amount`, utilisez seulement les formats:\n`200k` (200 000)\n`2m` (2 000 000)\n`200 000`")
                return await ctx.send(embed=embed)
            if amount < 1:
                embed = create_embed(title="Epargne-in", description="Le montant doit être supérieur à 0.")
                return await ctx.send(embed=embed)
            if amount + ep > max:
                embed = create_embed(title="Epargne-in", description=f"Vous ne pouvez pas deposer plus de **{display_big_nums(int(max))} ({afficher_nombre_fr(int(max))})** Trapcoins {str(trapcoins_emoji)} en épargne avec le {str_tier} !")
                return await ctx.send(embed=embed)
            if balance < amount:
                embed = create_embed(title="Epargne-in", description=f"Vous n'avez pas les fonds requis pour effectuer cette action !")
                return await ctx.send(embed=embed)
        else:
            amount = maximum

        await self.bot.trapcoin_handler.remove(userid=ctx.author.id, amount=amount, wallet="trapcoins")
        await self.bot.trapcoin_handler.add(userid=ctx.author.id, amount=amount, wallet="epargne")
        pts, ep = await self.bot.trapcoin_handler.get(userid=ctx.author.id)
        embed = create_embed(title="Epargne-in", description=f"**{display_big_nums(int(amount))} ({afficher_nombre_fr(int(amount))})** {str(trapcoins_emoji)} ont été ajoutés à votre épargne.\n\nTu as maintenant **{display_big_nums(int(pts))} ({afficher_nombre_fr(int(pts))})** {str(trapcoins_emoji)} sur ton compte courant.\nEt **{display_big_nums(int(ep))} ({afficher_nombre_fr(int(ep))})** {str(trapcoins_emoji)} en épargne.")
        return await ctx.send(embed=embed)

    @epargne.command()
    @app_commands.choices(maximum=[discord.app_commands.Choice(name="Maximum", value="Maximum")])
    @app_commands.describe(amount= "Le montant que tu veux retirer. Exemple: 1m ou 200k ou 10000")
    @app_commands.describe(maximum= "Retire tous les fonds de l'épargne.")
    async def remove(self, ctx: commands.Context, amount: str=None, maximum: discord.app_commands.Choice[str]=None):
        """Retier des Trapcoins à ton épargne."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)

        if amount is None and maximum is None:
            embed = create_embed(title="Epargne-in", description="Vous devez entrer une de ces deux valeurs:\n**amount** ou **Maximum**")
            return await ctx.send(embed=embed)
        
        if amount and maximum:
            embed = create_embed(title="Epargne-in", description="Vous devez entrer une de ces deux valeurs:\n**amount** ou **maximum**\n\n**Mais pas les deux !! Une seul !**") 
            return await ctx.send(embed=embed)

        user_id = str(ctx.author.id)
        balance, savings = await self.bot.trapcoin_handler.get(userid=user_id)

        if maximum:
            if savings > 0:
                to_put = savings
            else: 
                embed = create_embed(title="Epargne-out", description=f"Vous n'avez pas suffisamment d'argent dans votre épargne pour retirer des {str(trapcoins_emoji)}.\n\nLe maximum que vous pouvez retirer est **{display_big_nums(int(savings))} ({afficher_nombre_fr(int(savings))})** {str(trapcoins_emoji)}.")
                return await ctx.send(embed=embed)

        if amount:
            amount = convert_k_m_to_int(amount)
            if amount == "ValueError":
                embed = create_embed(title="Epargne-out", description="**Erreur**\n\nQuand vous utilisez le `amount`, utilisez seulement les formats:\n`200k` (200 000)\n`2m` (2 000 000)\n`200 000`")
                return await ctx.send(embed=embed)
            if amount < 1:
                embed = create_embed(title="Epargne-out", description="Le montant doit être supérieur à 0.")
                return await ctx.send(embed=embed)
            else:
                to_put = amount

        # Check if the user has enough savings
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        if savings >= to_put:
            # Remove the amount from the user's savings
            await self.bot.trapcoin_handler.remove(userid=user_id, amount=int(to_put), wallet="epargne")
            # Add the amount to the user's balance
            await self.bot.trapcoin_handler.add(userid=user_id, amount=int(to_put), wallet="trapcoins")
            pts, ep = await self.bot.trapcoin_handler.get(userid=user_id)
            embed = create_embed(title="Epargne-out", description=f"Vous avez retiré **{display_big_nums(int(to_put))} ({afficher_nombre_fr(int(to_put))})** {str(trapcoins_emoji)} de l'épargne.\n\nVous avez maintenant **{display_big_nums(int(pts))} ({afficher_nombre_fr(int(pts))})** {str(trapcoins_emoji)} sur votre compte courant.\nEt **{display_big_nums(int(ep))} ({afficher_nombre_fr(int(ep))})** {str(trapcoins_emoji)} en épargne.")
            return await ctx.send(embed=embed)
        else:
            embed = create_embed(title="Epargne-out", description=f"Vous n'avez pas suffisamment d'argent dans votre épargne pour retirer **{display_big_nums(int(to_put))} ({afficher_nombre_fr(int(to_put))})** {str(trapcoins_emoji)}.\n\nLe maximum que vous pouvez retirer est **{display_big_nums(int(savings))} ({afficher_nombre_fr(int(savings))})** {str(trapcoins_emoji)}.")
            return await ctx.send(embed=embed)

    @epargne.command()
    async def tiers(self, ctx: commands.Context):
        """Voir/débloquer les differents tiers d'interets."""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        try:
            if lol_player_in_game(self.bot.zigotos[ctx.author.id]) and int(ctx.author.id) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(ctx.author.id)] is not None:
                embed = create_embed(title="G-lol-bet", description="Il semble que vous êtes actuellement en game et que vous avez parié!\n\nVous ne pouvez pas gérer vos tiers durant la partie. **BUICON**.")
                return await ctx.send(embed=embed)
        except:
            pass
        userid = ctx.author.id
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        embeds = []
        i = 0
        page = 0
        total_pages = len(interests_infos) // 5
        embed = discord.Embed(title="Détail des Tiers")
        for key, data in interests_infos.items():
            string = f"- Cout : {display_big_nums(data['cout'])} {trapcoins_emoji}\n- Intérêt : {round(data['interet'], 2)}%\n- Épargne max : {display_big_nums(data['max'])} {trapcoins_emoji}\n- Gain max : **{display_big_nums(data['gain max'])} {trapcoins_emoji}**"
            embed.add_field(name=key, value=string)
            i += 1
            if i % 5 == 0:
                page += 1
                string2 = f"Page {page}/{total_pages}"
                embed.set_footer(text=f"{string2} | 1k: 1 000 | 1 M: 1 000 000 | 1 B: 1 000 000 000 | 1 T: 1 000 000 000 000")
                embeds.append(embed)
                embed = discord.Embed(title="Détail des Tiers")
        view = EpargneTier(ctx=ctx, userid=userid, pages=embeds, trapcoin_handler=self.bot.trapcoin_handler)

        await ctx.send(embed=embeds[0], view=view)
#END EPARGNE GROUP

    @commands.hybrid_command(name="dailyclaim")
    async def dailyclaim(self, ctx: commands.Context):
        """Récupérer tes Trapcoins quotidien."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            user_tier = load_json_data(item="interets", userid=str(ctx.author.id), opt_val="tier")
            bonus_gain = daily_claim_interest.get(user_tier)
            trapcoins_emoji = "<:trapcoins:1108725845339672597>"
            now = datetime.datetime.now()
            if ctx.author.id in self.claimed and self.claimed[ctx.author.id] == now.date():
                embed = create_embed(title="Daily-claim", description=f"Vous avez déjà récupéré vos Trapcoins {str(trapcoins_emoji)} aujourd'hui !", suggestions=["g-roulette", "g-lol-bet", "g-balance"])
                return await ctx.send(embed=embed)
            else:
                try:
                    user_streak_data = load_json_data(item="streak", userid=str(ctx.author.id))
                    user_streak, _ = user_streak_data['streak'], user_streak_data['timestamp']
                    user_streak += 1
                except: #USR NOT FOUND ?
                    user_streak = 1
                    init_user_to_item(item="streak", userid=str(ctx.author.id), values={"streak": 1, "timestamp": int(time.time())})
                    bonus_gain = 0
                if bonus_gain is None:
                    bonus_gain = 0
                bonus_streak = int(user_streak) * 10000
                total_gain = int(50000 + bonus_gain + bonus_streak)
                await self.bot.trapcoin_handler.add(userid=ctx.author.id, amount=total_gain, wallet="trapcoins")
                write_item(item="streak", userid=str(ctx.author.id), values={"streak": user_streak, "timestamp": int(time.time())})
                self.claimed[ctx.author.id] = now.date()
                editGstats(userID=ctx.author.id, total_gains=None, total_pertes=None, transfert=None, claims=total_gain, win_alpha=None, nb_games=None, biggest_win=None)
                txt = f"- Gain de base: **50 k** {str(trapcoins_emoji)}\n\n- Gain bonus tiers: **{display_big_nums(int(bonus_gain))}** {str(trapcoins_emoji)} || ({afficher_nombre_fr(bonus_gain)} {str(trapcoins_emoji)}) || (Tier {user_tier}) !\n\n- Gain bonus streak 🔥: **{display_big_nums(int(bonus_streak))}** {str(trapcoins_emoji)} || ({afficher_nombre_fr(bonus_streak)} {str(trapcoins_emoji)}) || (Streak de {user_streak}) 🔥\n\n- Total: **{display_big_nums(int(total_gain))} {str(trapcoins_emoji)}** || ({afficher_nombre_fr(total_gain)} {str(trapcoins_emoji)}) || claim !"
                embed = create_embed(title="G-daily-claim", description=txt)
                return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

    @commands.hybrid_command(name="baltop", aliases=["topbal"])
    async def baltop(self, ctx: commands.Context):
        """Affiche les plus grosse balance classé."""
        try:
            await command_counter(user_id=str(ctx.author.id), bot=self.bot)
            data = await self.bot.trapcoin_handler.baltop()      
            # Create an embed with the top balances
            embed = discord.Embed(title="Top Balances", color=discord.Color.blue())
            for i, line in enumerate(data): # Show only top 10 balances
                userid, balance, ep = line
                user = await self.bot.fetch_user(userid)
                embed.add_field(name=f"{i+1}. {user.display_name}", value=f"Balance: {afficher_nombre_fr(balance)}, epargne : {afficher_nombre_fr(ep)}", inline=True)
            return await ctx.send(embed=embed)
        except Exception as e:
            LogErrorInWebhook()

async def setup(bot: Trapard):
    await bot.add_cog(Trapcoins(bot))