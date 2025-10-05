import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID") or "-1002687753071"
YUAN_RATE = float(os.getenv("YUAN_RATE", 11.5))

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

# ------- Комиссия -------
CATEGORY_COMMISSION = {
    "Обувь/Куртки": 1000,
    "Джинсы/Кофты": 800,
    "Штаны/Юбки/Платья": 600,
    "Футболки/Аксессуары": 600,
    "Часы/Украшения": 1000,
    "Сумки/Рюкзаки": 900,
    "Техника/Другое": 0
}

# ------- Доставка -------
CATEGORY_DELIVERY = {
    "Обувь/Куртки": 1200,
    "Джинсы/Кофты": 950,
    "Штаны/Юбки/Платья": 800,
    "Футболки/Аксессуары": 700,
    "Часы/Украшения": 1000,
    "Сумки/Рюкзаки": 1000,
    "Техника/Другое": 0
}

MAIN_MENU = ReplyKeyboardMarkup(resize_keyboard=True).add(
    KeyboardButton("💴 Расчёт стоимости заказа"),
    KeyboardButton("🛍️ Оформление заказа")
)

CATEGORY_MENU = ReplyKeyboardMarkup(resize_keyboard=True).add(*[
    KeyboardButton(cat) for cat in CATEGORY_COMMISSION
])

# --- Состояния ---
class OrderStates(StatesGroup):
    WaitingForPhoto = State()
    WaitingForSize = State()
    WaitingForCategory = State()
    WaitingForYuan = State()
    WaitingForContact = State()
    WaitingForAction = State()

class CalcStates(StatesGroup):
    WaitingForCategory = State()
    WaitingForYuan = State()

# --- start ---
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!\n\n"
                        "💬 <b>Пожалуйста, выберите нужный раздел:</b>",
                reply_markup=MAIN_MENU,
                parse_mode="HTML"
            )
    except:
        await message.answer("Добро пожаловать! 👋🏼", reply_markup=MAIN_MENU)

# ================== РАСЧЁТ ===================
@dp.message_handler(lambda m: m.text == "💴 Расчёт стоимости заказа")
async def start_calc(message: types.Message, state: FSMContext):
    await message.answer("🗂️ Выберите категорию товара:", reply_markup=CATEGORY_MENU)
    await CalcStates.WaitingForCategory.set()

@dp.message_handler(lambda m: m.text in CATEGORY_COMMISSION, state=CalcStates.WaitingForCategory)
async def calc_category_chosen(message: types.Message, state: FSMContext):
    category = message.text
    await state.update_data(category=category)

    if category == "Техника/Другое":
        await message.answer("❗ Такое считаем индивидуально, напишите менеджеру 😊",
                             reply_markup=InlineKeyboardMarkup().add(
                                 InlineKeyboardButton("Менеджер", url="https://t.me/dadmaksi")
                             ))
        await state.finish()
        return

    await message.answer("💴 Введите стоимость товара в юанях (¥):")
    await CalcStates.WaitingForYuan.set()

