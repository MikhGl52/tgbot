import os
import yt_dlp
from config import FFMPEG_PATH, MAX_SIZE_BYTES

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def search_music(query: str) -> list[dict]:
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f'ytsearch5:{query} music', download=False)
        results = []
        for v in info['entries']:
            # thumbnail недоступен при extract_flat, строим URL вручную
            video_id = v.get('id', '')
            thumbnail = f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
            results.append({
                'title': v.get('title', 'No title'),
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'duration': str(v.get('duration', '?')) + 's',
                'channel': v.get('channel') or v.get('uploader', ''),
                'thumbnail': thumbnail,
            })
        return results
def download_music(url: str) -> dict:
    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
    }
    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.splitext(ydl.prepare_filename(info))[0] + '.mp3'

        if os.path.exists(filename) and os.path.getsize(filename) > MAX_SIZE_BYTES:
            os.remove(filename)
            return {'path': None, 'too_large': True}

        return {'path': filename, 'too_large': False}