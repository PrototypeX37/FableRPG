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
import datetime

import discord
from discord import Embed

from discord.ext import commands

from cogs.shard_communication import next_day_cooldown
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils import random, checks
from utils.checks import has_char, is_gm
from utils.i18n import _, locale_doc

rewards = {
    1: {"crates": 0, "puzzle": False, "money": 10000},
    2: {"crates": 0, "puzzle": True, "money": 0},
    3: {"crates": 0, "puzzle": False, "money": 15000},
    4: {"crates": 1, "puzzle": False, "money": 0},
    5: {"crates": 0, "puzzle": False, "money": 8000},
    6: {"crates": 0, "puzzle": True, "money": 0},
    7: {"crates": 1, "puzzle": False, "money": 0},
    8: {"crates": 0, "puzzle": False, "money": 10000},
    9: {"crates": 0, "puzzle": False, "money": 15000},
    10: {"crates": 1, "puzzle": False, "money": 0},
    11: {"crates": 0, "puzzle": False, "money": 16000},
    12: {"crates": 0, "puzzle": False, "money": 19000},
    13: {"crates": 0, "puzzle": True, "money": 0},
    14: {"crates": 1, "puzzle": False, "money": 0},
    15: {"crates": 0, "puzzle": False, "money": 22000},
    16: {"crates": 0, "puzzle": False, "money": 25500},
    17: {"crates": 0, "puzzle": True, "money": 0},
    18: {"crates": 0, "puzzle": False, "money": 27000},
    19: {"crates": 1, "puzzle": False, "money": 0},
    20: {"crates": 0, "puzzle": True, "money": 0},
    21: {"crates": 1, "puzzle": False, "money": 0},
    22: {"crates": 0, "puzzle": False, "money": 29000},
    23: {"crates": 0, "puzzle": True, "money": 0},
    24: {"crates": 1, "puzzle": False, "money": 50000},
}


