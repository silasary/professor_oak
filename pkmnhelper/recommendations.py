from discord.ext import commands

import database


class Recommendations(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def recommend(self, ctx: commands.Context) -> None:
        missing_pages = set()
        highest_page_seen = 47 # Eternatus is currently highest
        seen_pages = set()
        with self.get_db() as db:
            for pkmn in db.get_all_pokemon():
                if db.get_pokemon_by_name(pkmn.name).dex_page is not None:
                    entry = db.get_pokedex_entry(ctx.author.id, pkmn.name, 716390085896962058)

                    if entry.caught is None:
                        missing_pages.add(pkmn.dex_page)
                    else:
                        seen_pages.add(pkmn.dex_page)
                    if pkmn.dex_page > highest_page_seen:
                        highest_page_seen = pkmn.dex_page

            for page in range(1, highest_page_seen):
                if page not in seen_pages:
                    missing_pages.add(page)

            if missing_pages:
                missing_list = list(missing_pages)
                missing_list.sort()

                pages = ', '.join([str(i) for i in missing_list[0:5]])
                await ctx.send(f'Show me pokedex pages {pages}')
                return

            await ctx.send("I don't have any recommendations for you at this time")

    def get_db(self) -> database.Database:
        return self.bot.get_cog('Database')

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Recommendations(bot))
