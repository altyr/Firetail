import logging

from discord.ext import commands

from firetail.core import checks
from firetail.utils import make_embed

log = logging.getLogger(__name__)

HUBS = {
    'jita': 60003760,
    'amarr': 60008494,
    'dodixie': 60011866,
    'rens': 60004588,
    'hek': 60005686
}


class Price(commands.Cog):
    """This extension handles price lookups."""

    @commands.command(aliases=["pc", *HUBS])
    @checks.spam_check()
    @checks.is_whitelist()
    async def price(self, ctx, *, item: str):
        """Gets you price information from the top trade hubs.

        Use **!price item** or **!amarr item** (Works for Jita, Amarr, Dodixie, Rens, Hek)
        """

        if not item:
            dest = ctx.author if ctx.bot.config.dm_only else ctx
            embed = await ctx.error("An item to lookip needs to be provided.", send=False)
            await dest.send(embed=embed)
            return

        if item.lower() in ['fanfest ticket', 'fanfest']:
            msg = (
                "Looking to go to Fanfest?\n\n"
                "When: April 12th-14th\n\n"
                "Event Info: <https://fanfest.eveonline.com/>\n"
                "Buy Tickets: "
                "<https://www.eventbrite.com/e/eve-fanfest-2018-tickets-38384202182?aff=website>"
            )
            if ctx.bot.config.dm_only:
                return await ctx.author.send(msg)
            else:
                return await ctx.channel.send(msg)

        async with ctx.typing():
            if ctx.invoked_with not in ["pc", "price"]:
                lookup = ctx.invoked_with.title()
            else:
                lookup = 'Jita'

            log.info(f'Price - {ctx.author} requested price information for {item}')

            data = await ctx.bot.esi_data.market_data(item, HUBS.get(ctx.invoked_with, 60003760))

            if not data:
                if data is None:
                    log.info(f'Price - {item} could not be found')
                    embed = await ctx.error(f"'{item}' not found", "Are you sure it's an item?", send=False)
                if data is False:
                    log.info(f'Price - {item} multiple items found')
                    embed = await ctx.error(
                        f"'{item}' matched multiple items",
                        "Please try again with more a more specific query.",
                        send=False
                    )

                if ctx.bot.config.dm_only:
                    return await ctx.author.send(embed=embed)

                return await ctx.channel.send(embed=embed)

            type_id_raw = await ctx.bot.esi_data.esi_search(item, 'inventory_type')
            type_id = type_id_raw['inventory_type'][0]
            type_name_raw = await ctx.bot.esi_data.item_info(type_id)
            type_name = type_name_raw['name']
            buymax = '{0:,.2f}'.format(float(data['buy']['max']))
            buymin = '{0:,.2f}'.format(float(data['buy']['min']))
            buyavg = '{0:,.2f}'.format(float(data['buy']['weightedAverage']))
            buy_volume = '{0:,.0f}'.format(float(data['buy']['volume']))
            buy_orders = '{0:,.0f}'.format(float(data['buy']['orderCount']))
            sellmax = '{0:,.2f}'.format(float(data['sell']['max']))
            sellmin = '{0:,.2f}'.format(float(data['sell']['min']))
            sellavg = '{0:,.2f}'.format(float(data['sell']['weightedAverage']))
            sell_volume = '{0:,.0f}'.format(float(data['sell']['volume']))
            sell_orders = '{0:,.0f}'.format(float(data['sell']['orderCount']))
            em = make_embed(
                title=f"{lookup} System",
                title_url=f"https://market.fuzzwork.co.uk/type/{type_id}/",
                subtitle_url=f"https://market.fuzzwork.co.uk/type/{type_id}/",
                subtitle=type_name.title(),
                guild=ctx.guild
            )
            em.set_footer(text="Pricing data sourced from Fuzzworks Market API")
            em.set_thumbnail(url=f"https://image.eveonline.com/Type/{type_id}_64.png")
            em.add_field(
                name="Buy",
                value=(
                    f"Low: {buymin}\n"
                    f"Avg: {buyavg}\n"
                    f"High: {buymax}\n"
                    f"Number of Orders: {buy_orders}\n"
                    f"Volume: {buy_volume}"
                ),
                inline=True
            )
            em.add_field(
                name="Sell",
                value=(
                    f"Low: {sellmin}\n"
                    f"Avg: {sellavg}\n"
                    f"High: {sellmax}\n"
                    f"Number of Orders: {sell_orders}\n"
                    f"Volume: {sell_volume}"),
                inline=True
            )
            if ctx.bot.config.dm_only:
                await ctx.author.send(embed=em)
            else:
                await ctx.channel.send(embed=em)
            if ctx.bot.config.delete_commands:
                await ctx.message.delete()