class Christmas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @locale_doc
    async def calendar(self, ctx):
        _("""Look at your Winter Calendar""")
        try:
            today = datetime.datetime.now().day
            if today > 25 or today < 1:
                return await ctx.send(_("No calendar to show!"))
            await ctx.send("Dodgy Calendar:")
            await ctx.send(file=discord.File("assets/calendar/24 days of Fable.webp"))
        except Exception as e:
            await ctx.send(f"Error {e}")

    @checks.has_char()
    @commands.group(aliases=["cs"], brief=_("Opens Special Christmas Shop"))
    @locale_doc
    async def xmasshop(self, ctx):
        """
        Dive into the spectral realm with our limited-time Spooky Season Shop.
        Unearth rare treasures using bones you've collected from various eerie events.
        """
        if ctx.invoked_subcommand is None:
            try:
                # Fetch the user's bone count
                snowflake_count = await self.get_snowflakes_count(ctx.author.id)

                # Create the embed with various enhancements
                embed = Embed(title=_("🎁 Christmas Shop 🎁"), color=0x034f20)  # Dark orange color

                embed.set_thumbnail(url="https://gcdnb.pbrd.co/images/4EBx2R0ltpIR.png")
                embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)

                items = [
                    ("<:F_uncommon:1139514875828252702> Uncommon Crate", 700),
                    ("<:F_rare:1139514880517484666> Rare Crate", 1300),
                    ("<:F_Magic:1139514865174720532> Magic Crate", 2000),
                    ("<:F_Legendary:1139514868400132116> Legendary Crate", 5700),
                    ("<:f_divine:1169412814612471869> Divine Crate", 8000),
                    ("🖼️ Seasonal Background", 1500),
                    ("🟡 Weapon Type Token", 2000),
                    ("🧩 Puzzle Piece", 2750),
                ]

                for idx, (name, cost) in enumerate(items, 1):
                    if ctx.author.id == 708435868842459169:
                        embed.add_field(name=f"{idx}:  {name}",
                                        value=_("Cost: {} Pee Snowcones <:f_snowflake:1183619497412804660>").format(
                                            cost, ""),
                                        inline=False)

                    else:
                        embed.add_field(name=f"{idx}:  {name}",
                                        value=_("Cost: {} Snowflakes <:f_snowflake:1183619497412804660>").format(cost,
                                                                                                                 ""),
                                        inline=False)

                if ctx.author.id == 708435868842459169:
                    embed.set_footer(
                        text=_("You have {} Pee Snowcones - $cs buy <ID> to buy.").format(snowflake_count),
                        icon_url="https://gcdnb.pbrd.co/images/Nnp2NQ4fPJ0h.png")
                else:
                    embed.set_footer(
                        text=_("You have {} Snowflakes - $cs buy <ID> to buy.").format(snowflake_count),
                        icon_url="https://gcdnb.pbrd.co/images/Nnp2NQ4fPJ0h.png")

                await ctx.send(embed=embed)

            except Exception as e:
                error_embed = Embed(title=_("🚫 An error occurred!"), description=_(
                    f"Oh no! The Grinch stole your command. Try again later or contact Santa for help. {e}"),
                                    color=0xff0000)  # Red color for errors
                await ctx.send(embed=error_embed)

    @xmasshop.command(name="buy")
    @user_cooldown(30)
    async def _buy(self, ctx, item: int, quantity: int = 1):
        _("""
        This subcommand allows the user to buy an item from the Spooky Shop.

        :param item_name: The name of the item the user wants to buy.
        :param quantity: The quantity of the item the user wants to buy. Defaults to 1.
        """)

        if item < 0 and item > 7:
            await ctx.send("Invalid choice")
            return

        record = await self.bot.pool.fetchrow(
            'SELECT snowflakes FROM profile WHERE "user"=$1;',
            ctx.author.id
        )
        if record:
            snowflakes_count = record['snowflakes']
        else:
            snowflakes_count = 0

        if item == 1:
            if snowflakes_count < 700:
                await ctx.send("You cannot afford this")
                return
            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 700 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET crates_uncommon = crates_uncommon + 1 WHERE "user"=$1;',
                ctx.author.id
            )
            await ctx.send("You have successfully purchased a <:F_uncommon:1139514875828252702> for 700 Snowflakes!")

        if item == 2:
            if snowflakes_count < 1300:
                await ctx.send("You cannot afford this")
                return

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 1300 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET crates_rare = crates_rare + 1 WHERE "user"=$1;',
                ctx.author.id
            )
            await ctx.send("You have successfully purchased a <:F_rare:1139514880517484666> for 1300 Snowflakes!")

        if item == 3:
            if snowflakes_count < 2000:
                await ctx.send("You cannot afford this")
                return

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 2000 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET crates_magic = crates_magic + 1 WHERE "user"=$1;',
                ctx.author.id
            )
            await ctx.send("You have successfully purchased a <:F_Magic:1139514865174720532> for 2000 Snowflakes!")

        if item == 4:
            if snowflakes_count < 5700:
                await ctx.send("You cannot afford this")
                return

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 5700 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET crates_legendary = crates_legendary + 1 WHERE "user"=$1;',
                ctx.author.id
            )
            await ctx.send("You have successfully purchased a <:F_Legendary:1139514868400132116> for 5700 Snowflakes!")

        if item == 6:
            if snowflakes_count < 1500:
                await ctx.send("You cannot afford this")
                return

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 1500 WHERE "user"=$1;',
                ctx.author.id
            )

            backgrounds = [
                "https://cdn.discordapp.com/attachments/1145483687568363692/1185805642729009152/Csbg.png",
            ]
            async with self.bot.pool.acquire() as conn:
                background = random.choice(backgrounds)
                current_backgrounds = await conn.fetchval(
                    'SELECT "backgrounds" FROM profile WHERE "user"=$1;', ctx.author.id
                )
                if current_backgrounds is None or background not in current_backgrounds:
                    await conn.execute(
                        'UPDATE profile SET "backgrounds"=array_append("backgrounds", $1) WHERE "user"=$2;',
                        background,
                        ctx.author.id,
                    )

            await ctx.send("You have successfully purchased a Seasonal Background for 1500 Snowflakes!")
            await ctx.send("You can find it in $eventbackgrounds")

        if item == 5:
            if snowflakes_count < 8000:
                await ctx.send("You cannot afford this")
                return

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 8000 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET crates_divine = crates_divine + 1 WHERE "user"=$1;',
                ctx.author.id
            )
            await ctx.send("You have successfully purchased the a Divine crate for 8000 Snowflakes!")

        if item == 7:
            if snowflakes_count < 2000:
                await ctx.send("You cannot afford this")
                return

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 2000 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET weapontoken = weapontoken + 1 WHERE "user"=$1;',
                ctx.author.id
            )
            await ctx.send("You have successfully purchased a Weapon Type token for 2000 Snowflakes!")

        if item == 8:
            if snowflakes_count < 2750:
                await ctx.send("You cannot afford this")
                return
            await self.bot.pool.execute(
                'UPDATE profile SET puzzles = puzzles + 1 WHERE "user"=$1;',
                ctx.author.id
            )

            await self.bot.pool.execute(
                'UPDATE profile SET snowflakes = snowflakes - 2750 WHERE "user"=$1;',
                ctx.author.id
            )

            await ctx.send("You have successfully purchased a Puzzle piece for 2750 Snowflakes!")

    async def get_snowflakes_count(self, user_id):
        """Get the user's bone count from the database."""
        record = await self.bot.pool.fetchrow(
            'SELECT snowflakes FROM profile WHERE "user"=$1;',
            user_id
        )
        if record:
            return record['snowflakes']
        return 0

    @has_char()
    @commands.command(brief=_("Show some adventure stats"))
    @locale_doc
    async def snowflakes(self, ctx):
        _("""Displays the current amount of snowflakes you have.""")
        try:
            select_query = 'SELECT "snowflakes" FROM profile WHERE "user"=$1'

            # Assuming ctx.author.id is defined elsewhere
            author_id = ctx.author.id

            # Fetch the current value
            current_snowflakes = await self.bot.pool.fetchval(select_query, author_id)

            message = f"You currently have **{current_snowflakes}** snowflakes!"
            await ctx.send(message)
        except Exception as e:
            await ctx.send(f"{e}")

    @has_char()
    @next_day_cooldown()  # truly make sure they use it once a day
    @calendar.command(name="open")
    @locale_doc
    async def _open(self, ctx):
        _("""Open the Winter Calendar once every day.""")
        today = datetime.datetime.utcnow().date()
        christmas_too_late = datetime.date(2023, 12, 25)
        first_dec = datetime.date(2023, 12, 1)
        if today >= christmas_too_late or today < first_dec:
            return await ctx.send(_("It's not calendar time yet..."))
        reward = rewards[today.day]
        reward_text = _("**You opened day {today}!**").format(today=today.day)
        async with self.bot.pool.acquire() as conn:
            if reward["puzzle"]:
                await conn.execute(
                    'UPDATE profile SET "puzzles"="puzzles"+1 WHERE "user"=$1;',
                    ctx.author.id,
                )
                text = _("A mysterious puzzle piece")
                reward_text = f"{reward_text}\n- {text}"
            if reward["crates"]:
                rarity = random.choice(
                    ["legendary"]
                    + ["magic"] * 2
                    + ["rare"] * 5
                    + ["uncommon"] * 10
                    + ["common"] * 20
                )
                await conn.execute(
                    'UPDATE profile SET "crates_{rarity}"="crates_{rarity}"+$1 WHERE "user"=$2;',
                    reward["crates"],
                    ctx.author.id,
                )

                await self.bot.log_transaction(
                    ctx,
                    from_=1,
                    to=ctx.author.id,
                    subject="crates opened",
                    data={"Rarity": rarity, "Amount": reward["crates"]},
                    conn=conn,
                )
                text = _("{crates} {rarity} crate").format(
                    crates=reward["crates"], rarity=rarity
                )
                reward_text = f"{reward_text}\n- {text}"
            if reward["money"]:
                await conn.execute(
                    'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                    reward["money"],
                    ctx.author.id,
                )
                await self.bot.log_transaction(
                    ctx,
                    from_=1,
                    to=ctx.author.id,
                    subject="wintersday money",
                    data={"Gold": reward["money"]},
                    conn=conn,
                )
                reward_text = f"{reward_text}\n- ${reward['money']}"
        await ctx.send(reward_text)

    @has_char()
    @commands.command()
    @locale_doc
    async def combine(self, ctx):

        _("""Combine the mysterious puzzle pieces.""")
        if ctx.character_data["puzzles"] < 6:
            return await ctx.send(
                _(
                    "The mysterious puzzles don't fit together... Maybe some are"
                    " missing?"
                )
            )
        await self.bot.pool.fetchval(
            'UPDATE profile SET "chrissy2023"=true, "puzzles"=0 WHERE "user"=$1 RETURNING "chrissy2023";',
            ctx.author.id
        )

        await ctx.send(
            _(
                "Congratulations on solving the holiday puzzles! A jolly voice in your mind cheers: *Well done, festive friend!* "
                "Now, embrace the holiday spirit and unlock a special event class with `$class`. Experience the magic of Christmas in a whole new way! "
                "Spread joy and merriment throughout your journey. Happy holidays <3!"

            ).format(prefix=ctx.clean_prefix)
        )

    @has_char()
    @is_gm()
    @commands.command()
    @locale_doc
    async def fixpuzzle(self, ctx, target: discord.Member):

        try:

            await self.bot.pool.fetchval(
                'UPDATE profile SET "puzzles"=6 WHERE "user"=$1;',
                target.id
            )

            await ctx.send(
                _(
                    "All fixed up! :)"

                ).format(prefix=ctx.clean_prefix)
            )
        except Exception as e:
            await ctx.send(f"{e}")


async def setup(bot):
    await bot.add_cog(Christmas(bot))
