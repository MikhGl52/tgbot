import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from queue_manager import queue_manager

router = Router()


class QueueStates(StatesGroup):
    waiting_for_remove_index = State()


def format_queue_message(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    tasks = queue_manager.get_tasks(user_id)
    is_processing = queue_manager.is_processing(user_id)

    if not tasks:
        return '📭 Your queue is empty.', None

    lines = ['📋 <b>Your download queue:</b>\n']
    for i, task in enumerate(tasks, 1):
        status = '⬇️ Downloading...' if i == 1 and is_processing else f'#{i}'
        lines.append(f'{status} <b>{task.title[:50]}</b> [{task.quality or task.service}]')

    text = '\n'.join(lines)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🗑 Remove from queue', callback_data='queue_remove')]
    ])
    return text, markup


@router.message(Command('queue'))
async def show_queue(message: Message):
    text, markup = format_queue_message(message.from_user.id)
    await message.answer(text, reply_markup=markup, parse_mode='HTML')


@router.callback_query(F.data == 'queue_remove')
async def on_queue_remove(call: CallbackQuery, state: FSMContext):
    tasks = queue_manager.get_tasks(call.from_user.id)
    is_processing = queue_manager.is_processing(call.from_user.id)

    removable = [t for i, t in enumerate(tasks) if not (i == 0 and is_processing)]
    if not removable:
        await call.answer('Nothing to remove.', show_alert=True)
        return

    await state.set_state(QueueStates.waiting_for_remove_index)
    await call.message.delete()
    await call.answer()
    await call.message.answer(
        '✏️ Send the number of the task you want to remove:\n'
        '(currently downloading task cannot be removed)'
    )


@router.message(QueueStates.waiting_for_remove_index)
async def on_remove_index(message: Message, state: FSMContext):
    await state.clear()
    try:
        index = int(message.text.strip())
    except ValueError:
        await message.answer('❌ Please send a valid number.')
        return

    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    success = queue_manager.remove_task(message.from_user.id, index)
    if not success:
        await message.answer('❌ Could not remove task. It may be downloading or index is invalid.')
        return

    text, markup = format_queue_message(message.from_user.id)
    await message.answer(text, reply_markup=markup, parse_mode='HTML')