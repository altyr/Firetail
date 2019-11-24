import asyncio
import functools
import logging
import textwrap
from contextlib import suppress

import discord
from discord.ext import commands

from firetail.core import checks
from firetail.lib import db

log = logging.getLogger(__name__)


PERMS_MAP = {
    "kick_members": 1,
    "ban_members": 2,
    "administrator": 3,
    "manage_channels": 4,
    "manage_guild": 5,
    "add_reactions": 6,
    "view_audit_log": 7,
    "priority_speaker": 8,
    "stream": 9,
    "read_messages": 10,
    "send_messages": 11,
    "send_tts_messages": 12,
    "manage_messages": 13,
    "embed_links": 14,
    "attach_files": 15,
    "read_message_history": 16,
    "mention_everyone": 17,
    "external_emojis": 18,
    "view_guild_insights": 19,
    "connect": 20,
    "speak": 21,
    "mute_members": 22,
    "deafen_members": 23,
    "move_members": 24,
    "use_voice_activation": 25,
    "change_nickname": 26,
    "manage_nicknames": 27,
    "manage_roles": 28,
    "manage_webhooks": 29,
    "manage_emojis": 30
}


def same_len(txt, name_len):
    """Multiline string based on max available width."""
    return '\n'.join(txt + ([' '] * (name_len - len(txt))))


def perms_result(perms, req_perms):
    """Format permissions based on requirements."""
    data = []
    meet_req = perms >= req_perms
    result = "**PASS**" if meet_req else "**FAIL**"
    data.append(f"{result} - {perms.value}\n")
    true_perms = [k for k, v in dict(perms).items() if v is True]
    false_perms = [k for k, v in dict(perms).items() if v is False]
    req_perms_list = [k for k, v in dict(req_perms).items() if v is True]
    true_perms_str = '\n'.join(true_perms)
    if not meet_req:
        missing = '\n'.join([p for p in false_perms if p in req_perms_list])
        data.append(f"**MISSING**\n{missing}\n")
    if true_perms_str:
        data.append(f"**ENABLED**\n{true_perms_str}\n")
    return '\n'.join(data)


