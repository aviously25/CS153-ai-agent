import os
from mistralai import Mistral
import discord
from discord_agent import DiscordAgent
import re

MISTRAL_MODEL = "mistral-large-latest"

POSSIBLE_COMMANDS = [  # (command_name, description, arguments)
    (
        "create_group_chat",
        "Creates a private thread with the mentioned users.",
        [("user_mentions", "array")],
    ),
    (
        "invite_user_to_channel",
        "Add user(s) to exitsing channel.",
        [("user_mentions", "array"), ("channels_mention", "array")]
    ),
    (
         "create_poll",
         "Creates a poll in the channel.",
         [
             ("question", "string"),
             ("answers", "array of strings"),
             ("duration", "optional int in hours"),
         ],
     ),
    (   
        "change_bot_avatar", 
        "Changes the bot's avatar.", 
        [("bot_mention", "mention"), ("url", "string")]),
    (   
        "change_bot_name", 
        "Changes the bot's name.", 
        [("bot_mention", "mention"), ("new_name", "string")]),
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

User: Add @user1 to @channel1
You: invite_user_to_channel(user_mentions=[@user1], channel_mentions=[@channel1])


User: Create a poll for favorite color between red, blue, and green
You: create_poll(question="What is your favorite color?", answers=["red", "blue", "green"])

User: Change the bot's avatar
You: change_bot_avatar(bot_mention=?, url=?)

User: Change the bot @botname name to NewName
You: change_bot_name(bot_mention=@botname, new_name=NewName)

"""


class MistralAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.discord_agent = DiscordAgent()

    async def run(self, message: discord.Message):
        # The simplest form of an agent
        # Send the message's content to Mistral's API and return Mistral's response

         channel_members = []
         if not message.channel.type == discord.ChannelType.private:
             channel_members = await self.discord_agent.get_users_in_message(message)
         channel_mentions = await self.discord_agent.get_channel_mentions_in_message(
             message
         )

        # send initial message to Mistral
         messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Content: {message.content} \n\n Channel Mentioned: {str(channel_mentions)} \n\n Channel Members: {str(channel_members)} \n\n Sender: {message.author.id}",
            },
        ]

        # extract the response from Mistral
         response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )
         content = response.choices[0].message.content

        # check if the response contains a command
         if "create_group_chat" in content:
            # Check if there are any mentioned users in the mistral response
            if match := re.search(r"user_mentions=\[(.*)\]", content):
                user_mentions = match.group(1)
                user_mentions = user_mentions.split(",")
                user_mentions = [mention.strip() for mention in user_mentions]

                return await self.discord_agent.create_group_chat(
                    message, user_mentions
                )



         if "create_poll" in content:
             print("content: ", content)
             # extract question
             question_match = re.search(r"question=\"(.+?)\"", content)
             if not question_match:
                 return "No question found. Please specify the question for the poll."
             question = question_match.group(1)
 
             # extract answers
             answers_match = re.search(r"answers=\[(.*)\]", content)
             if not answers_match:
                 return "No answers found. Please specify the answers for the poll."
             answers = answers_match.group(1)
             answers = answers.split(",")
             answers = [answer.strip().strip("\"'") for answer in answers]
 
             # extract duration
             duration_match = re.search(r"duration=(\d+)", content)
             if duration_match:
                 duration = int(duration_match.group(1))
                 return await self.discord_agent.create_poll(
                     message, question, answers, duration
                 )
             else:
                 return await self.discord_agent.create_poll(message, question, answers)
                 
         if "invite_user_to_channel" in content:
            # Check if there are any mentioned users and channels in the mistral response
            channel_mentions = []
            if match := re.search(r"channel_mentions=\[(.*)\]", content):
                channel_mentions = match.group(1)
                channel_mentions = channel_mentions.split(",")
                channel_mentions = [mention.strip() for mention in channel_mentions]
            user_mentions = []
            if match := re.search(r"user_mentions=\[(.*)\]", content):
                user_mentions = match.group(1)
                user_mentions = user_mentions.split(",")
                user_mentions = [mention.strip() for mention in user_mentions]
            if len(channel_mentions) == 0:
                return "No channel mentioned. Please specify the channel you want to add new users to."
            if len(user_mentions) == 0:
                return "No user mentioned. Please specify the user(s) you want to add to the channel."

            return await self.discord_agent.create_group_chat(
                message, user_mentions
            )
         if "change_bot_avatar" in content:
            url_match = re.search(r"url=(https?://\S+)", content)
            bot_mention_match = re.search(r"bot_mention=<@!?(\d+)>", content)
            url = url_match.group(1) if url_match else None
            bot_id = int(bot_mention_match.group(1)) if bot_mention_match else None
            bot_member = message.guild.get_member(bot_id) if bot_id else None

            if bot_member and bot_member.bot and url:
                return await self.discord_agent.change_bot_avatar(message, bot_member, url)
            else:
                await self.discord_agent.handle_change_avatar(message, bot_member, url)
                return
         if "change_bot_name" in content:
            bot_mention_match = re.search(r"bot_mention=<@!?(\d+)>", content)
            new_name_match = re.search(r"new_name=(\w+)", content)
            
            bot_id = int(bot_mention_match.group(1)) if bot_mention_match else None
            new_name = new_name_match.group(1) if new_name_match else None
            bot_member = message.guild.get_member(bot_id) if bot_id else None

            if bot_member and bot_member.bot and new_name:
                return await self.discord_agent.change_bot_name(message, bot_member, new_name)
            else:
                await self.discord_agent.handle_change_name(message, bot_member, new_name)
                return

         return content
