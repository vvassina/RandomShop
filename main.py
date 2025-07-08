import logging
import os
from aiogram import Bot, Dispatcher, types
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

# Сделаем current_category и yuan_rate глобальными, храним в памяти через объект
class State:
    current_category = None
    yuan_rate = 11.5

state = State()

def get_main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(*[KeyboardButton(cat) for cat in CATEGORY_FEES])

@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    state.current_category = None
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

@dp.message()
async def handle_category(message: types.Message):
    if message.text not in CATEGORY_FEES:
        return  # Игнорируем, если текст не категория
    
    state.current_category = message.text

    if state.current_category == "Техника/Другое":
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

@dp.message()
async def calculate_total(message: types.Message):
    if state.current_category is None:
        return
    # Проверяем, что текст — число (цена в юанях)
    text = message.text.replace(",", ".")
    try:
        yuan = float(text)
    except ValueError:
        return  # Не число — игнорируем

    fixed_fee = CATEGORY_FEES[state.current_category]
    rub_no_fee = round(yuan * state.yuan_rate, 2)
    rub = round(rub_no_fee + fixed_fee, 2)

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Оформить заказ!🔥", "Вернуться в начало")

    await message.answer(
        f"💸 Итоговая сумма: {rub} ₽\n\n"
        f"🔹 Стоимость: ¥{yuan} × {state.yuan_rate} ₽ = {rub_no_fee} ₽\n"
        f"🔹 Комиссия: {fixed_fee} ₽\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока + тариф CDEK/Почты России",
        reply_markup=markup
    )

@dp.message()
async def set_yuan_rate(message: types.Message):
    if not message.text.lower().startswith("set yuan"):
        return
    try:
        new_rate = float(message.text.split()[-1].replace(",", "."))
        state.yuan_rate = new_rate
        await message.answer(f"Новый курс юаня установлен: {state.yuan_rate} ₽")
    except Exception:
        await message.answer("Неверный формат. Пример: set yuan 11.7")

@dp.message()
async def handle_buttons(message: types.Message):
    if message.text not in ["Вернуться в начало", "Оформить заказ!🔥"]:
        return

    if message.text == "Вернуться в начало":
        await start_handler(message)
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
        await message.answer("Свяжитесь с менеджером для оформления:", reply_markup=kb)

if _name_ == "_main_":
    import asyncio
    asyncio.run(dp.start_polling(bot))
