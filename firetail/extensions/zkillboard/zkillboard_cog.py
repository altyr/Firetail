import re
import urllib
import asyncio
from datetime import datetime
from collections import Counter

import discord
from discord.ext import commands

from firetail import utils

ZKB_TIMESTAMP_FORMAT = '%Y%m%d%H00'
ZKB_URL = "https://zkillboard.com/api"
EVE_IMG_URL = "https://imageserver.eveonline.com/{}/{}_64.jpg"
ZKB_PUBLIC_URL = 'https://zkillboard.com'


async def mention_to_member(guild, argument):
    match = re.match(r'<@!?([0-9]{17,21})>', argument)
    if not match:
        return None
    try:
        return guild.get_member(int(match.group(1)))
    except ValueError:
        return None


class ZKBRequestError(Exception):
    pass


class ZKBResultError(Exception):
    pass


class ZKBTooManyResults(ZKBResultError):
    pass


class ZKBNoResults(ZKBResultError):
    pass


class ZKBAlliance:
    def __init__(self, data, zkb_api):
        self._data = data
        self.api = zkb_api
        self.id = data['id']
        info = data['info']
        self.name = info['name']
        self.ticker = info['ticker']
        self.count = info.get('corpCount')
        self.executor_id = info.get('executorCorpID')
        self.faction_id = info.get('factionID')
        self.total_kills = data.get('allTimeSum')
        self.threat = data.get('dangerRatio')
        gang_ratio = data.get('gangRatio')
        self.solo = 100 - gang_ratio if gang_ratio else None
        self._groups = data.get('groups')
        self.supers = data.get('supers')
        self.isk_destroyed = data.get('iskDestroyed')
        self.isk_list = data.get('iskLost')
        self._months = data.get('months')
        self.points_destroyed = data.get('pointsDestroyed')
        self.points_lost = data.get('pointsLost')
        self.ships_destroyed = data.get('shipsDestroyed')
        self.ships_lost = data.get('shipsLost')
        self.solo_kills = data.get('soloKills')
        self.solo_losses = data.get('soloLosses')
        self._top_all_time = data.get('topAllTime')
        self.top_isk_kills = data.get('topIskKills')
        self._active_pvp = data.get('activepvp')
        self._top_lists = data.get('topLists')
        self.top_isk_kill_ids = data.get('topIskKillIDs')
        self._esi = None
        self._executor = None

    async def fetch_details(self):
        if not self._esi:
            self._esi = await self.api.esi.get_alliance(self.id)

        return self._esi

    def __str__(self):
        return "{}: ID{}".format(self.name, self.id)

    def __repr__(self):
        return "<{} name='{}', id={}>".format(
            self.__class__.__name__, self.name, self.id)

    @classmethod
    async def convert(cls, ctx, argument):
        await ctx.trigger_typing()
        result = await ctx.bot.zkb_api.esi_search_multi_handled(
            ctx, argument, 'alliance')
        if not result:
            raise commands.BadArgument(
                "Alliance '{}' not found." .format(argument))
        alliance = await ctx.bot.zkb_api.get_alliance(result)
        if not alliance:
            raise commands.BadArgument(
                "Alliance '{}' not found in ZKillboard.".format(argument))

        return alliance

    async def executor(self):
        if not self._executor:
            executor = await self.api.get_corporation(self.executor_id)
            self._executor = executor

        return self._executor


