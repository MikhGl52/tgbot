import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from music import search_music, download_music
from handlers.common import service_menu
from aiogram.types import URLInputFile  



router = Router()


class MusicStates(StatesGroup):
    choosing_track = State()


async def handle_search(message: Message, state: FSMContext, query: str):
    searching_msg = await message.answer('🔍 Searching...')
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, search_music, query)
    await searching_msg.delete()

    if not results:
        await message.answer('Nothing found.')
        return

    data = await state.get_data()
    await state.update_data(
        music_results=results,
        user_msg_id=message.message_id,
        service=data.get('service')
    )
    await state.set_state(MusicStates.choosing_track)

    buttons = [
        [InlineKeyboardButton(
            text=f"{i+1}. {r['title'][:40]} — {r['channel'][:20]} [{r['duration']}]",
            callback_data=f"track_{i}"
        )]
        for i, r in enumerate(results)
    ]
    buttons.append([InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('Choose a track:', reply_markup=markup)

@router.callback_query(MusicStates.choosing_track)
async def on_track_chosen(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split('_')[1])
    data = await state.get_data()
    track = data['music_results'][idx]
    url = track['url']
    thumbnail = track.get('thumbnail', '')
    service = data.get('service')

    await call.answer()
    await call.message.delete()

    confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⬇️ Download', callback_data=f'music_confirm_{idx}')],
        [InlineKeyboardButton(text='❌ Cancel', callback_data='cancel')]
    ])

    if thumbnail:
        try:
            await call.message.answer_photo(
                URLInputFile(thumbnail),
                caption=f'🎵 <b>{track["title"][:100]}</b>\n👤 {track["channel"]}\n⏱ {track["duration"]}',
                reply_markup=confirm_markup,
                parse_mode='HTML'
            )
        except Exception:
            await call.message.answer(
                f'🎵 <b>{track["title"][:100]}</b>\n👤 {track["channel"]}',
                reply_markup=confirm_markup,
                parse_mode='HTML'
            )
    else:
        await call.message.answer(
            f'🎵 <b>{track["title"][:100]}</b>\n👤 {track["channel"]}',
            reply_markup=confirm_markup,
            parse_mode='HTML'
        )


@router.callback_query(F.data.startswith('music_confirm_'))
async def on_music_confirmed(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split('_')[2])
    data = await state.get_data()
    track = data['music_results'][idx]
    url = track['url']
    service = data.get('service')

    await call.answer()
    await call.message.delete()

    from queue_manager import queue_manager, DownloadTask
    task = DownloadTask(
        user_id=call.from_user.id,
        url=url,
        format_id='bestaudio',
        service='music',
        title=track['title'],
        quality='MP3 320kbps'
    )
    position = queue_manager.add_task(task)

    if position == -1:
        await call.message.answer('⚠️ This track is already in your queue.')
        return

    msg = await call.message.answer('Choose a service:', reply_markup=service_menu())
    await state.clear()
    await state.update_data(service=service, service_msg_id=msg.message_id)

    if position > 1:
        await call.message.answer(f'✅ Added to queue at position #{position}')

    from handlers.youtube import process_queue
    if not queue_manager.is_processing(call.from_user.id):
        asyncio.create_task(process_queue(call.from_user.id, call.bot, call.message.chat.id))