# Merged Free Fire API

This service combines the profile/banner API with the player-statistics API.

## Main combined endpoint

`GET /accinfo?uid=PLAYER_UID&region=IND&matchmode=CAREER`

It returns `profile` with normal account information, `stats.br` with Battle Royale statistics, `stats.cs` with Clash Squad statistics, and `metadata` containing the UID, selected region, and match mode. The `matchmode` value can be `CAREER`, `NORMAL`, or `RANKED`.

## Routes

| Route | Purpose |
|---|---|
| `GET /info?uid=PLAYER_UID&region=IND` | Normal profile information only. |
| `GET /stats?uid=PLAYER_UID&region=IND&mode=br&matchmode=CAREER` | One statistics mode; `mode` is `br` or `cs`. |
| `GET /search?name=PLAYER_NAME&region=IND` | Account-name search. |
| `GET /banner-image?uid=PLAYER_UID&region=IND` | Profile banner PNG. |
| `GET /outfit-image?uid=PLAYER_UID&region=IND&mode=br&matchmode=CAREER` | New 1331×784 outfit/profile/statistics PNG using the requested Img background. |
| `GET /api/healthz` | Health check. |
| `GET` or `POST /refresh` | Refresh first-API tokens. |

The same routes are also available under the `/api` prefix, for example `/api/accinfo` and `/api/outfit-image`.

## New outfit-image layout

The outfit renderer uses `clean_reference_background.png`, prepared from the requested image at `https://raw.githubusercontent.com/harshpromax137-web/Img/main/1788661333331.png`. It places eight equipped item PNGs into the surrounding shapes and places the full-body character between those shapes.

The character source is requested dynamically from:

```text
https://raw.githubusercontent.com/harshpromax137-web/Anime-PNG/main/{avatarId}.png
```

The `{avatarId}` value comes from `profileInfo.avatarId`. For example, `avatarId: 102000015` resolves to `102000015.png`. The character PNG is alpha-composited into the center area behind the outfit-item layers. The profile card receives the live profile avatar, player name, UID, clan name, likes, level, and selected BR/CS statistic values.

The coordinate and asset notes are documented in `new_asset_notes.md`, and the renderer is implemented in `reference_renderer.py`. A local synthetic preview can be produced with `python make_new_background_preview.py` after the sample avatar has been downloaded by `python inspect_new_assets.py`.

## Font integration

The renderer now prefers `GFF-Latin-Regular.ttf` for generated text, with `GFF-Latin-Medium.ttf`, `arial_unicode_bold.otf`, and `NotoSansCherokee.ttf` retained as fallbacks. This lets generated profile, statistics, and outfit images use the supplied GFF Latin typeface while preserving rendering for characters outside the font's glyph coverage.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080
```

Do not expose the included account configuration publicly. Replace it with environment variables or a private secret before deployment, and rotate any credentials that were previously committed to a public repository.
