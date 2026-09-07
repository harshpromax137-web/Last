
import io
import os
import re
import asyncio
import secrets
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageChops, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor
from info_service import get_account_information, refresh_tokens
from stats_service import fetch_both_stats_async, fetch_stats_async, search_accounts_async
from reference_renderer import render_reference_outfit

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()
    process_pool.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INFO_API_URL = "/api/accinfo"
FONT_FILE = "arial_unicode_bold.otf"
FONT_CHEROKEE = "NotoSansCherokee.ttf"
API_PREFIX = "/api"
OUTFIT_BACKGROUNDS = (
    "outfit-background-1.webp",
    "outfit-background-2.webp",
    "outfit-background-3.webp",
    "outfit-background-4.png",
)
OUTFIT_LAYOUTS = {
    # Coordinates are calibrated in the final 1024x576 output space.  The
    # backgrounds contain irregular frame/ring shapes, so each background
    # has its own safe maximum artwork size rather than one universal square.
    "outfit-background-1.webp": {
        # Cyber scene: three frame pairs, with the left pair partly hidden
        # behind the scene artwork but still available for outfit icons.
        "slots": (
            (278, 110),
            (796, 110),
            (270, 280),
            (803, 280),
            (217, 457),
            (804, 457),
        ),
        "item_size": 76,
        "shape": "hexagon",
        "shape_inset": 6,
    },
    "outfit-background-2.webp": {
        "slots": (
            (656, 82),
            (742, 111),
            (833, 166),
            (886, 234),
            (920, 314),
            (915, 403),
            (925, 480),
        ),
        "item_size": 72,
        "shape": "ellipse",
        "shape_inset": 4,
    },
    "outfit-background-3.webp": {
        "slots": (
            (612, 110),
            (705, 112),
            (781, 155),
            (852, 215),
            (914, 276),
            (950, 354),
            (954, 443),
        ),
        "item_size": 72,
        "shape": "octagon",
        "shape_inset": 6,
    },
    "outfit-background-4.png": {
        # New neon banner. Source coordinates were supplied on a 1000x1000
        # normalized grid and converted to the API's 1024x576 output space.
        "slots": (
            (96, 56),
            (96, 142),
            (96, 226),
            (96, 316),
            (96, 404),
            (96, 492),
            (96, 470),
        ),
        "item_size": 72,
        "shape": "hexagon",
        "shape_inset": 6,
    },
}
OUTFIT_PREFIX_ORDER = ("211", "214", "211", "203", "204", "205", "203")

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=4)

def load_unicode_font(size, font_file=FONT_FILE):
    try:
        font_path = os.path.join(os.path.dirname(__file__), font_file)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) == "0" or item_id is None:
        return None

    item_id = str(item_id)
    url = (
        "https://raw.githubusercontent.com/danger738/"
        f"danger-item-library/main/PNG/{item_id}.png"
    )

    try:
        resp = await client.get(url)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except httpx.HTTPError:
        pass

    return None

def bytes_to_image(img_bytes):
    if img_bytes:
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    return Image.new('RGBA', (100, 100), (0, 0, 0, 0))


