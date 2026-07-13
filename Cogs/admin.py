import discord, subprocess
from io import BytesIO
from PIL import Image
from discord.ext import commands
from bot import Trapard
from .utils.functions import LogErrorInWebhook, write_item, load_json_data, create_embed
from asyncio import sleep
from Cogs.utils.RiotCore import RiotAPI, RiotAssetsAPI
from typing import Optional, Literal, List


class DataViewPage(discord.ui.View):
    def __init__(self, *,ctx: commands.Context, embeds: List[discord.Embed]):
        super().__init__(timeout=160)
        self.current_page = 0
        self.ctx = ctx
        self.embeds = embeds
        self.page_count = len(self.embeds)
        print(self.page_count, "nn")
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
        self.boutton_suivant.callback = lambda interaction=self.ctx, button=self.boutton_suivant: self.go_to_first_page(interaction, button)
        self.boutton_previous.callback = lambda interaction=self.ctx, button=self.boutton_previous: self.go_to_previous_page(interaction, button)
        self.boutton_last.callback = lambda interaction=self.ctx, button=self.boutton_last: self.go_to_next_page(interaction, button)
        self.boutton_first.callback = lambda interaction=self.ctx, button=self.boutton_first: self.go_to_last_page(interaction, button)
    async def show_current_page(self, inter: discord.Interaction, direction: int):
        self.current_page += direction
        if self.current_page < 0:
            self.current_page = 0
        elif self.current_page >= self.page_count:
            self.current_page = self.page_count - 1
        elif self.current_page == self.page_count:
            self.current_page = self.page_count

        first: discord.Button = discord.utils.get(self.children, custom_id="first")
        prev: discord.Button = discord.utils.get(self.children, custom_id="prev")
        next: discord.Button = discord.utils.get(self.children, custom_id="next")
        last: discord.Button = discord.utils.get(self.children, custom_id="last")

        if self.current_page < 2:
            first.disabled = True
        else: 
            first.disabled = False
        if self.current_page < 1:
            prev.disabled = True
        else: 
            prev.disabled = False
        if self.current_page >= self.page_count - 1:
            next.disabled = True
        else: 
            next.disabled = False
        if self.current_page >= self.page_count - 2:
            last.disabled = True
        else: 
            last.disabled = False

        await inter.message.edit(embed=self.embeds[self.current_page], view=self)
        try:
            await inter.response.defer()
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
        await self.show_current_page(interaction, self.page_count - 1 - self.current_page)


