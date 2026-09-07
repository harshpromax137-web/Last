from __future__ import annotations

import io
import os
import re
import unicodedata
from functools import lru_cache
from typing import Any, Iterable

from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


_INVISIBLE_FILLERS = {
    "\uffa0", "\u3164", "\u115f", "\u1160",
    "\u200b", "\u200c", "\u200d", "\ufeff", "\u2800",
}


def _normalize_display_text(value: str) -> str:
    if not value:
        return value
    cleaned = "".join(" " if ch in _INVISIBLE_FILLERS else ch for ch in value)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or value


@lru_cache(maxsize=64)
def _font_codepoints(path: str) -> frozenset[int]:
    try:
        font = TTFont(path, lazy=True)
        codepoints: set[int] = set()
        for table in font["cmap"].tables:
            codepoints.update(table.cmap.keys())
        return frozenset(codepoints)
    except Exception:
        return frozenset()


def _font_supports(path: str, value: str) -> bool:
    codepoints = _font_codepoints(path)
    return bool(codepoints) and all(ord(ch) in codepoints for ch in value)


def _nickname_segments(root: str, value: str, size: int) -> list[tuple[str, ImageFont.ImageFont]]:
    """Return per-character fonts: GFF first, Unicode fallbacks when needed."""
    font_files = (
        "GFF-Latin-Regular.ttf",
        "NotoSansCJKsc-Regular.otf",
        "NotoSerifTibetan-Regular.ttf",
        "arial_unicode_bold.otf",
    )
    segments: list[tuple[str, ImageFont.ImageFont]] = []
    for ch in value:
        chosen = None
        for filename in font_files:
            path = os.path.join(root, filename)
            if os.path.exists(path) and _font_supports(path, ch):
                chosen = ImageFont.truetype(path, size)
                break
        segments.append((ch, chosen or _font(root, size)))
    return segments


def _draw_nickname(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: str,
    root: str,
    size: int = 18,
    fill: str = "#763F82",
) -> None:
    """Center a nickname while preserving Unicode characters and visual spacing."""
    segments = _nickname_segments(root, value, size)
    if not segments:
        return
    widths = [font.getlength(ch) for ch, font in segments]
    total_width = sum(widths)
    left, top, right, bottom = box
    x = left + max(0.0, ((right - left) - total_width) / 2)
    metrics = [font.getbbox(ch, anchor="ls") for ch, font in segments]
    min_top = min(bbox[1] for bbox in metrics)
    max_bottom = max(bbox[3] for bbox in metrics)
    baseline = top + ((bottom - top) - (max_bottom - min_top)) / 2 - min_top
    for (ch, font), width in zip(segments, widths):
        draw.text((x, baseline), ch, font=font, fill=fill, anchor="ls", stroke_width=1, stroke_fill="black")
        x += width


CANVAS_SIZE = (1331, 784)
REFERENCE_BACKGROUND = "new_background.png"
CS_BACKGROUND = "cs_background.jpg"

LEVEL_EXP_TABLE = {
    1: 0, 2: 48, 3: 202, 4: 544, 5: 1012, 6: 1844, 7: 2792, 8: 3800, 9: 4870, 10: 6004,
    11: 7192, 12: 8448, 13: 9760, 14: 11140, 15: 12566, 16: 14060, 17: 15610, 18: 17224, 19: 18902, 20: 20632,
    21: 22424, 22: 24278, 23: 26192, 24: 28166, 25: 30200, 26: 32294, 27: 34448, 28: 37804, 29: 41274, 30: 44870,
    31: 48582, 32: 53394, 33: 58566, 34: 64096, 35: 69994, 36: 76460, 37: 83506, 38: 91128, 39: 99322, 40: 108092,
    41: 120144, 42: 133266, 43: 147472, 44: 162760, 45: 179126, 46: 196572, 47: 215368, 48: 235516, 49: 257010, 50: 279860,
    51: 304056, 52: 348318, 53: 394982, 54: 444044, 55: 495508, 56: 549364, 57: 633756, 58: 721744, 59: 813336, 60: 908522,
    61: 1041438, 62: 1180352, 63: 1325266, 64: 1476184, 65: 1634300, 66: 1840946, 67: 2056594, 68: 2281242, 69: 2514880, 70: 2757530,
    71: 3059506, 72: 3372284, 73: 3699456, 74: 4041030, 75: 4397002, 76: 4829104, 77: 5282204, 78: 5756304, 79: 6251404, 80: 6767502,
    81: 7381324, 82: 8043154, 83: 8752982, 84: 9510808, 85: 10316638, 86: 11277190, 87: 12291748, 88: 13360304, 89: 14482858, 90: 15659418,
    91: 17026708, 92: 18453950, 93: 19941280, 94: 21488570, 95: 23095858, 96: 24763138, 97: 26490428, 98: 28277708, 99: 30124996, 100: 32032284,
}


