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

# ---- Optional brightness notifications for light.* ----
# If True, any watched light entity will also notify when its 'brightness' attribute changes.
BRIGHTNESS_NOTIFICATIONS = True
# Minimum change to notify (pick ONE rule; percent takes precedence when set):
# As percent of full 0..255 scale (e.g., 5 means >= ~13 steps). Set to None to disable.
BRIGHTNESS_MIN_PERCENT = 5
# Absolute steps on the 0..255 scale (e.g., 16 ≈ ~6%). Used only if percent is None.
BRIGHTNESS_MIN_DELTA = 16

