import logging
import paramiko
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonCommands
from aiogram.filters import Command

# 🔐 ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ
TOKEN = "7056307221:AAG3hT2Vyn5AXaMTWrqr0JvaxXHks_4KkVk"
SSH_HOST = "34.88.223.194"
SSH_PORT = 22
SSH_USER = "zokirjonovjavohir61"
SSH_KEY_PATH = "id_rsa"
AUTHORIZED_USERS = [1395804259]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# 📌 Главное меню
menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚀 Запустить сервер", callback_data="run_server")],
    [InlineKeyboardButton(text="🛑 Остановить сервер", callback_data="stop_server")],
    [InlineKeyboardButton(text="🔄 Обновить сервер", callback_data="update_server")],
    [InlineKeyboardButton(text="📡 Статус сервера", callback_data="server_status")],
])

async def set_bot_commands():
    commands = [
        types.BotCommand(command="start", description="Главное меню"),
        types.BotCommand(command="run", description="Запустить сервер"),
        types.BotCommand(command="stop", description="Остановить сервер"),
        types.BotCommand(command="update", description="Обновить сервер"),
        types.BotCommand(command="status", description="Проверить статус сервера"),
        types.BotCommand(command="cmd", description="Команды для КС2")
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

def execute_ssh_command(command):
    """ Выполняет команду на сервере по SSH """
    try:
        key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=key)

        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        client.close()

        logging.info(f"Команда: {command}\nВывод: {output}\nОшибка: {error}")
        return output if output else error
    except Exception as e:
        logging.error(f"Ошибка SSH: {e}")
        return f"Ошибка: {str(e)}"

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id not in AUTHORIZED_USERS:
        await message.answer("⛔ У тебя нет прав на управление сервером.")
        return
    await message.answer("👋 Привет! Управляй сервером с помощью кнопок:", reply_markup=menu_keyboard)

@dp.callback_query(lambda c: c.data == "run_server")
async def run_server(callback: types.CallbackQuery):
    # Удаляем предыдущее сообщение
    await callback.message.delete()

    asyncio.create_task(start_cs2_server())

    connect_text = f"🎮 Подключение к серверу:\n```connect {SSH_HOST}:27015```"
    await callback.message.answer(
        f"✅ Сервер запущен!\n\n{connect_text}\n\n"
        "Скопируй команду и вставь в консоль CS2.",
        parse_mode="Markdown",
        reply_markup=menu_keyboard
    )

async def start_cs2_server():
    """ Запускает CS2 сервер в screen cs2_console """
    command = (
        "screen -dmS cs2_console bash -c '"
        "cd /home/zokirjonovjavohir61/.steam/steam/steamapps/common/Counter-Strike\\ Global\\ Offensive/game/bin/linuxsteamrt64/ && "
        "chmod +x start.sh && ./start.sh > cs2_log.txt 2>&1'"
    )
    execute_ssh_command(command)

@dp.callback_query(lambda c: c.data == "stop_server")
async def stop_server(callback: types.CallbackQuery):
    # Удаляем предыдущее сообщение
    await callback.message.delete()
    
    execute_ssh_command("screen -S cs2_console -X quit")
    await callback.message.answer("✅ Сервер остановлен.", reply_markup=menu_keyboard)

@dp.callback_query(lambda c: c.data == "update_server")
async def update_server(callback: types.CallbackQuery):
    # Удаляем предыдущее сообщение
    await callback.message.delete()
    
    execute_ssh_command("steamcmd +login anonymous +app_update 730 +quit")
    await callback.message.answer("✅ Сервер обновлен! Теперь запусти его снова.", reply_markup=menu_keyboard)

@dp.callback_query(lambda c: c.data == "server_status")
async def server_status(callback: types.CallbackQuery):
    # Удаляем предыдущее сообщение
    await callback.message.delete()
    
    output = execute_ssh_command("screen -ls | grep cs2_console")

    if "cs2_console" in output:
        connect_text = f"🎮 Подключение к серверу:\n```connect {SSH_HOST}:27015```"
        status_text = f"✅ Сервер **запущен**!\n\n{connect_text}\n\nСкопируй команду и вставь в консоль CS2."
    else:
        status_text = "❌ Сервер **выключен**!"

    await callback.message.answer(status_text, parse_mode="Markdown", reply_markup=menu_keyboard)

@dp.message(lambda m: m.text.startswith("/cmd"))
async def send_server_command(message: types.Message):
    """Отправляет команду в консоль CS2-сервера."""
    if message.from_user.id not in AUTHORIZED_USERS:
        await message.answer("⛔ У тебя нет прав на управление сервером.")
        return

    # Извлекаем команду из сообщения
    command = message.text[len("/cmd "):].strip()
    if not command:
        await message.answer("⚠️ Пожалуйста, укажите команду после `/cmd`.")
        return

    # Отправляем команду в screen сессию
    result = execute_ssh_command(f"screen -S cs2_console -X stuff '{command}\n'")
    
    if "No screen session found" in result:
        await message.answer("❌ Сервер не запущен. Запустите сервер перед отправкой команд.")
    else:
        await message.answer(f"✅ Команда `{command}` отправлена на сервер.")

async def on_startup():
    await set_bot_commands()

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())