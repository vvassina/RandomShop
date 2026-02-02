import logging
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto
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

# ------- Доставка от Китая до Владивостока -------
CATEGORY_DELIVERY = {
    "Обувь/Куртки": 1400,
    "Джинсы/Кофты": 1000,
    "Штаны/Юбки/Платья": 750,
    "Футболки/Аксессуары": 700,
    "Часы/Украшения": 1200,
    "Сумки/Рюкзаки": 1100,
    "Техника/Другое": 0
}

MAIN_MENU = ReplyKeyboardMarkup(resize_keyboard=True).add(
    KeyboardButton("💴 Расчёт стоимости заказа"),
    KeyboardButton("🛍️ Оформление заказа")
)

CATEGORY_MENU = ReplyKeyboardMarkup(resize_keyboard=True).add(*[
    KeyboardButton(cat) for cat in CATEGORY_COMMISSION
])

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

# ====== START ======
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption=(
                    "Привет!👋🏼\n\n"
                    "Я помогу Вам рассчитать стоимость товаров и оформить заказ!\n\n"
                    "💬 <b>Пожалуйста, выберите нужный раздел:</b>"
                ),
                reply_markup=MAIN_MENU,
                parse_mode="HTML"
            )
    except:
        await message.answer("Добро пожаловать! 👋🏼", reply_markup=MAIN_MENU)

# ====== РАСЧЁТ ======
@dp.message_handler(lambda m: m.text == "💴 Расчёт стоимости заказа")
async def start_calc(message: types.Message, state: FSMContext):
    await message.answer("🗂️ Выберите категорию товара:", reply_markup=CATEGORY_MENU)
    await CalcStates.WaitingForCategory.set()

@dp.message_handler(lambda m: m.text in CATEGORY_COMMISSION, state=CalcStates.WaitingForCategory)
async def calc_category_chosen(message: types.Message, state: FSMContext):
    category = message.text
    await state.update_data(category=category)

    if category == "Техника/Другое":
        await message.answer(
            "❗ Такое считаем индивидуально, напишите нашему менеджеру 😊",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("Менеджер", url="https://t.me/dadmaksi")
            )
        )
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🛍️ Оформление заказа", "🔙 Вернуться в начало")
        await message.answer("Вы можете продолжить оформление заказа или вернуться в начало:", reply_markup=markup)
        await state.finish()
        return

    # Отправка картинок расчёта
    try:
        media = types.MediaGroup()
        media.attach_photo(types.InputFile("order_price_1.jpg"))
        media.attach_photo(types.InputFile("order_price_2.jpg"))
        media.attach_photo(types.InputFile("order_price_3.jpg"))
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.warning(f"Ошибка при отправке фото: {e}")

    await message.answer("💴 Введите стоимость товара в юанях (¥):")
    await CalcStates.WaitingForYuan.set()

