import asyncio
import datetime
import decimal

from collections import deque
from decimal import Decimal

import discord
import random as random
from discord.enums import ButtonStyle
from discord.ext import commands
from discord.ui.button import Button

from classes.classes import Ranger, Reaper
from classes.classes import from_string as class_from_string
from classes.converters import IntGreaterThan
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils import random as randomm
from utils.checks import has_char, has_money, is_gm
from utils.i18n import _, locale_doc
from utils.joins import SingleJoinView
import asyncpg


# Assuming you have a database connection pool (self.bot.pool) already set up

class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @is_gm()
    async def gmlotto(self, ctx, amount: int, tickets: int):
        # Update the database with the new lottery settings

        try:
            async with self.bot.pool.acquire() as connection:
                # Check if data already exists
                existing_data = await connection.fetchrow("SELECT 1 FROM lottodata LIMIT 1")

                if existing_data:
                    # If data exists, remove it
                    await connection.execute("DELETE FROM lottodata")

                # Insert the new data
                await connection.execute(
                    "INSERT INTO lottodata (maxtickets, ticketcost) VALUES ($1, $2)",
                    tickets, amount
                )

            await ctx.send(
                f"Lottery settings updated. Ticket cost: **${amount}**, Max tickets per player: **{tickets}**")

            # Send a message to the specified channel
            lottery_channel_id = 1140207396459925596  # Replace with your desired channel ID
            lottery_channel = self.bot.get_channel(lottery_channel_id)

            if lottery_channel:
                embed = discord.Embed(
                    title="Weekly Lotto Started!",
                    description=f"**Ticket Cost:** ${amount}\n**Max Tickets per Player:** {tickets}\n\nTo participate, use the commands:\n`$lotto` - View lottery information\n`$lotto buy [num_tickets]` - Purchase lottery tickets",
                    color=0x00ff00
                )
                await lottery_channel.send(embed=embed)

                # Tag the specified role after sending the embed
                role_id = 1147199558766567559  # Replace with your desired role ID
                role = await discord.utils.get(ctx.guild.roles, id=role_id)
                if role:
                    await ctx.send(f"{role.mention} Lottery announcement sent!")
                else:
                    await ctx.send("Error: Role not found. Please check the role ID.")
            else:
                await ctx.send("Error: Lottery channel not found. Please check the channel ID.")
        except Exception as e:
            await ctx.send(f"Error: {e}")

    @commands.command()
    @has_char()
    async def lotto(self, ctx, subcommand=None, num_tickets: int = None):
        try:
            if subcommand == 'buy':
                # Check if there is existing lottery data
                async with self.bot.pool.acquire() as connection:
                    existing_data = await connection.fetchrow("SELECT * FROM lottodata")
                    user_tickets = await connection.fetchval("SELECT tickets FROM lottery WHERE id = $1",
                                                             ctx.author.id)

                if existing_data:
                    # Fetch the current lottery settings from the database
                    async with self.bot.pool.acquire() as connection:
                        row = await connection.fetchrow("SELECT maxtickets, ticketcost FROM lottodata")

                    if row:
                        max_tickets = row['maxtickets']
                        ticket_cost = row['ticketcost']
                        usertickets = user_tickets or 0
                        maxtickets = (user_tickets or 0) + num_tickets

                        # Check if the user is trying to buy more tickets than the maximum limit

                        if maxtickets > max_tickets:
                            return await ctx.send(
                                f"You cannot purchase more than {max_tickets} tickets total. You have {usertickets}.")

                        if num_tickets is None or num_tickets <= 0:
                            await ctx.send("Please provide a valid number of tickets to purchase.")
                        elif num_tickets > max_tickets:
                            await ctx.send(f"You cannot purchase more than {max_tickets} tickets total.")
                        else:
                            # Fetch the current number of tickets the user has
                            async with self.bot.pool.acquire() as connection:
                                user_id = ctx.author.id
                                user_tickets = await connection.fetchval("SELECT tickets FROM lottery WHERE id = $1",
                                                                         user_id)

                            # Calculate the total cost
                            total_cost = num_tickets * ticket_cost
                            #await ctx.send(f"{total_cost}")

                            updated_tickets = 0  # Initialize the variable outside the if block

                            if ctx.character_data["money"] < total_cost:
                                return await ctx.send(_("You are too poor."))

                            # Ask for confirmation
                            confirmation_message = (
                                f"You are about to purchase **{num_tickets}** tickets for a total cost of **${total_cost}**.\n"
                                f"Your current ticket count is **{user_tickets or 0}**. Do you want to proceed?"
                            )

                            if await ctx.confirm(confirmation_message):
                                # Execute buy logic if the user confirms
                                if ctx.character_data["money"] < total_cost:
                                    return await ctx.send(_("You are too poor."))
                                async with self.bot.pool.acquire() as connection:
                                    await self.bot.pool.execute(
                                        'UPDATE profile SET "money"="money"-$1 WHERE "user"=$2;',
                                        total_cost,
                                        ctx.author.id,
                                    )
                                async with self.bot.pool.acquire() as connection:
                                    # If the user doesn't exist in the table, insert a new row
                                    if user_tickets is None:
                                        await connection.execute("INSERT INTO lottery (id, tickets) VALUES ($1, $2)",
                                                                 user_id, num_tickets)
                                    else:
                                        # Update the number of tickets if the user already exists
                                        await connection.execute("UPDATE lottery SET tickets = $1 WHERE id = $2",
                                                                 user_tickets + num_tickets, user_id)

                                        # Fetch the updated number of tickets
                                        updated_tickets = await connection.fetchval(
                                            "SELECT tickets FROM lottery WHERE id = $1", user_id)

                                await ctx.send(
                                    f"You have successfully purchased {num_tickets} tickets for the lottery. You now have {updated_tickets} tickets.")
                            else:
                                await ctx.send("Purchase cancelled.")
                    else:
                        await ctx.send("No lottery settings found. Use $gmlotto to set them.")
                else:
                    await ctx.send("No lottery is currently running. Use $gmlotto to start a new lottery.")
            else:
                # Fetch and display lottery settings
                async with self.bot.pool.acquire() as connection:
                    row = await connection.fetchrow("SELECT maxtickets, ticketcost FROM lottodata")

                if row:
                    max_tickets = row['maxtickets']
                    ticket_cost = row['ticketcost']

                    # Fetch and display user tickets from the lottery table
                    async with self.bot.pool.acquire() as connection:
                        user_tickets = await connection.fetch("SELECT id, tickets FROM lottery WHERE id = $1",
                                                              ctx.author.id)

                    # Fetch the total tickets and calculate the prize pool before releasing the connection
                    async with self.bot.pool.acquire() as connection:
                        total_tickets = await connection.fetchval("SELECT SUM(tickets) FROM lottery")

                    # Calculate prize pool
                    total_tickets = total_tickets or 0
                    prize_pool = total_tickets * ticket_cost

                    if user_tickets:
                        tickets_info = "\n".join(
                            [f"{self.bot.get_user(user['id']).display_name}: {user['tickets']} tickets" for user in
                             user_tickets])
                    else:
                        # If user_tickets is empty, assume the user has 0 tickets
                        tickets_info = f"{ctx.author.display_name}: 0 tickets"

                    # Construct and send the embed
                    embed = discord.Embed(title="Lottery Information", color=0x00ff00)
                    embed.add_field(name="**Current Lottery Settings**",
                                    value=f"Ticket Cost: ${ticket_cost}\nMax Tickets per Player: {max_tickets}")
                    embed.add_field(name="**User Tickets**", value=tickets_info, inline=False)
                    embed.add_field(name="**Total Tickets in the Lottery**", value=total_tickets, inline=False)
                    embed.add_field(name="**Prize Pool**", value=f"${prize_pool}", inline=False)

                    await ctx.send(embed=embed)

                else:
                    await ctx.send("No lottery settings found. Use $gmlotto to set them.")
        except Exception as e:
            await ctx.send(f"Error: {e}")

    @commands.command()
    @is_gm()
    async def gmdraw(self, ctx):
        # Fetch the current lottery settings from the database
        async with self.bot.pool.acquire() as connection:
            row = await connection.fetchrow("SELECT maxtickets, ticketcost FROM lottodata")

        if row:
            max_tickets = row['maxtickets']
            ticket_cost = row['ticketcost']

            # Fetch all participants and their ticket counts
            async with self.bot.pool.acquire() as connection:
                participants = await connection.fetch("SELECT id, tickets FROM lottery")

            if participants:
                # Create a weighted list for random selection
                weighted_list = []
                for participant in participants:
                    user_id = participant['id']
                    tickets = participant['tickets']
                    weighted_list.extend([user_id] * tickets)

                if weighted_list:
                    # Select a winner randomly from the weighted list
                    winner_id = random.choice(weighted_list)

                    # Notify the winner
                    winner = await self.bot.fetch_user(winner_id)
                    await ctx.send(f"Congratulations to {winner.mention}! You've won the lottery!")

                    # Reset the lottery data
                    async with self.bot.pool.acquire() as connection:
                        await connection.execute("DELETE FROM lottodata")
                        await connection.execute("DELETE FROM lottery")


                    await ctx.send("Lottery data has been reset for the next round.")
                else:
                    await ctx.send("No participants found. Lotto ended with no winner.")
                    try:
                        async with self.bot.pool.acquire() as connection:
                            await connection.execute("DELETE FROM lottodata")
                    except Exception as e:
                        pass
            else:
                await ctx.send("No participants found. Lotto ended with no winner.")
                try:
                    async with self.bot.pool.acquire() as connection:
                        await connection.execute("DELETE FROM lottodata")
                except Exception as e:
                    pass
        else:
            await ctx.send("No lottery settings found. Use $gmlotto to set them.")


async def setup(bot):
    await bot.add_cog(Lottery(bot))
