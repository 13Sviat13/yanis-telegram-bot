import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from bot.models import db, Task, JournalEntry, MoodEntry, PomodoroSession

ENTRY_TYPE_CONFIG_LOGIC = {
    "idea": {"model": JournalEntry, "display_name": "Ідея"},
    "thought": {"model": JournalEntry, "display_name": "Думка"},
    "dream": {"model": JournalEntry, "display_name": "Сон"},
    "note": {"model": JournalEntry, "display_name": "Замітка"},
    "mood": {"model": MoodEntry, "display_name": "Запис про настрій"}
}


def mark_task_as_done_logic(user_id: int, task_id: int) -> tuple[Task | None, str]:
    """
    Знаходить завдання за ID та user_id, позначає його як виконане.
    Встановлює completed_at, reminder_sent, follow_up_sent.
    Повертає кортеж: (об'єкт завдання, повідомлення про успіх/помилку).
    """
    message = ""
    task_obj = None
    try:
        task_obj = Task.query.filter_by(id=task_id, user_id=user_id).first()

        if not task_obj:
            message = "Такого завдання не існує або воно належить іншому користувачу."
            return None, message

        if task_obj.completed:
            message = f"☑️ Завдання «{task_obj.description}» вже було виконане."
            return task_obj, message

        task_obj.completed = True
        task_obj.completed_at = datetime.utcnow()
        task_obj.reminder_sent = True
        task_obj.follow_up_sent = True
        db.session.commit()
        message = f"✅ Завдання «{task_obj.description}» успішно позначено як виконане!"
        print(f"LOGIC: Завдання {task_id} користувача {user_id} позначено як виконане.")
        return task_obj, message
    except Exception as e:
        db.session.rollback()
        print(f"Помилка в mark_task_as_done_logic для task_id {task_id}: {e}")
        message = f"Сталася помилка при оновленні завдання: {e}"
        return None, message
    finally:
        db.session.close()


def set_task_reminder_logic(user_id: int, task_id: int, remind_time_str: str | None) -> tuple[Task | None, str]:
    """
    Встановлює або вимикає нагадування для завдання.
    Конвертує введений локальний час в UTC для збереження.
    Повертає кортеж: (об'єкт завдання, повідомлення про результат).
    """
    session = db.session
    try:
        task = session.query(Task).filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return None, "Завдання не знайдено."

        if not remind_time_str or remind_time_str.strip().lower() == 'off':
            task.remind_at = None
            task.reminder_sent = False
            task.follow_up_sent = False
            session.commit()
            return task, "⏰ Нагадування вимкнено."

        parsed_local_naive = None
        if ' ' in remind_time_str.strip():
            try:
                parsed_local_naive = datetime.strptime(remind_time_str.strip(), '%d.%m.%Y %H:%M')
            except ValueError:
                try:
                    parsed_local_naive = datetime.strptime(remind_time_str.strip(), '%Y-%m-%d %H:%M')
                except ValueError:
                    raise ValueError("Невірний формат дати та часу.")
        else:
            remind_time_obj = datetime.strptime(remind_time_str.strip(), '%H:%M').time()
            now_local = datetime.now()
            parsed_local_naive = datetime.combine(now_local.date(), remind_time_obj)
            if parsed_local_naive < now_local:
                parsed_local_naive += timedelta(days=1)

        if parsed_local_naive:
            if parsed_local_naive.tzinfo is None:
                local_aware = parsed_local_naive.astimezone()
            else:
                local_aware = parsed_local_naive

            utc_aware = local_aware.astimezone(timezone.utc)
            task.remind_at = utc_aware.replace(tzinfo=None)

            task.reminder_sent = False
            task.follow_up_sent = False
            session.commit()
            return task, f"⏰ Нагадування для «{task.description}» встановлено на {parsed_local_naive.strftime('%d.%m.%Y %H:%M')} (ваш місцевий час)."
        else:
            return task, "Помилка обробки часу."

    except ValueError as ve:
        return None, f"⚠️ Невірний формат часу: {ve}. Використовуйте HH:MM, dd.mm.YYYY HH:MM або YYYY-MM-DD HH:MM."
    except Exception as e:
        session.rollback()
        print(f"Помилка в set_task_reminder_logic для task_id {task_id}: {e}")
        return None, f"Сталася помилка при встановленні нагадування: {e}"
    finally:
        session.close()


