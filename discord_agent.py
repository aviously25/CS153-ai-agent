from io import BytesIO
import aiohttp
import discord
import datetime


class DiscordAgent:
    def __init__(self, bot=None):
        self.bot = bot
        self.waiting_for_bot = {}
        self.waiting_for_role = {}  # Store user IDs waiting for role name
        self.waiting_for_member = {}  # Store user IDs waiting for member with role name
        self.role_for_member = {}  # Store role name waiting for member
        self.waiting_for_role_name = {}  # Store user IDs waiting for new role name
        self.waiting_for_revoke_role = {}  # Store user IDs waiting for role to revoke
        self.waiting_for_revoke_member = (
            {}
        )  # Store user IDs waiting for member to revoke from
        self.revoke_role_for_member = (
            {}
        )  # Store role name waiting for member to revoke from

    def get_user_by_id(self, user_id: str):
        try:
            clean_id = "".join(filter(str.isdigit, user_id)).strip()
            return self.bot.get_user(int(clean_id))
        except discord.NotFound:
            return None
        except ValueError:
            return None

    def get_channel_by_id(self, channel_id: str):
        try:
            clean_id = "".join(filter(str.isdigit, channel_id))
            return self.bot.get_channel((int(clean_id)))
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
        channel_mentions: list[str],
    ):

        discord_users = self.get_user_mentions(user_mentions)
        # Check if we found any valid users
        if not discord_users:
            return "No valid users found. Please check the user IDs."

        channels = self.get_channel_mentions(channel_mentions)
        # Check if we found any valid channels
        if not channels:
            return "No valid channels found. Please check the channel IDs."

        mentioned_users = [user.display_name for user in discord_users]
        mentioned_channels = [channel.name for channel in channels]
        res_message = await message.reply(
            f"Creating invites for {', '.join(mentioned_users)} to Channel {', '.join(mentioned_channels)}"
        )

        try:
            result_message = ''
            for channel in channels:
                result_message = result_message.join([channel.name, ":", "\n"])
                # Add mentioned users to the channel
                for user in discord_users:
                    invite = await channel.create_invite(max_uses=1,unique=True)
                    result_message = result_message.join([user.name, ":", invite.url, "\n"])
            await res_message.edit(
                content=f"Finished creating invites for {', '.join(mentioned_users)} to Channel {', '.join(mentioned_channels)}\nHere are the invite links:\n{result_message}."
            )

        except discord.Forbidden:
            return "I don't have permission to add users to channels!"
        except discord.HTTPException:
            return "Failed to add users to channels. Please try again later."

    async def mute_member_from_channel(
        self,
        message: discord.Message,
        user_mentions: list[str],
        channel_mentions: list[str],
    ):

        discord_users = self.get_user_mentions(user_mentions)
        # Check if we found any valid users
        if not discord_users:
            return "No valid users found. Please check the user IDs."

        channels = self.get_channel_mentions(channel_mentions)
        # Check if we found any valid channels
        if not channels:
            return "No valid channels found. Please check the channel IDs."

        mentioned_users = [user.display_name for user in discord_users]
        mentioned_channels = [channel.name for channel in channels]
        res_message = await message.reply(
            f"Muting {', '.join(mentioned_users)} from Channel {', '.join(mentioned_channels)}"
        )

        try:
            for channel in channels:
                # Remove mentioned users from the channel
                for user in discord_users:
                    perms = channel.overwrites_for(user)
                    perms.send_messages = False
                    await channel.set_permissions(user, overwrite=perms, reason="Muted!")
            await res_message.edit(
                content=f"Finished muting {', '.join(mentioned_users)} from Channel {', '.join(mentioned_channels)}"
            )

        except discord.Forbidden:
            return "I don't have permission to mute users to channels!"
        except discord.HTTPException:
            return "Failed to mute users to channels. Please try again later."

    async def unmute_member_from_channel(
        self,
        message: discord.Message,
        user_mentions: list[str],
        channel_mentions: list[str],
    ):

        discord_users = self.get_user_mentions(user_mentions)
        # Check if we found any valid users
        if not discord_users:
            return "No valid users found. Please check the user IDs."

        channels = self.get_channel_mentions(channel_mentions)
        # Check if we found any valid channels
        if not channels:
            return "No valid channels found. Please check the channel IDs."

        mentioned_users = [user.display_name for user in discord_users]
        mentioned_channels = [channel.name for channel in channels]
        res_message = await message.reply(
            f"Unmuting {', '.join(mentioned_users)} in Channel {', '.join(mentioned_channels)}"
        )

        try:
            for channel in channels:
                # Remove mentioned users from the channel
                for user in discord_users:
                    perms = channel.overwrites_for(user)
                    perms.send_messages = True
                    await channel.set_permissions(user, overwrite=perms, reason="Unmuted!")
            await res_message.edit(
                content=f"Finish unmuting {', '.join(mentioned_users)} in Channel {', '.join(mentioned_channels)}"
            )

        except discord.Forbidden:
            return "I don't have permission to unmute users to channels!"
        except discord.HTTPException:
            return "Failed to unmute users to channels. Please try again later."

    async def create_poll(
        self,
        message: discord.Message,
        question: str,
        answers: list[str],
        duration: int = 24,  # in hours
        multiple_answers: bool = False,  # whether multiple answers are allowed
    ):
        duration = datetime.timedelta(hours=duration)
        poll = discord.Poll(
            question=question,
            duration=duration,
        )

        for answer in answers:
            poll.add_answer(text=answer)

        await message.reply(poll=poll)
        return None

    async def change_bot_avatar(
        self, message: discord.Message, bot_mention: discord.Member, image_data: bytes
    ):
        if not bot_mention.bot:
            await message.channel.send("❌ The mentioned user is not a bot.")
            return

        if not image_data:
            await message.channel.send("❌ Please attach an image to change the bot's avatar.")
            return

        try:
            print(f"Attempting to change avatar for bot {bot_mention.name}")
            print(f"Image data size: {len(image_data)} bytes")
            # Use the correct parameter name for changing the avatar
            #await bot_mention.edit(avatar=image_data)
            await self.bot.user.edit(avatar=image_data)
            print("Avatar change successful")
            await message.channel.send(f"✅ Bot avatar changed successfully!")
        except discord.HTTPException as e:
            print(f"Error changing avatar: {str(e)}")
            await message.channel.send(f"❌ Error changing avatar: {str(e)}")

    async def prompt_change_avatar(self, message: discord.Message):
        await message.channel.send(
            "Please mention the bot and upload an image to change its avatar."
        )

    async def handle_change_avatar(
        self, 
        message: discord.Message, 
        bot_mention: discord.Member = None,
        image_data: bytes = None,
    ):
        user_id = message.author.id

        # If we have both bot and image, proceed with change
        if bot_mention and bot_mention.bot and image_data:
            await self.change_bot_avatar(message, bot_mention, image_data)
            return
        
        # Just prompt for complete instructions if anything is missing
        await self.prompt_change_avatar(message)
        return

    async def change_bot_name(
        self,
        message: discord.Message,
        bot_mention: discord.Member,
        new_name: str = None,
    ):
        if not bot_mention.bot:
            await message.channel.send("❌ The mentioned user is not a bot.")
            return

        if not new_name:
            await message.channel.send("❌ Please provide a new name for the bot.")
            return

        try:
            await bot_mention.edit(nick=new_name)
            await message.channel.send(
                f"✅ Successfully changed bot's name to **{new_name}**!"
            )
        except discord.Forbidden:
            await message.channel.send(
                "❌ I don't have permission to change the bot's name."
            )
        except discord.HTTPException as e:
            await message.channel.send(f"❌ Failed to change name: {str(e)}")

    async def prompt_change_name(self, message: discord.Message):
        await message.channel.send(
            "Please use the format: 'change the bot @botname name to <new_name>'"
        )

    async def handle_change_bot_name(
        self,
        message: discord.Message,
        bot_mention: discord.Member = None,
        new_name: str = None,
    ):
        if not bot_mention and not new_name:
            await message.channel.send(
                "❌ Please mention the bot and provide a new name."
            )
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


    async def assign_role(
        self, message: discord.Message, member: discord.Member, role_name: str
    ):
        """Assigns a role to a member."""
        if not message.guild.me.guild_permissions.manage_roles:
            await message.channel.send(
                "❌ I need the `Manage Roles` permission to assign roles."
            )
            return

        role = discord.utils.get(message.guild.roles, name=role_name)
        if not role:
            await message.channel.send(
                f"❌ Role '{role_name}' not found! Available roles: {', '.join([r.name for r in message.guild.roles])}"
            )
            return

        try:
            await member.add_roles(role)
            await message.channel.send(
                f"✅ Successfully assigned the **{role.name}** role to {member.display_name}!"
            )
        except discord.Forbidden:
            await message.channel.send(
                "❌ I don't have permission to assign this role."
            )
        except discord.HTTPException as e:
            await message.channel.send(f"❌ Failed to assign role: {str(e)}")

    async def prompt_assign_role(self, message: discord.Message):
        await message.channel.send(
            "To assign a role, use one of these formats:\n"
            "1. 'assign <role_name> role to @user'\n"
            "2. First mention the role, then the user\n"
            f"Available roles: {', '.join([r.name for r in message.guild.roles])}"
        )

    async def handle_assign_role(
        self,
        message: discord.Message,
        member: discord.Member = None,
        role_name: str = None,
    ):
        user_id = message.author.id

        # Handle response when waiting for role name
        if user_id in self.waiting_for_role:
            member = self.waiting_for_role.pop(user_id)
            role_name = message.content.strip()
            await self.assign_role(message, member, role_name)
            return

        # Handle response when waiting for member
        if user_id in self.waiting_for_member:
            if not message.mentions:
                await message.channel.send("❌ Please mention the user using @username")
                return
            role_name = self.waiting_for_member.pop(user_id)
            await self.assign_role(message, message.mentions[0], role_name)
            return

        # Initial request handling
        if not member and not role_name:
            await message.channel.send("❌ Please specify both the role and the user.")
            await self.prompt_assign_role(message)
            return
        elif not member:
            self.waiting_for_member[user_id] = role_name
            await message.channel.send(
                "Which user should get this role? (Please mention them using @)"
            )
            return
        elif not role_name:
            self.waiting_for_role[user_id] = member
            await message.channel.send(
                f"Which role should be assigned to {member.display_name}?\n"
                f"Available roles: {', '.join([r.name for r in message.guild.roles])}"
            )
            return

        await self.assign_role(message, member, role_name)


    async def create_role(self, message: discord.Message, role_name: str):
        """Creates a new role."""
        if not message.guild.me.guild_permissions.manage_roles:
            await message.channel.send(
                "❌ I need the `Manage Roles` permission to create roles."
            )
            return

        # Check if role already exists
        existing_role = discord.utils.get(message.guild.roles, name=role_name)
        if existing_role:
            await message.channel.send(f"❌ Role '{role_name}' already exists!")
            return

        try:
            await message.guild.create_role(name=role_name)
            await message.channel.send(f"✅ Successfully created role **{role_name}**!")
        except discord.Forbidden:
            await message.channel.send("❌ I don't have permission to create roles.")
        except discord.HTTPException as e:
            await message.channel.send(f"❌ Failed to create role: {str(e)}")

    async def prompt_create_role(self, message: discord.Message):
        await message.channel.send("What should the new role be called?")

    async def handle_create_role(self, message: discord.Message, role_name: str = None):
        user_id = message.author.id

        # Handle response when waiting for role name
        if user_id in self.waiting_for_role_name:
            role_name = message.content.strip()
            self.waiting_for_role_name.pop(user_id)
            await self.create_role(message, role_name)
            return

        # Initial request
        if not role_name:
            self.waiting_for_role_name[user_id] = True
            await self.prompt_create_role(message)
            return

        await self.create_role(message, role_name)

    async def revoke_role(
        self, message: discord.Message, member: discord.Member, role_name: str
    ):
        """Revokes a role from a member."""
        if not message.guild.me.guild_permissions.manage_roles:
            await message.channel.send(
                "❌ I need the `Manage Roles` permission to revoke roles."
            )
            return

        role = discord.utils.get(message.guild.roles, name=role_name)
        if not role:
            await message.channel.send(
                f"❌ Role '{role_name}' not found! Available roles: {', '.join([r.name for r in message.guild.roles])}"
            )
            return

        if role not in member.roles:
            await message.channel.send(
                f"❌ {member.display_name} doesn't have the role '{role_name}'"
            )
            return

        try:
            await member.remove_roles(role)
            await message.channel.send(
                f"✅ Successfully removed the **{role.name}** role from {member.display_name}!"
            )
        except discord.Forbidden:
            await message.channel.send(
                "❌ I don't have permission to revoke this role."
            )
        except discord.HTTPException as e:
            await message.channel.send(f"❌ Failed to revoke role: {str(e)}")

    async def prompt_revoke_role(self, message: discord.Message):
        await message.channel.send(
            "To revoke a role, use one of these formats:\n"
            "1. 'revoke <role_name> role from @user'\n"
            "2. First mention the role to revoke, then the user\n"
            f"Available roles: {', '.join([r.name for r in message.guild.roles])}"
        )

    async def handle_revoke_role(
        self,
        message: discord.Message,
        member: discord.Member = None,
        role_name: str = None,
    ):
        user_id = message.author.id

        # Handle response when waiting for role name
        if user_id in self.waiting_for_revoke_role:
            member = self.waiting_for_revoke_role.pop(user_id)
            role_name = message.content.strip()
            await self.revoke_role(message, member, role_name)
            return

        # Handle response when waiting for member
        if user_id in self.waiting_for_revoke_member:
            if not message.mentions:
                await message.channel.send("❌ Please mention the user using @username")
                return
            role_name = self.waiting_for_revoke_member.pop(user_id)
            await self.revoke_role(message, message.mentions[0], role_name)
            return

        # Initial request handling
        if not member and not role_name:
            await message.channel.send("❌ Please specify both the role and the user.")
            await self.prompt_revoke_role(message)
            return
        elif not member:
            self.waiting_for_revoke_member[user_id] = role_name
            await message.channel.send(
                "From which user should this role be revoked? (Please mention them using @)"
            )
            return
        elif not role_name:
            self.waiting_for_revoke_role[user_id] = member
            await message.channel.send(
                f"Which role should be revoked from {member.display_name}?\n"
                f"Their current roles: {', '.join([r.name for r in member.roles[1:]])}"
            )
            return

        await self.revoke_role(message, member, role_name)

    async def create_channel(
        self,
        message: discord.Message,
        channel_name: str,
        channel_type: str = "text",
        category: str = None,
        private: bool = False,
    ):
        """
        Creates a new channel in the server.

        Args:
            message: The Discord message that triggered this command
            channel_name: Name for the new channel
            channel_type: Either 'text' or 'voice'
            category: Category name to place the channel in (optional)
            private: Whether the channel should be private (default: False)
        """
        try:
            # Clean the channel name (Discord requirements)
            clean_name = channel_name.lower().replace(" ", "-")

            # Get the guild (server)
            guild = message.guild
            if not guild:
                return "This command can only be used in a server!"

            # Find category if specified
            category_obj = None
            if category:
                category_obj = discord.utils.get(guild.categories, name=category)
                if not category_obj:
                    return f"Category '{category}' not found!"

            # Set up permissions
            overwrites = {}
            if private:
                # Make channel private by default
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(read_messages=True),
                    message.author: discord.PermissionOverwrite(read_messages=True),
                }

            # Create the channel based on type
            if channel_type.lower() == "voice":
                new_channel = await guild.create_voice_channel(
                    name=clean_name,
                    category=category_obj,
                    overwrites=overwrites,
                    reason=f"Created by {message.author.display_name}",
                )
            else:
                new_channel = await guild.create_text_channel(
                    name=clean_name,
                    category=category_obj,
                    overwrites=overwrites,
                    reason=f"Created by {message.author.display_name}",
                )

            # Send confirmation message with channel mention
            return f"Created new {'private ' if private else ''}{channel_type} channel {new_channel.mention}"

        except discord.Forbidden:
            return "I don't have permission to create channels!"
        except discord.HTTPException as e:
            return f"Failed to create channel: {str(e)}"
        
        
    def parse_datetime(self, dt_str: str) -> datetime.datetime:
        """Attempt to parse a friendly datetime string using several formats."""
        formats = [
            "%Y-%m-%d %H:%M",         # e.g., 2025-03-10 15:30
            "%m/%d/%Y %I:%M %p",       # e.g., 03/10/2025 3:30 PM
            "%d/%m/%Y %H:%M",          # e.g., 10/03/2025 15:30
            "%B %d, %Y %H:%M",         # e.g., March 10, 2025 15:30
            "%B %d, %Y %I:%M %p"        # e.g., March 10, 2025 3:30 PM
        ]
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(dt_str, fmt)
                # Assuming the provided time is in local time; you can change to your preferred timezone.
                # Here we assume UTC for simplicity.
                return dt.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                continue
        raise ValueError("Time data does not match any supported format.")


    async def create_scheduled_event(
        self,
        message: discord.Message,
        event_name: str,
        start_datetime_str: str,
        voice_channel_str: str,
        event_topic: str,
    ):
        guild = message.guild
        if not guild:
            return "This command can only be used in a server!"

        # Parse the provided friendly date/time string.
        try:
            start_time = self.parse_datetime(start_datetime_str)
        except Exception as e:
            return f"Invalid date/time format: {str(e)}"

        # Retrieve the voice channel 
        channel = self.get_channel_by_id(voice_channel_str)
        if not channel:
            return "No valid channels found. Please check the channel IDs."
        # Ensure the channel is a VoiceChannel or StageChannel.
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return "Provided channel is not a voice or stage channel."

        try:
            scheduled_event = await guild.create_scheduled_event(
                name=event_name,
                start_time=start_time,
                channel=channel,
                entity_type=discord.EntityType.voice,  # For voice events.
                description=event_topic,
                privacy_level=discord.PrivacyLevel.guild_only,
            )
            await message.channel.send(
                f"Scheduled event **{event_name}** created for {start_time.isoformat()} in {channel.mention}!"
            )
            return scheduled_event
        except discord.Forbidden:
            return "I don't have permission to create scheduled events!"
        except discord.HTTPException as e:
            return f"Failed to create scheduled event: {str(e)}"
