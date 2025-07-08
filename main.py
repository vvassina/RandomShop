import logging
import os
import re
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()
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

current_category = None
yuan_rate = 11.5

def get_main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(*[KeyboardButton(cat) for cat in CATEGORY_FEES])

@dp.message(F.commands == ["start"])
async def start(message: types.Message):
    global current_category
    current_category = None
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
                reply_markup=get_main_menu()
            )
    except Exception as e:
        logging.error(f"Error sending photo: {e}")
        await message.answer("Добро пожаловать! Используйте меню ниже:", reply_markup=get_main_menu())

@dp.message(F.text.in_(CATEGORY_FEES))
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
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Введите стоимость в юанях (¥):"
            )
    except Exception as e:
        logging.error(f"Error sending price input photo: {e}")
        await message.answer("Введите стоимость в юанях (¥):")

@dp.message(lambda message: current_category and message.text.replace(',', '').replace('.', '').isdigit())
async def calculate_total(message: types.Message):
    global yuan_rate
    try:
        yuan = float(message.text.replace(",", "."))
        fixed_fee = CATEGORY_FEES[current_category]
        rub_no_fee = round(yuan * yuan_rate, 2)
        rub = round(rub_no_fee + fixed_fee, 2)

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Оформить заказ!🔥", "Вернуться в начало")

        await message.answer(
            f"💸 Итоговая сумма: {rub} ₽\n\n"
            f"🔹 Стоимость: ¥{yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
            f"🔹 Комиссия: {fixed_fee} ₽\n\n"
            f"🚚 Условия доставки:\n"
            f"600₽/кг до Владивостока + тариф CDEK/Почты России",
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Calculation error: {e}")
        await message.answer("Ошибка расчёта. Попробуйте снова.")

@dp.message(F.text.regexp(r"^set yuan\s+\d+(\.\d+)?$", flags=re.IGNORECASE))
async def set_yuan_rate(message: types.Message):
    global yuan_rate
    try:
        new_rate = float(message.text.split()[-1].replace(",", "."))
        yuan_rate = new_rate
        await message.answer(f"Новый курс юаня установлен: {yuan_rate} ₽")
    except Exception:
        await message.answer("Неверный формат. Пример: set yuan 11.7")

@dp.message(F.text.in_(["Вернуться в начало", "Оформить заказ!🔥"]))
async def handle_buttons(message: types.Message):
    if message.text == "Вернуться в начало":
        await start(message)
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Свяжитесь с менеджером для оформления:", reply_markup=kb)


# --- aiohttp web server для Render ---

async def handle_root(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# --- Главная корутина запуска ---

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
