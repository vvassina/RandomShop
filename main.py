import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
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

yuan_rate = float(os.getenv("YUAN_RATE", 11.5))  # курс юаня
user_data = {}

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💴 Рассчитать стоимость заказа"))
    kb.add(KeyboardButton("🛍 Оформить заказ"))
    return kb

async def send_start_photo(chat_id):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(chat_id, photo, caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"Error sending start photo: {e}")
        await bot.send_message(chat_id, "Привет! Я помогу рассчитать стоимость и оформить заказ.", reply_markup=main_menu())

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_data[message.chat.id] = {}
    await send_start_photo(message.chat.id)

@dp.message_handler(lambda m: m.text == "💴 Рассчитать стоимость заказа")
async def start_price_calc(message: types.Message):
    user_data[message.chat.id] = {"state": "waiting_category"}
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in CATEGORY_FEES.keys():
        kb.add(KeyboardButton(cat))
    kb.add(KeyboardButton("Вернуться в начало"))
    await message.answer("Выберите категорию товара:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_category")
async def handle_category(message: types.Message):
    if message.text == "Вернуться в начало":
        user_data[message.chat.id] = {}
        return await send_start_photo(message.chat.id)
    if message.text not in CATEGORY_FEES:
        return await message.answer("Пожалуйста, выберите категорию из списка.")
    user_data[message.chat.id]["category"] = message.text
    user_data[message.chat.id]["state"] = "waiting_price"
    try:
        media = types.MediaGroup()
        media.attach_photo(InputFile("order_price_1.jpg"))
        media.attach_photo(InputFile("order_price_2.jpg"))
        media.attach_photo(InputFile("order_price_3.jpg"))
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.error(f"Error sending price images: {e}")
    await message.answer("Введите стоимость товара в юанях (только число):")

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_price")
async def handle_price(message: types.Message):
    text = message.text.replace(",", ".")
    try:
        price = float(text)
        user_data[message.chat.id]["price"] = price
        fixed_fee = CATEGORY_FEES[user_data[message.chat.id]["category"]]
        rub_no_fee = round(price * yuan_rate, 2)
        rub = round(rub_no_fee + fixed_fee, 2)
        user_data[message.chat.id]["fixed_fee"] = fixed_fee
        user_data[message.chat.id]["rub_no_fee"] = rub_no_fee
        user_data[message.chat.id]["total_rub"] = rub
        user_data[message.chat.id]["state"] = "done"

        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("Изменить скрин", callback_data="edit_screenshot"),
            InlineKeyboardButton("Изменить размер", callback_data="edit_size"),
            InlineKeyboardButton("Изменить стоимость", callback_data="edit_price"),
            InlineKeyboardButton("✅ Всё верно!", callback_data="confirm_order")
        )

        # Если размер еще не выбран — спросим
        if "size" not in user_data[message.chat.id]:
            user_data[message.chat.id]["state"] = "waiting_size"
            await message.answer("Пришлите размер (если нет — пришлите 0):")
            return

        # Отправляем итоговое сообщение с кнопками
        size = user_data[message.chat.id].get("size", "0")
        await message.answer(
            f"💸 Итоговая сумма: {rub} ₽\n"
            f"🔹 Стоимость: ¥{price} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
            f"🔹 Комиссия: {fixed_fee} ₽\n"
            f"📏 Размер: {size}\n\n"
            f"🚚 Условия доставки:\n"
            f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n"
            f"📦 Точную стоимость доставки скажет менеджер.",
            reply_markup=kb
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число стоимости в юанях.")

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_size")
async def handle_size(message: types.Message):
    user_data[message.chat.id]["size"] = message.text
    user_data[message.chat.id]["state"] = "waiting_price"
    await message.answer("Введите стоимость товара в юанях (только число):")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("edit_"))
async def process_edit_callback(callback_query: types.CallbackQuery):
    action = callback_query.data
    chat_id = callback_query.message.chat.id

    if action == "edit_screenshot":
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(chat_id, "Пришлите скрин товара:")
        user_data[chat_id]["state"] = "waiting_screenshot"
    elif action == "edit_size":
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(chat_id, "Пришлите размер (если нет — 0):")
        user_data[chat_id]["state"] = "waiting_size"
    elif action == "edit_price":
        await bot.answer_callback_query(callback_query.id)
        try:
            media = types.MediaGroup()
            media.attach_photo(InputFile("order_price_1.jpg"))
            media.attach_photo(InputFile("order_price_2.jpg"))
            media.attach_photo(InputFile("order_price_3.jpg"))
            await bot.send_media_group(chat_id, media)
        except Exception as e:
            logging.error(f"Error sending price images: {e}")
        await bot.send_message(chat_id, "Введите стоимость товара в юанях (только число):")
        user_data[chat_id]["state"] = "waiting_price"

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_screenshot", content_types=types.ContentType.PHOTO)
async def handle_screenshot(message: types.Message):
    photos = message.photo
    if not photos:
        await message.answer("Пожалуйста, пришлите изображение (скрин товара).")
        return
    # Сохраняем file_id для показа в финальном сообщении
    user_data[message.chat.id]["screenshot_file_id"] = photos[-1].file_id
    user_data[message.chat.id]["state"] = "waiting_size"
    await message.answer("Скрин сохранён. Теперь пришлите размер (если нет — 0):")

