import json
import time
from datetime import timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters, ContextTypes

CONFIG_FILE = "config.json"

# Загрузка данных из config.json
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Сохранение данных в config.json
def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# Добавление брака
def add_marriage(chat_id, user1_id, user2_id):
    data = load_config()

    if chat_id not in data:
        data[chat_id] = []

    data[chat_id].append({
        "users": [user1_id, user2_id],
        "start_time": time.time()
    })
    save_config(data)

# Удаление брака
def remove_marriage(chat_id, user1_id, user2_id):
    data = load_config()
    if chat_id not in data:
        return False

    data[chat_id] = [
        marriage for marriage in data[chat_id]
        if set(marriage["users"]) != {user1_id, user2_id}
    ]
    save_config(data)
    return True

# Получение брака для пользователя
def get_user_marriage(chat_id, user_id):
    data = load_config()
    if chat_id not in data:
        return None

    for marriage in data[chat_id]:
        if user_id in marriage["users"]:
            return marriage
    return None

# Форматирование времени
def format_duration(seconds):
    delta = timedelta(seconds=int(seconds))
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days} дней {hours} часов {minutes} минут {seconds} секунд"
    return f"{hours} часов {minutes} минут {seconds} секунд"

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat_id)
    user = update.message.from_user
    text = update.message.text.lower()

    # Предложение брака
    if text.startswith("брак") and update.message.reply_to_message:
        partner = update.message.reply_to_message.from_user

        # Проверка на одинаковых пользователей
        if user.id == partner.id:
            await update.message.reply_text("Вы не можете заключить брак сами с собой!")
            return

        # Проверка на существующий брак
        if get_user_marriage(chat_id, user.id) or get_user_marriage(chat_id, partner.id):
            await update.message.reply_text("Один из вас уже в браке!")
            return

        # Кнопки для подтверждения
        keyboard = [
            [
                InlineKeyboardButton("Согласиться 💍", callback_data=f"accept|{user.id}|{partner.id}"),
                InlineKeyboardButton("Отклонить ❌", callback_data=f"decline|{user.id}|{partner.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"{partner.mention_html()}, {user.mention_html()} предлагает вам вступить в брак! 🥰",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    # Просмотр списка браков
    elif text == "браки":
        data = load_config()
        if chat_id not in data or not data[chat_id]:
            await update.message.reply_text("В этом чате пока нет браков.")
            return

        now = time.time()
        marriages = data[chat_id]
        marriages.sort(key=lambda x: now - x["start_time"], reverse=True)
        marriage_list = []
        for i, marriage in enumerate(marriages, 1):
            user1 = await context.bot.get_chat_member(chat_id, marriage["users"][0])
            user2 = await context.bot.get_chat_member(chat_id, marriage["users"][1])
            duration = format_duration(now - marriage["start_time"])
            marriage_list.append(
                f"{i}. {user1.user.mention_html()} + {user2.user.mention_html()} ({duration})"
            )

        await update.message.reply_text("\n".join(marriage_list), parse_mode="HTML")

    # Развод
    elif text == "развод":
        marriage = get_user_marriage(chat_id, user.id)
        if not marriage:
            await update.message.reply_text("Вы не состоите в браке!")
            return

        partner_id = marriage["users"][0] if marriage["users"][1] == user.id else marriage["users"][1]
        remove_marriage(chat_id, user.id, partner_id)
        partner = await context.bot.get_chat_member(chat_id, partner_id)
        await update.message.reply_text(f"💔 {user.mention_html()} и {partner.user.mention_html()} развелись.", parse_mode="HTML")

# Обработчик колбэков кнопок
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action, user1_id, user2_id = data[0], int(data[1]), int(data[2])
    chat_id = str(query.message.chat_id)

    if query.from_user.id != user2_id:
        await query.answer("Вы не можете взаимодействовать с этой кнопкой.", show_alert=True)
        return

    user1 = await context.bot.get_chat_member(chat_id, user1_id)
    user2 = await context.bot.get_chat_member(chat_id, user2_id)

    if action == "accept":
        add_marriage(chat_id, user1_id, user2_id)
        await query.edit_message_text(
            f"🎉 {user1.user.mention_html()} и {user2.user.mention_html()} теперь в браке! 🥰",
            parse_mode="HTML"
        )
    elif action == "decline":
        await query.edit_message_text(
            f"❌ {user2.user.mention_html()} отклонил предложение брака от {user1.user.mention_html()}.",
            parse_mode="HTML"
        )

import os
import time
from config import BOT_TOKEN
from init.designations import BOT_OWNER
from init.designations import OWNER_LINK
from init.designations import TELEGRAM_LINK
from init.designations import PROGRAM_LANGUAGE
from rich.console import Console
from rich.table import Table
from rich.text import Text
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, filters

def clear_console():
    """Очищает консоль в зависимости от операционной системы."""
    if os.name == 'nt':  # Для Windows
        os.system('cls')
    else:  # Для Linux, macOS, и других Unix-подобных систем
        os.system('clear')

def main():
    # Очищаем консоль перед выводом
    clear_console()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Информация о боте
    bot_info = app.bot.get_me()

    # Инициализация консоли для вывода
    console = Console()

    # Создание таблицы с информацией о боте
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Информация", style="bold blue")
    table.add_column("Значение", style="bold green")

    # Добавление данных в таблицу
    table.add_row("Токен бота", Text(BOT_TOKEN, style="bold cyan"))
    table.add_row("Дата запуска", Text(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()), style="bold yellow"))
    table.add_row("Создатель бота", Text(BOT_OWNER, style="bold white"))
    table.add_row("Github", Text(OWNER_LINK, style="bold purple"))
    table.add_row("По поводу заказов", Text(TELEGRAM_LINK, style="bold magenta"))
    table.add_row("Языки программирования", Text(PROGRAM_LANGUAGE, style="bold green"))

    # Создание раздела с командами
    table.add_row("Список команд", Text("/брак — предложение о браке\n/браки — просмотр списка браков\n/развод — развод", style="bold red"))

    # Вывод таблицы
    console.print(table)

    # Сообщение о готовности бота
    console.print("\nБот готов к работе!", style="bold green")

    # Обработчики команд
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()

if __name__ == "__main__":
    main()
