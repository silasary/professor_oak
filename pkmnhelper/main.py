from typing import List, cast

import aioredis
import discord
import discord.ext.commands
import discord.ext.tasks
from shared import configuration

configuration.DEFAULTS.update({
    "token": "",
    "db": "mysql+pool://pkmn:passwd@localhost/pkmndb?max_connections=20&stale_timeout=300",
    "owners": [154363842451734528]
})

class Config():
    def __init__(self) -> None:
        pass

    @property
    def owners(self) -> List[str]:
        return cast(List[str], configuration.get('owners'))

    @property
    def token(self) -> str:
        return cast(str, configuration.get('token'))

class Bot(discord.ext.commands.Bot):
    def __init__(self) -> None:
        self.config = Config()
        super().__init__(command_prefix=discord.ext.commands.when_mentioned_or('='))
        super().load_extension('pkmnhelper.listener')
        super().load_extension('pkmnhelper.recommendations')
        super().load_extension('pkmnhelper.updater')
        super().load_extension('database')
        super().load_extension('discordbot.owner')
        super().load_extension('discordbot.errors')
        self.redis: aioredis.Redis = None

    def init(self) -> None:
        self.run(self.config.token)

    async def on_ready(self) -> None:
        self.redis = await aioredis.create_redis_pool("redis://localhost", minsize=5, maxsize=10)
        print('Logged in as {username} ({id})'.format(username=self.user.name, id=self.user.id))
        print('Connected to {0}'.format(', '.join([server.name for server in self.guilds])))
        print('--------')


def init() -> None:
    client = Bot()
    client.init()

if __name__ == "__main__":
    init()
