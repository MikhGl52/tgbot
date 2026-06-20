# TG Bot — YouTube & Instagram Downloader

## Установка

```bash
git clone <repo_url>
cd tgbot

python3 -m venv .venv
source .venv/bin/activate       # Linux
# или .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

## Конфиг

```bash
cp config.example.py config.py
nano config.py  # вставь свой токен
```

## FFmpeg

**Linux (VPS):**
```bash
sudo apt update && sudo apt install ffmpeg -y
```

**Windows:**  
Скачай с https://ffmpeg.org/download.html, распакуй в папку `ffmpeg/` в корне проекта.

## Запуск

```bash
python run.py
```

## Структура

```
tgbot/
├── run.py              # точка входа
├── config.py           # токен и пути (не в git)
├── config.example.py   # шаблон конфига
├── database.py         # SQLite, хранение пользователей
├── youtube.py          # yt-dlp логика для YouTube
├── instagram.py        # yt-dlp логика для Instagram
├── requirements.txt
└── handlers/
    ├── common.py       # /start, /menu, выбор сервиса
    └── youtube.py      # хэндлеры скачивания
```
