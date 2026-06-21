import os
import yt_dlp
from config import FFMPEG_PATH, MAX_SIZE_BYTES
import math
import subprocess

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


VALID_HEIGHTS = {144, 240, 360, 480, 720, 1080, 1440, 2160}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}   

def is_youtube_url(text: str) -> bool:
    return 'youtube.com' in text or 'youtu.be' in text


def search_videos(query: str) -> list[dict]:
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'http_headers': HEADERS,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f'ytsearch5:{query}', download=False)
        results = []
        for v in info['entries']:
            results.append({
                'title': v.get('title', 'Без названия'),
                'url': f"https://www.youtube.com/watch?v={v['id']}",
                'duration': str(v.get('duration', '?')) + 's',
                'channel': v.get('channel') or v.get('uploader', ''),
            })
        return results


def get_available_formats(url: str) -> tuple[list[dict], str, str]:
    ydl_opts = {
        'quiet': True,
        'noplaylist': True,
    }
    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        thumbnail = info.get('thumbnail', '')
        title = info.get('title', '')
        formats = []
        seen = set()
        for f in info['formats']:
            height = f.get('height')
            if not height or height not in VALID_HEIGHTS:
                continue
            if not f.get('vcodec') or f.get('vcodec') == 'none':
                continue
            label = f'{height}p'
            if label in seen:
                continue
            seen.add(label)
            formats.append({
                'label': label,
                'format_id': f'bestvideo[height={height}]+bestaudio/best[height={height}]',
                'height': height,
            })
        formats.sort(key=lambda x: x['height'])
        return formats, thumbnail, title

def split_video(input_path: str) -> list[str]:
    ffprobe = os.path.join(FFMPEG_PATH, 'ffprobe') if FFMPEG_PATH else 'ffprobe'
    ffmpeg_bin = os.path.join(FFMPEG_PATH, 'ffmpeg') if FFMPEG_PATH else 'ffmpeg'

    # Получаем длительность и размер
    result = subprocess.run([
        ffprobe, '-v', 'error',
        '-show_entries', 'format=duration,size',
        '-of', 'default=noprint_wrappers=1',
        input_path
    ], capture_output=True, text=True)

    duration = None
    total_size = os.path.getsize(input_path)

    for line in result.stdout.strip().split('\n'):
        if line.startswith('duration='):
            duration = float(line.split('=')[1])

    if not duration:
        raise Exception('Could not get video duration')

    # Считаем длительность каждой части через битрейт
    bytes_per_sec = total_size / duration
    part_duration = (MAX_SIZE_BYTES * 0.70) / bytes_per_sec  # 0.95 — запас 5%
    num_parts = math.ceil(duration / part_duration)

    base = os.path.splitext(input_path)[0]
    parts = []

    for i in range(num_parts):
        start = i * part_duration
        output = f"{base}_part{i+1}.mp4"
        subprocess.run([
            ffmpeg_bin, '-i', input_path,
            '-ss', str(start),
            '-t', str(part_duration),
            '-c', 'copy',
            output, '-y',
            '-loglevel', 'quiet'
        ])
        # Проверяем размер части
        if os.path.exists(output) and os.path.getsize(output) > MAX_SIZE_BYTES:
            os.remove(output)
            raise Exception(f'Part {i+1} is still too large -- try a lower quality')
        parts.append(output)

    return parts

def download_video(url: str, format_id: str, progress_callback=None, cancel_event=None) -> dict:
    output_template = os.path.join(DOWNLOAD_DIR, '%(id)s_%(height)s.%(ext)s')

    def progress_hook(d):
        if cancel_event and cancel_event.is_set():
            raise Exception('Download cancelled by user')
        if progress_callback and d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta', 0) or 0
            if total:
                percent = int(downloaded / total * 100)
                progress_callback(percent, speed, eta)

    ydl_opts = {
        'format': format_id,
        'outtmpl': output_template,
        'quiet': True,
        'merge_output_format': 'mp4',
        'concurrent_fragment_downloads': 4,
        'http_headers': HEADERS,
        'progress_hooks': [progress_hook],
        'noplaylist': True,  # <- добавь
    }
    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace('.webm', '.mp4').replace('.mkv', '.mp4')

        if os.path.getsize(filename) > MAX_SIZE_BYTES:
            parts = split_video(filename)
            os.remove(filename)
            return {'path': None, 'too_large': False, 'parts': parts, 'direct_url': None}

        return {'path': filename, 'too_large': False, 'parts': None, 'direct_url': None}