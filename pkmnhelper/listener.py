import asyncio
import hashlib
import os
import re
from typing import TYPE_CHECKING, List

import discord
import imagehash
import PIL
import requests
from confusable_homoglyphs import categories, confusables
from discord.ext import commands

if TYPE_CHECKING:
    import database

Pokecord_id = 365975655608745985
catch_msg = re.compile(r'Congratulations <@([0-9]+)>! You caught a level \d+ ([\w ]+)!')
lvlup_title = re.compile(r'^Congratulations ([\w ]+)!$')
lvlup_desc = re.compile(r'^Your ([\w ]+) is now level \d+!$')
info_title = re.compile(r'^Level \d+ (.+)$')

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
                    footer = e.footer.text
                    if title == 'A wild pokémon has appeared!' or title == 'A wild pokémon has appearedǃ':
                        await self.spawn(e, message)
                    elif title.startswith('Congratulations '):
                        await self.levelup(e, message)
                    elif footer.startswith('Selected Pokémon:'):
                        await self.info(e)
                    elif footer.startswith("You haven't caught") or footer.startswith("You've caught "):
                        await self.dex_entry(e, message)
                    elif title == 'Pokédex':
                        await self.dex_list(e, message)
                    else:
                        print('> unknown pokecord message')
                        print(f'> {e}\n title: {repr(title)}\n desc: {e.description}')
                        for f in e.fields:
                            print(f'>> {f.name}={f.value}')
                        print(f'i {e.image.url}')
                        print('---')
                        print(e.to_dict())
            elif catch_msg.match(message.content):
                await self.catch(message)
            else:
                print('> no embed')
        elif message.channel.type == discord.ChannelType.private:
            # DMs.
            if re.match(r'^https://cdn.discordapp.com/attachments/.*/PokecordSpawn.jpg$', message.content):
                embed = discord.Embed().set_image(url=message.content)
                await self.spawn(embed, message)
        else:
            await self.bot.redis.set(f'pkmn:last:{message.channel.id}:author', message.author.id)
            await self.bot.redis.set(f'pkmn:last:{message.channel.id}:content', message.content)


    @commands.Cog.listener()
    async def on_message_edit(self, _: discord.Message, after: discord.Message) -> None:
        if after.author.id == Pokecord_id:
            if after.embeds:
                for e in after.embeds:
                    footer = e.footer.text
                    if footer and footer.startswith('Selected Pokémon:'):
                        await self.info(e)


    async def levelup(self, embed: discord.Embed, message: discord.Message) -> None:
        if message.guild.me.permissions_in(message.channel).manage_messages:
            delete_after_delay(message)
        reg_level = lvlup_title.match(embed.title)
        if reg_level:
            name = reg_level.group(1)
            member = find_user(message.guild, name)
            if member is None:
                print(f"I don't know who {name} is!")
                return
            reg_desc = lvlup_desc.match(embed.description)
            if reg_desc is None:
                print('level up description malformed')
                return
            print(f'{member}->{reg_desc.group(1)}')
            with self.get_db() as db:
                entry = db.get_pokedex_entry(member.id, reg_desc.group(1))
                if not entry.caught:
                    entry.caught = True
                    entry.save()
            return
        print('unknown levelup:')
        print(f'> {embed}\n title: {repr(embed.title)}\n desc: {embed.description}')
        for f in embed.fields:
            print(f'>> {f.name}={f.value}')

    async def spawn(self, embed: discord.Embed, message: discord.Message) -> None:
        md5 = get_md5(embed.image.url)
        await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}', md5)
        with self.get_db() as db:
            pkmn = db.get_pokemon_image_by_hash(md5)

            if not pkmn.name:
                phash = get_phash(embed.image.url)
                pkmn = db.get_pokemon_image_by_phash(phash)

            if not pkmn.name:
                await message.channel.send("I don't know this pokemon")
            else:
                embed = discord.Embed()
                if message.guild:
                    for p in self.active_players(message.guild):
                        entry = db.get_pokedex_entry(p.id, pkmn.name)
                        embed.add_field(name=p.display_name, value=entry.checkmark(), inline=False)
                else:
                    entry = db.get_pokedex_entry(message.author.id, pkmn.name)
                    embed.add_field(name=message.author.display_name, value=entry.checkmark(), inline=False)
                if len(embed) == 0:
                    embed = None
                else:
                    if not pkmn.flavor:
                        embed.set_footer(text="I don't know what to say about this Pokémon.", icon_url='https://cdn.bulbagarden.net/upload/3/36/479Rotom-Pok%C3%A9dex.png')
                    else:
                        embed.set_footer(text=pkmn.flavor, icon_url='https://cdn.bulbagarden.net/upload/3/36/479Rotom-Pok%C3%A9dex.png')
                await message.channel.send(f'This is a `{pkmn.name}`!', embed=embed)

    async def catch(self, message: discord.Message) -> None:
        match = catch_msg.match(message.content)
        if match is None:
            return
        player_id = int(match.group(1))
        truename = match.group(2)
        print(f'Caught {truename}!')
        md5 = await self.bot.redis.get(f'pkmn:lastspawn:{message.channel.id}')
        with self.get_db() as db:
            img = db.get_pokemon_image_by_hash(md5)
            if not img.pokemon:
                img.pokemon = db.get_pokemon_by_name(truename)
                img.save()
                print(f'Learned that {md5} is {truename} from Catch')

            elif img.name != truename:
                print(f'Caught {truename}, expected {img.name}. Updating')
                img.pokemon = db.get_pokemon_by_name(truename)
                img.save()
                return
            entry = db.get_pokedex_entry(player_id, truename)
            entry.caught = True
            entry.save()

    async def info(self, embed: discord.Embed) -> None:
        md5 = get_md5(embed.image.url)
        with self.get_db() as db:
            img = db.get_pokemon_image_by_hash(md5)
            if not img.pokemon:

                m = info_title.match(embed.title)
                if m:
                    truename = m.group(1)
                    img.pokemon = db.get_pokemon_by_name(truename)
                    img.save()
                    print(f'Learned that {md5} is {truename} from Info')
                else:
                    print('?')

    async def dex_entry(self, embed: discord.Embed, message: discord.Message) -> None:
        # {'footer': {'text': "You haven't caught this pokémon yet."}, 'image': {'width': 0, 'url': 'https://i.imgur.com/xSpdWqw.png', 'proxy_url': 'https://images-ext-1.discordapp.net/external/E3mzrefqRsMhAICteywWJ1DD3LLh9G7_WSdaq5ESIUw/https/i.imgur.com/xSpdWqw.png', 'height': 0}, 'author': {'name': 'Professor Oak'}, 'fields': [{'value': '**HP:** 45\n**Attack:** 49\n**Defense:** 49\n**Sp. Atk:** 65\n**Sp. Def:** 65\n**Speed:** 45', 'name': 'Base Stats', 'inline': True}, {'value': '0.7m', 'name': 'Height:', 'inline': True}, {'value': '6.9kg', 'name': 'Weight:', 'inline': True}, {'value': 'Grass | Poison', 'name': 'Types:', 'inline': True}, {'value': 'Overgrow\n*Hidden: Chlorophyll*', 'name': 'Abilities:', 'inline': True}, {'value': '87.5% Male\n12.5% Female', 'name': 'Gender:', 'inline': True}], 'color': 6607716, 'type': 'rich', 'description': ':flag_de: Bisasam\n:flag_jp: Fushigidane/フシギダネ/Fushigidane\n:flag_fr: Bulbizarre', 'title': '#1 - Bulbasaur'}
        _, name = embed.title.split('-')
        name = name.strip()
        md5 = get_md5(embed.image.url)
        with self.get_db() as db:
            img = db.get_pokemon_image_by_hash(md5)
            if not img.pokemon:
                img.pokemon = db.get_pokemon_by_name(name)
                img.save()
                print(f'Learned that {md5} is {name} from Pokedex')

    async def dex_list(self, embed: discord.Embed, message: discord.Message) -> None:
        player_id = int(await self.bot.redis.get(f'pkmn:last:{message.channel.id}:author'))
        invokation: bytes = await self.bot.redis.get(f'pkmn:last:{message.channel.id}:content')
        words = invokation.split()
        if not words[0].endswith(b'dex'):
            return
        if len(words) == 1:
            dex_page = 1
        else:
            dex_page = int(words[1])

        with self.get_db() as db:
            player = db.get_player(player_id)
            p_name = str(self.bot.get_user(player_id))
            if player.name != p_name:
                player.name = p_name
                player.save()
            for f in embed.fields:
                truename = f.name.split('#')[0].strip()
                pkmn = db.get_pokemon_by_name(truename)
                if pkmn.dex_page != dex_page:
                    pkmn.dex_page = dex_page
                    pkmn.save()
                caught = '✅' in f.value
                entry = db.get_pokedex_entry(player_id, truename)
                if entry.caught != caught:
                    print(f'{p_name} >> {truename}={caught}')
                    entry.caught = caught
                    entry.save()

    def active_players(self, guild: discord.Guild) -> List[discord.Member]:
        db = self.get_db()
        players = []
        for m in guild.members:
            if m.status == discord.Status.online and db.check_player(m.id):
                players.append(m)
        return players


    def get_db(self) -> 'database.Database':
        return self.bot.get_cog('Database')

