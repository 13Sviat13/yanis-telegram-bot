from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot.logic.logic import update_pomodoro_session_db, create_pomodoro_session_db
from bot.logic.menu_navigation import show_pomodoro_submenu

from bot.models import db, Task

# --- Константи ---
WORK_DURATION_MIN = 25
SHORT_BREAK_DURATION_MIN = 5
LONG_BREAK_DURATION_MIN = 15
POMODOROS_BEFORE_LONG_BREAK = 4
UPDATE_INTERVAL_SEC = 5


async def clear_jobs(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Видаляє всі активні Pomodoro jobs для чату."""
    timer_jobs = context.job_queue.get_jobs_by_name(f"pomodoro_timer_{chat_id}")
    update_jobs = context.job_queue.get_jobs_by_name(f"pomodoro_update_{chat_id}")
    for j in timer_jobs + update_jobs:
        j.schedule_removal()
    print(f"Jobs cleared for {chat_id}")


def generate_progress_bar(current_seconds, total_seconds, length=10):
    """Генерує текстовий прогрес-бар."""
    if total_seconds == 0:
        return f"[{'░' * length}]"
    percentage = current_seconds / total_seconds
    filled_length = int(length * percentage)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"


def get_pomodoro_keyboard(state, paused=False):
    """Повертає клавіатуру відповідно до стану таймера."""
    buttons = []
    if state == 'idle':
        buttons.append([InlineKeyboardButton("🚀 Розпочати (25 хв)", callback_data="pom:start_work")])
    elif state in ['work', 'short_break', 'long_break']:
        row = []
        if paused:
            row.append(InlineKeyboardButton("▶️ Відновити", callback_data="pom:resume"))
        else:
            row.append(InlineKeyboardButton("⏸️ Пауза", callback_data="pom:pause"))
        row.append(InlineKeyboardButton("⏹️ Зупинити", callback_data="pom:stop"))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


async def update_timer_message(context: ContextTypes.DEFAULT_TYPE):
    """Оновлює повідомлення таймера з прогресом."""
    job_data = context.job.data
    chat_id = job_data['chat_id']
    user_data = context.user_data.get('pomodoro', {})

    start_time = user_data.get('start_time')
    duration = user_data.get('duration')
    state = user_data.get('state')
    message_id = user_data.get('message_id')
    paused = user_data.get('paused', False)

    if not all([start_time, duration, state, message_id]) or paused:
        return

    now = datetime.utcnow()
    elapsed = now - start_time
    remaining = duration - elapsed

    if remaining <= timedelta(seconds=0):
        return

    progress_text = ""
    if state == 'work':
        progress_text = f"💪 Працюємо ({user_data.get('pomodoros_done', 0) + 1}/4)"
    elif state == 'short_break':
        progress_text = "☕️ Коротка перерва"
    elif state == 'long_break':
        progress_text = "🧘 Довга перерва"

    bar = generate_progress_bar(elapsed.total_seconds(), duration.total_seconds())
    time_left_str = str(remaining).split('.')[0][2:]

    text = f"{progress_text}\n{bar} {time_left_str}"

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=get_pomodoro_keyboard(state, paused)
        )
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            print(f"Error updating message {message_id} for {chat_id}: {e}")
    except Exception as e:
        print(f"Unexpected error updating message {message_id} for {chat_id}: {e}")


async def run_pomodoro_cycle(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data['chat_id']
    user_id = chat_id
    pom_data = context.user_data.setdefault('pomodoro', {})
    current_state = pom_data.get('state', 'idle')
    pomodoros_done = pom_data.get('pomodoros_done', 0)
    message_id = pom_data.get('message_id')
    current_pomodoro_session_id = pom_data.get('current_session_id')
    linked_task_id = pom_data.get('linked_task_id')

    await clear_jobs(context, chat_id)

    next_state = ''
    duration_min = 0
    notification = ""

    if current_state == 'work':
        update_pomodoro_session_db(current_pomodoro_session_id, 'completed')
        pom_data['current_session_id'] = None
        pomodoros_done += 1
        pom_data['pomodoros_done'] = pomodoros_done
        print(f"Pomodoro: Робоча сесія завершена. pomodoros_done тепер: {pomodoros_done}")
        if pomodoros_done % POMODOROS_BEFORE_LONG_BREAK == 0:
            next_state = 'long_break'
            duration_min = LONG_BREAK_DURATION_MIN
            notification = "🎉 Чудова робота! Час для довгої перерви."
        else:
            next_state = 'short_break'
            duration_min = SHORT_BREAK_DURATION_MIN
            notification = "👍 Інтервал завершено! Коротка перерва."

    elif current_state == 'short_break':
        next_state = 'work'
        duration_min = WORK_DURATION_MIN
        notification = "🏁 Час працювати!"

    elif current_state == 'long_break':
        await context.bot.send_message(chat_id=chat_id,
                                       text="🧘 Довга перерва завершена. Повна послідовність Pomodoro закінчена! Гарна робота! 👍")
        if linked_task_id:
            try:
                task_for_prompt = db.session.query(Task).filter_by(id=linked_task_id, user_id=user_id).first()
                if task_for_prompt and not task_for_prompt.completed:
                    keyboard_prompt = [[
                        InlineKeyboardButton("✅ Так, позначити виконаним",
                                             callback_data=f"task:done_pom_end:{linked_task_id}"),
                        InlineKeyboardButton("❌ Ні, залишити активним",
                                             callback_data=f"task:skip_done_pom:{linked_task_id}")
                    ]]
                    reply_markup_prompt = InlineKeyboardMarkup(keyboard_prompt)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"Ви працювали над завданням: «{task_for_prompt.description}».\nБажаєте позначити його як виконане?",
                        reply_markup=reply_markup_prompt
                    )
            except Exception as e:
                print(f"Помилка при спробі запропонувати виконати завдання: {e}")
            finally:
                db.session.close()
        if message_id:
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                    text="🍅 Послідовність Pomodoro завершено!", reply_markup=None)
            except Exception as e:
                print(f"Не вдалося відредагувати фінальне повідомлення Pomodoro: {e}")
        pom_data.clear()
        pom_data['state'] = 'idle'
        print(f"Pomodoro: Повна послідовність для user {user_id} завершена. Стан скинуто.")
        return

    elif current_state == 'idle':
        next_state = 'work'
        duration_min = WORK_DURATION_MIN
        notification = "🏁 Час працювати!"
        pom_data['pomodoros_done'] = 0

    else:
        await context.bot.send_message(chat_id=chat_id,
                                       text="❌ Виникла невідома помилка стану таймера, таймер зупинено.")
        if current_pomodoro_session_id:
            update_pomodoro_session_db(current_pomodoro_session_id, 'stopped')
        pom_data.clear()
        pom_data['state'] = 'idle'
        return

    duration = timedelta(minutes=duration_min)

    if next_state == 'work':
        pom_data['current_session_id'] = create_pomodoro_session_db(
            user_id,
            duration_min,
            'work',
            task_id=linked_task_id
        )

    pom_data['state'] = next_state
    pom_data['start_time'] = datetime.now(timezone.utc).replace(tzinfo=None)
    pom_data['duration'] = duration
    pom_data['paused'] = False
    pom_data['paused_time'] = None
    pom_data['remaining_on_pause'] = None

    await context.bot.send_message(chat_id=chat_id, text=notification)
    progress_text = ""
    current_pomodoros_display = pom_data.get('pomodoros_done', 0)
    if next_state == 'work':
        progress_text = f"💪 Працюємо ({current_pomodoros_display + 1}/{POMODOROS_BEFORE_LONG_BREAK})"
        if linked_task_id:
            try:
                task_desc_q = db.session.query(Task.description).filter_by(id=linked_task_id, user_id=user_id).scalar()
                if task_desc_q:
                    progress_text += f" (завдання: «{task_desc_q}»)"
            except Exception as e_td:
                print(f"Не вдалося отримати опис завдання {linked_task_id} для таймера: {e_td}")
            finally:
                db.session.close()
    elif next_state == 'short_break':
        progress_text = "☕️ Коротка перерва"
    elif next_state == 'long_break':
        progress_text = "🧘 Довга перерва"

    bar = generate_progress_bar(0, duration.total_seconds())
    time_left_str = str(duration).split('.')[0][2:]
    text_msg_pom = f"{progress_text}\n{bar} {time_left_str}"

    message_id_to_edit = pom_data.get('message_id')
    try:
        if message_id_to_edit:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=text_msg_pom,
                                                reply_markup=get_pomodoro_keyboard(next_state))
        else:
            message_obj = await context.bot.send_message(chat_id=chat_id, text=text_msg_pom,
                                                         reply_markup=get_pomodoro_keyboard(next_state))
            pom_data['message_id'] = message_obj.message_id
    except Exception as e:
        print(f"Error sending/editing message in run_pomodoro_cycle: {e}")
        message_obj = await context.bot.send_message(chat_id=chat_id, text=text_msg_pom,
                                                     reply_markup=get_pomodoro_keyboard(next_state))
        pom_data['message_id'] = message_obj.message_id

    job_payload = {'chat_id': chat_id}
    context.job_queue.run_once(run_pomodoro_cycle, duration.total_seconds(), chat_id=chat_id, user_id=user_id,
                               name=f"pomodoro_timer_{chat_id}", data=job_payload)
    context.job_queue.run_repeating(update_timer_message, interval=UPDATE_INTERVAL_SEC, first=0, chat_id=chat_id,
                                    user_id=user_id, name=f"pomodoro_update_{chat_id}", data=job_payload)
    print(
        f"Scheduled jobs for {chat_id} (user {user_id}): timer in {duration.total_seconds()}s, update every {UPDATE_INTERVAL_SEC}s. "
        f"Current pomodoros_done: {pom_data.get('pomodoros_done', 0)}")


async def _initiate_pomodoro_sequence(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int,
                                      linked_task_id: int | None = None, linked_task_description: str | None = None,
                                      source_message_id: int | None = None, is_callback: bool = False):
    """Готує та запускає послідовність Pomodoro."""
    pom_data = context.user_data.setdefault('pomodoro', {})

    if pom_data.get('state', 'idle') != 'idle' and pom_data.get('state') is not None:
        message_text = f"⏳ Таймер Pomodoro вже запущено (стан: {pom_data.get('state')}). Зупиніть його спочатку."
        if is_callback:
            await update.callback_query.answer(message_text.split('.')[0], show_alert=True)
        else:
            await update.message.reply_text(message_text)
        return

    pom_data.clear()
    pom_data['state'] = 'idle'
    pom_data['pomodoros_done'] = 0
    pom_data['current_session_id'] = None
    if linked_task_id:
        pom_data['linked_task_id'] = linked_task_id

    start_message_text = "🍅 Pomodoro запускається..."
    if linked_task_description:
        start_message_text += f"\n📝 Для завдання: «{linked_task_description}»"

    if is_callback and source_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=source_message_id,
                text=start_message_text,
                reply_markup=get_pomodoro_keyboard('idle')
            )
            pom_data['message_id'] = source_message_id
        except Exception as e:
            print(f"Помилка редагування повідомлення для старту Pomodoro: {e}")
            message_obj = await context.bot.send_message(chat_id=chat_id, text=start_message_text,
                                                         reply_markup=get_pomodoro_keyboard('idle'))
            pom_data['message_id'] = message_obj.message_id
    elif update.message:
        message_obj = await update.message.reply_text(start_message_text, reply_markup=get_pomodoro_keyboard('idle'))
        pom_data['message_id'] = message_obj.message_id
    else:
        print("Не вдалося надіслати стартове повідомлення Pomodoro")
        return


def get_tasks_for_linking_pomodoro(user_id: int, page: int = 0, page_size: int = 5) -> tuple[list[Task], int, int]:
    """Отримує сторінку активних завдань для прив'язки до Pomodoro."""
    session = db.session
    try:
        offset = page * page_size
        tasks_query = session.query(Task).filter_by(user_id=user_id, completed=False) \
            .order_by(Task.priority.desc(), Task.id.asc())
        tasks_on_page = tasks_query.offset(offset).limit(page_size).all()
        total_tasks = session.query(Task).filter_by(user_id=user_id,
                                                    completed=False).count()
        num_pages = (total_tasks + page_size - 1) // page_size
        if num_pages == 0 and total_tasks > 0:
            num_pages = 1
        return tasks_on_page, total_tasks, num_pages
    except Exception as e:
        print(f"Помилка отримання завдань для Pomodoro: {e}")
        session.rollback()
        return [], 0, 0
    finally:
        session.close()


async def display_tasks_for_pomodoro_linking(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Відображає список завдань з кнопками для запуску Pomodoro."""
    query = update.callback_query
    user_id = query.from_user.id

    tasks_on_page, total_tasks, num_pages = get_tasks_for_linking_pomodoro(user_id, page)

    if not tasks_on_page and page == 0:
        await query.edit_message_text("У вас немає активних завдань для прив'язки Pomodoro.")
        return
    elif not tasks_on_page and page > 0:
        await query.answer("Більше завдань немає.")
        return

    message_text = f"Оберіть завдання для Pomodoro (Стор. {page + 1} з {max(1, num_pages)}):"
    keyboard = []
    for task in tasks_on_page:
        desc_short = task.description[:30] + "..." if len(task.description) > 30 else task.description
        keyboard.append([
            InlineKeyboardButton(f"🍅 {task.id}. {desc_short}",
                                 callback_data=f"pomodoro_submenu:start_with_task:{task.id}")
        ])

    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pomodoro_submenu:link_page:{page - 1}"))
    if (page + 1) * 5 < total_tasks:
        pagination_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"pomodoro_submenu:link_page:{page + 1}"))

    if pagination_row:
        keyboard.append(pagination_row)

    keyboard.append([InlineKeyboardButton("↩️ Назад до опцій Pomodoro", callback_data="pomodoro_submenu:show_options")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message_text, reply_markup=reply_markup)


async def handle_pomodoro_submenu_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    action_parts = query.data.split(":")
    action = action_parts[1]

    if action == "start_any":
        await _initiate_pomodoro_sequence(update, context, chat_id, user_id, source_message_id=query.message.message_id,
                                          is_callback=True)

    elif action == "start_linked_select_task":
        await display_tasks_for_pomodoro_linking(update, context, page=0)

    elif action == "link_page":
        page_num = int(action_parts[2])
        await display_tasks_for_pomodoro_linking(update, context, page=page_num)

    elif action == "start_with_task":
        task_id_to_link = int(action_parts[2])
        task_description = "невідоме завдання"
        try:
            task_obj = db.session.query(Task).filter_by(id=task_id_to_link, user_id=user_id).first()
            if task_obj:
                task_description = task_obj.description
        except Exception as e:
            print(f"Помилка отримання опису завдання {task_id_to_link} для Pomodoro: {e}")
        finally:
            db.session.close()

        await _initiate_pomodoro_sequence(update, context, chat_id, user_id,
                                          linked_task_id=task_id_to_link,
                                          linked_task_description=task_description,
                                          source_message_id=query.message.message_id,
                                          is_callback=True)
    elif action == "show_options":
        from bot.logic.menu_navigation import show_pomodoro_submenu as show_pom_submenu_nav
        await query.edit_message_text(
            text="Налаштування Pomodoro:",
            reply_markup=show_pom_submenu_nav(None, None).reply_markup
        )

        pom_keyboard_layout = [
            [InlineKeyboardButton("🚀 Запустити Pomodoro (без прив'язки)", callback_data="pomodoro_submenu:start_any")],
            [InlineKeyboardButton("🔗 Запустити для завдання...",
                                  callback_data="pomodoro_submenu:start_linked_select_task")]
        ]
        reply_markup_pom = InlineKeyboardMarkup(pom_keyboard_layout)
        await query.edit_message_text("Налаштування Pomodoro:", reply_markup=reply_markup_pom)
    else:
        await query.edit_message_text("Невідома дія для Pomodoro меню.")


async def start_pomodoro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    linked_task_id_arg = None
    linked_task_description_arg = None

    if context.args:
        try:
            task_id_arg = int(context.args[0])
            task_to_link = db.session.query(Task).filter_by(id=task_id_arg, user_id=user_id, completed=False).first()
            if task_to_link:
                linked_task_id_arg = task_to_link.id
                linked_task_description_arg = task_to_link.description
            else:
                await update.message.reply_text(
                    f"⚠️ Завдання з ID {task_id_arg} не знайдено/виконане. Pomodoro без прив'язки.")
        except (ValueError, IndexError):
            await update.message.reply_text("⚠️ Невірний ID завдання. Pomodoro без прив'язки.")
        finally:
            db.session.close()

    await _initiate_pomodoro_sequence(update, context, chat_id, user_id, linked_task_id_arg,
                                      linked_task_description_arg)


async def handle_pomodoro_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = chat_id
    pom_data = context.user_data.get('pomodoro')
    if not pom_data or not pom_data.get('message_id'):
        await query.edit_message_text("❌ Помилка: Не знайдено даних таймера. Спробуйте /pomodoro знову.")
        return

    action = query.data.split(":")[1]
    state = pom_data.get('state')
    job_payload = {'chat_id': chat_id}

    if action == "start_work":
        if state == 'idle':
            pom_data['state'] = 'idle'
            context.job_queue.run_once(run_pomodoro_cycle, 0, chat_id=chat_id, user_id=user_id,
                                       name=f"pomodoro_timer_{chat_id}", data=job_payload)
        else:
            await query.answer("Таймер вже працює!")

    elif action == "pause":
        if not pom_data.get('paused', False) and state != 'idle':
            await clear_jobs(context, chat_id)
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            start_time_utc = pom_data['start_time']
            duration = pom_data['duration']
            elapsed = now_utc - start_time_utc
            remaining = duration - elapsed
            pom_data['paused'] = True
            pom_data['paused_time'] = now_utc
            pom_data['remaining_on_pause'] = remaining if remaining > timedelta(0) else timedelta(0)
            await query.edit_message_text(
                text=f"⏸️ Пауза. {str(pom_data['remaining_on_pause']).split('.')[0][2:]} залишилось.",
                reply_markup=get_pomodoro_keyboard(state, paused=True))
    elif action == "resume":
        if pom_data.get('paused', False):
            remaining = pom_data.get('remaining_on_pause')
            if remaining and remaining > timedelta(0):
                pom_data['paused'] = False
                pom_data['start_time'] = datetime.now(timezone.utc).replace(tzinfo=None)
                pom_data['duration'] = remaining
                context.job_queue.run_once(run_pomodoro_cycle, remaining.total_seconds(), chat_id=chat_id,
                                           user_id=user_id, name=f"pomodoro_timer_{chat_id}", data=job_payload)
                context.job_queue.run_repeating(update_timer_message, interval=UPDATE_INTERVAL_SEC, first=0,
                                                chat_id=chat_id, user_id=user_id, name=f"pomodoro_update_{chat_id}",
                                                data=job_payload)
                await query.edit_message_text(
                    text="▶️ Відновлено...",
                    reply_markup=get_pomodoro_keyboard(
                        state,
                        paused=False
                    ))
            else:
                context.job_queue.run_once(run_pomodoro_cycle, 0, chat_id=chat_id, user_id=user_id,
                                           name=f"pomodoro_timer_{chat_id}", data=job_payload)
    elif action == "stop":
        if state == 'work':
            update_pomodoro_session_db(pom_data.get('current_session_id'), 'stopped')

        await clear_jobs(context, chat_id)
        pom_data.clear()
        pom_data['state'] = 'idle'
        await query.edit_message_text("⏹️ Таймер Pomodoro зупинено.")


async def handle_menu_button_pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопки '🍅 Pomodoro' з головного меню."""
    await show_pomodoro_submenu(update, context)

    def get_tasks_for_linking_pomodoro(user_id: int, page: int = 0, page_size: int = 5) -> tuple[list[Task], int, int]:
        """Отримує сторінку активних завдань для прив'язки до Pomodoro."""
        session = db.session
        try:
            offset = page * page_size
            tasks_query = session.query(Task).filter_by(user_id=user_id, completed=False) \
                .order_by(Task.priority.desc(), Task.id.asc())
            tasks_on_page = tasks_query.offset(offset).limit(page_size).all()
            total_tasks = session.query(Task).filter_by(user_id=user_id,
                                                        completed=False).count()
            num_pages = (total_tasks + page_size - 1) // page_size
            if num_pages == 0 and total_tasks > 0:
                num_pages = 1
            return tasks_on_page, total_tasks, num_pages
        except Exception as e:
            print(f"Помилка отримання завдань для Pomodoro: {e}")
            session.rollback()
            return [], 0, 0
        finally:
            session.close()

    async def display_tasks_for_pomodoro_linking(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
        """Відображає список завдань з кнопками для запуску Pomodoro."""
        query = update.callback_query
        user_id = query.from_user.id

        tasks_on_page, total_tasks, num_pages = get_tasks_for_linking_pomodoro(user_id, page)

        if not tasks_on_page and page == 0:
            await query.edit_message_text("У вас немає активних завдань для прив'язки Pomodoro.")
            return
        elif not tasks_on_page and page > 0:
            await query.answer("Більше завдань немає.")
            return

        message_text = f"Оберіть завдання для Pomodoro (Стор. {page + 1} з {max(1, num_pages)}):"
        keyboard = []
        for task in tasks_on_page:
            desc_short = task.description[:30] + "..." if len(task.description) > 30 else task.description
            keyboard.append([
                InlineKeyboardButton(f"🍅 {task.id}. {desc_short}",
                                     callback_data=f"pomodoro_submenu:start_with_task:{task.id}")
            ])

        pagination_row = []
        if page > 0:
            pagination_row.append(
                InlineKeyboardButton("⬅️ Назад", callback_data=f"pomodoro_submenu:link_page:{page - 1}"))
        if (page + 1) * 5 < total_tasks:  # Припускаємо page_size = 5
            pagination_row.append(
                InlineKeyboardButton("Вперед ➡️", callback_data=f"pomodoro_submenu:link_page:{page + 1}"))

        if pagination_row:
            keyboard.append(pagination_row)

        keyboard.append(
            [InlineKeyboardButton("↩️ Назад до опцій Pomodoro", callback_data="pomodoro_submenu:show_options")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message_text, reply_markup=reply_markup)
