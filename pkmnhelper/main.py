import subprocess
import sys
from typing import Dict, List

import aioredis
import discord
import discord.ext.commands
import discord.ext.tasks
from discord.errors import Forbidden
from discord.guild import Guild
from discord.message import Message
from discord.reaction import Reaction
from discord.user import User

from shared import configuration
from shared.limited_dict import LimitedSizeDict

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
        return configuration.get('owners')

class Bot(discord.ext.commands.Bot):
    def __init__(self) -> None:
        self.config = Config()
        super().__init__(command_prefix='~')
        super().load_extension('pkmnhelper.listener')
        super().load_extension('database')


    def init(self) -> None:
        self.update.start()
        self.run(configuration.get('token'))

    async def on_ready(self) -> None:
        self.redis = await aioredis.create_redis_pool("redis://localhost", minsize=5, maxsize=10)
        print('Logged in as {username} ({id})'.format(username=self.user.name, id=self.user.id))
        print('Connected to {0}'.format(', '.join([server.name for server in self.guilds])))
        print('--------')

    @discord.ext.tasks.loop(minutes=5.0)
    async def update(self) -> None:
        if not self.commit_id:
            self.update.stop()
            return
        subprocess.check_output(['git', 'fetch']).decode()
        commit_id = subprocess.check_output(['git', 'rev-parse', f'origin/{self.branch}']).decode().strip()
        if commit_id != self.commit_id:
            print(f'origin/{self.branch} at {commit_id}')
            print('Update found, shutting down')
            await self.close()

    @update.before_loop
    async def before_update(self):
        self.commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
        self.branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
        print(f'Currently running {self.commit_id} on {self.branch}')
        upstream = subprocess.check_output(['git', 'rev-parse', f'origin/{self.branch}']).decode().strip()
        if upstream != self.commit_id:
            print(f'Upstream at {upstream}. Auto-reboot disabled.')
            self.update.stop()
            self.commit_id = None


def init() -> None:
    client = Bot()
    client.init()

if __name__ == "__main__":
    init()

