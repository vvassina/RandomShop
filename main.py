import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, MediaGroup
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

# Категории и фиксированные комиссии (в рублях)
CATEGORY_FEES = {
    "Обувь/Куртки": 1000,
    "Джинсы/Кофты": 800,
    "Штаны/Юбки/Платья": 600,
    "Футболки/Аксессуары": 600,
    "Часы/Украшения": 1000,
    "Сумки/Рюкзаки": 900,
    "Техника/Другое": 0
}

yuan_rate = float(os.getenv("YUAN_RATE", 11.5))  # загружается из переменной окружения

class OrderForm(StatesGroup):
    waiting_for_screenshot = State()
    waiting_for_size = State()
    waiting_for_price = State()
    confirmation = State()

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Рассчитать стоимость заказа"))
    markup.add(KeyboardButton("Оформить заказ"))
    return markup

def order_confirmation_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Изменить скрин", callback_data="edit_screenshot"),
        InlineKeyboardButton("Изменить размер", callback_data="edit_size"),
        InlineKeyboardButton("Изменить стоимость", callback_data="edit_price")
    )
    kb.add(InlineKeyboardButton("Отправить менеджеру", url="https://t.me/dadmaksi"))
    kb.add(InlineKeyboardButton("Вернуться в начало", callback_data="restart"))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
                reply_markup=main_menu()
            )
    except Exception as e:
        logging.error(f"Error sending start photo: {e}")
        await message.answer("Привет! Я помогу Вам рассчитать стоимость товаров и оформить заказ!", reply_markup=main_menu())

@dp.message_handler(lambda message: message.text == "Рассчитать стоимость заказа")
async def start_calculation(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(*[KeyboardButton(cat) for cat in CATEGORY_FEES])
    await message.answer("Выберите категорию товара:", reply_markup=markup)

@dp.message_handler(lambda message: message.text in CATEGORY_FEES)
async def handle_category(message: types.Message):
    category = message.text

    if category == "Техника/Другое":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Такое считаем индивидуально, напишите нашему менеджеру 😊", reply_markup=kb)
        return

    state = dp.current_state(user=message.from_user.id)
    await state.update_data(category=category)

    media = MediaGroup()
    media.attach_photo(InputFile("price_example_1.jpg"))
    media.attach_photo(InputFile("price_example_2.jpg"))
    media.attach_photo(InputFile("price_example_3.jpg"))
    await bot.send_media_group(message.chat.id, media)

    await message.answer("Введите стоимость в юанях (¥):")

@dp.message_handler(lambda message: True)
async def calculate_price(message: types.Message):
    state = dp.current_state(user=message.from_user.id)
    data = await state.get_data()
    category = data.get("category")

    if not category:
        await message.answer("Пожалуйста, сначала выберите категорию через меню.", reply_markup=main_menu())
        return

    text = message.text.replace(",", ".")
    try:
        yuan = float(text)
    except ValueError:
        await message.answer("Пожалуйста, введите число для стоимости в юанях.")
        return

    fixed_fee = CATEGORY_FEES[category]
    rub_no_fee = round(yuan * yuan_rate, 2)
    rub = round(rub_no_fee + fixed_fee, 2)

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Оформить заказ!🔥", "Вернуться в начало")

    await message.answer(
        f"💸 Итоговая сумма: {rub} ₽\n\n"
        f"🔹 Стоимость: ¥{yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
        f"🔹 Комиссия: {fixed_fee} ₽\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
        f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!",
        reply_markup=markup
    )

@dp.message_handler(lambda message: message.text == "Вернуться в начало")
async def return_to_start(message: types.Message):
    await cmd_start(message)

@dp.message_handler(lambda message: message.text == "Оформить заказ")
async def start_order(message: types.Message):
    await OrderForm.waiting_for_screenshot.set()
    await message.answer("Пришлите скрин товара", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=OrderForm.waiting_for_screenshot, content_types=types.ContentType.PHOTO)
async def process_screenshot(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(screenshot_file_id=photo.file_id)
    await OrderForm.next()
    await message.answer("Напишите размер (если размера нет — пришлите 0)")

@dp.message_handler(state=OrderForm.waiting_for_screenshot)
async def process_wrong_screenshot(message: types.Message):
    await message.answer("Пожалуйста, пришлите скрин в формате фото.")

@dp.message_handler(state=OrderForm.waiting_for_size)
async def process_size(message: types.Message, state: FSMContext):
    size = message.text.strip()
    await state.update_data(size=size)
    await OrderForm.next()

    media = MediaGroup()
    media.attach_photo(InputFile("price_example_1.jpg"))
    media.attach_photo(InputFile("price_example_2.jpg"))
    media.attach_photo(InputFile("price_example_3.jpg"))
    await bot.send_media_group(message.chat.id, media)

    await message.answer("Теперь введите стоимость товара в юанях (¥):")

@dp.message_handler(state=OrderForm.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    text = message.text.replace(",", ".")
    try:
        price = float(text)
        if price < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число для стоимости.")
        return

    await state.update_data(price=price)
    data = await state.get_data()

    caption = (
        f"🛍 Ваш заказ:\n\n"
        f"📷 Скрин: прикреплён\n"
        f"📏 Размер: {data.get('size')}\n"
        f"💴 Стоимость: ¥{price}\n\n"
        f"Перешлите итоговое сообщение менеджеру."
    )

    await OrderForm.confirmation.set()
    await bot.send_photo(
        message.chat.id,
        photo=data['screenshot_file_id'],
        caption=caption,
        reply_markup=order_confirmation_kb()
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("edit_"), state=OrderForm.confirmation)
async def process_edit_callback(callback_query: types.CallbackQuery, state: FSMContext):
    action = callback_query.data

    if action == "edit_screenshot":
        await OrderForm.waiting_for_screenshot.set()
        await bot.send_message(callback_query.from_user.id, "Пришлите новый скрин товара")
    elif action == "edit_size":
        await OrderForm.waiting_for_size.set()
        await bot.send_message(callback_query.from_user.id, "Напишите новый размер (если нет — пришлите 0)")
    elif action == "edit_price":
        await OrderForm.waiting_for_price.set()

        media = MediaGroup()
        media.attach_photo(InputFile("price_example_1.jpg"))
        media.attach_photo(InputFile("price_example_2.jpg"))
        media.attach_photo(InputFile("price_example_3.jpg"))
        await bot.send_media_group(callback_query.from_user.id, media)

        await bot.send_message(callback_query.from_user.id, "Введите новую стоимость в юанях (¥):")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "restart", state='*')
async def restart_order(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await cmd_start(await bot.get_chat(callback_query.from_user.id))
    await callback_query.answer("Возвращаемся в начало")

# --- Веб-сервер для Render ---
async def handle(request):
    return web.Response(text="Bot is running")

async def start_webserver():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Webserver started on port {port}")

async def main():
    await start_webserver()
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
