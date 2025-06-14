import os
import re
import json
import asyncio
import aiohttp
import yt_dlp
from typing import Dict, List, Tuple, Union, Optional
from ..utils.downloader import yt_dlp_download
from ..utils.errors import capture_internal_err

class Youtube:
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
        }

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if videoid:
            return f"https://www.youtube.com/watch?v={videoid}"
        return link

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        prepared_link = self._prepare_link(link, videoid)
        print(f"[Track] Processing link: {prepared_link}")

        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(prepared_link, download=False)
                if not info:
                    raise ValueError("Could not extract video info")

                # Get the best format
                formats = info.get('formats', [])
                best_format = None
                for f in formats:
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                        best_format = f
                        break

                if not best_format:
                    best_format = formats[0] if formats else None

                if not best_format:
                    raise ValueError("No suitable format found")

                # Get video details
                thumb = info.get('thumbnail', '').split('?')[0]
                details = {
                    "title": info.get('title', ''),
                    "link": prepared_link,
                    "vidid": info.get('id', ''),
                    "duration_min": str(info.get('duration', 0)),
                    "thumb": thumb,
                }

                return details, info.get('id', '')
        except Exception as e:
            print(f"[Track] Error: {str(e)}")
            raise ValueError("Track not found")

    @capture_internal_err
    async def playlist(self, link: str) -> List[Dict]:
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                if not info:
                    raise ValueError("Could not extract playlist info")

                entries = info.get('entries', [])
                if not entries:
                    raise ValueError("No entries found in playlist")

                tracks = []
                for entry in entries:
                    thumb = entry.get('thumbnail', '').split('?')[0]
                    track = {
                        "title": entry.get('title', ''),
                        "link": entry.get('webpage_url', ''),
                        "vidid": entry.get('id', ''),
                        "duration_min": str(entry.get('duration', 0)),
                        "thumb": thumb,
                    }
                    tracks.append(track)

                return tracks
        except Exception as e:
            print(f"[Playlist] Error: {str(e)}")
            raise ValueError("Playlist not found")

    @capture_internal_err
    async def download(self, link: str, type: str, format_id: str = None, title: str = None) -> Optional[str]:
        try:
            return await yt_dlp_download(link, type, format_id, title)
        except Exception as e:
            print(f"[Download] Error: {str(e)}")
            return None
