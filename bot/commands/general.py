import datetime
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update

from bot.commands.content import get_structured_focus_tip
from bot.logic.logic import get_statistics_logic
from bot.commands.pomodoro import WORK_DURATION_MIN
from bot.logic.menu_navigation import send_main_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await send_main_menu(update, context,
                         message_text=f"Привіт, {user_name}! Мене звати Яніс, ваш персональний помічник.\nЧим можу допомогти?")


async def fallback_in_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Здається, ми зараз щось обговорювали. Ви можете завершити це за допомогою /cancel або продовжити.")


async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Надсилає користувачу структуровану пораду з фокусування."""
    tip_article = get_structured_focus_tip()

    internal_error_phrases = [
        "Помилка: Вступний текст",
        "Помилка: Детальні поради не знайдено",
        "Помилка форматування вступного тексту",
        "На жаль, детальні поради зараз недоступні",
        "Виникла помилка при завантаженні",
        "Вибачте, поради тимчасово недоступні"
    ]

    is_internal_error_message = any(phrase in tip_article for phrase in internal_error_phrases)

    if is_internal_error_message:
        await update.message.reply_text(tip_article)
    else:
        try:
            await update.message.reply_text(tip_article, parse_mode=ParseMode.MARKDOWN_V2)
        except BadRequest as e:
            print(f"Telegram BadRequest при надсиланні поради з MarkdownV2: {e}")
            print(f"Оригінальний текст поради був:\n{tip_article}")
            await update.message.reply_text(
                "Виникла невелика проблема з форматуванням поради. Ось вона у простому вигляді:\n\n" + tip_article
            )
        except Exception as e:
            print(f"Неочікувана помилка в tip_command: {e}")

            await update.message.reply_text("Ой, сталася помилка при відображенні поради.")


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасовує поточну розмову (якщо вона є)."""
    keys_to_pop = ['conv_task_id']
    cleaned_any = False
    for key in keys_to_pop:
        if key in context.user_data:
            context.user_data.pop(key, None)
            cleaned_any = True
    if cleaned_any:
        await update.message.reply_text("Дію скасовано.")
    else:

        await update.message.reply_text("Немає активної операції для скасування.")
    return ConversationHandler.END


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now_display_raw = datetime.datetime.now(datetime.timezone.utc).strftime('%d.%m.%Y')
    now_display_escaped = escape_markdown(now_display_raw, version=2)

    stats = get_statistics_logic(user_id)

    if not stats:
        await update.message.reply_text("Не вдалося отримати статистику. Спробуйте пізніше.")
        return

    header_text = f"📊 *Ваша статистика* \\({now_display_escaped}\\) 📊"
    message_parts = [header_text + "\n"]

    message_parts.append(
        f"*Виконано завдань:*\n"  
        f"  \\- Сьогодні: {stats.get('tasks_today', 0)}\n"
        f"  \\- Цього тижня: {stats.get('tasks_week', 0)}\n"
        f"  \\- Цього місяця: {stats.get('tasks_month', 0)}\n"
    )

    tpw_minutes = (stats.get('total_pomodoros_week', 0) * WORK_DURATION_MIN)
    tpm_minutes = (stats.get('total_pomodoros_month', 0) * WORK_DURATION_MIN)
    message_parts.append(
        f"\n*Завершено Pomodoro \\(робочих, загалом\\):*\n"
        f"  \\- Сьогодні: {stats.get('total_pomodoros_today', 0)}\n"
        f"  \\- Цього тижня: {stats.get('total_pomodoros_week', 0)} \\(≈ {tpw_minutes // 60} год {tpw_minutes % 60} хв\\)\n"
        f"  \\- Цього місяця: {stats.get('total_pomodoros_month', 0)} \\(≈ {tpm_minutes // 60} год {tpm_minutes % 60} хв\\)\n"
    )

    completed_pom_per_task = stats.get('completed_pomodoros_per_task', [])
    if completed_pom_per_task:
        message_parts.append("\n*Завершені Pomodoro по завданнях \\(топ\\-5\\):*")
        for desc_raw, count in completed_pom_per_task:
            desc_escaped = escape_markdown(desc_raw or "Невідоме завдання", version=2)
            focus_time_minutes = count * WORK_DURATION_MIN
            message_parts.append(
                f"  \\- «{desc_escaped}»: {count} сесій \\(≈ {focus_time_minutes // 60} год {focus_time_minutes % 60} хв\\)"
            )

    tsmw_minutes = stats.get('total_stopped_minutes_week', 0)
    message_parts.append(
        f"\n*Перервано Pomodoro \\(робочих, цього тижня\\):*\n"
        f"  \\- Кількість: {stats.get('stopped_pom_count_week', 0)}\n"
        f"  \\- Загальний витрачений час: ≈ {tsmw_minutes // 60} год {tsmw_minutes % 60} хв"
    )

    final_message = "\n".join(message_parts)

    try:
        await update.message.reply_text(final_message, parse_mode=ParseMode.MARKDOWN_V2)
    except BadRequest as e_stats_br:
        print(f"Помилка Markdown в show_stats ПІСЛЯ ВИПРАВЛЕНЬ: {e_stats_br}")
        print(f"Проблемний текст:\n{final_message}")
        plain_text_parts = [f"Ваша статистика ({now_display_raw})\n"]
        plain_text_parts.append(f"Виконано завдань:\n  - Сьогодні: {stats.get('tasks_today', 0)}\n  - ...")
        await update.message.reply_text("Виникла помилка форматування статистики. Спробуйте пізніше.")
    except Exception as e_stats:
        print(f"Загальна помилка в show_stats: {e_stats}")
        await update.message.reply_text("Не вдалося відобразити статистику.")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update, context, message_text="Головне меню:")


async def handle_menu_button_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_stats(update, context)


async def handle_menu_button_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await tip_command(update, context)
