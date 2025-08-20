import aiohttp
import sqlite3
from config import HA_URL, HA_ACCESS_TOKEN, DB_PATH
from notifier import notify_watchers
from config import BRIGHTNESS_NOTIFICATIONS
from utils import log
from colorama import Fore

# --- Internal state for filtered subscriptions ---
_using_subscribe_entities = False
_last_state_by_eid = {}
_last_attrs_by_eid = {}

def _next_id():
    # Simple incremental id generator stored on the function object
    if not hasattr(_next_id, "i"):
        _next_id.i = 1
    _next_id.i += 1
    return _next_id.i

def _distinct_watched_entity_ids():
    """Return a de-duplicated list of all entity_ids being watched (across all channels)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT entity_id FROM watched_entities")
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows if r and r[0]]
    except Exception as e:
        log(f"Failed to read watched entity_ids from DB: {e}", level="WARN", color=Fore.YELLOW, icon="⚠️")
        return []

async def _try_subscribe_entities(ws, entity_ids):
    """Attempt to subscribe to a filtered entity stream. Returns True on success."""
    global _using_subscribe_entities
    if not entity_ids:
        return False
    sub_id = _next_id()
    msg = {"id": sub_id, "type": "subscribe_entities", "entity_ids": entity_ids}
    await ws.send_json(msg)

    # Expect either an ACK result or an immediate first event.
    ack = await ws.receive_json()
    if ack.get("type") == "result":
        ok = bool(ack.get("success"))
        _using_subscribe_entities = ok
        if ok:
            log(f"Subscribed to {len(entity_ids)} entities via subscribe_entities", level="INFO", color=Fore.CYAN, icon="🎯")
        return ok

    if ack.get("type") == "event" and "event" in ack:
        _using_subscribe_entities = True
        log(f"Subscribed to {len(entity_ids)} entities via subscribe_entities (stream started)", level="INFO", color=Fore.CYAN, icon="🎯")
        await _process_entities_event(ack)  # prime baseline
        return True

    return False

async def _subscribe_state_changed(ws):
    """Fallback to classic firehose of all state_changed events."""
    sub_id = _next_id()
    await ws.send_json({"id": sub_id, "type": "subscribe_events", "event_type": "state_changed"})
    log("Subscribed to all state_changed events (fallback)", level="INFO", color=Fore.WHITE, icon="🌊")

async def _process_entities_event(msg, bot=None):
    """Handle a subscribe_entities event message.

    Expected structure (compact diffs):
      event.a = { <eid>: { 's': 'on', 'a': {...}, ... }, ... }        # initial adds/snapshot
      event.c = { <eid>: { '+': { 's': 'off', 'a': {...} } } , ... }  # changes (plus/minus)
      event.r = [ '<eid>', ... ]                                      # removals
    We only care about 's' (state). We ignore attribute-only updates and baselines.
    """
    ev = msg.get("event", {}) or {}
    adds = ev.get("a") or {}
    changes = ev.get("c") or {}
    removes = ev.get("r") or []

    # Seed baseline without notifying
    for eid, payload in adds.items():
        if isinstance(payload, dict):
            _last_state_by_eid[eid] = payload.get("s")
            _last_attrs_by_eid[eid] = (payload.get("a") or {}).copy()

    # Apply changes; notify only on real flips
    for eid, diff in (changes or {}).items():
        if not isinstance(diff, dict):
            continue
        plus = diff.get("+") or {}
        new_state = plus.get("s")
        new_attrs = (plus.get("a") or {})
        if new_state is None:
            # Attribute-only change
            old_state = _last_state_by_eid.get(eid)
            old_attrs = _last_attrs_by_eid.get(eid, {})
            # Only forward attribute-only updates if brightness changed and feature is on
            if BRIGHTNESS_NOTIFICATIONS and "brightness" in new_attrs:
                if bot is not None:
                    await notify_watchers(bot, eid, old_state, old_state, old_attrs, {**old_attrs, **new_attrs})
            # Merge attrs baseline
            if old_attrs:
                _last_attrs_by_eid[eid] = {**old_attrs, **new_attrs}
            else:
                _last_attrs_by_eid[eid] = new_attrs.copy()
            continue
        old_state = _last_state_by_eid.get(eid)
        old_attrs = _last_attrs_by_eid.get(eid, {})
        if old_state != new_state:
            if bot is not None:
                await notify_watchers(bot, eid, old_state, new_state, old_attrs, {**old_attrs, **new_attrs})
        _last_state_by_eid[eid] = new_state
        # Merge attrs baseline even on state flips (brightness can update too)
        if new_attrs:
            _last_attrs_by_eid[eid] = {**old_attrs, **new_attrs}

    # Clean up removed
    for eid in removes:
        _last_state_by_eid.pop(eid, None)

async def start_ha_listener(bot):
    ws_url = f"{HA_URL.replace('http', 'ws')}/api/websocket"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            auth_msg = await ws.receive_json()
            log(f"HA: {auth_msg.get('type')}", level="INFO", color=Fore.MAGENTA)
            await ws.send_json({"type": "auth", "access_token": HA_ACCESS_TOKEN})
            while True:
                msg = await ws.receive_json()

                # Authentication handshake
                if msg.get("type") == "auth_ok":
                    log("Authenticated to HA WebSocket", level="INFO", color=Fore.GREEN, icon="🔐")

                    # Attempt filtered subscription to only watched entity_ids
                    entity_ids = _distinct_watched_entity_ids()
                    ok = await _try_subscribe_entities(ws, entity_ids)
                    if not ok:
                        await _subscribe_state_changed(ws)
                    continue

                # If using filtered stream, process compact entity messages
                if _using_subscribe_entities and msg.get("type") == "event" and "event" in msg and "data" not in msg.get("event", {}):
                    await _process_entities_event(msg, bot=bot)
                    continue

                # Fallback handler for classic state_changed events
                if msg.get("type") == "event":
                    event = msg.get("event") or {}
                    data = event.get("data") or {}

                    # Extract safely: old_state/new_state may be None or dicts
                    entity_id = data.get("entity_id")
                    old_state_obj = data.get("old_state") or {}
                    new_state_obj = data.get("new_state") or {}

                    old_state = old_state_obj.get("state") if isinstance(old_state_obj, dict) else None
                    new_state = new_state_obj.get("state") if isinstance(new_state_obj, dict) else None
                    old_attrs = old_state_obj.get("attributes") if isinstance(old_state_obj, dict) else {}
                    new_attrs = new_state_obj.get("attributes") if isinstance(new_state_obj, dict) else {}

                    # Real state flips
                    if entity_id and (old_state is not None) and (new_state is not None) and (old_state != new_state):
                        await notify_watchers(bot, entity_id, old_state, new_state, old_attrs, new_attrs)
                        continue
                    # Attribute-only: allow brightness flow-through for watched lights
                    if BRIGHTNESS_NOTIFICATIONS and entity_id and isinstance(new_attrs, dict):
                        if "brightness" in new_attrs:
                            await notify_watchers(bot, entity_id, old_state, new_state, old_attrs, new_attrs)

