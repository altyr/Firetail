import inspect
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import better_exceptions

import firetail

better_exceptions.hook()

LOG_PATH = Path(Path(inspect.getfile(firetail)).parent, 'logs')
LOG_PATH.mkdir(exist_ok=True)

LOG_FORMAT = logging.Formatter(
    '%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: %(message)s',
    datefmt="[%Y-%m-%d %H:%M:%S]"
)


def create_fh(name: str):
    """Create a logging filehandler based on given file path."""

    fh = RotatingFileHandler(
        filename=Path(LOG_PATH, f"{name}.log"),
        encoding='utf-8', mode='a',
        maxBytes=400000,
        backupCount=20,
    )
    fh.setFormatter(LOG_FORMAT)
    return fh


def init_logger(debug_flag=False):

    logging.getLogger().setLevel(logging.DEBUG)

    discord_log = logging.getLogger("discord")
    discord_log.addHandler(create_fh('discord'))

    firetail_log = logging.getLogger("firetail")
    firetail_log.addHandler(create_fh('firetail'))

    if debug_flag:
        discord_log.setLevel(logging.INFO)
        firetail_log.setLevel(logging.DEBUG)
    else:
        discord_log.setLevel(logging.ERROR)
        firetail_log.setLevel(logging.WARNING)

    firetail_log.addHandler(logging.StreamHandler())

    return firetail_log
