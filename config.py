import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HA_URL = os.getenv("HA_URL")
HA_ACCESS_TOKEN = os.getenv("HA_ACCESS_TOKEN")
DISCORD_APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID")
RAW_GUILD_IDS = os.getenv("GUILD_IDS", "")

GUILD_IDS = [int(gid.strip()) for gid in RAW_GUILD_IDS.split(",") if gid.strip().isdigit()]
GUILD_MODE = bool(GUILD_IDS)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "watched_entities.db"

MDI_SVG_URL = os.getenv("MDI_SVG_URL", "https://cdn.materialdesignicons.com/6.5.95/svg/")
MDI_PNG_DIR = os.getenv("MDI_PNG_DIR", "/var/www/html/mdi-pngs/")
MDI_PNG_URL = os.getenv("MDI_PNG_URL", "https://ex1.us/mdi-pngs/")

