import asyncio
import hashlib
import os
import re
from typing import TYPE_CHECKING, List

import discord
import requests
from confusable_homoglyphs import categories, confusables
from discord.ext import commands

if TYPE_CHECKING:
    import database

Pokecord_id = 365975655608745985
catch_msg = re.compile(r'Congratulations <@([0-9]+)>! You caught a level \d+ ([\w ]+)!')
lvlup_title = re.compile(r'^Congratulations ([\w ]+)!$')
lvlup_desc = re.compile(r'^Your ([\w ]+) is now level \d+!$')


class Listener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_result = None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id == Pokecord_id:
            print(f'pokecord message: {message}')
            print(f'"{message.content}"')
            if message.embeds:
                for e in message.embeds:
                    title = e.title.strip('\u200c')
                    title = rationalize_characterset(title) # They're using homographs on us
                    if title == 'A wild pokémon has appeared!' or title == 'A wild pokémon has appearedǃ':
                        await self.spawn(e, message)
                    elif title.startswith('Congratulations '):
                        await self.levelup(e, message)
                    else:
                        print('> unknown pokecord message')
                        print(f'> {e}\n title: {repr(title)}\n desc: {e.description}')
                        for f in e.fields:
                            print(f'>> {f.name}={f.value}')
                        print(f'i {e.image.url}')
            elif catch_msg.match(message.content):
                await self.catch(message)
            else:
                print('> no embed?')
                pass

    async def levelup(self, embed: discord.Embed, message: discord.Message) -> None:
        delete_after_delay(message)
        reg_level = lvlup_title.match(embed.title)
        if reg_level:
            name = reg_level.group(1)
            member = self.get_user(message.guild, name)
            if member is None:
                print(f"I don't know who {name} is!")
                return
            reg_desc = lvlup_desc.match(embed.description)
            print(f'{member}->{reg_desc.group(1)}')
            with self.get_db() as db:
                entry = db.get_pokedex_entry(member.id, reg_desc.group(1))
                if entry.caught != True:
                    entry.caught = True
                    entry.save()
            return
        print('unknown levelup:')
        print(f'> {embed}\n title: {repr(embed.title)}\n desc: {embed.description}')
        for f in embed.fields:
            print(f'>> {f.name}={f.value}')

    async def spawn(self, embed: discord.Embed, message: discord.Message) -> None:
        md5 = self.get_md5(embed.image.url)
        await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}', md5)
        with self.get_db() as db:
            pkmn = db.get_pokemon_image_by_hash(md5)

            if not pkmn.name:
                await message.channel.send("I don't know this pokemon")
            else:
                embed = discord.Embed()
                for p in self.active_players(message.guild):
                    entry = db.get_pokedex_entry(p.id, pkmn.name)
                    embed.add_field(name=p.display_name, value=entry.checkmark(), inline=False)
                if len(embed) == 0:
                    embed = None
                await message.channel.send(f'This is a `{pkmn.name}`!', embed=embed)

    async def catch(self, message: discord.Message):
        match = catch_msg.match(message.content)
        player_id = int(match.group(1))
        truename = match.group(2)
        print(f'Caught {truename}!')
        md5 = await self.bot.redis.get(f'pkmn:lastspawn:{message.channel.id}')
        with self.get_db() as db:
            img = db.get_pokemon_image_by_hash(md5)
            if not img.pokemon:
                img.pokemon = db.get_pokemon_by_name(truename)
                img.save()
            elif img.name != truename:
                print(f'Caught {truename}, expected {img.name}. Aborting.')
                return
            entry = db.get_pokedex_entry(player_id, truename)
            entry.caught = True
            entry.save()

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

    def active_players(self, guild: discord.Guild) -> List[discord.Member]:
        db = self.get_db()
        players = []
        for m in guild.members:
            if m.status == discord.Status.online and db.check_player(m.id):
                players.append(m)
        return players

    def get_user(self, guild: discord.Guild, name: str) -> discord.Member:
        for m in guild.members:
            if m.display_name == name:
                return m
        return None

    def get_db(self) -> 'database.Database':
        return self.bot.get_cog('Database')

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Listener(bot))


def rationalize_characterset(text: str) -> str:
    chars = confusables.is_confusable(text, preferred_aliases=['latin', 'common'], greedy=True)
    if chars:
        for issue in chars:
            bad = issue['character']
            replacement = [c for c in issue['homoglyphs'] if categories.aliases_categories(c['c'])[0] == 'LATIN'][0]
            print(f"{bad} ({issue['alias']}) -> {replacement['c']} ({replacement['n']})")
            text = text.replace(bad, replacement['c'])
    return text

def delete_after_delay(message: discord.Message) -> None:
    async def delete() -> None:
        await asyncio.sleep(3)
        await message.delete()
    asyncio.ensure_future(delete())
