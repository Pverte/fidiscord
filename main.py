from discord.ext import commands
import discord
import asyncio
import os
import sys
from datetime import datetime

from pymongo_get_database import get_database

# Get the database
dbname = get_database()
levels_db = dbname["levels"]
warnings_db = dbname["warnings"]

# Bot setup
intents = discord.Intents(guilds=True, members=True, messages=True, message_content=True)
bot = commands.Bot(command_prefix='!', intents=intents)

# Constants
levels_roles = {5: "level 5", 10: "level 10", 20: "level 20", 30: "level 30", 50: "level 50", 75: "level 75", 100: "level 100"}
verification_role = 1049314940709773352
welcome_chan = 1048814654262087761
modchan = 1049065426744783033

# Global variable to hold the moderation channel
modchannel = None

# Send log message function
async def sendlog(embed):
    global modchannel
    if modchannel is None:
        modchannel = bot.get_channel(modchan)
    await modchannel.send(embed=embed)

# Helper functions

def check_warnings(user_id):
    return warnings_db.count_documents({"author_id": str(user_id)})

def save_warning(author_id, user_id, reason, moderator_id):
    current_time = datetime.now()
    warnings_db.insert_one({
        "author_id": str(user_id),
        "reason": reason,
        "moderator_id": str(moderator_id),
        "timestamp": current_time
    })

# Bot events
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print(f"Bot ID: {bot.user.id}")
    await bot.change_presence(activity=discord.Game(name='Fur island'))

@bot.event
async def on_message(message):
    if not message.author.bot:
        author_id = message.author.id
        levels_author = levels_db.find_one({"_id": author_id})
        if levels_author is None: # if the user is not in the database, add them
            levels_db.insert_one({"_id": author_id, "xp": 0, "level": 1})
            levels_author = levels_db.find_one({"_id": author_id})
        levels_db.update_one({"_id": author_id}, {"$inc": {"xp": 1}})

        xp_needed = ((levels_author["level"]+1)**2)*10
        if levels_author["xp"] >= xp_needed:
            await message.reply(f"Congrats {message.author.mention}! You are now level {levels_author['level'] + 1}!")
            levels_db.update_one({"_id": author_id}, {"$inc": {"level": 1}})

@bot.event
async def on_member_update(before, after):
    after_role = [role.id for role in after.roles]
    before_role = [role.id for role in before.roles]
    if verification_role in after_role and verification_role not in before_role:
        print(f"{after.name} has been verified!")
        channel = bot.get_channel(welcome_chan)
        await channel.send(f"<@1062907835199004772>\n Welcome {after.mention} to Fur Island! Explore the server’s awesome features and invite some friends to help grow the server! We hope you enjoy your stay!\n \n Don't forget to check out our roles by clicking Channels & Roles at the top of the channel list!")

    # send an embed message with the updated profile before and after
    if before.display_name != after.display_name:
        embed = discord.Embed(title="New event", description=f"{before.mention} has changed his nickname", colour=discord.Colour.red())
        embed.add_field(name="Before :", value=before.display_name, inline=False)
        embed.add_field(name="After :", value=after.display_name, inline=False)
        embed.set_author(name=before, icon_url=before.display_avatar)
        embed.set_footer(text=f"ID: {before.id}")
        await sendlog(embed)
    if before.roles != after.roles:
        embed = discord.Embed(title="New event", description=f"{before.mention} has changed his roles", colour=discord.Colour.red())
        embed.add_field(name="Before :", value=[role.name for role in before.roles], inline=False)
        embed.add_field(name="After :", value=[role.name for role in after.roles], inline=False)
        embed.set_author(name=before, icon_url=before.display_avatar)
        print(before.display_avatar)
        embed.set_footer(text=f"ID: {before.id}")
        await sendlog(embed)

@bot.event
async def on_message_delete(message):
    embed = discord.Embed(title="Message Deleted", description=f"{message.author.mention} has deleted a message", colour=discord.Colour.red())
    embed.add_field(name="Message:", value=message.content or "No content", inline=False)
    embed.add_field(name="Channel:", value=message.channel.mention, inline=False)
    embed.set_author(name=message.author.name, icon_url=message.author.display_avatar)
    embed.set_footer(text=f"ID: {message.author.id}")

    print("Sending log message:", embed.to_dict())  
    await sendlog(embed=embed)

@bot.event
async def on_application_command_error(context, exception):
    devlog = bot.get_channel(1130971500439158865)
    await devlog.send(f"uups guys, we got an error wit the slash command {context}:\n {exception}")
    print(exception)
