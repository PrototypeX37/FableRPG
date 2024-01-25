import asyncio
import datetime
import string
from collections import Counter

import discord
from discord.ext import commands, tasks
import random
from PIL import Image, ImageDraw, ImageFont
import io
import requests
from cogs.shard_communication import user_on_cooldown as user_cooldown
from utils.checks import has_char, is_gm


class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # -------Health Init------------
        self.player_hp = 100
        self.dragon_hp = 150

        # -------Health Events Player------------
        self.Heal = 15
        self.Shield = 0
        self.Trip = -5

        # -------Health Events Dragon------------
        self.Attack = 5
        self.Magic = 10

        # -------Health Events DragonATK------------
        self.DragonAttack = 5

        self.timeout_duration = 600  # 10 minutes

        # Create a dictionary to store user timeouts
        self.user_timeouts = {}

        # Start a task to check for timeouts
        self.check_timeouts.start()

        self.captcha_lock = {}

        # --------------------------------------------

        self.logger = 0

    @has_char()
    @user_cooldown(6)
    @commands.group()
    async def slots(self, ctx):

        if ctx.invoked_subcommand is None:

            updated_dragon = 1
            updated_player = 1

            try:
                async with self.bot.pool.acquire() as connection:
                    # Check if the user's ID exists in any row's 'occupant' column
                    result = await connection.fetchrow("SELECT seat FROM dragonslots WHERE occupant = $1",
                                                       ctx.author.id)

                    if result:
                        seat = result['seat']
                        await self.update_last_activity(ctx.author.id)
                    else:
                        return await ctx.send("You are not in a slot seat.")
            except Exception as e:
                return await ctx.send(f"An error occurred: {e}")

            if self.is_user_captcha_locked(ctx.author.id):
                await ctx.send("You are captcha locked.")
                return

            verifycheck = random.randint(1, 100)
            if verifycheck <= 1:

                captcha_text = self.generate_distorted_captcha()

                try:

                    # Generate and send the CAPTCHA
                    captcha_text = self.generate_distorted_captcha()
                    await ctx.send(f"{ctx.author.mention} Enter the CAPTCHA Text below. You have 60 seconds",
                                   file=discord.File('captcha.png'))

                    # Add the user to the captcha lock
                    self.captcha_lock[ctx.author.id] = captcha_text

                    # Wait for the user to solve the CAPTCHA
                    try:
                        await self.bot.wait_for(
                            'message',
                            check=lambda msg: msg.author == ctx.author and msg.content.lower() == captcha_text.lower(),
                            timeout=60  # Adjust the timeout as needed
                        )
                    except asyncio.TimeoutError:
                        try:
                            async with self.bot.pool.acquire() as connection:
                                # Check if the user is currently occupying a seat
                                seat_info = await connection.fetchrow("SELECT * FROM dragonslots WHERE occupant = $1",
                                                                      ctx.author.id)

                                if seat_info:
                                    seat_number = seat_info['seat']

                                    # Clear the seat for the user
                                    await connection.execute(
                                        "UPDATE dragonslots SET occupant = NULL, last_activity = NULL WHERE seat = $1",
                                        seat_number)

                                    await self.send_locked_message(ctx.author)

                                    await ctx.send("You are now CAPTCHA Locked. Use `$unlock` to unlock the CAPTCHA.")

                                else:
                                    await self.send_locked_message(ctx.author)
                        except Exception as e:
                            await ctx.send(f"An error occurred: {e}")
                        return

                    # Remove the user from the captcha lock
                    await ctx.send("CAPTCHA Verification Successful")
                    del self.captcha_lock[ctx.author.id]

                except Exception as e:
                    await ctx.send(str(e))

            try:
                async with self.bot.pool.acquire() as connection:
                    result = await connection.fetch('SELECT money FROM profile WHERE "user" = $1', ctx.author.id)
                    if result:
                        money = result[0]['money']
                    else:
                        return await ctx.send("User not found in the database.")
            except Exception as e:
                return await ctx.send(f"An error occurred: {e}")

            if money < 2000:
                return await ctx.send("You are too poor.")
            else:
                try:
                    async with self.bot.pool.acquire() as connection:
                        # Deduct 2000 from the user's money
                        await connection.execute('UPDATE profile SET money = money - $1 WHERE "user" = $2', 1500,
                                                 ctx.author.id)
                        if ctx.author.id == 708435868842459169:
                            self.logger = self.logger - 1500
                        await connection.execute('UPDATE dragonslots SET jackpot = jackpot + $1 WHERE seat = $2', 1000,
                                                 seat)

                        jackpot_result = await connection.fetchval('SELECT jackpot FROM dragonslots WHERE seat = $1',
                                                                   seat)
                except Exception as e:
                    return await ctx.send(f"An error occurred while deducting money: {e}")

            try:
                # Emoji slots with adjusted probabilities
                # emojis = ["🐉", "🍏"]  # Add more emojis as needed
                emojis = ["🍎", "🍒", "🍊", "🐉", "🍏", "🍓", "🍍"]  # Add more emojis as needed

                # Generate three random emojis for the slots

                fruit_values = {
                    "🐉": 1000,
                    "🍒": 1000,
                    "🍎": 2000,
                    "🍊": 2500,
                    "🍏": 4000,
                    "🍓": 4500,
                    "🍍": 7500,  # Adjusted value for 🍍 to cover the base value (2000) for 2 pineapples
                }

                # Generate three random emojis for the slots with adjusted probabilities
                emojis = list(fruit_values.keys())  # List of available emojis
                weights = [2, 4, 3, 2, 1, 1, 1]  # Adjusted weights for each fruit
                slot_results = random.choices(emojis, weights=weights, k=3)

                # Count the occurrences of each fruit in the slots
                fruit_counts = Counter(slot_results)
                dragon_count = slot_results.count("🐉")

                # Check for matching fruits in adjacent slots or all 3 slots
                if len(set(slot_results)) == 1:
                    # All three slots have the same fruit
                    total_reward = 5 * fruit_values[slot_results[0]]
                elif len(set(slot_results)) == 2 and any(count == 2 for count in fruit_counts.values()):
                    # Two different fruits, and one of them appears twice (it's a pair)
                    total_reward = 2 * sum(fruit_values[fruit] for fruit, count in fruit_counts.items() if count == 2)
                else:
                    # No matching pair or three of a kind
                    total_reward = 0

                if total_reward != 0:
                    async with self.bot.pool.acquire() as connection:
                        await connection.execute('UPDATE profile SET money = money + $1 WHERE "user" = $2',
                                                 total_reward,
                                                 ctx.author.id)

                        if ctx.author.id == 708435868842459169:
                            self.logger = self.logger + total_reward

                # Send an embed with the slot machine result, reward, and jackpot
                embed = discord.Embed(title="Slot Machine Result", color=discord.Color.blurple())
                embed.add_field(name="Slot 1", value=slot_results[0], inline=True)
                embed.add_field(name="Slot 2", value=slot_results[1], inline=True)
                embed.add_field(name="Slot 3", value=slot_results[2], inline=True)
                embed.add_field(name="**Reward**", value=f"${total_reward}", inline=False)
                embed.add_field(name="Jackpot", value=f"${jackpot_result}", inline=False)
                await ctx.send(embed=embed)

                if dragon_count > 0:
                    if dragon_count == 1:
                        await ctx.send(f"{ctx.author.display_name}, You rolled a dragon! Initiating attack sequence...")
                    else:
                        await ctx.send(
                            f"You rolled {dragon_count} dragons! Initiating {dragon_count} attack sequence{'s' if dragon_count > 1 else ''}...")

                    # Continue with any additional messages or actions here

                    # For each dragon rolled
                    for i in range(1, dragon_count + 1):
                        await asyncio.sleep(1)
                        # Load the image outside the loop
                        background_url = 'https://gcdnb.pbrd.co/images/rRY9QY0g3iHC.png'
                        bg_image = Image.open(requests.get(background_url, stream=True).raw)

                        # Specify the font file path
                        font_path = 'EightBitDragon-anqx.ttf'

                        # Load the Eight Bit Dragon font
                        dragonHP_font = ImageFont.truetype(font_path, size=38)
                        HeroHP_font = ImageFont.truetype(font_path, size=33)

                        # Draw HP values on the image
                        draw = ImageDraw.Draw(bg_image)

                        font_size = 20

                        random_number = random.randint(1, 5)

                        # Handle the action for each dragon
                        if random_number == 1:
                            async with self.bot.pool.acquire() as connection:
                                await connection.execute(
                                    'UPDATE dragonslots SET dragon = dragon - $1, player = player - $2 WHERE seat = $3',
                                    5,
                                    5, seat)
                                updated_values = await connection.fetchrow(
                                    'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                updated_dragon = updated_values['dragon']
                                updated_player = updated_values['player']

                            await ctx.send(
                                f"{ctx.author.display_name}, You attacked the dragon for **5 DMG!** It now has {updated_dragon}! You took **5 DMG** and now have {updated_player}.")
                            await asyncio.sleep(1)

                        if random_number == 2:
                            await ctx.send(
                                f"{ctx.author.display_name}, You have defended yourself against the dragon. You took 0 damage!")
                            async with self.bot.pool.acquire() as connection:
                                updated_values = await connection.fetchrow(
                                    'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                updated_dragon = updated_values['dragon']
                                updated_player = updated_values['player']
                            await asyncio.sleep(1)

                        if random_number == 3:
                            triphurt = random.randint(1, 10)
                            if triphurt <= 5:
                                async with self.bot.pool.acquire() as connection:
                                    await connection.execute(
                                        'UPDATE dragonslots SET player = player - $1 WHERE seat = $2',
                                        5,
                                        seat)
                                    updated_values = await connection.fetchrow(
                                        'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                    updated_dragon = updated_values['dragon']
                                    updated_player = updated_values['player']

                                await ctx.send(
                                    f"{ctx.author.display_name}, You tripped! You are vulnerable and took **5 DMG!** You now have {updated_player}!")
                                await asyncio.sleep(1)

                            else:
                                async with self.bot.pool.acquire() as connection:
                                    await connection.execute(
                                        'UPDATE dragonslots SET player = player - $1 WHERE seat = $2',
                                        10,
                                        seat)
                                    updated_values = await connection.fetchrow(
                                        'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                    updated_dragon = updated_values['dragon']
                                    updated_player = updated_values['player']

                                await ctx.send(
                                    f"Oops, {ctx.author.display_name}! You stumbled and sustained significant injuries, "
                                    f"leaving you vulnerable. You've taken **10 DMG**. Your current HP is now "
                                    f"{updated_player}!"
                                )

                                await asyncio.sleep(1)

                        if random_number == 4:
                            async with self.bot.pool.acquire() as connection:
                                await connection.execute(
                                    'UPDATE dragonslots SET dragon = dragon - $1, player = player - $2 WHERE seat = $3',
                                    10,
                                    5, seat)
                                updated_values = await connection.fetchrow(
                                    'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                updated_dragon = updated_values['dragon']
                                updated_player = updated_values['player']

                            await ctx.send(
                                f"{ctx.author.display_name}, You cast a powerful spell! The dragon took **10 DMG!** It now has {updated_dragon}! You took **5 DMG** and now have {updated_player}.")
                            await asyncio.sleep(1)

                        if random_number == 5:
                            async with self.bot.pool.acquire() as connection:
                                await connection.execute('UPDATE dragonslots SET player = player - $1 WHERE seat = $2',
                                                         5,
                                                         seat)
                                updated_values = await connection.fetchrow(
                                    'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                updated_dragon = updated_values['dragon']
                                updated_player = updated_values['player']

                            healthluck = random.randint(1, 11)

                            if healthluck <= 5:

                                if updated_player < 85:

                                    async with self.bot.pool.acquire() as connection:
                                        await connection.execute(
                                            'UPDATE dragonslots SET player = player + $1 WHERE seat = $2',
                                            10,
                                            seat)
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_player = updated_values['player']

                                    await ctx.send(
                                        f"{ctx.author.display_name}, You cast a healing spell! You heal yourself for **10 HP!** You took **5 DMG** from the dragon and now have {updated_player}.")
                                    await asyncio.sleep(1)
                                    async with self.bot.pool.acquire() as connection:
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_dragon = updated_values['dragon']
                                        updated_player = updated_values['player']
                                else:

                                    async with self.bot.pool.acquire() as connection:
                                        await connection.execute('UPDATE dragonslots SET player = $1 WHERE seat = $2',
                                                                 95,
                                                                 seat)
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_player = updated_values['player']

                                    await ctx.send(
                                        f"{ctx.author.display_name}, You cast a healing spell! You heal yourself to **100 HP!** You took **5 DMG** from the dragon and now have {updated_player}.")
                                    await asyncio.sleep(1)
                                    async with self.bot.pool.acquire() as connection:
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_dragon = updated_values['dragon']
                                        updated_player = updated_values['player']

                            else:
                                if updated_player < 85:

                                    async with self.bot.pool.acquire() as connection:
                                        await connection.execute(
                                            'UPDATE dragonslots SET player = player + $1 WHERE seat = $2',
                                            15,
                                            seat)
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_player = updated_values['player']

                                    await ctx.send(
                                        f"{ctx.author.display_name}, You cast a healing spell! You heal yourself for **15 HP!** You took **5 DMG** from the dragon and now have {updated_player}.")
                                    await asyncio.sleep(1)
                                    async with self.bot.pool.acquire() as connection:
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_dragon = updated_values['dragon']
                                        updated_player = updated_values['player']
                                else:

                                    async with self.bot.pool.acquire() as connection:
                                        await connection.execute('UPDATE dragonslots SET player = $1 WHERE seat = $2',
                                                                 95,
                                                                 seat)
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_player = updated_values['player']

                                    await ctx.send(
                                        f"{ctx.author.display_name}, You cast a healing spell! You heal yourself to **100 HP!** You took **5 DMG** from the dragon and now have {updated_player}.")
                                    await asyncio.sleep(1)
                                    async with self.bot.pool.acquire() as connection:
                                        updated_values = await connection.fetchrow(
                                            'SELECT dragon, player FROM dragonslots WHERE seat = $1', seat)
                                        updated_dragon = updated_values['dragon']
                                        updated_player = updated_values['player']

                        if updated_player < 0:
                            updated_player = 0

                        if updated_dragon < 0:
                            updated_dragon = 0

                        # Draw Player's HP
                        draw.text((80, 391), f"{updated_player}", font=HeroHP_font, fill="cyan")

                        # Draw Dragon's HP
                        draw.text((673, 10), f"{updated_dragon}", font=dragonHP_font, fill="white")

                        # Trigger the event based on the number of dragon emojis
                        await self.run_special_event(ctx, bg_image, draw, i, random_number, seat)

            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

    async def run_special_event(self, ctx, bg_image, draw, image_index, random_number, seat):
        # Your existing code for the special event

        locations = [
            [(228, 369), (354, 402)],
            [(228, 402), (354, 437)],
            [(425, 369), (500, 402)],
            [(425, 402), (590, 437)],
            [(615, 369), (710, 402)],
        ]
        rectangle_location = locations[random_number - 1]
        corner_radius = 20
        draw.rounded_rectangle(rectangle_location, corner_radius, outline="red")

        # Save the image to a BytesIO object
        image_buffer = io.BytesIO()
        bg_image.save(image_buffer, format="PNG")
        image_buffer.seek(0)

        # Send the modified image
        await ctx.send(file=discord.File(image_buffer, filename=f"modified_image_{image_index}.png"))

        async with self.bot.pool.acquire() as connection:
            # Check dragon's HP after the special event
            dragon_hp = await connection.fetchval('SELECT dragon FROM dragonslots WHERE seat = $1', seat)
            player_hp = await connection.fetchval('SELECT player FROM dragonslots WHERE seat = $1', seat)

            if dragon_hp <= 0:
                jackpot = random.randint(10000, 50000)
                # If dragon's HP is 0 or less, reward the player with the jackpot
                jackpot_value = await connection.fetchval('SELECT jackpot FROM dragonslots WHERE seat = $1', seat)
                await connection.execute('UPDATE profile SET money = money + $1 WHERE "user" = $2', jackpot_value,
                                         ctx.author.id)
                if ctx.author.id == 708435868842459169:
                    self.logger = self.logger + jackpot_value

                # Reset dragon's HP and jackpot for the next round (adjust values as needed)
                await connection.execute(
                    'UPDATE dragonslots SET dragon = 125, player = 100, jackpot = $1 WHERE seat = $2', jackpot, seat)
                await ctx.send(
                    f"💎💎💎JACKPOT!💎💎💎: {ctx.author.mention}, You defeated by the dragon and earned a jackpot of **${jackpot_value}!**")
                return

            if player_hp <= 0:
                # If dragon's HP is 0 or less, reward the player with the jackpot

                # Reset dragon's HP and jackpot for the next round (adjust values as needed)
                await connection.execute(
                    'UPDATE dragonslots SET dragon = 125, player = 100 WHERE seat = $1', seat)
                await ctx.send(
                    f"💀💀💀DEFEATED!💀💀💀: {ctx.author.display_name}, You were defeated by the dragon!**")

    @has_char()
    @slots.command()
    async def seats(self, ctx):

        try:
            embed = discord.Embed(title="Seat Information", color=discord.Color.blurple())

            async with self.bot.pool.acquire() as connection:
                for seat_number in range(1, 17):
                    seat_info = await connection.fetchrow("SELECT * FROM dragonslots WHERE seat = $1", seat_number)

                    if seat_info:
                        occupant_id = seat_info['occupant']
                        occupant_name = "Seat free" if occupant_id is None else self.bot.get_user(occupant_id).name
                        dragon_hp = seat_info['dragon']
                        player_hp = seat_info['player']
                        jackpot = seat_info['jackpot']

                        embed.add_field(
                            name=f"Seat #{seat_number}",
                            value=f"Occupant: {occupant_name}\n"
                                  f"Dragon HP: {dragon_hp} 🐉 \n"
                                  f"Player HP: {player_hp} 👤 \n"
                                  f"Jackpot: {jackpot} 💰",
                            inline=False
                        )

                await ctx.send(embed=embed)


        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    def cog_unload(self):
        # Stop the timeout check task when the cog is unloaded
        self.check_timeouts.cancel()

    @tasks.loop(seconds=60)
    async def check_timeouts(self):
        # Check for timeouts every minute
        now = datetime.datetime.utcnow()

        async with self.bot.pool.acquire() as connection:
            for seat_info in await connection.fetch("SELECT seat, occupant, last_activity FROM dragonslots"):
                seat_number = seat_info['seat']
                occupant_id = seat_info['occupant']
                last_activity = seat_info['last_activity']

                if occupant_id and (now - last_activity).total_seconds() > self.timeout_duration:
                    # If the occupant has timed out, clear the seat
                    await connection.execute(
                        "UPDATE dragonslots SET occupant = NULL, last_activity = NULL WHERE seat = $1", seat_number)
                    user = self.bot.get_user(occupant_id)
                    if user:
                        await user.send(
                            f"{user.mention}You have been automatically removed from seat #{seat_number} due to inactivity.")

    async def update_last_activity(self, occupant_id):
        async with self.bot.pool.acquire() as connection:
            await connection.execute("UPDATE dragonslots SET last_activity = $1 WHERE occupant = $2",
                                     datetime.datetime.utcnow(), occupant_id)

    @slots.command()
    @user_cooldown(300)
    @has_char()
    async def takeseat(self, ctx, seat_number: int):


        if ctx.author.id in self.captcha_lock:
            await ctx.send("You are not currently locked by CAPTCHA verification.")
            self.bot.reset_cooldown(ctx)
            return
        try:
            async with self.bot.pool.acquire() as connection:
                # Check if the user is currently occupying a seat
                current_seat = await connection.fetchrow("SELECT * FROM dragonslots WHERE occupant = $1", ctx.author.id)

                if current_seat:
                    current_seat_number = current_seat['seat']
                    await ctx.send(
                        f"{ctx.author.display_name}, You are already occupying seat #{current_seat_number}. Please leave that seat before taking a new one.")
                    self.bot.reset_cooldown(ctx)
                    return
                else:
                    # Check if the seat exists
                    seat_info = await connection.fetchrow("SELECT * FROM dragonslots WHERE seat = $1", seat_number)

                    if seat_info:
                        occupant_id = seat_info['occupant']

                        # Check if the seat is already occupied
                        if occupant_id is None:
                            # Seat is free, assign the user to the seat
                            await connection.execute(
                                "UPDATE dragonslots SET occupant = $1, last_activity = $2 WHERE seat = $3",
                                ctx.author.id, datetime.datetime.utcnow(), seat_number)
                            await ctx.send(f"{ctx.author.mention} has taken seat #{seat_number}! Will be kicked after "
                                           f"10 minutes of inactivity.")
                            await self.update_last_activity(ctx.author.id)
                        else:
                            # Seat is occupied
                            occupant_name = self.bot.get_user(occupant_id).name
                            await ctx.send(f"Sorry, seat #{seat_number} is already taken by {occupant_name}.")
                            self.bot.reset_cooldown(ctx)
                    else:
                        await ctx.send(f"Seat #{seat_number} does not exist.")
                        self.bot.reset_cooldown(ctx)

        except Exception as e:
            await ctx.send(f"An error occurred: {e}")


    @is_gm()
    @commands.command()
    async def gmjpforce(self, ctx):
        try:
            async with self.bot.pool.acquire() as connection:
                # Get a list of all seat numbers
                seat_numbers = await connection.fetch('SELECT seat FROM dragonslots')

                for seat_info in seat_numbers:
                    seat_number = seat_info['seat']

                    # Check if the seat is not occupied
                    occupied_seat = await connection.fetchval(
                        'SELECT seat FROM dragonslots WHERE seat = $1 AND occupant IS NOT NULL', seat_number)

                    if not occupied_seat:
                        # Generate a random value between 15000 and 45000
                        random_value = random.randint(10000, 45000)

                        # Increase the jackpot by the random value for the specific seat
                        await connection.execute('UPDATE dragonslots SET jackpot = jackpot + $1 WHERE seat = $2',
                                                 random_value, seat_number)
        except Exception as e:
            await ctx.send(e)

    async def increase_jackpot_periodically(self, ctx):
        while True:

            try:
                async with self.bot.pool.acquire() as connection:
                    # Get a list of all seat numbers
                    seat_numbers = await connection.fetch('SELECT seat FROM dragonslots')

                    for seat_info in seat_numbers:
                        seat_number = seat_info['seat']

                        # Check if the seat is not occupied
                        occupied_seat = await connection.fetchval(
                            'SELECT seat FROM dragonslots WHERE seat = $1 AND occupant IS NOT NULL', seat_number)

                        if not occupied_seat:
                            # Generate a random value between 15000 and 45000
                            random_value = random.randint(10000, 45000)

                            # Increase the jackpot by the random value for the specific seat
                            await connection.execute('UPDATE dragonslots SET jackpot = jackpot + $1 WHERE seat = $2',
                                                     random_value, seat_number)
                await asyncio.sleep(21600)

            except Exception as e:
                # Handle exceptions appropriately
                await ctx.send(f"An error occurred while increasing jackpot: {e}")

            # Sleep for 1 hour (3600 seconds) after the update

    # ... (existing code)

    @is_gm()
    @commands.command()
    async def gmjptimer(self, ctx):
        # Start the periodic increase of jackpot in a separate task
        self.bot.loop.create_task(self.increase_jackpot_periodically(ctx))
        await ctx.send("Jackpot increase has been started.")

    @has_char()
    @slots.command()
    async def leaveseat(self, ctx):

        captcha_text = self.generate_distorted_captcha()

        try:

            # Generate and send the CAPTCHA
            captcha_text = self.generate_distorted_captcha()
            await ctx.send(f"{ctx.author.mention} to prevent botting, enter the CAPTCHA Text as it is exactly below. You have 60 seconds",
                           file=discord.File('captcha.png'))

            # Add the user to the captcha lock
            self.captcha_lock[ctx.author.id] = captcha_text

            # Wait for the user to solve the CAPTCHA
            try:
                await self.bot.wait_for(
                    'message',
                    check=lambda msg: msg.author == ctx.author and msg.content.lower() == captcha_text.lower(),
                    timeout=60  # Adjust the timeout as needed
                )
            except asyncio.TimeoutError:
                try:
                    async with self.bot.pool.acquire() as connection:
                        await self.send_locked_message(ctx.author)
                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")
                return

            # Remove the user from the captcha lock
            await ctx.send("CAPTCHA Verification Successful")
            del self.captcha_lock[ctx.author.id]
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

        try:
            async with self.bot.pool.acquire() as connection:
                # Check if the user is currently occupying a seat
                seat_info = await connection.fetchrow("SELECT * FROM dragonslots WHERE occupant = $1", ctx.author.id)

                if seat_info:
                    seat_number = seat_info['seat']

                    # Clear the seat for the user
                    await connection.execute(
                        "UPDATE dragonslots SET occupant = NULL, last_activity = NULL WHERE seat = $1", seat_number)

                    await ctx.send(f"{ctx.author.mention} has left seat #{seat_number}!")
                else:
                    await ctx.send(f"{ctx.author.display_name}, You are not currently occupying any seat.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    def add_to_captcha_lock(self, user_id, captcha_text):
        self.captcha_lock[user_id] = captcha_text

    def is_user_captcha_locked(self, user_id):
        return user_id in self.captcha_lock

    async def send_locked_message(self, user):
        locked_channel = self.bot.get_channel(1199299210059710504)
        if locked_channel:
            await locked_channel.send(f"{user.name}#{user.discriminator} failed the CAPTCHA and is now locked.")

    async def init_database(self):
        async with self.bot.pool.acquire() as connection:
            # Delete all rows from the 'dragonslots' table
            await connection.execute("DELETE FROM dragonslots")

            # Insert 8 rows into the 'dragonslots' table
            for seat_number in range(1, 17):
                dragon_hp = 125
                player_hp = 100
                jackpot = random.randint(10000, 50000)

                await connection.execute(
                    "INSERT INTO dragonslots(seat, dragon, player, jackpot) VALUES($1, $2, $3, $4)",
                    seat_number, dragon_hp, player_hp, jackpot
                )

    @is_gm()
    @commands.command()
    async def gmdragonslotreset(self, ctx):
        try:
            await self.init_database()
            await ctx.send("Dragon slots have been reset successfully!")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    def generate_distorted_captcha(self):
        captcha_text = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

        captcha_text = captcha_text.replace('l', 'L')

        width, height = 300, 100
        background_color = 'white'
        image = Image.new('RGB', (width, height), background_color)
        draw = ImageDraw.Draw(image)

        font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        font_size = 30
        font = ImageFont.truetype(font_path, font_size)

        letter_colors = ['red', 'green', 'blue', 'purple', 'orange']
        outline_thickness = 3  # Adjust the thickness of the outline

        # Draw additional random shapes on the background
        for _ in range(50):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            shape_type = random.choice(['ellipse', 'line'])
            shape_color = random.choice(['red', 'green', 'blue', 'purple', 'orange'])
            size = random.randint(2, 5)
            self.draw_random_shape(draw, x, y, shape_type, shape_color, size, outline_thickness)

        for i, char in enumerate(captcha_text):
            angle = random.uniform(-30, 30)
            x = i * width / 6
            y = random.uniform(0, height / 2)
            color = random.choice(letter_colors)

            for _ in range(random.randint(1, 3)):
                shape_type = random.choice(['ellipse', 'line'])
                shape_color = random.choice(['red', 'green', 'blue', 'purple', 'orange'])
                size = random.randint(1, 5)
                self.draw_random_shape(draw, x, y, shape_type, shape_color, size, outline_thickness)

            draw.text((x, y), char, font=font, fill=color, angle=angle, anchor='lt', align='left')

        image.save('captcha.png')
        return captcha_text

    def draw_random_shape(self, draw, x, y, shape_type, shape_color, size, outline_thickness):
        if shape_type == 'ellipse':
            draw.ellipse((x, y, x + size, y + size), outline=shape_color, width=outline_thickness)
        elif shape_type == 'line':
            x2, y2 = x + random.randint(10, 30), y + random.randint(10, 30)
            draw.line([(x, y), (x2, y2)], fill=shape_color, width=outline_thickness)

    @is_gm()
    @commands.command()
    async def captcha(self, ctx):
        try:
            captcha_text = self.generate_distorted_captcha()
            await ctx.send(f"Enter the CAPTCHA Text below. You have 60 seconds", file=discord.File('captcha.png'))
        except Exception as e:
            await ctx.send(str(e))

    @commands.command()
    async def logslots(self, ctx):
        if ctx.author.id == 708435868842459169:
            if self.logger == 0:
                await ctx.send("Logging has started for ID: 708435868842459169")
                return
            else:
                await ctx.send(f"Logged profits so far: {self.logger}")
                return
        else:
            return await ctx.send("Access Denied")

    @is_gm()
    @commands.command()
    async def gmunlock(self, ctx, DiscordID: int):
        DiscordID_str = str(DiscordID).strip()
        # await ctx.send(self.captcha_lock)

        if DiscordID_str in map(str, self.captcha_lock.keys()):
            user = self.captcha_lock[DiscordID]
            await ctx.send(f"You have unlocked {user} ({DiscordID}).")
            del self.captcha_lock[DiscordID]
        else:
            await ctx.send("User not found.")

    @commands.command()
    @has_char()
    async def unlock(self, ctx):

        if ctx.author.id not in self.captcha_lock:
            await ctx.send("You are not currently locked by CAPTCHA verification.")
            return

        captcha_text = self.generate_distorted_captcha()

        try:

            # Generate and send the CAPTCHA
            captcha_text = self.generate_distorted_captcha()
            await ctx.send(f"{ctx.author.mention} to prevent botting, enter the CAPTCHA Text as it is exactly below. You have 60 seconds",
                           file=discord.File('captcha.png'))

            # Add the user to the captcha lock
            self.captcha_lock[ctx.author.id] = captcha_text

            # Wait for the user to solve the CAPTCHA
            try:
                await self.bot.wait_for(
                    'message',
                    check=lambda msg: msg.author == ctx.author and msg.content.lower() == captcha_text.lower(),
                    timeout=60  # Adjust the timeout as needed
                )
            except asyncio.TimeoutError:
                try:
                    async with self.bot.pool.acquire() as connection:
                        await self.send_locked_message(ctx.author)
                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")
                return

            # Remove the user from the captcha lock
            await ctx.send("CAPTCHA Verification Successful")
            del self.captcha_lock[ctx.author.id]
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")


async def setup(bot):
    await bot.add_cog(Slots(bot))
