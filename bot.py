"""
Creates cache, and sets up all the variables and runs the bot.
Copyright (C) 2021 ppotatoo

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import collections
import datetime
import json
import os
import re
import time

import aiohttp
import alexflipnote
import asyncpg
import config
import discord
from discord.ext import commands

from cogs.useful import ChuckContext
from utils.default import Blacklisted, Maintenance


class Chuck(commands.Bot):
    """Subclassed Bot."""

    def __init__(self):
        self.bot = None
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=self.get_prefix,
            case_insensitive=True,
            intents=intents,
            owner_ids={809587169520910346},
            description="Walrus is a simple and easy-to-use Discord bot"
        )
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()
        self.author_id = 809587169520910346
        self.session = aiohttp.ClientSession()
        self.embed_color = 0x89CFF0  # discord.Color.green()  # 0x9c5cb4
        self.prefixes = collections.defaultdict(list)
        self.command_list = []
        self.deleted_messages = collections.defaultdict(list)
        self.default_prefix = 'p!'
        self.config = config
        self.support_invite = "https://discord.gg/NTNgvHkjSp"
        self.invite = "https://discord.com/oauth2/authorize?client_id=810570659968057384&scope=bot&permissions=70646849"
        self.alex = alexflipnote.Client(self.get_config('alex_api_key'))
        self.timetime = time.time()
        self.case_insensitive = True
        self.perspective = self.get_config("perspective_key")
        self.afk = {}
        self.highlights = {}
        self.usage_counter = 0
        self.command_usage = collections.Counter()
        self.maintenance = False

    @staticmethod
    def get_config(item: str):
        """Gets an item from the config."""
        with open('config.json', 'r') as f:
            f = json.load(f)
        return f[item]

    async def get_prefix(self, message):
        """Function for getting the command prefix."""
        if message.guild is None:
            return commands.when_mentioned_or(self.default_prefix)(self, message)
        if self.prefixes[message.guild.id]:
            return commands.when_mentioned_or(*self.prefixes[message.guild.id])(self, message)

        if not self.prefixes[message.guild.id]:
            await self.db.execute("INSERT INTO prefixes(guild_id,prefix) VALUES($1,$2)", message.guild.id,
                                  self.default_prefix)
            self.prefixes[message.guild.id].append(self.default_prefix)

            return commands.when_mentioned_or(*self.prefixes[message.guild.id])(self, message)
        return commands.when_mentioned_or(self.default_prefix)(self, message)

    async def try_user(self, user_id: int) -> discord.User:
        """Method to try and fetch a user from cache then fetch from API."""
        user = self.get_user(user_id)
        if not user:
            user = await self.fetch_user(user_id)
        return user

    def starter(self):
        """Runs the bot."""
        try:
            # dsn = os.environ['dsn'] or self.get_config('DSN')
            print("Connecting to database ...")
            pool_pg = self.loop.run_until_complete(asyncpg.create_pool(dsn=self.get_config('DSN')))
            print("Connected to PostgreSQL server!")
        except Exception as e:
            print("Could not connect to database:", e)
        else:
            print("Connecting to Discord ...")
            self.uptime = datetime.datetime.utcnow()
            self.db = pool_pg

            for file in os.listdir("cogs"):
                if not file.startswith("_"):
                    self.load_extension(f'cogs.{file[:-3]}')
            self.load_extension("jishaku")
            self.create_command_list()

            self.run(self.get_config('token'))

    async def create_tables(self):
        """Creates the needed SQL tables for this bot."""
        await self.wait_until_ready()
        with open("tables.sql") as f:
            await self.db.execute(f.read())

    async def create_cache(self):
        await self.wait_until_ready()
        self.mention_match = re.compile(fr"^(<@!?{self.user.id}>)\s*")
        for guild in self.guilds:
            await self.db.execute("INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
                                  guild.id)
        guilds = await self.db.fetch("SELECT * FROM prefixes")
        for guild in guilds:
            self.prefixes[guild['guild_id']].append(guild['prefix'])
        blacklist = await self.db.fetch('SELECT user_id, reason FROM blacklist')
        self.blacklist = dict(blacklist)


    def create_command_list(self):
        for command in self.commands:
            self.command_list.append(str(command))
            self.command_list.extend(list(command.aliases))
            if isinstance(command, commands.Group):
                self.command_list.extend(self.get_subcommands(command))

    def get_subcommands(self, command):
        gotten_subcommands = []
        for command in command.commands:
            gotten_subcommands.append(str(command))
            gotten_subcommands.extend([f"{command} {alias}" for alias in command.aliases])
            if isinstance(command, commands.Group):
                gotten_subcommands.extend(self.get_subcommands(command))
        return gotten_subcommands

    def check_owner(self, user: discord.User):
        return user.id in self.owner_ids

    async def close(self):
        await self.alex.close()
        await self.session.close()
        await self.db.close()
        await super().close()

    async def get_context(self, message: discord.Message, *, cls=None):
        """Method to override "ctx"."""
        return await super().get_context(message, cls=cls or ChuckContext)

    # https://github.com/InterStella0/stella_bot/blob/4636627b2f99b7f58260869f020e5adebb62e27d/main.py
    async def process_commands(self, message):
        """Override process_commands to call typing every invoke"""
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        if ctx.valid:
            await ctx.trigger_typing()
        await self.invoke(ctx)

    async def on_message(self, message: discord.Message):
        """Checking if someone pings the bot."""
        perms = message.channel.permissions_for(message.guild.me).send_messages + message.channel.permissions_for(
            message.guild.me).embed_links if message.guild else 2
        if message.author.bot or not self.is_ready() or perms != 2:
            return
        if self.mention_match.fullmatch(message.content):
            if self.prefixes[message.guild.id]:
                server_prefix = bot.prefixes[message.guild.id]
            else:
                await self.db.execute("INSERT INTO prefixes(guild_id,prefix) VALUES($1,$2)", message.guild.id,
                                      self.default_prefix)
                server_prefix = self.default_prefix
            await message.channel.send(
                "My prefixes on `{}` are \n[ `{}` ]".format(message.guild.name, "` | `".join(server_prefix)))
        await self.process_commands(message)

    async def on_message_edit(self, before, after):
        """Check on command edit so that you don't have to retype your command."""
        if before.author.id in self.owner_ids and not before.embeds and not after.embeds:
            await self.process_commands(after)


bot = Chuck()
bot.loop.create_task(bot.create_tables())
bot.loop.create_task(bot.create_cache())

os.environ['JISHAKU_NO_UNDERSCORE'] = 'True'
os.environ['JISHAKU_NO_DM_TRACEBACK'] = 'True'
os.environ['JISHAKU_HIDE'] = 'True'
os.environ["NO_COLOR"] = 'True'

bot.loop.set_debug(True)


@bot.event
async def on_ready():
    """Lets you know that the bot has run."""
    print(f'{bot.user} has connected to Discord!\n'
          f'Guilds: {len(bot.guilds)}\n'
          f'Members: {str(sum([guild.member_count for guild in bot.guilds]))}')


@bot.check
async def is_maintenance(ctx):
    if bot.maintenance and not bot.check_owner(ctx.author):
        raise Maintenance()
    return True


@bot.check
async def is_blacklisted(ctx):
    if ctx.author.id in bot.blacklist:
        raise Blacklisted()
    return True


if __name__ == "__main__":
    bot.starter()
