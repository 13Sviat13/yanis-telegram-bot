from telegram.ext import CommandHandler, filters, MessageHandler, CallbackQueryHandler, ConversationHandler

from bot.logic.menu_navigation import (
    MENU_TASKS_TEXT, MENU_JOURNAL_TEXT, MENU_MOOD_TEXT,
    MENU_POMODORO_TEXT, MENU_STATS_TEXT, MENU_TIP_TEXT,
)

from .commands.general import (
    start,
    show_stats,
    tip_command,
    cancel_conversation,
    fallback_in_conversation,
    menu_command,  # Команда /menu
    handle_menu_button_stats,
    handle_menu_button_tip

)
from bot.commands.tasks import (
    add_task_conversation_starter,
    list_tasks_command,
    done,
    set_reminder,
    handle_delay_time_input,
    handle_reminder_time_input,
    handle_button,
    handle_task_button,
    handle_priority_selection,
    handle_pomodoro_confirm,
    handle_reminder_confirm,
    handle_reminder_time_input_conv,
    ASK_PRIORITY, AWAIT_POMODORO_CONFIRM, AWAIT_REMINDER_CONFIRM, GET_REMINDER_TIME_CONV,
    handle_menu_button_tasks, prompt_for_task_description_conv_entry, GET_TASK_DESCRIPTION,
    received_task_description_conv_state, handle_tasks_submenu_action
)
from .commands.journaling import (
    save_generic_entry,
    show_journal_command,
    show_mood_command,
    handle_generic_pagination, handle_menu_button_journal, handle_menu_button_mood, prompt_for_journal_text_menu_entry,
    GET_JOURNAL_ENTRY_TEXT_FROM_MENU, received_journal_text_menu_state, cancel_journal_entry_conversation,
    handle_journal_submenu_view_all, prompt_for_mood_entry_menu, GET_MOOD_ENTRY_FROM_MENU,
    cancel_mood_entry_conversation, received_mood_entry_menu_state, handle_mood_submenu_view_all
)


from bot.commands.pomodoro import start_pomodoro_command, handle_pomodoro_button, handle_menu_button_pomodoro, \
    handle_pomodoro_submenu_action


def register_handlers(app_bot):
    add_task_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_task_conversation_starter),
                      CallbackQueryHandler(prompt_for_task_description_conv_entry, pattern=r"^tasks_submenu:add$")],
        states={
            GET_TASK_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_task_description_conv_state)],

            ASK_PRIORITY: [CallbackQueryHandler(handle_priority_selection, pattern=r"^conv_prio:")],
            AWAIT_POMODORO_CONFIRM: [CallbackQueryHandler(handle_pomodoro_confirm, pattern=r"^conv_sugg:pom_")],
            AWAIT_REMINDER_CONFIRM: [CallbackQueryHandler(handle_reminder_confirm, pattern=r"^conv_sugg:rem_")],
            GET_REMINDER_TIME_CONV: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reminder_time_input_conv)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_conversation),
            MessageHandler(filters.COMMAND | filters.TEXT, fallback_in_conversation)
        ],
        name="add_task_conversation",
        persistent=True
    )
    new_journal_entry_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(prompt_for_journal_text_menu_entry,
                                 pattern=r"^journal_submenu:new:(idea|thought|dream)$")
        ],
        states={
            GET_JOURNAL_ENTRY_TEXT_FROM_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_journal_text_menu_state)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_journal_entry_conversation)
        ],
        name="new_journal_entry_conversation",
        persistent=True
    )
    new_mood_entry_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(prompt_for_mood_entry_menu, pattern=r"^mood_submenu:new$")
        ],
        states={
            GET_MOOD_ENTRY_FROM_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_mood_entry_menu_state)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_mood_entry_conversation)
        ],
        name="new_mood_entry_conversation",
        persistent=True
    )
    app_bot.add_handler(add_task_conv_handler)
    app_bot.add_handler(new_journal_entry_conv_handler)
    app_bot.add_handler(new_mood_entry_conv_handler)

    app_bot.add_handler(CommandHandler('start', start))
    app_bot.add_handler(CommandHandler('menu', menu_command))
    app_bot.add_handler(CommandHandler('list', list_tasks_command))
    app_bot.add_handler(CommandHandler('done', done))
    app_bot.add_handler(CommandHandler('remind', set_reminder))
    app_bot.add_handler(CommandHandler('pomodoro', start_pomodoro_command))
    app_bot.add_handler(CommandHandler('stats', show_stats))
    app_bot.add_handler(CommandHandler('tip', tip_command))

    app_bot.add_handler(CommandHandler('idea', save_generic_entry))
    app_bot.add_handler(CommandHandler('thought', save_generic_entry))
    app_bot.add_handler(CommandHandler('dream', save_generic_entry))
    app_bot.add_handler(CommandHandler('my_journal', show_journal_command))
    app_bot.add_handler(CommandHandler('mood', save_generic_entry))
    app_bot.add_handler(CommandHandler('my_moods', show_mood_command))
    app_bot.add_handler(MessageHandler(filters.Text([MENU_STATS_TEXT]), handle_menu_button_stats), group=-1)
    app_bot.add_handler(MessageHandler(filters.Text([MENU_TIP_TEXT]), handle_menu_button_tip), group=-1)
    app_bot.add_handler(MessageHandler(filters.Text([MENU_TASKS_TEXT]), handle_menu_button_tasks), group=-1)
    app_bot.add_handler(MessageHandler(filters.Text([MENU_JOURNAL_TEXT]), handle_menu_button_journal), group=-1)
    app_bot.add_handler(MessageHandler(filters.Text([MENU_MOOD_TEXT]), handle_menu_button_mood), group=-1)
    app_bot.add_handler(MessageHandler(filters.Text([MENU_POMODORO_TEXT]), handle_menu_button_pomodoro), group=-1)
    app_bot.add_handler(MessageHandler(filters.Text([MENU_POMODORO_TEXT]), handle_menu_button_pomodoro), group=-1)

    app_bot.add_handler(MessageHandler(filters.Regex(r'^/done_(\d+)$'), done))
    app_bot.add_handler(MessageHandler(filters.Regex(r'^/remind_(\d+)$'), set_reminder))

    app_bot.add_handler(CallbackQueryHandler(handle_task_button, pattern=r"^task:"))
    app_bot.add_handler(CallbackQueryHandler(handle_tasks_submenu_action, pattern=r"^tasks_submenu:"))
    app_bot.add_handler(CallbackQueryHandler(handle_journal_submenu_view_all, pattern=r"^journal_submenu:view_all$"))
    app_bot.add_handler(CallbackQueryHandler(handle_mood_submenu_view_all, pattern=r"^mood_submenu:view_all$"))
    app_bot.add_handler(CallbackQueryHandler(handle_pomodoro_submenu_action, pattern=r"^pomodoro_submenu:"))

    app_bot.add_handler(CallbackQueryHandler(handle_pomodoro_button, pattern=r"^pom:"))
    app_bot.add_handler(CallbackQueryHandler(handle_button, pattern=r"^(done|delay):"))
    app_bot.add_handler(
        CallbackQueryHandler(handle_generic_pagination, pattern=r"^(journal|mood)(:(tag|type):[^:]+)?:page:\d+"))

    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reminder_time_input), group=0)
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delay_time_input), group=1)
