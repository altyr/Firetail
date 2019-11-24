import json
import logging
import re
from urllib import parse

import aiohttp
from discord.ext import commands

from firetail.core import checks

log = logging.getLogger(__name__)


class GroupLookup(commands.Cog):
    """This extension handles looking up corps and alliance."""

    @commands.command(aliases=["corp", "alliance"])
    @checks.spam_check()
    @checks.is_whitelist()
    async def group(self, ctx, *, name):
        """Shows corp and alliance information."""

        log.info(f'GroupLookup - {ctx.author} requested group info for the group {name}')
        corp_data = None
        alliance_data = None
        corp_id = None
        alliance_id = None
        corp = 'corporation'
        corp_ids = await ctx.bot.esi_data.esi_search(name, corp)
        if corp_ids is not None and 'corporation' in corp_ids:
            if len(corp_ids['corporation']) > 1:
                for corporation_id in corp_ids['corporation']:
                    group_data = await ctx.bot.esi_data.corporation_info(corporation_id)
                    if group_data['name'].lower().strip() == name.lower().strip():
                        corp_id = corporation_id
                        corp_data = await ctx.bot.esi_data.corporation_info(corp_id)
                        break
            elif len(corp_ids['corporation']) == 1:
                corp_id = corp_ids['corporation'][0]
                corp_data = await ctx.bot.esi_data.corporation_info(corp_id)
        alliance = 'alliance'
        alliance_ids = await ctx.bot.esi_data.esi_search(name, alliance)
        if alliance_ids is not None and 'alliance' in alliance_ids:
            if len(alliance_ids['alliance']) > 1:
                for ally_id in alliance_ids['alliance']:
                    group_data = await ctx.bot.esi_data.alliance_info(ally_id)
                    if group_data['name'].lower().strip() == name.lower().strip():
                        alliance_id = ally_id
                        alliance_data = await ctx.bot.esi_data.alliance_info(alliance_id)
                        break
            elif len(alliance_ids['alliance']) == 1:
                alliance_id = alliance_ids['alliance'][0]
                alliance_data = await ctx.bot.esi_data.alliance_info(alliance_id)

        # Check if a corp and alliance were both found
        if corp_data is not None and alliance_data is not None:
            if corp_data['name'].lower().strip() == name.lower().strip():
                alliance_data = None
            elif alliance_data['name'].lower().strip() == name.lower().strip():
                corp_data = None
            else:
                dest = ctx.author if ctx.bot.config.dm_only else ctx
                log.info(f'GroupLookup ERROR - {name} could not be found')
                return await dest.send(f'**ERROR:** Multiple Groups Found With Names Similiar To {name}')

        if corp_data is not None:
            group = 'corporation'
            group_id = corp_id
            group_data = corp_data
            zkill_stats = await self.zkill_stats(group_id, 'corporationID')
            raw_corp_description = group_data['description']
            new_lines = re.sub(r'<br\s*?>', '\n', raw_corp_description)
            tag_re = re.compile(r'(<!--.*?-->|<[^>]*>)')
            corp_description = tag_re.sub('', new_lines)
            try:
                alliance_id = group_data['alliance_id']
                alliance_info = await ctx.bot.esi_data.alliance_info(alliance_id)
                alliance_name = alliance_info['name']
                alliance = True
            except Exception:
                alliance = False
            zkill_link = f'https://zkillboard.com/corporation/{group_id}/'
            eve_who = f'https://evewho.com/corp/{parse.quote(name)}'
            dotlan = f'http://evemaps.dotlan.net/corporation/{parse.quote(name)}'
            logo = f'https://imageserver.eveonline.com/Corporation/{group_id}_64.png'
        elif alliance_data is not None:
            group = 'alliance'
            group_id = alliance_id
            group_data = alliance_data
            zkill_stats = await self.zkill_stats(group_id, 'allianceID')
            zkill_link = f'https://zkillboard.com/alliance/{group_id}/'
            eve_who = f'https://evewho.com/alli/{parse.quote(name)}'
            dotlan = f'http://evemaps.dotlan.net/alliance/{parse.quote(name)}'
            logo = f'https://imageserver.eveonline.com/Alliance/{group_id}_64.png'
        else:
            dest = ctx.author if ctx.bot.config.dm_only else ctx
            log.info(f'GroupLookup ERROR - {name} could not be found')
            return await dest.send(f'**ERROR:** No Group Found With The Name {name}')
        if zkill_stats:
            total_kills = str(zkill_stats['allTimeSum'])
            danger_ratio = zkill_stats['dangerRatio']
            gang_ratio = zkill_stats['gangRatio']
            solo_kills = str(zkill_stats['soloKills'])
            if zkill_stats['hasSupers']:
                try:
                    super_count = len(zkill_stats['supers']['supercarriers']['data'])
                except Exception:
                    super_count = 'N/A'
                try:
                    titan_count = len(zkill_stats['supers']['titans']['data'])
                except Exception:
                    titan_count = 'N/A'
            else:
                super_count = 'N/A'
                titan_count = 'N/A'
            for top in zkill_stats['topLists']:
                try:
                    if top['type'] == 'solarSystem':
                        most_active_system = top['values'][0]['solarSystemName']
                except Exception:
                    most_active_system = 'N/A'
        else:
            total_kills = 'N/A'
            danger_ratio = 'N/A'
            gang_ratio = 'N/A'
            solo_kills = 'N/A'
            super_count = 'N/A'
            titan_count = 'N/A'
            most_active_system = 'N/A'

        embed = await ctx.embed(
            name,
            f'[ZKill]({zkill_link}) / [EveWho]({eve_who}) / [Dotlan]({dotlan})',
            thumbnail=logo,
            send=False
        )

        if group == 'corporation' and alliance:
            embed.add_field(
                name="General Info",
                value=(
                    f"Name: {group_data['name']}\n"
                    f"Ticker: {group_data['ticker']}\n"
                    f"Member Count: {group_data['member_count']}\n"
                    f"Alliance: {alliance_name}"
                )
            )
            embed.add_field(
                name="PVP Info",
                value=(
                    f"Threat Rating: {danger_ratio}%\n"
                    f"Gang Ratio: {gang_ratio}%\n"
                    f"Solo Kills: {solo_kills}\n"
                    f"Total Kills: {total_kills}\n"
                    f"Known Super Count: {super_count}\n"
                    f"Known Titan Count: {titan_count}\n"
                    f"Most Active System: {most_active_system}"
                )
            )
            if corp_description:
                embed.add_field(name="Description", value=corp_description[:1023])

        elif group == 'corporation' and not alliance:
            embed.add_field(
                name="General Info",
                value=(
                    f"Name: {group_data['name']}\n"
                    f"Ticker: {group_data['ticker']}\n"
                    f"Member Count: {group_data['member_count']}"
                ),
                inline=False
            )
            if len(corp_description) > 1:
                embed.add_field(name="Description", value=corp_description[:1023], inline=False)
            embed.add_field(
                name="PVP Info",
                value=(
                    f"Threat Rating: {danger_ratio}%\n"
                    f"Gang Ratio: {gang_ratio}%\n"
                    f"Solo Kills: {solo_kills}\n"
                    f"Total Kills: {total_kills}\n"
                    f"Known Super Count: {super_count}\n"
                    f"Known Titan Count: {titan_count}\n"
                    f"Most Active System: {most_active_system}"
                )
            )

        elif group == 'alliance':
            embed.add_field(
                name="General Info",
                value=f"Name: {group_data['name']}\nTicker: {group_data['ticker']}",
                inline=False
            )
            embed.add_field(
                name="PVP Info",
                value=(
                    f"Threat Rating: {danger_ratio}%\n"
                    f"Gang Ratio: {gang_ratio}%\n"
                    f"Solo Kills: {solo_kills}\n"
                    f"Total Kills: {total_kills}\n"
                    f"Known Super Count: {super_count}\n"
                    f"Known Titan Count: {titan_count}\n"
                    f"Most Active System: {most_active_system}"
                )
            )

        dest = ctx.author if ctx.bot.config.dm_only else ctx
        await dest.send(embed=embed)
        if ctx.bot.config.delete_commands:
            await ctx.message.delete()

    async def zkill_stats(self, group_id, group_type):
        async with aiohttp.ClientSession() as session:
            url = f'https://zkillboard.com/api/stats/{group_type}/{group_id}/'
            async with session.get(url) as resp:
                data = await resp.text()
                data = json.loads(data)
                if 'allTimeSum' in data:
                    return data
                return None