def fit_item_to_frame(
    image: Image.Image,
    frame_size: int,
    shape: str,
    shape_inset: int,
) -> Image.Image:
    """Fit an item inside a frame and clip it to the frame's inner shape."""
    alpha_bbox = image.getchannel("A").getbbox()
    if not alpha_bbox:
        return Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))

    image = image.crop(alpha_bbox)
    available_size = max(1, frame_size - shape_inset * 2)
    image.thumbnail((available_size, available_size), Image.LANCZOS)

    fitted = Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))
    fitted.paste(
        image,
        (
            (frame_size - image.width) // 2,
            (frame_size - image.height) // 2,
        ),
        image,
    )

    mask = Image.new("L", (frame_size, frame_size), 0)
    draw = ImageDraw.Draw(mask)
    left = shape_inset
    top = shape_inset
    right = frame_size - shape_inset - 1
    bottom = frame_size - shape_inset - 1

    if shape == "ellipse":
        draw.ellipse((left, top, right, bottom), fill=255)
    elif shape == "hexagon":
        cut = max(4, (right - left + 1) // 4)
        draw.polygon(
            (
                (left + cut, top),
                (right - cut, top),
                (right, (top + bottom) // 2),
                (right - cut, bottom),
                (left + cut, bottom),
                (left, (top + bottom) // 2),
            ),
            fill=255,
        )
    else:
        cut = max(4, (right - left + 1) // 4)
        draw.polygon(
            (
                (left + cut, top),
                (right - cut, top),
                (right, top + cut),
                (right, bottom - cut),
                (right - cut, bottom),
                (left + cut, bottom),
                (left, bottom - cut),
                (left, top + cut),
            ),
            fill=255,
        )

    fitted.putalpha(ImageChops.multiply(fitted.getchannel("A"), mask))
    return fitted

def process_banner_image(data, avatar_bytes, banner_bytes, pin_bytes):
    avatar_img = bytes_to_image(avatar_bytes)
    banner_img = bytes_to_image(banner_bytes)
    pin_img = bytes_to_image(pin_bytes)

    level = str(data.get("AccountLevel", "Not Found"))
    name = data.get("AccountName", "Not Found")
    guild = data.get("GuildName", "Not Found")

    TARGET_HEIGHT = 400 
    avatar_img = avatar_img.resize((TARGET_HEIGHT, TARGET_HEIGHT), Image.LANCZOS)
    
    b_w, b_h = banner_img.size
    if b_w > 50 and b_h > 50:
        banner_img = banner_img.rotate(3, resample=Image.BICUBIC, expand=True)
        b_w, b_h = banner_img.size
        
        crop_top, crop_bottom, crop_sides = 0.23, 0.32, 0.17
        left, top = b_w * crop_sides, b_h * crop_top
        right, bottom = b_w * (1 - crop_sides), b_h * (1 - crop_bottom)
        banner_img = banner_img.crop((left, top, right, bottom))

    b_w, b_h = banner_img.size
    if b_h > 0:
        new_banner_w = int(TARGET_HEIGHT * (b_w / b_h) * 2.0)
        banner_img = banner_img.resize((new_banner_w, TARGET_HEIGHT), Image.LANCZOS)
    else:
        banner_img = Image.new("RGBA", (800, 400), (50, 50, 50))

    final_w = TARGET_HEIGHT + new_banner_w
    final_h = TARGET_HEIGHT
    combined = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    combined.paste(avatar_img, (0, 0))
    combined.paste(banner_img, (TARGET_HEIGHT, 0))
    
    draw = ImageDraw.Draw(combined)
    
    font_large = load_unicode_font(125) 
    font_large_cherokee = load_unicode_font(125, FONT_CHEROKEE)
    font_small = load_unicode_font(95) 
    font_small_cherokee = load_unicode_font(95, FONT_CHEROKEE)
    font_level = load_unicode_font(50)

    text_x = TARGET_HEIGHT + 40 
    text_y = 40 
    
    def is_cherokee(char):
        code = ord(char)
        return (0x13A0 <= code <= 0x13FF) or (0xAB70 <= code <= 0xABBF)

    def draw_text_with_stroke(x, y, text, font_main, font_fallback, size):
        current_x = x
        for char in text:
            font = font_fallback if is_cherokee(char) else font_main
            
            # Draw stroke
            for dx in range(-size, size + 1):
                for dy in range(-size, size + 1):
                    draw.text((current_x + dx, y + dy), char, font=font, fill=stroke_col)
            
            # Draw text
            draw.text((current_x, y), char, font=font, fill=text_col)
            
            # Advance cursor
            char_width = font.getlength(char)
            current_x += char_width

    stroke_col, text_col = "black", "white"
    draw_text_with_stroke(text_x + 25, text_y, name, font_large, font_large_cherokee, 4)
    draw_text_with_stroke(text_x + 25, text_y + 200, guild, font_small, font_small_cherokee, 3)

    if pin_bytes:
        pin_size = 130 
        pin_img = pin_img.resize((pin_size, pin_size), Image.LANCZOS)
        combined.paste(pin_img, (0, TARGET_HEIGHT - pin_size), pin_img)

    level_txt = f"Lvl.{level}"
    try:
        bbox = draw.textbbox((0, 0), level_txt, font=font_level)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        text_w, text_h = len(level_txt) * 20, 40

    px, py = 25, 16
    box_x = final_w - (text_w + px * 2)
    box_y = final_h - (text_h + py * 2)
    
    draw.rectangle([box_x, box_y, final_w, final_h], fill="black")
    draw.text((box_x + px, box_y + py - 6), level_txt, font=font_level, fill="white")

    img_io = io.BytesIO()
    combined.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

@app.get("/")
@app.get("/api")
@app.get("/api/")
async def home():
    return {"message": "⚡ Ultra Fast Banner API Running",
           "Fix By": "@h4rsh_007",
           "Telegram": "@h4rsh_007",
           "Authentication": "No API key required",
           "Info Endpoint": f"{API_PREFIX}/accinfo?uid={{uid}}",
           "Normal Info Endpoint": f"{API_PREFIX}/info?uid={{uid}}",
           "Stats Endpoint": f"{API_PREFIX}/stats?uid={{uid}}&mode=br&matchmode=CAREER",
           "Search Endpoint": f"{API_PREFIX}/search?name={{name}}",
           "Api Endpoint": f"{API_PREFIX}/banner-image?uid={{uid}}",
           "Outfit Endpoint": f"{API_PREFIX}/outfit-image?uid={{uid}}&region={{region}}",
           "Note": "MADE BY @h4rsh_007 "
    }

@app.get("/api/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/accinfo")
@app.get("/api/accinfo")
async def get_info(uid: str, region: str | None = None, matchmode: str = "CAREER"):
    """Return normal profile information together with BR and CS statistics."""
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")
    try:
        profile = await get_account_information(uid, region)
        if profile is None:
            raise HTTPException(status_code=404, detail="UID not found in any region")
        stats = await fetch_both_stats_async(uid, region, matchmode)
        return {
            "profile": profile,
            "stats": stats,
            "metadata": {
                "uid": uid,
                "region": (region or "auto").upper(),
                "matchmode": matchmode.upper(),
            },
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Combined lookup failed: {exc}") from exc


@app.get("/info")
@app.get("/api/info")
async def info_alias(uid: str, region: str | None = None):
    """Compatibility route for normal profile information only."""
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")
    try:
        data = await get_account_information(uid, region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=404, detail="UID not found in any region")
    return data


@app.get("/stats")
@app.get("/api/stats")
async def stats_endpoint(
    uid: str,
    region: str | None = None,
    mode: str = "br",
    matchmode: str = "CAREER",
):
    try:
        return await fetch_stats_async(uid, region, mode, matchmode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stats lookup failed: {exc}") from exc


@app.get("/search")
@app.get("/api/search")
async def search_endpoint(name: str, region: str | None = None):
    try:
        return await search_accounts_async(name, region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc

@app.api_route("/refresh", methods=["GET", "POST"])
@app.api_route("/api/refresh", methods=["GET", "POST"])
async def refresh():
    try:
        await refresh_tokens()
        return {"message": "Tokens refreshed for all regions."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {exc}") from exc

@app.get("/banner-image")
@app.get("/api/banner-image")
async def get_banner(uid: str, region: str | None = None):
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")

    try:
        data = await get_account_information(uid, region)
        if data is None:
            raise HTTPException(status_code=404, detail="UID not found in any region")

        basic_info = data.get("basicInfo", {})
        profile_info = data.get("profileInfo", {})
        clan_info = data.get("clanBasicInfo", {})
        avatar_id = basic_info.get("headPic") or profile_info.get("avatarId")
        banner_id = basic_info.get("bannerId")
        pin_id = basic_info.get("title") or basic_info.get("pinId")

        avatar_task = fetch_image_bytes(avatar_id)
        banner_task = fetch_image_bytes(banner_id)
        pin_task = fetch_image_bytes(pin_id)

        results = await asyncio.gather(avatar_task, banner_task, pin_task)
        avatar_bytes, banner_bytes, pin_bytes = results[0], results[1], results[2]

        loop = asyncio.get_event_loop()
        banner_data = {
            "AccountLevel": basic_info.get("level", "Not Found"),
            "AccountName": basic_info.get("nickname", "Not Found"),
            "GuildName": clan_info.get("clanName", "Not Found")
        }
        
        img_io = await loop.run_in_executor(
            process_pool, 
            process_banner_image, 
            banner_data, avatar_bytes, banner_bytes, pin_bytes
        )
        
        return Response(content=img_io.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=300"})

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_outfit_image(item_id: str):
    if not item_id or str(item_id) == "0":
        return None
    sources = (
        f"https://iconapi.wasmer.app/{item_id}",
        (
            "https://raw.githubusercontent.com/danger738/"
            f"danger-item-library/main/PNG/{item_id}.png"
        ),
    )
    for url in sources:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200 and response.content:
                return Image.open(io.BytesIO(response.content)).convert("RGBA")
        except (httpx.HTTPError, OSError):
            continue
    return None


async def fetch_character_image(avatar_id: str | int | None):
    """Fetch the full-body character PNG keyed by profileInfo.avatarId."""
    if not avatar_id or str(avatar_id) == "0":
        return None
    url = f"https://raw.githubusercontent.com/harshpromax137-web/Anime-PNG/main/{avatar_id}.png"
    try:
        response = await client.get(url, timeout=15.0)
        if response.status_code == 200 and response.content:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except (httpx.HTTPError, OSError):
        pass
    return None


def _iter_item_ids(value):
    """Yield numeric item IDs from either repeated or scalar profile fields."""
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_item_ids(item)
        return
    if isinstance(value, dict):
        for key in ("itemId", "itemID", "id", "clothes"):
            if key in value:
                yield from _iter_item_ids(value[key])
        return

    item_id = str(value).strip()
    if item_id and item_id != "0" and re.fullmatch(r"\d+", item_id):
        yield item_id


def select_equipped_outfit_ids(profile_info: dict) -> list[str]:
    """Collect all equipped clothing IDs without including equipped skills."""
    all_ids = []
    for field in (
        "clothes",
        "equippedClothes",
        "top",
        "bottom",
        "mask",
        "facepaint",
        "shoes",
    ):
        all_ids.extend(_iter_item_ids(profile_info.get(field)))

    unique_ids = list(dict.fromkeys(all_ids))
    selected_ids = []
    used_ids = set()

    # Keep the game's conventional category order for the seven frame slots.
    # Some profiles have two items with the same prefix, so the sequence
    # intentionally includes 211 and 203 twice.
    for prefix in OUTFIT_PREFIX_ORDER:
        matched = next(
            (
                item_id
                for item_id in unique_ids
                if item_id.startswith(prefix) and item_id not in used_ids
            ),
            None,
        )
        if matched:
            selected_ids.append(matched)
            used_ids.add(matched)

    # Preserve any valid clothing IDs from a newer profile schema as well.
    # They are still equipped items and should not disappear just because
    # their prefix is not in the older category list.
    selected_ids.extend(item_id for item_id in unique_ids if item_id not in used_ids)
    return selected_ids

@app.get("/outfit-image")
@app.get("/api/outfit-image")
async def outfit_image(
    uid: str,
    region: str | None = None,
    mode: str = "br",
    matchmode: str = "CAREER",
):
    """Render the supplied reference layout with live profile, outfit, and stats data."""
    if not uid:
        raise HTTPException(status_code=400, detail="Missing uid parameter")
    if mode.lower() not in {"br", "cs"}:
        raise HTTPException(status_code=400, detail="mode must be br or cs")

    player_data = await get_account_information(uid, region)
    if player_data is None:
        raise HTTPException(status_code=404, detail="Failed to fetch player info")

    profile_info = player_data.get("profileInfo", {})
    basic_info = player_data.get("basicInfo", {})
    profile_avatar_id = basic_info.get("headPic")
    character_id = profile_info.get("avatarId")
    # Reserve the final shape for the first weapon skin only. Any additional
    # weaponSkinShows entries are intentionally ignored.
    selected_ids = select_equipped_outfit_ids(profile_info)[:7]
    first_weapon_skin = next(_iter_item_ids(basic_info.get("weaponSkinShows")), None)
    if first_weapon_skin:
        selected_ids.append(first_weapon_skin)

    outfit_images, profile_avatar_image, character_image = await asyncio.gather(
        asyncio.gather(*(fetch_outfit_image(item_id) for item_id in selected_ids)),
        fetch_outfit_image(profile_avatar_id),
        fetch_character_image(character_id),
    )
    try:
        stats_bundle = await fetch_stats_async(uid, region, mode.lower(), matchmode.upper())
    except Exception as exc:
        stats_bundle = {"error": str(exc)}

    output_bytes = render_reference_outfit(
        os.path.dirname(__file__),
        player_data,
        list(outfit_images),
        profile_avatar_image,
        character_image,
        stats_bundle.get("data", stats_bundle) if isinstance(stats_bundle, dict) else stats_bundle,
        uid,
        mode,
    )
    return Response(
        content=output_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
