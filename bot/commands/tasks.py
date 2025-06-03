from telebot.formatting import escape_markdown
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler, CallbackContext
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton


from bot.logic.menu_navigation import show_tasks_submenu
from bot.models import Task, db
from bot.commands.pomodoro import run_pomodoro_cycle
from bot.commands.reminder import active_tasks
from bot.logic.logic import mark_task_as_done_logic, set_task_reminder_logic, delay_task_reminder_logic, create_task_logic, \
    set_task_priority_logic, get_active_tasks_page_logic

TASKS_PER_PAGE = 5
(GET_TASK_DESCRIPTION,
 ASK_PRIORITY,
 AWAIT_POMODORO_CONFIRM,
 AWAIT_REMINDER_CONFIRM,
 GET_REMINDER_TIME_CONV) = range(5)

PRIORITY_TEXT_MAP = {
    3: "Високий ⬆️",
    2: "Середній ⏺️",
    1: "Низький ⬇️",
}

PRIORITY_ICONS = {
    3: "⬆️",
    2: "⏺️",
    1: "⬇️",
    None: "⚪️"
}

DEFAULT_PRIORITY_ICON = "⚪️"
DEFAULT_PRIORITY_VALUE = 2


async def handle_menu_button_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Викликається при натисканні кнопки '📝 Завдання' з головного меню."""
    await show_tasks_submenu(update, context)


async def received_task_description_conv_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    description_from_user = update.message.text.strip()

    if not description_from_user:
        await update.message.reply_text(
            "Опис завдання не може бути порожнім. Спробуйте ще раз або надішліть /cancel, щоб скасувати.")
        return GET_TASK_DESCRIPTION

    new_task_id, _task_desc_from_logic = create_task_logic(user_id, description_from_user, DEFAULT_PRIORITY_VALUE)

    if not new_task_id:
        await update.message.reply_text(
            "Вибачте, сталася помилка при створенні завдання. Спробуйте пізніше або /cancel.")
        return ConversationHandler.END

    context.user_data['conv_task_id'] = new_task_id
    print(
        f"HANDLER (conv via button): Завдання {new_task_id} додано, очікуємо пріоритет. user_data: {context.user_data}")

    default_prio_text = PRIORITY_TEXT_MAP.get(DEFAULT_PRIORITY_VALUE, "Середній")
    priority_keyboard = [
        [
            InlineKeyboardButton(PRIORITY_TEXT_MAP[3], callback_data="conv_prio:3"),
            InlineKeyboardButton(PRIORITY_TEXT_MAP[2], callback_data="conv_prio:2"),
            InlineKeyboardButton(PRIORITY_TEXT_MAP[1], callback_data="conv_prio:1"),
        ],
        [InlineKeyboardButton(f"🚫 Залишити ({default_prio_text.split(' ')[0]})", callback_data="conv_prio:skip")]
    ]
    reply_markup = InlineKeyboardMarkup(priority_keyboard)
    await update.message.reply_text(
        f"✅ Завдання «{description_from_user}» додано (ID: {new_task_id}).\nОберіть пріоритет:",
        reply_markup=reply_markup
    )
    return ASK_PRIORITY


async def prompt_for_task_description_conv_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запитує опис завдання, коли розмова починається з кнопки меню 'Додати нове завдання'."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Будь ласка, введіть опис для нового завдання:")
    return GET_TASK_DESCRIPTION


async def handle_tasks_submenu_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє кнопки з підменю завдань."""
    query = update.callback_query
    await query.answer()

    action = query.data.split(":")[1]

    if action == "list":
        await list_tasks_command(update, context)

    elif action == "add":
        pass
    else:
        try:
            await query.edit_message_text("Невідома дія для підменю завдань.")
        except Exception as e:
            print(f"Помилка відповіді на невідому дію підменю: {e}")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    user_id = update.effective_user.id
    is_callback = update.callback_query is not None

    tasks_on_page, total_tasks, num_pages = get_active_tasks_page_logic(user_id, page, TASKS_PER_PAGE)

    target_message_obj = update.message if not is_callback else update.callback_query.message

    if not tasks_on_page and page == 0:
        message_text = "У вас немає активних завдань! 🎉"
        if target_message_obj:
            await target_message_obj.reply_text(message_text)
        return
    elif not tasks_on_page and page > 0:
        message_text = "Більше активних завдань немає."
        if is_callback:
            await update.callback_query.answer(message_text)
        return

    header_info_raw = f"Ваші активні завдання (Стор. {page + 1} з {max(1, num_pages)})"
    header_info_escaped = escape_markdown(header_info_raw)

    prio_col_display_width = 3
    id_col_width = 1
    desc_col_width = 25
    rem_col_width = 12

    table_header_str = (
        f"{'П':<{prio_col_display_width}}"
        f"{'ID':<{id_col_width}}  "
        f"{'Завдання':<{desc_col_width}}  "
        f"{'Нагадування':<{rem_col_width}}"
    )
    table_separator_str = (
        f"{'-' * (prio_col_display_width - 1)}-+"
        f"{'-' * (id_col_width)}-+-"
        f"{'-' * desc_col_width}-+-"
        f"{'-' * rem_col_width}"
    )
    task_lines_for_table = [table_header_str, table_separator_str]

    for t in tasks_on_page:
        prio_icon = PRIORITY_ICONS.get(t.priority, DEFAULT_PRIORITY_ICON)
        prio_cell = f"{prio_icon}".ljust(prio_col_display_width)
        id_cell = str(t.id).ljust(id_col_width)

        description_raw = t.description
        description_short = (description_raw[:desc_col_width - 3] + "...") if len(
            description_raw) > desc_col_width else description_raw
        desc_cell = escape_markdown(description_short).ljust(desc_col_width)

        reminder_text_raw = f"⏰{t.remind_at.strftime('%d.%m %H:%M')}" if t.remind_at else ""
        reminder_cell = escape_markdown(reminder_text_raw).ljust(rem_col_width)

        task_lines_for_table.append(
            f"{prio_cell}"
            f"{id_cell}  "
            f"{desc_cell}  "
            f"{reminder_cell}"
        )

    table_content = "\n".join(task_lines_for_table)
    message_text_final = f"{header_info_escaped}\n```\n{table_content}\n```"

    keyboard = []
    for t in tasks_on_page:
        keyboard.append([
            InlineKeyboardButton(f"✅ {t.id}", callback_data=f"task:done:{t.id}"),
            InlineKeyboardButton(f"📊 {t.id}", callback_data=f"task:prio:{t.id}"),
            InlineKeyboardButton(f"⏰ {t.id}", callback_data=f"task:remind:{t.id}")
        ])

    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Попередня", callback_data=f"task:page:{page - 1}"))
    if (page + 1) * TASKS_PER_PAGE < total_tasks:
        pagination_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"task:page:{page + 1}"))

    if pagination_row:
        keyboard.append(pagination_row)

    reply_markup = InlineKeyboardMarkup(
        keyboard) if keyboard else None

    try:
        if is_callback:
            current_telegram_message = update.callback_query.message
            if current_telegram_message.text != message_text_final or current_telegram_message.reply_markup != reply_markup:
                await update.callback_query.edit_message_text(message_text_final, reply_markup=reply_markup,
                                                              parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await update.callback_query.answer()
        else:
            await target_message_obj.reply_text(message_text_final, reply_markup=reply_markup,
                                                parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest as e:
        print(f"Telegram BadRequest в list_tasks: {e}")
        await target_message_obj.reply_text("Помилка форматування списку завдань.")
    except Exception as e:
        print(f"Загальна помилка в list_tasks: {e}")
        await target_message_obj.reply_text("Невідома помилка при відображенні списку завдань.")


async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_tasks(update, context, page=0)


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    task_id_str = None
    try:
        if context.args:
            task_id_str = context.args[0]
        elif update.message and update.message.text and update.message.text.startswith('/done_'):
            raw_id_part = update.message.text.split('_')[1]
            task_id_str = raw_id_part.split('$')[0] if '$' in raw_id_part else raw_id_part

        if not task_id_str:
            await update.message.reply_text("Використовуйте: /done <номер_завдання> або /done_<номер>")
            return

        task_id = int(task_id_str)
        task_obj, message = mark_task_as_done_logic(user_id, task_id)

        await update.message.reply_text(message)

    except (IndexError, ValueError):
        await update.message.reply_text("Невірний номер завдання.")
    except Exception as e:
        await update.message.reply_text(f"Загальна помилка в команді done: {e}")


async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    task_id = None
    remind_time_str = None

    try:
        if update.message.text.startswith('/remind_'):
            parts = update.message.text.split('_', 1)[1].split(' ', 1)
            task_id_from_text = parts[0].replace('$', '')
            if not task_id_from_text.isdigit():
                await update.message.reply_text("Невірний ID завдання у команді /remind_.")
                return
            task_id = int(task_id_from_text)
            if len(parts) > 1:
                remind_time_str = parts[1].strip()
        elif context.args and len(context.args) >= 1:
            if not context.args[0].isdigit():
                await update.message.reply_text("ID завдання має бути числом.")
                return
            task_id = int(context.args[0])
            if len(context.args) > 1:
                remind_time_str = ' '.join(context.args[1:])
        else:
            await update.message.reply_text(
                "Вкажіть ID завдання.\nПриклад: /remind 1 15:30 або /remind 1 <час> або /remind_1 <час>"
            )
            return

        if remind_time_str is None:
            try:
                task_check_obj = db.session.query(Task).filter_by(id=task_id, user_id=user_id).first()
                if not task_check_obj:
                    await update.message.reply_text("Завдання не знайдено або належить іншому користувачу.")
                    return
                await update.message.reply_text(
                    f"Для завдання {task_id} («{task_check_obj.description}») введіть час (HH:MM, dd.mm.YYYY HH:MM) або 'off':"
                )
                context.chat_data['set_reminder_task_id'] = task_id
            except Exception as e_query:
                print(f"Помилка запиту до БД в set_reminder при перевірці завдання: {e_query}")
                await update.message.reply_text("Помилка отримання даних завдання.")
            finally:
                db.session.close()
            return

        _task_obj, message = set_task_reminder_logic(user_id, task_id, remind_time_str)
        await update.message.reply_text(message)

    except ValueError:
        await update.message.reply_text("Невірний ID завдання. Будь ласка, введіть число.")
    except Exception as e:
        await update.message.reply_text(f"❌ Загальна помилка в команді set_reminder: {str(e)}")
        import traceback
        traceback.print_exc()


async def handle_button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        data = query.data.split(":")
        action = data[0]
        task_id = int(data[1])

        from bot.models import db, Task
        task = db.session.query(Task).get(task_id)

        if not task:
            await query.edit_message_text("⚠️ Завдання не знайдено.")
            return

        if action == "done":
            task_obj, message = mark_task_as_done_logic(user_id, task_id)
            await query.edit_message_text(text=message)
        elif action == "delay":
            await query.edit_message_text(
                "⏱ На скільки перенести нагадування?\n\n"
                "⌛ Введіть час у форматі HH:MM або кількість годин:")
            context.chat_data['delay_task_id'] = task_id
            context.chat_data['waiting_for_time'] = True
            print(
                f"DEBUG: handle_button (delay) - ВСТАНОВЛЕНО delay_task_id: {task_id} у chat_data: {context.chat_data}")
            context.chat_data['delay_task_id'] = task_id
    except Exception as e:
        await query.edit_message_text(f"⚠️ Сталася помилка: {str(e)}")


async def handle_task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    current_page = 0
    if query.message and query.message.text and "Стор." in query.message.text:
        try:
            page_str = query.message.text.split("Стор. ")[1].split(" з")[0]
            current_page = int(page_str) - 1
        except Exception as e_page:
            print(f"Не вдалося розпарсити номер сторінки з повідомлення: {e_page}")

    parts = query.data.split(":")
    action = parts[1]
    target_id_str = parts[2] if len(parts) > 2 else None

    if action == "page":
        if target_id_str is None:
            await query.message.reply_text("Помилка: не вказано номер сторінки для пагінації.")
            return
        try:
            page = int(target_id_str)
            await list_tasks(update, context, page=page)
        except ValueError:
            await query.message.reply_text("Помилка: неправильний номер сторінки.")
        except Exception as e:
            print(f"Помилка при пагінації в handle_task_button: {e}")
            await query.message.reply_text("Сталася помилка при спробі перейти на іншу сторінку.")
        return

    if target_id_str is None:
        await query.message.reply_text("Помилка: ID завдання не вказано.")
        return

    try:
        task_id = int(target_id_str)
    except ValueError:
        await query.message.reply_text("Помилка: ID завдання має бути числом.")
        return

    if action == "remind":
        try:
            task_for_remind = Task.query.filter_by(id=task_id, user_id=user_id).first()
            if not task_for_remind:
                await query.edit_message_text("⚠️ Завдання не знайдено.")
            else:
                context.chat_data['remind_task_id_from_button'] = task_id
                print(
                    f"DEBUG handle_task_button (remind): ВСТАНОВЛЕНО remind_task_id_from_button: {task_id}, chat_data: {context.chat_data}")
                await query.message.reply_text(
                    f"Для завдання «{task_for_remind.description}» (ID: {task_for_remind.id}) введіть час нагадування (HH:MM або dd.mm.YYYY HH:MM):"
                )
        except Exception as e:
            print(f"Помилка в 'remind' гілці handle_task_button: {e}")
            await query.message.reply_text("Сталася помилка при налаштуванні нагадування.")
        finally:
            db.session.close()
        return

    elif action == "skip_done_pom":
        try:
            task_skipped = Task.query.filter_by(id=task_id, user_id=user_id).first()
            desc = task_skipped.description if task_skipped else f"ID {task_id}"
            await query.edit_message_text(f"Гаразд, завдання «{desc}» залишається активним.")
        except Exception as e:
            print(f"Помилка в 'skip_done_pom' гілці handle_task_button: {e}")
            await query.message.reply_text("Сталася помилка.")
        finally:
            db.session.close()
        return

    if action == "done" or action == "done_pom_end":
        task_obj, message = mark_task_as_done_logic(user_id, task_id)

        if action == "done":
            if task_obj:
                await query.answer(f"Завдання «{task_obj.description}» оброблено!")
                await list_tasks(update, context, page=current_page)
            else:
                await query.edit_message_text(message)

        elif action == "done_pom_end":
            await query.edit_message_text(message)
        return

    try:
        await query.edit_message_text("Невідома дія.")
    except Exception as e:
        print(f"Помилка при відправці 'Невідома дія' в handle_task_button: {e}")


async def handle_reminder_time_input_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    task_id = context.user_data.pop('conv_task_id', None)
    print(f"--- DEBUG: handle_reminder_time_input_conv - Отримано task_id: {task_id} з user_data ---")

    if not task_id:
        await update.message.reply_text("Помилка: не вдалося визначити завдання для встановлення нагадування (conv). Спробуйте знову.")
        return ConversationHandler.END

    remind_time_str = update.message.text.strip()

    task_obj, message = set_task_reminder_logic(user_id, task_id, remind_time_str)
    await update.message.reply_text(message)

    if task_obj and "Невірний формат часу" in message :
        context.user_data['conv_task_id'] = task_id
        return GET_REMINDER_TIME_CONV

    return ConversationHandler.END


async def handle_reminder_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"--- DEBUG: handle_reminder_time_input ЗАПУЩЕНО, поточний chat_data: {context.chat_data} ---")
    actual_task_id = None

    if 'remind_task_id_from_button' in context.chat_data:
        actual_task_id = context.chat_data.pop('remind_task_id_from_button')
        print(f"--- DEBUG: handle_reminder_time_input - popped 'remind_task_id_from_button': {actual_task_id}")
    elif 'set_reminder_task_id' in context.chat_data:
        actual_task_id = context.chat_data.pop('set_reminder_task_id')
        print(f"--- DEBUG: handle_reminder_time_input - popped 'set_reminder_task_id': {actual_task_id}")

    if not actual_task_id:
        return

    user_id = update.effective_user.id
    remind_time_str = update.message.text.strip()

    task_obj, message = set_task_reminder_logic(user_id, actual_task_id, remind_time_str)
    await update.message.reply_text(message)

    if task_obj and "Невірний формат часу" in message:
        print(f"--- DEBUG: handle_reminder_time_input - Невірний формат для task_id {actual_task_id}. Користувач має спробувати знову.")


async def handle_delay_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("!!!!!!!!!!!! DEBUG: handle_delay_time_input ЗАПУЩЕНО !!!!!!!!!!!!")
    task_id_from_chat = context.chat_data.pop('delay_task_id', None)
    print(f"!!!!!!!!!!!! DEBUG: handle_delay_time_input - delay_task_id from chat_data: {task_id_from_chat}")

    if not task_id_from_chat:
        print("!!!!!!!!!!!! DEBUG: handle_delay_time_input - delay_task_id НЕ ЗНАЙДЕНО, вихід (return)")
        return

    user_input_delay = update.message.text.strip()
    user_id = update.effective_user.id

    task_obj, message = delay_task_reminder_logic(user_id, task_id_from_chat, user_input_delay)
    await update.message.reply_text(message)

    if task_obj and "Невірний формат" not in message:
        if task_id_from_chat in active_tasks:
            active_tasks.remove(task_id_from_chat)
            print(f"DEBUG: handle_delay_time_input - Завдання {task_id_from_chat} видалено з active_tasks")
        context.chat_data.pop('waiting_for_time', None)
    elif "Невірний формат" in message:
        context.chat_data['delay_task_id'] = task_id_from_chat
        print(f"DEBUG: handle_delay_time_input - Невірний формат, повернуто delay_task_id: {task_id_from_chat}")


async def add_task_conversation_starter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Починає розмову для додавання завдання та встановлення пріоритету."""
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text("Будь ласка, введіть опис завдання після /add.\nНаприклад: /add Зробити важливу справу")
        return ConversationHandler.END

    description = ' '.join(args)

    new_task = create_task_logic(user_id, description, DEFAULT_PRIORITY_VALUE)
    if not new_task or not new_task.id:
        await update.message.reply_text("Вибачте, сталася помилка при створенні завдання. Спробуйте пізніше.")
        return ConversationHandler.END

    context.user_data['conv_task_id'] = new_task.id
    print(f"HANDLER: Завдання {new_task.id} додано (з логіки), очікуємо пріоритет. user_data: {context.user_data}")

    priority_keyboard = [
        [
            InlineKeyboardButton(PRIORITY_TEXT_MAP[3], callback_data="conv_prio:3"),
            InlineKeyboardButton(PRIORITY_TEXT_MAP[2], callback_data="conv_prio:2"),
            InlineKeyboardButton(PRIORITY_TEXT_MAP[1], callback_data="conv_prio:1"),
        ],
        [InlineKeyboardButton(f"🚫 Залишити {PRIORITY_TEXT_MAP.get(DEFAULT_PRIORITY_VALUE, 'Середній')}", callback_data="conv_prio:skip")]
    ]
    reply_markup = InlineKeyboardMarkup(priority_keyboard)
    await update.message.reply_text(
        f"✅ Завдання «{description}» додано (ID: {new_task.id}).\nОберіть пріоритет:",
        reply_markup=reply_markup
    )
    return ASK_PRIORITY


async def handle_priority_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    task_id = context.user_data.get('conv_task_id')
    if not task_id:
        await query.edit_message_text("Помилка: ID завдання не знайдено в сесії. Спробуйте додати завдання знову.")
        return ConversationHandler.END

    chosen_priority_data = query.data.split(":")[1]
    next_state = ConversationHandler.END

    task_description_for_reply = "невідоме завдання"
    task_current_priority_for_suggestion = DEFAULT_PRIORITY_VALUE

    if chosen_priority_data == "skip":
        try:
            task_obj_skipped = db.session.query(Task).filter_by(id=task_id, user_id=user_id).first()
            if task_obj_skipped:
                task_description_for_reply = task_obj_skipped.description
                task_current_priority_for_suggestion = task_obj_skipped.priority
            priority_display_text = PRIORITY_TEXT_MAP.get(task_current_priority_for_suggestion, "Не встановлено")
            await query.edit_message_text(
                f"Пріоритет для завдання «{task_description_for_reply}» не змінено (залишився '{priority_display_text}').")
        except Exception as e_skip:
            print(f"Помилка при отриманні завдання для skip в handle_priority_selection: {e_skip}")
            await query.edit_message_text("Помилка отримання даних завдання.")
            context.user_data.pop('conv_task_id', None)
            return ConversationHandler.END
        finally:
            db.session.close()
    else:
        priority_value = int(chosen_priority_data)
        _updated_task_obj, returned_description, returned_priority = set_task_priority_logic(user_id, task_id,
                                                                                             priority_value)

        if not _updated_task_obj:
            error_message_from_logic = returned_description or "Не вдалося оновити пріоритет завдання."
            await query.edit_message_text(f"Помилка: {error_message_from_logic}")
            context.user_data.pop('conv_task_id', None)
            return ConversationHandler.END

        task_description_for_reply = returned_description
        task_current_priority_for_suggestion = returned_priority
        priority_display_text = PRIORITY_TEXT_MAP.get(task_current_priority_for_suggestion, "Невідомий")

        await query.edit_message_text(
            f"Пріоритет для завдання «{task_description_for_reply}» встановлено: {priority_display_text}.")

    if task_current_priority_for_suggestion == 3:
        pom_keyboard = [[
            InlineKeyboardButton("🚀 Так, почати Pomodoro", callback_data=f"conv_sugg:pom_yes:{task_id}"),
            InlineKeyboardButton("➖ Ні, дякую", callback_data=f"conv_sugg:pom_no:{task_id}")
        ]]
        await query.message.reply_text(
            f"Завдання «{task_description_for_reply}» високого пріоритету. Розпочати Pomodoro зараз?",
            reply_markup=InlineKeyboardMarkup(pom_keyboard)
        )
        next_state = AWAIT_POMODORO_CONFIRM
    elif task_current_priority_for_suggestion in [1, 2]:
        rem_keyboard = [[
            InlineKeyboardButton("⏰ Так, встановити нагадування", callback_data=f"conv_sugg:rem_yes:{task_id}"),
            InlineKeyboardButton("➖ Ні, дякую", callback_data=f"conv_sugg:rem_no:{task_id}")
        ]]
        await query.message.reply_text(
            f"Для завдання «{task_description_for_reply}» бажаєте встановити нагадування?",
            reply_markup=InlineKeyboardMarkup(rem_keyboard)
        )
        next_state = AWAIT_REMINDER_CONFIRM
    else:
        next_state = ConversationHandler.END

    if next_state == ConversationHandler.END:
        context.user_data.pop('conv_task_id', None)

    return next_state


async def handle_pomodoro_confirm(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    task_id = context.user_data.pop('conv_task_id', None)

    action_data = query.data.split(":")[1]

    if not task_id:
        await query.edit_message_text("Помилка: не вдалося визначити завдання для Pomodoro.")
        return ConversationHandler.END

    if action_data == "pom_yes":
        pom_data = context.user_data.setdefault('pomodoro', {})
        if pom_data.get('state', 'idle') != 'idle' and pom_data.get('state') is not None:
            await query.message.reply_text("Pomodoro вже запущено. Зупиніть поточний, щоб почати новий.")
        else:
            pom_data.clear()
            pom_data['state'] = 'idle'
            pom_data['pomodoros_done'] = 0
            pom_data['linked_task_id'] = task_id
            pom_data['current_session_id'] = None

            task_obj = Task.query.get(task_id)
            task_desc = task_obj.description if task_obj else f"ID {task_id}"
            db.session.close()

            context.job_queue.run_once(
                run_pomodoro_cycle,
                0,
                chat_id=chat_id,
                user_id=user_id,
                name=f"pomodoro_timer_{chat_id}",
                data={'chat_id': chat_id}
            )
            await query.edit_message_text(f"🚀 Pomodoro для завдання «{task_desc}» запущено!")
    else:
        await query.edit_message_text("Гаразд, Pomodoro не запущено.")

    return ConversationHandler.END


async def handle_reminder_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    task_id = context.user_data.get('conv_task_id')

    if not task_id:
        await query.edit_message_text("Помилка: не вдалося визначити завдання для нагадування.")
        return ConversationHandler.END

    action_data = query.data.split(":")[1]
    if action_data == "rem_yes":
        task = Task.query.get(task_id)
        task_desc = task.description if task else f"ID {task.id}"
        db.session.close()
        await query.edit_message_text(
            f"Для завдання «{task_desc}» введіть час нагадування (HH:MM або dd.mm.YYYY HH:MM):")
        return GET_REMINDER_TIME_CONV
    else:
        await query.edit_message_text("Гаразд, нагадування не встановлено.")
        context.user_data.pop('conv_task_id', None)
        return ConversationHandler.END
