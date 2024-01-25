import discord
from discord.ext import commands

from utils.checks import is_gm


class ReloadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @is_gm()
    @commands.command(name="unload", hidden=True)
    async def unload_cog(self, ctx, cog_name: str):
        try:
            if ctx.author.id != 295173706496475136:
                return await ctx.send("Access Denied")
            # Unload the existing cog
            await self.bot.unload_extension(f"cogs.{cog_name}")
            await ctx.send("Unloading Cog...")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @is_gm()
    @commands.command(name="load", hidden=True)
    async def load_cog(self, ctx, cog_name: str):
        try:
            if ctx.author.id != 295173706496475136:
                if ctx.author.id != 708435868842459169:
                    return await ctx.send("Access Denied")
            # Unload the existing cog
            await ctx.send("Loading Cog...")
            # Reload the cog using Discord.py's reload_extension
            await self.bot.load_extension(f"cogs.{cog_name}")
            await ctx.send(f"{cog_name} has been reloaded.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @is_gm()
    @commands.command(name="reload", hidden=True)
    async def reload_cog(self, ctx, cog_name: str):
        try:
            # Unload the existing cog
            await self.bot.unload_extension(f"cogs.{cog_name}")
            await ctx.send("Reloading Cog...")
            # Reload the cog using Discord.py's reload_extension
            await self.bot.load_extension(f"cogs.{cog_name}")
            await ctx.send(f"{cog_name} has been reloaded.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")


async def setup(bot):
    await bot.add_cog(ReloadCog(bot))
