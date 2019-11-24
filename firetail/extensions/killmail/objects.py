import asyncio
import logging
from typing import NamedTuple

from dateutil.parser import parse

from firetail.utils import make_embed

log = logging.getLogger(__name__)


class Position(NamedTuple):
    x: float
    y: float
    z: float


class Item:
    __slots__ = ('_data', '_esi', 'flag', 'item_type_id', 'qty_dropped', 'qty_destroyed', 'singleton', 'name')

    def __init__(self, data, esi):
        self._data = data
        self._esi = esi
        self.flag = data.get('flag')
        self.item_type_id = data.get('item_type_id')
        self.qty_dropped = data.get('quantity_dropped', 0)
        self.qty_destroyed = data.get('quantity_destroyed', 0)
        self.singleton = data.get('singleton')
        self.name = None

    async def fetch_name(self):
        item = await self._esi.item_info(self.item_type_id)
        self.name = item.get('name')


class Character:
    __slots__ = ('_data', '_esi', 'id', 'corp_id', 'alliance_id', 'ship_type_id', 'name', 'corp', 'alliance', 'ship')

    def __init__(self, data, esi):
        self._data = data
        self._esi = esi
        self.id = data.get('character_id')
        self.corp_id = data.get('corporation_id')
        self.alliance_id = data.get('alliance_id', None)
        self.ship_type_id = data.get('ship_type_id', None)
        self.name = None
        self.corp = None
        self.alliance = None
        self.ship = None

    async def fetch_name(self):
        if not self.name:
            self.name = await self._esi.character_name(self.id)

    async def fetch_corp(self):
        if not self.corp:
            corp = await self._esi.corporation_info(self.corp_id)
            self.corp = corp.get('name')

    async def fetch_alliance(self):
        if not self.alliance and self.alliance_id:
            alliance = await self._esi.alliance_info(self.alliance_id)
            self.alliance = alliance.get('name')

    async def fetch_ship(self):
        if not self.ship_type_id:
            return
        if not self.ship:
            ship = await self._esi.item_info(self.ship_type_id)
            self.ship = ship.get('name')

    def fetch_all(self):
        return asyncio.gather(
            self.fetch_name(),
            self.fetch_corp(),
            self.fetch_alliance(),
            self.fetch_ship()
        )

    def info_output(self):
        info = []
        if self.name:
            info.append(f"Name: [{self.name}](https://zkillboard.com/character/{self.id}/)")
            if self.ship:
                info.append(f"Ship: [{self.ship}](https://zkillboard.com/ship/{self.ship_type_id}/)")
        else:
            info.append(f"Structure: [{self.ship}](https://zkillboard.com/ship/{self.ship_type_id}/)")

        info.append(f"Corp: [{self.corp}](https://zkillboard.com/corporation/{self.corp_id}/)")

        if self.alliance:
            info.append(f"Alliance: [{self.alliance}](https://zkillboard.com/alliance/{self.alliance_id}/)")

        return "\n".join(info)


class Attacker(Character):
    __slots__ = ('weapon_type_id', 'damage', 'final_blow', 'security', *Character.__slots__)

    def __init__(self, data, esi):
        super().__init__(data, esi)
        self.weapon_type_id = data.get('weapon_type_id')
        self.damage = data.get('damage_done')
        self.final_blow = data.get('final_blow')
        self.security = data.get('security_status')


class Victim(Character):
    __slots__ = ('damage_taken', 'items', 'position', *Character.__slots__)

    def __init__(self, data, esi):
        super().__init__(data, esi)
        self.damage_taken = data.get('damage_taken')
        self.items = [Item(i, esi) for i in data.get('items', [])]
        pos = data.get('position')
        if pos:
            self.position = Position(**pos)