class ZKBCorporation:
    def __init__(self, data, zkb_api):
        self._data = data
        self.api = zkb_api
        self.id = data['id']
        info = data['info']
        self.name = info['name']
        self.ticker = info['ticker']
        self.count = info.get('memberCount')
        self.ceo_id = info.get('ceoID')
        self.alliance_id = info.get('alliance_id')
        self.faction_id = info.get('factionID')
        self.total_kills = data.get('allTimeSum')
        self.threat = data.get('dangerRatio')
        gang_ratio = data.get('gangRatio')
        self.solo = 100 - gang_ratio if gang_ratio else None
        self._groups = data.get('groups')
        self.supers = data.get('supers')
        self.isk_destroyed = data.get('iskDestroyed')
        self.isk_list = data.get('iskLost')
        self._months = data.get('months')
        self.points_destroyed = data.get('pointsDestroyed')
        self.points_lost = data.get('pointsLost')
        self.ships_destroyed = data.get('shipsDestroyed')
        self.ships_lost = data.get('shipsLost')
        self.solo_kills = data.get('soloKills')
        self.solo_losses = data.get('soloLosses')
        self._top_all_time = data.get('topAllTime')
        self.top_isk_kills = data.get('topIskKills')
        self._active_pvp = data.get('activepvp')
        self._top_lists = data.get('topLists')
        self.top_isk_kill_ids = data.get('topIskKillIDs')
        self._esi = None
        self._alliance = None
        self._ceo = None

    async def fetch_details(self):
        if not self._esi:
            self._esi = await self.api.esi.get_corporation(self.id)

        return self._esi

    def __str__(self):
        return "{}: ID{}".format(self.name, self.id)

    def __repr__(self):
        return "<{} name='{}', id={}>".format(
            self.__class__.__name__, self.name, self.id)

    @classmethod
    async def convert(cls, ctx, argument):
        await ctx.trigger_typing()
        result = await ctx.bot.zkb_api.esi_search_multi_handled(
            ctx, argument, 'corporation')
        if not result:
            raise commands.BadArgument(
                "Corporation '{}' not found." .format(argument))
        corp = await ctx.bot.zkb_api.get_corporation(result)
        if not corp:
            raise commands.BadArgument(
                "Corporation '{}' not found in ZKillboard." .format(
                    argument))
        return corp

    async def alliance(self):
        if not self.alliance_id:
            return None

        if not self._alliance:
            alliance = await self.api.get_alliance(self.alliance_id)
            self._alliance = alliance

        return self._alliance

    async def ceo(self):
        if not self._ceo:
            ceo = await self.api.get_character(self.ceo_id)
            self._ceo = ceo

        return self._ceo


