import importlib
import os
import pkgutil
import traceback

from discord.ext import commands

from firetail import utils
from firetail.core import checks


class ExtensionManager(commands.Cog):
    """Commands to add, remove and change extensions for Firetail."""

    def cog_check(self, ctx):
        return checks.check_is_co_owner(ctx)

    @commands.group()
    async def ext(self, ctx):
        """Commands to manage extensions."""
        if ctx.invoked_subcommand is None:
            await ctx.bot.send_cmd_help(ctx)

    @ext.command()
    async def list(self, ctx):
        """List all available extensions and their loaded status."""
        ext_folder = "extensions"
        ext_dir = os.path.join(os.path.dirname(__file__), "..", ext_folder)
        ext_files = [name for _, name, _ in pkgutil.iter_modules([ext_dir])]
        loaded_ext = []
        count_loaded = 0
        count_ext = 0
        msg = ""
        for ext in ctx.bot.extensions:
            loaded_ext.append(ext)
        for ext in ext_files:
            count_ext += 1
            ext_name = ("firetail.extensions." + ext)
            is_loaded = ext_name in loaded_ext
            status = ":black_small_square:"
            if is_loaded:
                count_loaded += 1
                status = ":white_small_square:"
            msg += f"{status} {ext}\n"
        count_msg = f"{count_loaded} of {count_ext} extensions loaded.\n\n"
        embed = utils.make_embed(msg_type='info',
                                 title='Available Extensions',
                                 content=count_msg + msg)
        await ctx.send(embed=embed)

    @ext.command()
    async def unload(self, ctx, ext):
        """Unload an extension."""
        ext_name = f"firetail.extensions.{ext}"
        if ext_name in ctx.bot.extensions:
            ctx.bot.unload_extension(ext_name)
            await ctx.success(f'{ext} extension unloaded.')
        else:
            await ctx.error(f'{ext} extension not loaded.')

    @ext.command(aliases=["reload"])
    async def load(self, ctx, ext):
        """Load or reload an extension."""
        ext_folder = "extensions"
        ext_dir = os.path.join(os.path.dirname(__file__), "..", ext_folder)
        ext_files = [name for _, name, _ in pkgutil.iter_modules([ext_dir])]
        if ext not in ext_files:
            await ctx.error(f"{ext} extension not found.")
            return

        ext_name = f"firetail.extensions.{ext}"
        was_loaded = ext_name in ctx.bot.extensions

        try:
            if was_loaded:
                ctx.bot.reload_extension(ext_name)
                await ctx.success(f'{ext} extension reloaded.')
            else:
                ctx.bot.load_extension(ext_name)
                await ctx.success(f'{ext} extension loaded.')
        except commands.ExtensionFailed as e:
            original_traceback = "\n".join(traceback.format_tb(e.original.__traceback__))
            await ctx.codeblock(original_traceback, title=f"Exception on loading {ext}")

    @ext.command()
    async def showext(self, ctx):
        """Show raw extension list."""
        bot = ctx.bot
        embed = utils.make_embed(msg_type='info',
                                 title='Raw Extension List',
                                 content='\n'.join(bot.extensions))
        await ctx.send(embed=embed)

    @commands.command(name="load", aliases=["reload"])
    async def load_alias(self, ctx, ext):
        """Load or reload an extension."""
        await ctx.invoke(self.load, ext)

    @commands.command()
    async def reload_core(self, ctx):
        """Reload Core Commands."""
        bot = ctx.bot
        try:
            bot.unload_extension('firetail.core.commands')
            bot.load_extension('firetail.core.commands')
            embed = utils.make_embed(msg_type='success',
                                     title='Core Commands reloaded.')
            await ctx.send(embed=embed)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            embed = utils.make_embed(msg_type='error',
                                     title='Error loading Core Commands',
                                     content=msg)
            await ctx.send(embed=embed)

    @commands.command()
    async def reload_dm(self, ctx):
        """Reload Data Manager."""
        bot = ctx.bot
        try:
            bot.unload_extension('firetail.data_manager')
            bot.load_extension('firetail.data_manager')
            embed = utils.make_embed(msg_type='success',
                                     title='Data Manager reloaded.')
            await ctx.send(embed=embed)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            embed = utils.make_embed(msg_type='error',
                                     title='Error loading Data Manager',
                                     content=msg)
            await ctx.send(embed=embed)

    @commands.command()
    async def reload_esi(self, ctx):
        """Reload API module."""

        try:
            from firetail.lib import esi
            importlib.reload(esi)
        except Exception as e:
            tb = "\n".join(traceback.format_tb(e.__traceback__))
            await ctx.codeblock(tb, title="Exception on loading ESI")
        else:
            ctx.bot.esi_data = esi.ESI(ctx.bot.session)
            await ctx.success("ESI Reloaded")


def setup(bot):
    bot.add_cog(ExtensionManager())
