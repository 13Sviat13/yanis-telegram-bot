from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import ContextTypes

# --- Тексти для кнопок Головного Меню ---
MENU_TASKS_TEXT = "📝 Завдання"
MENU_JOURNAL_TEXT = "📖 Журнал"
MENU_MOOD_TEXT = "😊 Настрій"
MENU_POMODORO_TEXT = "🍅 Pomodoro"
MENU_STATS_TEXT = "📊 Статистика"
MENU_TIP_TEXT = "💡 Порада дня"

# Головна клавіатура (ReplyKeyboard)
main_menu_keyboard_layout = [
    [KeyboardButton(MENU_TASKS_TEXT), KeyboardButton(MENU_JOURNAL_TEXT)],
    [KeyboardButton(MENU_MOOD_TEXT), KeyboardButton(MENU_POMODORO_TEXT)],
    [KeyboardButton(MENU_STATS_TEXT), KeyboardButton(MENU_TIP_TEXT)]
]
main_menu_reply_markup = ReplyKeyboardMarkup(
    main_menu_keyboard_layout,
    resize_keyboard=True,
    one_time_keyboard=False
)


async def send_main_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        message_text: str | None = None
):
    """Надсилає вітальне повідомлення та головне меню."""
    chat_id = update.effective_chat.id
    text_to_send = message_text if message_text else "Головне меню. Оберіть дію:"

    target_message_obj = update.message
    if not target_message_obj and update.callback_query:
        target_message_obj = update.callback_query.message

    if target_message_obj:
        await target_message_obj.reply_text(
            text_to_send,
            reply_markup=main_menu_reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text_to_send,
            reply_markup=main_menu_reply_markup
        )


async def show_tasks_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(
            "➕ Додати нове завдання",
            callback_data="tasks_submenu:add"
        )],
        [InlineKeyboardButton(
            "📋 Переглянути список завдань",
            callback_data="tasks_submenu:list"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Оберіть дію із завданнями:",
        reply_markup=reply_markup
    )


async def show_journal_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "💡 Ідея",
                callback_data="journal_submenu:new:idea"
            ),
            InlineKeyboardButton(
                "💭 Думка",
                callback_data="journal_submenu:new:thought"
            ),
            InlineKeyboardButton(
                "🌙 Сон",
                callback_data="journal_submenu:new:dream"
            ),
        ],
        [InlineKeyboardButton(
            "📚 Переглянути мій журнал",
            callback_data="journal_submenu:view_all"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Що бажаєте зробити з журналом?",
        reply_markup=reply_markup
    )


async def show_mood_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(
            "✏️ Записати настрій",
            callback_data="mood_submenu:new"
        )],
        [InlineKeyboardButton(
            "📊 Переглянути історію настрою",
            callback_data="mood_submenu:view_all"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Оберіть дію для журналу настрою:",
        reply_markup=reply_markup
    )


async def show_pomodoro_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(
            "🚀 Запустити Pomodoro (без прив'язки)",
            callback_data="pomodoro_submenu:start_any"
        )],
        [InlineKeyboardButton(
            "🔗 Запустити для завдання...",
            callback_data="pomodoro_submenu:start_linked_select_task"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Налаштування Pomodoro:", reply_markup=reply_markup)
