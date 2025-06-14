import os
import yt_dlp
import asyncio
import aiohttp
import aiofiles

async def download_audio(url: str) -> str:
    """Download audio from YouTube URL"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': '%(title)s.%(ext)s',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return f"{info['title']}.mp3"
            
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None

async def download_video(url: str) -> str:
    """Download video from YouTube URL"""
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': '%(title)s.%(ext)s',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return f"{info['title']}.{info['ext']}"
            
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        return None

async def yt_dlp_download(url: str, is_audio: bool = True) -> str:
    """Download media using yt-dlp"""
    if is_audio:
        return await download_audio(url)
    return await download_video(url)