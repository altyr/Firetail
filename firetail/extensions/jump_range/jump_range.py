import logging

from discord.ext import commands

from firetail.core import checks

log = logging.getLogger(__name__)


class JumpRange(commands.Cog):
    """This extension handles the time commands."""

    @commands.command()
    @checks.spam_check()
    @checks.is_whitelist()
    async def range(self, ctx, system, ship: str.title, jdc_level: int = 5):
        """Provides Jump Range."""

        async with ctx.typing():
            log.info(f'JumpRange - {ctx.message.author} requested a jump range map.')
            try:
                if '-' in system:
                    system = system.upper()
                else:
                    system = system.title()
            except Exception:
                await ctx.dest.send('**ERROR:** Do !help range for more info')
                return

            system_id = await ctx.bot.esi_data.esi_search(system, 'solar_system')

            if system_id is None:
                dest = ctx.author if ctx.bot.config.dm_only else ctx
                log.info(f'JumpPlanner ERROR - {system} could not be found')
                await dest.send(f'**ERROR:** No system found with the name {system}')
                return

            if system_id is False:
                log.info(f'JumpPlanner ERROR - {system} could not be found')
                await ctx.dest.send(f'**ERROR:** Multiple systems found matching {system}, please be more specific')
                return

            system_info = await ctx.bot.esi_data.system_info(system_id['solar_system'][0])
            system = system_info['name']

            if jdc_level > 5:
                await ctx.dest.send('**ERROR:** Improper JDC skill level')
                return

            item_id = await ctx.bot.esi_data.item_id(ship)
            if not item_id:
                await ctx.dest.send("**ERROR:** Invalid ship provided.")
                return

            accepted_ship_groups = [898, 659, 485, 547, 902, 30, 1538]
            ship_info = await ctx.bot.esi_data.item_info(item_id)
            ship_group_id = ship_info['group_id']
            if ship_group_id not in accepted_ship_groups:
                log.info(f'JumpRange ERROR - {ship} is not a Jump Capable Ship')
                await ctx.dest.send(f'**ERROR:** No Jump Capable Ship Found With The Name {ship}')
                return

            url = f'http://evemaps.dotlan.net/range/{ship},{jdc_level}/{system}'
            embed = await ctx.embed(
                f"{ship} jump range from {system} with JDC {jdc_level}",
                icon="https://pbs.twimg.com/profile_images/1145561069/dotlan-avatar_400x400.png",
                title_url=url,
                send=False
            )
            await ctx.dest.send(embed=embed)
            if ctx.bot.config.delete_commands:
                await ctx.message.delete()
