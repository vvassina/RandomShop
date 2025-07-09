import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
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

yuan_rate = float(os.getenv("YUAN_RATE", 11.5))  # курс юаня

# FSM для оформления заказа
class ConfirmOrderStates(StatesGroup):
    waiting_for_screenshot = State()
    waiting_for_size = State()
    waiting_for_price = State()
    waiting_for_confirmation = State()

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Рассчитать стоимость заказа"), KeyboardButton("Оформить заказ"))
    return markup

def get_edit_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("Изменить скрин", callback_data="edit_screenshot"),
        InlineKeyboardButton("Изменить размер", callback_data="edit_size"),
        InlineKeyboardButton("Изменить стоимость", callback_data="edit_price"),
        InlineKeyboardButton("✅ Всё верно", callback_data="confirm_order")
    )
    return markup

def get_manager_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
    return markup

# Старт бота
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость заказа и оформить заказ!",
                reply_markup=get_main_menu()
            )
    except Exception as e:
        logging.error(f"Error sending start photo: {e}")
        await message.answer("Привет! Выберите действие:", reply_markup=get_main_menu())

# Обработка главного меню
@dp.message_handler(lambda message: message.text == "Рассчитать стоимость заказа")
async def start_cost_calc(message: types.Message):
    await message.answer("Этот функционал пока не реализован, используйте оформление заказа.")
    # Здесь можно вставить текущий функционал расчёта стоимости

@dp.message_handler(lambda message: message.text == "Оформить заказ")
async def start_order(message: types.Message, state: FSMContext):
    await message.answer("Пришлите скрин товара:")
    await ConfirmOrderStates.waiting_for_screenshot.set()

# Приём скрина
@dp.message_handler(state=ConfirmOrderStates.waiting_for_screenshot, content_types=types.ContentType.PHOTO)
async def order_screenshot_received(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(screenshot=photo.file_id)
    await message.answer("Напишите размер (может быть буквенным или числовым). Если размера нет, пришлите 0.")
    await ConfirmOrderStates.waiting_for_size.set()

@dp.message_handler(state=ConfirmOrderStates.waiting_for_screenshot, content_types=types.ContentType.ANY)
async def invalid_screenshot(message: types.Message):
    await message.answer("Пожалуйста, пришлите именно фото товара.")

# Приём размера
@dp.message_handler(state=ConfirmOrderStates.waiting_for_size)
async def order_size_received(message: types.Message, state: FSMContext):
    size = message.text.strip()
    await state.update_data(size=size)

    # Отправляем три картинки с подсказками по цене одним сообщением
    media = []
    for filename in ["order_price_1.jpg", "order_price_2.jpg", "order_price_3.jpg"]:
        try:
            media.append(InputMediaPhoto(open(filename, "rb")))
        except Exception as e:
            logging.error(f"Cannot open image {filename}: {e}")

    if media:
        await bot.send_media_group(message.chat.id, media)

    await message.answer("Введите стоимость товара в юанях (только цифры):")
    await ConfirmOrderStates.waiting_for_price.set()

# Приём цены и формирование итогового сообщения без шага телефона
@dp.message_handler(state=ConfirmOrderStates.waiting_for_price)
async def order_price_received(message: types.Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        price_yuan = float(text)
        await state.update_data(price_yuan=price_yuan)
        data = await state.get_data()

        rub_no_fee = round(price_yuan * yuan_rate, 2)
        rub_total = rub_no_fee

        caption = (
            f"📋 Итог заказа:\n"
            f"-------------------\n"
            f"📸 Скрин: (отправлено ниже)\n"
            f"📏 Размер: {data.get('size')}\n"
            f"💴 Стоимость: ¥{price_yuan}\n\n"
            f"💸 Итоговая сумма: {rub_total} ₽ (курс {yuan_rate} ₽/¥)\n\n"
            f"🚚 Условия доставки:\n"
            f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
            f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток."
        )

        await bot.send_photo(message.chat.id, data.get("screenshot"), caption=caption, reply_markup=get_edit_markup())
        await ConfirmOrderStates.waiting_for_confirmation.set()

    except ValueError:
        await message.answer("Пожалуйста, введите стоимость только цифрами, например: 1500")

# Обработка кнопок редактирования и подтверждения
@dp.callback_query_handler(state=ConfirmOrderStates.waiting_for_confirmation)
async def edit_order_callbacks(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if call.data == "edit_screenshot":
        await call.message.answer("Пришлите новый скрин товара:")
        await ConfirmOrderStates.waiting_for_screenshot.set()
        await call.answer()
    elif call.data == "edit_size":
        await call.message.answer("Напишите новый размер (или 0, если нет):")
        await ConfirmOrderStates.waiting_for_size.set()
        await call.answer()
    elif call.data == "edit_price":
        media = []
        for filename in ["order_price_1.jpg", "order_price_2.jpg", "order_price_3.jpg"]:
            try:
                media.append(InputMediaPhoto(open(filename, "rb")))
            except Exception as e:
                logging.error(f"Cannot open image {filename}: {e}")
        if media:
            await bot.send_media_group(call.message.chat.id, media)
        await call.message.answer("Введите новую стоимость в юанях (только цифры):")
        await ConfirmOrderStates.waiting_for_price.set()
        await call.answer()
    elif call.data == "confirm_order":
        caption = call.message.caption or ""
        caption += "\n\n➡ Перешлите итоговое сообщение менеджеру для оформления заказа."
        await call.message.edit_caption(caption=caption, reply_markup=get_manager_button())
        await call.answer("Спасибо! Заказ оформлен.")
        await state.finish()

# --- Обработка команд set yuan ---
@dp.message_handler(lambda message: message.text.lower().startswith("set yuan"))
async def set_yuan_rate(message: types.Message):
    global yuan_rate
    try:
        new_rate = float(message.text.split()[-1].replace(",", "."))
        yuan_rate = new_rate
        await message.answer(
            f"Новый курс юаня установлен: {yuan_rate} ₽ ✅\n\n"
            f"⚠ ВНИМАНИЕ: это временный курс. "
            f"При перезапуске он сбросится.\n"
            f"Чтобы сохранить навсегда — зайдите на Render и измените переменную YUAN_RATE."
        )
    except:
        await message.answer("Неверный формат. Пример: set yuan 11.7")

# --- Вебсервер для Render ---
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