def _level_progress_fraction(level: int, exp: int) -> float:
    floor = LEVEL_EXP_TABLE.get(level)
    ceiling = LEVEL_EXP_TABLE.get(level + 1)
    if floor is None or ceiling is None or ceiling <= floor:
        return 0.0
    fraction = (exp - floor) / (ceiling - floor)
    return max(0.0, min(1.0, fraction))


OUTFIT_SLOT_CENTERS = (
    (124, 145), (74, 239), (97, 350), (141, 456),
    # Fifth slot: upper-right hexagon center in the 1331x784 canvas.
    (796, 155), (846, 238), (824, 359), (777, 445),
)
OUTFIT_ITEM_SIZE = 58
CHARACTER_BOX = (180, 108, 680, 706)
PROFILE_AVATAR_BOX = (984, 87, 1072, 175)

# Measured from the approved reference image: nickname sits immediately to
# the right of the profile avatar, around API pixels x=1094..1160, y=120..134.
NAME_BOX = (1085, 108, 1175, 142)
# Top header strip between the Free Fire MAX logo and settings icon.
CLAN_BOX = (1085, 25, 1275, 75)

LEVEL_VALUE_BOX = (972, 190, 1005, 208)
UID_VALUE_BOX = (1213, 193, 1320, 208)
LIKE_BOX = (1263, 153, 1320, 175)
XP_BAR_BOX = (1011, 196, 1151, 206)

# Center of the statistics value column. Values are centered individually
# so short values such as the first "Matches Played" number do not hug the left edge.
STAT_VALUE_CENTER_X = 1230
STAT_VALUE_Y = (285, 321, 357, 393, 429)
CS_STAT_VALUE_Y = (285, 321, 357, 393, 429)
STAT_LABELS = ("Matches Played", "Kills", "Headshots", "Win Rate", "KD Ratio")

# Shared size for every purple value field (UID, Level, Likes, Stats) so they
# read as one consistent style. Each box still shrinks independently via
# _draw_centered's fit loop if its own content is too long to fit.
VALUE_FONT_SIZE = 18
VALUE_FONT_MIN_SIZE = 8


