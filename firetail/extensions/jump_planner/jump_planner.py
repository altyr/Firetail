import logging

from discord.ext import commands

from firetail.core import checks

log = logging.getLogger(__name__)


class JumpPlanner(commands.Cog):
    """This extension handles the time commands."""

    @commands.command()
    @checks.spam_check()
    @checks.is_whitelist()
    async def jump(self, ctx, route, ship: str.title = 'Aeon', jdc_level: int = 5):
        """
        Provides a Jump route.

        '!jump system:system' Gives you the JDC 5 Carrier/Super/Fax route by default.
        '!jump system:system:system:system' accepts multiple waypoints.
        '!jump system:system SHIP' accepts a different jump capable ship as input.
        '!jump system:system SHIP 4' This is also possible to declare a JDC besides 5.
        """

        log.info(f'JumpPlanner - {ctx.message.author} requested a jump route.')

        if jdc_level > 5:
            await ctx.dest.send('**ERROR:** Invalid JDC level')
            return

        systems = route.split(':')
        skills = f'{jdc_level}55'
        x = 0
        url_route = []
        for system in systems:
            search = 'solar_system'
            system_id = await ctx.bot.esi_data.esi_search(system, search)
            if system_id is None:
                log.info(f'JumpPlanner ERROR - {system} could not be found')
                await ctx.dest.send(f'**ERROR:** No system found with the name {system}')
                return
            if system_id is False:
                log.info(f'JumpPlanner ERROR - {system} could not be found')
                await ctx.dest.send(f'**ERROR:** Multiple systems found matching {system}, please be more specific')
                return
            system_info = await ctx.bot.esi_data.system_info(system_id['solar_system'][0])
            if system_info['security_status'] >= 0.5 and x != 0:
                log.info(f'JumpPlanner ERROR - {system} is a high security system')
                await ctx.dest.send(
                    f'**ERROR:** {system} is a high security system, you can only jump out of high security systems.'
                )
                return
            x = x + 1
            url_route.append(system_info['name'])

        item_id = await ctx.bot.esi_data.item_id(ship)
        accepted_ship_groups = [898, 659, 485, 547, 902, 30, 1538]
        ship_info = await ctx.bot.esi_data.item_info(item_id)
        ship_group_id = ship_info['group_id']
        if ship_group_id not in accepted_ship_groups:
            dest = ctx.author if ctx.bot.config.dm_only else ctx
            log.info(f'JumpPlanner ERROR - {ship} is not a Jump Capable Ship')
            await dest.send(f'**ERROR:** No Jump Capable Ship Found With The Name {ship}')
            return

        url_route = ':'.join(url_route)
        url = f'http://evemaps.dotlan.net/jump/{ship},{skills}/{url_route}'
        clean_route = url_route.replace(':', ' to ')
        embed = await ctx.embed(
            f"{ship} jump route from {clean_route} with JDC {jdc_level}",
            icon="https://pbs.twimg.com/profile_images/1145561069/dotlan-avatar_400x400.png",
            title_url=url,
            send=False
        )

        await ctx.dest.send(embed=embed)
        if ctx.bot.config.delete_commands:
            await ctx.message.delete()
