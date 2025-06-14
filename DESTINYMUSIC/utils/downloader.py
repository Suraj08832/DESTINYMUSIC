import asyncio
import aiohttp
import aiofiles
import os
import re
from typing import Optional, Union, Dict

API_URL = "https://my-api-lc2j.onrender.com"
API_KEY = "zefron_api_key"

USE_API = bool(API_URL and API_KEY)
CHUNK_SIZE = 8192
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)


def extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    return link.split("/")[-1].split("?")[0]


def safe_filename(title: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", title)


def file_exists(video_id: str) -> Optional[str]:
    for ext in ["mp3", "mp4", "webm", "m4a"]:
        path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(path):
            return path
    return None


async def download_file(url: str, path: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"[Download Error] Status {response.status}")
                    return False

                async with aiofiles.open(path, "wb") as f:
                    while True:
                        chunk = await response.content.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        await f.write(chunk)
                return True
    except Exception as e:
        print(f"[Download Error] {e}")
        return False


async def download_audio(link: str) -> Optional[str]:
    video_id = extract_video_id(link)
    existing = file_exists(video_id)
    if existing:
        return existing

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": link, "format": "audio"},
                headers={"Authorization": f"Bearer {API_KEY}"}
            ) as response:
                if response.status != 200:
                    print(f"[API ERROR] Status {response.status}")
                    return None

                data = await response.json()
                download_url = data.get("url")
                if not download_url:
                    print("[API ERROR] No download URL in response")
                    return None

                fmt = data.get("format", "mp3").lower()
                path = f"{download_folder}/{video_id}.{fmt}"

                if await download_file(download_url, path):
                    return path
                return None
    except Exception as e:
        print(f"[API Download Error] {e}")
        return None


async def download_video(link: str, format_id: str = None) -> Optional[str]:
    video_id = extract_video_id(link)
    existing = file_exists(video_id)
    if existing:
        return existing

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": link, "format": "video", "format_id": format_id},
                headers={"Authorization": f"Bearer {API_KEY}"}
            ) as response:
                if response.status != 200:
                    print(f"[API ERROR] Status {response.status}")
                    return None

                data = await response.json()
                download_url = data.get("url")
                if not download_url:
                    print("[API ERROR] No download URL in response")
                    return None

                fmt = data.get("format", "mp4").lower()
                path = f"{download_folder}/{video_id}.{fmt}"

                if await download_file(download_url, path):
                    return path
                return None
    except Exception as e:
        print(f"[API Download Error] {e}")
        return None


async def download_audio_concurrent(link: str) -> Optional[str]:
    return await download_audio(link)


async def yt_dlp_download(link: str, type: str, format_id: str = None, title: str = None) -> Optional[str]:
    if type in ["audio", "song_audio"]:
        return await download_audio(link)
    elif type in ["video", "song_video"]:
        return await download_video(link, format_id)
    return None