class ZKBCharacter:
    __slots__ = (
        'id', 'name', 'threat', 'solo', 'group_data',
        'isk_destroyed', 'isk_lost', 'monthly_data', 'points_destroyed',
        'points_lost', 'ships_destroyed', 'ships_lost', 'solo_kills',
        'solo_losses', 'top_all_time', 'trophies', 'active_pvp', 'api',
        '_corporation', '_alliance', '_last_killmail', '_esi',
        '_killmail', 'corporation_id', 'faction_id', 'alliance_id',
        'security', '_top_lists', 'total_kills'
    )

    def __init__(self, data, zkb_api):
        self.api = zkb_api
        self.id = data['id']
        info = data.get('info')
        self.name = info['name']
        self.corporation_id = info['corporationID']
        self.alliance_id = info['allianceID']
        self.faction_id = info['factionID']
        self.total_kills = data.get('allTimeSum')
        self.threat = data.get('dangerRatio')
        self.security = data.get('secStatus')
        gang_ratio = data.get('gangRatio')
        self.solo = (100 - gang_ratio) if gang_ratio else None
        self.group_data = data.get('groups')
        self.isk_destroyed = data.get('iskDestroyed')
        self.isk_lost = data.get('iskLost')
        self.monthly_data = data.get('months')
        self.points_destroyed = data.get('pointsDestroyed')
        self.points_lost = data.get('pointsLost')
        self.ships_destroyed = data.get('shipsDestroyed')
        self.ships_lost = data.get('shipsLost')
        self.solo_kills = data.get('soloKills')
        self.solo_losses = data.get('soloLosses')
        self.top_all_time = data.get('topAllTime')
        self.trophies = data.get('trophies')
        self.active_pvp = data.get('activepvp')
        self._top_lists = data.get('topLists')
        self._corporation = None
        self._alliance = None
        self._last_killmail = None
        self._killmail = None
        self._esi = None

    async def fetch_details(self):
        if not self._esi:
            self._esi = await self.api.esi.get_character(self.id)

        return self._esi

    def __str__(self):
        return "{}: ID{}".format(self.name, self.id)

    def __repr__(self):
        return "<{} name='{}', id={}>".format(
            self.__class__.__name__, self.name, self.id)

    @classmethod
    async def convert(cls, ctx, argument):
        await ctx.trigger_typing()
        member = await mention_to_member(ctx.guild, argument)
        if member:
            argument = member.display_name

        result = await ctx.bot.zkb_api.esi_search_multi_handled(
            ctx, argument, 'character')

        if not result:
            raise commands.BadArgument(
                "Character '{}' not found." .format(argument))

        char = await ctx.bot.zkb_api.get_character(result)

        if not char:
            raise commands.BadArgument(
                "Character '{}' not found in ZKillboard." .format(
                    argument))

        return char

    async def corporation(self):
        if not self._corporation:
            corp = await self.api.get_corporation(self.corporation_id)
            self._corporation = corp

        return self._corporation

    async def alliance(self):
        if not self.alliance_id:
            return None

        if not self._alliance:
            alliance = await self.api.get_alliance(self.alliance_id)
            self._alliance = alliance

        return self._alliance

    @property
    def killmail_request(self):
        return self.api.killmail_request().character(self.id)

    async def killmail(self, no_items=True, kills_only=False):
        if not self._killmail or not no_items or kills_only:
            request = self.api.killmail_request().character(self.id)
            killmail = await request.fetch(
                no_items=no_items, kills=kills_only)

            if not no_items or kills_only:
                return killmail

            self._killmail = killmail

        return self._killmail

    async def last_killmail(self, kills_only=False):
        if not self._last_killmail or kills_only:
            killmail = await self.killmail(kills_only=kills_only)
            last_km = killmail[0]
            await last_km.fetch_details()

            if kills_only:
                return last_km

            self._last_killmail = last_km

        return self._last_killmail

    async def type(self):
        # prepare important item types
        titans = [11567, 3764, 671, 23773, 42126, 42241, 45649]
        supers = [23919, 23917, 23913, 22852, 3514, 42125]
        probe_launchers = [4258, 4260, 17901, 17938, 28756, 28758]
        rorqual = 28352

        type_count = Counter()
        notes = []

        # get killmails and load the details from esi all at the same time
        get_kills = self.killmail_request.fetch(kills=True, no_items=True)
        get_losses = self.killmail_request.fetch(losses=True, details=True)
        kills, losses = await asyncio.gather(get_kills, get_losses)

        # cache most recent killmail
        if kills and losses:
            if kills[0].id > losses[0].id:
                self._last_killmail = kills[0]
            else:
                self._last_killmail = losses[0]
        else:
            km = kills or losses
            if km:
                self._last_killmail = km[0]

        last_kill = None
        if kills:
            await kills[0].fetch_details()
            last_kill = kills[0]

        # collate all seen ship ids
        ship_ids = [k.details.ship_type_id for k in losses]

        if last_kill:
            for atk in last_kill.details._attackers:
                if atk.get('character_id') == self.id:
                    try:
                        ship_ids.append(atk['ship_type_id'])
                    except KeyError:
                        continue

        # note if seen in a super or titan
        seen_text = '**This pilot has been seen in a {}**'
        if any([s in titans for s in ship_ids]):
            notes.append(seen_text.format('Titan'))
        if any([s in supers for s in ship_ids]):
            notes.append(seen_text.format('Super'))

        for loss in losses:
            # get a full item list
            items = [i.get('item_type_id') for i in loss.details._items]

            # check if cynos are in item list
            if 28646 in items:
                type_count['covert_cyno'] += 1
            if 21096 in items:
                type_count['cyno'] += 1

            # check if probe launchers are in list
            pl_count = sum([1 for i in items if i in probe_launchers])
            type_count['probes'] += pl_count

        # blops hotdropper type
        if type_count['covert_cyno'] >= 2:
            alliances = Counter()
            corporations = Counter()

            # collate corps and alliances they've killed alongside before
            for kill in kills:
                for attacker in kill.details._attackers:
                    if attacker['alliance_id']:
                        alliances[attacker['alliance_id']] += 1
                    corporations[attacker['corporation_id']] += 1

            # base on alliance data if we have it
            if alliances:
                dominant = alliances.most_common(1)[0][0]
                alliance = await self.api.get_alliance(dominant)
                char_type = '**BLOPS Hotdropper for {}**'.format(
                    alliance.name)
                notes = '\n'.join(notes)
                return char_type, notes

            dominant = corporations.most_common(1)[0][0]
            corporation = await self.api.get_corporation(dominant)
            char_type = '**BLOPS Hotdropper for {}**'.format(
                corporation.name)
            notes = '\n'.join(notes)
            return char_type, notes

        # the rest of the types
        threat = self.threat or 0
        solo = self.solo or 0

        if type_count['cyno'] >= 5 and threat <= 30:
            return 'Cyno Alt', '\n'.join(notes)
        if type_count['probes'] >= 5 and threat > 50:
            return '**Combat Prober / Possible FC**', '\n'.join(notes)
        if type_count['probes'] >= 5 and threat <= 50:
            return 'Exploration Pilot', '\n'.join(notes)
        if type_count['cyno'] >= 5 and threat > 30:
            return '**Possible Hot Dropper**', '\n'.join(notes)
        if threat <= 30 and rorqual in ship_ids:
            return 'Rorqual Pilot', '\n'.join(notes)
        if threat <= 30:
            return 'PVE Pilot', '\n'.join(notes)
        if solo >= 50:
            return 'Solo PVP Pilot', '\n'.join(notes)
        if solo <= 15:
            return 'Fleet Pilot', '\n'.join(notes)
        if solo < 50:
            return 'Balanced PVP Pilot', '\n'.join(notes)

    async def intel(self):
        char_type, notes = await self.type()
        active_system = 'This player has not been active recently.'

        for top_type in self._top_lists:
            if top_type['type'] != 'solarSystem':
                continue
            try:
                system_name = top_type['values'][0]['solarSystemName']
            except (KeyError, IndexError):
                continue
            system_info = 'The past week they have been most active in {}'
            active_system = system_info.format(system_name)

        intel = []

        if notes:
            intel.append(notes)

        intel.append("{name} is most likely a {type}".format(
            name=self.name, type=char_type))

        intel.append(active_system)

        if self.solo:
            intel.append(("You have a {}% chance of encountering this "
                          "player solo.").format(self.solo))

        return '\n'.join(intel)

    async def intel_embed(self, guild):
        zkill = "{}/character/{}/".format(
            ZKB_PUBLIC_URL, self.id)
        eve_prism = 'http://eve-prism.com/?view=character&name={}'.format(
            urllib.parse.quote(self.name))
        eve_who = 'https://evewho.com/pilot/{}'.format(
            urllib.parse.quote(self.name))

        # start the embed
        embed = utils.make_embed(
            guild=guild,
            title_url=zkill,
            title=self.name,
            content='[ZKill]({}) / [EveWho]({}) / [EVE-Prism]({})'.format(
                zkill, eve_prism, eve_who))

        # add provider footer
        embed.set_footer(
            icon_url=guild.me.avatar_url,
            text="Provided Via Firetail Bot")

        # set character profile img
        char_img = EVE_IMG_URL.format('Character', self.id)
        embed.set_thumbnail(url=char_img)

        # add intel report
        intel = await self.intel()
        embed.add_field(
            name="Firetail Intel Report", value=intel, inline=False)

        # fetch alliance and corp details
        alliance = await self.alliance()
        corporation = await self.corporation()
        last_kill = await self.last_killmail()

        # add general info
        fields = ['Corporation:', 'Last Seen System:', 'Last Seen Ship:']
        values = [
            '{} [{}]'.format(corporation.name, corporation.ticker),
            await last_kill.details.system(),
            await last_kill.details.ship_type()
        ]
        if alliance:
            new_fields = ['Alliance:']
            new_values = ['{} [{}]'.format(alliance.name, alliance.ticker)]
            new_fields.extend(fields)
            new_values.extend(values)
            fields = new_fields
            values = new_values

        embed.add_field(
            name="General Info",
            value='\n'.join(fields),
            inline=True)
        embed.add_field(
            name="-",
            value='\n'.join(values),
            inline=True)

        # add pvp info
        if any([self.threat, self.solo, self.solo_kills, self.total_kills]):
            threat = "{}%".format(self.threat) if self.threat else 'N/A'
            solo = "{}%".format(100 - self.solo) if self.solo else 'N/A'
            embed.add_field(
                name="PVP Info",
                value='Threat Rating:\nGang Ratio:\nSolo Kills:\nTotal Kills:',
                inline=True)
            embed.add_field(
                name="-",
                value='{}\n{}\n{}\n{}'.format(
                    threat, solo, self.solo_kills, self.total_kills or 'N/A'),
                inline=True)

        return embed


