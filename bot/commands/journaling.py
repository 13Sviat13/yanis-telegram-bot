from telebot.formatting import escape_markdown
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from bot.logic.logic import save_generic_entry_logic, ENTRY_TYPE_CONFIG_LOGIC, get_paginated_entries_logic

from bot.commands.content import get_mood_advice_rules
from bot.logic.menu_navigation import show_journal_submenu, show_mood_submenu, send_main_menu
from bot.models import JournalEntry, MoodEntry


ENTRIES_PER_PAGE_CONFIG = {
    "journal": 5,
    "mood": 5
}

ENTRY_TYPE_DISPLAY_CONFIG = {
    "journal": {
        "idea": "Ідея",
        "thought": "Думка",
        "dream": "Сон",
        "note": "Замітка",
        "_default": "Запис"
    },
    "mood": {
        "_default": "Запис Настрою"
    }
}

JOURNAL_ENTRY_TYPE_DISPLAY_MAP = {
    "idea": "Ідея",
    "thought": "Думка",
    "dream": "Сон",
    "note": "Замітка",
    "_default": "Запис"
}

HEADER_TEXT_CONFIG = {
    "journal": "✒️ Ваш Журнал",
    "mood": "😊 Ваш Журнал Настрою"
}

NO_ENTRIES_MESSAGE_CONFIG = {
    "journal": "У вас ще немає жодного запису в журналі. Спробуйте /idea, /thought або /dream!",
    "mood": "У вас ще немає жодного запису про настрій. Спробуйте /mood!"
}

GET_JOURNAL_ENTRY_TEXT_FROM_MENU = range(20, 21)
GET_MOOD_ENTRY_FROM_MENU = range(21, 22)


async def save_generic_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text

    command_parts = message_text.split(' ', 1)
    command = command_parts[0].lstrip('/')

    config = ENTRY_TYPE_CONFIG_LOGIC.get(command)
    if not config:
        await update.message.reply_text("Невідомий тип запису.")
        return

    display_entry_type = config["display_name"]

    if len(command_parts) < 2 or not command_parts[1].strip():
        prompt_example = "Ваш запис..."
        if command == "idea":
            prompt_example = "Моя нова ідея."
        elif command == "thought":
            prompt_example = "Цікава думка на сьогодні."
        elif command == "dream":
            prompt_example = "Мені наснилося, що..."
        elif command == "mood":
            prompt_example = "5 Чудовий настрій #позитив"
        await update.message.reply_text(
            f"Будь ласка, введіть текст для '{display_entry_type}' після команди.\nНаприклад: /{command} {prompt_example}")
        return

    full_content_input = command_parts[1].strip()

    created_entry, confirmation_message, _parsed_tags, text_for_analysis = save_generic_entry_logic(
        user_id, command, full_content_input
    )

    await update.message.reply_text(confirmation_message)

    if created_entry and command == "mood" and text_for_analysis:
        normalized_text = text_for_analysis.lower()
        advice_to_send = None
        mood_advice_rules = get_mood_advice_rules()

        for rule in mood_advice_rules:
            if not isinstance(rule, dict) or "keywords" not in rule or "advice" not in rule:
                print(f"ПОПЕРЕДЖЕННЯ: Пропускаю неправильно сформоване правило в mood_advice_rules: {rule}")
                continue

            current_keywords = rule["keywords"]
            if isinstance(current_keywords, str):
                current_keywords = [current_keywords]
            if not isinstance(current_keywords, list):
                print(f"ПОПЕРЕДЖЕННЯ: 'keywords' в правилі не є списком: {rule}")
                continue

            for keyword in current_keywords:
                if keyword.lower() in normalized_text:
                    advice_to_send = rule["advice"]
                    break
            if advice_to_send:
                break

        if advice_to_send:
            await update.message.reply_text(advice_to_send)


