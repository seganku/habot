from config import MDI_SVG_URL, MDI_PNG_DIR
import requests
import cairosvg
from pathlib import Path

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

