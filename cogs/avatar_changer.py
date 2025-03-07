import discord
from discord.ext import commands
import aiohttp

class AvatarChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='change_avatar', help='Change the bot\'s avatar. Usage: !change_avatar <image_url>')
    async def change_avatar(self, ctx, image_url: str):
        # Fetch the image from the provided URL
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    await ctx.send('Failed to fetch the image. Please ensure the URL is correct.')
                    return
                image_data = await response.read()

        # Ensure the image size is within Discord's limits (8 MB)
        if len(image_data) > 8 * 1024 * 1024:
            await ctx.send('The image is too large. Please provide an image smaller than 8 MB.')
            return

        # Change the bot's avatar
        try:
            await self.bot.user.edit(avatar=image_data)
            await ctx.send('The bot\'s avatar has been successfully updated!')

            # await ctx.author.edit(avatar=image_data)
            # await ctx.send('Your avatar has been successfully updated!')
        except discord.HTTPException as e:
            await ctx.send(f'Failed to update avatar: {e}')

async def setup(bot):
    await bot.add_cog(AvatarChanger(bot))

