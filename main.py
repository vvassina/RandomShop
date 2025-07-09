import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto
)
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
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

# FSM states
class OrderFSM(StatesGroup):
    waiting_for_photo = State()
    waiting_for_size = State()
    waiting_for_category = State()
    waiting_for_price = State()
    waiting_for_price_photos = State()
    confirming_order = State()

user_orders = {}

def get_main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Посчитать стоимость заказа 💴")
    kb.add("Оформить заказ 🛍")
    return kb

def get_category_keyboard():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(*[KeyboardButton(cat) for cat in CATEGORY_FEES])

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_orders[message.chat.id] = []
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id, photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
                reply_markup=get_main_keyboard()
            )
    except:
        await message.answer("Привет! Я помогу вам с заказом.", reply_markup=get_main_keyboard())

@dp.message_handler(lambda m: m.text == "Посчитать стоимость заказа 💴")
async def price_calc_intro(message: types.Message):
    await message.answer("Выберите категорию товара для расчёта:", reply_markup=get_category_keyboard())

@dp.message_handler(lambda message: message.text in CATEGORY_FEES)
async def handle_category_calc(message: types.Message):
    category = message.text
    if category == "Техника/Другое":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Такое считаем индивидуально, напишите нашему менеджеру 😊", reply_markup=kb)
        return

    await message.answer("Введите стоимость в юанях (¥):")
    dp.register_message_handler(lambda m: True, lambda m: True, content_types=types.ContentTypes.TEXT)

@dp.message_handler(lambda m: m.text.replace(",", "").replace(".", "").isdigit())
async def calc_result(message: types.Message):
    yuan = float(message.text.replace(",", "."))
    category = None
    for cat in CATEGORY_FEES:
        if cat in message.text:
            category = cat
            break
    if not category:
        category = "Футболки/Аксессуары"  # default

    fee = CATEGORY_FEES[category]
    base = round(yuan * yuan_rate, 2)
    total = round(base + fee, 2)

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Оформить заказ!🔥", "Вернуться в начало")

    await message.answer(
        f"💸 Итоговая сумма: {total} ₽\n\n"
        f"🔹 Стоимость: ¥{yuan} × {yuan_rate} ₽ = {base} ₽\n"
        f"🔹 Комиссия: {fee} ₽\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.",
        reply_markup=markup
    )

@dp.message_handler(lambda m: m.text == "Оформить заказ!🔥")
@dp.message_handler(lambda m: m.text == "Оформить заказ 🛍")
async def start_order(message: types.Message):
    await message.answer("Шаг 1: Пришлите скриншот товара 🖼")
    await OrderFSM.waiting_for_photo.set()

@dp.message_handler(content_types=types.ContentTypes.PHOTO, state=OrderFSM.waiting_for_photo)
async def receive_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Шаг 2: Пришлите размер товара (например, L или 42)")
    await OrderFSM.waiting_for_size.set()

@dp.message_handler(state=OrderFSM.waiting_for_size)
async def receive_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Шаг 3: Выберите категорию товара", reply_markup=get_category_keyboard())
    await OrderFSM.waiting_for_category.set()

@dp.message_handler(state=OrderFSM.waiting_for_category)
async def receive_category(message: types.Message, state: FSMContext):
    if message.text not in CATEGORY_FEES:
        await message.answer("Пожалуйста, выберите категорию из меню.")
        return
    await state.update_data(category=message.text)
    await message.answer("Шаг 4: Введите стоимость товара в юанях (¥):")
    await OrderFSM.waiting_for_price.set()

@dp.message_handler(state=OrderFSM.waiting_for_price)
async def receive_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        await state.update_data(price=price)
        await message.answer("Шаг 5: Пришлите 3 фото товара (по одному)")
        await OrderFSM.waiting_for_price_photos.set()
        await state.update_data(price_photos=[])
    except:
        await message.answer("Введите корректную стоимость.")

@dp.message_handler(content_types=types.ContentTypes.PHOTO, state=OrderFSM.waiting_for_price_photos)
async def receive_price_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("price_photos", [])
    photos.append(message.photo[-1].file_id)

    await state.update_data(price_photos=photos)

    if len(photos) == 3:
        await finalize_order(message, state)
        await OrderFSM.confirming_order.set()
    else:
        await message.answer(f"Фото {len(photos)} загружено. Осталось {3 - len(photos)}.")

async def finalize_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = data['photo']
    size = data['size']
    category = data['category']
    price = data['price']
    photos = data['price_photos']

    fee = CATEGORY_FEES.get(category, 0)
    total = round(price * yuan_rate + fee, 2)

    user_orders.setdefault(message.chat.id, []).append({
        "category": category,
        "size": size,
        "price": price,
        "photos": photos,
        "total": total
    })

    count = len(user_orders[message.chat.id])
    summary = f"Ваш заказ:\nКоличество товаров: {count}"

    for idx, item in enumerate(user_orders[message.chat.id], 1):
        summary += f"\n\nТовар {idx} ⬇\nКатегория: {item['category']}\nРазмер: {item['size']}\nСтоимость: {item['total']} ₽"

    summary += "\n\n🚚 Условия доставки: 600₽/кг до Владивостока, далее по тарифу CDEK/Почты России."

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Изменить фото", "Изменить размер", "Изменить стоимость в юанях", "✅ Всё верно")

    await message.answer(summary, reply_markup=kb)

@dp.message_handler(lambda m: m.text == "✅ Всё верно", state=OrderFSM.confirming_order)
async def confirm_order(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Оформить заказ!🔥")
    kb.add("Добавить позиции в заказ")
    kb.add("Вернуться в начало")
    await message.answer("Отлично! Что делаем дальше?👇", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Оформить заказ!🔥", state="*")
async def finish_order(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Менеджер 👤", request_contact=False))
    kb.add("Вернуться назад")
    await message.answer("Перешлите итоговое сообщение нашему менеджеру 👇", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Менеджер 👤")
async def to_manager(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Начать заново 🔁")
    await message.answer("Свяжитесь с менеджером: https://t.me/dadmaksi", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Начать заново 🔁")
async def restart_order(message: types.Message, state: FSMContext):
    await state.finish()
    user_orders[message.chat.id] = []
    await start_handler(message)

@dp.message_handler(lambda m: m.text == "Добавить позиции в заказ")
async def add_more(message: types.Message):
    await start_order(message)

@dp.message_handler(lambda m: m.text == "Вернуться назад")
async def back_to_confirm(message: types.Message, state: FSMContext):
    await confirm_order(message, state)

# Web server for Render
async def handle(request):
    return web.Response(text="Bot is running")

async def start_webserver():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_webserver()
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
