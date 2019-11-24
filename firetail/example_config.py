# get token from https://discordapp.com/developers/applications/me
bot_token = ''

# bot settings
bot_prefix = ['!']
bot_master = 174764205927432192  # The discord ID of the owner
bot_coowners = [174764205927432192]  # The discord ID's of co-owners

# minimum required permissions
# see https://discordapi.com/permissions.html#2080762945
bot_permissions = 2080762945

# load extensions on start/restart
# alternatively load manually with !load after start.
preload_extensions = [
    'add_kills',            # Enables the addkills command
    'char_lookup',          # Get character info
    'dev',                  # Developer tools
    'eve_status',           # Get the status of the server and the player count
    'eve_time',             # Get the time in eve and around the world
    'group_lookup',         # Get corp/alliance info
    'jump_planner',         # Provides the shortcut for dotlan jump planning
    'jump_range',           # Provides the shortcut for dotlan jump range
    'killmails',            # Killmail posting extension
    'location_scout',       # Provides intel on systems/constellations/regions
    'price',                # Price check extension
    'sov_tracker',          # Provides real time info on sov fights

    # still in testing, use at your own risk

    # these require access tokens, please read the wiki for more information
    # 'tokens',               # Required if any in this group are enabled
    # 'eve_notifications',    # Shares notifications
    # 'eve_mail',             # Shares mail
    # 'jabber_relay'          # Completely broken, dont use me yet
    # 'rss',                  # RSS feed aggregator
    # 'eve_rpg'               # Text-based RPG game shib made

    # self-hosting only
    # 'fleet_up',             # Shares upcoming fleet-up operations
]

dm_only = False  # bot responses always sent via direct message
delete_commands = False  # user commands are deleted automatically

# Welcome message for new users
enable_welcome = False
welcome_string = (
    '**Welcome to the server!**\n\n'
    # 'To get roles, type !auth and use the returned auth system link.\n'
    'You can see available commands with `!help`'
)

# Auto Responses - Add more with the format 'trigger': 'Auto response'
# auto_responses = {
#     'auth': 'To get roles on this server visit: '
# }

# Killmail Settings - !addkills command has replaced this.
# killmail = {  # add or remove groups as needed, groups must have unique names.
#     'bigKills': True,  # Enable the sharing of eve wide big kills
#     'bigKillsValue': 1000000000,  # Big kill ISK threshold
#     'bigKillsChannel': '389827425581662226',  # Channel big kills are posted to
#     'killmailGroups': {
#         'group1': {  # feel free to add additional groups, be sure that each group has a unique name
#             'id': '498125261',  # Corp/Alliance ID
#             'channelId': '244061582496104448',  # Channel ID
#             'lossMails': True  # Show Loss Mails
#         }
#     }
# }

# Fleet-Up Settings
# add or remove groups as needed, groups must have unique names.
# fleetUp = {
#     'group_id': 12345,  # Fleet-up group ID
#     'user_id': 12345,  # User ID from your fleet-up api-key
#     'api_code': '',  # API Code from your fleet-up api-key
#     'auto_posting': True,  # Change to False if you don't want the bot to automatically post new and upcoming fleets
#     'channel_id': 12345,  # Channel to post fleet-up operations
# }

# RSS settings
# rss = {
#     'channelId': 12345,      # Default channel to which entries are sent
#     'updateInterval': 15,    # Time in minutes to wait between checks for new RSS content
#     'feeds': {
#         'eveNews': {
#             'uri': 'https://www.eveonline.com/rss/news',    # RSS feed URL
#             'channelId': 12345, # Channel to which feed should be sent. Override rss.channelId
#         },
#         'bbc': {
#             'uri': 'https://feeds.bbci.co.uk/news/world/rss.xml?edition=uk'
#         },
#     },
# }