@dp.message_handler(state=CalcStates.WaitingForYuan)
async def calc_price_final(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        category = data["category"]
        commission = CATEGORY_COMMISSION[category]
        delivery = CATEGORY_DELIVERY[category]
        yuan = float(message.text.replace(",", "."))
        rub_price = round(yuan * YUAN_RATE, 2)
        total = round(rub_price + commission + delivery, 2)

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🛍️ Оформление заказа", "🔙 Вернуться в начало")

        await message.answer(
            f"<b>💸 Итоговая сумма: {total} ₽</b> 🔥\n\n"
            f"💱 <b>Актуальный курс юаня (¥): {YUAN_RATE} ₽</b>\n"
            f"◾ Стоимость товара:\n"
            f"      ¥{yuan} × {YUAN_RATE} ₽ = {rub_price} ₽\n"
            f"◾ Доставка: {delivery} ₽\n"
            f"      (Китай → Владивосток)\n"
            f"◾ Комиссия: {commission} ₽\n\n"
            f"📦 <b>Дополнительно</b>: \n"
            f"• В стоимость также входят \n"
            f"<b>страховка и проверка товара</b>✅ \n"
            f"• После прибытия заказа во Владивосток применяются тарифы CDEK/Почты России для внутренней доставки — <b>эта сумма оплачивается отдельно</b>🫶🏼\n\n"
            f"<b>💬 Связь с менеджером:</b> <a href='https://t.me/dadmaksi'>@dadmaksi</a>",
            reply_markup=markup,
            parse_mode="HTML"
        )
        await state.finish()
    except Exception as e:
        logging.error(f"Ошибка расчёта: {e}")
        await message.answer("❗ Введите корректную сумму в юанях.")

# ====== ОФОРМЛЕНИЕ ЗАКАЗА ======
@dp.message_handler(lambda m: m.text == "🛍️ Оформление заказа")
async def start_order(message: types.Message, state: FSMContext):
    await state.update_data(order_items=[])
    await message.answer("📸 Пришлите фото товара:")
    await OrderStates.WaitingForPhoto.set()

@dp.message_handler(state=OrderStates.WaitingForPhoto, content_types=types.ContentTypes.PHOTO)
async def order_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("📏 Пришлите размер товара, например M или 44 (если размера нет, напишите 0):\n\n"
                         "🔙 Напишите 'назад' чтобы вернуться к фото.")
    await OrderStates.WaitingForSize.set()

@dp.message_handler(state=OrderStates.WaitingForSize)
async def order_size(message: types.Message, state: FSMContext):
    if message.text.lower() == "назад":
        await message.answer("📸 Пришлите фото товара заново:")
        await OrderStates.WaitingForPhoto.set()
        return
    await state.update_data(size=message.text)
    await message.answer("🧷 Выберите категорию товара:", reply_markup=CATEGORY_MENU)
    await OrderStates.WaitingForCategory.set()

@dp.message_handler(lambda m: m.text in CATEGORY_COMMISSION, state=OrderStates.WaitingForCategory)
async def order_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)

    # Отправка картинок расчёта
    try:
        media = types.MediaGroup()
        media.attach_photo(types.InputFile("order_price_1.jpg"))
        media.attach_photo(types.InputFile("order_price_2.jpg"))
        media.attach_photo(types.InputFile("order_price_3.jpg"))
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.warning(f"Ошибка при отправке фото: {e}")

    await message.answer("💴 Введите стоимость товара в юанях (¥):\n\n"
                         "🔙 Напишите 'назад' чтобы вернуться к выбору категории.")
    await OrderStates.WaitingForYuan.set()

@dp.message_handler(state=OrderStates.WaitingForYuan)
async def order_yuan(message: types.Message, state: FSMContext):
    if message.text.lower() == "назад":
        await message.answer("🧷 Выберите категорию товара:", reply_markup=CATEGORY_MENU)
        await OrderStates.WaitingForCategory.set()
        return

    try:
        yuan = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❗ Введите корректную сумму в юанях.")
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

    # Очищаем временные поля
    await state.update_data(photo_id=None, size=None, category=None, yuan=None)

    if "contact" not in data:
        await message.answer("📱 Напишите Ваш никнейм в Telegram или номер телефона:")
        await OrderStates.WaitingForContact.set()
    else:
        await send_summary(message, state)

# ====== ОТПРАВКА И ДЕЙСТВИЯ ======
@dp.message_handler(state=OrderStates.WaitingForContact)
async def order_contact(message: types.Message, state: FSMContext):
    forbidden = ["назад", "🔙 Вернуться в начало", "➕ Добавить товар", "📤 Отправить заказ менеджеру"]
    if message.text.lower() == "назад":
        await message.answer("💴 Введите стоимость товара в юанях (¥):")
        await OrderStates.WaitingForYuan.set()
        return
    if message.text in forbidden:
        await message.answer("❗ Пожалуйста, введите ваш контакт (никнейм или телефон), а не используйте кнопки.")
        return

    await state.update_data(contact=message.text)
    await send_summary(message, state)

