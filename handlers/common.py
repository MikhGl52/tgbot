from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

router = Router()


def service_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='▶️ YouTube', callback_data='service_youtube')],
        [InlineKeyboardButton(text='📷 Instagram', callback_data='service_instagram')],
        [InlineKeyboardButton(text='🎵 Music', callback_data='service_music')],
    ])


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    msg = await message.answer(
        '👋 Hi! Choose a service to download from:',
        reply_markup=service_menu()
    )
    await state.update_data(service_msg_id=msg.message_id)


@router.message(F.text == '/menu')
async def menu(message: Message, state: FSMContext):
    await state.clear()
    msg = await message.answer('Choose a service::', reply_markup=service_menu())
    await state.update_data(service_msg_id=msg.message_id)


@router.message(F.text == '/youtube')
async def cmd_youtube(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(service='youtube')
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Cancel service selection', callback_data='reset_service')]
    ])
    msg = await message.answer('✅ Service selected: YouTube\nNow send a link or a title.', reply_markup=markup)
    await state.update_data(service_msg_id=msg.message_id)


@router.message(F.text == '/instagram')
async def cmd_instagram(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(service='instagram')
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Cancel service selection', callback_data='reset_service')]
    ])
    msg = await message.answer('✅ Service selected: Instagram\nSend a link to a Reels or post.', reply_markup=markup)
    await state.update_data(service_msg_id=msg.message_id)


@router.message(F.text == '/music')
async def cmd_music(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(service='music')
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Cancel service selection', callback_data='reset_service')]
    ])
    msg = await message.answer('✅ Service selected: Music\nSend a track name or artist.', reply_markup=markup)
    await state.update_data(service_msg_id=msg.message_id)


@router.message(F.text == '/help')
async def help_cmd(message: Message):
    await message.answer(
        '📖 <b>Available commands:</b>\n\n'
        '/start — Start the bot\n'
        '/menu — Open service selection\n'
        '/youtube — Download from YouTube\n'
        '/instagram — Download from Instagram\n'
        '/music — Download music (MP3 320kbps)\n'
        '/queue — Show your download queue\n'
        '/help — Show this message\n\n'
        '📌 <b>How to use:</b>\n'
        '• Send a YouTube/Instagram link to download\n'
        '• Send a title to search on YouTube or Music\n'
        '• You can queue multiple downloads at once',
        parse_mode='HTML'
    )

@router.callback_query(F.data.startswith('service_'))
async def on_service_chosen(call: CallbackQuery, state: FSMContext):
    await state.clear()
    service = call.data.split('_', 1)[1]
    await state.update_data(service=service, service_msg_id=call.message.message_id)
    labels = {'youtube': 'YouTube', 'instagram': 'Instagram', 'music': 'Music'}
    label = labels.get(service, service)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Cancel service selection', callback_data='reset_service')]
    ])
    await call.message.edit_text(
        f'✅ Service selected: {label}\nNow send a link or a title.',
        reply_markup=markup
    )
    await call.answer()


@router.callback_query(F.data == 'reset_service')
async def on_reset_service(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text('Choose a service:', reply_markup=service_menu())
    await state.update_data(service_msg_id=call.message.message_id)
    await call.answer()


@router.callback_query(F.data == 'cancel')
async def on_cancel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_msg_id = data.get('user_msg_id')
    service = data.get('service')
    await state.clear()
    await state.update_data(service=service)
    await call.message.delete()
    if user_msg_id:
        try:
            await call.bot.delete_message(call.message.chat.id, user_msg_id)
        except Exception:
            pass
    await call.answer()
