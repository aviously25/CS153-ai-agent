import os
import discord
import logging
import aiohttp  # Import aiohttp for handling HTTP requests
import json
import base64


from discord.ext import commands
from dotenv import load_dotenv
from io import BytesIO

# Setup logging
logger = logging.getLogger("discord")
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Create bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")


class DiscordAgent:
    def __init__(self, bot):
        self.bot = bot  # Store bot instance for reference

    async def get_user_by_id(self, user_id: str, guild: discord.Guild):
        try:
            clean_id = "".join(filter(str.isdigit, user_id))
            return await guild.fetch_member(int(clean_id))
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

    async def create_group_chat(self, message: discord.Message, user_mentions: list[str]):
        discord_users = []
        for user_id in user_mentions:
            user = await self.get_user_by_id(user_id, message.guild)
            if user:
                discord_users.append(user)

        if not discord_users:
            return "No valid users found. Please check the user IDs."

        mentioned_users = [user.display_name for user in discord_users]
        thread_name = f"Private Chat with {', '.join(mentioned_users)}"

        try:
            thread = await message.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                invitable=False,
            )
            for user in discord_users:
                await thread.add_user(user)
            user_mentions_str = ", ".join([user.mention for user in discord_users])
            await thread.send(f"Private thread created! Welcome {user_mentions_str}!")
            return "Private thread created!"
        except discord.Forbidden:
            return "I don't have permission to create private threads!"
        except discord.HTTPException:
            return "Failed to create the thread. Please try again later."

    async def change_bot_avatar(self, ctx, url: str):
        """
        Changes the bot's avatar to an image from a given URL.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        avatar_data = await response.read()
                        image_bytes = BytesIO(avatar_data)
                        await self.bot.user.edit(avatar=image_bytes.getvalue())
                        await ctx.send("Avatar changed successfully!")
                    else:
                        await ctx.send("Failed to fetch avatar image. Check the URL.")
        except discord.HTTPException as e:
            logger.error(f"Error changing avatar: {e}")
            await ctx.send("An error occurred while changing the avatar. Ensure the image is a valid format (PNG, JPG, GIF).")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")


TOKEN_FILE = "user_tokens.json"

def save_user_access_token(user_id, access_token):
    """
    Saves the access token for a user in a JSON file.
    """
    try:
        with open(TOKEN_FILE, "r") as file:
            tokens = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        tokens = {}

    tokens[str(user_id)] = access_token

    with open(TOKEN_FILE, "w") as file:
        json.dump(tokens, file, indent=4)

def get_user_access_token(user_id):
    """
    Retrieves the access token for a user from the JSON file.
    """
    try:
        with open(TOKEN_FILE, "r") as file:
            tokens = json.load(file)
        return tokens.get(str(user_id))  # Returns None if user ID not found
    except (FileNotFoundError, json.JSONDecodeError):
        return None

async def exchange_code_for_token(code, user_id):
    """
    Exchanges an OAuth2 authorization code for an access token and stores it.
    """
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI")  # ✅ Read from environment variable
    
    # ✅ Force debug logging
    print("🔍 DEBUG: Function `exchange_code_for_token` is being called!")
    print(f"🔍 DEBUG: Received code = {code}")
    print(f"🔍 DEBUG: Received user_id = {user_id}")
    print(f"🔍 DEBUG: Using redirect_uri = {redirect_uri}")

    async with aiohttp.ClientSession() as session:
        async with session.post("https://discord.com/api/oauth2/token", data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI
        }) as response:
            token_data = await response.json()

            if "access_token" in token_data:
                save_user_access_token(user_id, token_data["access_token"])
                return token_data  # ✅ Return the token data instead of sending a message
            else:
                return {"error": token_data}  # ✅ Return error data

async def change_user_avatar(access_token, image_url):
    """
    Changes the authenticated user's avatar using their OAuth2 access token.
    """
    async with aiohttp.ClientSession() as session:
        # Download the image
        async with session.get(image_url) as image_response:
            if image_response.status == 200:
                avatar_data = await image_response.read()

                # Convert to base64 (required by Discord API)
                import base64
                avatar_base64 = base64.b64encode(avatar_data).decode("utf-8")
                avatar_payload = {"avatar": f"data:image/png;base64,{avatar_base64}"}

                # Send PATCH request to change user's avatar
                headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
                async with session.patch("https://discord.com/api/users/@me", json=avatar_payload, headers=headers) as response:
                    return await response.json()
            else:
                return {"error": "Failed to download image"}


# Instantiate DiscordAgent and pass the bot instance
agent = DiscordAgent(bot)


@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if message.author.bot or message.content.startswith("!"):
        return


@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")


@bot.command(name="change_bot_avatar", help="Changes the bot's avatar.")
async def change_bot_avatar(ctx, url: str):
    await agent.change_bot_avatar(ctx, url)  # Call the method from DiscordAgent


import aiohttp
import base64
@bot.command(name="change_my_avatar", help="Changes your avatar using OAuth2.")
async def change_my_avatar(ctx, image_url: str):
    """
    Changes the user's avatar using their OAuth2 access token.
    """
    user_id = str(ctx.author.id)
    
    # ✅ Retrieve the stored access token
    access_token = get_user_access_token(user_id)
    
    if not access_token:
        await ctx.send(f"{ctx.author.mention}, you need to authorize the bot first. Use `!authorize`.")
        return
    
    # ✅ Debugging output
    print(f"🔍 DEBUG: Using access_token = {access_token[:5]}... (hidden)")
    
    async with aiohttp.ClientSession() as session:
        # ✅ Download the image
        async with session.get(image_url) as image_response:
            if image_response.status == 200:
                avatar_data = await image_response.read()

                # Convert image to base64 (required by Discord API)
                avatar_base64 = base64.b64encode(avatar_data).decode("utf-8")
                avatar_payload = {"avatar": f"data:image/png;base64,{avatar_base64}"}

                # Send PATCH request to change user's avatar
                headers = {
                    "Authorization": f"Bearer {access_token}",  # ✅ Use Bearer Token
                    "Content-Type": "application/json"
                }
                
                async with session.patch("https://discord.com/api/v10/users/@me", json=avatar_payload, headers=headers) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        await ctx.send(f"✅ Successfully changed {ctx.author.display_name}'s avatar! 🎉")
                    else:
                        await ctx.send(f"❌ Failed to change avatar: {result}")
            else:
                await ctx.send("❌ Failed to fetch image. Ensure the URL is correct.")

# @bot.command(name="change_my_avatar", help="Changes your avatar using OAuth2.")
# async def change_my_avatar(ctx, image_url: str):
#     user_id = str(ctx.author.id)
    
#     # Retrieve the access token from storage
#     access_token = get_user_access_token(user_id)
    
#     if not access_token:
#         await ctx.send(f"{ctx.author.mention}, you need to authorize the bot first. Use this link: [OAuth2 Authorization Link]")
#         return
#     response = await change_user_avatar(access_token, image_url)
    
#     if "avatar" in response:
#         await ctx.send(f"Successfully changed {ctx.author.display_name}'s avatar! ✅")
#     else:
#         await ctx.send(f"Failed to change avatar: {response}")

# @bot.command(name="authorize", help="Get the OAuth2 authorization link.")
# async def authorize(ctx):
#     DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")  # Ensure this is set in .env
#     auth_url = f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&response_type=code&scope=identify+email"
#     await ctx.send(f"Click this link to authorize the bot: {auth_url}")


@bot.command(name="change_server_avatar", help="Changes a user's server avatar.")
async def change_server_avatar(ctx, member: discord.Member, image_url: str):
    """
    Changes the avatar for a user in the current Discord server (server profile avatar).
    """
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    if not ctx.author.guild_permissions.manage_nicknames:
        await ctx.send("You don't have permission to change nicknames or avatars in this server.")
        return

    if not ctx.guild.me.guild_permissions.manage_nicknames:
        await ctx.send("I need the `Manage Nicknames` and `Manage Server` permissions to change avatars.")
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as image_response:
            if image_response.status == 200:
                avatar_data = await image_response.read()

                # Convert image to BytesIO format
                image_bytes = BytesIO(avatar_data)

                try:
                    # Change the member's server-specific avatar
                    await member.edit(avatar=image_bytes.getvalue())

                    await ctx.send(f"✅ Successfully changed {member.display_name}'s server avatar! 🎉")
                except discord.Forbidden:
                    await ctx.send("❌ I don't have permission to change this user's avatar.")
                except discord.HTTPException as e:
                    await ctx.send(f"❌ Failed to change avatar: {e}")
            else:
                await ctx.send("❌ Failed to fetch image. Ensure the URL is correct.")


@bot.command(name="change_nickname", help="Changes a user's nickname.")
async def change_nickname(ctx, member: discord.Member, *, new_nickname: str):
    """
    Changes a user's nickname in the current Discord server.
    """
    if not ctx.author.guild_permissions.manage_nicknames:
        await ctx.send("❌ You don't have permission to change nicknames in this server.")
        return

    if not ctx.guild.me.guild_permissions.manage_nicknames:
        await ctx.send("❌ I need the `Manage Nicknames` permission to change nicknames.")
        return

    try:
        await member.edit(nick=new_nickname)
        await ctx.send(f"✅ Successfully changed {member.display_name}'s nickname to **{new_nickname}**!")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to change this user's nickname.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Failed to change nickname: {e}")

@bot.command(name="assign_role_icon", help="Assigns a role with an icon to a user.")
async def assign_role_icon(ctx, member: discord.Member, role_name: str):
    """
    Assigns a role with a custom icon to a user.
    """
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("❌ You don't have permission to manage roles in this server.")
        return

    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send("❌ I need the `Manage Roles` permission to assign roles.")
        return

    # Find the role by name
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    
    if not role:
        await ctx.send("❌ Role not found! Make sure it exists.")
        return

    try:
        await member.add_roles(role)
        await ctx.send(f"✅ Successfully assigned the **{role.name}** role to {member.display_name}!")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to assign this role.")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Failed to assign role: {e}")

@bot.command(name="authorize", help="Get the OAuth2 authorization link.")
async def authorize(ctx):
    DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
    DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

    auth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=identify+email+guilds+gdm.join+applications.commands+connections"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&permissions=8"
        f"&access_type=offline"
    )

    await ctx.send(f"Click this link to authorize the bot: {auth_url}")


@bot.command(name="exchange_code", help="Exchanges an OAuth2 authorization code for an access token.")
async def exchange_code(ctx, code: str):
    """
    Discord bot command to exchange the user's authorization code for an access token.
    """
    user_id = str(ctx.author.id)  # ✅ Get user ID from the message sender
    token_data = await exchange_code_for_token(code, user_id)  # ✅ Pass user_id

    if "access_token" in token_data:
        access_token = token_data["access_token"]
        await ctx.send(f"✅ Successfully retrieved access token!\n```\n{access_token}\n```")
    else:
        await ctx.send(f"❌ Failed to exchange code. Error: {token_data['error']}")


# Run the bot
bot.run(token)
