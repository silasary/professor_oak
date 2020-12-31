from typing import List, cast

import aioredis
import discord
import discord.ext.commands
import discord.ext.tasks
from shared import configuration
from fastai import *
from fastai.vision import load_learner, open_image, sys

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
        super().load_extension('fieldwork.seeker')
        self.redis: aioredis.Redis = None

    def init(self) -> None:
        self.run(self.config.token)

    async def setup_learner(self):
        try:
            learn = load_learner('model/', 'pokemon_v6_resnet50.pkl')
            return learn.to_fp32()
        except RuntimeError as e:
            if len(e.args) > 0 and 'CPU-only machine' in e.args[0]:
                print(e)
                message = "\n\nThis model was trained with an old version of fastai and will not work in a CPU environment.\n\nPlease update the fastai library in your training environment and export your model again.\n\nSee instructions for 'Returning to work' at https://course.fast.ai."
                raise RuntimeError(message)
            else:
                raise

    async def on_ready(self) -> None:
        self.redis = await aioredis.create_redis_pool("redis://localhost", minsize=5, maxsize=10)
        self.learn = await self.setup_learner()
        print('Logged in as {username} ({id})'.format(username=self.user.name, id=self.user.id))
        print('Connected to {0}'.format(', '.join([server.name for server in self.guilds])))
        print('--------')


def init() -> None:
    client = Bot()
    client.init()

if __name__ == "__main__":
    init()
