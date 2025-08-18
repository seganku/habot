from nextcord import Interaction, SlashOption
from nextcord.ext import commands
from colorama import Fore

from ha_api import fetch_entity_details, call_ha_assist, fetch_all_entities
from db import is_watching, add_watch, remove_watch, get_watched_entities
from utils import log
import re

# ---- Entity resolver ---------------------------------------------------------
async def resolve_entity_id_or_prompt(interaction: Interaction, query: str):
    """
    Resolve a user-provided string (friendly name or entity_id) to a single entity_id.
    If 0 or >1 match, send a helpful reply and return None.
    """
    query = (query or "").strip()
    if not query:
        await interaction.response.send_message("You must specify an entity to watch.")
        return None

    # {entity_id: friendly_name}
    all_entities = await fetch_all_entities()

    # Fast path: exact entity_id present
    if "." in query and query in all_entities:
        return query

    ql = query.lower()

    # 1) Exact matches (by name or id), case-insensitive
    exact_name = [(eid, name) for eid, name in all_entities.items()
                  if (name or "").lower() == ql]
    exact_eid  = [(eid, all_entities[eid]) for eid in all_entities
                  if eid.lower() == ql]

    candidates = []
    seen = set()
    for pair in (exact_eid + exact_name):
        if pair[0] not in seen:
            candidates.append(pair)
            seen.add(pair[0])

    # 2) Fallback: substring match on friendly name
    if not candidates:
        for eid, name in all_entities.items():
            if name and ql in name.lower():
                if eid not in seen:
                    candidates.append((eid, name))
                    seen.add(eid)

    # Outcome handling
    if len(candidates) == 1:
        return candidates[0][0]

    if len(candidates) == 0:
        await interaction.response.send_message(
            f"No entity matched `{query}`. Try the exact entity_id (e.g., `sensor.front_load_washer`)."
        )
        return None

    # Too many — present a short list to choose from
    lines = "\n".join(f"- {name or '(no name)'} — `{eid}`" for eid, name in candidates[:20])
    await interaction.response.send_message(
        f"Multiple entities matched `{query}`. Please choose one of these exact `entity_id`s:\n{lines}"
    )
    return None

