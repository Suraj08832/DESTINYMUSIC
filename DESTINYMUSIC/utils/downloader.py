import os
import yt_dlp
import asyncio
import aiohttp
import aiofiles
from typing import Optional, Dict, Any
from ..config import API_URL, API_KEY

async def download_audio(url: str, output_path: str) -> Optional[str]:
    """Download audio from YouTube URL using yt-dlp"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Return the path to the downloaded file
        return output_path + '.mp3'
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None

async def download_video(url: str, output_path: str) -> Optional[str]:
    """Download video from YouTube URL using yt-dlp"""
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Return the path to the downloaded file
        return output_path
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        return None

async def yt_dlp_download(url: str, output_path: str, is_audio: bool = True) -> Optional[str]:
    """Download audio or video using yt-dlp"""
    try:
        if is_audio:
            return await download_audio(url, output_path)
        else:
            return await download_video(url, output_path)
    except Exception as e:
        print(f"Error in yt_dlp_download: {str(e)}")
        return None