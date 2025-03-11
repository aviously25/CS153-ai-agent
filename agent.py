import os
from mistralai import Mistral
import discord
from discord_agent import DiscordAgent
import re
from collections import deque
from datetime import datetime, timezone

MISTRAL_MODEL = "mistral-large-latest"

POSSIBLE_COMMANDS = [  # (command_name, description, arguments)
    (
        "create_channel",
        "Creates a new channel in the server.",
        [
            ("channel_name", "string"),
            ("channel_type", "optional string: 'text' or 'voice'"),
            ("category", "optional string"),
            ("private", "optional boolean"),
        ],
    ),
    (
        "create_group_chat",
        "Creates a private thread with the mentioned users.",
        [("user_mentions", "array")],
    ),
    (
        "invite_user_to_channel",
        "Add user(s) to exitsing channel.",
        [("user_mentions", "array"), ("channels_mention", "array")],
    ),
    (
        "mute_member_from_channel",
        "Mute user(s) in exitsing channel.",
        [("user_mentions", "array"), ("channels_mention", "array")],
    ),
    (
        "unmute_member_from_channel",
        "Unmute user(s) in exitsing channel.",
        [("user_mentions", "array"), ("channels_mention", "array")],
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
        [("bot_mention", "mention"), ("url", "string")],
    ),
    (
        "change_bot_name",
        "Changes the bot's name.",
        [("bot_mention", "mention"), ("new_name", "string")],
    ),
    (
        "assign_role",
        "Assigns a role to a user.",
        [("member", "mention"), ("role_name", "string")],
    ),
    (
        "create_role",
        "Creates a new role.",
        [("role_name", "string")],
    ),
    (
        "revoke_role",
        "Revokes a role from a user.",
        [("member", "mention"), ("role_name", "string")],
    ),
    (
        "create_scheduled_event",
        "Creates a new scheduled event.",
        [
            ("event_name", "string"),
            ("start_datetime", "string (e.g., '2025-03-10 15:30' or '03/10/2025 3:30 PM')"),
            ("voice_channel", "string (channel mention or ID)"),
            ("event_topic", "string")
            
        ]
    ),
    (
        "summarize_server_activity",
        "Generates a summary of recent server activity.",
        []
    ),
    (
        "send_automated_message",
        "Sends or schedules automated messages.",
        [
            ("target_type", "string: 'dm' or 'channel'"),
            ("target", "mention: user or channel"),
            ("message", "string"),
            ("schedule_time", "optional string: time to send message"),
        ]
    ),
    (
        "send_welcome_message",
        "Sends a welcome message to a user.",
        [
            ("target", "mention"),
            ("custom_message", "optional string"),
        ]
    ),
    (
        "change_channel_name",
        "Changes a channel's name.",
        [
            ("channel", "channel mention"),
            ("new_name", "string"),
        ]
    ),
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

User: Add @user1 to #channel1
You: invite_user_to_channel(user_mentions=[@user1], channel_mentions=[#channel1])

User: Mute @user1 in #channel1
You: mute_member_from_channel(user_mentions=[@user1], channel_mentions=[#channel1])

User: Stop muting @user1 in #channel1
You: unmute_member_from_channel(user_mentions=[@user1], channel_mentions=[#channel1])

User: Unmute @user1 in #channel1
You: unmute_member_from_channel(user_mentions=[@user1], channel_mentions=[#channel1])

User: Create a poll for favorite color between red, blue, and green
You: create_poll(question="What is your favorite color?", answers=["red", "blue", "green"])

User: Change the bot's avatar
You: change_bot_avatar(bot_mention=?, url=?)

User: Change the bot @botname name to NewName
You: change_bot_name(bot_mention=@botname, new_name=NewName)

User: Assign student role to @user1
You: assign_role(member=@user1, role_name="student")

User: Give @user1 admin role
You: assign_role(member=@user1, role_name="admin")

User: Create a new role called moderator
You: create_role(role_name="moderator")

User: Make a new admin role
You: create_role(role_name="admin")

User: Revoke admin role from @user1
You: revoke_role(member=@user1, role_name="admin")

User: Remove moderator role from @user1
You: revoke_role(member=@user1, role_name="moderator")

User: Schedule an event called "Team Meeting" starting on "2025-03-10 15:30" in <#1234567890> with the topic "Discuss project updates".
You: create_scheduled_event(event_name="Team Meeting", start_datetime="2025-03-10 15:30", voice_channel=<#1234567890>, event_topic="Discuss project updates")

User: Change the bot's avatar
You: change_bot_avatar(bot_mention=?)

User: Change the bot @botname avatar 
You: change_bot_avatar(bot_mention=@botname)

User: Change the bot @botname avatar [uploaded an image]
You: change_bot_avatar(bot_mention=@botname)

User: summarize server activity
You: summarize_server_activity()

User: send a welcome message to @user1
You: send_welcome_message(target=@user1)

User: send a welcome message to @user1 saying "Welcome aboard!"
You: send_welcome_message(target=@user1, custom_message="Welcome aboard!")

User: send "Meeting in 5 minutes" to #announcements at 2:30 PM
You: send_automated_message(target_type="channel", target=#announcements, message="Meeting in 5 minutes", schedule_time="2:30 PM")

User: dm @user1 "Don't forget about the meeting!"
You: send_automated_message(target_type="dm", target=@user1, message="Don't forget about the meeting!")

User: rename #general to announcements
You: change_channel_name(channel=#general, new_name="announcements")

User: send "Good morning!" to #announcements in 5 minutes
You: send_automated_message(target_type="channel", target=#announcements, message="Good morning!", schedule_time="5m")

User: dm @user1 "Meeting starts" in 30 seconds
You: send_automated_message(target_type="dm", target=@user1, message="Meeting starts", schedule_time="30s")

User: send "Going live!" to #announcements in 1 hour
You: send_automated_message(target_type="channel", target=#announcements, message="Going live!", schedule_time="1h")

User: schedule a message "Meeting in 5 minutes" to @user1 in 10s
You: send_automated_message(target_type="dm", target=@user1, message="Meeting in 5 minutes", schedule_time="10s")

User: send "Hi there" to easecord in 1m
You: send_automated_message(target_type="dm", target=easecord, message="Hi there", schedule_time="1m")

"""


class MistralAgent:
    def __init__(self, bot):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.discord_agent = DiscordAgent(bot)
        self.conversation_history = {}  # guild_id -> deque of messages
        self.history_limit = 10  # Keep last 10 messages per guild
        
    def _add_to_history(self, guild_id: int, message: discord.Message):
        """Add message to conversation history for the guild."""
        if guild_id not in self.conversation_history:
            self.conversation_history[guild_id] = deque(maxlen=self.history_limit)
        
        self.conversation_history[guild_id].append({
            'author': message.author.name,
            'content': message.content,
            'timestamp': message.created_at.isoformat(),
        })

    def _get_history(self, guild_id: int) -> str:
        """Get formatted conversation history for the guild."""
        if guild_id not in self.conversation_history:
            return ""
            
        history = []
        for msg in self.conversation_history[guild_id]:
            history.append(f"{msg['author']}: {msg['content']}")
        return "\n".join(history)

    async def run(self, message: discord.Message):
        # Add message to history if in a guild
        if message.guild:
            self._add_to_history(message.guild.id, message)
            conversation_history = self._get_history(message.guild.id)
        else:
            conversation_history = ""

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
            {"role": "user", "content": f"""Recent conversation:
{conversation_history}

Current message:
{message.content}

Channel Mentioned: {str(channel_mentions)}
Channel Members: {str(channel_members)}
Sender: {message.author.id}"""}
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
            print("content: ", content)
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
            if len(channel_mentions) == 0:
                return "No channel mentioned. Please specify the channel you want to add new users to."
            user_mentions = []
            if match := re.search(r"user_mentions=\[(.*)\]", content):
                user_mentions = match.group(1)
                user_mentions = user_mentions.split(",")
                user_mentions = [mention.strip() for mention in user_mentions]
            if len(user_mentions) == 0:
                return "No user mentioned. Please specify the user(s) you want to add to the channel."

            return await self.discord_agent.invite_member_to_channel(message, user_mentions, channel_mentions)

        if "unmute_member_from_channel" in content:
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

            return await self.discord_agent.unmute_member_from_channel(message, user_mentions, channel_mentions)

        if "mute_member_from_channel" in content:
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

            return await self.discord_agent.mute_member_from_channel(message, user_mentions, channel_mentions)

        if "create_channel" in content:
            # Extract channel name
            name_match = re.search(r"channel_name=\"(.+?)\"", content)
            if not name_match:
                return "No channel name found. Please specify the name for the new channel."
            channel_name = name_match.group(1)

            # Extract optional channel type
            channel_type = "text"  # default
            type_match = re.search(r"channel_type=\"(.+?)\"", content)
            if type_match:
                channel_type = type_match.group(1)

            # Extract optional category
            category = None
            category_match = re.search(r"category=\"(.+?)\"", content)
            if category_match:
                category = category_match.group(1)

            # Extract optional private setting
            private = False
            private_match = re.search(r"private=(true|false)", content)
            if private_match:
                private = private_match.group(1).lower() == "true"

            return await self.discord_agent.create_channel(
                message,
                channel_name,
                channel_type=channel_type,
                category=category,
                private=private,
            )

        if "change_bot_avatar" in content:
            bot_mention_match = re.search(r"bot_mention=<@!?(\d+)>", content)
            bot_id = int(bot_mention_match.group(1)) if bot_mention_match else None
            bot_member = message.guild.get_member(bot_id) if bot_id else None

            # Get the uploaded image
            image_data = None
            if message.attachments:
                #print(f"Found {len(message.attachments)} attachments")
                #print(f"First attachment type: {message.attachments[0].content_type}")
                #print(f"First attachment size: {message.attachments[0].size} bytes")
                image_data = await message.attachments[0].read()
                #print(f"Successfully read image data: {len(image_data)} bytes")

            # If we have a bot mention and an image, change the avatar
            if bot_member and image_data:
                return await self.discord_agent.change_bot_avatar(
                    message, bot_member, image_data
                )
            elif not bot_member:
                await message.channel.send("❌ Please mention the bot whose avatar you want to change.")
            elif not image_data:
                await message.channel.send("❌ Please attach an image to change the bot's avatar.")
            return

        if "change_bot_name" in content:
            # Try to extract bot mention and new name
            bot_mention_match = re.search(r'bot_mention=([^,\)]+)', content)
            new_name_match = re.search(r'new_name="?([a-zA-Z0-9_-]+)"?', content)  # Only allow valid name characters

            # Get bot member from mention
            target = None
            if bot_mention_match:
                bot_str = bot_mention_match.group(1).strip()
                # Try mention format first
                mention_match = re.search(r'<@!?(\d+)>', bot_str)
                if mention_match:
                    bot_id = int(mention_match.group(1))
                    target = message.guild.get_member(bot_id)
                else:
                    # Try finding bot by name
                    bot_name = bot_str.strip('@')
                    target = discord.utils.get(message.guild.members, name=bot_name, bot=True)

            new_name = new_name_match.group(1) if new_name_match else None
            
            # Additional validation
            if target and not target.bot:
                await message.channel.send("❌ The specified user is not a bot.")
                return
            elif new_name and not 2 <= len(new_name) <= 32:
                await message.channel.send("❌ Bot name must be between 2 and 32 characters.")
                return

            if target and target.bot and new_name:
                return await self.discord_agent.change_bot_name(message, target, new_name)
            elif not target:
                await message.channel.send("❌ Please mention or specify the bot you want to rename.")
                await self.discord_agent.prompt_change_name(message)
            elif not new_name:
                await message.channel.send(f"❌ Please specify a valid new name for {target.display_name}.")
                await self.discord_agent.prompt_change_name(message)
            return

        if "assign_role" in content:
            member_match = re.search(r"member=<@!?(\d+)>", content)
            role_match = re.search(r"role_name=\"([^\"]+)\"", content)

            member_id = int(member_match.group(1)) if member_match else None
            role_name = role_match.group(1) if role_match else None
            member = message.guild.get_member(member_id) if member_id else None

            if member and role_name:
                return await self.discord_agent.assign_role(message, member, role_name)
            else:
                await self.discord_agent.handle_assign_role(message, member, role_name)
                return

        if "create_role" in content:
            role_match = re.search(r"role_name=\"([^\"]+)\"", content)
            role_name = role_match.group(1) if role_match else None

            await self.discord_agent.handle_create_role(message, role_name)
            return

        if "revoke_role" in content:
            member_match = re.search(r"member=<@!?(\d+)>", content)
            role_match = re.search(r"role_name=\"([^\"]+)\"", content)

            member_id = int(member_match.group(1)) if member_match else None
            role_name = role_match.group(1) if role_match else None
            member = message.guild.get_member(member_id) if member_id else None

            if member and role_name:
                return await self.discord_agent.revoke_role(message, member, role_name)
            else:
                await self.discord_agent.handle_revoke_role(message, member, role_name)
                return
            
            
        if "create_scheduled_event" in content:
            event_name_match = re.search(r'event_name="(.+?)"', content)
            start_datetime_match = re.search(r'start_datetime="(.+?)"', content)
            event_topic_match = re.search(r'event_topic="(.+?)"', content)

            # Try to extract voice_channel from a command parameter format
            voice_channel_match = re.search(r'voice_channel=<#\!?(\d+)>', content)
            # Fallback: if not found, search for any channel mention in the content
            if not voice_channel_match:
                voice_channel_match = re.search(r"<#\!?(\d+)>", content)

            missing_params = []
            if not event_name_match:
                missing_params.append("event_name")
            if not start_datetime_match:
                missing_params.append("start_datetime")
            if not voice_channel_match:
                missing_params.append("voice_channel")
            if not event_topic_match:
                missing_params.append("event_topic")

            if missing_params:
                return f"Missing required parameter(s): {', '.join(missing_params)}"
            
            event_name = event_name_match.group(1) 
            start_datetime_str = start_datetime_match.group(1) 
            event_topic = event_topic_match.group(1) 
            voice_channel_str = voice_channel_match.group(1) 

            return await self.discord_agent.create_scheduled_event(
                message, event_name, start_datetime_str, voice_channel_str, event_topic
            )
            
        if "summarize_server_activity" in content:
            return await self.discord_agent.get_server_activity_summary(message)

        if "send_automated_message" in content:
            target_type_match = re.search(r'target_type="(.+?)"', content)
            target_match = re.search(r'target=([^,\)]+)', content)
            message_match = re.search(r'message="(.+?)"', content)
            schedule_match = re.search(r'schedule_time="(.+?)"', content)

            if not all([target_type_match, target_match, message_match]):
                return "Missing required parameters for automated message!"

            target_type = target_type_match.group(1)
            msg_content = message_match.group(1)
            schedule_time = schedule_match.group(1) if schedule_match else None
            target_str = target_match.group(1).strip()

            # Get target based on type
            target = None
            if target_type == "dm":
                # Pass the raw target string to the agent for flexible matching
                target = target_str.strip()
            else:  # channel
                channel_match = re.search(r'<#!?(\d+)>', target_str)
                if not channel_match:
                    return "❌ Invalid channel mention format!"
                try:
                    channel_id = int(channel_match.group(1))
                    target = message.guild.get_channel(channel_id)
                except (ValueError, AttributeError):
                    return "❌ Could not parse channel ID!"

            if not target:
                return f"❌ Could not find the specified {'user' if target_type == 'dm' else 'channel'}!"

            return await self.discord_agent.send_automated_message(
                message, target_type, target, msg_content, schedule_time
            )

        if "send_welcome_message" in content:
            target_match = re.search(r'target=<@!?(\d+)>', content)
            message_match = re.search(r'custom_message="(.+?)"', content)

            if not target_match:
                return "Please specify a target user!"

            target_id = int(target_match.group(1))
            target_member = message.guild.get_member(target_id)
            custom_message = message_match.group(1) if message_match else None

            return await self.discord_agent.send_welcome_message(
                message, target_member, custom_message
            )

        if "change_channel_name" in content:
            channel_match = re.search(r'channel=<#!?(\d+)>', content)
            name_match = re.search(r'new_name="(.+?)"', content)

            if not all([channel_match, name_match]):
                return "❌ Please provide both channel and new name!"
            
            try:
                channel_id = int(channel_match.group(1))
                channel = message.guild.get_channel(channel_id)
                new_name = name_match.group(1)

                if not channel:
                    return "❌ Could not find the specified channel!"
                
                return await self.discord_agent.change_channel_name(
                    message, channel, new_name
                )
            except (ValueError, AttributeError):
                return "❌ Invalid channel mention or name format!"

        return content
