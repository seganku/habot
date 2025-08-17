import aiohttp
from config import HA_URL, HA_ACCESS_TOKEN
from notifier import notify_watchers
from utils import log
from colorama import Fore

async def start_ha_listener(bot):
    headers = {"Authorization": f"Bearer {HA_ACCESS_TOKEN}"}
    ws_url = f"{HA_URL.replace('http', 'ws')}/api/websocket"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            auth_msg = await ws.receive_json()
            log(f"HA: {auth_msg.get('type')}", level="INFO", color=Fore.MAGENTA)
            await ws.send_json({"type": "auth", "access_token": HA_ACCESS_TOKEN})
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "auth_ok":
                    log("Authenticated to HA WebSocket", level="INFO", color=Fore.GREEN, icon="🔐")
                    await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
                elif msg.get("type") == "event":
                    event_data = msg.get("event", {}).get("data")
                    if not event_data:
                        continue  # Skip this event if data is missing or malformed

                    entity_id = event_data.get("entity_id")
                    new_state = event_data.get("new_state", {}).get("state")
                    old_state = event_data.get("old_state", {}).get("state")

                    if entity_id and new_state:
                        await notify_watchers(bot, entity_id, old_state, new_state)

