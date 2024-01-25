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
import asyncio
import datetime
import math
from decimal import Decimal

from collections import deque
from decimal import Decimal

import random as rnd

import discord

from discord.enums import ButtonStyle
from discord.ext import commands
from discord.ui.button import Button

from classes.converters import IntFromTo
from classes.classes import Raider
from classes.classes import from_string as class_from_string
from cogs.help import chunks
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils import random
from utils.checks import has_char, is_gm
from utils.i18n import _, locale_doc
from utils.joins import JoinView


class Tournament(commands.Cog):
    def __init__(self, bot):
        self.deffbuff = 1
        self.bot = bot
        self.dmgbuff = 1

    def get_dmgbuff(self):
        return self.dmgbuff

    def get_deffbuff(self):
        return self.deffbuff

    async def get_raidstatsjug(
        self,
        thing,
        atkmultiply=None,
        defmultiply=None,
        classes=None,
        race=None,
        guild=None,
        god=None,
        conn=None,
    ):
        """Generates the raidstats for a user"""
        v = thing.id if isinstance(thing, (discord.Member, discord.User)) else thing
        local = False
        if conn is None:
            conn = await self.bot.pool.acquire()
            local = True
        if (
            atkmultiply is None
            or defmultiply is None
            or classes is None
            or guild is None
        ):
            row = await conn.fetchrow('SELECT * FROM profile WHERE "user"=$1;', v)
            atkmultiply, defmultiply, classes, race, guild, user_god = (
                row["atkmultiply"],
                row["defmultiply"],
                row["class"],
                row["race"],
                row["guild"],
                row["god"],
            )
            if god is not None and god != user_god:
                raise ValueError()
        damage, armor = await self.bot.get_damage_armor_for(
            v, classes=classes, race=race, conn=conn
        )
        if buildings := await self.bot.get_city_buildings(guild, conn=conn):
            atkmultiply += buildings["raid_building"] * Decimal("0.1")
            defmultiply += buildings["raid_building"] * Decimal("0.1")
        classes = [class_from_string(c) for c in classes]
        for c in classes:
            if c and c.in_class_line(Raider):
                grade = c.class_grade()
                atkmultiply = atkmultiply + Decimal("0.1") * grade
                defmultiply = defmultiply + Decimal("0.1") * grade
        tournament_instance = Tournament(self)
        dmgbuff = self.dmgbuff
        deffbuff = self.deffbuff

        atkmultiply = atkmultiply + dmgbuff
        defmultiply = defmultiply + deffbuff
        dmg = damage * atkmultiply
        deff = armor * defmultiply
        if local:
            await self.bot.pool.release(conn)
        return dmg, deff

    @has_char()
    @user_cooldown(1800)
    @commands.command(brief=_("Start a new tournament"))
    @locale_doc
    async def tournament(self, ctx, prize: IntFromTo(0, 100_000_000) = 0):
        _(
            """`[prize]` - The amount of money the winner will get

            Start a new tournament. Players have 30 seconds to join via the reaction.
            Tournament entries are free, only the tournament host has to pay the price.

            Only an exponent of 2 (2^n) users can join. If there are more than the nearest exponent, the last joined players will be disregarded.

            The match-ups will be decided at random, the battles themselves will be decided like regular battles (see `{prefix}help battle` for details).

            The winner of a match moves onto the next round, the losers get eliminated, until there is only one player left.
            Tournaments in IdleRPG follow the single-elimination principle.

            (This command has a cooldown of 30 minutes.)"""
        )
        if ctx.character_data["money"] < prize:
            await self.bot.reset_cooldown(ctx)
            return await ctx.send(_("You are too poor."))

        await self.bot.pool.execute(
            'UPDATE profile SET "money"="money"-$1 WHERE "user"=$2;',
            prize,
            ctx.author.id,
        )

        if (
                self.bot.config.game.official_tournament_channel_id
                and ctx.channel.id == self.bot.config.game.official_tournament_channel_id
        ):
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join the tournament!",
                    emoji="\U00002694",
                ),
                message=_("You joined the tournament."),
                timeout=60 * 10,
            )
            await ctx.send(
                "A mass-tournament has been started. The tournament starts in 10 minutes! The"
                f" prize is **${prize}**!",
                view=view,
            )
            await asyncio.sleep(60 * 10)
            view.stop()
            participants = []
            async with self.bot.pool.acquire() as conn:
                for u in view.joined:
                    if await conn.fetchrow(
                            'SELECT * FROM profile WHERE "user"=$1;', u.id
                    ):
                        participants.append(u)

        else:
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join the tournament!",
                    emoji="\U00002694",
                ),
                message=_("You joined the tournament."),
                timeout=60 * 2,
            )
            view.joined.add(ctx.author)
            msg = await ctx.send(
                _(
                    "{author} started a tournament! Free entries, prize is"
                    " **${prize}**!"
                ).format(author=ctx.author.mention, prize=prize),
                view=view,
            )
            await asyncio.sleep(60 * 10)
            view.stop()
            participants = []
            async with self.bot.pool.acquire() as conn:
                for u in view.joined:
                    if await conn.fetchrow(
                            'SELECT * FROM profile WHERE "user"=$1;', u.id
                    ):
                        participants.append(u)

        if len(participants) < 2:
            await self.bot.reset_cooldown(ctx)
            await self.bot.pool.execute(
                'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                prize,
                ctx.author.id,
            )
            return await ctx.send(
                _("Noone joined your tournament {author}.").format(
                    author=ctx.author.mention
                )
            )

        toremove = 2 ** math.floor(math.log2(len(participants)))
        if toremove != len(participants):
            await ctx.send(
                _(
                    "There are **{num}** entries, due to the fact we need a playable"
                    " tournament, the last **{removed}** have been removed."
                ).format(num=len(participants), removed=len(participants) - toremove)
            )
            participants = participants[: -(len(participants) - toremove)]
        else:
            await ctx.send(
                _("Tournament started with **{num}** entries.").format(num=toremove)
            )
        text = _("vs")
        while len(participants) > 1:
            participants = random.shuffle(participants)
            matches = list(chunks(participants, 2))

            for match in matches:
                await ctx.send(f"{match[0].mention} {text} {match[1].mention}")
                await asyncio.sleep(2)
                async with self.bot.pool.acquire() as conn:
                    val1 = sum(
                        await self.bot.get_damage_armor_for(match[0], conn=conn)
                    ) + random.randint(1, 7)
                    val2 = sum(
                        await self.bot.get_damage_armor_for(match[1], conn=conn)
                    ) + random.randint(1, 7)
                if val1 > val2:
                    winner = match[0]
                    looser = match[1]
                elif val2 > val1:
                    winner = match[1]
                    looser = match[0]
                else:
                    winner = random.choice(match)
                    looser = match[1 - match.index(winner)]
                participants.remove(looser)
                await ctx.send(
                    _("Winner of this match is {winner}!").format(winner=winner.mention)
                )
                await asyncio.sleep(2)

            await ctx.send(_("Round Done!"))

        msg = await ctx.send(
            _("Tournament ended! The winner is {winner}.").format(
                winner=participants[0].mention
            )
        )

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                prize,
                participants[0].id,
            )
            await self.bot.log_transaction(
                ctx,
                from_=ctx.author.id,
                to=participants[0].id,
                subject="Torunament Winner",
                data={"Gold": prize},
                conn=conn,
            )
        await msg.edit(
            content=_(
                "Tournament ended! The winner is {winner}.\nMoney was given!"
            ).format(winner=participants[0].mention)
        )

    @has_char()
    @user_cooldown(300)
    @commands.command()
    @locale_doc
    async def juggernaut(self, ctx, prize: IntFromTo(0, 100_000_000) = 0, hp: int = 250, juggernaut_hp: int = 7500):
        _(
            """`[prize]` - The amount of money the winner will get

            Start a new raid tournament. Players have 30 seconds to join via the reaction.
            Tournament entries are free, only the tournament host has to pay the price.

            Only an exponent of 2 (2^n) users can join. If there are more than the nearest exponent, the last joined players will be disregarded.

            The match-ups will be decided at random, the battles themselves will be decided like raid battles (see `{prefix}help raidbattle` for details).

            The winner of a match moves onto the next round, the losers get eliminated, until there is only one player left.
            Tournaments in IdleRPG follow the single-elimination principle.

            (This command has a cooldown of 30 minutes.)"""
        )

        if ctx.character_data["money"] < prize:
            await self.bot.reset_cooldown(ctx)
            return await ctx.send(_("You are too poor."))


        await self.bot.pool.execute(
            'UPDATE profile SET "money"="money"-$1 WHERE "user"=$2;',
            prize,
            ctx.author.id,
        )

        if (
                self.bot.config.game.official_tournament_channel_id
                and ctx.channel.id == self.bot.config.game.official_tournament_channel_id
        ):
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join Juggernaut!",
                    emoji="\U00002694",
                ),
                message=_("You joined the Juggernaut Gamemode."),
                timeout=60 * 3,
            )
            if hp == 250:
                await ctx.send(
                    "A Juggernaut gamemode has been started. The gamemode starts in 3 minutes! The"
                    f" prize pool is **${prize}**!",
                    view=view,
                )
            else:
                await ctx.send(
                    f"A Juggernaut gamemode has been started. Custom HP set to {hp}! The Juggernaut gamemode starts in 3 minutes! The"
                    f" prize is **${prize}**!",
                    view=view,
                )
            await asyncio.sleep(60 * 3)
            view.stop()
            participants = []
            async with self.bot.pool.acquire() as conn:
                for u in view.joined:
                    if await conn.fetchrow(
                            'SELECT * FROM profile WHERE "user"=$1;', u.id
                    ):
                        participants.append(u)

        else:
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join juggernaut!",
                    emoji="\U00002694",
                ),
                message=_("You joined the juggernaut gamemode."),
                timeout=60 * 3,
            )
            view.joined.add(ctx.author)
            msg = await ctx.send(
                _(
                    "{author} started a juggernaut gamemode! Free entries, prize pool is"
                    " **${prize}**!"
                ).format(author=ctx.author.mention, prize=prize),
                view=view,
            )
            await asyncio.sleep(60 * 3)
            view.stop()
            participants = []
            async with self.bot.pool.acquire() as conn:
                for u in view.joined:
                    if await conn.fetchrow(
                            'SELECT * FROM profile WHERE "user"=$1;', u.id
                    ):
                        participants.append(u)

        if len(participants) < 3:
            await self.bot.reset_cooldown(ctx)
            await self.bot.pool.execute('UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;', prize, ctx.author.id)
            return await ctx.send(
                _("Not enough participants to start the game, {author}.").format(author=ctx.author.mention))
        try:
            await ctx.send(f"There are {len(participants)} participants in the game.")
            # 2. Select a juggernaut
            juggernaut = random.choice(participants)

            # Get and double the juggernaut's stats
            async with self.bot.pool.acquire() as conn:
                juggernaut_dmg, juggernaut_deff = await self.bot.get_raidstats(juggernaut, conn=conn)
            juggernaut_deff *= 3

            await ctx.send(_(f"{juggernaut.mention} has been chosen as the juggernaut with **{juggernaut_hp}** HP!"))
            participants.remove(juggernaut)

            self.dmgbuff = 0
            self.deffbuff = 0

        except Exception as e:
            await ctx.send(f"{e}")

        def buff_stats(stats):
            def round_to_nearest(x, base=0.1):
                return round(x / base) * base

            self.deffbuff += Decimal(round_to_nearest(rnd.uniform(0.1, 0.2)))
            self.dmgbuff += Decimal(round_to_nearest(rnd.uniform(0.1, 0.2)))

        juggernaut_tracker_HP = juggernaut_hp
        TurnCounter = 0
        juggernaut_killer = None
        all_player_stats = {}
        defeated = []
        turnpass = False
        turn = False
        battle_ongoing = True  # Initialize a variable to track the battle state

        while participants and battle_ongoing:
            random.shuffle(participants)
            for player in participants:
                # Get player's stats
                if battle_ongoing:

                    try:
                        async with self.bot.pool.acquire() as conn:
                            dmg, deff = await self.get_raidstatsjug(player, conn=conn)
                            dmg = round(dmg, 2)
                            deff = round(deff, 2)

                        async with self.bot.pool.acquire() as conn:
                            dmgt, defft = await self.bot.get_raidstats(player, conn=conn)
                            dmgt = round(dmgt, 2)
                            defft = round(defft, 2)

                        await ctx.send(f"Normie: ATK {dmgt}, DEF {defft}. Modified: {dmg}, DEF {deff}")

                    except Exception as e:
                        await ctx.send(f"{e}")

                    player_stats = {
                        "user": player,
                        "hp": hp,  # This hp needs to be defined elsewhere
                        "armor": deff,
                        "damage": dmg,
                    }
                    all_player_stats[player.id] = player_stats
                    # Set up the battle participants
                    try:
                        players = [player_stats, {
                            "user": juggernaut,
                            "hp": juggernaut_tracker_HP,
                            "damage": juggernaut_dmg,
                            "armor": juggernaut_deff
                        }]
                    except Exception as e:
                        await ctx.send(f"An error occurred: {e}")

                    battle_log = deque(
                        [
                            (
                                0,
                                _("Raidbattle {p1} vs. {p2} started!").format(
                                    p1=players[0]["user"].mention, p2=players[1]["user"].mention
                                ),
                            )
                        ],
                        maxlen=3,
                    )

                    embed = discord.Embed(
                        description=battle_log[0][1],
                        color=self.bot.config.game.primary_colour,
                    )

                    log_message = await ctx.send(embed=embed)
                    await asyncio.sleep(4)

                    start = datetime.datetime.utcnow()
                    attacker, defender = players
                    while (
                            attacker["hp"] > 0
                            and defender["hp"] > 0
                            and datetime.datetime.utcnow()
                            < start + datetime.timedelta(minutes=5)
                    ):
                        dmg = (
                                attacker["damage"]
                                + Decimal(random.randint(0, 100))
                                - defender["armor"]
                        )
                        dmg = 1 if dmg <= 0 else dmg  # make sure no negative damage happens
                        if defender["user"] != juggernaut and TurnCounter >= 6:
                            await ctx.send("The Juggernaut charges their weapon")
                            dmg = dmg + 1000
                        defender["hp"] -= dmg
                        if defender["hp"] < 0:
                            defender["hp"] = 0
                        battle_log.append(
                            (
                                battle_log[-1][0] + 1,
                                _(
                                    "{attacker} attacks! {defender} takes **{dmg}HP**"
                                    " damage."
                                ).format(
                                    attacker=attacker["user"].mention,
                                    defender=defender["user"].mention,
                                    dmg=dmg,
                                ),
                            )
                        )

                        embed = discord.Embed(
                            description=_(
                                "{p1} - {hp1} HP left\n{p2} - {hp2} HP left"
                            ).format(
                                p1=players[0]["user"].mention,
                                hp1=players[0]["hp"],
                                p2=players[1]["user"].mention,
                                hp2=players[1]["hp"],
                            ),
                            color=self.bot.config.game.primary_colour,
                        )

                        for line in battle_log:
                            embed.add_field(
                                name=_("Action #{number}").format(number=line[0]),
                                value=line[1],
                            )
                        TurnCounter = TurnCounter + 1
                        await log_message.edit(embed=embed)
                        await asyncio.sleep(4)
                        juggernaut_tracker_HP = players[1]["hp"]
                        if juggernaut_tracker_HP <= 0:
                            await ctx.send(_("Juggernaut has been defeated!"))
                            juggernaut_killer = attacker["user"].id
                            await ctx.send(
                                _("{attacker} has dealt the finishing blow to the juggernaut and is the winner!").format(
                                    attacker=attacker["user"].mention))
                            battle_ongoing = False
                            self.deffbuff = 0
                            self.dmgbuff = 0
                            break
                        if players[0]["hp"] <= 0:
                            defeated.append(player)
                            await ctx.send(_(f"Juggernaut has defeated {player.name}!"))
                            TurnCounter = 0
                            juggernaut_tracker_HP = players[1]["hp"]
                            await asyncio.sleep(2)
                        attacker, defender = defender, attacker  # This line swaps attacker and defender

            # If all players are defeated, buff their stats and go for another round
            if battle_ongoing:
                if set(defeated) == set(participants):

                    for player in participants:
                        player_stats = all_player_stats[player.id]
                        random.shuffle(participants)
                        try:
                            buff_stats(player_stats)

                        except Exception as e:
                            await ctx.send(f"An error occurred: {e}")
                            continue  # move to the next player if there was an issue buffing this one

                        # Revive the player by resetting their HP to the original value
                        player_stats["hp"] = hp

                    # Clear the list of defeated players for the next round
                    turn = True
                    await ctx.send(
                        _(f"Juggernaut has defeated all participants! The party raid stats grown to am additional x{round(self.deffbuff, 2)} DEF and x{round(self.dmgbuff, 2)} ATK.")
                    )

                    defeated.clear()

        if battle_ongoing == False:
            totalprize = prize
            prizejug = prize * 0.2
            prize = prize * 0.8
            prize = round(prize)  # Rounds to the nearest whole number
            prizejug = round(prizejug)
            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                    prize,
                    juggernaut_killer,
                )
                await conn.execute(
                    'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                    prizejug,
                    juggernaut.id,
                )
                await self.bot.log_transaction(
                    ctx,
                    from_=ctx.author.id,
                    to=participants[0].id,
                    subject="Juggernaut",
                    data={"Gold": prize},
                    conn=conn,
                )
            if prize > 0:
                await ctx.send(
                    f"Juggernaut received **${prizejug}** and {juggernaut_killer.mention} has received **${prize}** of the total prize of **{totalprize}**")

    @has_char()
    @is_gm()
    @user_cooldown(1800)
    @commands.command()
    @locale_doc
    async def uno(self, ctx, prize: IntFromTo(0, 100_000_000) = 0, hp: int = 250):
        _(
            """`[prize]` - The amount of money the winner will get

            Start a new raid tournament. Players have 30 seconds to join via the reaction.
            Tournament entries are free, only the tournament host has to pay the price.

            Only an exponent of 2 (2^n) users can join. If there are more than the nearest exponent, the last joined players will be disregarded.

            The match-ups will be decided at random, the battles themselves will be decided like raid battles (see `{prefix}help raidbattle` for details).

            The winner of a match moves onto the next round, the losers get eliminated, until there is only one player left.
            Tournaments in IdleRPG follow the single-elimination principle.

            (This command has a cooldown of 30 minutes.)"""
        )
        if ctx.character_data["money"] < prize:
            await self.bot.reset_cooldown(ctx)
            return await ctx.send(_("You are too poor."))

        await self.bot.pool.execute(
            'UPDATE profile SET "money"="money"-$1 WHERE "user"=$2;',
            prize,
            ctx.author.id,
        )

        if (
                self.bot.config.game.official_tournament_channel_id
                and ctx.channel.id != self.bot.config.game.official_tournament_channel_id
        ):
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join the uno tournament!",
                    emoji="\U00002694",
                ),
                message=_("You joined the uno tournament."),
                timeout=60 * 10,
            )
            if hp == 250:
                await ctx.send(
                    "A mass-uno tournament has been started. The tournament starts in 5 minutes! The"
                    f" prize is **${prize}**!",
                    view=view,
                )
            else:
                await ctx.send(
                    f"A mass-uno tournament has been started. Custom HP set to {hp}! The tournament starts in 5 minutes! The"
                    f" prize is **${prize}**!",
                    view=view,
                )
            await asyncio.sleep(60)
            view.stop()
            await ctx.send("https://media.tenor.com/x8v1oNUOmg4AAAAd/rickroll-roll.gif")

    @has_char()
    @user_cooldown(1800)
    @commands.command()
    @locale_doc
    async def raidtournament(self, ctx, prize: IntFromTo(0, 100_000_000) = 0, hp: int = 500):
        _(
            """`[prize]` - The amount of money the winner will get

            Start a new raid tournament. Players have 30 seconds to join via the reaction.
            Tournament entries are free, only the tournament host has to pay the price.

            Only an exponent of 2 (2^n) users can join. If there are more than the nearest exponent, the last joined players will be disregarded.

            The match-ups will be decided at random, the battles themselves will be decided like raid battles (see `{prefix}help raidbattle` for details).

            The winner of a match moves onto the next round, the losers get eliminated, until there is only one player left.
            Tournaments in IdleRPG follow the single-elimination principle.

            (This command has a cooldown of 30 minutes.)"""
        )
        if ctx.character_data["money"] < prize:
            await self.bot.reset_cooldown(ctx)
            return await ctx.send(_("You are too poor."))

        await self.bot.pool.execute(
            'UPDATE profile SET "money"="money"-$1 WHERE "user"=$2;',
            prize,
            ctx.author.id,
        )

        if (
                self.bot.config.game.official_tournament_channel_id
                and ctx.channel.id == self.bot.config.game.official_tournament_channel_id
        ):
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join the raid tournament!",
                    emoji="\U00002694",
                ),
                message=_("You joined the raid tournament."),
                timeout=60 * 10,
            )
            if hp == 250:
                await ctx.send(
                    "A mass-raidtournament has been started. The tournament starts in 5 minutes! The"
                    f" prize is **${prize}**!",
                    view=view,
                )
            else:
                await ctx.send(
                    f"A mass-raidtournament has been started. Custom HP set to {hp}! The tournament starts in 5 minutes! The"
                    f" prize is **${prize}**!",
                    view=view,
                )
            await asyncio.sleep(60 * 5)
            view.stop()
            participants = []
            async with self.bot.pool.acquire() as conn:
                for u in view.joined:
                    if await conn.fetchrow(
                            'SELECT * FROM profile WHERE "user"=$1;', u.id
                    ):
                        participants.append(u)

        else:
            view = JoinView(
                Button(
                    style=ButtonStyle.primary,
                    label="Join the raid tournament!",
                    emoji="\U00002694",
                ),
                message=_("You joined the raid tournament."),
                timeout=60 * 2,
            )
            view.joined.add(ctx.author)
            msg = await ctx.send(
                _(
                    "{author} started a raid tournament! Free entries, prize is"
                    " **${prize}**!"
                ).format(author=ctx.author.mention, prize=prize),
                view=view,
            )
            await asyncio.sleep(60 * 5)
            view.stop()
            participants = []
            async with self.bot.pool.acquire() as conn:
                for u in view.joined:
                    if await conn.fetchrow(
                            'SELECT * FROM profile WHERE "user"=$1;', u.id
                    ):
                        participants.append(u)

        if len(participants) < 2:
            await self.bot.reset_cooldown(ctx)
            await self.bot.pool.execute(
                'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                prize,
                ctx.author.id,
            )
            return await ctx.send(
                _("Noone joined your raid tournament {author}.").format(
                    author=ctx.author.mention
                )
            )

        bye_recipients = []  # To keep track of participants who received a bye

        nearest_power_of_2 = 2 ** math.ceil(math.log2(len(participants)))
        byes_needed = nearest_power_of_2 - len(participants)

        if byes_needed > 0:
            bye_recipients = random.sample(participants, byes_needed)
            for recipient in bye_recipients:
                await ctx.send(
                    _("Participant {participant} received a bye for this round!").format(participant=recipient.mention))
                participants.remove(recipient)

        await ctx.send(
            _("Tournament started with **{num}** entries.").format(num=len(participants) + len(bye_recipients)))

        text = _("vs")
        while len(participants) > 1:
            participants = random.shuffle(participants)
            matches = list(chunks(participants, 2))

            for match in matches:
                await ctx.send(f"{match[0].mention} {text} {match[1].mention}")

                players = []
                async with self.bot.pool.acquire() as conn:
                    for player in match:
                        dmg, deff = await self.bot.get_raidstats(player, conn=conn)
                        u = {
                            "user": player,
                            "hp": hp,
                            "armor": deff,
                            "damage": dmg,
                        }
                        players.append(u)

                battle_log = deque(
                    [
                        (
                            0,
                            _("Raidbattle {p1} vs. {p2} started!").format(
                                p1=players[0]["user"], p2=players[1]["user"]
                            ),
                        )
                    ],
                    maxlen=3,
                )

                embed = discord.Embed(
                    description=battle_log[0][1],
                    color=self.bot.config.game.primary_colour,
                )

                log_message = await ctx.send(embed=embed)
                await asyncio.sleep(4)

                start = datetime.datetime.utcnow()
                attacker, defender = random.shuffle(players)
                while (
                        attacker["hp"] > 0
                        and defender["hp"] > 0
                        and datetime.datetime.utcnow()
                        < start + datetime.timedelta(minutes=5)
                ):
                    # this is where the fun begins
                    dmg = (
                            attacker["damage"]
                            + Decimal(random.randint(0, 100))
                            - defender["armor"]
                    )
                    dmg = 1 if dmg <= 0 else dmg  # make sure no negative damage happens
                    defender["hp"] -= dmg
                    if defender["hp"] < 0:
                        defender["hp"] = 0
                    battle_log.append(
                        (
                            battle_log[-1][0] + 1,
                            _(
                                "{attacker} attacks! {defender} takes **{dmg}HP**"
                                " damage."
                            ).format(
                                attacker=attacker["user"].mention,
                                defender=defender["user"].mention,
                                dmg=dmg,
                            ),
                        )
                    )

                    embed = discord.Embed(
                        description=_(
                            "{p1} - {hp1} HP left\n{p2} - {hp2} HP left"
                        ).format(
                            p1=players[0]["user"],
                            hp1=players[0]["hp"],
                            p2=players[1]["user"],
                            hp2=players[1]["hp"],
                        ),
                        color=self.bot.config.game.primary_colour,
                    )

                    for line in battle_log:
                        embed.add_field(
                            name=_("Action #{number}").format(number=line[0]),
                            value=line[1],
                        )

                    await log_message.edit(embed=embed)
                    await asyncio.sleep(4)
                    attacker, defender = defender, attacker  # switch places
                if players[0]["hp"] == 0:
                    winner = match[1]
                    looser = match[0]
                else:
                    winner = match[0]
                    looser = match[1]
                participants.remove(looser)
                await ctx.send(
                    _("Winner of this match is {winner}!").format(winner=winner.mention)
                )
                await asyncio.sleep(2)

            await ctx.send(_("Round Done!"))
            participants.extend(bye_recipients)  # Add back participants who received a bye
            bye_recipients = []  # Reset the list for the next round

        msg = await ctx.send(
            _("Raid Tournament ended! The winner is {winner}.").format(
                winner=participants[0].mention
            )
        )

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE profile SET "money"="money"+$1 WHERE "user"=$2;',
                prize,
                participants[0].id,
            )
            await self.bot.log_transaction(
                ctx,
                from_=ctx.author.id,
                to=participants[0].id,
                subject="Tournament Prize",
                data={"Gold": prize},
                conn=conn,
            )
        await msg.edit(
            content=_(
                "Raid Tournament ended! The winner is {winner}.\nMoney was given!"
            ).format(winner=participants[0].mention)
        )


async def setup(bot):
    await bot.add_cog(Tournament(bot))
