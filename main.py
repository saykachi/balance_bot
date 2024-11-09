from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
from datetime import datetime

# Настроим соединение с базой данных
database_file = 'database.db'
conn = sqlite3.connect(database_file)
cursor = conn.cursor()

# Создание таблиц, если они не существуют
def create_tables():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        earnings REAL,
        admin TEXT,
        shift TEXT,
        is_on_shift BOOLEAN,
        platform TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rating (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        earnings REAL
    )
    ''')
    conn.commit()

# Функция для добавления пользователя в базу данных (если его нет)
def add_user(user_id):
    cursor.execute('''
    INSERT INTO users (user_id, name, earnings, admin, shift, is_on_shift, platform)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, '', 0.0, '', '', False, ''))
    conn.commit()

create_tables()

# Функция для обновления или добавления в рейтинг
def update_rating(user_id, earnings, name):
    cursor.execute('''
    INSERT INTO rating (user_id, earnings, name)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET earnings = ?, name = ?
    ''', (user_id, earnings, name, earnings, name))
    conn.commit()

# Функция для получения данных пользователя из базы данных
def get_user_data(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    return user_data

# Функция для отображения рейтинга с кнопкой "Назад"
async def show_daily_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем данные о пользователях, отсортированных по заработку
    cursor.execute("SELECT name, earnings FROM rating ORDER BY earnings DESC LIMIT 10")
    ranking = cursor.fetchall()

    # Формируем сообщение для рейтинга
    ranking_text = "🏆 *Рейтинг за сегодня:*\n\n"
    for i, (name, earnings) in enumerate(ranking, 1):
        ranking_text += f"{i}. {name} - ${earnings}\n"

    # Кнопка "Назад"
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(ranking_text, parse_mode='Markdown', reply_markup=reply_markup)

# Функция для отображения выбора администратора
async def show_admin_selection(update: Update):
    keyboard = [
        [InlineKeyboardButton("🧑‍💼 Админ 1", callback_data="admin_1")],
        [InlineKeyboardButton("🧑‍💼 Админ 2", callback_data="admin_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👔 *Выберите администратора:*", reply_markup=reply_markup, parse_mode='Markdown')

# Функция для отображения выбора платформы
async def show_platform_selection(update: Update):
    keyboard = [
        [InlineKeyboardButton("LOYALFANS", callback_data="LOYALFANS")],
        [InlineKeyboardButton("MANYVIDS", callback_data="MANYVIDS")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌐 *Выберите платформу:*", reply_markup=reply_markup, parse_mode='Markdown')

# Функция для создания клавиатуры выбора администратора
async def admin_selection_markup():
    keyboard = [
        [InlineKeyboardButton("🧑‍💼 Админ 1", callback_data="admin_1")],
        [InlineKeyboardButton("🧑‍💼 Админ 2", callback_data="admin_2")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчик нажатий на кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Получаем данные пользователя из базы данных
    user_data = get_user_data(user_id)

    if query.data == "show_daily_rating":
        # Показываем рейтинг
        await show_daily_rating(update, context)
    elif query.data == "back_to_main_menu":
        # Возвращаем в главное меню
        await show_main_menu(query.message.chat_id, query._bot)

    if user_data is None:
        add_user(user_id)
        user_data = get_user_data(user_id)

    # Обработка нажатий кнопок
    if query.data == "enter_name":
        # Запрашиваем имя пользователя
        await query.edit_message_text("✍️ Напишите своё имя:")
        context.user_data["state"] = "waiting_for_name"
    elif query.data == "admin_1" or query.data == "admin_2":
        admin_name = query.data.split("_")[1]
        cursor.execute("UPDATE users SET admin = ? WHERE user_id = ?", (admin_name, user_id))
        conn.commit()
        await query.edit_message_text(f"✅ Вы выбрали администратора: *{admin_name}*", parse_mode='Markdown')
        # Переходим к выбору платформы после выбора администратора
        await show_platform_selection(query)
    elif query.data == "LOYALFANS" or query.data == "MANYVIDS":
        platform_name = query.data
        cursor.execute("UPDATE users SET platform = ? WHERE user_id = ?", (platform_name, user_id))
        conn.commit()
        await query.edit_message_text(f"✅ Вы выбрали платформу: *{platform_name}*", parse_mode='Markdown')
        # Переходим к выбору смены после выбора платформы
        await show_shift_selection(query)
    elif query.data == "shift_00_06" or query.data == "shift_06_12" or query.data == "shift_12_18" or query.data == "shift_18_00":
        shift_time = query.data.split("_")[1] + " - " + query.data.split("_")[2]
        cursor.execute("UPDATE users SET shift = ? WHERE user_id = ?", (shift_time, user_id))
        conn.commit()
        await query.edit_message_text(f"🕰️ Вы выбрали смену: *{shift_time}*", parse_mode='Markdown')
        # Завершаем регистрацию
        await show_finish_registration(query)
    elif query.data == "start_shift":
        # Начало смены
        await send_shift_start_message(context, user_id)
    elif query.data == "end_shift":
        # Завершение смены
        await send_shift_end_message(query, context, user_id)

# Функция для отправки сообщения о начале смены
async def send_shift_start_message(context, user_id):
    user_data = get_user_data(user_id)
    name = user_data[1]
    shift = user_data[4]

    # Отправляем сообщение пользователю в личные сообщения
    await context.bot.send_message(
        chat_id=user_id,
        text=f"🚀 *Начало смены!*",
        parse_mode='Markdown'
    )

    # Обновляем статус пользователя
    cursor.execute("UPDATE users SET is_on_shift = ? WHERE user_id = ?", (True, user_id))
    conn.commit()

# Новый код для отправки сообщения о завершении смены в группу
async def send_shift_end_message(query, context, user_id):
    user_data = get_user_data(user_id)
    name = user_data[1]  # Имя пользователя
    admin = user_data[3]  # Администратор
    shift = user_data[4]  # Смена
    earnings = user_data[2]  # Заработок
    platform = user_data[6]  # Платформа пользователя

    # Экранируем специальные символы, если нужно (для Markdown):
    name = name.replace("_", "\_").replace("*", "\*").replace("[", "\[").replace("]", "\]")  # и так далее

    # Переводим диалог в состояние ожидания заработка
    await context.bot.send_message(
        chat_id=user_id,
        text="✍️ Напишите, сколько вы заработали за смену:"
    )

    # Ожидаем, что пользователь введет заработок
    context.user_data["state"] = "waiting_for_earnings"
    context.user_data["user_id"] = user_id  # Сохраняем ID пользователя для дальнейшей обработки

# Функция для отображения выбора смены
async def show_shift_selection(query):
    keyboard = [
        [InlineKeyboardButton("00:00 - 06:00", callback_data="shift_00_06")],
        [InlineKeyboardButton("06:00 - 12:00", callback_data="shift_06_12")],
        [InlineKeyboardButton("12:00 - 18:00", callback_data="shift_12_18")],
        [InlineKeyboardButton("18:00 - 00:00", callback_data="shift_18_00")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🕰️ *Выберите смену:*", reply_markup=reply_markup, parse_mode='Markdown')

# Функция для завершения регистрации и отображения основного меню
async def show_finish_registration(query):
    await query.edit_message_text("✅ *Регистрация завершена!* Теперь вы можете использовать основные функции бота.", parse_mode='Markdown')
    await show_main_menu(query.message.chat_id, query._bot)

# Функция для отображения основного меню
async def show_main_menu(chat_id, bot):
    keyboard = [
        [InlineKeyboardButton("📊 Показать рейтинг за сегодня", callback_data="show_daily_rating")],
        [InlineKeyboardButton("🚀 Начать смену", callback_data="start_shift")],
        [InlineKeyboardButton("🏁 Завершить смену", callback_data="end_shift")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(chat_id=chat_id, text="📋 *Основное меню*:", reply_markup=reply_markup, parse_mode='Markdown')

# Обработчик для ввода текста заработка
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text.strip()

    # Проверяем, находимся ли мы в состоянии "ожидание имени"
    if context.user_data.get("state") == "waiting_for_name":
        # Сохраняем имя в базе данных
        cursor.execute("UPDATE users SET name = ? WHERE user_id = ?", (user_input, user_id))
        conn.commit()

        # Меняем состояние на "ожидание администратора"
        context.user_data["state"] = "waiting_for_admin"

        # Переходим к выбору администратора
        await update.message.reply_text("🎉 Имя сохранено! Теперь выберите администратора:", reply_markup=await admin_selection_markup())

    # Проверяем, находимся ли мы в состоянии "ожидание заработка"
    elif context.user_data.get("state") == "waiting_for_earnings":
        # Обновляем заработок пользователя в базе данных
        cursor.execute("UPDATE users SET earnings = ? WHERE user_id = ?", (user_input, user_id))
        conn.commit()

        # Получаем обновленные данные пользователя
        user_data = get_user_data(user_id)
        name = user_data[1]  # Имя пользователя
        admin = user_data[3]  # Администратор
        shift = user_data[4]  # Смена
        platform = user_data[6]  # Платформа

        # Экранируем специальные символы для Markdown
        name = name.replace("_", "\_").replace("*", "\*").replace("[", "\[").replace("]", "\]")

        # Отправляем информацию о завершении смены в группу с использованием HTML-разметки
        await context.bot.send_message(
            chat_id=-1002424831865,  # Замените на ваш ID группы
            text=f"🏁 <b>Смена завершена!</b>\n"
                 f"👤 <b>Имя:</b> {name}\n"
                 f"🧑‍💼 <b>Админ:</b> {admin}\n"
                 f"🕒 <b>Смена:</b> {shift}\n"
                 f"💵 <b>Заработок:</b> ${user_input}\n"
                 f"🌐 <b>Платформа:</b> {platform}",
            parse_mode='HTML'  # Используем HTML вместо Markdown
        )

        # Завершаем обработку и уведомляем пользователя
        await update.message.reply_text(f"✅ Ваш заработок за смену: ${user_input}. Спасибо!")

        # Отправляем основное меню
        await show_main_menu(update.message.chat_id, update._bot)

        # Очистим состояние, чтобы избежать бесконечного запроса
        context.user_data["state"] = None  # Сбрасываем состояние после завершения

# Главная функция для запуска бота
async def show_registration_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📝 Ввести имя", callback_data="enter_name")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎉 *Начнём регистрацию!* Пожалуйста, введите своё имя.", reply_markup=reply_markup, parse_mode='Markdown')

# Your bot token here
BOT_TOKEN = '7635200135:AAG3n_WdCFAGQwtipLFqgaBKZyIoM1CC-vE'

def main():
    # Initialize bot application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers for commands
    application.add_handler(CommandHandler("start", show_registration_menu))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


    # Start polling updates from Telegram
    application.run_polling()

if __name__ == "__main__":
    main()
