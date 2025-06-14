import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from DESTINYMUSIC.utils.database import is_on_off
from DESTINYMUSIC.utils.downloader import download_audio, download_video
from DESTINYMUSIC.utils.errors import capture_internal_err
from DESTINYMUSIC.utils.formatters import time_to_seconds

API_URL = "https://my-api-lc2j.onrender.com"
API_KEY = "zefron_api_key"

_cache = {}

@capture_internal_err
async def shell_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return (out or err).decode()

@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    if query in _cache:
        return _cache[query]
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/search",
                params={"query": query},
                headers={"Authorization": f"Bearer {API_KEY}"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result_data = data.get("result", [])
                    if result_data:
                        _cache[query] = result_data
                    return result_data
    except Exception as e:
        print(f"[Custom API] Search failed: {e}")
    return []

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    async def _fetch_from_custom_api(self, query: str) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/search",
                    params={"query": query},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result", [{}])[0]
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
        if use_cache and not query.startswith("http"):
            if query in _cache:
                return _cache[query][0]

            api_result = await self._fetch_from_custom_api(query)
            if api_result:
                _cache[query] = [api_result]
                return api_result

        elif query.startswith("http"):
            api_result = await self._fetch_from_custom_api(query)
            if api_result:
                return api_result

        return None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/info",
                    params={"url": link},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("is_live", False)
        except Exception as e:
            print(f"[Custom API] Failed to check live status: {e}")
        return False

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        duration_text = info.get("duration")
        duration_sec = int(time_to_seconds(duration_text)) if duration_text else 0
        thumb = info.get("thumbnail", "").split("?")[0]
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
        return info.get("thumbnail", "").split("?")[0] if info else ""

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/video",
                    params={"url": link},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return (1, data.get("url", ""))
        except Exception as e:
            print(f"[Custom API] Failed to get video URL: {e}")
        return (0, "Failed to get video URL")

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/playlist",
                    params={"url": link, "limit": limit},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("videos", [])
        except Exception as e:
            print(f"[Custom API] Failed to get playlist: {e}")
        return []

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)
        print(f"[Track] Processing link: {prepared_link}")

        async def search_with_query(query: str) -> Optional[Tuple[Dict, str]]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{API_URL}/search",
                        params={"query": query},
                        headers={"Authorization": f"Bearer {API_KEY}"}
                    ) as resp:
                        print(f"[Track] Search response status for '{query}': {resp.status}")
                        if resp.status == 200:
                            data = await resp.json()
                            print(f"[Track] Raw API response for '{query}': {data}")
                            
                            # Handle different response formats
                            if isinstance(data, dict):
                                # Format 1: {"result": [...]}
                                if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                                    info = data["result"][0]
                                    print(f"[Track] Found result in 'result' array: {info}")
                                    return create_track_details(info, prepared_link)
                                
                                # Format 2: Direct result array
                                elif isinstance(data.get("data"), list) and len(data["data"]) > 0:
                                    info = data["data"][0]
                                    print(f"[Track] Found result in 'data' array: {info}")
                                    return create_track_details(info, prepared_link)
                                
                                # Format 3: Direct video info
                                elif all(key in data for key in ["title", "id"]):
                                    print(f"[Track] Found direct video info: {data}")
                                    return create_track_details(data, prepared_link)
                                
                                # Format 4: {"videos": [...]}
                                elif "videos" in data and isinstance(data["videos"], list) and len(data["videos"]) > 0:
                                    info = data["videos"][0]
                                    print(f"[Track] Found result in 'videos' array: {info}")
                                    return create_track_details(info, prepared_link)
                                
                                # Format 5: {"items": [...]}
                                elif "items" in data and isinstance(data["items"], list) and len(data["items"]) > 0:
                                    info = data["items"][0]
                                    print(f"[Track] Found result in 'items' array: {info}")
                                    return create_track_details(info, prepared_link)
                            
                            # Format 6: Direct array of results
                            elif isinstance(data, list) and len(data) > 0:
                                info = data[0]
                                print(f"[Track] Found result in direct array: {info}")
                                return create_track_details(info, prepared_link)
                            
                            print(f"[Track] Unrecognized response format for '{query}': {data}")
            except Exception as e:
                print(f"[Track] Error searching for '{query}': {str(e)}")
                import traceback
                print(f"[Track] Error traceback: {traceback.format_exc()}")
            return None

        def create_track_details(info: Dict, link: str) -> Tuple[Dict, str]:
            try:
                # Handle different thumbnail formats
                thumb = ""
                if "thumbnail" in info:
                    thumb = info["thumbnail"].split("?")[0]
                elif "thumbnails" in info and isinstance(info["thumbnails"], list) and len(info["thumbnails"]) > 0:
                    thumb = info["thumbnails"][0].get("url", "").split("?")[0]
                elif "thumb" in info:
                    thumb = info["thumb"].split("?")[0]

                # Handle different ID formats
                vid_id = info.get("id", "") or info.get("videoId", "") or info.get("video_id", "")

                # Handle different URL formats
                video_url = info.get("webpage_url", "") or info.get("url", "") or info.get("link", "") or link

                details = {
                    "title": info.get("title", ""),
                    "link": video_url,
                    "vidid": vid_id,
                    "duration_min": info.get("duration") if isinstance(info.get("duration"), str) else None,
                    "thumb": thumb,
                }
                print(f"[Track] Created details: {details}")
                return details, vid_id
            except Exception as e:
                print(f"[Track] Error creating track details: {str(e)}")
                import traceback
                print(f"[Track] Error traceback: {traceback.format_exc()}")
                raise

        try:
            # Check if the input is a YouTube URL or just a search query
            is_youtube_url = "youtube.com" in prepared_link or "youtu.be" in prepared_link
            
            if is_youtube_url:
                # Handle YouTube URL
                print(f"[Track] Processing YouTube URL: {prepared_link}")
                video_id = prepared_link.split("v=")[-1] if "v=" in prepared_link else prepared_link.split("/")[-1]
                result = await search_with_query(video_id)
                if result:
                    return result
            else:
                # Handle search query (song name)
                print(f"[Track] Processing search query: {prepared_link}")
                
                # Try multiple search variations
                search_queries = [
                    prepared_link,  # Original query
                    f"{prepared_link} audio",  # Add audio keyword
                    f"{prepared_link} official",  # Add official keyword
                    f"{prepared_link} song",  # Add song keyword
                    f"{prepared_link} music",  # Add music keyword
                    f"{prepared_link} lyrics"  # Add lyrics keyword
                ]
                
                # Try each search variation
                for query in search_queries:
                    print(f"[Track] Trying search query: {query}")
                    result = await search_with_query(query)
                    if result:
                        return result

            # If direct search fails, try cached search
            print(f"[Track] Attempting cached search for: {prepared_link}")
            try:
                search_results = await cached_youtube_search(prepared_link)
                print(f"[Track] Cached search results: {search_results}")
                if search_results and len(search_results) > 0:
                    info = search_results[0]
                    return create_track_details(info, prepared_link)
            except Exception as e:
                print(f"[Track] Error during cached search: {str(e)}")

            print(f"[Track] All search attempts failed for: {prepared_link}")
            raise ValueError("Track not found via API")

        except Exception as e:
            print(f"[Track] Error occurred: {str(e)}")
            print(f"[Track] Error type: {type(e)}")
            import traceback
            print(f"[Track] Traceback: {traceback.format_exc()}")
            raise ValueError("Track not found")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/formats",
                    params={"url": link},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        formats = data.get("formats", [])
                        return formats, link
        except Exception as e:
            print(f"[Custom API] Failed to get formats: {e}")
        return [], link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/search",
                    params={"query": self._prepare_link(link, videoid), "limit": 10},
                    headers={"Authorization": f"Bearer {API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("result", [])
                        if not results or query_type >= len(results):
                            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
                        res = results[query_type]
                        return (
                            res.get("title", ""),
                            res.get("duration"),
                            res.get("thumbnail", "").split("?")[0],
                            res.get("id", ""),
                        )
        except Exception as e:
            print(f"[Custom API] Failed to get slider: {e}")
        raise IndexError("Failed to get slider results")

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
        link = self._prepare_link(link, videoid)

        try:
            if songvideo:
                # Use /search endpoint to get video info first
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{API_URL}/search",
                        params={"query": link},
                        headers={"Authorization": f"Bearer {API_KEY}"}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and "result" in data and len(data["result"]) > 0:
                                video_info = data["result"][0]
                                path = await download_video(video_info["id"], format_id)
                                return (path, True) if path else (None, None)

            elif songaudio:
                # Use /search endpoint to get audio info first
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{API_URL}/search",
                        params={"query": link},
                        headers={"Authorization": f"Bearer {API_KEY}"}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and "result" in data and len(data["result"]) > 0:
                                audio_info = data["result"][0]
                                path = await download_audio(audio_info["id"])
                                return (path, True) if path else (None, None)

            elif video:
                if await self.is_live(link):
                    status, stream_url = await self.video(link)
                    if status == 1:
                        return stream_url, None
                    raise ValueError("Unable to fetch live stream link")
                
                # Use /search endpoint to get video info first
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{API_URL}/search",
                        params={"query": link},
                        headers={"Authorization": f"Bearer {API_KEY}"}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and "result" in data and len(data["result"]) > 0:
                                video_info = data["result"][0]
                                path = await download_video(video_info["id"])
                                return (path, True) if path else (None, None)

            else:
                # Use /search endpoint to get audio info first
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{API_URL}/search",
                        params={"query": link},
                        headers={"Authorization": f"Bearer {API_KEY}"}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and "result" in data and len(data["result"]) > 0:
                                audio_info = data["result"][0]
                                path = await download_audio(audio_info["id"])
                                return (path, True) if path else (None, None)

        except Exception as e:
            print(f"[Download Error] {e}")
            return None, None
