from io import BytesIO
import aiohttp
import discord


class DiscordAgent:
    def __init__(self, bot=None):
        self.bot = bot

    def get_user_by_id(self, user_id: str):
        try:
            clean_id = "".join(filter(str.isdigit, user_id))
            return discord.Client.get_user((int(clean_id)))
        except discord.NotFound:
            return None
        except ValueError:
            return None

    def get_channel_by_id(self, channel_id: str):
        try:
            clean_id = "".join(filter(str.isdigit, channel_id))
            return discord.Client.get_channel((int(clean_id)))
        except discord.NotFound:
            return None
        except ValueError:
            return None

    async def get_users_in_message(self, message: discord.Message):
        try:
            members = message.channel.members
            return [
                {
                    "id": member.id,
                    "display_name": member.display_name,
                    "name": member.name,
                }
                for member in members
            ]
        except discord.NotFound:
            return None
    
    async def get_channel_mentions_in_message(self, message: discord.Message):
        try:
            channels = message.channel_mentions
            return [
                {
                    "id": channel.id,
                    "guild_id": channel.guild.id,
                    "name": channel.name,
                }
                for channel in channels
            ]
        except discord.NotFound:
            return None
    
    # Convert string IDs to Discord User objects
    def get_user_mentions(self, user_mentions: list[str]):
        discord_users = []
        for user_id in user_mentions:
            user = self.get_user_by_id(user_id)
            if user:
                discord_users.append(user)
        return discord_users
    
    # Convert string IDs to Discord Channel objects
    def get_channel_mentions(self, channel_mentions: list[str]):
        channels = []
        for channel_id in channel_mentions:
            channel = self.get_channel_by_id(channel_id)
            if channel:
                channels.append(channel)
        return channels

    async def create_group_chat(
        self,
        message: discord.Message,
        user_mentions: list[str],
    ):
        discord_users = self.get_user_mentions(user_mentions)

        # Check if we found any valid users
        if not discord_users:
            return "No valid users found. Please check the user IDs."

        # Create a list of usernames for the thread name
        mentioned_users = [user.display_name for user in discord_users]
        thread_name = f"Private Chat with {', '.join(mentioned_users)}"

        try:
            # Create a private thread
            thread = await message.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                invitable=False,  # Only moderators can add users
            )

            # Add mentioned users to the thread
            for user in discord_users:
                await thread.add_user(user)

            # Create mentions for the welcome message
            user_mentions_str = ", ".join([user.mention for user in discord_users])
            await thread.send(f"Private thread created! Welcome {user_mentions_str}!")

            return "Private thread created!"

        except discord.Forbidden:
            return "I don't have permission to create private threads!"
        except discord.HTTPException:
            return "Failed to create the thread. Please try again later."
    
    async def invite_member_to_channel(        
        self,
        message: discord.Message,
        user_mentions: list[str],
        channel_mentions: list[str]):

        discord_users = self.get_user_mentions(user_mentions)
        # Check if we found any valid users
        if not discord_users:
            return "No valid users found. Please check the user IDs."

        channels = self.get_channel_mentions(channel_mentions)
        # Check if we found any valid channels
        if not channels:
            return "No valid channels found. Please check the channel IDs."

        # Create a list of usernames for the thread name
        mentioned_users = [user.display_name for user in discord_users]
        mentioned_channels = [channel.name for channel in channels]
        res_message = await message.reply(f"Adding {', '.join(mentioned_users)} to Channel {', '.join(mentioned_channels)}")

        try:
            for channel in mentioned_channels:
                # Add mentioned users to the channel
                for user in discord_users:
                    await channel.add_user(user)
                    # Create mentions for the welcome message
                    user_mentions_str = ", ".join([user.mention for user in discord_users])
                    await channel.send(f"Welcome {user_mentions_str}!")
            await res_message.edit(content=f"Finished adding {', '.join(mentioned_users)} to Channel {', '.join(mentioned_channels)}")

        except discord.Forbidden:
            return "I don't have permission to add users to channels!"
        except discord.HTTPException:
            return "Failed to add users to channels. Please try again later."
    
        
    async def change_bot_avatar(self, message: discord.Message, bot_mention: discord.Member, url: str):
        if not bot_mention.bot:
            await message.channel.send("❌ The mentioned user is not a bot.")
            return

        # Clean up URL
        url = url.strip().strip('"\'')
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            await message.channel.send("❌ Invalid URL format. URL must start with http:// or https://")
            return

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/*'
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, ssl=False) as response:
                    if response.status == 200:
                        if not response.headers.get('content-type', '').startswith('image/'):
                            await message.channel.send("❌ The URL does not point to a valid image.")
                            return
                        
                        avatar_data = await response.read()
                        try:
                            await message.guild.me.edit(avatar=avatar_data)
                            await message.channel.send(f"✅ Bot avatar changed successfully!")
                        except discord.HTTPException as e:
                            await message.channel.send(f"❌ Error changing avatar: {str(e)}")
                    else:
                        await message.channel.send(f"❌ Failed to fetch image. Status code: {response.status}")
            except aiohttp.ClientError as e:
                await message.channel.send(f"❌ Error accessing URL: {str(e)}")

    async def prompt_change_avatar(self, message: discord.Message):
        await message.channel.send("Please mention the bot and provide the image URL to change its avatar.")

    async def handle_change_avatar(self, message: discord.Message, bot_mention: discord.Member = None, url: str = None):
        if not bot_mention or not url:
            await self.prompt_change_avatar(message)
            return

        await self.change_bot_avatar(message, bot_mention, url)

    async def change_bot_name(self, message: discord.Message, bot_mention: discord.Member, new_name: str = None):
        if not bot_mention.bot:
            await message.channel.send("❌ The mentioned user is not a bot.")
            return

        if not new_name:
            await message.channel.send("❌ Please provide a new name for the bot.")
            return

        try:
            await bot_mention.edit(nick=new_name)
            await message.channel.send(f"✅ Successfully changed bot's name to **{new_name}**!")
        except discord.Forbidden:
            await message.channel.send("❌ I don't have permission to change the bot's name.")
        except discord.HTTPException as e:
            await message.channel.send(f"❌ Failed to change name: {str(e)}")

    async def prompt_change_name(self, message: discord.Message):
        await message.channel.send("Please use the format: 'change the bot @botname name to <new_name>'")

    async def handle_change_name(self, message: discord.Message, bot_mention: discord.Member = None, new_name: str = None):
        if not bot_mention and not new_name:
            await message.channel.send("❌ Please mention the bot and provide a new name.")
            await self.prompt_change_name(message)
            return
        elif not bot_mention:
            await message.channel.send("❌ Please mention the bot you want to rename.")
            await self.prompt_change_name(message)
            return
        elif not new_name:
            await message.channel.send("❌ Please provide a new name for the bot.")
            await self.prompt_change_name(message)
            return

        await self.change_bot_name(message, bot_mention, new_name)
