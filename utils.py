import datetime
import os
from colorama import Fore, Style

LOG_LEVELS = {
    "DEBUG": Fore.MAGENTA,
    "INFO": Fore.CYAN,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED
}

def log(message, level="INFO", color=None, icon=None, plain=False):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level = level.upper()
    color_code = LOG_LEVELS.get(level, Fore.WHITE) if not plain else ""
    icon_part = f"{icon} " if icon and not plain else ""
    level_tag = f"[{level}]"
    log_msg = f"[{timestamp}] {level_tag} {icon_part}{message}"
    if plain:
        print(log_msg)
    else:
        print(f"{color_code}{log_msg}{Style.RESET_ALL}")

