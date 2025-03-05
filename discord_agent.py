import discord


class DiscordAgent:
    async def get_user_by_id(self, user_id: str, guild: discord.Guild):
        try:
            clean_id = "".join(filter(str.isdigit, user_id))
            return await guild.fetch_member((int(clean_id)))
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

    async def create_group_chat(
        self,
        message: discord.Message,
        user_mentions: list[str],
    ):
        print("called create_group_chat with user_mentions:", user_mentions)

        # Convert string IDs to Discord User objects
        discord_users = []
        for user_id in user_mentions:
            user = await self.get_user_by_id(user_id, message.guild)
            if user:
                discord_users.append(user)

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
