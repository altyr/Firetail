import discord


def colour(*args):
    """Returns a discord Colour object.
    Pass one as an argument to define colour:
        `str` match common colour names.
        `discord.Guild` bot's guild colour.
        `None` light grey.
    """
    arg = args[0] if args else None
    if isinstance(arg, str):
        color = arg
        try:
            return getattr(discord.Colour, color)()
        except AttributeError:
            return discord.Colour.lighter_grey()
    if isinstance(arg, discord.Guild):
        return arg.me.colour
    else:
        return discord.Colour.lighter_grey()


def make_embed(
    msg_type='', title=None, icon=discord.Embed.Empty, content=None, msg_colour=None, guild=None,
    title_url=discord.Embed.Empty, thumbnail='', image='', fields=None, footer=None, footer_icon=None, inline=False,
    subtitle=None, subtitle_url=None
):
    """
    Helper for generating a formatted embed.

    Types available:
    error, warning, info, success, help.
    """

    embed_types = {
        'error': {
            'icon': 'https://i.imgur.com/juhq2uJ.png',
            'colour': 'red'
        },
        'warning': {
            'icon': 'https://i.imgur.com/4JuaNt9.png',
            'colour': 'gold'
        },
        'info': {
            'icon': 'https://i.imgur.com/wzryVaS.png',
            'colour': 'blue'
        },
        'success': {
            'icon': 'https://i.imgur.com/ZTKc3mr.png',
            'colour': 'green'
        },
        'help': {
            'icon': 'https://i.imgur.com/kTTIZzR.png',
            'colour': 'blue'
        }
    }

    if msg_type in embed_types.keys():
        msg_colour = embed_types[msg_type]['colour']
        icon = embed_types[msg_type]['icon']

    if guild and not msg_colour:
        msg_colour = colour(guild)
    else:
        if not isinstance(msg_colour, discord.Colour):
            msg_colour = colour(msg_colour)

    embed = discord.Embed(description=content, colour=msg_colour, title=subtitle, url=subtitle_url)

    if title:
        embed.set_author(name=title, icon_url=icon, url=title_url)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if image:
        embed.set_image(url=image)

    fields = fields or {}
    for key, value in fields.items():
        ilf = inline
        if not isinstance(value, str):
            ilf = value[0]
            value = value[1]
        embed.add_field(name=key, value=value, inline=ilf)

    if footer:
        footer = {'text': footer}

        if footer_icon:
            footer['icon_url'] = footer_icon

        embed.set_footer(**footer)
    return embed


def bold(msg: str):
    """Format to bold markdown text"""
    return f'**{msg}**'


def italics(msg: str):
    """Format to italics markdown text"""
    return f'*{msg}*'


def bolditalics(msg: str):
    """Format to bold italics markdown text"""
    return f'***{msg}***'


def code(msg: str):
    """Format to markdown code block"""
    return f'```{msg}```'


def pycode(msg: str):
    """Format to code block with python code highlighting"""
    return f'```py\n{msg}```'


def ilcode(msg: str):
    """Format to inline markdown code"""
    return f'`{msg}`'


def convert_to_bool(argument):
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False
    else:
        return None


def bitround(x):
    return max(min(1 << int(x).bit_length() - 1, 1024), 16)
