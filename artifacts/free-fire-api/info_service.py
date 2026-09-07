"""Free Fire account information service from the supplied source archive."""

import asyncio
import base64
import json
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urlencode

import httpx
from Crypto.Cipher import AES
from google.protobuf import json_format, message
from google.protobuf.message import Message

from Proto import AccountPersonalShow_pb2, FreeFire_pb2, main_pb2

MAIN_KEY = base64.b64decode("WWcmdGMlREV1aDYlWmNeOA==")
MAIN_IV = base64.b64decode("Nm95WkRyMjJFM3ljaGpNJQ==")
RELEASE_VERSION = "OB54"
USER_AGENT = (
    "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
)
SUPPORTED_REGIONS = (
    "IND",
    "BR",
    "US",
    "SAC",
    "NA",
    "SG",
    "RU",
    "ID",
    "TW",
    "VN",
    "TH",
    "ME",
    "PK",
    "CIS",
    "BD",
    "EUROPE",
)

# Credentials used by the server when it requests account information from
# Garena. They are intentionally kept server-side and are never accepted from
# or returned to API callers.
INFO_API_UID = "7402777449"
INFO_API_PASSWORD = (
    "EB1B139FECAEC90A1A7EAD1E5AED3713C0B057490829666213D09801FFEE2F95"
)

cached_tokens: dict[str, dict[str, Any]] = defaultdict(dict)
uid_region_cache: dict[str, str] = {}
token_locks = {region: asyncio.Lock() for region in SUPPORTED_REGIONS}


def pad(data: bytes) -> bytes:
    padding_length = AES.block_size - (len(data) % AES.block_size)
    return data + bytes([padding_length] * padding_length)


def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext))


def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    instance = message_type()
    instance.ParseFromString(encoded_data)
    return instance


def get_account_credentials(region: str) -> str:
    del region
    return urlencode({"uid": INFO_API_UID, "password": INFO_API_PASSWORD})


async def get_access_token(region: str) -> tuple[str, str]:
    del region
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = (
        get_account_credentials("")
        + "&response_type=token&client_type=2"
        "&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
        "&client_id=100067"
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, content=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("access_token", "0"), data.get("open_id", "0")


async def create_jwt(region: str) -> None:
    token_value, open_id = await get_access_token(region)
    body = json.dumps(
        {
            "open_id": open_id,
            "open_id_type": "4",
            "login_token": token_value,
            "orign_platform_type": "4",
        }
    )
    proto_bytes = json_format.ParseDict(
        json.loads(body), FreeFire_pb2.LoginReq()
    ).SerializeToString()
    payload = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, proto_bytes)
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/octet-stream",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://loginbp.ggpolarbear.com/MajorLogin",
            content=payload,
            headers=headers,
        )
        response.raise_for_status()
        login_response = decode_protobuf(response.content, FreeFire_pb2.LoginRes)
        message_json = json.loads(json_format.MessageToJson(login_response))
        cached_tokens[region] = {
            "token": f"Bearer {message_json.get('token', '0')}",
            "region": message_json.get("lockRegion", "0"),
            "server_url": message_json.get("serverUrl", "0"),
            "expires_at": time.time() + 25200,
        }


async def get_token_info(region: str) -> tuple[str, str, str]:
    normalized_region = region.upper()
    info = cached_tokens.get(normalized_region)
    if info and time.time() < info["expires_at"]:
        return info["token"], info["region"], info["server_url"]

    lock = token_locks.setdefault(normalized_region, asyncio.Lock())
    async with lock:
        info = cached_tokens.get(normalized_region)
        if not info or time.time() >= info["expires_at"]:
            await create_jwt(normalized_region)
        info = cached_tokens[normalized_region]
        return info["token"], info["region"], info["server_url"]


async def get_account_information_for_region(
    uid: str, region: str
) -> dict[str, Any]:
    request_message = main_pb2.GetPlayerPersonalShow()
    json_format.ParseDict({"a": uid, "b": "7"}, request_message)
    payload = aes_cbc_encrypt(
        MAIN_KEY,
        MAIN_IV,
        request_message.SerializeToString(),
    )
    token, _lock_region, server_url = await get_token_info(region)
    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/octet-stream",
        "Expect": "100-continue",
        "Authorization": token,
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{server_url}/GetPlayerPersonalShow",
            content=payload,
            headers=headers,
        )
        response.raise_for_status()
        account_message = decode_protobuf(
            response.content,
            AccountPersonalShow_pb2.AccountPersonalShowInfo,
        )
        return json.loads(json_format.MessageToJson(account_message))


async def get_account_information(
    uid: str, requested_region: str | None = None
) -> dict[str, Any] | None:
    if requested_region:
        normalized_region = requested_region.upper()
        if normalized_region not in SUPPORTED_REGIONS:
            raise ValueError(f"Unsupported region: {requested_region}")
    else:
        normalized_region = uid_region_cache.get(uid)

    # An explicitly supplied region is a deliberate fast path. The caller
    # already provided the server to query, so probing every other region only
    # adds latency and can turn a temporary upstream response into a very slow
    # lookup. Automatic multi-region discovery remains available when no
    # region was supplied.
    if normalized_region:
        regions = [normalized_region]
    else:
        regions = list(SUPPORTED_REGIONS)
        cached_region = uid_region_cache.get(uid)
        if cached_region and cached_region in regions:
            regions.remove(cached_region)
            regions.insert(0, cached_region)

    for region in regions:
        try:
            data = await get_account_information_for_region(uid, region)
            uid_region_cache[uid] = region
            return data
        except Exception:
            continue
    return None


async def refresh_tokens() -> None:
    await asyncio.gather(*(create_jwt(region) for region in SUPPORTED_REGIONS))