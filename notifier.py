from config import HA_URL, HA_ACCESS_TOKEN, MDI_PNG_URL
from utils import log
from db import get_watchers
from ha_api import fetch_entity_details, get_readable_state
from icons import get_icon_path
import nextcord
from nextcord.utils import get
from colorama import Fore
from datetime import datetime

async def get_or_create_webhook(channel: nextcord.TextChannel) -> nextcord.Webhook:
    if not hasattr(get_or_create_webhook, "cache"):
        get_or_create_webhook.cache = {}
    if channel.id in get_or_create_webhook.cache:
        return get_or_create_webhook.cache[channel.id]
    webhooks = await channel.webhooks()
    for wh in webhooks:
        if wh.user and wh.user.id == channel.guild.me.id:
            get_or_create_webhook.cache[channel.id] = wh
            return wh
    webhook = await channel.create_webhook(name="HA Bot")
    get_or_create_webhook.cache[channel.id] = webhook
    return webhook

async def notify_watchers(bot, entity_id, old_state, new_state):
    rows = get_watchers(entity_id)
    friendly_name, icon, current_state, device_class = await fetch_entity_details(entity_id)

    display_name = friendly_name or entity_id
    icon_url = None
    if icon and icon.startswith("mdi:"):
        icon_slug = icon[4:]
        icon_path = get_icon_path(icon)
        if icon_path and icon_path.exists():
            icon_url = f"{MDI_PNG_URL}{icon_slug}.png"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    mapped_old_state = get_readable_state(device_class, old_state)
    mapped_new_state = get_readable_state(device_class, new_state)

    for row in rows:
        user_id, channel_id = row[0], row[1]
        try:
            user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
        except Exception as e:
            log(f"Failed to fetch user {user_id}: {e}", color="YELLOW", icon="⚠️")
            user = None

        channel = bot.get_channel(int(channel_id))
        if not channel or not channel.guild:
            log(f"Could not find valid channel {channel_id} for user {user.display_name if user else user_id}", color="YELLOW", icon="⚠️")
            continue

        log(f"friendly_name: {friendly_name}", level="debug")
        log(f"icon: {icon}", level="debug")
        log(f"current_state: {current_state}", level="debug")
        log(f"device_class: {device_class}", level="debug")
        log(f"display_name: {display_name}", level="debug")
        log(f"icon_url: {icon_url}", level="debug")
        log(f"old_state: {old_state}", level="debug")
        log(f"new_state: {new_state}", level="debug")
        log(f"mapped_old_state: {mapped_old_state}", level="debug")
        log(f"mapped_new_state: {mapped_new_state}", level="debug")

        webhook = await get_or_create_webhook(channel)

        rule_type = row[2] if len(row) > 2 else None
        from_state = row[3] if len(row) > 3 else None
        to_state = row[4] if len(row) > 4 else None
        operator = row[5] if len(row) > 5 else None
        threshold = row[6] if len(row) > 6 else None
        custom_message = row[7] if len(row) > 7 else None
        log(f"rule_type: {rule_type}", level="debug")
        log(f"from_state: {from_state}", level="debug")
        log(f"to_state: {to_state}", level="debug")
        log(f"operator: {operator}", level="debug")
        log(f"threshold: {threshold}", level="debug")
        log(f"custom_message: {custom_message}", level="debug")

        should_notify = False

        if not rule_type or rule_type == "any":
            should_notify = True
        elif rule_type == "state_change":
            if (from_state == "any" or from_state == old_state) and (to_state == "any" or new_state == to_state):
                should_notify = True
        elif rule_type == "threshold":
            try:
                new_val = float(new_state)
                thresh_val = float(threshold)
                if operator == ">=" and new_val >= thresh_val:
                    should_notify = True
                elif operator == "<=" and new_val <= thresh_val:
                    should_notify = True
                elif operator == ">" and new_val > thresh_val:
                    should_notify = True
                elif operator == "<" and new_val < thresh_val:
                    should_notify = True
            except (ValueError, TypeError):
                log(f"Could not evaluate threshold for {entity_id}: {new_state}", color="YELLOW", icon="⚠️")

        if should_notify:
            message = custom_message or f"`{display_name}` changed to `{mapped_new_state}`"
            message = message.replace("{old_state}", str(mapped_old_state))\
                               .replace("{new_state}", str(mapped_new_state))\
                               .replace("{display_name}", display_name)\
                               .replace("{entity_id}", entity_id)\
                               .replace("{timestamp}", timestamp)

            try:
                await webhook.send(
                    content=message,
                    username=display_name,
                    avatar_url=icon_url
                )
                log(
                    f"Notified user {user.display_name if user else user_id} ({user_id}) in {channel.guild.name} ({channel.guild.id}) #{channel.name} ({channel_id})",
                    color="CYAN",
                    icon="📢"
                )
            except Exception as e:
                log(f"Failed to send webhook for {entity_id}: {e}", color="YELLOW", icon="⚠️")
        else:
            log(
                f"Skipped notify: rule not matched for {entity_id} in {channel.guild.name} ({channel.guild.id}) #{channel.name} ({channel_id})",
                color="WHITE",
                icon="⚙️"
            )

