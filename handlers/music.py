import os
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from music import search_music, download_music
from handlers.common import service_menu

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
            text=f"{i+1}. {r['title'][:50]} [{r['duration']}]",
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
    url = data['music_results'][idx]['url']
    service = data.get('service')

    await call.message.edit_text('⬇️ Downloading...')
    await call.answer()

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, download_music, url)
    except Exception as e:
        await call.message.edit_text(f'Error: {e}')
        await state.clear()
        await state.update_data(service=service)
        return

    if result['too_large']:
        await call.message.edit_text('❌ File is too large for Telegram (>50MB).')
    else:
        await call.message.edit_text('📤 Sending...')
        await call.message.answer_audio(FSInputFile(result['path']), request_timeout=7200)
        os.remove(result['path'])
        await call.message.delete()

    msg = await call.message.answer('Choose a service:', reply_markup=service_menu())
    await state.clear()
    await state.update_data(service=service, service_msg_id=msg.message_id)