import discord
from discord.ext import commands
from bot import Trapard
from .utils.functions import LogErrorInWebhook, write_item, load_json_data
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
    async def pm(self, ctx: commands.Context, membre: discord.Member, *,message: str, ):
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
                        return await ctx.send(f"Query returned: {output[0]}")
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

async def setup(bot: Trapard):
    await bot.add_cog(Admin(bot))