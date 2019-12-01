import asyncio
import json
import logging
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from firetail.core import checks
from firetail.lib import db
from firetail.utils.formatters import convert_to_bool
from .objects import Mail, Subscription

log = logging.getLogger(__name__)


class Killmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.subs = {}
        self.ws_task = None
        self.km_counter = 0
        self.prepare = self.bot.loop.create_task(self.prepare_subs())

    @staticmethod
    async def get_subs(*, channel_id: int = None, sub_id: int = None):
        sql = "SELECT id, channelid, serverid, losses, threshold, groupid FROM add_kills"
        if sub_id:
            sql += " WHERE id = (?)"
            result = await db.select_var(sql, (sub_id,))
            if result:
                return result[0]
            return None

        if channel_id:
            sql += " WHERE channelid = (?)"
            return await db.select_var(sql, (channel_id,))

        return await db.select(sql)

    async def add_sub(
        self, channel_id: int, server_id: int, owner_id: int, group_id: int = 6, losses: str = 'true',
        threshold: int = 1
    ):
        sql = (
            "INSERT INTO add_kills (channelid, serverid, groupid, ownerid, losses, threshold) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        id_ = await db.execute_sql(sql, (channel_id, server_id, group_id, owner_id, losses, threshold or 1))
        sub = Subscription(id_, self.bot.get_channel(channel_id), threshold, convert_to_bool(losses), group_id)
        self.subs[sub.id] = sub

    async def prepare_subs(self):
        await self.bot.wait_until_ready()
        log.debug("Preparing killmail subs.")

        killboard_subs = await self.get_subs()
        for sub_data in killboard_subs:
            id_, channel_id, _, losses, threshold, group_id = sub_data
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await self.remove_bad_channel(channel_id)

            sub = Subscription(id_, channel, threshold, convert_to_bool(losses), group_id)
            self.subs[sub.id] = sub

        self.ws_task = self.bot.loop.create_task(self.listen_for_mails())

    def process_mail(self, killmail_data):
        killmail_data['killmail']['zkb'] = killmail_data['zkb']
        mail = Mail(killmail_data['killmail'], self.bot.esi_data)
        if mail.npc:
            return
        asyncio.gather(*[sub.mail(mail) for sub in self.subs.values()])

    async def listen_for_mails(self):
        log.debug("Listening for killmails.")
        while True:
            try:
                await self.get_new_mail()
            except (json.JSONDecodeError, KeyError):
                log.exception("Killmail data was badly formed.")
                pass
            except aiohttp.ClientError:
                log.exception("Failure when requesting new mails encountered.")
                pass

    async def get_new_mail(self):
        url = f"https://redisq.zkillboard.com/listen.php?queueID=firetail_{self.bot.user.id}"
        async with self.bot.session.get(url) as resp:
            data = await resp.json()
            log.debug(json.dumps(data['package'], indent=4))
        if data['package']:
            self.km_counter += 1
            self.process_mail(data['package'])

    @staticmethod
    async def remove_bad_channel(channel_id):
        sql = "DELETE FROM add_kills WHERE channelid = (?)"
        values = (channel_id,)
        await db.execute_sql(sql, values)
        log.info(f'Killmail - Bad Channel {channel_id} removed successfully')

    @commands.group(aliases=["km", "killmails"], invoke_without_command=True)
    async def killmail(self, ctx, *, channel: discord.TextChannel = None):
        """Show the current channel's killmail subscriptions."""

        channel = channel or ctx.channel
        subs_data = await self.get_subs(channel_id=channel.id)

        subs = []
        for sub_data in subs_data:
            id_, _, _, losses, threshold, group_id = sub_data
            sub_text = f"`{id_}`: Kills"
            if convert_to_bool(losses):
                sub_text += " and Losses"
            if threshold:
                sub_text += f" over {threshold:,} ISK"
            if group_id and group_id != 6:
                sub_text += f" matching ID {group_id}"
            subs.append(sub_text)

        if not subs_data:
            subs.append("There's no subs for this channel.")

        await ctx.info(f"Killmails for #{ctx.channel}", "\n".join(subs))

    @checks.is_mod()
    @killmail.group(name="add", aliases=["sub"], invoke_without_command=True)
    async def add_killmail(self, ctx, match_id: int, threshold: Optional[int], include_losses: bool = False):
        """
        Add a new killmail subscription to the channel.

        `match_id` can be an Alliance ID, Corp ID, Region ID, System ID (Use Zkill or Dotlan to get them)
        """

        losses = 'true' if include_losses else 'false'
        await self.add_sub(ctx.channel.id, ctx.guild.id, ctx.author.id, match_id, losses, threshold)
        await ctx.success("Killmail subscription added!")

    @checks.is_mod()
    @add_killmail.command(name="global", aliases=["big"])
    async def add_killmail_global(self, ctx, threshold: int = 2000000000):
        """
        Add a new global killmail subscription to the channel.

        Global subscriptions cover all kills in the EVE universe.
        """

        await self.add_sub(ctx.channel.id, ctx.guild.id, ctx.author.id, threshold=threshold)
        await ctx.success("Killmail subscription added!")

    @checks.is_mod()
    @killmail.command(name="clear", aliases=["remove", "unsub"])
    async def killmail_clear(self, ctx, sub_id: int = None):
        """
        Clear all killmails for the channel or individually remove with subscription IDs.

        You can find subscription IDs with the 'killmail' command.
        """

        if sub_id:
            sub = await self.get_subs(sub_id=sub_id)

            if not sub:
                await ctx.error(f"ID {sub_id} does not match any of your killmail subscriptions.")
                return

            id_, channel_id, server_id, losses, threshold, group_id = sub
            if server_id != ctx.guild.id:
                await ctx.error(f"ID {sub_id} does not match any of your killmail subscriptions.")
                return

            sql = "DELETE FROM add_kills WHERE id = (?)"
            await db.execute_sql(sql, (sub_id,))
            del self.subs[sub_id]
            await ctx.success(f'Killmail {sub_id} has been removed.')
            return

        sql = "DELETE FROM add_kills WHERE channelid = ?"
        await db.execute_sql(sql, (ctx.channel.id,))

        rm_ids = []
        for sub in self.subs.values():
            if sub.channel.id == ctx.channel.id:
                rm_ids.append(sub.id)
        for rm_id in rm_ids:
            del self.subs[rm_id]

        await ctx.success(
            "All killmail subs removed for this channel.",
            "You may see more killmails that had already been submitted "
            "and partially processed in the message queue."
        )

    @checks.is_mod()
    @commands.command(hidden=True)
    async def addkills(self, ctx):
        """Old command replaced with `killmail add`."""
        await ctx.error(f"Moved to `{ctx.prefix}killmail add`")

    @checks.is_co_owner()
    @killmail.command(name="counter")
    async def killmail_counter(self, ctx):
        await ctx.info(f"Killmails Processed: {self.km_counter:,}")

    def cog_unload(self):
        self.ws_task.cancel()
