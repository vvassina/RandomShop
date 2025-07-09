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
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

# Курс юаня
yuan_rate = float(os.getenv("YUAN_RATE", 11.5))

# Категории и комиссии (для "Рассчитать стоимость 💴")
CATEGORY_FEES = {
    "Обувь/Куртки": 1000,
    "Джинсы/Кофты": 800,
    "Штаны/Юбки/Платья": 600,
    "Футболки/Аксессуары": 600,
    "Часы/Украшения": 1000,
    "Сумки/Рюкзаки": 900,
    "Техника/Другое": 0
}

# FSM для оформления заказа (фото, размер, цена, подтверждение)
class OrderStates(StatesGroup):
    waiting_screenshot = State()
    waiting_size = State()
    waiting_price = State()
    waiting_confirmation = State()

# FSM для расчёта стоимости (категория, цена, итог)
class CalcStates(StatesGroup):
    waiting_category = State()
    waiting_price = State()

# Главное меню
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Рассчитать стоимость заказа 💴"))
    kb.add(KeyboardButton("Оформить заказ 🛍"))
    return kb

# Категории для расчёта стоимости
def categories_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in CATEGORY_FEES.keys():
        kb.add(KeyboardButton(cat))
    return kb

# Кнопки редактирования заказа (в один столбик)
def edit_order_markup():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Изменить скрин", callback_data="edit_screenshot"),
        InlineKeyboardButton("Изменить размер", callback_data="edit_size"),
        InlineKeyboardButton("Изменить стоимость", callback_data="edit_price"),
        InlineKeyboardButton("✅ Всё верно", callback_data="confirm_order")
    )
    return kb

# Кнопка менеджера
def manager_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
    return kb

# --- Обработчики ---

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет! 👋🏼\n\nЯ помогу рассчитать стоимость заказа или оформить заказ.",
                reply_markup=main_menu()
            )
    except Exception as e:
        logging.error(f"Error sending start photo: {e}")
        await message.answer("Привет! Выберите действие:", reply_markup=main_menu())

# Главное меню — обработка выбора
@dp.message_handler(lambda m: m.text in ["Рассчитать стоимость заказа 💴", "Оформить заказ 🛍"])
async def handle_main_menu(message: types.Message, state: FSMContext):
    if message.text == "Рассчитать стоимость заказа 💴":
        await message.answer("Выберите категорию товара:", reply_markup=categories_menu())
        await CalcStates.waiting_category.set()
    else:
        await message.answer("Пришлите скрин товара:")
        await OrderStates.waiting_screenshot.set()

# === Ветка расчёта стоимости ===

@dp.message_handler(state=CalcStates.waiting_category)
async def calc_category_chosen(message: types.Message, state: FSMContext):
    category = message.text
    if category not in CATEGORY_FEES:
        await message.answer("Пожалуйста, выберите категорию из списка.")
        return
    await state.update_data(category=category)
    if category == "Техника/Другое":
        await message.answer(
            "Такое считаем индивидуально. Напишите нашему менеджеру 😊",
            reply_markup=manager_button()
        )
        await state.finish()
        return
    # Отправляем три картинки с подсказками цен
    media = []
    for fname in ["order_price_1.jpg", "order_price_2.jpg", "order_price_3.jpg"]:
        try:
            media.append(InputMediaPhoto(open(fname, "rb")))
        except Exception as e:
            logging.error(f"Cannot open image {fname}: {e}")
    if media:
        await bot.send_media_group(message.chat.id, media)
    await message.answer("Введите стоимость товара в юанях (только цифры):")
    await CalcStates.waiting_price.set()

