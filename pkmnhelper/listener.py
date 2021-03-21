import asyncio
from pkmnhelper import ai
from helpers.hashing import EmbedImage
import os
import re
from typing import TYPE_CHECKING, List, Optional

from helpers import hashing
import discord
from confusable_homoglyphs import categories, confusables
from discord.ext import commands

if TYPE_CHECKING:
    import database

Pokecord_id = [716390085896962058, 743761282108227584]

catch_msg = re.compile(r'Congratulations <@!?([0-9]+)>! You caught a level \d+ ([\w ]+)!')
lvlup_title = re.compile(r'^Congratulations ([\w ]+)!$')
lvlup_desc = re.compile(r'^Your ([\w ]+) is now level \d+!$')
info_title = re.compile(r'^Level \d+ (.+)$')

class Listener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_result = None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot and message.author.id not in Pokecord_id and message.embeds and message.embeds[0].title == 'A wild pokémon has appeared!':
            # Detect devenv instances
            print(f'Identified {message.author} as Pokecord')
            Pokecord_id.append(message.author.id)

        if message.author.id in Pokecord_id:
            print(f'pokecord message: {message}')
            print(f'"{message.content}"')
            if message.embeds:
                for e in message.embeds:
                    title = e.title or ''
                    title = title.strip('\u200c')
                    title = rationalize_characterset(title) # They're using homographs on us
                    footer = e.footer.text
                    if title == 'A wild pokémon has appeared!' or title == 'A wild pokémon has appearedǃ':
                        await self.spawn(e, message)
                    elif title.startswith("Wild ") and title.endswith("fled. A new wild pokémon has appeared!"):
                        # todo: Maybe learn from misses?
                        await self.spawn(e, message)
                    elif title.startswith('Congratulations '):
                        await self.levelup(e, message)
                    elif footer and footer.startswith('Displaying pokémon '):
                        await self.info(e)
                    elif footer.startswith("You haven't caught") or footer.startswith("You've caught "):
                        await self.dex_entry(e)
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
            elif message.content == 'Your account has been suspended.':
                await message.guild.leave()
            else:
                print('> no embed')
        elif re.match(r'^https://cdn.discordapp.com/attachments/.*/pokemon.png$', message.content):
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


    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        offline = [discord.Status.offline, discord.Status.dnd, discord.Status.idle, discord.Status.do_not_disturb]
        online = discord.Status.online
        if before.status in offline:
            if after.status == online:
                for channel in after.guild.text_channels:
                    await self.update_last_message(after, channel)

    @commands.Cog.listener()
    async def on_typing(self, channel: discord.TextChannel, user: discord.User, _: int) -> None:
        await self.update_last_message(user, channel)

    async def update_last_message(self, user: discord.User, channel: discord.TextChannel) -> None:
        rid = await self.bot.redis.get(f'pkmn:lastspawn:{channel.id}:response')
        if rid is None:
            return
        response: discord.Message = discord.utils.get(self.bot.cached_messages, id=int(rid))
        with self.get_db() as db:
            if response and response.embeds and db.check_player(user.id):
                name = await self.bot.redis.get(f'pkmn:lastspawn:{channel.id}:name')
                if not name:
                    return

                entry = db.get_pokedex_entry(user.id, name)
                embed = response.embeds[0]
                for field in embed.fields:
                    if field.name == user.display_name:
                        return
                embed.add_field(name=user.display_name, value=entry.checkmark(), inline=False)
                await response.edit(embed=embed)

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
        img = hashing.EmbedImage(embed.image.url)

        await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}:md5', img.md5)
        with self.get_db() as db:
            prediction = ai.predict(img.filename)
            print(prediction)
            pkmn = db.get_pokemon_by_name(prediction)

            phash = img.phash
            await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}:phash', phash)
            if not pkmn:
                pkmn = db.get_pokemon_image_by_phash(phash)


            if not pkmn.name:
                response: discord.Message = await message.channel.send("I don't know this pokemon")
                await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}:response', response.id)
                await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}:name', '')
                await self.do_guess(img, response)

            else:
                active_players = self.active_players(message.guild)
                embed = self.generate_embed(message, active_players, pkmn)
                response = await message.channel.send(f'This is a `{pkmn.name}`!', embed=embed)

                await self.clean_last_message(message.channel)

                await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}:response', response.id)
                await self.bot.redis.set(f'pkmn:lastspawn:{message.channel.id}:name', pkmn.name)

    async def do_guess(self, img: hashing.EmbedImage, response: discord.Message) -> None:
        await response.edit(content=f'I think that might be a {img.get_closest().name}')


    async def catch(self, message: discord.Message) -> None:
        match = catch_msg.match(message.content)
        if match is None:
            return
        player_id = int(match.group(1))
        truename = match.group(2)
        print(f'Caught {truename}!')
        phash = await self.bot.redis.get(f'pkmn:lastspawn:{message.channel.id}:phash')
        with self.get_db() as db:
            img = db.get_pokemon_image_by_phash(phash)
            if not img.pokemon:
                img.pokemon = db.get_pokemon_by_name(truename)
                img.save()
                print(f'Learned that {phash} is {truename} from Catch')

            elif img.name != truename:
                print(f'Caught {truename}, expected {img.name}. Updating')
                img.pokemon = db.get_pokemon_by_name(truename)
                img.save()
                return
            entry = db.get_pokedex_entry(player_id, truename)
            entry.caught = True
            entry.save()
        await self.clean_last_message(message.channel)

    async def clean_last_message(self, channel: discord.TextChannel) -> None:
        rid = await self.bot.redis.get(f'pkmn:lastspawn:{channel.id}:response')
        if not rid:
            return
        response: discord.Message = discord.utils.get(self.bot.cached_messages, id=int(rid))
        if response:
            if response.embeds:
                embed: discord.Embed = response.embeds[0]
                for _ in embed.fields:
                    embed.remove_field(0)
                await response.edit(embed=embed)
            await self.bot.redis.delete(f'pkmn:lastspawn:{channel.id}:response')


    async def info(self, embed: discord.Embed) -> None:
        embedimage = EmbedImage(embed.image.url)
        md5 = embedimage.md5
        filename = os.path.splitext(os.path.basename(embed.image.url))[0]
        with self.get_db() as db:
            img = db.get_pokemon_image_by_hash(md5)
            if not img.pokemon:

                m = info_title.match(embed.title)
                if m:
                    truename = m.group(1)
                    img.pokemon = db.get_pokemon_by_name(truename)
                    try:
                        img.pokemon.dex_num = int(filename)
                    except TypeError:
                        print(f'{filename} is not an int')
                    img.save()
                    print(f'Learned that {md5} is {truename} from Info')
                else:
                    print('?')

    async def dex_entry(self, embed: discord.Embed) -> None:
        # {'footer': {'text': "You haven't caught this pokémon yet."}, 'image': {'width': 0, 'url': 'https://i.imgur.com/xSpdWqw.png', 'proxy_url': 'https://images-ext-1.discordapp.net/external/E3mzrefqRsMhAICteywWJ1DD3LLh9G7_WSdaq5ESIUw/https/i.imgur.com/xSpdWqw.png', 'height': 0}, 'author': {'name': 'Professor Oak'}, 'fields': [{'value': '**HP:** 45\n**Attack:** 49\n**Defense:** 49\n**Sp. Atk:** 65\n**Sp. Def:** 65\n**Speed:** 45', 'name': 'Base Stats', 'inline': True}, {'value': '0.7m', 'name': 'Height:', 'inline': True}, {'value': '6.9kg', 'name': 'Weight:', 'inline': True}, {'value': 'Grass | Poison', 'name': 'Types:', 'inline': True}, {'value': 'Overgrow\n*Hidden: Chlorophyll*', 'name': 'Abilities:', 'inline': True}, {'value': '87.5% Male\n12.5% Female', 'name': 'Gender:', 'inline': True}], 'color': 6607716, 'type': 'rich', 'description': ':flag_de: Bisasam\n:flag_jp: Fushigidane/フシギダネ/Fushigidane\n:flag_fr: Bulbizarre', 'title': '#1 - Bulbasaur'}
        _, name = embed.title.split('-')
        name = name.strip()
        embedimage = EmbedImage(embed.image.url)
        md5 = embedimage.md5

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

    def generate_embed(self, message: discord.Message, active_players: List[discord.User], pkmn: 'database.HashMixin') -> discord.Embed:
        if pkmn is None or pkmn.name is None:
            return None
        db = self.get_db()
        embed = discord.Embed()
        if message.guild:
            for p in active_players:
                entry = db.get_pokedex_entry(p.id, pkmn.name)
                embed.add_field(name=p.display_name, value=entry.checkmark(), inline=False)
        else:
            entry = db.get_pokedex_entry(message.author.id, pkmn.name)
            embed.add_field(name=message.author.display_name, value=entry.checkmark(), inline=False)
        if not pkmn.flavor:
            embed.set_footer(text="I don't know what to say about this Pokémon.", icon_url='https://cdn.bulbagarden.net/upload/3/36/479Rotom-Pok%C3%A9dex.png')
        else:
            embed.set_footer(text=pkmn.flavor, icon_url='https://cdn.bulbagarden.net/upload/3/36/479Rotom-Pok%C3%A9dex.png')
        return embed

    def active_players(self, guild: Optional[discord.Guild]) -> List[discord.Member]:
        if guild is None:
            return []
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