async def show_paginated_entries(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        page: int = 0,
        entry_config_key: str = "journal",
        tag_filter: str | None = None,
        entry_type_filter: str | None = None
):
    user_id = update.effective_user.id
    is_callback = update.callback_query is not None

    model_to_query_class = None
    if entry_config_key == "journal":
        model_to_query_class = JournalEntry
    elif entry_config_key == "mood":
        model_to_query_class = MoodEntry
    else:
        error_target = update.message if not is_callback \
            else update.callback_query.message
        if error_target:
            await error_target.reply_text("Невідомий тип журналу.")
        return

    page_size = ENTRIES_PER_PAGE_CONFIG.get(entry_config_key, 5)

    entries_on_page, total_entries, num_pages = get_paginated_entries_logic(
        user_id, page, page_size, model_to_query_class, tag_filter, entry_type_filter
    )

    no_entries_base_message = NO_ENTRIES_MESSAGE_CONFIG.get(entry_config_key, "Записів немає.")
    target_message_obj = update.message if not is_callback else update.callback_query.message

    if not entries_on_page and page == 0:
        current_filter_message_part = ""
        if tag_filter:
            current_filter_message_part += f" з тегом #{tag_filter}"
        if entry_config_key == "journal" and entry_type_filter:
            display_type = ENTRY_TYPE_DISPLAY_CONFIG.get("journal", {}).get(entry_type_filter, entry_type_filter)
            current_filter_message_part += f" типу '{escape_markdown(display_type)}'"

        no_entries_message = f"Не знайдено записів{current_filter_message_part}." if current_filter_message_part else no_entries_base_message
        if page == 0 and not entries_on_page :
            no_entries_message += f"\n({no_entries_base_message})" if current_filter_message_part else ""

        if target_message_obj:
            await target_message_obj.reply_text(no_entries_message)
        return

    elif not entries_on_page and page > 0:
        current_filter_message_part = ""
        if tag_filter:
            current_filter_message_part += f" з тегом #{tag_filter}"
        if entry_config_key == "journal" and entry_type_filter:
            display_type = ENTRY_TYPE_DISPLAY_CONFIG.get("journal", {}).get(entry_type_filter, entry_type_filter)
            current_filter_message_part += f" типу '{escape_markdown(display_type)}'"
        if is_callback:
            await update.callback_query.answer(f"Більше записів{current_filter_message_part} немає.")
        return

    header_title_base = HEADER_TEXT_CONFIG.get(entry_config_key, "Ваші Записи")
    filter_display_header = ""
    if tag_filter:
        filter_display_header += f" (Тег: \\#{escape_markdown(tag_filter)})"
    if entry_config_key == "journal" and entry_type_filter:
        display_type_header = ENTRY_TYPE_DISPLAY_CONFIG.get("journal", {}).get(entry_type_filter, entry_type_filter)
        filter_display_header += f" (Тип: {escape_markdown(display_type_header)})"
    header_info_raw = f"{header_title_base}{filter_display_header} (Стор. {page + 1} з {max(1, num_pages)})"
    header_info_escaped = escape_markdown(header_info_raw)
    message_parts = [header_info_escaped + "\n"]

    for entry in entries_on_page:
        date_str_raw = entry.created_at.strftime('%d.%m.%Y %H:%M') if entry.created_at else "невідомо"
        date_str_escaped = escape_markdown(date_str_raw)
        entry_specific_parts_md = []
        if entry_config_key == "journal":
            entry_type_map = ENTRY_TYPE_DISPLAY_CONFIG.get("journal", {})
            default_type_display = entry_type_map.get("_default", "Запис")
            entry_type_raw = entry_type_map.get(entry.entry_type, entry.entry_type.capitalize() if entry.entry_type else default_type_display)
            entry_type_escaped = escape_markdown(entry_type_raw)
            entry_specific_parts_md.append(f"*{entry_type_escaped}*")
            if hasattr(entry, 'content') and entry.content:
                entry_specific_parts_md.append(escape_markdown(entry.content))
        elif entry_config_key == "mood":
            if hasattr(entry, 'rating') and entry.rating is not None:
                escaped_rating = escape_markdown(str(entry.rating))
                entry_specific_parts_md.append(f"Оцінка: *{escaped_rating}/5*")
            if hasattr(entry, 'text') and entry.text:
                entry_specific_parts_md.append(escape_markdown(entry.text))

        tags_display_formatted = ""
        if entry.tags_str:
            tags_list_raw = [tag.strip() for tag in entry.tags_str.split(',') if tag.strip()]
            tags_list_escaped = [f"\\#{escape_markdown(tag)}" for tag in tags_list_raw]
            if tags_list_escaped:
                tags_display_formatted = "\n*Теги:* " + ", ".join(tags_list_escaped)

        entry_header_md = f"🗓️ *{date_str_escaped}*"
        entry_content_joined_md = " \\- ".join(filter(None, entry_specific_parts_md))
        full_entry_text = f"\n{entry_header_md}"
        if entry_content_joined_md:
            full_entry_text += f" \\- {entry_content_joined_md}"
        full_entry_text += f"{tags_display_formatted}\n────────────────────"
        message_parts.append(full_entry_text)

    message_text_final = "\n".join(message_parts)
    keyboard_buttons = []
    pagination_row = []
    base_callback_prefix = f"{entry_config_key}"
    filter_callback_part = ""
    if tag_filter:
        safe_tag = tag_filter.replace(":", "_").replace("#", "")
        filter_callback_part = f":tag:{safe_tag}"
    elif entry_type_filter and entry_config_key == "journal":
        safe_type = entry_type_filter.replace(":", "_")
        filter_callback_part = f":type:{safe_type}"
    callback_data_prefix_with_filter = f"{base_callback_prefix}{filter_callback_part}"
    if page > 0:
        pagination_row.append(InlineKeyboardButton(
            "⬅️ Попередня",
            callback_data=f"{callback_data_prefix_with_filter}:page:{page - 1}"))
    if (page + 1) * page_size < total_entries:
        pagination_row.append(InlineKeyboardButton(
            "Наступна ➡️",
            callback_data=f"{callback_data_prefix_with_filter}:page:{page + 1}")
        )
    if pagination_row:
        keyboard_buttons.append(pagination_row)
    reply_markup = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

    try:
        if is_callback:
            await update.callback_query.edit_message_text(message_text_final, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await target_message_obj.reply_text(message_text_final, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest as e_br:

        print(f"BadRequest in show_paginated_entries: {e_br}")
        await target_message_obj.reply_text("Помилка форматування, спробуйте пізніше.")
    except Exception as e_gen:
        print(f"Exception in show_paginated_entries: {e_gen}")
        await target_message_obj.reply_text("Сталася помилка при відображенні записів.")


async def show_journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag_filter = None
    entry_type_filter = None
    if context.args:
        first_arg = context.args[0]
        if first_arg.startswith("#") and len(first_arg) > 1:
            tag_filter = first_arg[1:]
            print(f"DEBUG: /my_journal called with tag: {tag_filter}")
        elif first_arg.lower() in ENTRY_TYPE_DISPLAY_CONFIG.get("journal", {}):
            entry_type_filter = first_arg.lower()
            print(f"DEBUG: /my_journal called with entry_type: {entry_type_filter}")

    await show_paginated_entries(update, context, page=0, entry_config_key="journal",
                                 tag_filter=tag_filter, entry_type_filter=entry_type_filter)


async def show_mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag_filter = None
    if context.args:
        tag_arg = context.args[0]
        if tag_arg.startswith("#") and len(tag_arg) > 1:
            tag_filter = tag_arg[1:]
            print(f"DEBUG: /my_moods called with tag: {tag_filter}")

    await show_paginated_entries(update, context, page=0, entry_config_key="mood", tag_filter=tag_filter)


async def handle_generic_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":")


    entry_config_key = data_parts[0]
    tag_filter_cb = None
    entry_type_filter_cb = None
    page_num_cb = 0

    if entry_config_key not in ["journal", "mood"]:
        await query.message.reply_text("Помилка: Невідомий тип для пагінації.")
        return

    try:
        if len(data_parts) == 3 and data_parts[1] == "page":
            page_num_cb = int(data_parts[2])
        elif len(data_parts) == 5 and data_parts[3] == "page":
            filter_type = data_parts[1]
            filter_value = data_parts[2].replace("_", ":")
            page_num_cb = int(data_parts[4])
            if filter_type == "tag":
                tag_filter_cb = filter_value
            elif filter_type == "type":
                entry_type_filter_cb = filter_value
            print(f"DEBUG: Pagination with filter: type='{filter_type}', value='{filter_value}', page={page_num_cb}")
        else:
            await query.message.reply_text("Помилка: Неправильний формат даних пагінації.")
            return

        await show_paginated_entries(update, context, page=page_num_cb,
                                     entry_config_key=entry_config_key,
                                     tag_filter=tag_filter_cb,
                                     entry_type_filter=entry_type_filter_cb)
    except ValueError:
        await query.message.reply_text("Помилка: Неправильний номер сторінки.")
    except Exception as e:
        print(f"Error in handle_generic_pagination: {e}")
        await query.message.reply_text("Помилка обробки пагінації.")


async def handle_menu_button_journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопки '📖 Журнал' з головного меню."""
    await show_journal_submenu(update, context)


async def handle_menu_button_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє натискання кнопки '😊 Настрій' з головного меню."""
    await show_mood_submenu(update, context)


async def prompt_for_journal_text_menu_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запитує текст для нового запису журналу (ідея, думка, сон) після натискання кнопки в меню."""
    query = update.callback_query
    await query.answer()

    try:
        entry_type = query.data.split(":")[2]
    except IndexError:
        await query.edit_message_text("Помилка: не вдалося визначити тип запису. Спробуйте знову.")
        return ConversationHandler.END

    context.user_data['conv_journal_entry_type'] = entry_type

    display_name_map = ENTRY_TYPE_DISPLAY_CONFIG.get("journal", {})
    display_name = display_name_map.get(entry_type, entry_type.capitalize())

    await query.edit_message_text(text=f"Введіть текст для вашої '{display_name}':\n(або /cancel для скасування)")
    return GET_JOURNAL_ENTRY_TEXT_FROM_MENU


async def received_journal_text_menu_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримує текст, зберігає запис журналу та завершує розмову."""
    user_id = update.effective_user.id
    text_content_with_tags = update.message.text.strip()

    entry_type = context.user_data.pop('conv_journal_entry_type', None)

    if not entry_type:
        await update.message.reply_text("Помилка: тип запису не визначено. Спробуйте знову або /cancel.")
        return ConversationHandler.END

    if not text_content_with_tags:
        await update.message.reply_text("Текст запису не може бути порожнім. Спробуйте ще раз або /cancel.")
        context.user_data['conv_journal_entry_type'] = entry_type
        return GET_JOURNAL_ENTRY_TEXT_FROM_MENU

    _created_entry, message_for_user, _parsed_tags, _text_for_analysis = save_generic_entry_logic(
        user_id, entry_type, text_content_with_tags
    )

    await update.message.reply_text(message_for_user)
    await send_main_menu(update, context, "Повертаюся в головне меню...")
    return ConversationHandler.END


async def cancel_journal_entry_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасовує розмову створення запису журналу."""
    context.user_data.pop('conv_journal_entry_type', None)
    await update.message.reply_text("Створення запису в журнал скасовано.")
    await send_main_menu(update, context, "Головне меню:")
    return ConversationHandler.END


async def handle_journal_submenu_view_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє кнопку 'Переглянути мій журнал'."""
    query = update.callback_query
    await query.answer()

    await show_journal_command(update, context)


async def prompt_for_mood_entry_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запитує опис настрою/оцінку після натискання кнопки в меню."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="Будь ласка, опишіть свій настрій або поставте оцінку (1-5).\n"
             "Наприклад: '5 Чудово почуваюся #натхнення' або просто 'Сумно'.\n"
             "Або надішліть /cancel для скасування."
    )
    return GET_MOOD_ENTRY_FROM_MENU


