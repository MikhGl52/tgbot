import aiosqlite

DB_PATH = 'users.db'


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                last_name   TEXT,
                language    TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                service     TEXT,
                title       TEXT,
                url         TEXT,
                quality     TEXT,
                file_size   INTEGER,
                duration_sec INTEGER,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()


async def log_download(user_id: int, service: str, title: str, url: str,
                       quality: str, file_size: int, duration_sec: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO downloads (user_id, service, title, url, quality, file_size, duration_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, service, title, url, quality, file_size, duration_sec))
        await db.commit()

async def upsert_user(user):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, language)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                language   = excluded.language
        ''', (
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            user.language_code
        ))
        await db.commit()
