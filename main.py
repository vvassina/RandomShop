import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
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

current_category = None
yuan_rate = float(os.getenv("YUAN_RATE", 11.5))  # загружается из переменной окружения

def get_main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(*[KeyboardButton(cat) for cat in CATEGORY_FEES])

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption=(
                    "Привет!👋🏼\n\n"
                    "Я помогу Вам рассчитать стоимость товаров и оформить заказ! \n\n"
                    "💬 <b>Пожалуйста, выберите категорию товара:</b>"
                ),
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Error sending photo: {e}")
        await message.answer("Добро пожаловать! Используйте меню ниже:", reply_markup=get_main_menu())

@dp.message_handler(lambda message: message.text in CATEGORY_FEES)
async def handle_category(message: types.Message):
    global current_category
    current_category = message.text

    if current_category == "Техника/Другое":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Такое считаем индивидуально, напишите нашему менеджеру 😊", reply_markup=kb)
        return

    # Отправляем 3 картинки
    try:
        media = types.MediaGroup()
        media.attach_photo(types.InputFile("order_price_2.jpg"))
        media.attach_photo(types.InputFile("order_price_3.jpg"))
        media.attach_photo(types.InputFile("order_price_1.jpg"))
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.error(f"Ошибка при отправке изображений: {e}")

    await message.answer("Введите стоимость товара в юанях (¥):")

@dp.message_handler(lambda message: current_category and message.text.replace(',', '').replace('.', '').isdigit())
async def calculate_total(message: types.Message):
    try:
        yuan = float(message.text.replace(",", "."))
        fixed_fee = CATEGORY_FEES[current_category]
        rub_no_fee = round(yuan * yuan_rate, 2)
        total = round(rub_no_fee + fixed_fee, 2)

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Оформить заказ!🔥", "Вернуться в начало")

        await message.answer(
            f"Итоговая сумма без учёта доставки: <b>{total} ₽</b> 🔥\n\n"
            f"💱 Актуальный курс юаня (¥): {yuan_rate} ₽\n"
            f"◾ Стоимость товара:\n"
            f"      ¥{yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
            f"◾ Комиссия: {fixed_fee} ₽\n\n"
            f"🚚 <i>Условия доставки:</i>\n"
            f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
            f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!",
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Calculation error: {e}")
        await message.answer("Ошибка расчёта. Попробуйте снова.")

@dp.message_handler(lambda message: message.text.lower().startswith("set yuan"))
async def set_yuan_rate(message: types.Message):
    global yuan_rate
    try:
        new_rate = float(message.text.split()[-1].replace(",", "."))
        yuan_rate = new_rate
        await message.answer(
            f"Новый курс юаня установлен: {yuan_rate} ₽ ✅\n\n"
            f"⚠️ ВНИМАНИЕ: это временный курс. "
            f"При перезапуске он сбросится.\n"
            f"Чтобы сохранить навсегда — зайди на Render и измени переменную YUAN_RATE."
        )
    except:
        await message.answer("Неверный формат. Пример: set yuan 11.7")

@dp.message_handler(lambda message: message.text in ["Вернуться в начало", "Оформить заказ!🔥"])
async def handle_buttons(message: types.Message):
    if message.text == "Вернуться в начало":
        await start(message)
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Свяжитесь с менеджером для оформления:", reply_markup=kb)

# --- Web-сервер для Render ---
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
