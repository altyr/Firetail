import logging
from datetime import datetime

import pytz
from discord.ext import commands

from firetail.core import checks


log = logging.getLogger(__name__)

TIMEZONES = {
    'EVE Time': 'UTC',
    'PST/California': 'America/Los_Angeles',
    'EST/New York': 'America/New_York',
    'CET/Copenhagen': 'Europe/Copenhagen',
    'MSK/Moscow': 'Europe/Moscow',
    'AEDT/Sydney': 'Australia/Sydney',
}


class EveTime(commands.Cog):
    """This extension handles the time commands."""

    @commands.command()
    @checks.spam_check()
    @checks.is_whitelist()
    async def time(self, ctx):
        """Shows the time in a range of timezones."""

        log.info('EveTime - {ctx.message.author} requested time info.')

        tz_field = []
        time_field = []
        for display, zone in TIMEZONES.items():
            tz_field.append(str(display))
            time_field.append(datetime.now(pytz.timezone(zone)).strftime('%H:%M'))

        embed = await ctx.embed(
            f"{tz_field.pop(0)}: {time_field.pop(0)}",
            fields={
                "Time Zones": '\n'.join(tz_field),
                "Time": '\n'.join(time_field),
            },
            inline=True,
            send=False
        )

        dest = ctx.author if ctx.bot.config.dm_only else ctx
        await dest.send(embed=embed)
        if ctx.bot.config.delete_commands:
            await ctx.message.delete()