async def send_summary(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("order_items", [])
    contact = data.get("contact", "Не указан")

    text = "<b>📝 Ваш заказ:</b>\n\n"
    media = []
    grand_total = 0.0

    for idx, item in enumerate(items, start=1):
        yuan = item["yuan"]
        rub = round(yuan * YUAN_RATE, 2)
        commission = CATEGORY_COMMISSION[item["category"]]
        delivery = CATEGORY_DELIVERY[item["category"]]

        text += f"<b>Товар {idx}:</b>\n"
        text += f"📏 Размер: {item['size']}\n"
        text += f"📂 Категория: {item['category']}\n"
        text += f"💴 Стоимость товара: ¥{yuan}\n"
        text += f"💰 Цена товара в рублях: {rub} ₽\n"

        if item["category"] != "Техника/Другое":
            total = round(rub + commission + delivery, 2)
            grand_total += total
            text += f"➕ Комиссия: {commission} ₽\n"
            text += f"🚚 Доставка: {delivery} ₽\n"
            text += f"      (Китай → Владивосток)\n"
            text += f"<b>💸 Итог по этому товару: {total} ₽</b>\n"
        else:
            text += "❗ <i>Итоговую стоимость данного товара Вам напишет менеджер, такое считаем индивидуально.</i>\n"
        text += "\n"
        media.append(types.InputMediaPhoto(item["photo_id"]))

    if grand_total:
        text += f"<b>🧾 Общая сумма заказа: {round(grand_total, 2)} ₽</b>\n"

    text += f"<b>📞 Контакт для связи:</b> {contact}"

    try:
        if media:
            await bot.send_media_group(message.chat.id, media)
        await message.answer(text, parse_mode="HTML",
                             reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(
                                 "📤 Отправить заказ менеджеру").row(
                                 "➕ Добавить товар", "🔙 Вернуться в начало"))
    except Exception as e:
        logging.warning(f"Ошибка при отправке summary: {e}")

    await OrderStates.WaitingForAction.set()

@dp.message_handler(lambda m: m.text == "📤 Отправить заказ менеджеру", state=OrderStates.WaitingForAction)
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    items = data.get("order_items", [])
    contact = data.get("contact", "Не указан")

    text = "<b>📝 Новый заказ от клиента:</b>\n\n"
    media = []
    grand_total = 0.0

    for idx, item in enumerate(items, start=1):
        yuan = item["yuan"]
        rub = round(yuan * YUAN_RATE, 2)
        commission = CATEGORY_COMMISSION[item["category"]]
        delivery = CATEGORY_DELIVERY[item["category"]]

        text += f"<b>Товар {idx}:</b>\n"
        text += f"📏 Размер: {item['size']}\n"
        text += f"📂 Категория: {item['category']}\n"
        text += f"💴 Цена товара: ¥{yuan}\n"
        text += f"💰 Стоимость товара в рублях: {rub} ₽\n"

        if item["category"] != "Техника/Другое":
            total = round(rub + commission + delivery, 2)
            grand_total += total
            text += f"➕ Комиссия: {commission} ₽\n"
            text += f"🚚 Доставка (Китай → Владивосток): {delivery} ₽\n"
            text += f"<b>💸 Итог по этому товару: {total} ₽</b>\n"
        else:
            text += "❗ <i>Итоговую стоимость данного товара нужно рассчитать индивидуально.</i>\n"
        text += "\n"
        media.append(types.InputMediaPhoto(item["photo_id"]))

    if grand_total:
        text += f"\n<b>🧾 Общая сумма по товарам (без индивидуальной техники): {round(grand_total, 2)} ₽</b>\n"

    text += f"<b>📞 Контакт клиента:</b> {contact}"

    try:
        if media:
            await bot.send_media_group(chat_id=GROUP_CHAT_ID, media=media)
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка отправки заказа в группу: {e}")
        await message.answer("❗ Ошибка при отправке заказа менеджеру. Попробуйте позже.")
        return

    await message.answer(
        "<b>Спасибо за заказ! 🤍</b>\nМенеджер скоро свяжется с Вами для подтверждения и оплаты.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU
    )
    await state.finish()

@dp.message_handler(lambda m: m.text == "➕ Добавить товар", state=OrderStates.WaitingForAction)
async def add_more(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_items = data.get("order_items", [])
    await state.update_data(photo_id=None, size=None, category=None, yuan=None, order_items=order_items)
    await message.answer("📸 Пришлите фото нового товара:")
    await OrderStates.WaitingForPhoto.set()

@dp.message_handler(lambda m: m.text == "🔙 Вернуться в начало", state=OrderStates.WaitingForAction)
async def back_to_start(message: types.Message, state: FSMContext):
    await state.finish()
    await start(message)

@dp.message_handler(lambda m: m.text == "🔙 Вернуться в начало", state="*")
async def back_to_start_global(message: types.Message, state: FSMContext):
    await state.finish()
    await start(message)


# ====== WEB SERVER ======
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

# ====== MAIN ======
async def set_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="Перезапуск")
    ]
    await bot.set_my_commands(commands)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_webserver())
    loop.run_until_complete(set_bot_commands(bot))  # ← ДОБАВИЛИ ВЫЗОВ КОМАНД
    executor.start_polling(dp, skip_updates=True)
