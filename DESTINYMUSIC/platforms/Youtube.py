import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from DESTINYMUSIC.utils.database import is_on_off
from DESTINYMUSIC.utils.errors import capture_internal_err
from DESTINYMUSIC.utils.formatters import time_to_seconds

_cache = {}

API_URL = "https://my-api-lc2j.onrender.com"
API_KEY = "zefron_api_key"

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = API_URL
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            return videoid.strip()
        if "youtu.be" in link:
            return link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            return link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    async def _fetch_from_custom_api(self, query: str) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/search",
                    params={"query": query},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result")
        except Exception as e:
            print(f"[Custom API] Failed to fetch: {e}")
        return None

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        if use_cache and query in _cache:
            return _cache[query]

        api_result = await self._fetch_from_custom_api(query)
        if api_result:
            _cache[query] = api_result
            return api_result

        return None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        info = await self._fetch_video_info(self._prepare_link(link))
        return bool(info.get("is_live")) if info else False

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        duration_text = info.get("duration")
        duration_sec = int(time_to_seconds(duration_text)) if duration_text else 0
        thumb = info.get("thumbnail", "")
        return (
            info.get("title", ""),
            duration_text,
            duration_sec,
            thumb,
            info.get("id", ""),
        )

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("thumbnail", "") if info else ""

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            return (0, "Video not found")
        return (1, info.get("video_url", ""))

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/playlist",
                    params={"id": videoid if videoid else link, "limit": limit},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return [item.get("id") for item in data.get("items", [])]
        except Exception as e:
            print(f"[Playlist] Failed to fetch: {e}")
        return []

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Track not found")

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", ""),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration"),
            "thumb": info.get("thumbnail", ""),
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            return [], ""
        
        formats = []
        for fmt in info.get("formats", []):
            formats.append({
                "format": fmt.get("format", ""),
                "filesize": fmt.get("filesize", 0),
                "format_id": fmt.get("format_id", ""),
                "ext": fmt.get("ext", ""),
                "format_note": fmt.get("format_note", ""),
                "yturl": link,
            })
        return formats, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/search",
                    params={"query": link, "limit": 10},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if not results or query_type >= len(results):
                            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
                        res = results[query_type]
                        return (
                            res.get("title", ""),
                            res.get("duration"),
                            res.get("thumbnail", ""),
                            res.get("id", ""),
                        )
        except Exception as e:
            print(f"[Slider] Failed to fetch: {e}")
        raise IndexError("No results found")

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        try:
            info = await self._fetch_video_info(self._prepare_link(link, videoid))
            if not info:
                return None, None

            if video:
                return info.get("video_url", ""), True
            elif songaudio:
                return info.get("audio_url", ""), False
            elif songvideo:
                return info.get("video_url", ""), True
            elif format_id:
                for fmt in info.get("formats", []):
                    if fmt.get("format_id") == format_id:
                        return fmt.get("url", ""), "video" in fmt.get("format", "").lower()
            else:
                return info.get("audio_url", ""), False

        except Exception as e:
            print(f"[Download] Failed: {e}")
            return None, None
