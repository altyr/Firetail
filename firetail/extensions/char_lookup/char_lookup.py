import json
import logging
import urllib
from typing import Union

import aiohttp
import discord
from discord.ext import commands

from firetail.core import checks
from firetail.utils import make_embed


log = logging.getLogger(__name__)


class CharLookup(commands.Cog):
    """This extension handles looking up characters."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["char"])
    @checks.spam_check()
    @checks.is_whitelist()
    async def character(self, ctx, *, name: Union[discord.Member, str]):
        """Show character information."""

        if len(ctx.message.content.split()) == 1:
            dest = ctx.author if ctx.bot.config.dm_only else ctx
            return await dest.send('**ERROR:** Use **!help char** for more info.')

        if isinstance(name, discord.Member):
            name = name.display_name

        log.info(f'CharLookup - {ctx.author} requested character info for the user {name}')

        async with ctx.typing():
            character_id = await ctx.bot.esi_data.esi_search(name, 'character')

            try:
                if len(character_id['character']) > 1:
                    for eve_id in character_id['character']:
                        character_data = await ctx.bot.esi_data.character_info(eve_id)
                        if character_data['name'].lower().strip() == name.lower().strip():
                            character_id = eve_id
                            character_data = await ctx.bot.esi_data.character_info(character_id)
                            name = character_data['name']
                            break
                else:
                    character_id = character_id['character'][0]
                    character_data = await ctx.bot.esi_data.character_info(character_id)
                    name = character_data['name']

            except Exception:
                dest = ctx.author if ctx.bot.config.dm_only else ctx
                log.info(f'CharLookup ERROR - {name} could not be found')
                return await dest.send(f'**ERROR:** No User Found With The Name {name}')

            latest_killmail, latest_system_id = await self.zkill_last_mail(character_id)
            ship_lost = 'No Killmails Found'
            solar_system_name = 'N/A'
            if latest_killmail is not None:
                if 'ship_type_id' in latest_killmail:
                    ship_lost_raw = await ctx.bot.esi_data.type_info_search(latest_killmail['ship_type_id'])
                    ship_lost = ship_lost_raw['name']
                else:
                    ship_lost = 'N/A'
                solar_system_info = await ctx.bot.esi_data.system_info(latest_system_id)
                solar_system_name = solar_system_info['name']
            victim_corp_raw = await ctx.bot.esi_data.corporation_info(character_data['corporation_id'])
            victim_corp = victim_corp_raw['name']
            zkill_stats = await self.zkill_stats(character_id)
            firetail_intel = await self.firetail_intel(character_id, name, zkill_stats)
            zkill_link = f'https://zkillboard.com/character/{character_id}/'
            eve_prism = f'http://eve-prism.com/?view=character&name={urllib.parse.quote(name)}'
            eve_who = f'https://evewho.com/pilot/{urllib.parse.quote(name)}'
            try:
                if zkill_stats['allTimeSum']:
                    total_kills = str(zkill_stats['allTimeSum'])
                    danger_ratio = zkill_stats['dangerRatio']
                    gang_ratio = zkill_stats['gangRatio']
                    solo_kills = str(zkill_stats['soloKills'])
                else:
                    total_kills = 'N/A'
                    danger_ratio = 'N/A'
                    gang_ratio = 'N/A'
                    solo_kills = 'N/A'
                try:
                    victim_alliance_raw = await ctx.bot.esi_data.alliance_info(character_data['alliance_id'])
                    victim_alliance = victim_alliance_raw['name']
                except Exception:
                    victim_alliance = None

                embed = make_embed(guild=ctx.guild,
                                   title_url="https://zkillboard.com/character/" + str(character_id) + "/",
                                   title=character_data['name'],
                                   content=f'[ZKill]({zkill_link}) / [EveWho]({eve_who}) / [EVE-Prism]({eve_prism})')
                embed.set_thumbnail(
                    url="https://imageserver.eveonline.com/Character/" + str(character_id) + "_64.jpg")
                if victim_alliance:
                    embed.add_field(name="Firetail Intel Report", value=firetail_intel,
                                    inline=False)
                    embed.add_field(name="General Info",
                                    value='Alliance:\nCorporation:\nLast Seen Location:\nLast Seen Ship:',
                                    inline=True)
                    embed.add_field(name="-",
                                    value=f'{victim_alliance}\n{victim_corp}\n{solar_system_name}\n{ship_lost}',
                                    inline=True)
                    embed.add_field(name="PVP Info", value='Threat Rating:\nGang Ratio:\nSolo Kills:\nTotal Kills:',
                                    inline=True)
                    embed.add_field(name="-",
                                    value=f'{danger_ratio}%\n{gang_ratio}%\n{solo_kills}\n{total_kills}',
                                    inline=True)
                else:
                    embed.add_field(name="Firetail Intel Report", value=firetail_intel,
                                    inline=False)
                    embed.add_field(name="General Info", value='Corporation:\nLast Seen System:\nLast Seen Ship:',
                                    inline=True)
                    embed.add_field(name="-", value=f'{victim_corp}\n{solar_system_name}\n{ship_lost}',
                                    inline=True)
                    embed.add_field(name="PVP Info", value='Threat Rating:\nGang Ratio:\nSolo Kills:\nTotal Kills:',
                                    inline=True)
                    embed.add_field(name="-",
                                    value=f'{danger_ratio}%\n{gang_ratio}%\n{solo_kills}\n{total_kills}',
                                    inline=True)
                dest = ctx.author if ctx.bot.config.dm_only else ctx
                await dest.send(embed=embed)
                if ctx.bot.config.delete_commands:
                    await ctx.message.delete()
            except Exception:
                try:
                    victim_alliance_raw = await ctx.bot.esi_data.alliance_info(character_data['alliance_id'])
                    victim_alliance = victim_alliance_raw['name']
                except Exception:
                    victim_alliance = None

                embed = make_embed(
                    guild=ctx.guild,
                    title_url="https://zkillboard.com/character/" + str(character_id) + "/",
                    title=character_data['name'],
                    content=f'[ZKill]({zkill_link}) / [EveWho]({eve_who}) / [EVE-Prism]({eve_prism})'
                )
                embed.set_thumbnail(
                    url="https://imageserver.eveonline.com/Character/" + str(character_id) + "_64.jpg")
                if victim_alliance:
                    embed.add_field(name="Firetail Intel Report", value=firetail_intel,
                                    inline=False)
                    embed.add_field(name="General Info",
                                    value='Alliance:\nCorporation:\nLast Seen Location:\nLast Seen Ship:',
                                    inline=True)
                    embed.add_field(name="-",
                                    value=f'{victim_alliance}\n{victim_corp}\n{solar_system_name}\n{ship_lost}',
                                    inline=True)
                else:
                    embed.add_field(name="Firetail Intel Report", value=firetail_intel,
                                    inline=False)
                    embed.add_field(name="General Info", value='Corporation:\nLast Seen System:\nLast Seen Ship:',
                                    inline=True)
                    embed.add_field(name="-", value=f'{victim_corp}\n{solar_system_name}\n{ship_lost}',
                                    inline=True)
                dest = ctx.author if ctx.bot.config.dm_only else ctx
                await dest.send(embed=embed)
                if ctx.bot.config.delete_commands:
                    await ctx.message.delete()

    async def zkill_last_mail(self, character_id):
        async with aiohttp.ClientSession() as session:
            url = f'https://zkillboard.com/api/no-items/characterID/{character_id}/'
            async with session.get(url) as resp:
                data = await resp.text()
                data = json.loads(data)
                try:
                    kill_esi_url = (
                        f"https://esi.evetech.net/latest/killmails/{data[0]['killmail_id']}/{data[0]['zkb']['hash']}/"
                    )
                except Exception:
                    return None, None
                async with session.get(kill_esi_url) as kill_resp:
                    data = await kill_resp.text()
                    data = json.loads(data)
                    try:
                        victim_id = data['victim']['character_id']
                    except Exception:
                        victim_id = 0
                    try:
                        if victim_id == character_id:
                            return data['victim'], data['solar_system_id']
                        else:
                            for attacker in data['attackers']:
                                if attacker['character_id'] == character_id:
                                    return attacker, data['solar_system_id']
                    except Exception:
                        return None, None

    async def zkill_stats(self, character_id):
        url = f'https://zkillboard.com/api/stats/characterID/{character_id}/'
        async with self.bot.session.get(url) as resp:
            try:
                data = await resp.json(content_type=None)
            except json.JSONDecodeError:
                return None
        if 'allTimeSum' in data:
            return data

    async def firetail_intel(self, character_id, character_name, zkill_stats):
        try:
            solo = 100 - zkill_stats['gangRatio']
            threat = zkill_stats['dangerRatio']
            character_type, special = await self.character_type(character_id, solo, threat)
            top_lists = zkill_stats['topLists']
            for top_type in top_lists:
                if top_type['type'] == 'solarSystem':
                    try:
                        top_system = (
                            f"The past week they have been most active in {top_type['values'][0]['solarSystemName']}"
                        )
                    except Exception:
                        top_system = 'This player has not been active recently'
            intel = f'{special}\n{character_name} is most likely a {character_type}. {top_system}. ' \
                    f'You have a {solo}% chance of encountering this player solo.'
            return intel
        except Exception:
            solo = 0
            threat = 0
            character_type, special = await self.character_type(character_id, solo, threat)
            intel = f'{special}\n{character_name} is most likely a {character_type}. ' \
                    f'No further intel available at this time.'
            return intel

    async def character_type(self, character_id, solo, threat):
        titans = [11567, 3764, 671, 23773, 42126, 42241, 45649]
        supers = [23919, 23917, 23913, 22852, 3514, 42125]
        probe_launchers = [4258, 4260, 17901, 17938, 28756, 28758]
        loss_url = f'https://zkillboard.com/api/kills/characterID/{character_id}/losses/no-attackers/'
        kill_url = f'https://zkillboard.com/api/kills/characterID/{character_id}/kills/no-items/'
        covert_cyno = 0
        cyno = 0
        probes = 0
        lost_ship_type_id = 0
        special = ' '
        last_kill = await self.last_kill(kill_url)
        try:
            for attacker in last_kill[0]['attackers']:
                if attacker['character_id'] == character_id:
                    if attacker['ship_type_id'] in titans:
                        special = '**This pilot has been seen in a Titan\n**'
                    elif attacker['ship_type_id'] in supers:
                        special = '**This pilot has been seen in a Super\n**'
                    else:
                        special = ' '
        except Exception:
            special = ' '
        async with aiohttp.ClientSession() as session:
            async with session.get(loss_url) as resp:
                losses = await resp.text()
                losses = json.loads(losses)
                i = 0
                for loss in losses:
                    i = i + 1
                    if i >= 50:
                        break
                    loss_esi_url = (
                        f"https://esi.evetech.net/latest/killmails/{loss['killmail_id']}/{loss['zkb']['hash']}/"
                    )
                    async with session.get(loss_esi_url) as data:
                        loss_data = await data.text()
                        loss_data = json.loads(loss_data)
                        for item in loss_data['victim']['items']:
                            if item['item_type_id'] == 28646:
                                covert_cyno = covert_cyno + 1
                            elif item['item_type_id'] == 21096:
                                cyno = cyno + 1
                            elif item['item_type_id'] in probe_launchers:
                                probes = probes + 1
                        lost_ship_type_id = loss_data['victim']['ship_type_id']
                if covert_cyno >= 2:
                    if 'attackers' not in last_kill:
                        return '**BLOPS Hotdropper**', special
                    alliance_ids = []
                    corporation_ids = []
                    for attacker in last_kill['attackers']:
                        if 'alliance_id' in attacker:
                            alliance_ids.append(attacker['alliance_id'])
                        if 'corporation_id' in attacker:
                            corporation_ids.append(attacker['corporation_id'])
                    try:
                        dominant_alliance = max(set(alliance_ids), key=alliance_ids.count)
                        alliance_raw = await self.bot.esi_data.alliance_info(dominant_alliance)
                        alliance = alliance_raw['name']
                        return f'**BLOPS Hotdropper for {alliance}**', special
                    except Exception:
                        dominant_corp = max(set(corporation_ids), key=corporation_ids.count)
                        corp_raw = await self.bot.esi_data.corporation_info(dominant_corp)
                        corp = corp_raw['name']
                        return f'**BLOPS Hotdropper for {corp}**', special
                if cyno >= 5 and (threat <= 30 or threat == 0):
                    return 'Cyno Alt', special
                if probes >= 5 and threat >= 51:
                    return '**Combat Prober / Possible FC**', special
                if probes >= 5 and (threat <= 50 or threat == 0):
                    return 'Exploration Pilot', special
                if cyno >= 5 and threat >= 31:
                    return '**Possible Hot Dropper**', special
                if threat <= 30 and lost_ship_type_id == 28352:
                    return 'Rorqual Pilot', special
                if threat <= 30:
                    return 'PVE Pilot', special
                if solo >= 50:
                    return 'Solo PVP Pilot', special
                if solo <= 15:
                    return 'Fleet Pilot', special
                if solo <= 49:
                    return 'Balanced PVP Pilot', special

    async def last_kill(self, kill_url):
        async with self.bot.session.get(kill_url) as resp:
            try:
                data = await resp.json(content_type=None)
            except json.JSONDecodeError:
                return None

        kill_esi_url = (
            f"https://esi.evetech.net/latest/killmails/{data[0]['killmail_id']}/{data[0]['zkb']['hash']}/"
        )

        async with self.bot.session.get(kill_esi_url) as resp:
            try:
                data = await resp.json(content_type=None)
            except json.JSONDecodeError:
                return None
            return data[0]

    def most_common(self, lst):
        return max(set(lst), key=lst.count)
