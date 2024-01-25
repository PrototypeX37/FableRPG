"""
The IdleRPG Discord Bot
Copyright (C) 2018-2021 Diniboy and Gelbpunkt

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from collections import defaultdict, deque
from functools import partial

import aiohttp

import discord

from discord.ext import commands

from classes.converters import ImageFormat, ImageUrl
from cogs.help import chunks
from cogs.shard_communication import next_day_cooldown
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils import random
from utils.checks import ImgurUploadError, has_char, user_is_patron, is_gm
from utils.i18n import _, locale_doc


class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.talk_context = defaultdict(partial(deque, maxlen=3))
        self.conversations = {}
        self.ALLOWED_CHANNELS = {
            1199300115672870983
        }

    async def get_imgur_url(self, url: str):
        async with self.bot.session.post(
                "https://api.imgur.com/3/image",
                headers={
                    "Authorization": f"Client-ID {self.bot.config.external.imgur_token}"
                },
                json={"image": url, "type": "url"},
        ) as r:
            json = await r.json()
            try:
                short_url = json["data"]["link"]
            except KeyError:
                raise ImgurUploadError()
        return short_url

    @has_char()
    @next_day_cooldown()
    @commands.command(brief=_("Get your daily reward"))
    @locale_doc
    async def daily(self, ctx):
        _(
            """Get your daily reward. Depending on your streak, you will gain better rewards.

            After ten days, your rewards will reset. Day 11 and day 1 have the same rewards.
            The rewards will either be money (2/3 chance) or crates (1/3 chance).

            The possible rewards are:

              __Day 1__
              $50 or 1-6 common crates

              __Day 2__
              $100 or 1-5 common crates

              __Day 3__
              $200 or 1-4 common (99%) or uncommon (1%) crates

              __Day 4__
              $400 or 1-4 common (99%) or uncommon (1%) crates

              __Day 5__
              $800 or 1-4 common (99%) or uncommon (1%) crates

              __Day 6__
              $1,600 or 1-3 common (80%), uncommon (19%) or rare (1%) crates

              __Day 7__
              $3,200 or 1-2 uncommon (80%), rare (19%) or magic (1%) crates

              __Day 8__
              $6,400 or 1-2 uncommon (80%), rare (19%) or magic (1%) crates

              __Day 9__
              $12,800 or 1-2 uncommon (80%), rare (19%) or magic (1%) crates

              __Day 10__
              $25,600 or 1 rare (80%), magic (19%) or legendary (1%) crate

            If you don't use this command up to 48 hours after the first use, you will lose your streak.

            (This command has a cooldown until 12am UTC.)"""
        )
        streak = await self.bot.redis.execute_command(
            "INCR", f"idle:daily:{ctx.author.id}"
        )
        await self.bot.redis.execute_command(
            "EXPIRE", f"idle:daily:{ctx.author.id}", 48 * 60 * 60
        )  # 48h: after 2 days, they missed it
        money = 2 ** ((streak + 9) % 10) * 50
        # Either money or crates
        if random.randint(0, 2) > 0:
            money = 2 ** ((streak + 9) % 10) * 50
            # Silver = 1.5x
            if await user_is_patron(self.bot, ctx.author, "silver"):
                money = round(money * 1.5)

            result = await self.bot.pool.fetchval('SELECT tier FROM profile WHERE "user" = $1;', ctx.author.id)

            if result >= 3:
                money = round(money * 3)

            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                    money,
                    ctx.author.id,
                )

                await self.bot.log_transaction(
                    ctx,
                    from_=1,
                    to=ctx.author.id,
                    subject="daily",
                    data={"Gold": money},
                    conn=conn,
                )
            txt = f"**${money}**"
        else:
            num = round(((streak + 9) % 10 + 1) / 2)
            amt = random.randint(1, 6 - num)
            types = [
                "common",
                "uncommon",
                "rare",
                "magic",
                "legendary",
                "common",
                "common",
                "common",
            ]  # Trick for -1
            type_ = random.choice(
                [types[num - 3]] * 80 + [types[num - 2]] * 19 + [types[num - 1]] * 1
            )
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    f'UPDATE profile SET "crates_{type_}"="crates_{type_}"+$1 WHERE'
                    ' "user"=$2;',
                    amt,
                    ctx.author.id,
                )
                await self.bot.log_transaction(
                    ctx,
                    from_=1,
                    to=ctx.author.id,
                    subject="crates",
                    data={"Rarity": type_, "Amount": amt},
                    conn=conn,
                )
            txt = f"**{amt}** {getattr(self.bot.cogs['Crates'].emotes, type_)}"

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE profile SET "freeimage"=$1 WHERE "user"=$2;',
                3,
                ctx.author.id,
            )

        await ctx.send(
            _(
                "You received your daily {txt} and 3 free images!\nYou are on a streak of **{streak}**"
                " days!\n*Tip: `{prefix}vote` every 12 hours to get an up to legendary"
                " crate with possibly rare items!*"
            ).format(txt=txt, money=money, streak=streak, prefix=ctx.clean_prefix)
        )

    @has_char()
    @commands.command(brief=_("View your current streak"))
    @locale_doc
    async def streak(self, ctx):
        _(
            """Want to flex your streak on someone or just check how many days in a row you've claimed your daily reward? This command is for you"""
        )
        streak = await self.bot.redis.execute_command(
            "GET", f"idle:daily:{ctx.author.id}"
        )
        if not streak:
            return await ctx.send(
                _(
                    "You don't have a daily streak yet. You can get one going by using"
                    " the command `{prefix}daily`!"
                ).format(prefix=ctx.clean_prefix)
            )
        await ctx.send(
            _("You are on a daily streak of **{streak}!**").format(
                streak=streak.decode()
            )
        )

    @commands.command(aliases=["shorten"], brief=_("Shorten an image URL."))
    @locale_doc
    async def imgur(self, ctx, given_url: ImageUrl(ImageFormat.all) = None):
        _(
            """`[given_url]` - The URL to shorten; if not given, this command will look for image attachments

            Get a short URL from a long one or an image attachment.

            If both a URL and an attachment is given, the attachment is preferred. GIFs are not supported, only JPG and PNG.
            In case this command fails, you can [manually upload your image to Imgur](https://imgur.com/upload)."""
        )
        if not given_url and not ctx.message.attachments:
            return await ctx.send(_("Please supply a URL or an image attachment"))
        if ctx.message.attachments:
            if len(ctx.message.attachments) > 1:
                return await ctx.send(_("Please only use one image at a time."))
            given_url = await ImageUrl(ImageFormat.all).convert(
                ctx, ctx.message.attachments[0].url
            )

        link = await self.get_imgur_url(given_url)
        await ctx.send(_("Here's your short image URL: <{link}>").format(link=link))

    @commands.command(aliases=["donate"], brief=_("Support the bot financially"))
    @locale_doc
    async def patreon(self, ctx):
        _(
            """View the Patreon page of the bot. The different tiers will grant different rewards.
            View `{prefix}help module Patreon` to find the different commands.

            Thank you for supporting Fable RPG!"""
        )
        guild_count = sum(
            await self.bot.cogs["Sharding"].handler(
                "guild_count", self.bot.cluster_count
            )
        )
        await ctx.send(
            _(
                """\
This bot has its own patreon page.

**Why should I donate?**
This bot is currently on {guild_count} servers, and it is growing fast.
Hosting this bot for all users is not easy and costs a lot of money.
If you want to continue using the bot or just help us, please donate a small amount.
Even $1 can help us.
**Thank you!**

<https://patreon.com/FableRPG>"""
            ).format(guild_count=guild_count)
        )

    @commands.command(
        aliases=["license"], brief=_("Shows the source code and license.")
    )
    @locale_doc
    async def source(self, ctx):
        _(
            """Shows Idles GitLab page and license alongside our own source as required by AGPLv3 Licensing."""
        )
        await ctx.send("IdleRPG - AGPLv3+\nhttps://git.travitia.xyz/Kenvyra/IdleRPG")

        await ctx.send("Fable - AGPLv3+\nhttps://github.com/PrototypeX37/IdleRPG-FRPG")

    @commands.command(brief=_("Invite the bot to your server."))
    @locale_doc
    async def invite(self, ctx):
        _(
            """Invite the bot to your server.

            Use this https://discord.com/api/oauth2/authorize?client_id=1136590782183264308&permissions
            =8945276537921&scope=bot"""
        )
        await ctx.send(
            _(
                "You are running version **{version}** by The Fable"
                "Developers.\nInvite me! https://discord.com/api/oauth2/authorize?client_id=1136590782183264308"
                "&permissions=8945276537921&scope=bot"
            ).format(version=self.bot.version)
        )

    @commands.command(brief=_("View the uptime"))
    @locale_doc
    async def uptime(self, ctx):
        _("""Shows how long the bot has been connected to Discord.""")
        await ctx.send(
            _("I am online for **{time}**.").format(
                time=str(self.bot.uptime).split(".")[0]
            )
        )

    @commands.command()
    @has_char()
    async def credits(self, ctx):
        credits = ctx.character_data["imagecredits"]
        freecredits = ctx.character_data["freeimage"]
        return await ctx.send(f"You have **{freecredits}** free images left and a balance of **${credits}**.")

    @commands.command(name='talk', help='Ask ChatGPT a question!')
    async def talk(self, ctx, *, question):
        # Check if the command is invoked in one of the allowed channels
        if ctx.author.id != 598004694060892183:
            if ctx.author.id != 295173706496475136:
                if ctx.channel.id not in self.ALLOWED_CHANNELS:
                    await ctx.send("This command can only be used in specific channels!")
                    return

        user_id = ctx.author.id

        # Add the user's new message to their conversation history
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        # Fetch the response from GPT-3 using the entire conversation as context
        response = await self.get_gpt_response_async(self.conversations[user_id] + [{"role": "user", "content": question}])

        # Append the user message and response to the conversation
        self.conversations[user_id].extend([
            {"role": "user", "content": question},
            {"role": "system", "content": response}
        ])

        # Ensure the conversation doesn't exceed 100 messages
        while len(self.conversations[user_id]) > 25:
            self.conversations[user_id].pop(0)  # remove the oldest message

        # Split and send the response back to the user
        for chunk in self.split_message(response):
            await ctx.send(chunk)

    from discord.ext import commands

    class YourCogName(commands.Cog):
        def __init__(self, bot):
            self.bot = bot

    @commands.command()
    async def cookie(self, ctx, target_member: discord.Member):
        await ctx.send(
            f"**{target_member.display_name}**, you've been given a cookie by **{ctx.author.display_name}**. 🍪")

    @commands.command()
    async def ice(self, ctx, target_member: discord.Member):
        await ctx.send(
            f"{target_member.mention}, here is your ice: 🍨!")

    @commands.command(name='wipe', help='Clear your conversation history with the bot.')
    async def clear_memory(self, ctx):
        user_id = ctx.author.id
        if user_id in self.conversations:
            del self.conversations[user_id]
            await ctx.send("Your conversation history has been cleared!")
        else:
            await ctx.send("You don't have any conversation history to clear.")

    def split_message(self, content, limit=1909):
        """Split a message into chunks under a specified limit without breaking words."""
        chunks = []
        while len(content) > limit:
            split_index = content.rfind(' ', 0, limit)
            if split_index == -1:
                split_index = limit
            chunk = content[:split_index]
            chunks.append(chunk)
            content = content[split_index:].strip()  # Remove leading space for next chunk
        chunks.append(content)
        return chunks

    async def get_gpt_response_async(self, conversation_history):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer Token",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4-1106-preview",
            "messages": conversation_history
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response_data = await response.json()
                    return response_data['choices'][0]['message']['content'].strip()
        except aiohttp.ClientError as e:
            return f"Error connecting to OpenAI: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}! Try using $wipe."

    @commands.command(brief=_("Our partnered bots"))
    @locale_doc
    async def partners(self, ctx):
        _("""Awesome bots by other coffee-drinking individuals.""")
        em = discord.Embed(
            title=_("Partnered Bots"),
            description=_("Awesome bots made by other people!"),
            colour=discord.Colour.blurple(),
        )
        em.add_field(
            name="GamesROB",
            value=_(
                "Trivia, Hangman, Minesweeper, Connect 4 and more, right from your"
                " chat! A bot offering non-RPG games made by deprilula28 and"
                " Fin.\n[top.gg Page](https://top.gg/bot/gamesrob)"
            ),
        )
        em.add_field(
            name="Cautious Memory",
            value=_(
                "Cautious Memory brings wiki-style pages to your server. Use it to"
                " document who's who in your server, inside jokes, or community lore."
                " Includes a full featured permissions system to keep your pages"
                " squeaky clean.\n[top.gg Page](https://top.gg/bot/541707781665718302)"
            ),
        )
        em.add_field(
            name="Cleverbot",
            value=_(
                "Cleverbot is a Discord bot that will chat with you and your"
                " friends.\n[top.gg Page](https://top.gg/bot/508012980194115595)"
            ),
        )
        await ctx.send(embed=em)

    @commands.command(brief=_("Search wikipedia"))
    @locale_doc
    async def wikipedia(self, ctx, *, query: str):
        _(
            """`<query>` - The wikipedia query to search for

            Searches Wikipedia for an entry."""
        )
        try:
            page = (await self.bot.wikipedia.opensearch(query))[0]
            text = await page.summary()
        except (aiowiki.exceptions.PageNotFound, IndexError):
            return await ctx.send(_("No wikipedia entry found."))
        if not text:
            return await ctx.send(_("Could not parse article summary."))
        p = commands.Paginator()
        for line in text.split("\n"):
            for i in chunks(line, 1900):
                p.add_line(i)
        await self.bot.paginator.Paginator(
            title=page.title, entries=p.pages, length=1
        ).paginate(ctx)

    @commands.command(aliases=["wiki"], brief=_("Search the Idle Wiki"))
    @locale_doc
    async def idlewiki(self, ctx, *, query: str = None):
        _(
            """`[query]` - The idlewiki query to search for

            Searches Idle's wiki for an entry."""
        )
        if not query:
            return await ctx.send(
                _(
                    "Check out the official IdleRPG Wiki"
                    " here:\n<https://wiki.idlerpg.xyz/index.php?title=Main_Page>"
                )
            )
        try:
            page = (await self.bot.idlewiki.opensearch(query))[0]
            text = await page.summary()
        except (aiowiki.exceptions.PageNotFound, IndexError):
            return await ctx.send(_("No entry found."))
        else:
            if not text:
                return await ctx.send(_("No content to display."))
        p = commands.Paginator()
        for line in text.split("\n"):
            for i in chunks(line, 1900):
                p.add_line(i)
        await self.bot.paginator.Paginator(
            title=page.title, entries=p.pages, length=1
        ).paginate(ctx)

    @commands.command(
        aliases=["pages", "about"], brief=_("Info about the bot and related sites")
    )
    @locale_doc
    async def web(self, ctx):
        _("""About the bot and our websites.""")
        await ctx.send(
            _(
                # xgettext: no-python-format
                """\
**IdleRPG** is Discord's most advanced medieval RPG bot.
We aim to provide the perfect experience at RPG in Discord with minimum effort for the user.

We are not collecting any data apart from your character information and our transaction logs.
The bot is 100% free to use and open source.
This bot is developed by people who love to code for a good cause and improving your gameplay experience.

**Links**
<https://git.travitia.xyz/Kenvyra/IdleRPG> - Source Code
<https://git.travitia.xyz> - GitLab (Public)
<https://idlerpg.xyz> - Bot Website
<https://wiki.idlerpg.xyz> - IdleRPG wiki
<https://travitia.xyz> - IdleRPG's next major upgrade
<https://idlerpg.xyz> - Our forums
<https://public-api.travitia.xyz> - Our public API
<https://cloud.idlerpg.xyz> - VPS hosting by IdleRPG
<https://github.com/Kenvyra> - Other IdleRPG related code
<https://discord.com/terms> - Discord's ToS
<https://www.ncpgambling.org/help-treatment/national-helpline-1-800-522-4700/> - Gambling Helpline"""
            )
        )

    @commands.command(brief=_("Show the rules again"))
    @locale_doc
    async def rules(self, ctx):
        _(
            """Shows the rules you consent to when creating a character. Don't forget them!"""
        )
        await ctx.send(
            _(
                """\
1) Only up to two characters per individual
2) No abusing or benefiting from bugs or exploits
3) Be friendly and kind to other players
4) Trading in-game content for anything outside of the game is prohibited
5) Giving or selling renamed items is forbidden

IdleRPG is a global bot, your characters are valid everywhere"""
            )
        )


async def setup(bot):
    await bot.add_cog(Miscellaneous(bot))