class Admin(commands.Cog):
    def __init__(self, bot: Trapard) -> None:
        self.bot = bot
    
    @commands.command(name="add-trapcoins", hidden=True)
    @commands.is_owner()
    async def add_trapcoins(self, ctx: commands.Context, userid: discord.Member, nb: int):
        try:
            if ctx.author.id != self.bot.owner_id:
                return await ctx.send("Tu n'es pas autorisé à utiliser cette commande !")
            tr, ep = await self.bot.trapcoin_handler.get(userid=userid.id)
            if tr == "Unknown user":
                await self.bot.trapcoin_handler.create_user(userid=userid.id)
                await self.bot.trapcoin_handler.add(userid=userid.id, amount=int(nb), wallet='trapcoins')
            else:
                await self.bot.trapcoin_handler.add(userid=userid.id, amount=int(nb), wallet='trapcoins')
            return await ctx.send("points ajouté !", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

    @commands.command()
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        if not guilds:
            if spec == "~":
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await self.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await self.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.is_owner()
    async def mp(self, ctx: commands.Context, membre: discord.Member, *,message: str, ):
        try:
            if ctx.author.id != 311013099719360512:
                return await ctx.send("Vous n'êtes pas autorisé à utiliser cette commande.", ephemeral=True)
            user = await self.bot.fetch_user(membre.id)
            await user.send(message)
            return await ctx.send("Le message a été envoyé !", ephemeral=True)
        except Exception as e:
            LogErrorInWebhook()

    @commands.command()
    @commands.is_owner()
    async def fetch(self, ctx: commands.Context, user: discord.User):
        try:
            if ctx.author.id != 311013099719360512:
                return await ctx.send("This command is only available for the bot owner.")
            channel = user.dm_channel or await user.create_dm()
            messages = []
            await ctx.send('a')
            async for message in channel.history(limit=100):
                    messages.append(f"Auteur: {message.author} - `{message.content}`")
                    await ctx.send(f"Auteur: {message.author} - `{message.content}`")
        except Exception as e:
            LogErrorInWebhook()

    @commands.command(name="sql")
    @commands.is_owner()
    async def text(self, ctx: commands.Context, query_type: Literal["fetchall", "fetchone", "exec", "execute"], *, query: str):
        try:
            async with self.bot.pool.acquire() as conn:
                if query_type in ["exec", "execute"]:
                    cmd = await conn.execute(query)
                    output = None
                else:
                    fetch_func = getattr(conn, query_type)
                    cmd = await fetch_func(query)
                    output = cmd
                if output is not None:
                    print(output, len(output))
                    if (isinstance(output, int)) or (len(output)) == 1:
                        return await ctx.send(f"Query returned: `{' | '.join(map(str, output[0]))}`")
                    print(len(output))
                    embeds = []
                    embed = discord.Embed(title="SQL request")
                    field = "```"
                    for i, row in enumerate(output):
                        print(row)
                        if i % 10 == 0 and i != 0:
                            field += "```"
                            embed.add_field(name=f"Page 1", value=field, inline=False)
                            embeds.append(embed)
                            embed = discord.Embed(title="SQL request")
                            field = "```"
                        line = " | ".join(map(str, row))
                        field += line + "\n"
                        if (i == len(output) -1) and (i < 10):
                            field += "```"
                            embed.add_field(name=f"Page 1", value=field, inline=False)
                            embeds.append(embed)
                    if embed.fields:
                        embeds.append(embed)
                    view = DataViewPage(ctx=ctx, embeds=embeds)
                    await ctx.send(f"query: {query}", view=view, embed=embeds[0])
                else:
                    await ctx.send(f"query: {query} executed successfully")
        except Exception as e:
            LogErrorInWebhook()

    @commands.command(name="reboot")
    @commands.is_owner()
    async def reboot(self, ctx: commands.Context):
        try:
            if ctx.author.id != self.bot.owner_id:
                return await ctx.send("You are not allowed to use this command.")
            await ctx.send(embed=create_embed(title="Admin", description="Rebooting...\n*ETA: 20-40s*", color=0xff0000))
            proc = subprocess.run(
                ["sudo", "systemctl", "restart", "trapard"],
                capture_output=True,
                text=True
            )
            if proc.returncode != 0:
                await ctx.send(embed=create_embed(title="Admin", description=f"❌ Failed to restart service.\nError: {proc.stderr}", color=0xff0000))
        except Exception as e:
            LogErrorInWebhook()

    @commands.is_owner()
    @commands.command(name='reload', description='DEV: Reload a cog file', hidden=True)
    async def reload_cog(self, interaction: commands.Context, cog: str) -> None:
        from bot import initial_extensions
        if f"Cogs.{cog}" not in initial_extensions:
            return await interaction.reply(embed=create_embed(title="Cog Reload", description=f'Cog "{cog}" ne semble pas exister.\nIl doit être dans la liste suivante: {", ".join([c.replace("Cogs.", "") for c in initial_extensions])}', color=0xff0000))
        try:
            await self.bot.reload_extension(f"Cogs.{cog}")
            await interaction.reply(embed=create_embed(title="Cog Reload", description=f'Cog "{cog}" rechargée avec succès.', color=0x00ff00))
        except Exception as e:
            await interaction.reply(embed=create_embed(title="Cog Reload", description=f'Erreur lors du rechargement du Cog "{cog}".\nErreur: {e}', color=0xff0000))

    @commands.is_owner()
    @commands.command(name='checkemojis', description='Create and check all lol champion emojis', hidden=True)
    async def check_emojis(self, interaction: commands.Context) -> None:
        EMOJIS_GUILDS_IDS = [1464341094769885186,1464341347564781824,1464341600682377411,1464341853473345579]
        riot_assets_api = RiotAssetsAPI(session=self.bot.session)
        riot_api = RiotAPI(session=self.bot.session)
        api_version = await riot_api.get_api_version()
        champion_list = await riot_assets_api.get_champions_list(api_version=api_version)
        all_present_emojis = []
        for guild_id in EMOJIS_GUILDS_IDS:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            existing_emojis = {emoji.name: emoji for emoji in guild.emojis}
            all_present_emojis.extend(existing_emojis.keys())
        print(len(all_present_emojis), "emojis already present")
        for _, champ_data in champion_list.items():
            emoji_name = champ_data['id'].lower().replace("'", "").replace(".", "").replace(" ", "_")
            if emoji_name in all_present_emojis:
                continue
            champion_icon_image = await riot_assets_api.get_champion_icon(championName=champ_data['id'], api_version=api_version)
            if champion_icon_image is None:
                continue

            created = False
            # Try to create the emoji in the first guild that has a free slot and doesn't already have it
            for guild_id in EMOJIS_GUILDS_IDS:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue

                # skip if emoji already exists in this guild
                if any(e.name == emoji_name for e in guild.emojis):
                    created = True
                    break

                # respect the guild's emoji limit (fallback to 50)
                limit = getattr(guild, "emoji_limit", 50)
                if len(guild.emojis) >= limit:
                    print(f"Guild {guild.name} has reached emoji limit ({limit}), skipping.")
                    continue

                try:
                    # Ensure we pass proper PNG/JPEG bytes to Discord (not raw pixel data)
                    if isinstance(champion_icon_image, bytes):
                        image_bytes = champion_icon_image
                    else:
                        buf = BytesIO()
                        try:
                            # Try saving as PNG
                            champion_icon_image.save(buf, format='PNG', optimize=True)
                        except Exception:
                            champion_icon_image = champion_icon_image.convert("RGBA")
                            champion_icon_image.save(buf, format='PNG', optimize=True)
                        image_bytes = buf.getvalue()

                        # Resize if it's too large for Discord (256KB)
                        MAX_SIZE = 256 * 1024
                        if len(image_bytes) > MAX_SIZE:
                            resized = champion_icon_image.resize((128, 128), Image.LANCZOS)
                            buf = BytesIO()
                            resized.save(buf, format='PNG', optimize=True)
                            image_bytes = buf.getvalue()

                    await guild.create_custom_emoji(name=emoji_name, image=image_bytes)
                    print(f"Emoji {emoji_name} created in guild {guild.name}")
                    all_present_emojis.append(emoji_name)
                    created = True
                    await sleep(10)  # avoid hitting rate limits
                    break
                except Exception as e:
                    # log and try the next guild
                    LogErrorInWebhook(f"Error creating emoji {emoji_name} in guild {guild.name}: {e}")
                    return

            if not created:
                LogErrorInWebhook(f"No available guild slots to create emoji {emoji_name}")

    @commands.is_owner()
    @commands.command(name='initmastery', description='Initialize mastery data for all users', hidden=True)
    async def init_mastery(self, interaction: commands.Context) -> None:
        riot_api = RiotAPI(session=self.bot.session)
        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetchall("SELECT puuid, region FROM LoLGamesTracker")
            for row in rows:
                puuid = row['puuid']
                region = row['region']
                champions_masteries = await riot_api.get_all_champion_masteries(puuid=puuid, region=region)
                for champ_mastery in champions_masteries.data:
                    champion_id = champ_mastery['championId']
                    mastery_level = champ_mastery['championLevel']
                    mastery_points = champ_mastery['championPoints']
                    points_since_last_level = champ_mastery['championPointsSinceLastLevel']
                    points_until_next_level = champ_mastery['championPointsUntilNextLevel']
                    await conn.execute(
                        "INSERT OR REPLACE INTO LoLChampionsMastery (champion_id, puuid, mastery_level, mastery_points, points_since_last_level, points_until_next_level) VALUES (?, ?, ?, ?, ?, ?)",
                        champion_id, puuid, mastery_level, mastery_points, points_since_last_level, points_until_next_level
                    )
                print(f"Initialized mastery data for user {puuid}")
            return await interaction.reply(f"Mastery data initialization complete for {len(rows)} users.")

async def setup(bot: Trapard):
    await bot.add_cog(Admin(bot))