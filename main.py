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

yuan_rate = float(os.getenv("YUAN_RATE", 11.5))
MANAGER_CHAT_ID = -1001234567890  # Вставь сюда ID твоей группы для заказов

# Хранение данных пользователей: структура
# user_orders = {
#   user_id: {
#       "contact": "номер или юзернейм",
#       "items": [
#           {"screenshot": file_id, "size": "M", "category": "Обувь/Куртки", "price_yuan": 100, "price_rub": 0},
#           ...
#       ],
#       "current_step": "awaiting_screenshot" | "awaiting_size" | ...
#       "current_item_index": int,
#   }
# }
user_orders = {}

# Главное меню
def get_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Рассчитать стоимость заказа💴"))
    kb.add(KeyboardButton("Оформить заказ🛍️"))
    return kb

# Кнопки для выбора категории
def get_category_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(*[KeyboardButton(cat) for cat in CATEGORY_FEES])
    kb.add(KeyboardButton("🔙 Назад в меню"))
    return kb

# Кнопки после расчёта стоимости
def get_after_calc_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Оформить заказ🛍️"))
    kb.add(KeyboardButton("Вернуться в начало"))
    return kb

# Кнопки финального подтверждения заказа (редактирование и подтверждение)
def get_edit_keyboard(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    items = user_orders[user_id]["items"]
    current_idx = user_orders[user_id]["current_item_index"]

    kb.add(
        InlineKeyboardButton("Изменить скрин", callback_data=f"edit_screenshot_{current_idx}"),
        InlineKeyboardButton("Изменить размер", callback_data=f"edit_size_{current_idx}"),
        InlineKeyboardButton("Изменить категорию", callback_data=f"edit_category_{current_idx}"),
        InlineKeyboardButton("Изменить стоимость", callback_data=f"edit_price_{current_idx}")
    )
    kb.add(InlineKeyboardButton("Да, всё верно ✅", callback_data="confirm_order"))
    return kb

# Кнопки после подтверждения заказа — отправить менеджеру / добавить товар / вернуться в начало
def get_post_confirm_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Отправить заказ менеджеру"))
    kb.add(KeyboardButton("Добавить позицию в заказ"))
    kb.add(KeyboardButton("Вернуться в главное меню"))
    return kb

# --- Старт ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    try:
        with open("start.jpg", "rb") as photo:
            await bot.send_photo(
                message.chat.id,
                photo,
                caption="Привет!👋🏼\n\nЯ помогу Вам рассчитать стоимость товаров и оформить заказ!",
                reply_markup=get_main_menu()
            )
    except Exception as e:
        logging.error(f"Error sending start photo: {e}")
        await message.answer("Добро пожаловать! Используйте меню ниже:", reply_markup=get_main_menu())
    user_orders.pop(message.from_user.id, None)  # Очистить старый заказ при старте

# --- Главное меню ---
@dp.message_handler(lambda m: m.text == "Рассчитать стоимость заказа💴")
async def calc_price_start(message: types.Message):
    kb = get_category_keyboard()
    await message.answer("Выберите категорию товара:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Оформить заказ🛍️")
async def order_start(message: types.Message):
    user_id = message.from_user.id
    user_orders[user_id] = {
        "contact": None,
        "items": [],
        "current_step": "awaiting_screenshot",
        "current_item_index": 0
    }
    await message.answer("🛍️ Оформление заказа\n\nШаг 1️⃣ Пришлите скрин товара")

@dp.message_handler(lambda m: m.text == "Вернуться в начало")
async def back_to_start(message: types.Message):
    await cmd_start(message)

# --- Обработка выбора категории для расчёта стоимости (не для заказа) ---
@dp.message_handler(lambda m: m.text in CATEGORY_FEES and m.chat.type != "private" or m.text in CATEGORY_FEES)
async def category_selected_for_calc(message: types.Message):
    category = message.text
    # Отправляем три картинки в одном media_group + запрос стоимости
    try:
        media = types.MediaGroup()
        media.attach_photo(InputFile("price_example_1.jpg"))
        media.attach_photo(InputFile("price_example_2.jpg"))
        media.attach_photo(InputFile("price_example_3.jpg"), caption="Введите стоимость в юанях (¥):")
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.error(f"Error sending media group: {e}")
        await message.answer("Введите стоимость в юанях (¥):")

    # Сохраняем выбранную категорию для расчёта
    user_id = message.from_user.id
    if user_id not in user_orders:
        user_orders[user_id] = {}
    user_orders[user_id]["calc_category"] = category

@dp.message_handler(lambda m: "calc_category" in user_orders.get(m.from_user.id, {}) and m.text and m.text.replace(",", "").replace(".", "").isdigit())
async def calculate_cost(message: types.Message):
    user_id = message.from_user.id
    category = user_orders[user_id]["calc_category"]
    try:
        yuan = float(message.text.replace(",", "."))
        fixed_fee = CATEGORY_FEES[category]
        rub_no_fee = round(yuan * yuan_rate, 2)
        rub = round(rub_no_fee + fixed_fee, 2)
        markup = get_after_calc_keyboard()

        await message.answer(
            f"💸 Итоговая сумма: {rub} ₽\n\n"
            f"🔹 Стоимость: ¥{yuan} × {yuan_rate} ₽ = {rub_no_fee} ₽\n"
            f"🔹 Комиссия: {fixed_fee} ₽\n\n"
            f"🚚 Условия доставки:\n"
            f"600₽/кг до Владивостока, далее по тарифу CDEK/Почты России.\n\n"
            f"📦 Точную стоимость доставки скажет менеджер, когда заказ прибудет во Владивосток!",
            reply_markup=markup
        )
        # Очистить категорию после расчёта, чтобы не путать
        user_orders[user_id].pop("calc_category", None)
    except Exception as e:
        logging.error(f"Calculation error: {e}")
        await message.answer("Ошибка расчёта. Попробуйте снова.")

# --- Оформление заказа: многошаговый ввод ---
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def photo_received(message: types.Message):
    user_id = message.from_user.id
    order = user_orders.get(user_id)
    if not order:
        return  # Игнорируем, если не в процессе заказа

    step = order.get("current_step")
    idx = order["current_item_index"]

    if step == "awaiting_screenshot":
        photo = message.photo[-1]  # Самое качественное
        file_id = photo.file_id

        # Если товара ещё нет, добавляем пустой
        if len(order["items"]) <= idx:
            order["items"].append({
                "screenshot": file_id,
                "size": None,
                "category": None,
                "price_yuan": None,
                "price_rub": None
            })
        else:
            order["items"][idx]["screenshot"] = file_id

        order["current_step"] = "awaiting_size"
        await message.answer("✅ Скриншот получен!\n\nШаг 2️⃣ Введите размер товара (например, M или 42)")

@dp.message_handler(lambda m: True)
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    order = user_orders.get(user_id)
    text = message.text

    if not order:
        # Если пользователь не в заказе — можно обработать кнопки главного меню
        if text == "Вернуться в начало":
            await cmd_start(message)
        return

    step = order.get("current_step")
    idx = order["current_item_index"]

    if step == "awaiting_size":
        # Сохраняем размер
        order["items"][idx]["size"] = text
        order["current_step"] = "awaiting_category"
        await message.answer("Шаг 3️⃣ Выберите категорию товара:", reply_markup=get_category_keyboard())

    elif step == "awaiting_category":
        if text == "🔙 Назад в меню":
            order["current_step"] = "awaiting_screenshot"
            await message.answer("Возврат к шагу 1️⃣ Пришлите скрин товара")
            return

        if text not in CATEGORY_FEES:
            await message.answer("Пожалуйста, выберите категорию из списка или нажмите «🔙 Назад в меню»")
            return

        order["items"][idx]["category"] = text

        if text == "Техника/Другое":
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Написать менеджеру", url="https://t.me/dadmaksi"))
            await message.answer("Такое считаем индивидуально, напишите нашему менеджеру 😊", reply_markup=kb)
            # Заканчиваем оформление для этого товара — предлагаем добавить позицию или отправить заказ
            order["current_step"] = "awaiting_post_order_action"
            await send_order_summary(message)
            return

        # Отправляем 3 картинки + запрос стоимости
        try:
            media = types.MediaGroup()
            media.attach_photo(InputFile("price_example_1.jpg"))
            media.attach_photo(InputFile("price_example_2.jpg"))
            media.attach_photo(InputFile("price_example_3.jpg"), caption="Введите стоимость в юанях (¥):")
            await bot.send_media_group(message.chat.id, media)
        except Exception as e:
            logging.error(f"Error sending media group: {e}")
            await message.answer("Введите стоимость в юанях (¥):")

        order["current_step"] = "awaiting_price"

    elif step == "awaiting_price":
        try:
            price_yuan = float(text.replace(",", "."))
            order["items"][idx]["price_yuan"] = price_yuan
            fixed_fee = CATEGORY_FEES[order["items"][idx]["category"]]
            rub_no_fee = round(price_yuan * yuan_rate, 2)
            price_rub = round(rub_no_fee + fixed_fee, 2)
            order["items"][idx]["price_rub"] = price_rub

            # Проверяем, есть ли контакт пользователя, если нет — спрашиваем
            if not order["contact"]:
                order["current_step"] = "awaiting_contact"
                await message.answer("Пожалуйста, введите Ваш номер телефона или Telegram username (например, @username):")
                return

            order["current_step"] = "awaiting_post_order_action"
            await send_order_summary(message)

        except ValueError:
            await message.answer("Пожалуйста, введите корректную числовую стоимость в юанях (например, 150.5)")

    elif step == "awaiting_contact":
        # Принимаем контакт пользователя
        contact = text.strip()
        order["contact"] = contact
        order["current_step"] = "awaiting_post_order_action"
        await send_order_summary(message)

    elif step == "awaiting_post_order_action":
        if text == "Отправить заказ менеджеру":
            await send_order_to_manager(message)
            await message.answer("Спасибо за заказ! Скоро наш менеджер свяжется с Вами❤️", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Вернуться в начало")))
            user_orders.pop(user_id, None)  # Очистить данные после отправки

        elif text == "Добавить позицию в заказ":
            order["current_item_index"] = len(order["items"])
            order["current_step"] = "awaiting_screenshot"
            await message.answer("Добавляем новую позицию.\n\nПришлите скрин товара")

        elif text == "Вернуться в главное меню":
            user_orders.pop(user_id, None)
            await cmd_start(message)

        else:
            await message.answer("Пожалуйста, выберите одну из кнопок:\n"
                                 "Отправить заказ менеджеру, Добавить позицию в заказ или Вернуться в главное меню")

    else:
        # Любой другой текст игнорируем или отвечаем приветствием
        await message.answer("Используйте меню для взаимодействия.", reply_markup=get_main_menu())

# --- Функция формирования и отправки сводки заказа ---
async def send_order_summary(message: types.Message):
    user_id = message.from_user.id
    order = user_orders[user_id]
    items = order["items"]

    text = f"Ваш заказ:\n\n"
    total_rub = 0
    for i, item in enumerate(items, 1):
        text += f"Товар {i}:\n"
        text += f" - Размер: {item.get('size')}\n"
        text += f" - Категория: {item.get('category')}\n"
        price_yuan = item.get("price_yuan")
        price_rub = item.get("price_rub")
        if price_yuan and price_rub:
            text += f" - Цена: ¥{price_yuan} (~{price_rub} ₽)\n"
            total_rub += price_rub
        text += "\n"

    text += f"Общая сумма заказа: {total_rub} ₽\n\n"
    text += "Если всё верно, отправьте заказ менеджеру, добавьте позицию или вернитесь в меню."

    await message.answer(text, reply_markup=get_post_confirm_keyboard())

# --- Отправка заказа в группу менеджеров ---
async def send_order_to_manager(message: types.Message):
    user_id = message.from_user.id
    order = user_orders.get(user_id)
    if not order:
        await message.answer("Нет данных заказа для отправки.")
        return

    items = order["items"]
    contact = order.get("contact", "Не указан")

    caption = f"Новый заказ от @{message.from_user.username or message.from_user.id} (ID: {user_id})\nКонтакт: {contact}\n\n"
    total_rub = 0
    media_group = types.MediaGroup()

    for i, item in enumerate(items, 1):
        caption += f"Товар {i}:\n"
        caption += f"Размер: {item.get('size')}\n"
        caption += f"Категория: {item.get('category')}\n"
        price_yuan = item.get("price_yuan")
        price_rub = item.get("price_rub")
        if price_yuan and price_rub:
            caption += f"Цена: ¥{price_yuan} (~{price_rub} ₽)\n"
            total_rub += price_rub
        caption += "\n"
        # Добавляем скрин в media_group
        media_group.attach_photo(item["screenshot"])

    caption += f"Общая сумма заказа: {total_rub} ₽"

    try:
        # Отправляем media group с подписью первого фото
        # Telegram API позволяет добавить подпись только к первому элементу
        if media_group.media:
            media_group.media[0].caption = caption
            await bot.send_media_group(MANAGER_CHAT_ID, media_group.media)
        else:
            await bot.send_message(MANAGER_CHAT_ID, caption)
    except Exception as e:
        logging.error(f"Error sending order to manager: {e}")
        await message.answer("Ошибка при отправке заказа менеджеру. Попробуйте позже.")

# --- Обработка кнопок inline (редактирование) ---
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("edit_"))
async def process_edit_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    order = user_orders.get(user_id)
    if not order:
        await callback_query.answer("Данные заказа не найдены.")
        return

    parts = data.split("_")  # например, edit_size_0
    if len(parts) != 3:
        await callback_query.answer("Неверные данные.")
        return

    action, field, idx_str = parts
    idx = int(idx_str)
    order["current_item_index"] = idx

    if field == "screenshot":
        order["current_step"] = "awaiting_screenshot"
        await bot.send_message(user_id, f"Редактирование товара {idx + 1}: пришлите новый скрин.")
    elif field == "size":
        order["current_step"] = "awaiting_size"
        await bot.send_message(user_id, f"Редактирование товара {idx + 1}: введите новый размер.")
    elif field == "category":
        order["current_step"] = "awaiting_category"
        await bot.send_message(user_id, f"Редактирование товара {idx + 1}: выберите новую категорию.", reply_markup=get_category_keyboard())
    elif field == "price":
        order["current_step"] = "awaiting_price"
        try:
            media = types.MediaGroup()
            media.attach_photo(InputFile("price_example_1.jpg"))
            media.attach_photo(InputFile("price_example_2.jpg"))
            media.attach_photo(InputFile("price_example_3.jpg"), caption="Введите новую стоимость в юанях (¥):")
            await bot.send_media_group(user_id, media)
        except Exception as e:
            logging.error(f"Error sending media group for price edit: {e}")
            await bot.send_message(user_id, "Введите новую стоимость в юанях (¥):")
    else:
        await callback_query.answer("Неизвестное действие.")
        return

    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "confirm_order")
async def confirm_order_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.send_message(user_id, "Отлично! Заказ готов к отправке.\n"
                                    "Нажмите кнопку 'Отправить заказ менеджеру' чтобы отправить.\n"
                                    "Или добавьте ещё позиции или вернитесь в меню.",
                           reply_markup=get_post_confirm_keyboard())
    user_orders[user_id]["current_step"] = "awaiting_post_order_action"
    await callback_query.answer()

# --- Запуск бота ---
if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