def find_user(guild: discord.Guild, name: str) -> discord.Member:
    for m in guild.members:
        if m.display_name == name:
            return m
    return None

def setup(bot: commands.Bot) -> None:
    bot.add_cog(Listener(bot))


def rationalize_characterset(text: str) -> str:
    chars = confusables.is_confusable(text, preferred_aliases=['latin', 'common'], greedy=True)
    if chars:
        for issue in chars:
            bad = issue['character']
            replacement = [c for c in issue['homoglyphs'] if categories.aliases_categories(c['c'])[0] == 'LATIN'][0]
            # print(f"{bad} ({issue['alias']}) -> {replacement['c']} ({replacement['n']})")
            text = text.replace(bad, replacement['c'])
    return text

def delete_after_delay(message: discord.Message) -> None:
    async def delete() -> None:
        await asyncio.sleep(3)
        await message.delete()
    asyncio.ensure_future(delete())


def get_md5(url: str) -> str:
    resp = requests.get(url)
    md5 = hashlib.md5(resp.content).hexdigest()
    filename = os.path.join('images', md5 + '.jpg')
    if not os.path.exists(filename):
        print(f'saving {filename}')
        with open(filename, 'wb') as fd:
            for chunk in resp.iter_content(chunk_size=128):
                fd.write(chunk)
    return md5


def get_phash(url: str) -> str:
    resp = requests.get(url)
    md5 = hashlib.md5(resp.content).hexdigest()
    filename = os.path.join('images', md5 + '.jpg')
    if not os.path.exists(filename):
        print(f'saving {filename}')
        with open(filename, 'wb') as fd:
            for chunk in resp.iter_content(chunk_size=128):
                fd.write(chunk)
    with PIL.Image.open(filename) as image:
        phash = str(imagehash.phash(image))
    return phash