class ZKBKillmailRequest:
    def __init__(self, zkb_api, kill_id=None):
        self.api = zkb_api
        self.base_url = ZKB_URL
        self.modifiers = {}
        self.kill_id = kill_id

    def __str__(self):
        return self.url()

    def __repr__(self):
        if self.kill_id:
            return "<{} id={}, settings={}>".format(
                self.__class__.__name__, self.kill_id, self.modifiers)
        return "<{} settings={}>".format(
            self.__class__.__name__, self.modifiers)

    def _remove_modifier(self, key):
        if key in self.modifiers:
            self.modifiers.pop(key)

    def page(self, page_number: int = None):
        if page_number:
            self.modifiers['page'] = str(int(page_number))
        else:
            self._remove_modifier('page')

        return self

    def time_range(self, start_time=None, end_time=None,
                   year: int = None, month: int = None,
                   past_seconds: int = None):

        parts = [start_time or end_time, year and month, past_seconds]
        if sum(map(bool, parts)) > 1:
            raise ZKBRequestError(
                "Can't mix start/endtimes, year/month, and past_seconds")

        if start_time or end_time:
            # format datetime to zkb timestamp
            if isinstance(start_time, datetime):
                start_time = start_time.strftime(ZKB_TIMESTAMP_FORMAT)
            if isinstance(end_time, datetime):
                end_time = end_time.strftime(ZKB_TIMESTAMP_FORMAT)

        if start_time:
            self.modifiers['startTime'] = start_time
        else:
            self._remove_modifier('startTime')

        if end_time:
            self.modifiers['endTime'] = end_time
        else:
            self._remove_modifier('endTime')

        if year and month:
            year = str(int(year))
            if len(year) == 2:
                year = "20" + year

            self.modifiers['year'] = year

            self.modifiers['month'] = str(int(month)).zfill(2)

        else:
            self._remove_modifier('year')
            self._remove_modifier('month')

        if past_seconds:
            self.modifiers['pastSeconds'] = str(int(past_seconds))

        else:
            self._remove_modifier('pastSeconds')

        return self

    def id_range(self, before_id: int = None, after_id: int = None):
        if before_id:
            self.modifiers['beforeKillID'] = str(int(before_id))
        else:
            self._remove_modifier('beforeKillID')

        if after_id:
            self.modifiers['afterKillID'] = str(int(after_id))
        else:
            self._remove_modifier('afterKillID')

        return self

    def id(self, kill_id=None):
        if kill_id:
            self.kill_id = kill_id
        else:
            self.kill_id = None

        return self

    def url(self, kills=False, losses=False, w_space=False,
            solo=False, final_blow=False, awox: bool = None,
            npc: bool = None, no_items=False, no_attackers=False):
        url_str = self.base_url
        if kills:
            url_str += '/kills'
        if losses:
            url_str += '/losses'
        if w_space:
            url_str += '/w-space'
        if solo:
            url_str += '/solo'
        if final_blow:
            url_str += '/finalblow-only'
        if awox is not None:
            url_str += '/awox/{}'.format(int(awox))
        if npc is not None:
            url_str += '/npc/{}'.format(int(npc))
        if no_items:
            url_str += '/no-items'
        if no_attackers:
            url_str += '/no-attackers'
        for k, v in self.modifiers.items():
            url_str += '/{}/{}'.format(k, v)
        return url_str + '/'

    async def fetch(self, kills=False, losses=False, w_space=False,
                    solo=False, final_blow=False, awox: bool = None,
                    npc: bool = None, details=False, no_items=False,
                    no_attackers=False):
        url = self.url(kills, losses, w_space, solo, final_blow, awox,
                       npc, no_items, no_attackers)
        async with self.api.session.get(url) as r:
            try:
                data = await r.json()
            except ValueError:
                return None

        killmails = [ZKBKillmail(k, self.api) for k in data]
        if details:
            killmails = killmails[:50]
            km_fetches = [k.fetch_details() for k in killmails]
            await asyncio.gather(*km_fetches)
        return killmails

    def character(self, character_id=None):
        if character_id:
            self.modifiers['characterID'] = character_id
        else:
            self._remove_modifier('characterID')
        return self

    def corporation(self, corporation_id):
        if corporation_id:
            self.modifiers['corporationID'] = corporation_id
        else:
            self._remove_modifier('corporationID')
        return self

    def alliance(self, alliance_id):
        if alliance_id:
            self.modifiers['allianceID'] = alliance_id
        else:
            self._remove_modifier('allianceID')
        return self

    def faction(self, faction_id):
        if faction_id:
            self.modifiers['factionID'] = faction_id
        else:
            self._remove_modifier('factionID')
        return self

    def ship_type(self, ship_type_id):
        if ship_type_id:
            self.modifiers['shipTypeID'] = ship_type_id
        else:
            self._remove_modifier('shipTypeID')
        return self

    def group(self, group_id):
        if group_id:
            self.modifiers['groupID'] = group_id
        else:
            self._remove_modifier('groupID')
        return self

    def system(self, system_id=None):
        if system_id:
            self.modifiers['solarSystemID'] = system_id
        else:
            self._remove_modifier('solarSystemID')
        return self

    def region(self, region_id):
        if region_id:
            self.modifiers['regionID'] = region_id
        else:
            self._remove_modifier('regionID')
        return self

    def war(self, war_id=None):
        if war_id:
            self.modifiers['warID'] = war_id
        else:
            self._remove_modifier('warID')
        return self

    def isk(self, min_isk_value=None):
        if min_isk_value:
            self.modifiers['iskValue'] = min_isk_value
        else:
            self._remove_modifier('iskValue')
        return self