def setup_slash_commands(bot):
    from config import GUILD_IDS, GUILD_MODE

    @bot.slash_command(
        name="hassio",
        description="Interact with Home Assistant",
        guild_ids=GUILD_IDS if GUILD_MODE else None
    )
    async def hassio(interaction: Interaction, action: str = SlashOption(
        description="Command action",
        choices=["watch", "del", "list", "help", "search"],
        required=True
    ), entity_id: str = SlashOption(
        description="The entity ID (for watch/del)",
        required=False
    ),
    condition: str = SlashOption(
        description="Optional rule condition",
        required=False
    ),
    message: str = SlashOption(
        description="Custom message with {old_state} and {new_state} placeholders",
        required=False
    )):
        log(
            f"/hassio action:{action}"
            f"{f' entity_id:{entity_id}' if entity_id else ''}"
            f"{f' condition:{condition}' if condition else ''}"
            f"{f' message:{message}' if message else ''}",
            level="INFO", color=Fore.YELLOW, icon="🗘️"
        )

        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel.id)

        if action == "watch":
            if not entity_id:
                await interaction.response.send_message("You must specify an entity_id to watch.")
                return

            # Resolve friendly name -> entity_id (ensure exactly one match)
            resolved = await resolve_entity_id_or_prompt(interaction, entity_id)
            if not resolved:
                return
            entity_id = resolved

            # Parse condition
            from_state = to_state = rule_type = "any"
            operator = threshold = None

            # Fetch current state to validate against
            friendly_name, icon, current_state, device_class = await fetch_entity_details(entity_id)
            if friendly_name is None and current_state is None:
                await interaction.response.send_message(
                    f"Couldn’t read `{entity_id}` from Home Assistant. "
                    "Double-check the entity_id or try again."
                )
                return

            if condition:
                if "->" in condition:
                    from_state, to_state = [s.strip() for s in condition.split("->", 1)]
                    rule_type = "state_change"
                elif any(op in condition for op in [">=", "<=", "<", ">"]):
                    for op in [">=", "<=", ">", "<"]:
                        if op in condition:
                            parts = condition.split(op)
                            if len(parts) == 2:
                                operator = op
                                threshold = parts[1].strip()
                                rule_type = "threshold"
                                break

            # Validate against current state
            if rule_type == "state_change":
                if from_state and from_state != "any" and from_state != current_state and to_state and to_state != "any" and to_state != current_state:
                    await interaction.response.send_message(
                        f"Warning: current state is `{current_state}`, but you're watching for `{from_state} -> {to_state}`. Check for typos or state mismatch."
                    )
                    return

            elif rule_type == "threshold":
                try:
                    float(current_state)
                except (ValueError, TypeError):
                    await interaction.response.send_message(
                        f"Error: entity `{entity_id}` has current state `{current_state}` which is not numeric. Thresholds require numeric values."
                    )
                    return

            if is_watching(channel_id, entity_id, from_state, to_state, operator, threshold):
                await interaction.response.send_message(f"You're already watching `{entity_id}` with this condition in this channel.")
                return

            add_watch(user_id, entity_id, channel_id, rule_type, from_state, to_state, operator, threshold, message)
            await interaction.response.send_message(f"Started watching `{entity_id}` with rule type `{rule_type}`.")
            log(f"{interaction.user} started watching {entity_id}", level="INFO", color=Fore.BLUE, icon="👁️")

        elif action == "del":
            if not entity_id:
                await interaction.response.send_message("You must specify an ID to delete. Use /hassio list to get the ID.")
                return
            try:
                watch_id = int(entity_id)
            except ValueError:
                await interaction.response.send_message("Invalid ID format. Must be an integer.")
                return
            if remove_watch(watch_id):
                await interaction.response.send_message(f"Stopped watching ID `{watch_id}`.")
                log(f"{interaction.user} stopped watching ID {watch_id}", level="INFO", color=Fore.RED, icon="🔘")
            else:
                await interaction.response.send_message(f"No watch found with ID `{watch_id}`.")

        elif action == "list":
            rows = get_watched_entities(channel_id)
            if not rows:
                await interaction.response.send_message("You're not watching any entities.")
                return
            lines = []
            for id, eid, rule_type, from_state, to_state, operator, threshold, custom_message in rows:
                friendly, _, _, _ = await fetch_entity_details(eid)

                if rule_type == "state_change":
                    condition_desc = f"{from_state or '*'} → {to_state or '*'}"
                elif rule_type == "threshold":
                    condition_desc = f"{operator} {threshold}"
                elif rule_type == "any":
                    condition_desc = "any state change"
                else:
                    condition_desc = "(unknown rule)"

                suffix = f" — " + custom_message if custom_message else ""
                lines.append(f"- ID `{id}`: `{eid}` ({friendly or '(no name)'}) — `{condition_desc}`{suffix}")

            await interaction.response.send_message("You're watching:\n" + "\n".join(lines))

        elif action == "search":
            if not entity_id:
                await interaction.response.send_message("Please provide a search string." , ephemeral=True)
                return

            all_entities = await fetch_all_entities()
            matches = []
            seen_ids = set()
            query = entity_id.strip()
            words = query.split()

            def check_and_add(condition):
                for eid, name in all_entities.items():
                    if eid in seen_ids:
                        continue
                    if condition(name):
                        matches.append((eid, name))
                        seen_ids.add(eid)
                    if len(matches) >= 10:
                        return True
                return False

            checks = [
                lambda n: query in n,
                lambda n: query.lower() in n.lower(),
                lambda n: n.startswith(query),
                lambda n: n.lower().startswith(query.lower()),
                lambda n: query in n,
                lambda n: query.lower() in n.lower(),
                lambda n: re.search(".*".join(words), n),
                lambda n: re.search(".*".join(words), n, re.IGNORECASE),
                lambda n: all(w in n.split() for w in words),
                lambda n: all(w.lower() in n.lower() for w in words)
            ]

            for check in checks:
                if check_and_add(check):
                    break

            if not matches:
                await interaction.response.send_message("No matches found.", ephemeral=True)
            else:
                reply = "Top Matches:\n" + "\n".join([f"- `{eid}` — {name}" for eid, name in matches])
                await interaction.response.send_message(reply, ephemeral=True)

        elif action == "help":
            await interaction.response.send_message(
                "**Home Assistant Bot Usage:**\n"
                "`/hassio watch <entity_id> [condition] [message]` — Start watching an entity\n"
                "`/hassio del <watch_id>` — Stop watching a specific watch ID\n"
                "`/hassio list` — List all entities watched in this channel\n"
                "`/hassio search <string>` — Search available entity names\n"
                "`/hassio help` — Show this help message\n\n"
                "**Conditions:**\n"
                "`on -> off` — Watch for a specific state change\n"
                "`>= 37` — Watch for numeric threshold conditions\n"
                "`any` — Watch for any state change (default)\n\n"
                "**Message Template:**\n"
                "You can customize the notification message using these placeholders:\n"
                "`{old_state}`, `{new_state}`, `{display_name}`, `{entity_id}`, `{timestamp}`\n"
                "Example: `The {display_name} changed from {old_state} to {new_state} at {timestamp}`"
            )

        else:
            # This should not be hit unless a bad action somehow got through
            await interaction.response.send_message("Unknown action. Use /hassio help for valid commands.")

