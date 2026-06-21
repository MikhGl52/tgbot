import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from youtube import is_youtube_url, search_videos, get_available_formats, download_video, MAX_SIZE_BYTES
from instagram import is_instagram_url, download_instagram_video
from handlers.common import service_menu
from handlers.music import handle_search as music_search

router = Router()


class DownloadStates(StatesGroup):
    choosing_video = State()
    choosing_quality = State()


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    data = await state.get_data()
    service = data.get('service')

    if service is None:
        msg = await message.answer('Please choose a service first:', reply_markup=service_menu())
        await state.update_data(service_msg_id=msg.message_id)
        return

    service_msg_id = data.get('service_msg_id')
    if service_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, service_msg_id)
        except Exception:
            pass

    text = message.text.strip()

    if service == 'youtube':
        if is_youtube_url(text):
            await handle_url(message, state, text)
        else:
            await handle_search(message, state, text)
    elif service == 'instagram':
        if is_instagram_url(text):
            await handle_instagram_url(message, state, text)
        else:
            await message.answer('Send a link to an Instagram video or Reels.')
    elif service == 'music':
        await music_search(message, state, text)


async def handle_search(message: Message, state: FSMContext, text: str):
    searching_msg = await message.answer('🔍 Searching...')
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_videos, text)
    await searching_msg.delete()

    if not results:
        await message.answer('Nothing found.')
        return

    data = await state.get_data()
    await state.update_data(
        search_results=results,
        user_msg_id=message.message_id,
        service=data.get('service')
    )
    await state.set_state(DownloadStates.choosing_video)

    buttons = [
        [InlineKeyboardButton(
            text=f"{i+1}. {r['title'][:50]} [{r['duration']}]",
            callback_data=f"video_{i}"
        )]
        for i, r in enumerate(results)
    ]
    buttons.append([InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('Choose a video:', reply_markup=markup)


async def handle_url(message: Message, state: FSMContext, url: str):
    waiting_msg = await message.answer('⏳ Getting available formats...')
    loop = asyncio.get_event_loop()
    try:
        formats = await loop.run_in_executor(None, get_available_formats, url)
    except Exception as e:
        await waiting_msg.delete()
        await message.answer(f'Error: {e}')
        return
    await waiting_msg.delete()

    data = await state.get_data()
    await state.update_data(url=url, user_msg_id=message.message_id, service=data.get('service'))
    await state.set_state(DownloadStates.choosing_quality)

    buttons = [
        [InlineKeyboardButton(text=f['label'], callback_data=f"quality_{f['label']}_{f['format_id']}")]
        for f in formats
    ]
    buttons.append([InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('Choose quality:', reply_markup=markup)


async def handle_instagram_url(message: Message, state: FSMContext, url: str):
    waiting_msg = await message.answer('⬇️ Downloading...')
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, download_instagram_video, url)
    except Exception as e:
        await waiting_msg.edit_text(f'Error: {e}')
        return

    if result['too_large']:
        await waiting_msg.edit_text(
            f'❌ File is too large for Telegram (>{MAX_SIZE_BYTES // (1024 * 1024)}MB).\n'
            f'🔗 Download directly: {result["direct_url"]}'
        )
    else:
        await waiting_msg.edit_text('📤 Sending...')
        await message.answer_video(FSInputFile(result['path']), request_timeout=7200)
        os.remove(result['path'])
        await waiting_msg.delete()

    data = await state.get_data()
    service = data.get('service')
    await state.clear()
    msg = await message.answer('Choose a service:', reply_markup=service_menu())
    await state.update_data(service=service, service_msg_id=msg.message_id)


@router.callback_query(DownloadStates.choosing_video)
async def on_video_chosen(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split('_')[1])
    data = await state.get_data()
    url = data['search_results'][idx]['url']

    await call.message.edit_text('⏳ Getting available formats...')
    loop = asyncio.get_event_loop()
    try:
        formats = await loop.run_in_executor(None, get_available_formats, url)
    except Exception as e:
        await call.message.edit_text(f'Error: {e}')
        return
    await call.message.delete()

    await state.update_data(url=url, service=data.get('service'))
    await state.set_state(DownloadStates.choosing_quality)

    buttons = [
        [InlineKeyboardButton(text=f['label'], callback_data=f"quality_{f['label']}_{f['format_id']}")]
        for f in formats
    ]
    buttons.append([InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.answer('Choose quality:', reply_markup=markup)
    await call.answer()


@router.callback_query(DownloadStates.choosing_quality)
async def on_quality_chosen(call: CallbackQuery, state: FSMContext):
    parts = call.data.split('_', 2)
    format_id = parts[2]
    data = await state.get_data()
    url = data['url']
    service = data.get('service')

    status_msg = await call.message.edit_text('⬇️ Downloading...\n░░░░░░░░░░ 0%')
    await call.answer()

    queue = asyncio.Queue()
    last_percent = [-1]
    loop = asyncio.get_event_loop()

    def progress_callback(percent, speed, eta):
        if percent != last_percent[0] and percent % 5 == 0:
            last_percent[0] = percent
            asyncio.run_coroutine_threadsafe(
                queue.put((percent, speed, eta)), loop
            )

    async def update_progress():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
                if item is None:
                    break
                percent, speed, eta = item
                filled = int(percent / 10)
                bar = '█' * filled + '░' * (10 - filled)
                speed_str = f'{speed/1024/1024:.1f} MB/s' if speed else '...'
                if eta:
                    m, s = divmod(int(eta), 60)
                    eta_str = f'{m}m {s}s' if m else f'{s}s'
                else:
                    eta_str = '...'
                await status_msg.edit_text(
                    f'⬇️ Downloading...\n'
                    f'{bar} {percent}%\n'
                    f'🚀 {speed_str} | ⏱ {eta_str}'
                )
            except asyncio.TimeoutError:
                continue

    progress_task = asyncio.create_task(update_progress())

    try:
        result = await loop.run_in_executor(
            None, download_video, url, format_id, progress_callback
        )
    except Exception as e:
        await queue.put(None)
        await progress_task
        await status_msg.edit_text(f'Download error: {e}')
        await state.clear()
        await state.update_data(service=service)
        return

    await queue.put(None)
    await progress_task

    if result.get('parts'):
        total = len(result['parts'])
        await status_msg.edit_text(f'📤 Sending {total} parts...')
        for i, part_path in enumerate(result['parts'], 1):
            await call.message.answer_video(
                FSInputFile(part_path),
                caption=f'Part {i}/{total}',
                request_timeout=7200
            )
            os.remove(part_path)
        await status_msg.delete()
    elif result['path']:
        await status_msg.edit_text('📤 Sending...')
        await call.message.answer_video(
            FSInputFile(result['path']),
            request_timeout=7200
        )
        os.remove(result['path'])
        await status_msg.delete()

    msg = await call.message.answer('Choose a service:', reply_markup=service_menu())
    await state.clear()
    await state.update_data(service=service, service_msg_id=msg.message_id)