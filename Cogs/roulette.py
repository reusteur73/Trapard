from .utils.functions import LogErrorInWebhook, command_counter,convert_k_m_to_int, create_embed, write_item, afficher_nombre_fr, load_json_data, lol_player_in_game, display_big_nums
from .utils.path import G_STATS
from discord.ext import commands
import discord, random, json
from bot import Trapard


def get_last_20_numbers_embed():
    data = load_json_data(item="roulette-history")
    m = 'Les 36 derniers chiffres :\n```'
    for index, line in enumerate(data):
        if index != len(data) -1:
            m += str(line) + " - "
        else: m += str(line) + "."
    m += "```"
    return m

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


class QuestionnaireCustomAmount(discord.ui.Modal, title='Questionnaire Response'):
    montant = discord.ui.TextInput(label='Combien tu paris ?', style=discord.TextStyle.short, required=True, min_length=1, max_length=99)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.montant_value = self.montant.value
        return


class RouletteGame(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
        

    @commands.hybrid_command(name="roulette", aliases=["g-roulette"])
    async def roulette(self, ctx: commands.Context):
        """Paris tes Trapcoins à la roulette."""
        
        class Roulette(discord.ui.View):
            try:
                def __init__(self, inter: commands.Context, serverid: int, player_balance, phase: int, bot: Trapard, wanted_game: str=None, bet_amount: int=None, winning_number: int=None, winning_color: str=None):
                    super().__init__(timeout=None)
                    self.bot = bot
                    self.inter = inter
                    self.serverid = serverid
                    self.winning_number = winning_number
                    self.winning_color = winning_color
                    self.player_balance = player_balance
                    self.phase = phase
                    self.trapcoins_em = "<:trapcoins:1108725845339672597>"
                    self.wanted_game = wanted_game
                    self.bet_amount = bet_amount
                    self.e = get_last_20_numbers_embed()

                    self.payouts = {
                        'alpha': 35,
                        'paire-impaire': 1,
                        'rouge-noir': 1,
                        'haut-bas': 1,
                        'douzaines': 2,
                        'colonnes': 2
                    }

                    if self.phase == 1:
                        self.alpha_btn = discord.ui.Button(label="Alpha",style=discord.ButtonStyle.blurple, custom_id="alpha")
                        self.paire_impaire_btn = discord.ui.Button(label="Paire/impaire",style=discord.ButtonStyle.blurple, custom_id="paire-impaire")
                        self.rouge_noir_btn = discord.ui.Button(label="Rouge/noir",style=discord.ButtonStyle.blurple, custom_id="rouge-noir")
                        self.haut_bas_btn = discord.ui.Button(label="Haut/bas",style=discord.ButtonStyle.blurple, custom_id="haut-bas")
                        self.douzaines_btn = discord.ui.Button(label="douzaines",style=discord.ButtonStyle.blurple, custom_id="douzaines")
                        self.colonnes_btn =  discord.ui.Button(label="colonnes",style=discord.ButtonStyle.blurple, custom_id="colonnes")

                        self.add_item(self.alpha_btn)
                        self.add_item(self.paire_impaire_btn)
                        self.add_item(self.rouge_noir_btn)
                        self.add_item(self.haut_bas_btn)
                        self.add_item(self.douzaines_btn)
                        self.add_item(self.colonnes_btn)

                        self.alpha_btn.callback = lambda interaction=self.inter, button=self.alpha_btn: self.handle_phase(interaction, button, self.phase) 
                        self.paire_impaire_btn.callback = lambda interaction=self.inter, button=self.paire_impaire_btn: self.handle_phase(interaction, button, self.phase) 
                        self.rouge_noir_btn.callback = lambda interaction=self.inter, button=self.rouge_noir_btn: self.handle_phase(interaction, button, self.phase) 
                        self.haut_bas_btn.callback = lambda interaction=self.inter, button=self.haut_bas_btn: self.handle_phase(interaction, button, self.phase) 
                        self.douzaines_btn.callback = lambda interaction=self.inter, button=self.douzaines_btn: self.handle_phase(interaction, button, self.phase) 
                        self.colonnes_btn.callback = lambda interaction=self.inter, button=self.colonnes_btn: self.handle_phase(interaction, button, self.phase) 

                        self.winning_number, self.winning_color = self.spin_wheel()

                    elif self.phase == 2:
                        def calculate_percentages(x):
                            return [int(x*0.25), int(x*0.5), int(x*0.75), int(x)]
                        self.bet_list = calculate_percentages(self.player_balance)

                        self.button_25 = discord.ui.Button(style=discord.ButtonStyle.grey, label=f"25% - {afficher_nombre_fr(int(self.bet_list[0]))}", custom_id="25")
                        self.button_50 = discord.ui.Button(style=discord.ButtonStyle.primary, label=f"50% - {afficher_nombre_fr(int(self.bet_list[1]))}", custom_id="50")
                        self.button_75 = discord.ui.Button(style=discord.ButtonStyle.green, label=f"75% - {afficher_nombre_fr(int(self.bet_list[2]))}", custom_id="75")
                        self.button_100 = discord.ui.Button(style=discord.ButtonStyle.red, label=f"100% - {afficher_nombre_fr(int(self.bet_list[3]))}", custom_id="100")
                        self.button_custom = discord.ui.Button(style=discord.ButtonStyle.blurple, label=f"Montant custom", custom_id="custom")
                        if self.inter.author.id in self.bot.user_predefinie:
                            if self.player_balance < self.bot.user_predefinie[self.inter.author.id]:
                                self.button_custom2 = discord.ui.Button(style=discord.ButtonStyle.blurple, label=f"Montant définie - {afficher_nombre_fr(self.bot.user_predefinie[self.inter.author.id])}", custom_id="custom2", disabled=True)
                            else:
                                self.button_custom2 = discord.ui.Button(style=discord.ButtonStyle.blurple, label=f"Montant définie - {afficher_nombre_fr(self.bot.user_predefinie[self.inter.author.id])}", custom_id="custom2", disabled=False)
                        self.add_item(self.button_25)
                        self.button_25.callback = lambda interaction=self.inter, button=self.button_25: self.handle_phase(interaction, button, self.phase)
                        self.add_item(self.button_50)
                        self.button_50.callback = lambda interaction=self.inter, button=self.button_50: self.handle_phase(interaction, button, self.phase)
                        self.add_item(self.button_75)
                        self.button_75.callback = lambda interaction=self.inter, button=self.button_75: self.handle_phase(interaction, button, self.phase)
                        self.add_item(self.button_100)
                        self.button_100.callback = lambda interaction=self.inter, button=self.button_100: self.handle_phase(interaction, button, self.phase)
                        self.add_item(self.button_custom)
                        self.button_custom.callback = lambda interaction=self.inter, button=self.button_custom: self.handle_phase(interaction, button, self.phase)
                        if self.inter.author.id in self.bot.user_predefinie:
                            self.add_item(self.button_custom2)
                            self.button_custom2.callback = lambda interaction=self.inter, button=self.button_custom2: self.handle_phase(interaction, button, self.phase)
                    
                    elif self.phase == 3: # Handle items
                        if self.wanted_game == "alpha":
                            self.zero_quinze_btn = discord.ui.Button(label="0-15",style=discord.ButtonStyle.blurple, custom_id="0-15")
                            self.seize_trente_six_btn = discord.ui.Button(label="16-36",style=discord.ButtonStyle.blurple, custom_id="16-36")
                            self.add_item(self.zero_quinze_btn)
                            self.add_item(self.seize_trente_six_btn)
                            self.zero_quinze_btn.callback = lambda interaction=self.inter, button=self.zero_quinze_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.seize_trente_six_btn.callback = lambda interaction=self.inter, button=self.seize_trente_six_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                        if self.wanted_game == "paire-impaire":
                            self.paire_btn = discord.ui.Button(label="Paire",style=discord.ButtonStyle.blurple, custom_id="paire")
                            self.impaire_btn = discord.ui.Button(label="Impaire",style=discord.ButtonStyle.blurple, custom_id="impaire")
                            self.add_item(self.paire_btn)
                            self.add_item(self.impaire_btn)
                            self.paire_btn.callback = lambda interaction=self.inter, button=self.paire_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.impaire_btn.callback = lambda interaction=self.inter, button=self.impaire_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                        if self.wanted_game == "rouge-noir":
                            self.rouge_btn = discord.ui.Button(label="Rouge",style=discord.ButtonStyle.blurple, custom_id="rouge")
                            self.noir_btn = discord.ui.Button(label="Noir",style=discord.ButtonStyle.blurple, custom_id="noir")
                            self.add_item(self.rouge_btn)
                            self.add_item(self.noir_btn)
                            self.rouge_btn.callback = lambda interaction=self.inter, button=self.rouge_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.noir_btn.callback = lambda interaction=self.inter, button=self.noir_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                        if self.wanted_game == "haut-bas":
                            self.haut_btn = discord.ui.Button(label="Haut",style=discord.ButtonStyle.blurple, custom_id="haut")
                            self.bas_btn = discord.ui.Button(label="Bas",style=discord.ButtonStyle.blurple, custom_id="bas")
                            self.add_item(self.haut_btn)
                            self.add_item(self.bas_btn)
                            self.haut_btn.callback = lambda interaction=self.inter, button=self.haut_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.bas_btn.callback = lambda interaction=self.inter, button=self.bas_btn: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                        if self.wanted_game == "douzaines":
                            self.premiere = discord.ui.Button(label="1er",style=discord.ButtonStyle.blurple, custom_id="1")
                            self.deuxieme = discord.ui.Button(label="2ème",style=discord.ButtonStyle.blurple, custom_id="2")
                            self.troisieme = discord.ui.Button(label="3ème",style=discord.ButtonStyle.blurple, custom_id="3")
                            self.add_item(self.premiere)
                            self.add_item(self.deuxieme)
                            self.add_item(self.troisieme)
                            self.premiere.callback = lambda interaction=self.inter, button=self.premiere: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.deuxieme.callback = lambda interaction=self.inter, button=self.deuxieme: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.troisieme.callback = lambda interaction=self.inter, button=self.troisieme: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                        if self.wanted_game == "colonnes":
                            self.premiere = discord.ui.Button(label="1er",style=discord.ButtonStyle.blurple, custom_id="1")
                            self.deuxieme = discord.ui.Button(label="2ème",style=discord.ButtonStyle.blurple, custom_id="2")
                            self.troisieme = discord.ui.Button(label="3ème",style=discord.ButtonStyle.blurple, custom_id="3")
                            self.add_item(self.premiere)
                            self.add_item(self.deuxieme)
                            self.add_item(self.troisieme)
                            self.premiere.callback = lambda interaction=self.inter, button=self.premiere: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.deuxieme.callback = lambda interaction=self.inter, button=self.deuxieme: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
                            self.troisieme.callback = lambda interaction=self.inter, button=self.troisieme: self.handle_phase(interaction, button, self.phase, game_type=self.wanted_game) 
    
                    elif self.phase == 4.1:
                        for i in range(0, 16):
                            button = discord.ui.Button(style=discord.ButtonStyle.blurple, label=str(i), disabled=False, custom_id=f"{i}")
                            button.callback = lambda interaction, button=button: self.handle_phase(interaction, button, self.phase)
                            self.add_item(button)
                    
                    elif self.phase == 4.2:
                        for i in range(16, 37):
                            button = discord.ui.Button(style=discord.ButtonStyle.blurple, label=str(i), disabled=False, custom_id=f"{i}")
                            button.callback = lambda interaction, button=button: self.handle_phase(interaction, button, self.phase)
                            self.add_item(button)
                    
                    elif self.phase == 5: # Rejouer 
                        # Rejouer BTN
                        if int(self.player_balance) <= 1:
                            self.rejouer_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Rejouer", emoji="🔄", custom_id="rejouer", disabled=True)
                        else:
                            self.rejouer_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Rejouer", emoji="🔄", custom_id="rejouer")
                        self.add_item(self.rejouer_button)
                        self.rejouer_button.callback = lambda interaction=self.inter, button=self.rejouer_button: self.handle_phase(interaction, button, self.phase)

                        # BaltopBTN
                        self.baltop_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="Baltop", emoji="💰", custom_id="baltop")
                        self.add_item(self.baltop_btn)
                        self.baltop_btn.callback = lambda interaction=self.inter, button=self.baltop_btn: self.handle_phase(interaction, button, self.phase)

                        # Stats BTN
                        self.stats_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="Afficher les stats", emoji="📈", custom_id="stats")
                        self.add_item(self.stats_btn)
                        self.stats_btn.callback = lambda interaction=self.inter, button=self.stats_btn: self.handle_phase(interaction, button, self.phase)

                        # Devinette BTN
                        self.dev_btn = discord.ui.Button(style=discord.ButtonStyle.primary, label="Devinette", emoji="🤔", custom_id="devinette")
                        self.add_item(self.dev_btn)
                        self.dev_btn.callback = lambda interaction=self.inter, button=self.dev_btn: self.handle_phase(interaction, button, self.phase)

                async def handle_phase(self, interaction: discord.Interaction, button: discord.ui.Button, current_phase: int, game_type: str=None):
                    print("Btn clicked")
                    try:
                        if button.custom_id != "custom":
                            await interaction.response.defer()
                    except:
                        pass
                    print(1)
                    if interaction.user.id != self.inter.author.id:
                        embed = create_embed(title="G-roulette", description=f"- <@{interaction.user.id}>, tu n'es pas autorisé à jouer à la place de <@{self.inter.author.id}>\n\n- Utilises </g-roulette:1103411566868709508> pour jouer.")
                        return await interaction.followup.send(embed=embed, ephemeral=True)
                    if current_phase == 1: # Choix du type de pari
                        print(2)
                        self.bot.user_locks[interaction.user.id] = True
                        self.wanted_game = button.custom_id
                        print(22)
                        embed = create_embed(title="G-roulette", description=f"<@{ctx.author.id}>,\n\n- Tu as **{afficher_nombre_fr(int(self.player_balance))}** Trapcoins {self.trapcoins_em}.\n\n- **Combien tu paris ?**\n\n- {self.e}")
                        print(222)
                        try:
                            view = Roulette(inter=self.inter, serverid=self.serverid, winning_number=self.winning_number,winning_color=self.winning_color,player_balance=self.player_balance,phase=2, wanted_game=self.wanted_game, bot=self.bot)
                        except Exception as e:
                            print(e)
                        print(3)
                    elif current_phase == 2: # Choix du montant du paris paris
                        if button.custom_id == "25":
                            self.bet_amount = self.bet_list[0]
                        elif button.custom_id == "50":
                            self.bet_amount = self.bet_list[1]
                        elif button.custom_id == "75":
                            self.bet_amount = self.bet_list[2]
                        elif button.custom_id == "100":
                            self.bet_amount = self.bet_list[3]
                        elif button.custom_id == "custom":
                            modal = QuestionnaireCustomAmount(title="Combien tu paris ?", custom_id="1")
                            await interaction.response.send_modal(modal)
                            await modal.wait()
                            self.bet_amount = convert_k_m_to_int(modal.montant_value)
                            if self.bet_amount == "ValueError":
                                embed = create_embed(title="G-roulette", description="**Erreur**\n\nPour entrer un montant custom, utilisez seulement les formats:\n`200k` (200 000)\n`2m` (2 000 000)\n`200 000`")
                                return await interaction.message.edit(embed=embed, view=None)
                            if self.bet_amount <= 0 or self.bet_amount > self.player_balance:
                                del self.bot.user_locks[self.inter.author.id]
                                return await interaction.message.edit("Il semble que tu n'aies pas assez de Trapcoins.", view=None)
                        elif button.custom_id == "custom2":
                            self.bet_amount = self.bot.user_predefinie[interaction.user.id]
                        embed = create_embed(title="G-roulette", description=f"<@{ctx.author.id}>,\n\n- Tu paris {display_big_nums(int(self.bet_amount))} {str(self.trapcoins_em)}. || ({afficher_nombre_fr(self.bet_amount)} {str(self.trapcoins_em)}) ||\n\n- En {self.wanted_game}.\n\n- **Dans quelle moitier ce situe ton chiffre ?**\n\n- {self.e}")
                        view = Roulette(inter=self.inter, serverid=self.serverid, winning_number=self.winning_number,winning_color=self.winning_color,player_balance=self.player_balance,phase=3, wanted_game=self.wanted_game,bet_amount=self.bet_amount, bot=self.bot)
                    
                    elif current_phase == 3: # Handle paris ICI
                        if game_type == "alpha": # Handle alpha
                            embed = create_embed(title="G-roulette", description=f"<@{ctx.author.id}>,\n\n- Tu paris {display_big_nums(int(self.bet_amount))} {str(self.trapcoins_em)}. || ({afficher_nombre_fr(self.bet_amount)} {str(self.trapcoins_em)}) ||\n\n- En {self.wanted_game}.\n\n- **Sur quelle nombre tu paris ?**\n\n- {self.e}")
                            if button.custom_id == "0-15":
                                view = Roulette(inter=self.inter, serverid=self.serverid, winning_number=self.winning_number,winning_color=self.winning_color,player_balance=self.player_balance,phase=4.1, wanted_game=self.wanted_game,bet_amount=self.bet_amount)
                            elif button.custom_id == "16-36":
                                view = Roulette(inter=self.inter, serverid=self.serverid, winning_number=self.winning_number,winning_color=self.winning_color,player_balance=self.player_balance,phase=4.2, wanted_game=self.wanted_game,bet_amount=self.bet_amount)

                        elif game_type == "paire-impaire": # handle paire impaire
                            self.bet_on = button.custom_id
                            if (self.winning_number % 2 == 0 and button.custom_id == 'paire') or (self.winning_number % 2 == 1 and button.custom_id == 'impaire'):
                                self.gains = self.bet_amount * self.payouts[self.wanted_game]
                                return await self.end_game(win=True, interaction=interaction)
                            else:
                                self.gains = self.bet_amount
                                return await self.end_game(win=False, interaction=interaction)
                        
                        elif game_type == "rouge-noir":
                            self.bet_on = button.custom_id
                            if (self.winning_color == 'rouge' and button.custom_id == 'rouge') or (self.winning_color == 'noir' and button.custom_id == 'noir'):
                                self.gains = self.bet_amount
                                return await self.end_game(win=True, interaction=interaction)
                            else:
                                self.gains = self.bet_amount
                                return await self.end_game(win=False, interaction=interaction)
                        elif game_type == "haut-bas":
                            self.bet_on = button.custom_id
                            high_numbers = list(range(19, 37))
                            low_numbers = list(range(1, 19))
                            if (self.winning_number in high_numbers and button.custom_id == "haut") or (self.winning_number in low_numbers and button.custom_id == "bas"):
                                self.gains = self.bet_amount
                                return await self.end_game(win=True, interaction=interaction)
                            else:
                                self.gains = self.bet_amount
                                self.player_balance -= self.bet_amount
                                return await self.end_game(win=False, interaction=interaction)
                        elif game_type == "douzaines":
                            self.bet_on = button.custom_id
                            dozen1_numbers = list(range(1, 13))
                            dozen2_numbers = list(range(13, 25))
                            dozen3_numbers = list(range(25, 37))
                            if (self.winning_number in dozen1_numbers and button.custom_id == '1') or (self.winning_number in dozen2_numbers and button.custom_id == '2') or (self.winning_number in dozen3_numbers and button.custom_id == '3'):
                                self.gains = (self.bet_amount * 2)
                                return await self.end_game(win=True, interaction=interaction)
                            else:
                                self.gains = self.bet_amount
                                return await self.end_game(win=False, interaction=interaction)
                        elif game_type == "colonnes":
                            self.bet_on = button.custom_id
                            numbers = list(range(0, 37))
                            column1_numbers = [n for n in numbers if (n-1) % 3 == 0]
                            column2_numbers = [n for n in numbers if (n-2) % 3 == 0]
                            column3_numbers = [n for n in numbers if n % 3 == 0 and n != 0]
                            if (self.winning_number in column1_numbers and button.custom_id == '1') or (self.winning_number in column2_numbers and button.custom_id == '2') or (self.winning_number in column3_numbers and button.custom_id == '3'):
                                self.gains = (self.bet_amount * 2)
                                return await self.end_game(win=True, interaction=interaction)
                            else:
                                self.gains = self.bet_amount
                                return await self.end_game(win=False, interaction=interaction)
                    
                    elif current_phase == 4.1 or current_phase == 4.2: # Juste pour les alpha
                        self.bet_on = int(button.custom_id)
                        if self.bet_on == self.winning_number:
                            self.gains = self.bet_amount * self.payouts[self.wanted_game]
                            return await self.end_game(win=False, interaction=interaction)
                        else: # Lose alpha
                            self.gains = self.bet_amount
                            return await self.end_game(win=False, interaction=interaction)
                    
                    elif current_phase == 5: # Handle Rejouer 
                        if button.custom_id == "rejouer":
                            view = Roulette(inter=ctx, serverid=ctx.guild.id, winning_color=self.winning_color, winning_number=self.winning_number, player_balance=player_balance, phase=1, bot=self.bot)
                            e = get_last_20_numbers_embed()
                            embed = create_embed(title="G-roulette", description=f"<@{ctx.author.id}>,\n\n- Tu as **{afficher_nombre_fr(int(self.player_balance))}** Trapcoins {self.trapcoins_em}.\n\n- Quel est le type de pari ?\n\n- {e}")
                        # if button.custom_id == "baltop":
                        #     await baltop.callback(interaction)
                        # if button.custom_id == "stats":
                        #     await gStats.callback(interaction)
                        # if button.custom_id == "devinette":
                        #     await guessing_game.callback(interaction)
                    try:
                        print(4)
                        return await interaction.edit_original_response(embed=embed, view=view)
                    except Exception as e:
                        print(e)
                        pass

                async def end_game(self, win: bool, interaction: discord.Interaction):
                    if win:
                        await self.bot.trapcoin_handler.add(userid=self.inter.author.id, amount=self.gains, wallet="trapcoins")
                    else:
                        await self.bot.trapcoin_handler.remove(userid=self.inter.author.id, amount=self.gains, wallet="trapcoins")
                    last_nums = load_json_data(item="roulette-history")
                    last_nums.append(int(self.winning_number))
                    last_nums = last_nums[-36:]
                    write_item(item="roulette-history", array=last_nums)
                    e = get_last_20_numbers_embed()
                    del self.bot.user_locks[interaction.user.id]
                    editGstats(userID=self.inter.author.id, total_gains=self.bet_amount * self.payouts[self.wanted_game], total_pertes=None, transfert=None, claims=None, win_alpha=None, nb_games=1, biggest_win=self.bet_amount * self.payouts[self.wanted_game])
                    tr, ep = await self.bot.trapcoin_handler.get(userid=self.inter.author.id)
                    if win:
                        embed = create_embed(title="G-roulette", description=f"🤑<@{self.inter.author.id}> **- Bravo tu as gagné, en {self.wanted_game} {display_big_nums(int(self.bet_amount * self.payouts[self.wanted_game]))}  {self.trapcoins_em} || ({afficher_nombre_fr(self.bet_amount * self.payouts[self.wanted_game])} {self.trapcoins_em}) || 🤑**\n\n{e}\n\n- Tu as {display_big_nums(tr)} {self.trapcoins_em} || ({afficher_nombre_fr(tr)}) {self.trapcoins_em} || en poche.\n- Et {display_big_nums(int(ep))} {self.trapcoins_em} || ({afficher_nombre_fr(ep)}) {self.trapcoins_em}) || en épargne.", suggestions=["g-roulette", "g-balance", "g-stats"])
                    else:
                        embed = create_embed(title="G-roulette", description=f"💸 <@{self.inter.author.id}> **- Sad tu as perdu, en {self.wanted_game} {display_big_nums(int(self.bet_amount))} {self.trapcoins_em} || ({afficher_nombre_fr(self.bet_amount)} {self.trapcoins_em}) ||  💸**\n\n- Le bon numéro étais **{self.winning_number}**.\n- **Vous avez parié sur {self.bet_on}.**\n\n- {e}\n\n- Tu as {display_big_nums(tr)} {self.trapcoins_em} || ({afficher_nombre_fr(tr)}) {self.trapcoins_em} || en poche.\n- Et {display_big_nums(ep)} {self.trapcoins_em} || ({afficher_nombre_fr(ep)}) {self.trapcoins_em}) || en épargne.")

                    view = Roulette(inter=ctx, serverid=ctx.guild.id, winning_color=self.winning_color, winning_number=self.winning_number, player_balance=self.player_balance, phase=5, bot=self.bot)
                    return await interaction.message.edit(embed=embed, view=view)

                def spin_wheel(self):
                    """Simulates spinning the roulette wheel and returns the winning number and color."""
                    numbers = list(range(0, 37)) # 0-36
                    colors = ['vert'] + ['rouge', 'noir']*18
                    winning_number = random.choice(numbers)
                    winning_color = colors[winning_number] if winning_number != 0 else 'vert'
                    print("_wheel spinned !")
                    return winning_number, winning_color
                
            except Exception as e:
                LogErrorInWebhook()
            
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        try:
            if await lol_player_in_game(self.bot.zigotos[ctx.author.id], bot=self.bot) and int(ctx.author.id) in self.bot.lol_bet_dict and self.bot.lol_bet_dict[int(ctx.author.id)] is not None:
                embed = create_embed(title="G-lol-bet", description=f"Il semble que vous êtes actuellement en game et que vous avez parié!\n\nVous ne pouvez pas parier vos {str(trapcoins_emoji)} durant la partie. **BUICON**.")
                return await ctx.send(embed=embed)
        except:
            pass
        if ctx.channel.name == "général" or ctx.channel.name == "lol-games-reward":
            embed = create_embed(title="Erreur", description="Merci de ne pas utiliser les channels général et lol-games-reward pour le g-roulette.")
            return await ctx.send(embed=embed, ephemeral=True)
        player_balance, _ = await self.bot.trapcoin_handler.get(userid=ctx.author.id)
        if player_balance == 0:
            del self.bot.user_locks[ctx.author.id]
            embed = create_embed(title="G-roulette", description="Il semble que tu n'aies plus de pièces...")
            return await ctx.send(embed=embed)
        
        if ctx.author.id in self.bot.user_locks:
            embed = create_embed(title="G-roulette", description=f"{ctx.author.name}, vous avez déjà lancé la roulette. Veuillez patienter jusqu'à ce que le jeu soit terminé.\n C'est un bug ? /g-debug.")
            return await ctx.send(embed=embed)
        
        self.bot.user_locks[ctx.author.id] = True

        e = get_last_20_numbers_embed()
        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        view1 = Roulette(inter=ctx, serverid=ctx.guild.id, player_balance=player_balance, phase=1, bot=self.bot)
        embed = create_embed(title="G-roulette", description=f"<@{ctx.author.id}>,\n\n- Tu as **{afficher_nombre_fr(player_balance)}** Trapcoins {trapcoins_emoji}.\n\n- Quel est le type de pari ?\n\n- {e}")
        await ctx.send(embed=embed, view=view1)
        # interaction = await view1.wait()

    @commands.hybrid_command(name='roulette-stats', aliases=["r-stats"])
    async def gStats(self, ctx: commands.Context):
        """Affiche les statistiques de chaques joueurs sur le g-roulette"""
        await command_counter(user_id=str(ctx.author.id), bot=self.bot)
        with open(G_STATS, "r") as file:
            player_data = json.load(file)

        trapcoins_emoji = "<:trapcoins:1108725845339672597>"
        embed = discord.Embed(title="Les stats du g-roulette:")
        for player in player_data:
            username = self.bot.get_user(int(player)).name
            embed.add_field(name=f"{username}", value=f'Gains: {display_big_nums(int(player_data[player]["gains_total"]))} {str(trapcoins_emoji)}\nPertes: {display_big_nums(int(player_data[player]["pertes_total"]))} {str(trapcoins_emoji)}\nPlus gros gain: {display_big_nums(int(player_data[player]["plus_gros_gain"]))} {str(trapcoins_emoji)}\nTransferts: {display_big_nums(int(player_data[player]["transfert"]))} {str(trapcoins_emoji)}\nClaims: {display_big_nums(int(player_data[player]["claims"]))} {str(trapcoins_emoji)}\nAlpha win: {player_data[player]["win_en_alpha"]}\nGames: {player_data[player]["nombre_parties_jouees"]}', inline=True)
        return await ctx.send(embed=embed)

async def setup(bot: Trapard):
    await bot.add_cog(RouletteGame(bot))
    