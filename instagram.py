import os
import yt_dlp
from config import FFMPEG_PATH, MAX_SIZE_BYTES

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)



def is_instagram_url(text: str) -> bool:
    return 'instagram.com' in text


def download_instagram_video(url: str) -> dict:
    output_template = os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s')
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,
        'quiet': True,
        'merge_output_format': 'mp4',
    }
    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace('.webm', '.mp4').replace('.mkv', '.mp4')

        if os.path.exists(filename) and os.path.getsize(filename) > MAX_SIZE_BYTES:
            os.remove(filename)
            return {'path': None, 'too_large': True, 'direct_url': info['webpage_url']}

        return {'path': filename, 'too_large': False, 'direct_url': None}
