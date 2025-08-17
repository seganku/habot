import asyncio
import aiohttp
from nextcord.ext import commands
import nextcord
from nextcord.utils import oauth_url
from nextcord import Permissions

from config import DISCORD_TOKEN, HA_URL, HA_ACCESS_TOKEN, DISCORD_APPLICATION_ID, GUILD_IDS, GUILD_MODE, DB_PATH
from utils import log
from notifier import notify_watchers, get_or_create_webhook
from ha_websocket import start_ha_listener
from colorama import Fore
from db import init_db, is_watching, add_watch, remove_watch, get_watched_entities, get_watchers
from commands import setup_slash_commands

intents = nextcord.Intents.default()
intents.message_content = True
init_db()

bot = commands.Bot(command_prefix="!", intents=intents)
setup_slash_commands(bot)

webhook_cache = {}

def get_invite_url() -> str:
    if not DISCORD_APPLICATION_ID:
        return "Missing DISCORD_APPLICATION_ID in .env"
    perms = Permissions()
    perms.send_messages = True
    perms.read_message_history = True
    perms.use_slash_commands = True
    perms.manage_webhooks = True
    perms.mention_everyone = True
    return oauth_url(
        client_id=DISCORD_APPLICATION_ID,
        permissions=perms,
        scopes=["bot", "applications.commands"]
    )

@bot.event
async def on_ready():
    log(f"Bot connected as {bot.user}", level="INFO", color=Fore.CYAN, icon="🤖")
    for g in bot.guilds:
        log(f"Connected to: {g.name} ({g.id})", level="INFO", color=Fore.CYAN)
    log("Invite your bot using this URL:", level="INFO", color=Fore.GREEN)
    log(get_invite_url(), level="INFO")
    bot.loop.create_task(start_ha_listener(bot))

bot.run(DISCORD_TOKEN)