def delay_task_reminder_logic(user_id: int, task_id: int, user_input_delay: str) -> tuple[Task | None, str]:
    """Переносить нагадування для завдання. Конвертує в UTC."""
    session = db.session
    try:
        task = session.query(Task).filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return None, "⚠️ Завдання не знайдено."

        new_local_naive_time = None
        time_str_for_reply = ""

        if user_input_delay.isdigit():
            hours = int(user_input_delay)
            new_local_naive_time = datetime.now() + timedelta(hours=hours)
            time_str_for_reply = f"{hours} годин(и)"
        else:
            try:
                input_time_obj = datetime.strptime(user_input_delay, "%H:%M").time()
                now_local = datetime.now()
                new_local_naive_time = datetime.combine(now_local.date(), input_time_obj)
                if new_local_naive_time < now_local:
                    new_local_naive_time += timedelta(days=1)
                time_str_for_reply = new_local_naive_time.strftime("%H:%M (%d.%m)")
            except ValueError:
                return task, "❌ Невірний формат для перенесення. Введіть число (години) або час у форматі HH:MM"

        if new_local_naive_time:
            local_aware = new_local_naive_time.astimezone()
            utc_aware = local_aware.astimezone(timezone.utc)
            task.remind_at = utc_aware.replace(tzinfo=None)

            task.reminder_sent = False
            task.follow_up_sent = False
            session.commit()
            return task, f"🔁 Нагадування перенесено на {time_str_for_reply}."
        else:
            return task, "Помилка розрахунку нового часу для перенесення."

    except Exception as e:
        session.rollback()
        print(f"Помилка в delay_task_reminder_logic для task_id {task_id}: {e}")
        return None, f"❌ Помилка при перенесенні: {str(e)}"
    finally:
        session.close()


def update_pomodoro_session_db(session_id: int | None, status: str,
                               end_time_utc: datetime | None = None) -> PomodoroSession | None:
    """Оновлює статус та/або час завершення існуючої сесії Pomodoro в БД."""
    if not session_id:
        return None

    session_db_obj = None
    session = db.session
    try:
        session_db_obj = session.query(PomodoroSession).get(session_id)
        if session_db_obj:
            session_db_obj.status = status
            session_db_obj.end_time = end_time_utc if end_time_utc else datetime.now(timezone.utc).replace(
                tzinfo=None)
            session.commit()
            print(f"LOGIC: Pomodoro сесія {session_id} оновлена, статус: {status}")
            return session_db_obj
        else:
            print(f"LOGIC WARNING: Pomodoro сесія {session_id} не знайдена для оновлення.")
            return None
    except Exception as e:
        session.rollback()
        print(f"Помилка в update_pomodoro_session_db для session_id {session_id}: {e}")
        return None
    finally:
        session.close()


