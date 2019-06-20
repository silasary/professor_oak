import asyncio
import json
from typing import Optional

import peewee
import peewee_async
import peeweedbevolve
from discord.ext.commands import Bot, Cog
from playhouse import db_url

from shared import configuration

POOL = db_url.connect(configuration.get('db'))

HASHES = {}
HASHES_BY_NAME = {}

class BaseModel(peewee.Model):
    class Meta:
        database = POOL


class Player(BaseModel):
    discord_id = peewee.BigIntegerField(null=False, unique=True)
    name = peewee.CharField(null=True, max_length=32, default=None)
    active = peewee.BooleanField(default=False)


class Pokemon(BaseModel):
    md5 = peewee.CharField(null=True, unique=True, max_length=32)
    name = peewee.CharField(null=True, unique=True, max_length=32)

    def load_name(self) -> None:
        if self.name:
            return
        if not HASHES:
            with open('imagehashes.json', mode='r') as f:
                HASHES.update({value["hash"]: value["name"] for value in json.load(f)})
        self.name = HASHES.get(self.md5)
        if self.name:
            self.save()

    def load_hash(self) -> None:
        if self.md5:
            return
        if not HASHES_BY_NAME:
            with open('imagehashes.json', mode='r') as f:
                HASHES_BY_NAME.update({value["name"]: value["hash"] for value in json.load(f)})
        self.md5 = HASHES_BY_NAME.get(self.name)
        if self.md5:
            self.save()

class PokedexEntry(BaseModel):
    pokemon = peewee.ForeignKeyField(Pokemon)
    person = peewee.ForeignKeyField(Player)
    caught = peewee.BooleanField(null=True)

    def checkmark(self):
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


    def get_pokemon_by_hash(self, hashstr: str) -> Pokemon:
        pkmn, _ = Pokemon.get_or_create(md5=hashstr)
        return pkmn

    def get_pokemon_by_name(self, name: str) -> Pokemon:
        pkmn, _ = Pokemon.get_or_create(name=name)
        return pkmn

    def get_pokedex_entry(self, player_id, pkmn_name) -> PokedexEntry:
        player = self.get_player(player_id)
        pkmn = self.get_pokemon_by_name(pkmn_name)
        entry, _ = PokedexEntry.get_or_create(pokemon=pkmn, person=player)
        return entry

POOL.evolve(interactive=False)

def setup(bot: Bot) -> None:
    bot.add_cog(Database(bot))
