from __future__ import annotations

import asyncio
from typing import Any

from Api.Account import get_garena_token, get_major_login
from Api.InGame import get_player_stats, search_account_by_keyword
from Utilities.until import load_accounts


ACCOUNTS = load_accounts()


def _region_name(region: str | None) -> str:
    return (region or "IND").strip().upper()


def _login(region: str) -> tuple[dict[str, Any], str, str]:
    if region not in ACCOUNTS:
        raise ValueError(f"Unsupported region: {region}")

    account = ACCOUNTS[region]
    auth = get_garena_token(account["uid"], account["password"])
    if not auth or "access_token" not in auth or "open_id" not in auth:
        raise RuntimeError("Garena authentication failed")

    login = get_major_login(auth["access_token"], auth["open_id"])
    if not login or "token" not in login or "serverUrl" not in login:
        raise RuntimeError("Major login failed")

    return login, login["token"], login["serverUrl"]


def fetch_stats(uid: str, region: str | None = None, mode: str = "br", matchmode: str = "CAREER") -> dict[str, Any]:
    region_name = _region_name(region)
    if not str(uid).isdigit():
        raise ValueError("UID must be numeric")
    mode = mode.lower()
    matchmode = matchmode.upper()
    if mode not in {"br", "cs"}:
        raise ValueError("mode must be 'br' or 'cs'")
    if matchmode not in {"CAREER", "NORMAL", "RANKED"}:
        raise ValueError("matchmode must be CAREER, NORMAL, or RANKED")

    _login_result, token, server_url = _login(region_name)
    data = get_player_stats(token, server_url, mode, uid, matchmode)
    return {
        "mode": mode,
        "matchmode": matchmode,
        "region": region_name,
        "data": data,
    }


def fetch_both_stats(uid: str, region: str | None = None, matchmode: str = "CAREER") -> dict[str, Any]:
    """Fetch BR and CS stats using one upstream authentication flow."""
    if not str(uid).isdigit():
        raise ValueError("UID must be numeric")
    matchmode = matchmode.upper()
    if matchmode not in {"CAREER", "NORMAL", "RANKED"}:
        raise ValueError("matchmode must be CAREER, NORMAL, or RANKED")

    region_name = _region_name(region)
    _login_result, token, server_url = _login(region_name)
    result: dict[str, Any] = {}
    for mode in ("br", "cs"):
        try:
            result[mode] = {
                "mode": mode,
                "matchmode": matchmode,
                "region": region_name,
                "data": get_player_stats(token, server_url, mode, uid, matchmode),
            }
        except Exception as exc:
            result[mode] = {"error": str(exc)}
    return result


def search_accounts(name: str, region: str | None = None) -> Any:
    region_name = _region_name(region)
    if len(name.strip()) < 3:
        raise ValueError("name must be at least 3 characters long")
    _login_result, token, server_url = _login(region_name)
    return search_account_by_keyword(server_url, token, name.strip())


async def fetch_both_stats_async(uid: str, region: str | None = None, matchmode: str = "CAREER") -> dict[str, Any]:
    return await asyncio.to_thread(fetch_both_stats, uid, region, matchmode)


async def fetch_stats_async(uid: str, region: str | None = None, mode: str = "br", matchmode: str = "CAREER") -> dict[str, Any]:
    return await asyncio.to_thread(fetch_stats, uid, region, mode, matchmode)


async def search_accounts_async(name: str, region: str | None = None) -> Any:
    return await asyncio.to_thread(search_accounts, name, region)
