import asyncio
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from typing import Callable, Awaitable, Any
from config import TOKEN
from database import init_db, upsert_user
from handlers.common import router as common_router
from handlers.youtube import router as youtube_router
from handlers.music import router as music_router
from aiogram.client.telegram import TelegramAPIServer


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
dp.include_router(youtube_router)
dp.include_router(music_router)

async def main():
    await init_db()
    bot = Bot(
        token=TOKEN,
        server=TelegramAPIServer.from_base('http://telegram-bot-api:8081')
    )
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
