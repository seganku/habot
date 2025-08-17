import aiohttp
from config import HA_URL, HA_ACCESS_TOKEN
from db import get_cached_entity_details, cache_entity_details

DEVICE_CLASS_STATE_MAP = {
    "battery": {"name": "Battery", "state": {"off": "Normal", "on": "Low"}},
    "battery_charging": {"name": "Charging", "state": {"off": "Not charging", "on": "Charging"}},
    "carbon_monoxide": {"name": "Carbon monoxide", "state": {"off": "Clear", "on": "Detected"}},
    "cold": {"name": "Cold", "state": {"off": "Normal", "on": "Cold"}},
    "connectivity": {"name": "Connectivity", "state": {"off": "Disconnected", "on": "Connected"}},
    "door": {"name": "Door", "state": {"off": "Closed", "on": "Open"}},
    "garage_door": {"name": "Garage door", "state": {"off": "Closed", "on": "Open"}},
    "gas": {"name": "Gas", "state": {"off": "Clear", "on": "Detected"}},
    "heat": {"name": "Heat", "state": {"off": "Normal", "on": "Hot"}},
    "light": {"name": "Light", "state": {"off": "No light", "on": "Light detected"}},
    "lock": {"name": "Lock", "state": {"off": "Locked", "on": "Unlocked"}},
    "moisture": {"name": "Moisture", "state": {"off": "Dry", "on": "Wet"}},
    "motion": {"name": "Motion", "state": {"off": "Clear", "on": "Detected"}},
    "moving": {"name": "Moving", "state": {"off": "Not moving", "on": "Moving"}},
    "occupancy": {"name": "Occupancy", "state": {"off": "Clear", "on": "Detected"}},
    "opening": {"name": "Opening", "state": {"off": "Closed", "on": "Open"}},
    "plug": {"name": "Plug", "state": {"off": "Unplugged", "on": "Plugged in"}},
    "power": {"name": "Power", "state": {"off": "Off", "on": "On"}},
    "presence": {"name": "Presence", "state": {"off": "Away", "on": "Home"}},
    "problem": {"name": "Problem", "state": {"off": "OK", "on": "Problem"}},
    "running": {"name": "Running", "state": {"off": "Not running", "on": "Running"}},
    "safety": {"name": "Safety", "state": {"off": "Safe", "on": "Unsafe"}},
    "smoke": {"name": "Smoke", "state": {"off": "Clear", "on": "Detected"}},
    "sound": {"name": "Sound", "state": {"off": "Clear", "on": "Detected"}},
    "tamper": {"name": "Tamper", "state": {"off": "Clear", "on": "Tampering detected"}},
    "update": {"name": "Update", "state": {"off": "Up-to-date", "on": "Update available"}},
    "vibration": {"name": "Vibration", "state": {"off": "Clear", "on": "Detected"}},
    "window": {"name": "Window", "state": {"off": "Closed", "on": "Open"}}
}

_entity_cache = {}

def get_readable_state(device_class: str, state: str) -> str:
    try:
        state_map = DEVICE_CLASS_STATE_MAP.get(device_class, {}).get("state", {})
        return state_map.get(state, state)
    except Exception:
        return state

async def fetch_entity_details(entity_id: str):
    if entity_id in _entity_cache:
        return _entity_cache[entity_id]

    cached = get_cached_entity_details(entity_id)
    if cached:
        _entity_cache[entity_id] = cached
        return cached

    url = f"{HA_URL}/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {HA_ACCESS_TOKEN}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                attributes = data.get("attributes", {})
                result = (
                    attributes.get("friendly_name", None),
                    attributes.get("icon", None),
                    data.get("state", None),
                    attributes.get("device_class", None)
                )
                _entity_cache[entity_id] = result
                cache_entity_details(entity_id, *result)
                return result
            return (None, None, None, None)

async def fetch_all_entities():
    url = f"{HA_URL}/api/states"
    headers = {"Authorization": f"Bearer {HA_ACCESS_TOKEN}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {
                    item["entity_id"]: item["attributes"].get("friendly_name", "")
                    for item in data
                }
            return {}

async def call_ha_assist(text: str) -> str:
    url = f"{HA_URL}/api/services/conversation/process"
    headers = {
        "Authorization": f"Bearer {HA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"text": text}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list) and data:
                    return str(data[0])
                elif isinstance(data, dict):
                    return data.get("response", "No response from Assist.")
                else:
                    return "Unexpected response format from Assist."
            return f"Error {resp.status}: {await resp.text()}"

