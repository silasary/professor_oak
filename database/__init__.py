import asyncio
import json
from typing import Dict, Optional

import peewee
import peeweedbevolve
from discord.ext.commands import Bot, Cog
from playhouse import db_url

from shared import configuration

POOL = db_url.connect(configuration.get('db'))

HASHES: Dict[str, str] = {}
HASHES_BY_NAME: Dict[str, str] = {}


class BaseModel(peewee.Model):
    class Meta:
        database = POOL


class Player(BaseModel):
    discord_id = peewee.BigIntegerField(null=False, unique=True)
    name = peewee.CharField(null=True, max_length=32, default=None)
    active = peewee.BooleanField(default=False)


class Pokemon(BaseModel):
    name = peewee.CharField(null=True, unique=True, max_length=32)

class Image(BaseModel):
    md5 = peewee.CharField(null=False, unique=True, max_length=32)
    pokemon = peewee.ForeignKeyField(Pokemon, backref='images', null=True)

    def load_name(self) -> None:
        if self.pokemon and self.pokemon.name:
            return
        if not HASHES:
            with open('imagehashes.json', mode='r') as f:
                HASHES.update({value["hash"]: value["name"]
                               for value in json.load(f)})
        name = HASHES.get(self.md5)
        if name is not None:
            if self.pokemon is None:
                pkmn, _ = Pokemon.get_or_create(name=name)
                self.pokemon = pkmn
            self.pokemon.name = name
        if self.name:
            self.save()

    def load_hash(self) -> None:
        if self.md5:
            return
        if not HASHES_BY_NAME:
            with open('imagehashes.json', mode='r') as f:
                HASHES_BY_NAME.update(
                    {value["name"]: value["hash"] for value in json.load(f)})
        self.md5 = HASHES_BY_NAME.get(self.pokemon.name)
        if self.md5:
            self.save()

    @property
    def name(self) -> Optional[str]:
        self.load_name()
        if self.pokemon is None:
            return None
        return self.pokemon.name
class PokedexEntry(BaseModel):
    pokemon = peewee.ForeignKeyField(Pokemon)
    person = peewee.ForeignKeyField(Player)
    caught = peewee.BooleanField(null=True)

    def checkmark(self) -> str:
        if self.caught is None:
            return '❓'
        elif self.caught:
            return '✅'
        return '❎'


class Database(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.pool = POOL
        bot.pool = self.pool

    def get_player(self, discord_id: int) -> Player:
        user, _ = Player.get_or_create(discord_id=discord_id)
        return user

    def check_player(self, discord_id: int) -> Optional[Player]:
        try:
            user = Player.get(discord_id=discord_id)
            return user
        except Player.DoesNotExist:
            return None

    def get_pokemon_image_by_hash(self, hashstr: str) -> Image:
        pkmn, _ = Image.get_or_create(md5=hashstr)
        return pkmn

    def get_pokemon_by_name(self, name: str) -> Pokemon:
        pkmn, _ = Pokemon.get_or_create(name=name)
        return pkmn

    def get_pokedex_entry(self, player_id: int, pkmn_name: str) -> PokedexEntry:
        player = self.get_player(player_id)
        pkmn = self.get_pokemon_by_name(pkmn_name)
        entry, _ = PokedexEntry.get_or_create(pokemon=pkmn, person=player)
        return entry

    def __enter__(self) -> 'Database':
        if self.pool.is_closed():
            self.pool.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pool.close()


POOL.evolve(interactive=False)


def setup(bot: Bot) -> None:
    bot.add_cog(Database(bot))
