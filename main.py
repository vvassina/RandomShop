from aiogram import Bot, Dispatcher, executor
import os

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message):
    await message.answer("Бот жив!")

if _name_ == '_main_':
    executor.start_polling(dp)
