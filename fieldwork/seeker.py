from typing import List, Tuple
import database
import random
import csv
from pathlib import Path

from helpers.hashing import EmbedImage
from discord.ext import commands
from discord.ext.commands import Bot, Cog
from discord.ext.tasks import loop

mons: List[Tuple[int, str]] = []


# pylint: disable=no-self-use
class Fieldwork(Cog):
    def __init__(self, bot: Bot):
        self.time = ''
        self.bot = bot
        if bot is not None:
            self.db = bot.get_cog('database')
        if not self.db:
            self.db = database.Database(None)
        # self.observe_random_mon.start()

    # @loop(seconds=90)
    async def observe_random_mon(self) -> None:
        if not mons:
            load()
            self.time = 'night' if self.time == 'day' else 'day'
        dex, name = mons.pop()
        url = f"https://server.poketwo.net/image?species={dex}&time={self.time}"
        img = EmbedImage(url)
        phash = img.phash
        print(f'{phash}={name}')
        pkmn = self.db.get_pokemon_image_by_phash(phash)
        if not pkmn.pokemon:
            pkmn.pokemon = self.db.get_pokemon_by_name(name)
            pkmn.save()
            print(f'Learned that {phash} is {name} from fieldwork')

def isnumber(v):
    try:
        int(v)
    except ValueError:
        return False
    return True

def load() -> None:
    path = Path.cwd() / "data" / "pokemon.csv"

    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(
            {k: int(v) if isnumber(v) else v for k, v in row.items() if v != ""}
            for row in reader
        )
    mons.extend([(p['id'], p.get('name.en', p.get('slug'))) for p in data]) # type: ignore
    random.shuffle(mons)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Fieldwork(bot))
