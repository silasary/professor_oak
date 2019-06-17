import asyncio
import json

import peewee
import peewee_async
import peeweedbevolve
from discord.ext.commands import Bot, Cog
from playhouse import db_url

from shared import configuration

POOL = db_url.connect(configuration.get('db'))

HASHES = {}

class BaseModel(peewee.Model):
    class Meta:
        database = POOL


class Player(BaseModel):
    discord_id = peewee.BigIntegerField(null=False, unique=True)
    name = peewee.CharField(null=True, max_length=32, default=None)
    active = peewee.BooleanField(default=False)


class Pokemon(BaseModel):
    md5 = peewee.CharField(null=False, max_length=32)
    name = peewee.CharField(null=True, max_length=32)

    def load_name(self) -> None:
        if self.name:
            return
        if not HASHES:
            with open('imagehashes.json', mode='r') as f:
                HASHES.update({value["hash"]: value["name"] for value in json.load(f)})
        self.name = HASHES[self.md5]
        if self.name:
            Pokemon.update(self)

class Database(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.pool = POOL
        bot.pool = self.pool

    def get_player(self, discord_id: int) -> Player:
        user, _ = Player.get_or_create(discord_id=discord_id)
        return user

    def get_pokemon_by_hash(self, hashstr: str) -> Pokemon:
        pkmn, _ = Pokemon.get_or_create(md5=hashstr)
        return pkmn

    def update_pkmn(self, pkmn: Pokemon) -> None:
        Pokemon.update(pkmn)

POOL.evolve(interactive=False)

def setup(bot: Bot) -> None:
    bot.add_cog(Database(bot))