@dp.callback_query_handler(lambda c: c.data == "confirm_order")
async def confirm_order(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = user_data.get(chat_id, {})
    if not data:
        await bot.answer_callback_query(callback_query.id, text="Данные не найдены. Начните сначала.")
        return

    size = data.get("size", "0")
    price = data.get("price", 0)
    fixed_fee = data.get("fixed_fee", 0)
    rub_no_fee = data.get("rub_no_fee", 0)
    total_rub = data.get("total_rub", 0)
    screenshot_file_id = data.get("screenshot_file_id")

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("Связаться с менеджером", url="https://t.me/dadmaksi"))
    kb.add(InlineKeyboardButton("Вернуться в начало", callback_data="restart"))

    text = (
        f"📋 Итоговый заказ:\n"
        f"📸 Товар (скрин):\n"
    )
    if screenshot_file_id:
        await bot.send_photo(chat_id, screenshot_file_id)
    text += (
        f"📏 Размер: {size}\n"
        f"💰 Стоимость: ¥{price} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
        f"💸 Комиссия: {fixed_fee} ₽\n"
        f"💳 Итого: {total_rub} ₽\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
        f"Перешлите это сообщение менеджеру для оформления заказа."
    )

    await bot.send_message(chat_id, text, reply_markup=kb)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == "restart")
async def restart(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    user_data[chat_id] = {}
    await bot.answer_callback_query(callback_query.id)
    await send_start_photo(chat_id)

@dp.message_handler(lambda m: m.text == "🛍 Оформить заказ")
async def start_order_process(message: types.Message):
    user_data[message.chat.id] = {"state": "waiting_screenshot_order"}
    await message.answer("Пришлите скрин товара:")

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_screenshot_order", content_types=types.ContentType.PHOTO)
async def order_handle_screenshot(message: types.Message):
    photos = message.photo
    if not photos:
        await message.answer("Пожалуйста, пришлите изображение (скрин товара).")
        return
    user_data[message.chat.id]["screenshot_file_id"] = photos[-1].file_id
    user_data[message.chat.id]["state"] = "waiting_size_order"
    await message.answer("Пришлите размер (если нет — 0):")

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_size_order")
async def order_handle_size(message: types.Message):
    user_data[message.chat.id]["size"] = message.text
    user_data[message.chat.id]["state"] = "waiting_price_order"
    try:
        media = types.MediaGroup()
        media.attach_photo(InputFile("order_price_1.jpg"))
        media.attach_photo(InputFile("order_price_2.jpg"))
        media.attach_photo(InputFile("order_price_3.jpg"))
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.error(f"Error sending price images: {e}")
    await message.answer("Пришлите стоимость товара в юанях (только число):")

@dp.message_handler(lambda m: user_data.get(m.chat.id, {}).get("state") == "waiting_price_order")
async def order_handle_price(message: types.Message):
    text = message.text.replace(",", ".")
    try:
        price = float(text)
        user_data[message.chat.id]["price"] = price
        fixed_fee = 0  # Здесь по желанию можно ставить комиссию для оформления заказа
        rub_no_fee = round(price * yuan_rate, 2)
        rub = round(rub_no_fee + fixed_fee, 2)
        user_data[message.chat.id]["fixed_fee"] = fixed_fee
        user_data[message.chat.id]["rub_no_fee"] = rub_no_fee
        user_data[message.chat.id]["total_rub"] = rub
        user_data[message.chat.id]["state"] = "order_done"

        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("Оформить заказ заново", callback_data="restart_order"),
            InlineKeyboardButton("✅ Всё верно!", callback_data="confirm_order_order")
        )

        size = user_data[message.chat.id].get("size", "0")
        await message.answer(
            f"📸 Скрин товара сохранён.\n"
            f"📏 Размер: {size}\n"
            f"💰 Стоимость в юанях: ¥{price}\n"
            f"💸 Итог (без комиссии): {rub_no_fee} ₽\n\n"
            f"Перешлите это сообщение менеджеру или нажмите кнопку ниже.",
            reply_markup=kb
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число стоимости в юанях.")

@dp.callback_query_handler(lambda c: c.data == "restart_order")
async def restart_order(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    user_data[chat_id] = {"state": "waiting_screenshot_order"}
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(chat_id, "Пришлите скрин товара:")

@dp.callback_query_handler(lambda c: c.data == "confirm_order_order")
async def confirm_order_order(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = user_data.get(chat_id, {})
    if not data:
        await bot.answer_callback_query(callback_query.id, text="Данные не найдены. Начните сначала.")
        return

    screenshot_file_id = data.get("screenshot_file_id")
    size = data.get("size", "0")
    price = data.get("price", 0)
    rub_no_fee = data.get("rub_no_fee", 0)

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("Связаться с менеджером", url="https://t.me/dadmaksi"))
    kb.add(InlineKeyboardButton("Вернуться в начало", callback_data="restart"))

    text = (
        f"📋 Итоговый заказ:\n"
        f"📸 Товар (скрин):\n"
    )
    if screenshot_file_id:
        await bot.send_photo(chat_id, screenshot_file_id)
    text += (
        f"📏 Размер: {size}\n"
        f"💰 Стоимость: ¥{price}\n"
        f"💸 Итог: {rub_no_fee} ₽\n\n"
        f"Перешлите это сообщение менеджеру для оформления заказа."
    )

    await bot.send_message(chat_id, text, reply_markup=kb)
    await bot.answer_callback_query(callback_query.id)

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
