from datetime import datetime, timedelta
from telegram import Bot, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.request import HTTPXRequest
from config import BOT_TOKEN
from bot.models import db, Task
import asyncio

bot = Bot(token=BOT_TOKEN, request=HTTPXRequest(connection_pool_size=10))
reminder_loop = asyncio.new_event_loop()
asyncio.set_event_loop(reminder_loop)
queue = asyncio.Queue()
active_tasks = set()


async def worker():

    while True:
        task = await queue.get()
        try:
            if task.id in active_tasks:
                continue

            active_tasks.add(task.id)

            if not task.reminder_sent:
                await send_first_reminder(task)
            elif not task.follow_up_sent and datetime.utcnow() >= task.follow_up_time:
                await send_follow_up(task)

        except Exception as e:
            print(f"Помилка обробки завдання {task.id}: {e}")
        finally:
            queue.task_done()


async def send_first_reminder(task):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Виконано", callback_data=f"done:{task.id}"),
            InlineKeyboardButton("⏱ Перенести", callback_data=f"delay:{task.id}")
        ]
    ])
    await bot.send_message(
        chat_id=task.user_id,
        text=f"⏰❓ Ви виконали '{task.description}'?",
        reply_markup=keyboard
    )
    task.reminder_sent = True
    task.follow_up_time = datetime.utcnow() + timedelta(hours=3)
    db.session.commit()


async def send_follow_up(task):
    """Відправка повторного нагадування"""
    await bot.send_message(
        chat_id=task.user_id,
        text=f"❓ Ви виконали '{task.description}'?",
        reply_markup=ReplyKeyboardMarkup([
            ["✅ Так, видалити", "⏱ Перенести на 1 год", "🔄 Перенести на 3 год"]
        ], one_time_keyboard=True)
    )
    task.follow_up_sent = True
    db.session.commit()


def check_reminders():
    """Пошук та додавання нагадувань у чергу"""
    try:
        now = datetime.now()
        print(f"Перевірка нагадувань о {now}")

        first_reminders = db.session.query(Task).filter(
            Task.remind_at <= now,
            Task.reminder_sent.is_(False)
        ).all()

        follow_ups = db.session.query(Task).filter(
            Task.follow_up_time <= now,
            Task.follow_up_sent.is_(False),
            Task.reminder_sent.is_(True)
        ).all()
        print(f"Знайдено {len(first_reminders)} перших та {len(follow_ups)} повторних нагадувань")

        for task in first_reminders + follow_ups:
            asyncio.run_coroutine_threadsafe(queue.put(task), reminder_loop)

        print(f"Додано до черги: {len(first_reminders)} перших та {len(follow_ups)} повторних нагадувань")

    except Exception as e:
        print(f"Помилка пошуку нагадувань: {e}")
    finally:
        db.session.close()