def create_pomodoro_session_db(user_id: int, duration_minutes: int, session_type: str,
                               task_id: int | None = None) -> int | None:
    """Створює нову сесію Pomodoro в БД та повертає її ID."""
    session = db.session
    try:
        new_pom_session = PomodoroSession(
            user_id=user_id,
            task_id=task_id,
            duration_minutes=duration_minutes,
            session_type=session_type,
            status='started',
            start_time=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(new_pom_session)
        session.commit()
        print(f"LOGIC: Створено Pomodoro сесію {new_pom_session.id} для user {user_id}, task_id: {task_id}")
        return new_pom_session.id
    except Exception as e:
        session.rollback()
        print(f"Помилка в create_pomodoro_session_db: {e}")
        return None
    finally:
        session.close()


def save_generic_entry_logic(
        user_id: int,
        command: str,
        full_content_input: str) -> tuple[object | None, str, list[str] | None, str | None]:

    session = db.session
    created_entry_obj = None
    message_for_user = ""
    parsed_tags_list = []
    text_for_mood_analysis = None

    config = ENTRY_TYPE_CONFIG_LOGIC.get(command)
    if not config:
        return None, "Невідомий тип запису для збереження.", None, None

    entry_model = config["model"]
    display_entry_type_for_msg = config["display_name"]
    entry_type_for_db = command  # "idea", "thought", "dream", "mood"

    rating = None
    text_content_for_db = full_content_input

    try:
        if entry_type_for_db == "mood":
            mood_args = full_content_input.split(' ', 1)
            if mood_args and mood_args[0].isdigit():
                potential_rating = int(mood_args[0])
                if 1 <= potential_rating <= 5:
                    rating = potential_rating
                    text_content_for_db = mood_args[1].strip() if len(mood_args) > 1 else ""

            if rating is None and not text_content_for_db.strip():
                return None, f"Будь ласка, для /{command} додайте опис настрою або оцінку (1-5).", None, None

        parsed_tags_list = re.findall(r"#(\w+)", full_content_input)
        tags_str_for_db = ",".join(sorted(list(set(parsed_tags_list)))) if parsed_tags_list else None

        entry_data = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None)
        }

        if entry_model == JournalEntry:
            entry_data["entry_type"] = entry_type_for_db
            entry_data["content"] = text_content_for_db
            entry_data["tags_str"] = tags_str_for_db
        elif entry_model == MoodEntry:
            entry_data["rating"] = rating
            entry_data["text"] = text_content_for_db if text_content_for_db.strip() else None
            entry_data["tags_str"] = tags_str_for_db
            text_for_mood_analysis = text_content_for_db

        new_entry = entry_model(**entry_data)
        session.add(new_entry)
        session.commit()
        created_entry_obj = new_entry

        message_parts = [f"{display_entry_type_for_msg} успішно збережено!"]
        if entry_model == MoodEntry and rating:
            message_parts.append(f"Оцінка: {rating}/5")

        text_in_confirmation = text_content_for_db
        if text_in_confirmation and text_in_confirmation.strip():
            display_text_confirm = text_in_confirmation[:100] + "..." if len(
                text_in_confirmation) > 100 else text_in_confirmation
            message_parts.append(f"Запис: «{display_text_confirm}»")
        if parsed_tags_list:
            message_parts.append(f"Теги: {', '.join([f'#{t}' for t in parsed_tags_list])}")
        message_for_user = "\n".join(message_parts)

        print(f"LOGIC: Збережено {entry_type_for_db} для user {user_id}. ID: {new_entry.id}, Теги: {tags_str_for_db}")
        return created_entry_obj, message_for_user, parsed_tags_list, text_for_mood_analysis

    except Exception as e:
        session.rollback()
        print(f"Помилка в save_generic_entry_logic ({entry_type_for_db}): {e}")
        import traceback
        traceback.print_exc()
        message_for_user = f"Вибачте, сталася помилка. При збереженні вашого запису ({display_entry_type_for_msg})."
        return None, message_for_user, None, None
    finally:
        session.close()


