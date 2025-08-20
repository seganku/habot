try:
    # Prefer new config knobs, but don't crash if not defined yet
    from config import HA_URL, HA_ACCESS_TOKEN, BRIGHTNESS_NOTIFICATIONS, BRIGHTNESS_MIN_PERCENT, BRIGHTNESS_MIN_DELTA
except Exception:
    from config import HA_URL, HA_ACCESS_TOKEN
    BRIGHTNESS_NOTIFICATIONS = True
    BRIGHTNESS_MIN_PERCENT = 5
    BRIGHTNESS_MIN_DELTA = 16
from utils import log
from db import get_watchers
from ha_api import fetch_entity_details, get_readable_state
from icons import get_colored_icon_path
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

    if v is None:
        return None
    try:
        return round(int(v) * 100 / 255)
    except Exception:
        return None

def _bri_to_pct(v):
    if v is None:
        return None
    try:
        return round(int(v) * 100 / 255)
    except Exception:
        return None

def _brightness_changed_enough(old_bri, new_bri):
    if old_bri is None or new_bri is None:
        return False
    try:
        delta = abs(int(new_bri) - int(old_bri))
    except Exception:
        return False
    if BRIGHTNESS_MIN_PERCENT is not None:
        return (delta * 100 / 255) >= BRIGHTNESS_MIN_PERCENT
    return delta >= (BRIGHTNESS_MIN_DELTA or 0)

async def notify_watchers(bot, entity_id, old_state, new_state, old_attrs=None, new_attrs=None):
    rows = get_watchers(entity_id)
    friendly_name, icon, current_state, device_class = await fetch_entity_details(entity_id)

    display_name = friendly_name or entity_id
    # Prepare optional attachment-based *colored* icon (tinted & cached per ON/OFF).
    icon_file = None
    embed = None
    if icon and icon.startswith("mdi:"):
        # Tint icon based on current *state* (on/off); not brightness level.
        colored_path = get_colored_icon_path(icon, device_class, new_state)
        if colored_path:
            icon_filename = colored_path.name  # e.g., washing-machine.png
            try:
                icon_file = nextcord.File(str(colored_path), filename=icon_filename)
                embed = nextcord.Embed()
                embed.set_thumbnail(url=f"attachment://{icon_filename}")
                # Optional: match embed color to icon tint (pull hex from parent dir)
                try:
                    tint_hex = colored_path.parent.name  # 'ffc107' or '44739e'
                    embed.color = int(tint_hex, 16)
                except Exception:
                    pass
            except Exception as e:
                log(f"Failed to prepare colored icon for {entity_id}: {e}", color="YELLOW", icon="⚠️")

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
        log(f"icon_file: {icon_file}", level="debug")
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
        reason = ""

        # --- Rule evaluation ---
        if not rule_type or rule_type == "any":
            should_notify = (old_state != new_state)
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

        # NEW: brightness change notices (implicit, opt-in if entity is a watched light)
        # If user is watching this entity (any rule) and it’s a light, notify on brightness change over threshold.
        # This happens in addition to (not instead of) state rules, but only when enabled in config.
        if not should_notify and BRIGHTNESS_NOTIFICATIONS and entity_id.startswith("light."):
            ob = (old_attrs or {}).get("brightness") if isinstance(old_attrs, dict) else None
            nb = (new_attrs or {}).get("brightness") if isinstance(new_attrs, dict) else None
            if _brightness_changed_enough(ob, nb):
                ob_pct, nb_pct = _bri_to_pct(ob), _bri_to_pct(nb)
                # Construct a brightness-specific message
                delta_pct = (abs(int(nb) - int(ob)) * 100 / 255) if (ob is not None and nb is not None) else None
                direction = "↑" if (ob is not None and nb is not None and nb > ob) else ("↓" if (ob is not None and nb is not None and nb < ob) else "")
                reason = f"brightness change {direction} ({ob_pct}% → {nb_pct}%, Δ≈{round(delta_pct)}%)"
                should_notify = True

        if should_notify:
            message = custom_message or f"`{display_name}` changed to `{mapped_new_state}`"
            message = message.replace("{old_state}", str(mapped_old_state))\
                               .replace("{new_state}", str(mapped_new_state))\
                               .replace("{display_name}", display_name)\
                               .replace("{entity_id}", entity_id)\
                               .replace("{timestamp}", timestamp)

            try:
                # If we prepared an embed+attachment icon, put the message in the embed
                # so the thumbnail shows without needing external hosting.
                if embed and icon_file:
                    embed.description = message
                    await webhook.send(
                        username=display_name,
                        embed=embed,
                        file=icon_file
                    )
                else:
                    # No icon available — send a plain text message.
                    await webhook.send(
                        content=message,
                        username=display_name
                    )
            except Exception as e:
                log(f"Failed to send webhook for {entity_id}: {e}", color="YELLOW", icon="⚠️")
        else:
            log(
                f"Skipped notify: rule not matched for {entity_id} in {channel.guild.name} ({channel.guild.id}) #{channel.name} ({channel_id})",
                color="WHITE",
                icon="⚙️"
            )

