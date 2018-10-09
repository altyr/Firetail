from .zkillboard_cog import ZKillboard


def setup(bot):
    bot.add_cog(ZKillboard(bot))