@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="New event", description=f"{member.mention} has left the server", colour=discord.Colour.red())
    embed.set_author(name=member, icon_url=member.display_avatar)
    embed.set_footer(text=f"ID: {member.id}")
    await sendlog(embed)

@bot.slash_command(name="ban", description="Ban a user from the server") # ban command
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member):
    await member.ban(reason=f"Banned by {ctx.author.name}")
    await ctx.respond(f"{member.name} has been banned from the server.", ephemeral=True)

@bot.slash_command(name="unban", description="Unban a user from the server")
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: str):
    try:
        user_id = int(user_id)  # Convert the user_id to an integer
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.respond(f"{user.mention} has been unbanned.")
    except ValueError:
        await ctx.respond("Please provide a valid user ID.")
    except discord.NotFound:
        await ctx.respond("User not found. Make sure you provide the correct user ID.")

@bot.slash_command(name="kick", description="Kick an user from the server") # kick command
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member):
    await member.kick(reason=f"Kicked by {ctx.author.name}")
    await ctx.respond(f"{member.name} has been kicked from the server.")


@bot.slash_command(name="warn", description="Warn a user.")
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason: str):
    save_warning(member.id, ctx.author.id, reason, ctx.author.id)  # Assuming ctx.author.id is the moderator ID
    num_warnings = check_warnings(member.id)
    print("passed check_warnings")
    print(num_warnings)
    if num_warnings >= 3:
        await member.kick(reason="Reached three warnings")
        await ctx.respond(f"{member.name} has been kicked for reaching three warnings.")
    else:
        try:
            dm_channel = await member.create_dm()
            await dm_channel.send(f"You have been warned in **{ctx.guild.name}** for: **{reason}**")
        except discord.errors.HTTPException:
            await ctx.respond(f"Warning for {member.name} (ID: {member.id}) recorded, but I couldn't send a DM to the user.")
            return
        await ctx.respond(f"**{member.name} has been warned** for: {reason}.")

@bot.slash_command(name="warnings", description="View warnings of a user")
@commands.has_permissions(kick_members=True)
async def warnings(ctx, member: discord.Member):
    user_warnings = list(warnings_db.find({"author_id": str(member.id)}))  # Convert Cursor to a list
    num_warnings = len(user_warnings)
    if num_warnings == 0:
        await ctx.respond(f"{member.name} has no warnings.", ephemeral=True)
        return
    warning_message = f"Warnings for {member.name} (ID: {member.id}):\n\n"
    for warning in user_warnings:
        moderator_id = warning["moderator_id"]
        moderator = bot.get_user(int(moderator_id)) or f"Unknown User (ID: {moderator_id})"
        timestamp = warning["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        warning_message += f"**ID:** {warning['_id']} - **Reason:** {warning['reason']} - **Moderator:** {moderator} - **Date:** {timestamp}\n"

    await ctx.respond(warning_message)

@bot.slash_command(name="unwarn", description="Remove warnings from a user")
@commands.has_permissions(kick_members=True)
async def remove_warn(ctx, member: discord.Member, num_warns: int):
    num_warnings = check_warnings(member.id)

    if num_warns <= 0:
        await ctx.respond("Please provide a positive number of warnings to remove.", ephemeral=True)
        return

    if num_warnings == 0:
        await ctx.respond(f"{member.name} has no warnings to remove.", ephemeral=True)
        return

    if num_warnings < num_warns:
        await ctx.respond(f"{member.name} only has {num_warnings} warning(s).", ephemeral=True)
        return
    #removes the number of warnings from the user from the warnings database
    for i in range(num_warns):
        warning = warnings_db.find_one({"author_id": str(member.id)})
        warnings_db.delete_one(warning)
    await ctx.respond(f"{num_warns} warnings removed for {member.name}.")

@bot.slash_command(name="mute", description="Mute an user")
@commands.has_permissions(kick_members=True)
async def mute(ctx, member: discord.Member, reason=None):
    guild = ctx.guild.id
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, speak=False, send_messages=False, read_message_history=True, read_messages=True)
    await member.add_roles(muted_role, reason=reason)
    embed = discord.Embed(title="New event", description=f"{member.mention} has been muted", colour=discord.Colour.red())
    embed.add_field(name="Moderator :", value=ctx.author.mention, inline=False)
    embed.add_field(name="Raison :", value=reason, inline=False)
    await sendlog(embed)
    await ctx.respond(f"{member.display_name} has been muted successfully.")

@bot.slash_command(name="unmute", description="Unmute an user")
@commands.has_permissions(kick_members=True)
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    await member.remove_roles(muted_role)
    global modchannel
    if modchannel is None:
        modchannel = bot.get_channel(modchan)
    await modchannel.send(embed=discord.Embed(title="New event", description=f"{member.mention} has been unmuted", colour=discord.Colour.green()))
    await ctx.respond(f"{member.display_name} has been unmuted successfully.")