class Core(commands.Cog):
    """General bot functions."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["exit"])
    @checks.is_owner()
    async def shutdown(self, ctx):
        """Shutdown the bot"""

        with suppress(discord.HTTPException):
            await ctx.embed(title='Shutting down.', colour='red', icon="https://i.imgur.com/uBYS8DR.png")

        await self.bot.shutdown()

    @commands.command()
    @checks.is_owner()
    async def restart(self, ctx):
        """Restart the bot"""

        with suppress(discord.HTTPException):
            await ctx.embed(title='Restarting.', colour='red', icon="https://i.imgur.com/uBYS8DR.png")

        await self.bot.shutdown(restart=True)

    @commands.group(name="set", invoke_without_command=True)
    @checks.is_co_owner()
    async def set_(self, ctx):
        """Change bot settings"""

        await ctx.send_help(ctx.command)

    @set_.command(name="activity")
    @checks.is_admin()
    async def set_activity(self, ctx, *, activity: discord.Game = None):
        """Set bot activity"""

        await self.bot.change_presence(status=ctx.me.status, activity=activity)
        await ctx.success('Activity set.')

    @set_.command(name="status")
    @checks.is_admin()
    async def set_status(self, ctx, *, status: str = "online"):
        """
        Set bot status to online, idle or dnd
        """

        try:
            status = discord.Status[status.lower()]
        except KeyError:
            await ctx.error("Invalid Status", "Only `online`, `idle` or `dnd` statuses are available.")
        else:
            await self.bot.change_presence(status=status, activity=ctx.me.activity)
            await ctx.success(f"Status changed to {status}.")

    @set_.command(name="username", aliases=["name"])
    @checks.is_admin()
    async def set_username(self, ctx, *, username: str):
        """Set bot username"""

        try:
            await self.bot.user.edit(username=username)

        except discord.HTTPException:
            await ctx.error(
                "Failed to change name",
                "Remember that you can only do it up to 2 times an hour.\n"
                "Use nicknames if you need frequent changes.\n"
                f"`{ctx.prefix}set nickname`"
            )

        else:
            await ctx.success("Username set.")

    @set_.command(name="avatar")
    @checks.is_admin()
    async def set_avatar(self, ctx, *, avatar_url: str):
        """Set bot avatar"""

        async with self.bot.session.get(avatar_url) as r:
            data = await r.read()

        try:
            await self.bot.user.edit(avatar=data)

        except discord.HTTPException:
            await ctx.error(
                "Failed to set avatar",
                "You can only edit user details up to 2 times an hour. "
                "URLs must be a direct link to a JPG / PNG."
            )

        else:
            await ctx.success("Avatar set.")

    @set_.command(name="nickname")
    @checks.is_admin()
    async def set_nickname(self, ctx, *, nickname: str):
        """Set bot nickname"""

        try:
            await ctx.guild.me.edit(nick=nickname)

        except discord.Forbidden:
            await ctx.success(
                "Failed to set nickname",
                "I'm missing permissions to change my nickname. "
                f"Use `{ctx.prefix}get guildperms` to check permissions."
            )

        else:
            await ctx.success("Nickname set.")

    @commands.command()
    @checks.spam_check()
    async def uptime(self, ctx):
        """Show how long the bot has been running for"""

        try:
            await ctx.embed('Uptime', self.bot.uptime_str, colour='blue', icon="https://i.imgur.com/82Cqf1x.png")

        except discord.errors.Forbidden:
            await ctx.send(f"Uptime: {self.bot.uptime_str}")

    @commands.command(aliases=["botinvite"])
    @checks.spam_check()
    async def invite(self, ctx, plain_url: bool = False):
        """Provide the bot invite link"""

        if not plain_url:
            try:
                await ctx.embed(
                    'Click to invite me to your server!',
                    title_url=self.bot.invite_url,
                    colour='blue',
                    icon="https://i.imgur.com/DtPWJPG.png"
                )
            except discord.errors.Forbidden:
                pass
            else:
                return

        await ctx.send(f"Invite URL: <{self.bot.invite_url}>")

    @commands.command()
    @checks.spam_check()
    async def about(self, ctx):
        """Show information about Firetail"""

        author_repo = "https://github.com/scragly"
        bot_repo = author_repo + "/Firetail"
        server_url = "https://discord.gg/ZWmzTP3"
        owner = "Discord: Scragly#5146\nEVE: Kyo Kuronami"
        member_count = sum(g.member_count for g in self.bot.guilds)
        server_count = len(self.bot.guilds)

        description = (
            "Made for EVE Online Communities\n"
            f"[**Docs & Source**]({bot_repo})\n"
            f"[**Support Server**]({server_url})\n"
            f"[**Invite Me**]({self.bot.invite_url})\n"
            "\n"
            f"See available commands with:\n`{ctx.prefix}help`\n"
            "\n"
            f"**Maintained and Developed by**\n"
            f"{owner}\n"
            "\n"
            f"**Servers:** {server_count}\n"
            f"**Members:** {member_count}\n"
            f"**Uptime:** {self.bot.uptime_str}"
        )

        try:
            await ctx.info("About Firetail", description, thumbnail=self.bot.user.avatar_url_as(format='png'))

        except discord.HTTPException:
            await ctx.send("I need the `Embed links` permission for this command.")

    @commands.group(name="get", invoke_without_command=True)
    @checks.is_co_owner()
    async def get_(self, ctx):
        """Show current bot settings"""

        await ctx.send_help(ctx.command)

    @commands.group(category="Bot Info", aliases=['perms'], invoke_without_command=True)
    @checks.is_mod()
    async def permissions(self, ctx, *, channel_id: int = None):
        """Show all current contextual permissions for Firetail."""

        if not await ctx.is_co_owner() and channel_id is not None:
            return await ctx.error('Only co-owners of the bot can specify channel')

        channel = ctx.get(ctx.bot.get_all_channels(), id=channel_id)
        guild = channel.guild if channel else ctx.guild
        channel = channel or ctx.channel
        guild_perms = guild.me.guild_permissions
        chan_perms = channel.permissions_for(guild.me)
        req_perms = ctx.bot.req_perms

        embed = await ctx.info('Bot Permissions', send=False)

        wrap = functools.partial(textwrap.wrap, width=20)
        names = [wrap(channel.name), wrap(guild.name)]
        if channel.category:
            names.append(wrap(channel.category.name))
        name_len = max(len(n) for n in names)
        names = [same_len(n, name_len) for n in names]
        chan_msg = [f"**{names[0]}**\n{channel.id}\n"]
        guild_msg = [f"**{names[1]}**\n{guild.id}\n", perms_result(guild_perms, req_perms)]
        chan_msg.append(perms_result(chan_perms, req_perms))
        embed.add_field(name='GUILD', value='\n'.join(guild_msg))
        if channel.category:
            cat_perms = channel.category.permissions_for(guild.me)
            cat_msg = [f"**{names[2]}**\n{channel.category.id}\n", perms_result(cat_perms, req_perms)]
            embed.add_field(name='CATEGORY', value='\n'.join(cat_msg))
        embed.add_field(name='CHANNEL', value='\n'.join(chan_msg))

        try:
            await ctx.send(embed=embed)
        except discord.errors.Forbidden:
            # didn't have permissions to send a message with an embed
            try:
                msg = "I couldn't send an embed here, so I've sent you a DM"
                await ctx.send(msg)
            except discord.errors.Forbidden:
                # didn't have permissions to send a message at all
                pass
            await ctx.author.send(embed=embed)

    @permissions.command(name="guild", aliases=["server"])
    @checks.is_admin()
    async def perms_guild(self, ctx):
        """Show permissions for Firetail for the current guild."""

        guild_perms = ctx.guild.me.guild_permissions
        perms_compare = guild_perms >= self.bot.req_perms
        msg = f"Guild Permissions: {guild_perms.value}\n"
        msg += f"Met Minimum Permissions: {perms_compare}\n\n"

        if not perms_compare:
            msg += (
                "You can reconfigure the bot role by\n"
                f"[reauthorising the permissions here]({self.bot.invite_url}).\n\n"
                "The new auth will update the existing\n"
                "bot role automatically.\n\n"
            )

        for perm, bitshift in PERMS_MAP.items():
            if bool((self.bot.req_perms.value >> bitshift) & 1):
                if bool((guild_perms.value >> bitshift) & 1):
                    msg += f":white_small_square:  {perm}\n"
                else:
                    msg += f":black_small_square:  {perm}\n"

        embed = await ctx.info('Guild Permissions', msg, send=False)

        try:
            if guild_perms.embed_links:
                await ctx.send(embed=embed)
            else:
                await ctx.send(msg)

        except discord.errors.Forbidden:
            await ctx.author.send(embed=embed)

    @permissions.command(name="channel", aliases=["chan"])
    @checks.is_admin()
    async def perms_channel(self, ctx):
        """Get permissions for Firetail for the current channel."""

        chan_perms = ctx.channel.permissions_for(ctx.guild.me)
        req_perms = self.bot.req_perms
        perms_compare = chan_perms >= req_perms
        msg = f"Channel Permissions: {chan_perms.value}\n"
        msg += f"Met Minimum Permissions: {perms_compare}\n\n"

        for perm, bitshift in PERMS_MAP.items():
            if bool((req_perms.value >> bitshift) & 1):
                if bool((chan_perms.value >> bitshift) & 1):
                    msg += f":white_small_square:  {perm}\n"
                else:
                    msg += f":black_small_square:  {perm}\n"

        embed = await ctx.info('Channel Permissions', msg, send=False)

        try:
            if chan_perms.embed_links:
                await ctx.send(embed=embed)
            else:
                await ctx.send(msg)

        except discord.errors.Forbidden:
            await ctx.author.send(embed=embed)

    @get_.command()
    @checks.spam_check()
    async def resumes(self, ctx):
        """Get websocket reconnection count."""

        await ctx.info(f"Connections Resumed: {self.bot.resumed_count}")

    @commands.command()
    @checks.spam_check()
    async def ping(self, ctx):
        """Get the Discord API response time."""

        msg = f"{(self.bot.ws.latency * 1000):.2f} ms"
        await ctx.info(f"Bot Latency: {msg}")

    @commands.command()
    @checks.is_mod()
    async def purge(self, ctx, msg_number: int = 10):
        """
        Delete a number of messages from the channel.

        Default is 10. Max 100.
        """

        if ctx.guild.id == 202724765218242560:
            return

        if msg_number > 100:
            await ctx.error("No more than 100 messages can be purged at a time.")
            return

        deleted = await ctx.channel.purge(limit=msg_number)
        s = "s" if len(deleted) > 1 else ""
        result_msg = await ctx.info(f'Deleted {len(deleted)} message{s}.')
        await asyncio.sleep(3)
        await result_msg.delete()

    @commands.command(name="reload_em")
    @checks.is_co_owner()
    async def reload_em(self, ctx):
        """Reload Extension Manager."""

        try:
            self.bot.unload_extension('firetail.core.extension_manager')
            self.bot.load_extension('firetail.core.extension_manager')
            await ctx.success('Extension Manager reloaded.')
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            await ctx.error('Error loading Extension Manager', msg)
            raise

    @commands.command()
    @checks.spam_check()
    async def prefix(self, ctx, *, new_prefix: str = None):
        """
        Get and set server prefix.

        Use the argument 'reset' to reset the guild prefix to default.
        """

        if not ctx.guild:
            if new_prefix:
                await ctx.error("Prefix cannot be set in DMs.")
                return

            await ctx.info(f"Prefix is {self.bot.default_prefix}")
            return

        if not new_prefix:
            guild_prefix = self.bot.prefixes.get(ctx.guild.id)
            prefix = guild_prefix or self.bot.default_prefix
            await ctx.info(f"Prefix is {prefix}")
            return

        if await checks.check_is_admin(ctx):
            await db.execute_sql(
                "INSERT OR REPLACE INTO prefixes(guild_id, prefix)"
                "VALUES(?, ?)", (ctx.guild.id, new_prefix)
            )

            self.bot.prefixes[ctx.guild.id] = new_prefix

            await ctx.info(f"Prefix set to {new_prefix}")
            return

        await ctx.error("Prefix can only be set by admins.")
        return

    @commands.group()
    @checks.is_admin()
    async def whitelist(self, ctx, scope: str, role: discord.Role):
        """
        Whitelist a role to allow server/channel access to the bot.

        Use '!whitelist server/channel/remove role_name'
        """

        scopes = {
            'server': ctx.guild,
            'channel': ctx.channel,
            'remove': False
        }

        try:
            scope = scopes[scope.lower()]
        except KeyError:
            await ctx.error(
                'Incorrect scope.',
                'You must pick either `server` or `channel` scopes, or `remove` to clear from whitelist.'
            )
            return

        if scope is False:
            sql = """DELETE FROM whitelist WHERE `role_id` = (?)"""
            values = (role.id,)
            await db.execute_sql(sql, values)
            await ctx.success(f'{role} has been removed from all whitelists.')
            return

        sql = """REPLACE INTO whitelist(location_id, role_id) VALUES(?,?)"""
        values = (scope.id, role.id)

        await db.execute_sql(sql, values)
        return await ctx.success(f'{role} has been whitelisted in {scope}')


def setup(bot):
    bot.add_cog(Core(bot))
