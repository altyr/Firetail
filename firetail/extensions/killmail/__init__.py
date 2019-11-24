from .killmail import Killmail


def setup(bot):
    bot.add_cog(Killmail(bot))
