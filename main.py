
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# Категории и комиссии
CATEGORY_FEES = {
    "Обувь/Куртки": 0.2,
    "Джинсы/Кофты": 0.18,
    "Штаны/Юбки/Платья": 0.18,
    "Футболки/Аксессуары": 0.15,
    "Часы/Украшения": 0.15,
    "Сумки/Рюкзаки": 0.2,
    "Техника/Другое": 0.0  # Обрабатывается отдельно
}

# Начальное меню
def get_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in CATEGORY_FEES:
        kb.add(KeyboardButton(cat))
    return kb

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    with open("start.jpg", "rb") as photo:
        await bot.send_photo(
            message.chat.id,
            photo,
            caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
            reply_markup=get_main_menu()
        )

@dp.message_handler(lambda message: message.text in CATEGORY_FEES)
async def handle_category(message: types.Message):
    category = message.text

    if category == "Техника/Другое":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Написать менеджеру", url="https://t.me/your_manager_link"))
        await message.answer("Такое считаем индивидуально, напишите нашему менеджеру 😊", reply_markup=kb)
        return

    with open("price_input.jpg", "rb") as photo:
        await bot.send_photo(
            message.chat.id,
            photo,
            caption="Введите стоимость в юанях (¥):"
        )

    dp.register_message_handler(
        lambda msg: calculate_total(msg, category), content_types=types.ContentTypes.TEXT)

# Переменная для курса юаня (можно менять админом)
yuan_rate = 11.5

@dp.message_handler(lambda message: message.text.lower().startswith("set yuan"))
async def set_yuan_rate(message: types.Message):
    global yuan_rate
    try:
        parts = message.text.split()
        if len(parts) == 3:
            yuan_rate = float(parts[2].replace(",", "."))
            await message.answer(f"Новый курс юаня установлен: {yuan_rate} ₽")
    except:
        await message.answer("Неверный формат. Пример: set yuan 11.7")

async def calculate_total(message: types.Message, category: str):
    try:
        yuan = float(message.text.replace(",", "."))
        fee_rate = CATEGORY_FEES[category]
        rub_no_fee = round(yuan * yuan_rate, 2)
        fee = round(rub_no_fee * fee_rate, 2)
        rub = round(rub_no_fee + fee, 2)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Оформить заказ!🔥", "Вернуться в начало")

        await message.answer(
            f"💸 Итоговая сумма: {rub} ₽\n\n"
            f"🔹 Стоимость: ¥{yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
            f"🔹 Комиссия: {fee} ₽\n\n"
            f"🚚 У нас новые условия доставки:  \n"
            f"Теперь тариф 600₽/кг до Владивостока,  \n"
            f"далее по тарифу CDEK/Почты России 🤍\n\n"
            f"Точную стоимость доставки Вам скажет менеджер,  \n"
            f"когда товар будет во Владивостоке!",
            reply_markup=markup
        )
    except:
        await message.answer("Пожалуйста, введите число — стоимость в юанях.")

@dp.message_handler(lambda message: message.text == "Вернуться в начало")
async def back_to_start(message: types.Message):
    await start(message)

@dp.message_handler(lambda message: message.text == "Оформить заказ!🔥")
async def contact_manager(message: types.Message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Написать менеджеру", url="https://t.me/your_manager_link"))
    await message.answer("Свяжитесь с нашим менеджером для оформления заказа:", reply_markup=kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