def create_task_logic(
        user_id: int,
        description: str,
        default_priority: int
) -> Task | None:
    """
    Створює нове завдання з описом та пріоритетом за замовчуванням.
    Повертає створений об'єкт Task або None у разі помилки.
    """
    session = db.session
    new_task_id = None
    task_description = None
    try:
        new_task = Task(
            user_id=user_id,
            description=description,
            priority=default_priority,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(new_task)
        session.commit()
        new_task_id = new_task.id
        task_description = new_task.description
        print(f"LOGIC: Створено завдання ID {new_task_id} для user {user_id} з пріоритетом {default_priority}")
        return new_task_id, task_description
    except Exception as e:
        session.rollback()
        print(f"Помилка в create_task_logic: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    finally:
        session.close()


def set_task_priority_logic(
        user_id: int,
        task_id: int,
        priority_value: int
) -> tuple[Task | None, str | None, int | None]:
    """
    Знаходить завдання та встановлює пріоритет.
    Повертає: (
    об'єкт Task | None, опис завдання str | None,
    встановлений пріоритет int | None
    ).
    """
    session = db.session
    task_description = None
    actual_priority_set = None
    task = None
    try:
        task = session.query(Task).filter_by(id=task_id, user_id=user_id).first()
        if not task:
            return None, "Завдання не знайдено", None

        task.priority = priority_value
        session.commit()
        task_description = task.description
        actual_priority_set = task.priority
        return task, task_description, actual_priority_set
    except Exception as e:
        session.rollback()
        print(f"Помилка в set_task_priority_logic для task_id {task_id}: {e}")
        return None, f"Помилка оновлення пріоритету: {e}", None
    finally:
        session.close()


def get_active_tasks_page_logic(
        user_id: int,
        page: int,
        page_size: int
) -> tuple[list[Task], int, int]:
    """
    Отримує сторінку активних (невиконаних) завдань для користувача.
    Сортує за пріоритетом (спадання), потім за ID (зростання).
    Повертає: (
    список завдань на сторінці,
    загальна кількість активних завдань,
    загальна кількість сторінок
    ).
    """
    session = db.session
    tasks_on_page = []
    total_active_tasks = 0
    num_pages = 0
    try:
        offset = page * page_size

        tasks_query_for_page = session.query(Task).filter_by(
            user_id=user_id,
            completed=False
        ).order_by(Task.priority.desc(),
                   Task.id.asc()).offset(offset).limit(page_size)
        tasks_on_page = tasks_query_for_page.all()

        total_active_tasks_query = session.query(Task).filter_by(
            user_id=user_id,
            completed=False
        )
        total_active_tasks = total_active_tasks_query.count()

        if total_active_tasks > 0:
            num_pages = (total_active_tasks + page_size - 1) // page_size
        if (num_pages == 0 and total_active_tasks > 0):
            num_pages = 1

        print(
            f"LOGIC: get_active_tasks_page - User {user_id}, "
            f"Page {page}, PageSize {page_size}. "
            f"Found {len(tasks_on_page)} tasks on page, "
            f"Total active: {total_active_tasks}, "
            f"NumPages: {num_pages}"
        )
        return tasks_on_page, total_active_tasks, num_pages

    except Exception as e:
        print(f"Помилка в get_active_tasks_page_logic для user {user_id}: {e}")
        return [], 0, 0
    finally:
        session.close()


def get_paginated_entries_logic(
        user_id: int,
        page: int,
        page_size: int,
        model_to_query: db.Model,
        tag_filter: str | None = None,
        entry_type_filter: str | None = None
) -> tuple[list, int, int]:
    """
    Універсальна функція для отримання сторінки записів (JournalEntry або MoodEntry)
    з фільтрами та пагінацією.
    """
    session = db.session
    entries_on_page = []
    total_filtered_entries = 0
    num_pages = 0

    try:
        query = session.query(model_to_query).filter_by(user_id=user_id)

        if tag_filter and hasattr(model_to_query, 'tags_str'):
            query = query.filter(model_to_query.tags_str.ilike(f"%{tag_filter}%"))

        if (model_to_query == JournalEntry
                and entry_type_filter
                and hasattr(model_to_query,
                            'entry_type'
                            )):
            query = query.filter(model_to_query.entry_type == entry_type_filter)

        query = query.order_by(model_to_query.created_at.desc())

        total_filtered_entries = query.count()

        offset = page * page_size
        entries_on_page = query.offset(offset).limit(page_size).all()

        if total_filtered_entries > 0:
            num_pages = (total_filtered_entries + page_size - 1) // page_size
        if num_pages == 0 and total_filtered_entries > 0 :
            num_pages = 1

        print(f"LOGIC: get_paginated_entries - User {user_id}, "
              f"Model {model_to_query.__name__}, Page {page}, "
              f"Tag '{tag_filter}', Type '{entry_type_filter}'. "
              f"Found {len(entries_on_page)} on page, "
              f"Total: {total_filtered_entries}, "
              f"NumPages: {num_pages}")
        return entries_on_page, total_filtered_entries, num_pages

    except Exception as e:
        print(f"Помилка в get_paginated_entries_logic для user {user_id}, "
              f"model {model_to_query.__name__}: {e}")
        return [], 0, 0
    finally:
        session.close()


def get_statistics_logic(user_id: int) -> dict:
    # """
    # Збирає статистику для користувача (завдання, Pomodoro).
    # Повертає словник зі статистичними даними.
    # """
    stats_data = {}
    session = db.session
    try:
        now_utc = datetime.now(timezone.utc)
        today_start_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start_utc = today_start_utc - timedelta(days=now_utc.weekday())
        month_start_utc = today_start_utc.replace(day=1)

        stats_data['tasks_today'] = session.query(func.count(Task.id)).filter(
            Task.user_id == user_id, Task.completed.is_(True),
            Task.completed_at >= today_start_utc
        ).scalar() or 0
        stats_data['tasks_week'] = session.query(func.count(Task.id)).filter(
            Task.user_id == user_id, Task.completed.is_(True),
            Task.completed_at >= week_start_utc
        ).scalar() or 0
        stats_data['tasks_month'] = session.query(func.count(Task.id)).filter(
            Task.user_id == user_id, Task.completed.is_(True),
            Task.completed_at >= month_start_utc
        ).scalar() or 0

        stats_data['total_pomodoros_today'] = session.query(
            func.count(PomodoroSession.id)).filter(
            PomodoroSession.user_id == user_id,
            PomodoroSession.status == 'completed',
            PomodoroSession.session_type == 'work',
            PomodoroSession.end_time >= today_start_utc
        ).scalar() or 0
        stats_data['total_pomodoros_week'] = session.query(
            func.count(PomodoroSession.id)).filter(
            PomodoroSession.user_id == user_id,
            PomodoroSession.status == 'completed',
            PomodoroSession.session_type == 'work',
            PomodoroSession.end_time >= week_start_utc
        ).scalar() or 0
        stats_data['total_pomodoros_month'] = session.query(
            func.count(PomodoroSession.id)).filter(
            PomodoroSession.user_id == user_id,
            PomodoroSession.status == 'completed',
            PomodoroSession.session_type == 'work',
            PomodoroSession.end_time >= month_start_utc
        ).scalar() or 0

        # Pomodoro по завданнях
        stats_data['completed_pomodoros_per_task'] = session.query(
            Task.description, func.count(PomodoroSession.id)
        ).join(PomodoroSession, PomodoroSession.task_id == Task.id) \
            .filter(PomodoroSession.user_id == user_id,
                    PomodoroSession.status == 'completed',
                    PomodoroSession.session_type == 'work') \
            .group_by(Task.id, Task.description) \
            .order_by(func.count(PomodoroSession.id).desc()).limit(5).all()

        # Перервані Pomodoro
        stopped_sessions_week_q = session.query(
            PomodoroSession.start_time, PomodoroSession.end_time
        ).filter(
            PomodoroSession.user_id == user_id,
            PomodoroSession.status == 'stopped',
            PomodoroSession.session_type == 'work',
            PomodoroSession.end_time >= week_start_utc,
            PomodoroSession.start_time.isnot(None),
            PomodoroSession.end_time.isnot(None)
        ).all()

        stats_data['stopped_pom_count_week'] = len(stopped_sessions_week_q)
        total_actual_stopped_duration_week = timedelta()
        for start, end in stopped_sessions_week_q:
            total_actual_stopped_duration_week += (end - start)
            stats_data['total_stopped_minutes_week'] = int(
                total_actual_stopped_duration_week.total_seconds() // 60
            )

        print(f"LOGIC: Зібрано статистику для user {user_id}")
        return stats_data

    except Exception as e:
        print(f"Помилка в get_statistics_logic для user {user_id}: {e}")
        return {}
    finally:
        session.close()