@dp.message_handler(state=CalcStates.WaitingForYuan)
async def calc_price_final(message: types.Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        yuan = float(text)
    except ValueError:
        await message.answer("❗ Введите корректную сумму в юанях.")
        return

    data = await state.get_data()
    category = data.get("category")

    commission = CATEGORY_COMMISSION[category]
    delivery = CATEGORY_DELIVERY[category]
    rub_price = round(yuan * YUAN_RATE, 2)
    total = round(rub_price + commission + delivery, 2)

    await message.answer(
        f"<b>💸 Итоговая сумма (товар + комиссия + доставка): {total} ₽</b>\n\n"
        f"💱 Курс: {YUAN_RATE} ₽\n"
        f"Товар: ¥{yuan} = {rub_price} ₽\n"
        f"Комиссия: {commission} ₽\n"
        f"Доставка: {delivery} ₽\n\n"
        f"📦 Доставка по РФ (CDEK/Почта) оплачивается отдельно после прибытия во Владивосток.\n\n"
        f"Менеджер: <a href='https://t.me/dadmaksi'>@dadmaksi</a>",
        parse_mode="HTML",
        reply_markup=MAIN_MENU
    )
    await state.finish()

# ================== ОФОРМЛЕНИЕ ЗАКАЗА ===================
@dp.message_handler(lambda m: m.text == "🛍️ Оформление заказа")
async def start_order(message: types.Message, state: FSMContext):
    await state.update_data(order_items=[])
    await message.answer("📸 Пришлите фото товара:")
    await OrderStates.WaitingForPhoto.set()

@dp.message_handler(state=OrderStates.WaitingForPhoto, content_types=types.ContentTypes.PHOTO)
async def order_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("📏 Пришлите размер (или 0, если нет):")
    await OrderStates.WaitingForSize.set()

@dp.message_handler(state=OrderStates.WaitingForSize)
async def order_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("🧷 Выберите категорию:", reply_markup=CATEGORY_MENU)
    await OrderStates.WaitingForCategory.set()

@dp.message_handler(lambda m: m.text in CATEGORY_COMMISSION, state=OrderStates.WaitingForCategory)
async def order_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("💴 Введите цену в юанях (¥):")
    await OrderStates.WaitingForYuan.set()

@dp.message_handler(state=OrderStates.WaitingForYuan)
async def order_yuan(message: types.Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        yuan = float(text)
    except ValueError:
        await message.answer("❗ Введите корректную сумму.")
        return

    data = await state.get_data()
    order_items = data.get("order_items", [])
    new_item = {
        "photo_id": data["photo_id"],
        "size": data["size"],
        "category": data["category"],
        "yuan": yuan
    }
    order_items.append(new_item)
    await state.update_data(order_items=order_items)

    if "contact" not in data:
        await message.answer("📱 Укажите ваш контакт (ник или телефон):")
        await OrderStates.WaitingForContact.set()
    else:
        await send_summary(message, state)

@dp.message_handler(state=OrderStates.WaitingForContact)
async def order_contact(message: types.Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await send_summary(message, state)

async def send_summary(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("order_items", [])
    contact = data.get("contact", "Не указан")

    text = "<b>📝 Ваш заказ:</b>\n\n"
    grand_total = 0

    for idx, item in enumerate(items, start=1):
        rub = round(item["yuan"] * YUAN_RATE, 2)
        commission = CATEGORY_COMMISSION[item["category"]]
        delivery = CATEGORY_DELIVERY[item["category"]]

        if item["category"] != "Техника/Другое":
            total = rub + commission + delivery
            grand_total += total
        else:
            total = 0

        caption = (
            f"<b>Товар {idx}</b>\n"
            f"Размер: {item['size']}\n"
            f"Категория: {item['category']}\n"
            f"Цена: ¥{item['yuan']} = {rub} ₽\n"
        )
        if item["category"] != "Техника/Другое":
            caption += f"Комиссия: {commission} ₽\nДоставка: {delivery} ₽\n<b>Итого: {total} ₽</b>\n"
        else:
            caption += "❗ Итог уточнит менеджер\n"

        await bot.send_photo(message.chat.id, item["photo_id"], caption=caption, parse_mode="HTML")

    if grand_total:
        text += f"<b>🧾 Общая сумма: {grand_total} ₽</b>\n\n"
    text += f"<b>📞 Контакт:</b> {contact}"

    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(
        "📤 Отправить заказ менеджеру", "➕ Добавить товар", "🔙 Вернуться в начало"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=markup)
    await OrderStates.WaitingForAction.set()

# --- Вернуться в начало ---
@dp.message_handler(lambda m: m.text == "🔙 Вернуться в начало", state="*")
async def back_to_start(message: types.Message, state: FSMContext):
    await state.finish()
    await start(message)

# --- Web server ---
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

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver())
    executor.start_polling(dp, skip_updates=True)
