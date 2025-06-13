import asyncio
import json
import re
from typing import Dict, List, Optional, Tuple, Union
import aiohttp
from pathlib import Path
from ..config import DOWNLOAD_DIR
import random
import time
from .youtube_cookies import get_cookies

API_URL = "https://my-api-lc2j.onrender.com"
API_KEY = "zefron_api_key"

class DownloadError(Exception):
    """Custom exception for download errors"""
    pass

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

    async def _make_api_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a request to the custom API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_URL}/{endpoint}",
                    params=params,
                    headers={"X-API-Key": API_KEY}
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    raise DownloadError(f"API request failed: {resp.status}")
        except Exception as e:
            raise DownloadError(f"API request failed: {str(e)}")

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
        try:
            response = await self._make_api_request("search", {"query": query})
            if response and "results" in response and response["results"]:
                return response["results"][0]
        except Exception as e:
            print(f"Failed to fetch video info: {e}")
        return None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        try:
            response = await self._make_api_request("video-info", {"url": link})
            return response.get("is_live", False)
        except Exception:
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
        try:
            response = await self._make_api_request("video-stream", {"url": link, "quality": "720p"})
            if response and response.get("success"):
                return 1, response["stream_url"]
            return 0, "Failed to get video stream"
        except Exception as e:
            return 0, str(e)

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        try:
            response = await self._make_api_request("playlist", {"url": link, "limit": limit})
            if response and "videos" in response:
                return [video["id"] for video in response["videos"]]
            return []
        except Exception:
            return []

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Track not found")

        details = {
            "title": info.get("title", ""),
            "link": info.get("url", self._prepare_link(link, videoid)),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration"),
            "thumb": info.get("thumbnail", "").split("?")[0],
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        try:
            response = await self._make_api_request("formats", {"url": link})
            if response and "formats" in response:
                return response["formats"], link
            return [], link
        except Exception:
            return [], link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        try:
            response = await self._make_api_request("search", {"query": link, "limit": 10})
            if response and "results" in response and response["results"]:
                results = response["results"]
                if query_type < len(results):
                    res = results[query_type]
                    return (
                        res.get("title", ""),
                        res.get("duration"),
                        res.get("thumbnail", "").split("?")[0],
                        res.get("id", ""),
                    )
        except Exception as e:
            print(f"Slider error: {e}")
        raise IndexError(f"Query type index {query_type} out of range")

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
            if video:
                if await self.is_live(link):
                    status, stream_url = await self.video(link)
                    if status == 1:
                        return stream_url, None
                    raise ValueError("Unable to fetch live stream link")

                response = await self._make_api_request("download", {
                    "url": link,
                    "format": "best",
                    "type": "video"
                })
                if response and response.get("success"):
                    return response["file_path"], True
                return None, None

            if songaudio or songvideo:
                response = await self._make_api_request("download", {
                    "url": link,
                    "format": format_id or "bestaudio/best",
                    "type": "song_video" if songvideo else "song_audio",
                    "title": title
                })
                if response and response.get("success"):
                    return response["file_path"], True
                return None, None

            response = await self._make_api_request("download", {
                "url": link,
                "format": "bestaudio/best",
                "type": "audio"
            })
            if response and response.get("success"):
                return response["file_path"], True
            return None, None

        except Exception as e:
            print(f"Download error: {e}")
            return None, None

def get_yt_dlp_opts(format: str = "bestaudio/best") -> Dict:
    """Configure yt-dlp options with anti-ban measures"""
    cookies_path = get_cookies()
    
    opts = {
        'format': format,
        'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_audio': format == "bestaudio",
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }] if format == "bestaudio" else [],
        # Anti-ban and rate limiting measures
        'socket_timeout': 10,
        'retries': 3,
        'fragment_retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        # Avoid throttling
        'throttledratelimit': 100000,
        'sleep_interval': 2,  # Sleep between requests
        'max_sleep_interval': 5,
        # Network settings
        'source_address': '0.0.0.0',  # Use all available network interfaces
        'nocheckcertificate': True,
        # Cookies and cache
        'cachedir': False,  # Disable cache
    }
    
    # Add cookies if available
    if cookies_path:
        opts['cookiefile'] = cookies_path
    
    return opts

def download_video(url: str, format: str = "bestaudio/best") -> Optional[Path]:
    """
    Download a video from YouTube with anti-ban measures
    
    Args:
        url: YouTube video URL
        format: Format to download (bestaudio/best, best, etc.)
    
    Returns:
        Path to the downloaded file
    
    Raises:
        DownloadError: If download fails
    """
    try:
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))
        
        with yt_dlp.YoutubeDL(get_yt_dlp_opts(format)) as ydl:
            # Extract info first to validate URL
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise DownloadError("Failed to extract video information")
                
                # Check if video is available
                if info.get('is_live', False):
                    raise DownloadError("Live streams are not supported")
                
                # Download the video
                info = ydl.extract_info(url, download=True)
                
                # Get the downloaded file path
                if 'requested_downloads' in info:
                    filename = info['requested_downloads'][0]['filepath']
                else:
                    filename = ydl.prepare_filename(info)
                
                file_path = Path(filename)
                if not file_path.exists():
                    raise DownloadError("Downloaded file not found")
                
                return file_path
                
            except yt_dlp.utils.DownloadError as e:
                if "Video unavailable" in str(e):
                    raise DownloadError("Video is unavailable or region-restricted")
                elif "sign in to view" in str(e).lower():
                    raise DownloadError("This video requires authentication. Please provide valid YouTube cookies.")
                else:
                    raise DownloadError(f"Download failed: {str(e)}")
            
    except Exception as e:
        raise DownloadError(f"Download failed: {str(e)}")

def get_video_info(url: str) -> Dict:
    """
    Get video information without downloading
    
    Args:
        url: YouTube video URL
    
    Returns:
        Dict containing video information
    """
    try:
        with yt_dlp.YoutubeDL({
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'cookiefile': get_cookies(),
        }) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        raise DownloadError(f"Failed to get video info: {str(e)}")

async def get_video_stream(url: str, quality: str = "720p") -> Optional[str]:
    """
    Get direct video stream URL from YouTube
    
    Args:
        url: YouTube video URL
        quality: Desired video quality (360p, 480p, 720p, 1080p)
    
    Returns:
        Direct stream URL if found, None otherwise
    """
    try:
        # Map quality to format
        quality_formats = {
            "360p": "18",  # MP4 360p
            "480p": "135", # MP4 480p
            "720p": "22",  # MP4 720p
            "1080p": "137" # MP4 1080p
        }
        
        format_id = quality_formats.get(quality, "22")  # Default to 720p
        cookies_path = get_cookies()
        
        cmd = ["yt-dlp", "-g", "-f", format_id]
        if cookies_path:
            cmd.extend(["--cookies", cookies_path])
        cmd.append(url)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        if stdout:
            return stdout.decode().strip()
            
        return None
        
    except Exception as e:
        raise DownloadError(f"Failed to get video stream: {str(e)}") 
