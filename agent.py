import os
from mistralai import Mistral
import discord
from discord_agent import DiscordAgent
import re

MISTRAL_MODEL = "mistral-large-latest"

POSSIBLE_COMMANDS = [
    (  # (command_name, description, arguments)
        "create_group_chat",
        "Creates a private thread with the mentioned users.",
        ["user_mentions", "array"],
    )
]

SYSTEM_PROMPT = f"""
You are a friendly discord assistant. 
You live on a discord server and help users with their discord usage. You have access to the following
commands:
{POSSIBLE_COMMANDS}

If you think a user wants to use a command, please only respond with the command name and the arguments.
For example,
User: create a group chat with @user1 and @user2
You: create_group_chat(user_mentions=[@user1, @user2])

User: create a group chat with me and @user1
You: create_group_chat(user_mentions=[@{{id of the message sender}}, @user1])
"""

discord_agent = DiscordAgent()


class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def run(self, message: discord.Message):
        # The simplest form of an agent
        # Send the message's content to Mistral's API and return Mistral's response

        channel_members = await discord_agent.get_users_in_message(message)
        print("channel_members:", channel_members)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Content: {message.content} \n\n Channel Members: {str(channel_members)} \n\n Sender: {message.author.id}",
            },
        ]

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
        content = response.choices[0].message.content
        print("content:", content)

        if "create_group_chat" in content:
            if match := re.search(r"user_mentions=\[(.*)\]", content):
                user_mentions = match.group(1)
                user_mentions = user_mentions.split(",")
                user_mentions = [mention.strip() for mention in user_mentions]

                return await discord_agent.create_group_chat(message, user_mentions)

        return content
