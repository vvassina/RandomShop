import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YUAN_RATE = float(os.getenv("YUAN_RATE", 11.5))

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
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

class OrderState(StatesGroup):
    waiting_for_photo = State()
    waiting_for_size = State()
    waiting_for_category = State()
    waiting_for_price = State()
    waiting_for_contact = State()
    confirm_order = State()
    
current_category = None
yuan_rate = float(os.getenv("YUAN_RATE", 11.5))  # загружается из переменной окружения

user_orders = {}

def main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("Посчитать стоимость заказа 💴"),
        KeyboardButton("Оформить заказ 🛍")
    )

@dp.message_handler(commands=["start"])
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    try:
        with open("start.jpg", "rb") as photo:
            await message.answer_photo(
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
                reply_markup=main_menu()
            )
    except:
        await message.answer(
            "Привет!👋🏼 Я помогу Вам рассчитать стоимость товаров и оформить заказ!",
            reply_markup=main_menu()
        )

# --- Расчёт стоимости ---
@dp.message_handler(lambda m: m.text == "Посчитать стоимость заказа 💴")
async def choose_category_for_price(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in CATEGORY_FEES:
        markup.add(KeyboardButton(cat))
    await message.answer("Выберите категорию товара:", reply_markup=markup)

@dp.message_handler(lambda message: message.text in CATEGORY_FEES)
async def input_price_yuan(message: types.Message, state: FSMContext):
    await state.update_data(selected_category=message.text)
    try:
        media = types.MediaGroup()
        for i in range(1, 4):
            media.attach_photo(types.InputFile(f"price_example_{i}.jpg"))
        await bot.send_media_group(message.chat.id, media)
    except:
        pass
    await message.answer("Введите стоимость товара в юанях (¥):")

@dp.message_handler(lambda m: m.text.replace(",", ".").replace("¥", "").strip().replace(".", "").isdigit())
async def calculate_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("selected_category")
    if not category:
        return
    try:
        yuan = float(message.text.replace("¥", "").replace(",", ".").strip())
        rub_no_fee = round(yuan * YUAN_RATE, 2)
        fee = CATEGORY_FEES[category]
        total = rub_no_fee + fee

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Оформить заказ 🛍", "Вернуться в начало")

        await message.answer(
            f"💸 Итоговая сумма: {total} ₽\n\n"
            f"🔹 Стоимость: ¥{yuan} × {YUAN_RATE} ₽ = {rub_no_fee} ₽\n"
            f"🔹 Комиссия: {fee} ₽\n\n"
            f"🚚 Условия доставки:\n"
            f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n"
            f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!",
            reply_markup=markup
        )
    except Exception as e:
        logging.error(e)
        await message.answer("Произошла ошибка. Попробуйте снова.")
class OrderState(StatesGroup):
    waiting_for_photo = State()
    waiting_for_size = State()
    waiting_for_category = State()
    waiting_for_price = State()
    waiting_for_contact = State()
    confirm_order = State()

user_orders = {}

@dp.message_handler(lambda m: m.text == "Оформить заказ 🛍", state="*")
async def start_order(message: types.Message, state: FSMContext):
    await state.update_data(current_order=[], editing_index=None)
    await message.answer("Шаг 1️⃣: Пришлите скриншот товара.")
    await OrderState.waiting_for_photo.set()

@dp.message_handler(content_types=types.ContentType.PHOTO, state=OrderState.waiting_for_photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await message.answer("Шаг 2️⃣: Пришлите размер товара (например, 42 или M).")
    await OrderState.waiting_for_size.set()

@dp.message_handler(state=OrderState.waiting_for_size)
async def handle_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text.strip())
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in CATEGORY_FEES:
        markup.add(KeyboardButton(cat))
    await message.answer("Шаг 3️⃣: Выберите категорию товара:", reply_markup=markup)
    await OrderState.waiting_for_category.set()

@dp.message_handler(lambda m: m.text in CATEGORY_FEES, state=OrderState.waiting_for_category)
async def handle_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("Шаг 4️⃣: Пришлите стоимость товара в юанях (¥).")
    await OrderState.waiting_for_price.set()

@dp.message_handler(state=OrderState.waiting_for_price)
async def handle_price(message: types.Message, state: FSMContext):
    text = message.text.replace("¥", "").replace(",", ".").strip()
    if not text.replace('.', '').isdigit():
        await message.answer("Введите корректную сумму в юанях.")
        return
    await state.update_data(yuan=float(text))
    await message.answer("Шаг 5️⃣: Пришлите ваш никнейм в Telegram или номер телефона для связи 📞")
    await OrderState.waiting_for_contact.set()

@dp.message_handler(state=OrderState.waiting_for_contact)
async def handle_contact(message: types.Message, state: FSMContext):
    contact = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id

    # Добавляем позицию к заказу
    item = {
        "photo": data["photo"],
        "size": data["size"],
        "category": data["category"],
        "yuan": data["yuan"],
        "contact": contact
    }

    user_orders.setdefault(user_id, []).append(item)
    await state.update_data(current_order=user_orders[user_id])

    await show_order_summary(message, state)
    await OrderState.confirm_order.set()

      from aiogram.types import InputMediaPhoto

async def show_order_summary(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("current_order", [])
    user_id = message.from_user.id

    media = types.MediaGroup()
    for item in items:
        media.attach_photo(item["photo"])
    try:
        await bot.send_media_group(user_id, media)
    except:
        pass

    summary = f"Ваш заказ:\nКоличество товаров: {len(items)}\n\n"
    total_price = 0

    for idx, item in enumerate(items, start=1):
        category = item["category"]
        yuan = item["yuan"]
        rub_no_fee = round(yuan * YUAN_RATE, 2)
        fee = CATEGORY_FEES.get(category, 0)
        total = rub_no_fee + fee
        total_price += total

        summary += (
            f"📦 Товар {idx} ⬇\n"
            f"Категория: {category}\n"
            f"Размер: {item['size']}\n"
            f"Стоимость: ¥{yuan} × {YUAN_RATE} ₽ + {fee} ₽ = {total} ₽\n\n"
        )

    summary += (
        f"💰 Общая сумма: {total_price} ₽\n\n"
        f"🚚 Условия доставки:\n"
        f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n"
        f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!"
    )

    buttons = [
        [KeyboardButton("Изменить фото"), KeyboardButton("Изменить размер")],
        [KeyboardButton("Изменить стоимость в юанях")],
        [KeyboardButton("✅ Всё верно")]
    ]
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)
    await message.answer(summary, reply_markup=markup)

@dp.message_handler(lambda m: m.text == "✅ Всё верно", state=OrderState.confirm_order)
async def after_confirmation(message: types.Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Оформить заказ!🔥")
    markup.add("Добавить позиции в заказ")
    markup.add("Вернуться в начало")
    await message.answer("Выберите дальнейшее действие:", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "Добавить позиции в заказ", state=OrderState.confirm_order)
async def add_more_items(message: types.Message, state: FSMContext):
    await message.answer("Шаг 1️⃣: Пришлите скриншот товара.")
    await OrderState.waiting_for_photo.set()

@dp.message_handler(lambda m: m.text == "Оформить заказ!🔥", state=OrderState.confirm_order)
async def ready_to_send(message: types.Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📩 Отправить заказ менеджеру", "🔙 Вернуться назад")
    await message.answer("Выберите действие:", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "📩 Отправить заказ менеджеру", state=OrderState.confirm_order)
async def send_to_manager(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("current_order", [])
    contact = items[-1]["contact"]
    total_text = f"🛍 Новый заказ от {contact}:\n"

    total_price = 0
    for idx, item in enumerate(items, start=1):
        category = item["category"]
        size = item["size"]
        yuan = item["yuan"]
        rub_no_fee = round(yuan * YUAN_RATE, 2)
        fee = CATEGORY_FEES.get(category, 0)
        rub = rub_no_fee + fee
        total_price += rub

        total_text += (
            f"\n📦 Товар {idx}:\n"
            f"Категория: {category}\n"
            f"Размер: {size}\n"
            f"Цена: ¥{yuan} → {rub_no_fee} + {fee} = {rub} ₽"
        )

    total_text += f"\n\n💰 Общая сумма: {total_price} ₽\nКонтакт: {contact}"

    media = types.MediaGroup()
    for item in items:
        media.attach_photo(item["photo"])
    try:
        await bot.send_media_group(chat_id='-1002687753071', media=media)
        await bot.send_message(chat_id='-1002687753071', text=total_text)
    except Exception as e:
        await message.answer("❗ Не удалось отправить заказ менеджеру. Попробуйте позже.")
        return

    await message.answer("✅ Ваш заказ отправлен менеджеру! Ожидайте, совсем скоро мы свяжемся с Вами! Спасибо за заказ ❤")

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Вернуться в начало")
    await message.answer("Что хотите сделать дальше?", reply_markup=markup)
    await state.finish()
@dp.message_handler(lambda m: m.text == "Изменить фото", state=OrderState.confirm_order)
async def edit_photo(message: types.Message, state: FSMContext):
    await message.answer("Пришлите новое фото товара:")
    await OrderState.waiting_for_photo.set()

@dp.message_handler(lambda m: m.text == "Изменить размер", state=OrderState.confirm_order)
async def edit_size(message: types.Message, state: FSMContext):
    await message.answer("Введите новый размер товара:")
    await OrderState.waiting_for_size.set()

@dp.message_handler(lambda m: m.text == "Изменить стоимость в юанях", state=OrderState.confirm_order)
async def edit_price(message: types.Message, state: FSMContext):
    await message.answer("Введите новую стоимость в юанях:")
    await OrderState.waiting_for_price.set()

@dp.message_handler(lambda m: m.text == "🔙 Вернуться назад", state=OrderState.confirm_order)
async def back_after_confirm(message: types.Message, state: FSMContext):
    await show_order_summary(message, state)

@dp.message_handler(lambda m: m.text == "Вернуться в начало", state="*")
async def go_to_start(message: types.Message, state: FSMContext):
    await state.finish()
    await start(message)

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
