import datetime
import logging
import traceback
from contextlib import suppress

import aiohttp
from discord.ext import commands

from firetail.core.context import Context

INTRO = (
    "=========================================",
    "Firetail - The Discord Bot for EVE Online",
    "========================================="
)

log = logging.getLogger("firetail")


async def update_discordbots(bot):
    if bot.debug:
        return

    try:
        token = bot.config.dbots_token
    except AttributeError:
        token = None

    if not token:
        return

    with suppress(aiohttp.ClientError):
        db_token = bot.config.db_token
        url = f"https://discordbots.org/api/bots/{bot.user.id}/stats"
        headers = {"Authorization": db_token}
        payload = {"server_count": len(bot.guilds)}
        async with bot.session as r:
            r.post(url, data=payload, headers=headers)


def init_events(bot, launcher=None):
    @bot.event
    async def on_connect():
        if hasattr(bot, 'launch_time'):
            return print("Reconnected.")

        if not hasattr(bot, 'launch_time'):
            bot.launch_time = datetime.datetime.utcnow()
        if not launcher:
            print("\n".join(INTRO))
        if bot.invite_url:
            print(f"\nInvite URL: {bot.invite_url}\n")

    @bot.event
    async def on_ready():
        guilds = len(bot.guilds)
        users = len(list(bot.get_all_members()))
        if guilds:
            print(f"Servers: {guilds}")
            print(f"Members: {users}")
        else:
            print("Invite me to a server!")
        await update_discordbots(bot)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.error(
                "A required argument was missing",
                f"Command Usage: ```{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}```"
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.error(
                "An invalid argument was encountered",
                f"Command Usage: ```{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}```"
            )
        elif isinstance(error, commands.DisabledCommand):
            pass
        elif isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.error("Not available in DMs")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.error(f"Command is on cooldown.", "Try again in {error.retry_after:.2f}s")
        elif isinstance(error, commands.CommandInvokeError) and ctx.author.id is bot.config.bot_master:
            # Need to test if the following still works
            """
            no_dms = "Cannot send messages to this user"
            is_help_cmd = ctx.command.qualified_name == "help"
            is_forbidden = isinstance(error.original, discord.Forbidden)
            if is_help_cmd and is_forbidden and error.original.text == no_dms:
                msg = ("I couldn't send the help message to you in DM. Either"
                       " you blocked me or you disabled DMs in this server.")
                await ctx.send(msg)
                return
            """
            log.exception(f"Exception in command '{ctx.command.qualified_name}'", exc_info=error.original)
            message = f"Error in command '{ctx.command.qualified_name}'. Check your console or logs for details."
            exception_log = "Exception in command '{ctx.command.qualified_name}'\n"
            exception_log += "".join(traceback.format_exception(type(error), error, error.__traceback__))
            bot._last_exception = exception_log
            if "Missing Permissions" in exception_log:
                await ctx.error("Permissions are missing.")
            else:
                await ctx.send(message)

        else:
            log.exception(type(error).__name__, exc_info=error)

    @bot.event
    async def on_message(message):
        bot.counter["messages_read"] += 1
        if message.author.bot:
            return

        ctx = await bot.get_context(message, cls=Context)
        await bot.invoke(ctx)

    @bot.event
    async def on_resumed():
        bot.counter["sessions_resumed"] += 1

    @bot.event
    async def on_command(command):
        bot.counter["processed_commands"] += 1

        if not bot.config.dm_only:
            return
        if 'help' not in command.message.content.lower():
            return
        if command.guild:
            await command.send(f"{command.author.mention} check your DM's for the help info.")

    @bot.event
    async def on_guild_join(guild):
        log.info(f"Connected to a new guild. Guild ID/Name: {guild.id}/{guild.name}")
        await update_discordbots(bot)

    @bot.event
    async def on_guild_remove(guild):
        log.info("Leaving guild. Guild ID/Name: {guild.id}/{guild.name}")
        await update_discordbots(bot)

    @bot.event
    async def on_member_ban(guild, user):
        log.info("New Ban Reported. Guild ID/Name: {guild.id}/{guild} -- Member ID/Name: {user.id}/{user}")

    @bot.event
    async def on_member_join(member):
        if bot.config.enable_welcome is True:
            await member.send(bot.config.welcome_string)
