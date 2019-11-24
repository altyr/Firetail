import logging

from discord.ext import commands

from firetail.core import checks

log = logging.getLogger(__name__)


class EveStatus(commands.Cog):
    """This extension handles the status command."""

    @commands.command(aliases=["tq", "eve"])
    @checks.spam_check()
    @checks.is_whitelist()
    async def status(self, ctx):
        """Shows the current status of TQ."""

        log.info(f'EveStatus - {ctx.message.author} requested server info.')

        data = await ctx.bot.esi_data.server_info()
        start_time = data.get('start_time') if data else None

        if start_time:
            player_count = data.get('players')
            embed = await ctx.embed(
                "Server Online", f"{player_count:,} players connected.",
                icon="https://image.eveonline.com/Alliance/434243723_64.png",
                colour="green",
                send=False
            )
        else:
            embed = await ctx.error("Server Offline", send=False)

        # embed = make_embed(guild=ctx.guild)
        # embed.set_footer(icon_url=ctx.bot.user.avatar_url, text="Provided Via Firetail Bot")
        # embed.set_thumbnail(url="https://image.eveonline.com/Alliance/434243723_64.png")
        # embed.add_field(name="Status", value="Server State:\nPlayer Count:", inline=True)
        # embed.add_field(name="-", value=f"{status}\n{player_count}", inline=True)

        dest = ctx.author if ctx.bot.config.dm_only else ctx
        await dest.send(embed=embed)
        if ctx.bot.config.delete_commands:
            await ctx.message.delete()
