import os
import platform

MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

TOKEN = "YOUR_BOT_TOKEN_HERE"

SPOTIFY_CLIENT_ID = "YOUR_SPOTIFY_CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "YOUR_SPOTIFY_CLIENT_SECRET"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if platform.system() == 'Windows':
    FFMPEG_PATH = os.path.join(BASE_DIR, 'ffmpeg', 'bin')
else:
    FFMPEG_PATH = None