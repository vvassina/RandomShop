import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

CATEGORY_FEES = {
    "Обувь/Куртки": 1000,
    "Джинсы/Кофты": 800,
    "Штаны/Юбки/Платья": 600,
    "Футболки/Аксессуары": 600,
    "Часы/Украшения": 1000,
    "Сумки/Рюкзаки": 900,
    "Техника/Другое": 0
}

yuan_rate = float(os.getenv("YUAN_RATE", 11.5))
current_category = None

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💸 Рассчитать стоимость", "🛍 Оформить заказ")
    return markup

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
                reply_markup=get_main_menu()
            )
    except:
        await message.answer("Добро пожаловать!", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.text == "💸 Рассчитать стоимость")
async def show_categories(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*CATEGORY_FEES.keys())
    markup.add("🔙 Вернуться в начало")
    await message.answer("Выберите категорию товара:", reply_markup=markup)

@dp.message_handler(lambda message: message.text in CATEGORY_FEES)
async def handle_category(message: types.Message):
    global current_category
    current_category = message.text

    if current_category == "Техника/Другое":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Такое считаем индивидуально, напишите нашему менеджеру 😊", reply_markup=kb)
        return

    try:
        with open("price_input.jpg", "rb") as photo:
            await bot.send_photo(message.chat.id, photo, caption="Введите стоимость в юанях (¥):")
    except:
        await message.answer("Введите стоимость в юанях (¥):")

@dp.message_handler(lambda message: message.text.replace(',', '').replace('.', '').isdigit())
async def calculate_total(message: types.Message):
    global current_category
    if not current_category:
        return
    try:
        yuan = float(message.text.replace(",", "."))
        fixed_fee = CATEGORY_FEES[current_category]
        rub_no_fee = round(yuan * yuan_rate, 2)
        rub = round(rub_no_fee + fixed_fee, 2)

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🛍 Перейти к оформлению заказа", "🔙 Вернуться в начало")

        await message.answer(
            f"💸 Итоговая сумма: {rub} ₽\n\n"
            f"🔹 Стоимость: ¥{yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
            f"🔹 Комиссия: {fixed_fee} ₽\n\n"
            f"🚚 Условия доставки:\n"
            f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
            f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!",
            reply_markup=markup
        )
    except:
        await message.answer("Ошибка расчёта. Попробуйте снова.")
    current_category = None

@dp.message_handler(lambda m: m.text == "🔙 Вернуться в начало")
async def go_back(message: types.Message):
    await start(message)

# --------------------------- FSM ORDERING ---------------------------

class OrderStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_size = State()
    waiting_for_price = State()
    confirming = State()

user_data = {}

@dp.message_handler(lambda m: m.text == "🛍 Оформить заказ" or m.text == "🛍 Перейти к оформлению заказа")
async def order_start(message: types.Message):
    await message.answer("Пришлите скрин товара 📸")
    await OrderStates.waiting_for_photo.set()

@dp.message_handler(content_types=types.ContentType.PHOTO, state=OrderStates.waiting_for_photo)
async def order_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Напишите размер товара (если нет — отправьте 0):")
    await OrderStates.waiting_for_size.set()

@dp.message_handler(state=OrderStates.waiting_for_size)
async def order_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)

    media = [
        InputMediaPhoto(media=open("order_price_1.jpg", "rb")),
        InputMediaPhoto(media=open("order_price_2.jpg", "rb")),
        InputMediaPhoto(media=open("order_price_3.jpg", "rb")),
    ]
    await bot.send_media_group(chat_id=message.chat.id, media=media)
    await message.answer("Пришлите стоимость товара в юанях (¥):")
    await OrderStates.waiting_for_price.set()

@dp.message_handler(lambda m: m.text.replace(",", "").replace(".", "").isdigit(), state=OrderStates.waiting_for_price)
async def order_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    data = await state.get_data()

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Изменить скрин", callback_data="change_photo"),
        InlineKeyboardButton("Изменить размер", callback_data="change_size"),
        InlineKeyboardButton("Изменить цену", callback_data="change_price"),
    )
    kb.add(InlineKeyboardButton("✅ Всё верно", callback_data="confirm_order"))

    await bot.send_photo(
        chat_id=message.chat.id,
        photo=data["photo"],
        caption=f"📷 Скрин: получен\n📏 Размер: {data['size']}\n💴 Цена: ¥{data['price']}",
        reply_markup=kb
    )
    await OrderStates.confirming.set()

@dp.callback_query_handler(lambda c: c.data.startswith("change_"), state=OrderStates.confirming)
async def handle_changes(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    if call.data == "change_photo":
        await call.message.answer("Пришлите новый скрин товара 📸")
        await OrderStates.waiting_for_photo.set()
    elif call.data == "change_size":
        await call.message.answer("Введите новый размер:")
        await OrderStates.waiting_for_size.set()
    elif call.data == "change_price":
        await call.message.answer("Введите новую цену в юанях:")
        await OrderStates.waiting_for_price.set()

@dp.callback_query_handler(lambda c: c.data == "confirm_order", state=OrderStates.confirming)
async def confirm_order(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
    await bot.send_photo(
        chat_id=call.message.chat.id,
        photo=data["photo"],
        caption=(
            f"📦 Финальное сообщение:\n"
            f"📷 Скрин: получен\n📏 Размер: {data['size']}\n💴 Цена: ¥{data['price']}\n\n"
            f"Перешлите итоговое сообщение менеджеру 👇"
        ),
        reply_markup=markup
    )
    await state.finish()

# ---------------------------

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