async def received_mood_entry_menu_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримує текст/оцінку, зберігає запис настрою та завершує розмову."""
    user_id = update.effective_user.id
    full_content_input = update.message.text.strip()

    if not full_content_input:
        await update.message.reply_text("Запис про настрій не може бути порожнім. Спробуйте ще раз або /cancel.")
        return GET_MOOD_ENTRY_FROM_MENU

    created_entry, confirmation_msg, _parsed_tags, text_for_mood_analysis = save_generic_entry_logic(
        user_id, "mood", full_content_input
    )

    await update.message.reply_text(confirmation_msg)

    if created_entry and text_for_mood_analysis:
        normalized_text = text_for_mood_analysis.lower()
        advice_to_send = None
        mood_advice_rules = get_mood_advice_rules()

        for rule in mood_advice_rules:
            if not isinstance(rule, dict) or "keywords" not in rule or "advice" not in rule:
                continue
            current_keywords = rule["keywords"]
            if isinstance(current_keywords, str):
                current_keywords = [current_keywords]
            if not isinstance(current_keywords, list):
                continue

            for keyword in current_keywords:
                if keyword.lower() in normalized_text:
                    advice_to_send = rule["advice"]
                    break
            if advice_to_send:
                break

        if advice_to_send:
            await update.message.reply_text(advice_to_send)

    await send_main_menu(update, context, "Повертаюся в головне меню...")
    return ConversationHandler.END


async def cancel_mood_entry_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасовує розмову створення запису настрою."""
    await update.message.reply_text("Запис настрою скасовано.")
    await send_main_menu(update, context, "Головне меню:")
    return ConversationHandler.END


async def handle_mood_submenu_view_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє кнопку 'Переглянути історію настрою'."""
    query = update.callback_query
    await query.answer()
    await show_mood_command(update, context)