@bot.slash_command(name="purge", description="Delete a specific number of messages in the channel.")
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    limit = min(limit + 1, 1000)
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.respond(f"Deleted {len(deleted) - 1} messages.")

@bot.slash_command(name="level", description="Check your level and XP")
async def level(ctx, member: discord.Member = None):
    if member is not None:
        author_id = member.id
        author_name = member.name
    else:
        author_id = ctx.author.id
        author_name = ctx.author.name
    levels_author = levels_db.find_one({"_id": author_id})
    if levels_author is not None:
        user_level = levels_author["level"]
        user_xp = levels_author["xp"]
        await ctx.respond(f"{author_name}'s level is {user_level} and have {user_xp} XP. {author_name} needs {((user_level+1)**2)*10 - user_xp} XP to reach the next level.")
    else:
        await ctx.respond("You haven't earned any XP yet.")

@bot.slash_command(name="leaderboard", description="Check the server's leaderboard")
async def leaderboard(ctx):
    leaderboard = levels_db.find().sort("level", -1).limit(10)
    embed = discord.Embed(title="Leaderboard", color=discord.Colour.blurple())
    for index, user in enumerate(leaderboard):
        user_id = user["_id"]
        user_obj = await bot.fetch_user(user_id)
        user_name = user_obj.name
        user_level = user["level"]
        user_xp = user["xp"]
        embed.add_field(name=f"{index+1}. {user_name}", value=f"Level: {user_level} with {user_xp} XP", inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(name="whois", description="Get information about a user")
async def whois(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(title="User Information", color=discord.Colour.blurple())
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="Name", value=member.name, inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Bot", value=member.bot, inline=True)
    roles_str = ", ".join(role.mention for role in member.roles[1:])
    embed.add_field(name="Roles", value=roles_str, inline=False)
    embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)

    await ctx.respond(embed=embed)


@bot.slash_command(name="serverinfo", description="Get information about the server")
async def server_info(ctx):
    guild = ctx.guild

    # Get information about the server
    server_name = guild.name
    server_owner = guild.owner
    server_creation_date = guild.created_at.strftime("%Y-%m-%d %H:%M:%S")
    member_count = guild.member_count
    role_count = len(guild.roles)
    text_channel_count = len(guild.text_channels)
    voice_channel_count = len(guild.voice_channels)
    verification_level = guild.verification_level.name
    server_icon_url = guild.icon.url if guild.icon else discord.Embed.Empty  # Use the server icon URL or set to discord.Embed.Empty if no icon

    # Create the embed with the server information
    embed = discord.Embed(title="Server Information", color=discord.Colour.green())
    embed.set_thumbnail(url=server_icon_url)  # Set the server icon URL as the thumbnail
    embed.add_field(name="Name", value=server_name, inline=False)
    embed.add_field(name="Owner", value=server_owner.mention, inline=False)
    embed.add_field(name="Creation Date", value=server_creation_date, inline=False)
    embed.add_field(name="Members", value=member_count, inline=True)
    embed.add_field(name="Roles", value=role_count, inline=True)
    embed.add_field(name="Text Channels", value=text_channel_count, inline=True)
    embed.add_field(name="Voice Channels", value=voice_channel_count, inline=True)
    embed.add_field(name="Verification Level", value=verification_level, inline=True)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)

    await ctx.respond(embed=embed)

bot_start_time = datetime.utcnow()

@bot.slash_command(name="uptime", description="Check the bot's uptime")
async def uptime(ctx):
    uptime_delta = datetime.utcnow() - bot_start_time
    days = uptime_delta.days
    hours, remainder = divmod(uptime_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    uptime_str = f"{days} days, {hours} hrs, {minutes} min, {seconds} sec"
    embed = discord.Embed(title="Uptime", description=uptime_str, color=discord.Colour.blue())
    await ctx.respond(embed=embed)

@bot.slash_command(name="restart")
async def restart(ctx):
    allowed_users = [749895975694499930, 577089415369981952]
    
    if ctx.author.id not in allowed_users:
        await ctx.respond("You are not authorized to restart the bot.", ephemeral=True)
        return
    await ctx.respond("<:yes:1131632585244688424> All processes have been restarted", ephemeral=False)
    print("Restarting bot...")
    os.execv(sys.executable, ["python", os.path.abspath(__file__)])

bot.run('MTEyODI0MjY5Mzc0MzU3NTA4MA.GE8qFX.jTn_jHw3MuuHLkQu_Q6YdvS9pP58xI-7OMo8FY')