class ZKBKillmail:
    def __init__(self, data, zkb_api):
        self.id = data['killmail_id']
        self.api = zkb_api
        zkb_data = data['zkb']
        self.hash = zkb_data['hash']
        self.fitted_value = zkb_data.get('fittedValue')
        self.location_id = zkb_data.get('locationID')
        self.points = zkb_data.get('points')
        self.total_value = zkb_data.get('totalValue')
        self.npc = zkb_data.get('npc')
        self.solo = zkb_data.get('solo')
        self.awox = zkb_data.get('awox')
        self.details = None

    async def fetch_details(self):
        if not self.details:
            self.details = await self.api.esi.get_killmail(self.id, self.hash)
        return self.details


class ZKillboard:
    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.bot.zkb_api = self
        self.esi = bot.esi_data
        self.base_url = ZKB_URL
        self.history_url = self.base_url + "/history/{date}/"

    def __unload(self):
        del self.bot.zkb_api

    @staticmethod
    async def esi_search_multi_handled(ctx, item, category):
        esi = ctx.bot.esi_data
        # get the results from esi
        results = await esi.esi_search(item, category)

        # handle if none or too many
        if not results:
            raise ZKBNoResults("No results for '{}'".format(item))
        elif len(results) > 9:
            raise ZKBTooManyResults(
                'Too many results ({}/10)'.format(len(results)))

        # handle if between 2 and 9 results
        elif len(results) > 1:
            result_list = []

            # get the proper esi model type
            esi_get_method = getattr(esi, 'get_{}'.format(category))
            for idx, result in enumerate(results):
                esi_result = await esi_get_method(result)

                # disregard if not found in esi
                if not esi_result:
                    continue

                # append to result_list with choice number emoji
                result_list.append("{}\u20e3 {}: ID{}".format(
                    idx, esi_result.name, esi_result.id))

            # send embed for asking which result they wanted
            embed = utils.make_embed(
                guild=ctx.guild,
                title='Which was the result you wanted?',
                content='\n'.join(result_list))
            ask_msg = await ctx.send(embed=embed)

            # add choice number reactions for user to respond with
            for i in range(len(results)):
                await ask_msg.add_reaction('{}\u20e3'.format(i))

            # add cancel option
            await ask_msg.add_reaction('\u274e')

            # check it's the author and it's a number or cancel emoji
            def check(reaction, user):
                if user != ctx.author:
                    return False
                if len(str(reaction.emoji)) == 1:
                    return False
                if str(reaction.emoji) == '\u274e':
                    return True
                if str(reaction.emoji)[1] != '\u20e3':
                    return False
                return True
            reaction, __ = await ctx.bot.wait_for(
                'reaction_add', timeout=30.0, check=check)

            if not reaction or str(reaction.emoji) == '\u274e':
                try:
                    await ask_msg.remove_reactions()
                except discord.Forbidden:
                    pass
                return

            # get the result, but account for invalid number emoji's
            try:
                result = results[int(str(reaction.emoji)[0])]
            except KeyError:
                return await ctx.send("Invalid response received. Try again.")

            # delete prompt unless we don't have permissions here
            try:
                await ask_msg.delete()
            except discord.Forbidden:
                pass
        else:
            result = results[0]

        return result

    async def fetch_stats(self, entity_type, entity_id):
        url = '{}/stats/{}/{}/'.format(self.base_url, entity_type, entity_id)
        async with self.bot.session.get(url) as r:
            try:
                data = await r.json()
            except ValueError:
                return None
        return data

    async def get_alliance(self, alliance_id):
        data = await self.fetch_stats('allianceID', alliance_id)
        if not data:
            return None
        if not data.get('id'):
            return None
        return ZKBAlliance(data, self)

    async def get_corporation(self, corporation_id):
        data = await self.fetch_stats('corporationID', corporation_id)
        if not data:
            return None
        if not data.get('id'):
            return None
        return ZKBCorporation(data, self)

    async def get_character(self, character_id):
        data = await self.fetch_stats('characterID', character_id)
        if not data:
            return None
        if not data.get('id'):
            return None
        return ZKBCharacter(data, self)

    def killmail_request(self, kill_id=None):
        return ZKBKillmailRequest(self, kill_id)

    @commands.group(invoke_without_command=True)
    async def zk(self, ctx):
        pass

    @zk.command(aliases=['char'])
    async def character(self, ctx, *, character: ZKBCharacter):
        embed = await character.intel_embed(ctx.guild)
        await ctx.send(embed=embed)

    @zk.command(aliases=['ally'])
    async def alliance(self, ctx, *, alliance: ZKBAlliance):
        await ctx.send(repr(alliance))

    @zk.command(aliases=['corp'])
    async def corporation(self, ctx, *, corporation: ZKBCorporation):
        await ctx.send(str(corporation))

    async def __error(self, ctx, error):
        if isinstance(error, ZKBResultError):
            await ctx.send(error)
