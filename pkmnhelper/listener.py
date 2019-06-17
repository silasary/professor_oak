import re
import os
import hashlib
import requests
import discord
from discord.ext import commands

Pokecord_id = 365975655608745985
catch_msg = re.compile(r'Congratulations <@[0-9]+>! You caught a level \d+ (\w+)!')

class Listener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == Pokecord_id:
            print(f'pokecord message: {message}')
            print(f'"{message.content}"')
            if message.embeds:
                for e in message.embeds:
                    title = e.title.strip('\u200c')
                    if title == 'A wild pokémon has appeared!':
                        await self.spawn(e, message)
                        # return
                    else:
                        print('> unknown pokecord message')
                        print(f'> {e}\n title: {repr(title)}\n desc: {e.description}')
                        for f in e.fields:
                            print(f'>> {f.name}={f.value}')
                        print(f'i {e.image.url}')
            elif catch_msg.match(message.content):
                await self.catch(message)
            else:
                pass


    async def spawn(self, embed, message):
        md5 = self.get_md5(embed.image.url)
        await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}', md5)
        db = self.bot.get_cog('Database')
        pkmn = db.get_pokemon_by_hash(md5)
        if not pkmn.name:
            pkmn.load_name()

        if not pkmn.name:
            await message.channel.send("I don't know this pokemon")
        else:
            await message.channel.send(f'This is a `{pkmn.name}`!')

    async def catch(self, message):
        match = catch_msg.match(message.content)
        print('Caught something!')
        md5 = await self.bot.redis.get(f'pkmn:lastspawn:{message.channel.id}')
        db = self.bot.get_cog('Database')
        pkmn = db.get_pokemon_by_hash(md5)
        if not pkmn.name:
            pkmn.name = match.group(1)
            db.update_pkmn(pkmn)

    def get_md5(self, url: str) -> str:
        resp = requests.get(url)
        md5 = hashlib.md5(resp.content).hexdigest()
        filename = os.path.join('images', md5 + '.jpg')
        if not os.path.exists(filename):
            print(f'saving {filename}')
            with open(filename, 'wb') as fd:
                for chunk in resp.iter_content(chunk_size=128):
                    fd.write(chunk)
        return md5

def setup(bot):
    bot.add_cog(Listener(bot))
