import discord
from discord.ext import commands
import asyncio
from PIL import Image, ImageDraw, ImageEnhance
from io import BytesIO

from utils.checks import is_gm


class WarMap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def lerp(self, a, b, t):
        """Linear interpolation between a and b."""
        return a + (b - a) * t

    def gradient_arrow(self, draw, start, end, start_color, end_color, steps=100):
        """Draw an arrow with a gradient from start_color to end_color."""
        for i in range(steps):
            t = i / steps
            color = (
                int(self.lerp(start_color[0], end_color[0], t)),
                int(self.lerp(start_color[1], end_color[1], t)),
                int(self.lerp(start_color[2], end_color[2], t))
            )
            segment_start = (self.lerp(start[0], end[0], t), self.lerp(start[1], end[1], t))
            segment_end = (self.lerp(start[0], end[0], t + 1 / steps), self.lerp(start[1], end[1], t + 1 / steps))
            draw.line([segment_start, segment_end], fill=color, width=5)

        # Draw the arrowhead (triangle)
        arrowhead_length = 15
        arrowhead_width = 10
        arrow_direction = ((end[0] - start[0]), (end[1] - start[1]))
        arrow_direction_normalized = (
            arrow_direction[0] / (arrow_direction[0] ** 2 + arrow_direction[1] ** 2) ** 0.5,
            arrow_direction[1] / (arrow_direction[0] ** 2 + arrow_direction[1] ** 2) ** 0.5)

        point1 = end
        point2 = (
            end[0] - arrowhead_length * arrow_direction_normalized[0] + arrowhead_width * 0.5 *
            arrow_direction_normalized[1],
            end[1] - arrowhead_length * arrow_direction_normalized[1] - arrowhead_width * 0.5 *
            arrow_direction_normalized[0])
        point3 = (
            end[0] - arrowhead_length * arrow_direction_normalized[0] - arrowhead_width * 0.5 *
            arrow_direction_normalized[1],
            end[1] - arrowhead_length * arrow_direction_normalized[1] + arrowhead_width * 0.5 *
            arrow_direction_normalized[0])

        draw.polygon([point1, point2, point3], fill=end_color)

    @is_gm()
    @commands.command()
    async def warmap(self, ctx):
        try:
            await ctx.send("Generating War Map. Please wait..")

            await asyncio.sleep(1)

            await ctx.send("No current war, Showing Default Map..!")

            await asyncio.sleep(4)

            # Load your map
            base_map = Image.open("assets/conquest/Map.png")

            enhancer = ImageEnhance.Brightness(base_map)
            base_map = enhancer.enhance(0.65)  # Decrease brightness (0.7 is just an example, adjust as needed)

            # Load flags and resize them
            flag_size = (75, 150)
            asterea_flag = Image.open("assets/conquest/Good_Flag.png").resize(flag_size)
            sepulchre_flag = Image.open("assets/conquest/Evil_Flag.png").resize(flag_size)
            drakath_flag = Image.open("assets/conquest/Chaos_Flag.png").resize(flag_size)
            neutral_flag = Image.open("assets/conquest/Neutral.png").resize(flag_size)

            # Define predefined coordinates for territories
            territories_coords = {
                "Drakath": (1344, 306),
                "Zanjuro": (1172, 405),
                "OrderTemple": (944, 209),
                "Isyldill": (932, 500),
                "Shir": (1305, 822),
                "Ollin": (787, 702),
                "Sepulchre": (440, 874),
                "Lankerque": (710, 498),
                "DragonFoe": (552, 695),
                "Asterea": (119, 144),
                "BuhayCitadel": (327, 309),
                "BreftValley": (473, 135),
                "WellOfUnity": (615, 289),
                "Manumit": (260, 470),
                "BoneDunes": (157, 549),
                "DragonMountain": (75, 781),
                "Lakoldon": (468, 448),
                "Telfinor": (741, 179),
                "OnlookerPeak": (298, 774),
            }

            connections = [
                ("Drakath", "Zanjuro"),
                ("Zanjuro", "OrderTemple"),
                ("OrderTemple", "Isyldill"),
                ("Isyldill", "Shir"),
                ("Zanjuro", "Shir"),
                ("Shir", "Ollin"),
                ("Ollin", "Lankerque"),
                ("Sepulchre", "OnlookerPeak"),
                ("Lankerque", "DragonFoe"),
                ("Asterea", "BuhayCitadel"),
                ("BuhayCitadel", "BreftValley"),
                ("BreftValley", "WellOfUnity"),
                ("BuhayCitadel", "Manumit"),
                ("Manumit", "BoneDunes"),
                ("BoneDunes", "DragonMountain"),
                ("OnlookerPeak", "DragonMountain"),
                ("Lakoldon", "Manumit"),
                ("Lakoldon", "Lankerque"),
                ("Telfinor", "BreftValley"),
                ("Telfinor", "OrderTemple"),
                ("Lankerque", "WellOfUnity"),
                ("Lankerque", "Isyldill"),
                ("Isyldill", "WellOfUnity"),
                ("OnlookerPeak", "DragonFoe"),
            ]

            # Example data from your database (replace this with actual data)
            territories_control = {
                "Drakath": "Drakath",
                "Sepulchre": "Sepulchre",
                "Asterea": "Asterea",
            }

            # Overlay flags on territories
            color_map = {
                'Asterea': (255, 255, 0),
                'Sepulchre': (255, 0, 0),
                'Drakath': (128, 0, 128),
                'Neutral': (255, 255, 255)  # White color for neutral
            }

            # Overlay flags on territories
            for territory, coords in territories_coords.items():
                god = territories_control.get(territory, "Neutral")  # Default to "Neutral" if not found
                adjusted_coords = (coords[0] - flag_size[0] // 2, coords[1] - flag_size[1])

                flag_map = {
                    'Asterea': asterea_flag,
                    'Sepulchre': sepulchre_flag,
                    'Drakath': drakath_flag,
                    'Neutral': neutral_flag
                }
                flag = flag_map.get(god)

                if flag:
                    base_map.paste(flag, adjusted_coords, flag)

            draw = ImageDraw.Draw(base_map)

            # Draw arrows for connections and flags on top of arrows
            for start, end in connections:
                start_coords = territories_coords[start]
                end_coords = territories_coords[end]
                start_color = color_map.get(territories_control.get(start, "Neutral"))
                end_color = color_map.get(territories_control.get(end, "Neutral"))

                self.gradient_arrow(draw, start_coords, end_coords, start_color, end_color)

                # Place flags on top of the arrows
                start_flag = flag_map.get(territories_control.get(start, "Neutral"))
                end_flag = flag_map.get(territories_control.get(end, "Neutral"))

                if start_flag:
                    base_map.paste(start_flag, (start_coords[0] - flag_size[0] // 2, start_coords[1] - flag_size[1]),
                                   start_flag)
                if end_flag:
                    base_map.paste(end_flag, (end_coords[0] - flag_size[0] // 2, end_coords[1] - flag_size[1]),
                                   end_flag)

            # Save the Resulting Map
            base_map.save("result.png")

            # Load the generated map image
            map_image = Image.open("result.png")

            # Convert the PIL image to bytes
            image_bytes = BytesIO()
            map_image.save(image_bytes, format="PNG")
            image_bytes.seek(0)

            # Send the image to the Discord channel
            await ctx.send(file=discord.File(image_bytes, filename="result.png"))

        except Exception as e:
            # Handle exceptions and send an error message
            await ctx.send(f"An error occurred: {str(e)}")


async def setup(bot):
    await bot.add_cog(WarMap(bot))
