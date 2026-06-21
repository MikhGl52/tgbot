import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from youtube import is_youtube_url, search_videos, get_available_formats, download_video, MAX_SIZE_BYTES
from instagram import is_instagram_url, download_instagram_video
from handlers.common import service_menu
from handlers.music import handle_search as music_search
from queue_manager import queue_manager, DownloadTask
import time
from database import log_download



router = Router()


class DownloadStates(StatesGroup):
    choosing_video = State()
    choosing_quality = State()


async def process_queue(user_id: int, bot: Bot, chat_id: int):
    import time
    from database import log_download

    while True:
        task = queue_manager.get_next_task(user_id)
        if not task:
            queue_manager.set_processing(user_id, False)
            await bot.send_message(
                chat_id,
                '✅ All downloads completed! Choose a service:',
                reply_markup=service_menu()
            )
            return

        queue_manager.set_processing(user_id, True)
        cancel_event = queue_manager.get_cancel_event(user_id)
        cancel_event.clear()

        cancel_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='❌ Cancel download', callback_data='cancel_download')]
        ])

        status_msg = await bot.send_message(
            chat_id,
            f'⬇️ <b>{task.title[:50]}</b>\n░░░░░░░░░░ 0%',
            reply_markup=cancel_markup,
            parse_mode='HTML'
        )

        queue = asyncio.Queue()
        last_percent = [-1]
        loop = asyncio.get_event_loop()
        start_time = time.time()

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
                    try:
                        await status_msg.edit_text(
                            f'⬇️ <b>{task.title[:50]}</b>\n'
                            f'{bar} {percent}%\n'
                            f'🚀 {speed_str} | ⏱ {eta_str}',
                            reply_markup=cancel_markup,
                            parse_mode='HTML'
                        )
                    except Exception:
                        pass
                except asyncio.TimeoutError:
                    continue

        progress_task = asyncio.create_task(update_progress())

        cancelled = False
        result = None
        try:
            if task.service == 'youtube':
                result = await loop.run_in_executor(
                    None, download_video, task.url, task.format_id, progress_callback, cancel_event
                )
            elif task.service == 'instagram':
                result = await loop.run_in_executor(
                    None, download_instagram_video, task.url
                )
            elif task.service == 'music':
                from music import download_music
                result = await loop.run_in_executor(
                    None, download_music, task.url
                )
        except Exception as e:
            await queue.put(None)
            await progress_task
            if cancel_event.is_set():
                cancelled = True
                await status_msg.edit_text('🚫 Download cancelled.', reply_markup=None)
            else:
                await status_msg.edit_text(f'❌ Download error: {e}', reply_markup=None)
            queue_manager.complete_task(user_id)
            continue

        await queue.put(None)
        await progress_task

        elapsed = int(time.time() - start_time)
        time_str = f'{elapsed // 60}m {elapsed % 60}s' if elapsed >= 60 else f'{elapsed}s'

        if not cancelled and result:
            if task.service in ('youtube', 'instagram'):
                if result.get('parts'):
                    total = len(result['parts'])
                    await status_msg.edit_text(
                        f'📤 Sending {total} parts...', reply_markup=None
                    )
                    total_size = 0
                    for i, part_path in enumerate(result['parts'], 1):
                        total_size += os.path.getsize(part_path)
                        await bot.send_video(
                            chat_id, FSInputFile(part_path),
                            caption=f'Part {i}/{total}',
                            request_timeout=7200
                        )
                        os.remove(part_path)
                    await status_msg.delete()
                    size_str = f'{total_size / 1024 / 1024:.1f} MB'
                    await bot.send_message(
                        chat_id,
                        f'✅ <b>{task.title[:50]}</b>\n'
                        f'📦 Size: {size_str} | ⏱ Time: {time_str}',
                        parse_mode='HTML'
                    )
                    await log_download(user_id, task.service, task.title, task.url,
                                       task.quality or '', total_size, elapsed)

                elif result.get('path'):
                    file_size = os.path.getsize(result['path'])
                    size_str = f'{file_size / 1024 / 1024:.1f} MB'
                    await status_msg.edit_text('📤 Sending...', reply_markup=None)
                    await bot.send_video(
                        chat_id, FSInputFile(result['path']), request_timeout=7200
                    )
                    os.remove(result['path'])
                    await status_msg.delete()
                    await bot.send_message(
                        chat_id,
                        f'✅ <b>{task.title[:50]}</b>\n'
                        f'📦 Size: {size_str} | ⏱ Time: {time_str}',
                        parse_mode='HTML'
                    )
                    await log_download(user_id, task.service, task.title, task.url,
                                       task.quality or '', file_size, elapsed)

            elif task.service == 'music':
                if result.get('path'):
                    file_size = os.path.getsize(result['path'])
                    size_str = f'{file_size / 1024 / 1024:.1f} MB'
                    await status_msg.edit_text('📤 Sending...', reply_markup=None)
                    await bot.send_audio(
                        chat_id, FSInputFile(result['path']), request_timeout=7200
                    )
                    os.remove(result['path'])
                    await status_msg.delete()
                    await bot.send_message(
                        chat_id,
                        f'✅ <b>{task.title[:50]}</b>\n'
                        f'📦 Size: {size_str} | ⏱ Time: {time_str}',
                        parse_mode='HTML'
                    )
                    await log_download(user_id, task.service, task.title, task.url,
                                       task.quality or '', file_size, elapsed)

        queue_manager.complete_task(user_id)



