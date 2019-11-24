import asyncio
import logging
from datetime import datetime

import pytz
from discord.ext import commands

from firetail.core import checks
from firetail.lib import db
from firetail.utils import make_embed

log = logging.getLogger(__name__)


class SovTracker(commands.Cog):
    """This extension provides real time info on sov fights."""

    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.tick_loop())

    async def tick_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                sql = "SELECT * FROM sov_tracker"
                sov_tracking = await db.select(sql)
                sov_battles = await self.bot.esi_data.get_active_sov_battles()
                for tracked in sov_tracking:
                    active = False
                    tracked_system_id = tracked[3]
                    tracked_fight_type = tracked[2]
                    system_data = await self.bot.esi_data.system_info(tracked_system_id)
                    for fights in sov_battles:
                        fight_system_id = fights['solar_system_id']
                        fight_fight_type = fights['event_type']
                        if fight_system_id == tracked_system_id and fight_fight_type == tracked_fight_type:
                            active = True
                            defender_score = fights['defender_score']
                            attacker_score = fights['attackers_score']
                            if defender_score != tracked[4] or attacker_score != tracked[5]:
                                fight_type = fights['event_type'].replace('_', ' ').title()
                                defender_id = fights['defender_id']
                                defender_name = await self.group_name(defender_id)
                                if tracked[4] < defender_score:
                                    winning = 1
                                else:
                                    winning = 2
                                await self.report_current(system_data, fight_type, defender_name, defender_score,
                                                          attacker_score, None, tracked[1], winning)
                                sql = (
                                    "UPDATE sov_tracker "
                                    "SET defender_score = (?), attackers_score = (?) "
                                    "WHERE system_id = (?) AND fight_type = (?)"
                                )
                                values = (defender_score, attacker_score, fight_system_id, fight_fight_type,)
                                await db.execute_sql(sql, values)
                    if active is False:
                        sql = "DELETE FROM sov_tracker WHERE system_id = (?) AND fight_type = (?)"
                        values = (tracked_system_id, tracked_fight_type,)
                        await db.execute_sql(sql, values)
                        if tracked[4] > tracked[5]:
                            winner = 'Defender'
                        else:
                            winner = 'Attacker'
                        await self.report_ended(system_data, tracked_fight_type, winner, tracked[1])
                await asyncio.sleep(60)
            except Exception:
                log.info('ERROR:', exc_info=True)
                await asyncio.sleep(120)

    @commands.group(aliases=["wand", "cancer"], invoke_without_command=True)
    @checks.spam_check()
    @checks.is_whitelist()
    async def sov(self, ctx, system):
        """
        Sets the bot to track a sov fight within the given system.

        Updates are checked every minute.
        It will also report upcoming fights.
        """

        system_data = await self.get_data(system)
        log.info(f'SovTracker - {ctx.author} requested information for {system}')
        if system_data is None:
            dest = ctx.author if ctx.bot.config.dm_only else ctx
            return await dest.send(f'**ERROR:** Could not find a system named {system}')
        sov_battles = await self.bot.esi_data.get_active_sov_battles()
        for fights in sov_battles:
            if fights['solar_system_id'] == system_data['system_id']:
                fight_type_raw = fights['event_type']
                fight_type = fight_type_raw.replace('_', ' ').title()
                start_time = datetime.strptime(fights['start_time'], '%Y-%m-%dT%H:%M:%SZ')
                time = datetime.now(pytz.timezone('UTC')).strftime('%Y-%m-%dT%H:%M:%SZ')
                current_time = datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ')
                defender_id = fights.get('defender_id', 'Freeport')
                defender_name = await self.group_name(defender_id) if defender_id != 'Freeport' else 'Freeport'
                if current_time > start_time:
                    defender_score = fights['defender_score']
                    attacker_score = fights['attackers_score']
                    sql = (
                        "REPLACE INTO sov_tracker(channel_id, fight_type, system_id, defender_score, attackers_score) "
                        "VALUES(?,?,?,?,?)"
                    )
                    values = (ctx.channel.id, fight_type_raw, system_data['system_id'], defender_score, attacker_score)
                    await db.execute_sql(sql, values)
                    await self.report_current(
                        system_data, fight_type, defender_name, defender_score, attacker_score, ctx
                    )
                else:
                    await self.report_upcoming(ctx, system_data, fight_type, defender_name)

    @sov.command(name="remove")
    @checks.spam_check()
    @checks.is_whitelist()
    async def sov_remove(self, ctx, system):
        """Removes a registered system from sov updates."""

        system_data = await self.get_data(system)
        log.info(f'SovTracker - {ctx.author} requested information for {system}')
        if system_data is None:
            await ctx.dest.send(f'**ERROR:** Could not find a location named {system}')
            return
        sql = "DELETE FROM sov_tracker WHERE `system_id` = (?)"
        values = (system_data['system_id'],)
        await db.execute_sql(sql, values)
        await ctx.dest.send(f"No longer tracking sov battles in {system_data['name']}")

    async def get_data(self, location):
        search = 'solar_system'
        data = await self.bot.esi_data.esi_search(location, search)
        if data is None or data is False:
            return None
        return await self.bot.esi_data.system_info(data['solar_system'][0])

    async def report_current(
        self, system_data, fight_type, defender_name, defender_score, attacker_score, ctx=None, channel_id=None,
        winning=None
    ):
        defender_score = f'{defender_score * 100}%'
        attacker_score = f'{attacker_score * 100}%'
        constellation_data = await self.bot.esi_data.constellation_info(system_data['constellation_id'])
        constellation_name = constellation_data['name']
        region_id = constellation_data['region_id']
        region_data = await self.bot.esi_data.region_info(region_id)
        region_name = region_data['name']
        zkill_link = f"https://zkillboard.com/system/{system_data['system_id']}"
        dotlan_link = f"http://evemaps.dotlan.net/system/{system_data['name'].replace(' ', '_')}"
        constellation_dotlan = f"http://evemaps.dotlan.net/map/{region_name}/{constellation_name}".replace(' ', '_')
        title = f"Active Sov Battle Reported In: {system_data['name']}"
        content = (
            f"[ZKill]({zkill_link}) / "
            f"[{system_data['name']}]({dotlan_link}) / "
            f"[Constellation: {constellation_name}]({constellation_dotlan})\n"
            f"Bot is tracking this battle."
        )
        embed_type = 'info'
        if winning == 1:
            defender_score = f'{defender_score} :arrow_up:'
            attacker_score = f'{attacker_score}'
            title = f"Update For {system_data['name']}"
            content = (
                f"[ZKill]({zkill_link}) / "
                f"[{system_data['name']}]({dotlan_link}) / "
                f"[Constellation: {constellation_name}]({constellation_dotlan})\n"
                f"The Defender is making progress."
            ),
            embed_type = 'success'
        elif winning == 2:
            defender_score = str(defender_score)
            attacker_score = f'{attacker_score} :arrow_up:'
            title = f"Update For {system_data['name']}"
            content = (
                f"[ZKill]({zkill_link}) / "
                f"[{system_data['name']}]({dotlan_link}) / "
                f"[Constellation: {constellation_name}]({constellation_dotlan})\n"
                f"The Attacker is making progress."
            ),
            embed_type = 'error'
        embed = make_embed(msg_type=embed_type, title=title, title_url=dotlan_link, content=content)
        embed.add_field(
            name="Active Sov Battle",
            value=(
                f'Defender: {defender_name}\n'
                f'Fight Type: {fight_type}\n'
                f'Defender Score: {defender_score}\n'
                f'Attacker Score: {attacker_score}'
            ),
            inline=False
        )
        try:
            if channel_id is None:
                await ctx.channel.send(embed=embed)
            else:
                channel = self.bot.get_channel(channel_id)
                await channel.send(embed=embed)
        except Exception:
            return None

    async def report_upcoming(self, ctx, system_data, fight_type, defender_name):
        constellation_data = await self.bot.esi_data.constellation_info(system_data['constellation_id'])
        constellation_name = constellation_data['name']
        region_id = constellation_data['region_id']
        region_data = await self.bot.esi_data.region_info(region_id)
        region_name = region_data['name']
        zkill_link = f"https://zkillboard.com/system/{system_data['system_id']}"
        dotlan_link = f"http://evemaps.dotlan.net/system/{system_data['name'].replace(' ', '_')}"
        constellation_dotlan = f"http://evemaps.dotlan.net/map/{region_name}/{constellation_name}".replace(' ', '_')
        title = f"Upcoming Sov Battle In: {system_data['name']}"
        embed = make_embed(
            msg_type='info',
            title=title,
            title_url=dotlan_link,
            content=(
                f"[ZKill]({zkill_link}) / "
                f"[{system_data['name']}]({dotlan_link}) / "
                f"[Constellation: {constellation_name}]({constellation_dotlan})\n"
                f"Do this command again once the battle has begun to receive live updates."
            )
        )
        embed.add_field(
            name="Upcoming Sov Battle",
            value=f'Defender: {defender_name}\nFight Type: {fight_type}',
            inline=False
        )
        await ctx.channel.send(embed=embed)

    async def report_ended(self, system_data, tracked_fight_type, winner, channel_id):
        fight_type_raw = tracked_fight_type
        fight_type = fight_type_raw.replace('_', ' ').title()
        constellation_data = await self.bot.esi_data.constellation_info(system_data['constellation_id'])
        constellation_name = constellation_data['name']
        region_id = constellation_data['region_id']
        region_data = await self.bot.esi_data.region_info(region_id)
        region_name = region_data['name']
        zkill_link = f"https://zkillboard.com/system/{system_data['system_id']}"
        dotlan_link = f"http://evemaps.dotlan.net/system/{system_data['name'].replace(' ', '_')}"
        constellation_dotlan = f"http://evemaps.dotlan.net/map/{region_name}/{constellation_name}".replace(' ', '_')
        title = f"Sov Battle In {system_data['name']} has ended."
        embed = make_embed(
            msg_type='info',
            title=title,
            title_url=dotlan_link,
            content=(
                f"[ZKill]({zkill_link}) / "
                f"[{system_data['name']}]({dotlan_link}) / "
                f"[Constellation: {constellation_name}]({constellation_dotlan})\n\n"
                f"The {fight_type} fight has ended with the {winner} claiming victory."
            ),
            inline=False
        )
        channel = self.bot.get_channel(channel_id)
        try:
            await channel.send(embed=embed)
        except Exception:
            return None

    async def get_sov_info(self, system_id):
        url = 'https://esi.evetech.net/latest/sovereignty/map/?datasource=tranquility'
        async with self.bot.session.get(url) as resp:
            data = await resp.json(content_type=None)
            sov_alliance_id = 1
            sov_corp = 'N/A'
            sov_alliance = 'N/A'
            for system in data:
                if system['system_id'] == system_id:
                    if 'corporation_id' in system:
                        sov_corp_id = system['corporation_id']
                        corporation_info = await self.bot.esi_data.corporation_info(sov_corp_id)
                        sov_corp = corporation_info['name']
                    if 'alliance_id' in system:
                        sov_alliance_id = system['alliance_id']
                        alliance_info = await self.bot.esi_data.alliance_info(sov_alliance_id)
                        sov_alliance = alliance_info['name']
                    break
            return sov_corp, sov_alliance, sov_alliance_id

    async def group_name(self, group_id):
        url = f'https://esi.evetech.net/latest/alliances/{group_id}/?datasource=tranquility'
        async with self.bot.session.get(url) as resp:
            data = await resp.json(content_type=None)
            try:
                return data["name"]
            except Exception:
                return 'Unknown'
