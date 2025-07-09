import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto, MediaGroup
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
        media = MediaGroup()
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

@dp.message_handler(lambda m: m.text == "Оформить заказ 🛍", state="*")
async def start_order(message: types.Message, state: FSMContext):
    await state.update_data(items=[], edit_index=None)
    await message.answer("Шаг 1️⃣: Пришлите скриншот товара.")
    await OrderState.waiting_for_photo.set()

@dp.message_handler(content_types=types.ContentType.PHOTO, state=OrderState.waiting_for_photo)
async def handle_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    edit_index = data.get("edit_index")

    photo_file_id = message.photo[-1].file_id

    if edit_index is not None and 0 <= edit_index < len(items):
        items[edit_index]["photo"] = photo_file_id
    else:
        items.append({
            "photo": photo_file_id,
            "size": None,
            "category": None,
            "yuan": None,
        })

    await state.update_data(items=items, edit_index=None)
    await message.answer("Шаг 2️⃣: Пришлите размер товара (например, 42 или M).")
    await OrderState.waiting_for_size.set()

@dp.message_handler(state=OrderState.waiting_for_size)
async def handle_size(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    edit_index = data.get("edit_index")

    size = message.text.strip()

    if edit_index is not None and 0 <= edit_index < len(items):
        items[edit_index]["size"] = size
    elif items:
        items[-1]["size"] = size
    else:
        items.append({
            "photo": None,
            "size": size,
            "category": None,
            "yuan": None,
        })

    await state.update_data(items=items, edit_index=None)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in CATEGORY_FEES:
        markup.add(KeyboardButton(cat))
    await message.answer("Шаг 3️⃣: Выберите категорию товара:", reply_markup=markup)
    await OrderState.waiting_for_category.set()
    
@dp.message_handler(lambda m: m.text in CATEGORY_FEES, state=OrderState.waiting_for_category)
async def handle_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    edit_index = data.get("edit_index")

    category = message.text

    if edit_index is not None and 0 <= edit_index < len(items):
        items[edit_index]["category"] = category
    elif items:
        items[-1]["category"] = category
    else:
        items.append({
            "photo": None,
            "size": None,
            "category": category,
            "yuan": None,
        })

    await state.update_data(items=items, edit_index=None)
    await message.answer("Шаг 4️⃣: Пришлите стоимость товара в юанях (¥).")
    await OrderState.waiting_for_price.set()
    
@dp.message_handler(state=OrderState.waiting_for_price)
async def handle_price(message: types.Message, state: FSMContext):
    text = message.text.replace("¥", "").replace(",", ".").strip()
    if not text.replace('.', '').isdigit():
        await message.answer("Введите корректную сумму в юанях.")
        return

    data = await state.get_data()
    items = data.get("items", [])
    edit_index = data.get("edit_index")

    price_yuan = float(text)

    if edit_index is not None and 0 <= edit_index < len(items):
        items[edit_index]["yuan"] = price_yuan
    elif items:
        items[-1]["yuan"] = price_yuan
    else:
        items.append({
            "photo": None,
            "size": None,
            "category": None,
            "yuan": price_yuan,
        })

    await state.update_data(items=items, edit_index=None)
    await message.answer("Шаг 5️⃣: Пришлите ваш никнейм в Telegram или номер телефона для связи 📞")
    await OrderState.waiting_for_contact.set()

@dp.message_handler(state=OrderState.waiting_for_contact)
async def handle_contact(message: types.Message, state: FSMContext):
    contact = message.text.strip()
    data = await state.get_data()
    items = data.get("items", [])
    
    if not items:
        await message.answer("Ошибка: нет товаров в заказе. Начните заново.")
        await state.finish()
        return
    
    await state.update_data(contact=contact)

    # Формируем итоговое сообщение с товарами
    msg_lines = [f"Ваш заказ:\nКоличество товаров: {len(items)}"]
    total_rub = 0
    
    for i, item in enumerate(items, 1):
        cat_fee = CATEGORY_FEES.get(item.get("category"), 0)
        price_rub = round(item.get("yuan", 0) * YUAN_RATE + cat_fee, 2)
        total_rub += price_rub
        msg_lines.append(
            f"\nТовар {i}⬇\n"
            f"Категория: {item.get('category')}\n"
            f"Размер: {item.get('size')}\n"
            f"Стоимость: {price_rub} ₽ (¥{item.get('yuan')})"
        )
    msg_lines.append(f"\nОбщая сумма: {total_rub} ₽")
    msg_lines.append(f"Контакт: {contact}")
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📩 Отправить заказ менеджеру")
    markup.add("Вернуться в начало")
    
    await message.answer("\n".join(msg_lines), reply_markup=markup)
    await OrderState.confirm_order.set()

@dp.message_handler(lambda m: m.text == "📩 Отправить заказ менеджеру", state=OrderState.confirm_order)
async def send_to_manager(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("items", [])
    contact = data.get("contact", "не указан")

    total_text = f"🛍 Новый заказ от {contact}:\n"
    total_price = 0
    media = MediaGroup()

    for idx, item in enumerate(items, start=1):
        category = item.get("category", "не указана")
        size = item.get("size", "не указан")
        yuan = item.get("yuan", 0)
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

        if item.get("photo"):
            media.attach_photo(item["photo"])

    total_text += f"\n\n💰 Общая сумма: {total_price} ₽\nКонтакт: {contact}"

    manager_chat_id = -1002687753071  # Твой ID группы

    try:
        if media.media:
            await bot.send_media_group(chat_id=manager_chat_id, media=media)
        await bot.send_message(chat_id=manager_chat_id, text=total_text)
    except Exception as e:
        await message.answer("❗ Не удалось отправить заказ менеджеру. Попробуйте позже.")
        return

    await message.answer("✅ Ваш заказ отправлен менеджеру! Ожидайте, скоро мы свяжемся с Вами! Спасибо за заказ ❤")

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Вернуться в начало")
    await message.answer("Что хотите сделать дальше?", reply_markup=markup)
    await state.finish()

@dp.message_handler(lambda m: m.text == "Вернуться в начало", state="*")
async def back_to_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Возвращаемся в главное меню", reply_markup=main_menu())

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp)