@router.callback_query(F.data == 'cancel_download')
async def on_cancel_download(call: CallbackQuery):
    user_id = call.from_user.id
    if queue_manager.is_processing(user_id):
        queue_manager.cancel_current(user_id)
        await call.answer('Cancelling download...', show_alert=False)
    else:
        await call.answer('Nothing to cancel.', show_alert=True)

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
            text=f"{i+1}. {r['title'][:35]} — {r['channel'][:15]} [{r['duration']}]",
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
        formats, thumbnail, title = await loop.run_in_executor(None, get_available_formats, url)
    except Exception as e:
        await waiting_msg.delete()
        await message.answer(f'Error: {e}')
        return
    await waiting_msg.delete()

    data = await state.get_data()
    await state.update_data(
        url=url,
        user_msg_id=message.message_id,
        service=data.get('service'),
        video_title=title,
        thumbnail=thumbnail
    )
    await state.set_state(DownloadStates.choosing_quality)

    buttons = [
        [InlineKeyboardButton(text=f['label'], callback_data=f"quality_{f['label']}_{f['format_id']}")]
        for f in formats
    ]
    buttons.append([InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    if thumbnail:
        await message.answer_photo(
            URLInputFile(thumbnail),
            caption=f'🎬 <b>{title[:100]}</b>\n\nChoose quality:',
            reply_markup=markup,
            parse_mode='HTML'
        )
    else:
        await message.answer(f'🎬 <b>{title[:100]}</b>\n\nChoose quality:', reply_markup=markup, parse_mode='HTML')


# async def handle_instagram_url(message: Message, state: FSMContext, url: str):
#     user_id = message.from_user.id
#     task = DownloadTask(
#         user_id=user_id,
#         url=url,
#         format_id='best',
#         service='instagram',
#         title=url
#     )
#     position = queue_manager.add_task(task)

#     if position == -1:
#         await message.answer('⚠️ This video is already in your queue.')
#         return

#     if position > 1:
#         await message.answer(f'✅ Added to queue at position #{position}')

#     if not queue_manager.is_processing(user_id):
#         asyncio.create_task(process_queue(user_id, message.bot, message.chat.id))

async def handle_instagram_url(message: Message, state: FSMContext, url: str):
    await message.answer(
        '⚠️ Instagram downloading is temporarily unavailable due to platform restrictions.\n'
        'We apologize for the inconvenience and are working on a fix. Please try again later.'
    )

@router.callback_query(DownloadStates.choosing_video)
async def on_video_chosen(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split('_')[1])
    data = await state.get_data()
    url = data['search_results'][idx]['url']

    await call.message.edit_text('⏳ Getting available formats...')
    loop = asyncio.get_event_loop()
    try:
        formats, thumbnail, title = await loop.run_in_executor(None, get_available_formats, url)
    except Exception as e:
        await call.message.edit_text(f'Error: {e}')
        return
    await call.message.delete()

    await state.update_data(url=url, service=data.get('service'), video_title=title, thumbnail=thumbnail)
    await state.set_state(DownloadStates.choosing_quality)

    buttons = [
        [InlineKeyboardButton(text=f['label'], callback_data=f"quality_{f['label']}_{f['format_id']}")]
        for f in formats
    ]
    buttons.append([InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    if thumbnail:
        await call.message.answer_photo(
            URLInputFile(thumbnail),
            caption=f'🎬 <b>{title[:100]}</b>\n\nChoose quality:',
            reply_markup=markup,
            parse_mode='HTML'
        )
    else:
        await call.message.answer(f'🎬 <b>{title[:100]}</b>\n\nChoose quality:', reply_markup=markup, parse_mode='HTML')
    await call.answer()


MAX_QUEUE_SIZE = 5

@router.callback_query(DownloadStates.choosing_quality)
async def on_quality_chosen(call: CallbackQuery, state: FSMContext):
    parts = call.data.split('_', 2)
    format_id = parts[2]
    quality_label = parts[1]
    data = await state.get_data()
    url = data['url']
    service = data.get('service')
    title = data.get('video_title', url)
    user_id = call.from_user.id

    # Лимит очереди
    current_tasks = queue_manager.get_tasks(user_id)
    if len(current_tasks) >= MAX_QUEUE_SIZE:
        await call.answer(f'❌ Queue is full (max {MAX_QUEUE_SIZE} tasks).', show_alert=True)
        return

    task = DownloadTask(
        user_id=user_id,
        url=url,
        format_id=format_id,
        service='youtube',
        title=title,
        quality=quality_label
    )
    position = queue_manager.add_task(task)
    await call.answer()

    if position == -1:
        await call.message.answer('⚠️ This video is already in your queue.')
        return

    try:
        await call.message.delete()
    except Exception:
        pass

    msg = await call.message.answer('Choose a service:', reply_markup=service_menu())
    await state.clear()
    await state.update_data(service=service, service_msg_id=msg.message_id)

    if position > 1:
        await call.message.answer(f'✅ Added to queue at position #{position}')

    if not queue_manager.is_processing(user_id):
        asyncio.create_task(process_queue(user_id, call.bot, call.message.chat.id))

@router.message(DownloadStates.choosing_quality)
async def download_in_progress(message: Message):
    await message.answer('⏳ Your download is in progress, please wait...')