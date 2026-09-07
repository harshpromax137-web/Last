"""
Generate a sample /outfit-image preview using fake player data.

This only touches reference_renderer.render_reference_outfit() - the pure
image-compositing function that takes plain data/PIL images as arguments.
It never logs in, calls Garena's servers, or touches proto/AES - it's just
built-in sample data plus (optionally) a couple of public image fetches for
the avatar/character/outfit art, so you can see the layout without needing
a real UID.

Run it from inside the merged-freefire-api folder:

    python make_sample_outfit_image.py

Output: sample_outfit_preview.png in the same folder.
"""

from __future__ import annotations

import asyncio
import io
import os

import httpx
from PIL import Image

from reference_renderer import render_reference_outfit

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(ROOT, "sample_outfit_preview.png")

# --- Sample player data -----------------------------------------------------
# Shaped like the real API's player_data dict (basicInfo / profileInfo /
# clanBasicInfo), but every value here is made up.
SAMPLE_PLAYER_DATA = {
    "basicInfo": {
        "nickname": "ExamplePlayer",
        "accountName": "ExamplePlayer",
        "level": 70,
        "exp": 2896658,
        "likes": 2345,
        "headPic": "102000015",  # profile avatar image id
    },
    "profileInfo": {
        "avatarId": "102000015",  # full-body character image id
    },
    "clanBasicInfo": {
        "clanName": "SampleClan",
    },
}

SAMPLE_UID = "102000015"
SAMPLE_MODE = "br"

# Made-up stats - keys match what reference_renderer.py looks for.
SAMPLE_STATS_DATA = {
    "matchesplayed": 512,
    "kills": 1830,
    "headshots": 402,
    "winrate": 18,
    "kdratio": 3.6,
}

# A few sample outfit item ids to *try* fetching art for (purely cosmetic -
# these are just public icon lookups, not account data). Any that fail to
# load are skipped and that hex slot is simply left empty, same as the real
# endpoint does when a slot has no equipped item.
SAMPLE_OUTFIT_ITEM_IDS = [
    "203000004",
    "203000021",
    "204000008",
    None,
    None,
    None,
    None,
    None,
]

# Local sample avatar shipped in this project - used instead of a network
# fetch when present, so the script still produces useful output offline.
LOCAL_SAMPLE_AVATAR = os.path.join(ROOT, "sample_avatar_102000015.png")


async def _fetch_image(client: httpx.AsyncClient, url: str) -> Image.Image | None:
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code == 200 and response.content:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except (httpx.HTTPError, OSError):
        pass
    return None


async def _fetch_outfit_item(client: httpx.AsyncClient, item_id: str | None) -> Image.Image | None:
    if not item_id:
        return None
    # Same two public icon sources the live app tries, in order.
    sources = (
        f"https://iconapi.wasmer.app/{item_id}",
        f"https://raw.githubusercontent.com/danger738/danger-item-library/main/PNG/{item_id}.png",
    )
    for url in sources:
        image = await _fetch_image(client, url)
        if image is not None:
            return image
    return None


async def _fetch_character_image(client: httpx.AsyncClient, avatar_id: str | None) -> Image.Image | None:
    if not avatar_id:
        return None
    url = f"https://raw.githubusercontent.com/harshpromax137-web/Anime-PNG/main/{avatar_id}.png"
    return await _fetch_image(client, url)


def _load_local_avatar() -> Image.Image | None:
    if os.path.exists(LOCAL_SAMPLE_AVATAR):
        try:
            return Image.open(LOCAL_SAMPLE_AVATAR).convert("RGBA")
        except OSError:
            return None
    return None


async def build_sample_image() -> bytes:
    async with httpx.AsyncClient() as client:
        outfit_images, character_image = await asyncio.gather(
            asyncio.gather(*(_fetch_outfit_item(client, item_id) for item_id in SAMPLE_OUTFIT_ITEM_IDS)),
            _fetch_character_image(client, SAMPLE_PLAYER_DATA["profileInfo"]["avatarId"]),
        )

    profile_avatar_image = _load_local_avatar()

    return render_reference_outfit(
        root=ROOT,
        player_data=SAMPLE_PLAYER_DATA,
        outfit_images=list(outfit_images),
        profile_avatar_image=profile_avatar_image,
        character_image=character_image,
        stats_data=SAMPLE_STATS_DATA,
        uid=SAMPLE_UID,
        mode=SAMPLE_MODE,
    )


def main() -> None:
    png_bytes = asyncio.run(build_sample_image())
    with open(OUTPUT_PATH, "wb") as f:
        f.write(png_bytes)
    print(f"Wrote {len(png_bytes)} bytes to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
