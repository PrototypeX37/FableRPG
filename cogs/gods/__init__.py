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
from decimal import Decimal
from io import BytesIO

import discord

from discord.ext import commands

from classes.classes import Ritualist, from_string
from classes.converters import IntGreaterThan
from cogs.shard_communication import next_day_cooldown
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils import random
from utils.checks import has_char, has_god, has_no_god
from utils.i18n import _, locale_doc


class Gods(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.gods = {god["user"]: god for god in self.bot.config.gods}

    @has_god()
    @has_char()
    @user_cooldown(180, identifier="sacrificeexchange")
    @commands.command(brief=_("Sacrifice loot for favor"))
    @locale_doc
    async def sacrifice(self, ctx, *loot_ids: int):
        _(
            """`[loot_ids...]` - The loot IDs to sacrifice, can be one or multiple IDs separated by space; defaults to all loot

            Sacrifice loot to your God to gain favor points.

            If no loot IDs are given with this command, all loot you own will be sacrificed.
            You can see your current loot with `{prefix}loot`.

            Only players, who follow a God can use this command."""
        )
        async with self.bot.pool.acquire() as conn:
            if not loot_ids:
                value, count = await conn.fetchval(
                    'SELECT (SUM("value"), COUNT(*)) FROM loot WHERE "user"=$1;',
                    ctx.author.id,
                )
                if count == 0:
                    await self.bot.reset_cooldown(ctx)
                    return await ctx.send(_("You don't have any loot."))
                if not await ctx.confirm(
                    _(
                        "This will sacrifice all of your loot and give {value} favor."
                        " Continue?"
                    ).format(value=value)
                ):
                    return
            else:
                value, count = await conn.fetchval(
                    'SELECT (SUM("value"), COUNT("value")) FROM loot WHERE "id"=ANY($1)'
                    ' AND "user"=$2;',
                    loot_ids,
                    ctx.author.id,
                )

                if not count:
                    return await ctx.send(
                        _(
                            "You don't own any loot items with the IDs: {itemids}"
                        ).format(
                            itemids=", ".join([str(loot_id) for loot_id in loot_ids])
                        )
                    )
            class_ = ctx.character_data["class"]
            for class_ in ctx.character_data["class"]:
                c = from_string(class_)
                if c and c.in_class_line(Ritualist):
                    value = round(value * Decimal(1 + 0.05 * c.class_grade()))

            if len(loot_ids) > 0:
                await conn.execute(
                    'DELETE FROM loot WHERE "id"=ANY($1) AND "user"=$2;',
                    loot_ids,
                    ctx.author.id,
                )
            else:
                await conn.execute('DELETE FROM loot WHERE "user"=$1;', ctx.author.id)
            await conn.execute(
                'UPDATE profile SET "favor"="favor"+$1 WHERE "user"=$2;',
                value,
                ctx.author.id,
            )

            value = float(value)
            value = int(value)


            await self.bot.log_transaction(
                ctx,
                from_=ctx.author.id,
                to=2,
                subject="sacrifice",
                data={"Item-Count": count, "Amount": value},
                conn=conn,
            )
        await ctx.send(
            _(
                "You prayed to {god}, and they accepted your {count} sacrificed loot"
                " item(s). Your standing with the god has increased by **{points}**"
                " points."
            ).format(god=ctx.character_data["god"], count=count, points=value)
        )

    @has_char()
    @user_cooldown(180)  # to prevent double invoke
    @commands.command(brief=_("Choose or change your God"))
    @locale_doc
    async def follow(self, ctx):
        _(
            """Choose a God or change your current God for a reset point.
            Every player gets 2 reset points when they start playing, you cannot get any more.

            Following a God allows your `{prefix}luck` to fluctuate, check `{prefix}help luck` to see the exact effects this will have on your gameplay.
            If you don't have any reset points left, or became Godless, you cannot follow another God.

            (This command has a cooldown of 3 minutes.)"""
        )
        if not has_no_god(ctx):
            if ctx.character_data["reset_points"] < 1:
                return await ctx.send(_("You have no more reset points."))
            if not await ctx.confirm(
                _(
                    "You already chose a god. This change now will cost you a reset"
                    " point. Are you sure?"
                )
            ):
                return
        if ctx.character_data["reset_points"] < 0:
            return await ctx.send("You became Godless and cannot follow a God anymore.")
        embeds = [
            discord.Embed(
                title=god["name"],
                description=god["description"],
                color=self.bot.config.game.primary_colour,
            )
            for god in self.bot.gods.values()
        ]
        god = await self.bot.paginator.ChoosePaginator(
            extras=embeds,
            placeholder=_("Choose a god"),
            choices=[g["name"] for g in self.bot.gods.values()],
        ).paginate(ctx)

        if not await ctx.confirm(
            _(
                """\
⚠ **Warning**: When you have a God, your luck will change (**including decreasing it!**)
This impacts your adventure success chances amongst other things.

Are you sure you want to follow {god}?"""
            ).format(god=god)
        ):
            return

        async with self.bot.pool.acquire() as conn:
            if (
                await conn.fetchval(
                    'SELECT reset_points FROM profile WHERE "user"=$1;', ctx.author.id
                )
                < 0
            ):
                return await ctx.send(
                    _(
                        "You became Godless while using this command. Following a God"
                        " is not allowed after that."
                    )
                )
            if not has_no_god(ctx):
                await conn.execute(
                    'UPDATE profile SET "reset_points"="reset_points"-$1 WHERE'
                    ' "user"=$2;',
                    1,
                    ctx.author.id,
                )
            await conn.execute(
                'UPDATE profile SET "god"=$1 WHERE "user"=$2;', god, ctx.author.id
            )

        await ctx.send(_("You are now a follower of {god}.").format(god=god))

    @has_char()
    @has_god()
    @commands.command(brief=_("Unfollow your God and become Godless"))
    @locale_doc
    async def unfollow(self, ctx):
        _(
            """Unfollow your current God and become Godless. **This is permanent!**

            Looking to change your God instead? Simply use `{prefix}follow` again.

            Once you become Godless, all your reset points and your God are removed.
            Becoming Godless does not mean that your luck returns to 1.00 immediately, it changes along with everyone else's luck on Monday."""
        )
        if ctx.character_data["reset_points"] < 0:
            # this shouldn't happen in normal play, but you never know
            return await ctx.send(_("You already became Godless before."))

        if not await ctx.confirm(
            _(
                """\
    ⚠ **Warning**: After unfollowing your God, **you cannot follow any God anymore** and will remain Godless.
    If your luck is below average and you decided to unfollow, know that **your luck will not return to 1.0 immediately**.

    Are you sure you want to become Godless?"""
            )
        ):
            return await ctx.send(
                _("{god} smiles proudly down upon you.").format(
                    god=ctx.character_data["god"]
                )
            )

        await self.bot.pool.execute(
            'UPDATE profile SET "favor"=0, "god"=NULL, "reset_points"=-1 WHERE'
            ' "user"=$1;',
            ctx.author.id,
        )

        await ctx.send(_("You are now Godless."))

    @has_god()
    @has_char()
    @next_day_cooldown()
    @commands.command(brief=_("Pray to your God to gain favor"))
    @locale_doc
    async def pray(self, ctx):
        _(
            # xgettext: no-python-format
            """Pray to your God in order to gain a random amont of favor points, ranging from 0 to 1000.

            There is a 33% chance you will gain 0 favor, a 33% chance to gain anywhere from 0 to 500 favor and a 33% chance to gain anywhere from 500 to 1000 favor.

            (This command has a cooldown until 12am UTC.)"""
        )
        if (rand := random.randint(0, 2)) == 0:
            message = random.choice(
                [
                    _("They obviously didn't like your prayer!"),
                    _("Noone heard you!"),
                    _("Your voice has made them screw off."),
                    _("Even a donkey would've been a better follower than you."),
                ]
            )
            val = 0
        elif rand == 1:
            val = random.randint(1, 500)
            message = random.choice(
                [
                    _("„Rather lousy, but okay“, they said."),
                    _("You were a little sleepy."),
                    _("They were a little amused about your singing."),
                    _("Hearing the same prayer over and over again made them tired."),
                ]
            )
        elif rand == 2:
            val = random.randint(0, 500) + 500
            message = random.choice(
                [
                    _("Your Gregorian chants were amazingly well sung."),
                    _("Even the birds joined in your singing."),
                    _(
                        "The other gods applauded while your god noted down the best"
                        " mark."
                    ),
                    _("Rarely have you had a better day!"),
                ]
            )
        if val > 0:
            await self.bot.pool.execute(
                'UPDATE profile SET "favor"="favor"+$1 WHERE "user"=$2;',
                val,
                ctx.author.id,
            )
        await ctx.send(
            _("Your prayer resulted in **{val}** favor. {message}").format(
                val=val, message=message
            )
        )

    @has_god()
    @has_char()
    @commands.command(aliases=["favour"], brief=_("Shows your God and favor"))
    @locale_doc
    async def favor(self, ctx):
        _(
            """Shows your current God and how much favor you have with them at the time.

            If you have enough favor to place in the top 25 of that God's followers, you will gain extra luck when the new luck is decided, this usually happens on Monday.
              - The top 25 to 21 will gain +0.1 luck
              - The top 20 to 16 will gain +0.2 luck
              - The top 15 to 11 will gain +0.3 luck
              - The top 10 to 6 will gain +0.4 luck
              - The top 5 to 1 will gain +0.5 luck

            These extra luck values are based off the decided luck value.
            For example, if your God's luck value is decided to be 1.2 and you are the 13th best follower, you will have 1.5 luck for that week.
            All favor is reset to 0 when the new luck is decided to make it fair for everyone."""
        )
        await ctx.send(
            _("Your god is **{god}** and you have **{favor}** favor with them.").format(
                god=ctx.character_data["god"], favor=ctx.character_data["favor"]
            )
        )

    # just like admin commands, these aren't translated
    @has_char()
    @commands.command(brief=_("Show the top followers of your God"))
    @locale_doc
    async def followers(self, ctx, limit: IntGreaterThan(0)):
        _(
            """`<limit>` - A whole number from 0 to 25. If you are a God, the upper bound is lifted.

            Display your God's (or your own, if you are a God) top followers, up to `<limit>`.

            The format for this is as follows:
              - Placement
              - User ID
              - Amount of favor
              - current luck

            The result is attached as a text file."""
        )
        if ctx.author.id in self.bot.gods:
            god = self.bot.gods[ctx.author.id]["name"]
        elif not ctx.character_data["god"]:
            return await ctx.send(
                _(
                    "You are not following any god currently, therefore the list cannot"
                    " be generated."
                )
            )
        else:
            if limit > 25:
                return await ctx.send(_("Normal followers may only view the top 25."))
            god = ctx.character_data["god"]
        data = await self.bot.pool.fetch(
            'SELECT * FROM profile WHERE "god"=$1 ORDER BY "favor" DESC LIMIT $2;',
            god,
            limit,
        )
        formatted = "\n".join(
            [
                f"{idx + 1}. {i['user']}: {i['favor']} Favor, Luck: {i['luck']}"
                for idx, i in enumerate(data)
            ]
        )
        await ctx.send(
            file=discord.File(filename="followers.txt", fp=BytesIO(formatted.encode()))
        )


async def setup(bot):
    await bot.add_cog(Gods(bot))