def _font(root: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the supplied Free Fire-style GFF Latin font first.

    The legacy bundled fonts remain as fallbacks for characters that the GFF
    family may not contain, so existing Unicode account names still render.
    """
    for filename in (
        "GFF-Latin-Regular.ttf",
        "GFF-Latin-Medium.ttf",
        "arial_unicode_bold.otf",
        "NotoSansCherokee.ttf",
    ):
        path = os.path.join(root, filename)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _first_value(value: Any, keys: Iterable[str]) -> Any:
    if not isinstance(value, dict):
        return None
    for key in keys:
        if key in value and value[key] not in (None, "", 0, "0"):
            return value[key]
    return None


def _recursive_value(value: Any, keys: set[str]) -> Any:
    normalized = {key.lower() for key in keys}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in normalized and child not in (None, ""):
                return child
            found = _recursive_value(child, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _recursive_value(child, keys)
            if found not in (None, ""):
                return found
    return None


def _text(data: Any, keys: set[str], fallback: str = "-") -> str:
    value = _recursive_value(data, keys)
    return fallback if value in (None, "") else str(value)


def _win_rate_text(stats: Any) -> str:
    """Calculate win rate when the stats response exposes wins and games played."""
    direct = _recursive_value(stats, {"winrate", "win_rate", "winpercentage"})
    if direct not in (None, ""):
        return str(direct)
    wins = _recursive_value(stats, {"wins", "win"})
    games = _recursive_value(stats, {"gamesplayed", "matchesplayed", "matches"})
    try:
        if wins not in (None, "") and games not in (None, "") and float(games) > 0:
            return f"{100.0 * float(wins) / float(games):.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return "-"


def _kd_text(stats: Any) -> str:
    """Return direct KD when supplied, otherwise calculate total kills/deaths."""
    direct = _recursive_value(stats, {"kdratio", "kd", "kdr", "killdeathratio"})
    if direct not in (None, ""):
        return str(direct)
    kills = deaths = 0
    found = False

    def walk(value: Any) -> None:
        nonlocal kills, deaths, found
        if isinstance(value, dict):
            if "kills" in value:
                nested_deaths = _recursive_value(value, {"deaths"})
                if nested_deaths not in (None, ""):
                    try:
                        kills += float(value["kills"])
                        deaths += float(nested_deaths)
                        found = True
                    except (TypeError, ValueError):
                        pass
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(stats)
    if not found or deaths <= 0:
        return "-"
    return f"{kills / deaths:.2f}".rstrip("0").rstrip(".")


def _fit_avatar(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    left, top, right, bottom = box
    return ImageOps.fit(image.convert("RGBA"), (right - left, bottom - top), method=Image.LANCZOS)


def _fit_character(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    left, top, right, bottom = box
    rgba = image.convert("RGBA")
    alpha_bbox = rgba.getchannel("A").getbbox()
    if alpha_bbox:
        rgba = rgba.crop(alpha_bbox)
    available = (right - left, bottom - top)
    rgba.thumbnail(available, Image.LANCZOS)
    layer = Image.new("RGBA", available, (0, 0, 0, 0))
    x = (available[0] - rgba.width) // 2
    y = (available[1] - rgba.height) // 2
    layer.alpha_composite(rgba, (x, y))
    return layer



def _hex_mask(size: int, inset: int = 3) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    left, top = inset, inset
    right, bottom = size - inset - 1, size - inset - 1
    cut = max(7, size // 4)
    draw.polygon(
        (
            (left + cut, top), (right - cut, top), (right, (top + bottom) // 2),
            (right - cut, bottom), (left + cut, bottom), (left, (top + bottom) // 2),
        ),
        fill=255,
    )
    return mask


def _draw_golden_slot_border(draw: ImageDraw.ImageDraw, center_x: int, center_y: int) -> None:
    """Draw a minimal golden border around one occupied outfit hexagon."""
    size = OUTFIT_ITEM_SIZE
    inset = 2
    left, top = center_x - size // 2 + inset, center_y - size // 2 + inset
    right, bottom = center_x + size // 2 - inset, center_y + size // 2 - inset
    cut = max(7, size // 4)
    points = (
        (left + cut, top), (right - cut, top), (right, (top + bottom) // 2),
        (right - cut, bottom), (left + cut, bottom), (left, (top + bottom) // 2),
        (left + cut, top),
    )
    draw.line(points, fill="#F4C542", width=1, joint="curve")


def _fit_outfit_item(image: Image.Image) -> Image.Image:
    """Center visible item pixels, not the source canvas's transparent padding."""
    rgba = image.convert("RGBA")
    alpha_bbox = rgba.getchannel("A").getbbox()
    if alpha_bbox:
        rgba = rgba.crop(alpha_bbox)
    fitted = ImageOps.contain(rgba, (OUTFIT_ITEM_SIZE - 8, OUTFIT_ITEM_SIZE - 8), method=Image.LANCZOS)
    layer = Image.new("RGBA", (OUTFIT_ITEM_SIZE, OUTFIT_ITEM_SIZE), (0, 0, 0, 0))
    layer.alpha_composite(fitted, ((OUTFIT_ITEM_SIZE - fitted.width) // 2, (OUTFIT_ITEM_SIZE - fitted.height) // 2))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), _hex_mask(OUTFIT_ITEM_SIZE)))
    return layer


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: str,
    font: ImageFont.ImageFont,
    fill: str = "white",
    root: str | None = None,
    min_size: int = 8,
    stroke: bool = False,
) -> None:
    left, top, right, bottom = box
    max_width = right - left
    chosen_font = font
    if root is not None:
        size = font.size if hasattr(font, "size") else 16
        while size > min_size:
            bbox = draw.textbbox((0, 0), value, font=chosen_font)
            if (bbox[2] - bbox[0]) <= max_width:
                break
            size -= 1
            chosen_font = _font(root, size)
    bbox = draw.textbbox((0, 0), value, font=chosen_font)
    x = left + max(0, (right - left - (bbox[2] - bbox[0])) // 2)
    y = top + max(0, (bottom - top - (bbox[3] - bbox[1])) // 2) - bbox[1]
    if stroke:
        draw.text((x, y), value, font=chosen_font, fill=fill, stroke_width=1, stroke_fill="black")
    else:
        draw.text((x, y), value, font=chosen_font, fill=fill)


def render_reference_outfit(
    root: str,
    player_data: dict[str, Any],
    outfit_images: list[Image.Image | None],
    profile_avatar_image: Image.Image | None,
    character_image: Image.Image | None,
    stats_data: dict[str, Any] | None,
    uid: str,
    mode: str = "br",
) -> bytes:
    background_name = CS_BACKGROUND if mode.lower() == "cs" else REFERENCE_BACKGROUND
    background_path = os.path.join(root, background_name)
    if os.path.exists(background_path):
        background = Image.open(background_path).convert("RGBA")
        canvas = ImageOps.fit(background, CANVAS_SIZE, method=Image.LANCZOS)
    else:
        canvas = Image.new("RGBA", CANVAS_SIZE, "black")

    if character_image is not None:
        # The center character comes directly from profileInfo.avatarId.
        # Equipped clothes are rendered only in the surrounding item slots.
        character = _fit_character(character_image, CHARACTER_BOX)
        canvas.alpha_composite(character, (CHARACTER_BOX[0], CHARACTER_BOX[1]))

    draw = ImageDraw.Draw(canvas)
    for image, (center_x, center_y) in zip(outfit_images, OUTFIT_SLOT_CENTERS):
        if image is None:
            continue
        item = _fit_outfit_item(image)
        canvas.paste(item, (center_x - OUTFIT_ITEM_SIZE // 2, center_y - OUTFIT_ITEM_SIZE // 2), item)
        _draw_golden_slot_border(draw, center_x, center_y)

    basic = player_data.get("basicInfo", {}) if isinstance(player_data, dict) else {}
    profile = player_data.get("profileInfo", {}) if isinstance(player_data, dict) else {}

    if profile_avatar_image is not None:
        left, top, right, bottom = PROFILE_AVATAR_BOX
        avatar = _fit_avatar(profile_avatar_image, PROFILE_AVATAR_BOX)
        canvas.paste(avatar, (left, top), avatar)

    name = str(_first_value(basic, ("nickname", "name", "accountName")) or _first_value(profile, ("nickname", "name")) or "Unknown")
    name = _normalize_display_text(name)
    clan_info = player_data.get("clanBasicInfo", {}) if isinstance(player_data, dict) else {}
    clan_name = str(_first_value(clan_info, ("clanName", "name")) or name)
    clan_name = _normalize_display_text(clan_name)
    level_raw = _first_value(basic, ("level", "accountLevel"))
    level = str(level_raw or "-")
    exp_raw = _first_value(basic, ("exp", "experience"))
    likes = str(_first_value(basic, ("liked", "likes", "likeCount", "likedCount")) or _first_value(profile, ("liked", "likes", "likeCount", "likedCount")) or "-")

    text_color = "#F4C542"
    _draw_nickname(draw, CLAN_BOX, clan_name, root, size=16, fill=text_color)
    _draw_nickname(draw, NAME_BOX, name, root, size=21, fill=text_color)
    _draw_centered(draw, UID_VALUE_BOX, uid if uid else "-", _font(root, VALUE_FONT_SIZE), fill=text_color, root=root, min_size=VALUE_FONT_MIN_SIZE, stroke=False)
    _draw_centered(draw, LIKE_BOX, likes, _font(root, VALUE_FONT_SIZE), fill=text_color, root=root, min_size=VALUE_FONT_MIN_SIZE, stroke=True)
    _draw_centered(draw, LEVEL_VALUE_BOX, level, _font(root, VALUE_FONT_SIZE), fill=text_color, root=root, min_size=VALUE_FONT_MIN_SIZE, stroke=False)

    if isinstance(level_raw, int) and isinstance(exp_raw, int):
        fraction = _level_progress_fraction(level_raw, exp_raw)
        bx0, by0, bx1, by1 = XP_BAR_BOX
        fill_width = int((bx1 - bx0) * fraction)
        if fill_width > 0:
            draw.rectangle((bx0, by0, bx0 + fill_width, by1), fill="#d99a5b")

    stats = stats_data or {}
    value_aliases = (
        {"matchesplayed", "matches", "gamesplayed"},
        {"kills", "totalkills"},
        {"headshots", "headshot"},
        {"winrate", "win_rate", "wins"},
        {"kdratio", "kd", "kdr"},
    )
    stat_max_width = 90
    stat_rows = CS_STAT_VALUE_Y if mode.lower() == "cs" else STAT_VALUE_Y
    for y, label, aliases in zip(stat_rows, STAT_LABELS, value_aliases):
        if label == "KD Ratio":
            value = _kd_text(stats)
        elif label == "Win Rate" and mode.lower() == "cs":
            value = _win_rate_text(stats)
        elif label == "Headshots" and mode.lower() == "cs":
            value = _text(stats, {"headshotkills", "headshots", "headshot"}, "-")
        else:
            value = _text(stats, aliases, "-")
        if label == "Win Rate" and value not in {"-", ""} and not value.endswith("%"):
            value = f"{value}%"
        size = VALUE_FONT_SIZE
        font = _font(root, size)
        while size > VALUE_FONT_MIN_SIZE:
            bbox = draw.textbbox((0, 0), value, font=font)
            if (bbox[2] - bbox[0]) <= stat_max_width:
                break
            size -= 1
            font = _font(root, size)
        bbox = draw.textbbox((0, 0), value, font=font)
        value_width = bbox[2] - bbox[0]
        value_x = STAT_VALUE_CENTER_X - (value_width // 2) - bbox[0]
        draw.text((value_x, y), value, font=font, fill="#F4C542")

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()