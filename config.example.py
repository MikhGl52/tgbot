import os
import platform

TOKEN = "YOUR_BOT_TOKEN_HERE"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if platform.system() == 'Windows':
    FFMPEG_PATH = os.path.join(BASE_DIR, 'ffmpeg', 'bin')
else:
    FFMPEG_PATH = None  # на Linux ffmpeg ставится через apt
