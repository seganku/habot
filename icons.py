from config import MDI_SVG_URL, MDI_PNG_DIR
import requests
import cairosvg
from pathlib import Path
from PIL import Image
from config import MDI_PNG_DIR

def get_icon_path(icon: str) -> Path | None:
    if not icon or not icon.startswith("mdi:"):
        return None

    slug = icon[4:]
    from pathlib import Path
    png_path = Path(MDI_PNG_DIR) / f"{slug}.png"

    if not png_path.exists():
        print(f"🔍 Fetching and caching icon: {slug}")
        svg_url = f"{MDI_SVG_URL}{slug}.svg"
        response = requests.get(svg_url)
        if response.status_code == 200:
            cairosvg.svg2png(bytestring=response.content, write_to=str(png_path))
            import os
            os.chmod(png_path, 0o644)
        else:
            print(f"❌ Failed to download: {svg_url} (Status: {response.status_code})")
            return None

    return png_path

# ------------------- Colorizing support (ON/OFF) -------------------
# Colors (hex) requested:
ON_HEX  = "#ffc107"   # amber for ON / synonyms
OFF_HEX = "#44739e"   # HA blue for OFF / synonyms

# Basic synonyms (covers common HA states and binary_sensor semantics)
_ON_LIKE  = {
    "on","open","detected","home","present","occupied","running","heat","cool",
    "charging","wet","motion","moving","armed","unsafe","problem","sound","vibration"
}
_OFF_LIKE = {
    "off","closed","clear","away","not_home","idle","dry","no_motion","still",
    "disarmed","safe","paused","standby"
}

def classify_on_off(device_class: str | None, state: str | None) -> str | None:
    """Return 'on', 'off', or None if unknown."""
    if state is None:
        return None
    s = str(state).lower().strip()
    if s in _ON_LIKE:
        return "on"
    if s in _OFF_LIKE:
        return "off"
    # Device-class specific nudges
    if device_class in {"door","window","garage_door","opening"}:
        return "on" if s == "open" else ("off" if s == "closed" else None)
    if device_class in {"presence","occupancy"}:
        return "on" if s in {"home","present","occupied","on"} else ("off" if s in {"away","not_home","off"} else None)
    return None

def _parse_hex_rgb(hex_color: str) -> tuple[int,int,int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

def get_colored_icon_path(icon: str, device_class: str | None, state: str | None) -> Path | None:
    """
    Return a cached, colorized PNG path for the given mdi: icon based on the *state*.
    Falls back to OFF_HEX when classification is unknown.
    """
    if not icon or not icon.startswith("mdi:"):
        return None
    slug = icon[4:]
    base_path = get_icon_path(icon)  # existing function ensures base PNG exists (monochrome)
    if not base_path or not Path(base_path).exists():
        return None

    onoff = classify_on_off(device_class, state) or "off"
    hex_color = ON_HEX if onoff == "on" else OFF_HEX

    out_dir = Path(MDI_PNG_DIR) / "colored" / hex_color.lstrip("#")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.png"
    if out_path.exists():
        return out_path

    r,g,b = _parse_hex_rgb(hex_color)
    with Image.open(base_path).convert("RGBA") as im:
        alpha = im.split()[-1]  # keep source alpha
        solid = Image.new("RGBA", im.size, (r, g, b, 255))
        solid.putalpha(alpha)
        solid.save(out_path, format="PNG", optimize=True)
    return out_path
