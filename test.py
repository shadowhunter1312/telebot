from telegram import Update, Chat, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import timedelta

import logging
import re

def escape_markdown_v2(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

# Enable logging with WARNING level (only warnings and errors will be logged)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.WARNING)
logger = logging.getLogger(__name__)

# Dictionary to store user link counts and unsafe users
link_counts = {}
unsafe_users = {}
safe_users = {}
# Add a global flag for tracking system
tracking_enabled = False
# Words to check for exact matches
ad_words = {"ad", "all done", "AD", "all dn", "alldone","done"}

excluded_users = {"Sage_003","Mehunnaa","hectorthisside","kanika_sheoran","TereEhsaasoonMein","Maxxxxxx07", "suubhraa","tinfoilhat46"}

async def is_admin(update: Update) -> bool:
    chat = update.effective_chat
    user_id = update.message.from_user.id
    # Fetch chat administrators and check if the user is one of them
    admins = await chat.get_administrators()
    for admin in admins:
        if admin.user.id == user_id:
            return True
    return False

# Start command to reset all counts
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!.")
        return

    global link_counts, unsafe_users, safe_users
    link_counts = {}  # Reset all counts
    unsafe_users = {}
    safe_users = {}  # Reset unsafe list
    await update.message.reply_text("🎉 Welcome to the new session! 🎉\n\n"
        "Please share your link to get started! 😎\n"
        "We'll track your activity and handle the rest! 🚀")

# Message handler to count messages with links
async def count_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global link_counts, unsafe_users, safe_users, excluded_users

    user = update.message.from_user
    user_id = user.id
    user_full_name = user.full_name
    user_username = user.username or "No Username"

    # Skip processing if the user is in the excluded list
    if user_username in excluded_users:
        return  # Do nothing for excluded users

    # Initialize or update user's data in link_counts
    if user_id not in link_counts:
        link_counts[user_id] = {
            "srno": len(link_counts) + 1,  # Assign unique serial number
            "name": user_full_name,
            "username": user_username,
            "x_username": None,  # Initialize as None
            "link_count": 0 ,
            "ad_count": 0
        }

    # Process the message to check for links and extract Twitter/X username
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type in ["url", "text_link"]:
                # Extract the URL
                url = update.message.text[entity.offset:entity.offset + entity.length]

                # Extract Twitter/X username if the link is from Twitter/X
                x_username = None
                if "twitter.com/" in url or "x.com/" in url:
                    try:
                        x_username = (
                            url.split("twitter.com/")[-1]
                            .split("x.com/")[-1]
                            .split("/")[0]
                            .split("?")[0]
                        )
                    except IndexError:
                        x_username = "Unknown"

                # Update the user's Twitter/X username (only if not already set or changed)
                if x_username and link_counts[user_id].get("x_username") != x_username:
                    link_counts[user_id]["x_username"] = x_username

                # Increment link count
                link_counts[user_id]["link_count"] += 1

                # Add user to unsafe_users if not already categorized
                if user_id not in safe_users and user_id not in unsafe_users:
                    unsafe_users[user_id] = {
                        "srno": link_counts[user_id]["srno"],
                        "name": user_full_name,
                        "username": user_username,
                    }

                break  # Only count one link per message

async def count_ad_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track ad messages and reply to users with their ID & username."""
    global link_counts, unsafe_users, safe_users

    # Only proceed if tracking is enabled
    if not tracking_enabled:
        return

    user = update.message.from_user
    user_id = user.id
    user_full_name = user.full_name
    user_username = user.username or "No Username"

    # ✅ Only proceed if the user already exists in `link_counts`
    if user_id not in link_counts:
        return  # Ignore new users, do not create a new entry

    # ✅ Fetch `x_username` for existing users
    x_username = link_counts[user_id]["x_username"] or "Unknown"

    # Combine text and caption for processing
    message_text = update.message.text or ""
    caption_text = update.message.caption or ""
    combined_text = f"{message_text} {caption_text}".strip()

    # Check for exact matches of ad_words in combined text
    ad_match = any(re.search(rf"\b{re.escape(word)}\b", combined_text, re.IGNORECASE) for word in ad_words)

    if ad_match:
        # Increment the ad count for the user
        link_counts[user_id]["ad_count"] += 1

        # Remove from unsafe_users if present (they are now "safe")
        unsafe_users.pop(user_id, None)

        # Mark user as "safe"
        safe_users[user_id] = {
            "name": user_full_name,
            "username": user_username,
        }

        # ✅ Reply to user with their stored `x_username`
        await update.message.reply_text(
            f"✖️ ID: @{x_username}\n"
        )

    else:
        # Add to unsafe_users only if they are not already marked as safe
        if user_id not in safe_users and user_id not in unsafe_users:
            unsafe_users[user_id] = {
                "name": user_full_name,
                "username": user_username,
            }
# Command to show users with multiple links
async def multiple_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    if not link_counts:
        await update.message.reply_text("No users have shared links yet!")
        return

    # Find users who have shared more than one link
    users_with_multiple_links = [
        f"{data['srno']}. {data['name']}- @{data['username']} : {data['link_count']}"
        for data in link_counts.values()
        if data['link_count'] > 1
    ]

    if not users_with_multiple_links:
        await update.message.reply_text("No users have shared multiple links yet.")
        return

    # Construct the message
    multiple_links_text = "Users with multiple links:\n" + "\n".join(users_with_multiple_links)
    await update.message.reply_text(multiple_links_text)


# Command to show unsafe users (only showing usernames)
async def show_unsafe_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    if not unsafe_users:
        await update.message.reply_text("🌟 Everyone is playing nice and staying safe! 🌟")
        return

    # Create a list of usernames from the unsafe users
    unsafe_usernames = "\n".join([f"{data['srno']}. {data['name']} -( @{data['username']} )" for data in unsafe_users.values()])

    # Send the list of unsafe usernames
    await update.message.reply_text(f"Unsafe users:\n{unsafe_usernames}")


# Command to show link counts
async def show_link_counts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    if not link_counts:
        await update.message.reply_text("📭 No users have shared links yet!")
        return

    # Count total users with links (with count > 0)
    total_users = sum(1 for data in link_counts.values() if data['link_count'] > 0)

    # Find users with more than 2 links
    users_with_more_than_2_links = [
        f"@{data['username']} : {data['link_count']} links"
        for data in link_counts.values()
        if data['link_count'] > 1
    ]

    # Construct the message
    counts_text = f"Total users who shared links: {total_users}"

    await update.message.reply_text(counts_text)


# Command to show a simple list of users with numbering
async def user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    if not link_counts:
        await update.message.reply_text("No users found!")
        return

    user_list_text = "List:\n\n"
    user_count = 0  # Keep track of how many users have been added

    for idx, data in enumerate(link_counts.values(), start=1):
        # Using Heavy Multiplication X symbol before username


        user_list_text += f"{idx}.✖️ ID - ( @{data['x_username']})\n"
        user_count += 1

        # If we reach 80 users, send the message and reset the text
        if user_count % 80 == 0:
            await update.message.reply_text(user_list_text)
            user_list_text = ""  # Reset text for the next batch

    # If there are remaining users, send them as well
    if user_list_text:
        await update.message.reply_text(user_list_text)



# Command to clear chat history (remove counts for a specific user or group)
async def clear_counts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    global link_counts, unsafe_users
    chat = update.effective_chat

    if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        link_counts = {}  # Reset all counts for the group
        unsafe_users = {}  # Reset unsafe users
        await update.message.reply_text("✅ Everything's cleared!")
    else:
        user = update.message.from_user
        if user.id in link_counts:
            del link_counts[user.id]
        if user.id in unsafe_users:
            del unsafe_users[user.id]
        await update.message.reply_text(f"All data for {user.full_name} has been cleared!")


async def show_ad_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global link_counts

    # Calculate the total number of users who completed the ad task
    total_completed_users = sum(1 for data in link_counts.values() if data.get("ad_count", 0) > 0)

    # Send a message to the user with the total count
    if total_completed_users > 0:
        await update.message.reply_text(f"✅ {total_completed_users} users have completed")
    else:
        await update.message.reply_text("❌ No users have completed the task")



async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

      # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    # Check if the user has provided arguments
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /muteuser @username duration (e.g., /muteuser @username 5h)")
        return

    # Extract username and duration
    username = context.args[0]
    duration = context.args[1]

    # Validate username (must start with @)
    if not username.startswith("@"):
        await update.message.reply_text("Invalid username")
        return

    # Validate duration (must be a valid time string like 5m, 2h, 1d)
    duration_match = re.match(r"(\d+)([smhd])", duration)
    if not duration_match:
        await update.message.reply_text("Invalid duration")
        return

    # Parse duration
    time_value = int(duration_match.group(1))
    time_unit = duration_match.group(2)
    if time_unit == "s":
        mute_duration = timedelta(seconds=time_value)
    elif time_unit == "m":
        mute_duration = timedelta(minutes=time_value)
    elif time_unit == "h":
        mute_duration = timedelta(hours=time_value)
    elif time_unit == "d":
        mute_duration = timedelta(days=time_value)

    # Find user by username in link_counts or unsafe_users
    target_user_id = None
    target_user_full_name = None
    for user_id, data in {**link_counts, **unsafe_users}.items():
        if f"@{data['username']}" == username:
            target_user_id = user_id
            target_user_full_name = data['name']
            break

    # If user not found
    if not target_user_id:
        await update.message.reply_text(f"User {username} not found")
        return

    # Check if the bot has permissions to mute
    chat = update.effective_chat
    bot_member = await chat.get_member(context.bot.id)
    if not bot_member.can_restrict_members:
        await update.message.reply_text("I need 'Manage Members' permissions to mute users.")
        return

    # Mute the user
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=update.message.date + mute_duration,
        )
        await update.message.reply_text(
            f"Muted {target_user_full_name} ({username}) for {mute_duration.total_seconds() // 3600} hour."
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to mute user: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):

      # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    # Check if the user has provided a username
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unmuteuser @username (e.g., /unmuteuser @username)")
        return

    # Extract username
    username = context.args[0]

    # Validate username
    if not username.startswith("@"):
        await update.message.reply_text("Invalid username")
        return

    # Find user by username in link_counts or unsafe_users
    target_user_id = None
    target_user_full_name = None
    for user_id, data in {**link_counts, **unsafe_users}.items():
        if f"@{data['username']}" == username:
            target_user_id = user_id
            target_user_full_name = data['name']
            break

    # If user not found
    if not target_user_id:
        await update.message.reply_text(f"User {username} not found.")
        return

    # Check if the bot has permissions to unmute
    chat = update.effective_chat
    bot_member = await chat.get_member(context.bot.id)
    if not bot_member.can_restrict_members:
        await update.message.reply_text("I need 'Manage Members' permissions to unmute users.")
        return

    # Unmute the user
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_user_id,
            permissions=ChatPermissions(can_send_messages=True),
        )
        await update.message.reply_text(f"Unmuted {target_user_full_name} ({username}).")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")

# Command to enable ad tracking
async def start_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global tracking_enabled

     # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    tracking_enabled = True
    await update.message.reply_text("🎉 Ad tracking is live! Watching 'ad,' 'alldone,' 'dn,' and 'alldn' like a hawk. 👀 Let’s make it count!")

# Command to stop ad tracking (optional)
async def stop_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global tracking_enabled

    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    tracking_enabled = False
    await update.message.reply_text("Ad trackinghas been Stopped!")

# Command to show rules
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the user is an admin
    if not await is_admin(update):
        await update.message.reply_text("🚨 Unauthorized access attempt detected!")
        return

    rules_text = """
    ✨ ILLUMINATI-LIKE GC ✨

    RULES & REGULATIONS ⚠️

    1) Each member is required to post 1 tweet per day.

    2) When sharing links, remove everything after the “?” in the URL to maintain privacy.

    3) Interact with all posts on the TL account during each session.

    4) The TL (Timeline) will be updated after every session.
       - Ensure all engagements are completed before the deadline.

    5) After completing engagements, send an “ad” message in the group to confirm.

    6) All activities must be completed within 1 hour and 40 minutes of the TL update.
       - Missed deadlines will result in being placed on the unsafe list.

    7) Every member must like all posts on the TL.
       - Skipping even one post will lead to penalties.
    """
    await update.message.reply_text(rules_text)

async def mute_all_unsafe_users(update: Update, context: ContextTypes.DEFAULT_TYPE):


    if not await is_admin(update):
        STICKER_ID = "CAACAgUAAxkBAAICLWfAVQEf_k6dGDuoUbGDUrcng0BlAAJWBQACDLDZVke9Qr6WRu8KNgQ"

        await update.message.reply_sticker(STICKER_ID)  # Send sticker
        return  # Stop execution if user is not an admin
    # Check if the user has provided a duration
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /muteall duration (e.g., /muteall 5h)")
        return

    # Extract duration
    duration = context.args[0]

    # Validate duration (must be a valid time string like 5m, 2h, 1d)
    duration_match = re.match(r"(\d+)([smhd])", duration)
    if not duration_match:
        await update.message.reply_text("Invalid duration. Use format like 5m (minutes), 2h (hours), or 1d (days).")
        return

    # Parse duration
    time_value = int(duration_match.group(1))
    time_unit = duration_match.group(2)

    if time_unit == "s":
        mute_duration = timedelta(seconds=time_value)
    elif time_unit == "m":
        mute_duration = timedelta(minutes=time_value)
    elif time_unit == "h":
        mute_duration = timedelta(hours=time_value)
    elif time_unit == "d":
        mute_duration = timedelta(days=time_value)

    # Check if there are users to mute
    if not unsafe_users:
        await update.message.reply_text("No users in the unsafe list to mute.")
        return

    # Check if the bot has permissions to mute
    chat = update.effective_chat
    bot_member = await chat.get_member(context.bot.id)
    if not bot_member.can_restrict_members:
        await update.message.reply_text("I need 'Manage Members' permissions to mute users.")
        return

    # Mute all unsafe users
    muted_users = []
    failed_users = []

    for user_id, data in unsafe_users.items():
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=update.message.date + mute_duration,
            )
            muted_users.append(f"{data['name']} (@{data['username']})")
        except Exception as e:
            failed_users.append(f"{data['name']} (@{data['username']}): {e}")

    # Prepare response message
    response_message = "✅ Muted users:\n" + "\n".join(muted_users) if muted_users else "❌ No users were muted."

    if failed_users:
        response_message += "\n\n⚠️ Failed to mute:\n" + "\n".join(failed_users)

    await update.message.reply_text(response_message)




def main():
    # Replace 'YOUR_BOT_TOKEN' with your bot's token
    application = Application.builder().token("7677452394:AAGt0gfCkFPwTqlQmVohDWwH_2yGMDeUvSM").build()

    # Command handlers
    application.add_handler(CommandHandler("starts", start))
    application.add_handler(CommandHandler("count", show_link_counts))
    application.add_handler(CommandHandler("unsafe", show_unsafe_users))
    application.add_handler(CommandHandler("close", clear_counts))
    application.add_handler(CommandHandler("muteuser", mute_user))
    application.add_handler(CommandHandler("unmuteuser", unmute_user))
    application.add_handler(CommandHandler("start_ad_track", start_ad))  # New command
    application.add_handler(CommandHandler("ad_total", show_ad_completed))
    application.add_handler(CommandHandler("rules", rules))  # New rules command
    application.add_handler(CommandHandler("mult", multiple_links))  # New multiple links command
    application.add_handler(CommandHandler("userlist", user_list))
    application.add_handler(CommandHandler("muteall", mute_all_unsafe_users))



    # Message handlers for links and specific words with media
    application.add_handler(MessageHandler(filters.Entity("url") | filters.Entity("text_link"), count_links))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL, count_ad_messages))



    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