@dp.message_handler(state=CalcStates.waiting_price)
async def calc_price_entered(message: types.Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        price_yuan = float(text)
    except:
        await message.answer("Введите стоимость числом, например: 1500")
        return
    data = await state.get_data()
    category = data["category"]
    fee = CATEGORY_FEES[category]
    rub_no_fee = round(price_yuan * yuan_rate, 2)
    rub_total = rub_no_fee + fee

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Оформить заказ!🔥"))
    markup.add(KeyboardButton("Вернуться в начало"))

    await message.answer(
        f"💸 Итоговая сумма: {rub_total} ₽\n\n"
        f"🔹 Стоимость: ¥{price_yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
        f"🔹 Комиссия: {fee} ₽\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
        f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!",
        reply_markup=markup
    )
    await state.finish()

@dp.message_handler(lambda m: m.text == "Вернуться в начало")
async def return_to_start(message: types.Message):
    await message.answer("Вы вернулись в главное меню.", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "Оформить заказ!🔥")
async def go_to_order(message: types.Message):
    await message.answer("Пришлите скрин товара:")
    await OrderStates.waiting_screenshot.set()

# === Ветка оформления заказа ===

@dp.message_handler(state=OrderStates.waiting_screenshot, content_types=types.ContentType.PHOTO)
async def order_received_screenshot(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(screenshot=photo.file_id)
    await message.answer("Напишите размер (может быть буквенным или числовым). Если размера нет — пришлите 0.")
    await OrderStates.waiting_size.set()

@dp.message_handler(state=OrderStates.waiting_screenshot)
async def order_wrong_screenshot(message: types.Message):
    await message.answer("Пожалуйста, пришлите фото товара.")

@dp.message_handler(state=OrderStates.waiting_size)
async def order_received_size(message: types.Message, state: FSMContext):
    size = message.text.strip()
    await state.update_data(size=size)

    media = []
    for fname in ["order_price_1.jpg", "order_price_2.jpg", "order_price_3.jpg"]:
        try:
            media.append(InputMediaPhoto(open(fname, "rb")))
        except Exception as e:
            logging.error(f"Cannot open image {fname}: {e}")
    if media:
        await bot.send_media_group(message.chat.id, media)

    await message.answer("Введите стоимость товара в юанях (только цифры):")
    await OrderStates.waiting_price.set()

@dp.message_handler(state=OrderStates.waiting_price)
async def order_received_price(message: types.Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        price_yuan = float(text)
    except:
        await message.answer("Введите стоимость числом, например: 1500")
        return

    await state.update_data(price_yuan=price_yuan)
    data = await state.get_data()

    rub_no_fee = round(price_yuan * yuan_rate, 2)
    # комиссия не берём, только курс юаня
    caption = (
        f"📋 Итог заказа:\n"
        f"-------------------\n"
        f"📏 Размер: {data.get('size')}\n"
        f"💴 Стоимость: ¥{price_yuan}\n"
        f"💸 Итоговая сумма: {rub_no_fee} ₽ (курс {yuan_rate} ₽/¥)\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
        f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток."
    )

    await bot.send_photo(
        message.chat.id,
        data.get("screenshot"),
        caption=caption,
        reply_markup=edit_order_markup()
    )
    await OrderStates.waiting_confirmation.set()

# Обработка кнопок редактирования и подтверждения заказа
@dp.callback_query_handler(state=OrderStates.waiting_confirmation)
async def order_edit_callback(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if call.data == "edit_screenshot":
        await call.message.answer("Пришлите новый скрин товара:")
        await OrderStates.waiting_screenshot.set()
        await call.answer()
    elif call.data == "edit_size":
        await call.message.answer("Напишите новый размер (или 0, если нет):")
        await OrderStates.waiting_size.set()
        await call.answer()
    elif call.data == "edit_price":
        media = []
        for fname in ["order_price_1.jpg", "order_price_2.jpg", "order_price_3.jpg"]:
            try:
                media.append(InputMediaPhoto(open(fname, "rb")))
            except Exception as e:
                logging.error(f"Cannot open image {fname}: {e}")
        if media:
            await bot.send_media_group(call.message.chat.id, media)
        await call.message.answer("Введите новую стоимость в юанях (только цифры):")
        await OrderStates.waiting_price.set()
        await call.answer()
    elif call.data == "confirm_order":
        caption = call.message.caption or ""
        caption += "\n\n➡ Перешлите итоговое сообщение менеджеру для оформления заказа."
        await call.message.edit_caption(caption=caption, reply_markup=manager_button())
        await call.answer("Спасибо! Заказ оформлен.")
        await state.finish()

# --- Вебсервер (Render) ---
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

if __name__ == "__main__":
    asyncio.run(main())
