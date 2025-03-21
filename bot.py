import logging
import paramiko
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonCommands

TOKEN = "7056307221:AAG3hT2Vyn5AXaMTWrqr0JvaxXHks_4KkVk"
SSH_HOST = "34.88.223.194"
SSH_PORT = 22
SSH_USER = "zokirjonovjavohir61"
SSH_KEY_PATH = "id_rsa"
AUTHORIZED_USERS = [1395804259]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Главное меню (осталось внизу)
menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚀 Запустить сервер", callback_data="run_server")],
    [InlineKeyboardButton(text="🛑 Остановить сервер", callback_data="stop_server")],
    [InlineKeyboardButton(text="🔄 Обновить сервер", callback_data="update_server")]
])

async def set_bot_commands():
    commands = [
        types.BotCommand(command="start", description="Главное меню"),
        types.BotCommand(command="run", description="Запустить сервер"),
        types.BotCommand(command="stop", description="Остановить сервер"),
        types.BotCommand(command="update", description="Обновить сервер")
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

def execute_ssh_command(command, async_mode=False):
    """
    Выполняет команду по SSH.
    Если `async_mode=True`, команда запускается в фоне (не блокирует бота).
    """
    try:
        key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=key)

        if async_mode:
            # Запускаем в фоне
            command = f"nohup {command} > /dev/null 2>&1 &"

        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        client.close()

        logging.info(f"Команда выполнена: {command}\nВывод: {output}\nОшибка: {error}")
        return output if output else error
    except Exception as e:
        logging.error(f"Ошибка SSH: {e}")
        return f"Ошибка: {str(e)}"

@dp.message()
async def start(message: types.Message):
    if message.from_user.id not in AUTHORIZED_USERS:
        await message.answer("⛔ У тебя нет прав на управление сервером.")
        return
    await message.answer("👋 Привет! Управляй сервером с помощью кнопок:", reply_markup=menu_keyboard)

@dp.callback_query(lambda c: c.data == "run_server")
async def run_server(callback: types.CallbackQuery):
    # Отправляем пользователю мгновенное сообщение
    await callback.message.edit_text("🚀 Запускаю сервер CS2...")

    # Запускаем сервер в фоне
    asyncio.create_task(start_cs2_server())

    # Отправляем текст с командой подключения
    connect_text = f"🎮 Подключение к серверу:\n```connect {SSH_HOST}:27015```"

    await callback.message.answer(
        f"✅ Сервер запущен!\n\n{connect_text}\n\n"
        "Скопируй команду и вставь в консоль CS2.",
        parse_mode="Markdown",
        reply_markup=menu_keyboard
    )

async def start_cs2_server():
    """
    Запускает сервер CS2 в фоне через screen.
    """
    command = (
        "screen -dmS cs2_server bash -c '"
        "cd /home/zokirjonovjavohir61/.steam/steam/steamapps/common/Counter-Strike\\ Global\\ Offensive/game/bin/linuxsteamrt64/ && "
        "chmod +x start.sh && ./start.sh > cs2_log.txt 2>&1'"
    )
    output = execute_ssh_command(command)
    logging.info(f"Запуск сервера: {output}")


@dp.callback_query(lambda c: c.data == "stop_server")
async def stop_server(callback: types.CallbackQuery):
    execute_ssh_command("pkill -f cs2")
    await callback.message.edit_text("✅ Сервер остановлен.", reply_markup=menu_keyboard)

@dp.callback_query(lambda c: c.data == "update_server")
async def update_server(callback: types.CallbackQuery):
    execute_ssh_command("steamcmd +login anonymous +app_update 730 +quit")
    await callback.message.edit_text("✅ Сервер обновлен! Теперь запусти его снова.", reply_markup=menu_keyboard)

async def on_startup():
    await set_bot_commands()

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
