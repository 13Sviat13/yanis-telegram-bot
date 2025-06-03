import asyncio
import threading
import time
from flask import Flask
from telegram.ext import ApplicationBuilder, PicklePersistence
from config import BOT_TOKEN, DATABASE_URL
from bot.models import db
from bot.commands.reminder import check_reminders, reminder_loop, worker

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def create_bot():
    persistence = PicklePersistence(filepath="data/bot_persistence.pickle")

    app_builder = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence)
    bot = app_builder.build()

    return bot


def start_reminder_system():
    """Запуск системи нагадувань у окремому потоці"""
    asyncio.set_event_loop(reminder_loop)
    reminder_loop.create_task(worker())

    def run_checks():
        while True:
            try:
                with app.app_context():
                    check_reminders()
            except Exception as e:
                print(f"Помилка перевірки: {e}")
            time.sleep(30)

    thread = threading.Thread(target=run_checks, daemon=True)
    thread.start()
    return thread


@app.route('/')
def home():
    return "Bot is running"


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        from bot.bot import register_handlers

        reminder_thread = start_reminder_system()

        bot = create_bot()

        register_handlers(bot)

        print("Бот запущений. Система нагадувань активна.")

        try:
            bot.run_polling()
        finally:
            reminder_loop.stop()
