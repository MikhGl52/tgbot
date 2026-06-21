import asyncio
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.memory import MemoryStorage
from typing import Callable, Awaitable, Any
from config import TOKEN, USE_LOCAL_API, PROXY
from database import init_db, upsert_user
from handlers.common import router as common_router
from handlers.youtube import router as youtube_router
from handlers.music import router as music_router
from handlers.queue import router as queue_router
import glob
import os


class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict
    ) -> Any:
        user = data.get('event_from_user')
        if user:
            await upsert_user(user)
        return await handler(event, data)


dp = Dispatcher(storage=MemoryStorage())
dp.update.middleware(UserTrackingMiddleware())
dp.include_router(common_router)
dp.include_router(queue_router)
dp.include_router(youtube_router)
dp.include_router(music_router)
async def main():
    for f in glob.glob('downloads/*'):
        try:
            os.remove(f)
        except Exception:
            pass

    await init_db()
    if USE_LOCAL_API:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base('http://telegram-bot-api:8081'),
            timeout=7200
        )
    else:
        session = AiohttpSession(proxy=PROXY)
    bot = Bot(token=TOKEN, session=session)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')