class Mail:
    __slots__ = (
        '_data', '_esi', 'id', 'time', 'system_id', 'final_attacker', 'attackers', 'victim', 'corp_id', 'alliance_id',
        'location_id', 'hash', 'fitted_value', 'value', 'points', 'npc', 'solo', 'awox', 'eve_url', 'url', 'system',
        'celestial', 'constellation', 'constellation_id', 'region_id', 'region'
    )

    def __init__(self, payload, esi):
        self._data = payload
        self._esi = esi
        self.id = payload.get('killmail_id')
        self.time = parse(payload.get('killmail_time'))
        self.system_id = payload.get('solar_system_id')

        self.final_attacker = None
        self.attackers = {}
        for attacker_data in payload.get("attackers", []):
            attacker = Attacker(attacker_data, esi)
            self.attackers[attacker.id] = attacker
            if attacker.final_blow:
                self.final_attacker = attacker

        self.victim = Victim(payload.get('victim'), esi)
        self.corp_id = self.victim.corp_id
        self.alliance_id = self.victim.alliance_id

        zkb = payload.get('zkb', {})
        self.location_id = zkb.get('locationID')
        self.hash = zkb.get('hash')
        self.fitted_value = zkb.get('fittedValue')
        self.value = zkb.get('totalValue')
        self.points = zkb.get('points')
        self.npc = zkb.get('npc')
        self.solo = zkb.get('solo')
        self.awox = zkb.get('awox')
        self.eve_url = zkb.get('esi')
        self.url = f"https://zkillboard.com/kill/{self.id}/"

        self.system = None
        self.celestial = None
        self.constellation = None
        self.constellation_id = None
        self.region_id = None
        self.region = None

    def __repr__(self):
        sys = self.system_id
        victim = self.victim.id
        ship = self.victim.ship
        value = self.value
        npc = " NPC" if self.npc else ""
        return f"<Mail {self.id}{npc} system={sys} victim={victim} ship={ship} value={value}>"

    async def fetch_region(self):
        if not self.region:
            await self.fetch_constellation()
            region = await self._esi.region_info(self.region_id)
            self.region = region.get('name')

    async def fetch_constellation(self):
        if not self.constellation:
            await self.fetch_system()
            constellation = await self._esi.constellation_info(self.constellation_id)
            self.constellation = constellation.get('name')
            self.region_id = constellation.get('region_id')

    async def fetch_system(self):
        if not self.system:
            if not self.system_id:
                return "Unknown"
            system = await self._esi.system_info(self.system_id)
            if not system:
                return "Unknown"
            self.constellation_id = system.get('constellation_id')
            self.system = system.get('name')

    async def fetch_celestial(self):
        if not self.celestial:
            celestial = await self._esi.celestial_info(self.location_id)
            self.celestial = celestial.get('name', 'Unknown')

    def fetch_all(self):
        return asyncio.gather(self.victim.fetch_all(), self.fetch_celestial(), self.fetch_system())

    def info_output(self):
        info = [
            f"{self.system} System: "
            f"[Map](http://evemaps.dotlan.net/search?q={self.system_id}) | "
            f"[Killboard](https://zkillboard.com/system/{self.system_id}/)",
        ]
        if self.solo:
            info.insert(0, "**SOLO KILL**")
        if self.celestial:
            info.append(f"Nearest Celestial: {self.celestial}")

        return "\n".join(info)

    async def send_embed(self, channel, is_loss=False):
        await asyncio.gather(self.fetch_all(), self.victim.fetch_all(), self.final_attacker.fetch_all())

        title = "LOSS" if is_loss else "Killmail"
        embed = make_embed(
            title=f"{title}: {self.value:,} ISK",
            title_url=self.url,
            subtitle=f"{self.victim.ship} in {self.system}",
            subtitle_url=self.url,
            content=self.info_output(),
            icon="https://zkillboard.com/img/wreck.png",
            fields={
                "Victim Info": self.victim.info_output(),
                "Final Blow": self.final_attacker.info_output()
            },
            thumbnail=f"https://image.eveonline.com/Type/{self.victim.ship_type_id}_128.png",
            footer=self.time.strftime("Report created: %Y-%m-%d %H:%M EVE")
        )
        await channel.send(embed=embed)


class Subscription:
    __slots__ = ('id', 'channel', 'losses', 'threshold', 'group_id')

    def __init__(self, id_: int, channel, threshold: int = None, losses: bool = True, group_id: int = None):
        self.id = id_
        self.channel = channel

        self.losses = losses
        self.threshold = threshold

        self.group_id = group_id if group_id != 6 else None

    def __repr__(self):
        id_ = self.id
        chan = self.channel
        th = self.threshold
        loss = f" losses={self.losses}" if self.losses else ""
        grp = f"group_id={self.group_id}" if self.group_id else ""
        return f"<Subscription {id_} channel={chan} threshold={th}{loss}{grp}>"

    async def mail(self, killmail: Mail):
        if await self.valid(killmail):
            loop = asyncio.get_event_loop()
            if self.group_id:
                is_loss = self.group_id in [killmail.corp_id, killmail.alliance_id]
            else:
                is_loss = False
            loop.create_task(killmail.send_embed(self.channel, is_loss))

    async def valid(self, killmail: Mail):
        if self.threshold and killmail.value < self.threshold:
            return False

        if not self.group_id:
            return True

        if self.group_id == killmail.system_id:
            return True

        if self.losses and self.group_id in [killmail.corp_id, killmail.alliance_id]:
            return True

        if any(a.corp_id == self.group_id for a in killmail.attackers.values()):
            return True

        if any(a.alliance_id == self.group_id for a in killmail.attackers.values()):
            return True

        if not killmail.region_id:
            await killmail.fetch_celestial()
        if self.group_id == killmail.region_id:
            return True

        return False
