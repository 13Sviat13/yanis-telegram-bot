# yanis-telegram-bot
# 🤖 Yanis Bot: Персональний асистент у Telegram

> Багатофункціональний Telegram-бот для автоматизації повсякденних завдань, управління часом та ведення особистих записів.

---

## 👤 Автор

- **ПІБ**: Николин Святослав Тарасович
- **Група**: ФЕП-42
- **Керівник**: проф. Клим Галина Іванівна 
- **Дата виконання**: 01.05.2025

---

## 📌 Загальна інформація

- **Тип проєкту**: Telegram-бот
- **Мова програмування**: Python
- **Ключові бібліотеки/фреймворки**: `python-telegram-bot`, `SQLAlchemy`, `Flask`, `Alembic`, `psycopg2-binary`.
- **База даних**: PostgreSQL

---

## 🧠 Опис функціоналу

- ✅ **Управління завданнями:** Створення, пріоритезація, перегляд списку, позначення як виконаних.
- ⏰ **Система нагадувань:** Встановлення та перенесення нагадувань для завдань.
- 🍅 **Таймер Pomodoro:** Техніка для фокусованої роботи з можливістю прив'язки сесій до конкретних завдань.
- 📖 **Журналінг:** Збереження ідей, думок та снів з підтримкою тегів.
- 😊 **Відстеження настрою:** Можливість записувати настрій з оцінкою та текстом, отримання автоматизованих порад на основі ключових слів.
- 📊 **Статистика:** Перегляд особистої продуктивності (виконані завдання, сесії Pomodoro).
- 💡 **Поради:** Отримання порад з фокусування та продуктивності.
- 🧭 **Меню-керований інтерфейс:** Взаємодія з ботом через зручні кнопки меню замість текстових команд.

---

## 🧱 Опис основних модулів / файлів

| Файл / Директорія           | Призначення                                                                                      |
|-----------------------------|--------------------------------------------------------------------------------------------------|
| `app.py`                    | Головний файл запуску. Ініціалізує додаток, БД, та запускає бота і фонові процеси.                 |
| `config.py` / `.env`        | Зберігання конфігураційних змінних (токен, рядок підключення до БД).                               |
| `data/`                     | Директорія для файлів даних (`*.json`, `bot_persistence.pickle`).                                    |
| `bot/models.py`             | Визначення моделей бази даних (`Task`, `PomodoroSession`, `JournalEntry`, `MoodEntry`).             |
| `bot/logic/logic.py`        | Основна бізнес-логіка: функції для роботи з БД, відокремлені від обробників.                      |
| `bot/logic/menu_navigation.py` | Визначення та функції для відображення головного меню та інтерактивних підменю.                     |
| `bot/commands/`             | Пакет з обробниками команд, згрупованими за функціоналом (`tasks.py`, `journaling.py` і т.д.). |
| `bot/pomodoro.py`           | Логіка та обробники для функціоналу Pomodoro.                                                    |
| `bot/reminder.py`           | Логіка фонової системи перевірки та відправки нагадувань.                                         |
| `alembic.ini` / `migrations/`| Конфігурація та файли міграцій бази даних Alembic.                                                |

---

## ▶️ Як запустити проєкт "з нуля"

### 1. Встановлення інструментів

- **Python** (рекомендована версія 3.10 або вище)
- **PostgreSQL** (встановлений локально або доступний через хмарний сервіс)
- **Git** (для клонування репозиторію)

### 2. Клонування репозиторію

```bash
git clone https://github.com/13Sviat13/yanis-telegram-bot.git
cd yanis-telegram-bot
```

### 3. Створення та активація віртуального середовища

```bash
# Створення віртуального середовища
python3 -m venv venv

# Активація (macOS/Linux)
source venv/bin/activate

# Активація (Windows)
# venv\Scripts\activate
```

### 4. Встановлення залежностей

```bash
pip install -r requirements.txt
```
*(Примітка: Вам потрібно буде створити файл `requirements.txt`. Це можна зробити командою `pip freeze > requirements.txt` після встановлення всіх бібліотек).*

### 5. Налаштування PostgreSQL та `.env`

1.  **Створіть базу даних PostgreSQL та користувача** для бота (детальніше описано в документації або бакалаврській роботі).
2.  **Створіть файл `.env`** у кореневій директорії проєкту та додайте до нього ваші конфігураційні змінні:

```env
BOT_TOKEN=ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН
DATABASE_URL=postgresql://ім'я_користувача:пароль@хост:порт/назва_бази_даних
```

### 6. Застосування міграцій бази даних

Переконайтеся, що `alembic.ini` налаштований на вашу базу даних PostgreSQL, а потім виконайте:
```bash
alembic upgrade head
```

### 7. Запуск

```bash
python app.py
```

---

## 🖱️ Інструкція для користувача

1. **Запустіть бота** командою `/start`. З'явиться головне меню з кнопками.
2. **"📝 Завдання"**:
    - `➕ Додати нове завдання`: Запускає діалог, де бот запитає опис, а потім запропонує встановити пріоритет.
    - `📋 Переглянути список завдань`: Показує таблицю ваших активних завдань. Ви можете використовувати кнопки `✅`, `📊`, `⏰` для взаємодії з кожним завданням.
3. **"📖 Журнал"**:
    - `💡 Ідея`, `💭 Думка`, `🌙 Сон`: Запускають діалог для запису відповідної нотатки. Можна використовувати `#теги`.
    - `📚 Переглянути мій журнал`: Показує всі ваші ідеї, думки та сни з пагінацією. Можна фільтрувати за типом (`/my_journal idea`) або тегом (`/my_journal #тег`).
4. **"😊 Настрій"**:
    - `✏️ Записати настрій`: Запускає діалог, де можна вказати оцінку (1-5) та/або текстовий опис. Якщо текст містить ключові слова ("втома", "радість" тощо), бот надасть пораду.
    - `📊 Переглянути історію настрою`: Показує історію ваших записів про настрій.
5. **"🍅 Pomodoro"**:
    - `🚀 Запустити без прив'язки`: Запускає стандартний Pomodoro.
    - `🔗 Запустити для завдання...`: Показує список ваших активних завдань, щоб ви могли обрати, на яке з них буде витрачено час.

---

## 📷 Приклади / скриншоти

**(Сюди ви можете додати ваші найкращі скріншоти. Створіть папку `/screenshots/` у проекті та покладіть їх туди)**

- **Рисунок 1:** Головне меню бота (`ReplyKeyboardMarkup`) та підменю "Завдання" (`InlineKeyboardMarkup`).
- **Рисунок 2:** Список завдань у табличному вигляді.
- **Рисунок 3:** Діалог додавання завдання з вибором пріоритету.
- **Рисунок 4:** Інтерфейс активного таймера Pomodoro.
- **Рисунок 5:** Приклад перегляду журналу настрою з пагінацією.
- **Рисунок 6:** Приклад виводу статистики `/stats`.

---

## 🧪 Проблеми і рішення

| Проблема                                    | Можливе рішення                                                                                                      |
|:--------------------------------------------|:-------------------------------------------------------------------------------------------------------------------|
| Бот не запускається / Помилка підключення до БД | Перевірити правильність рядка `DATABASE_URL` у `.env` файлі та чи запущений сервер PostgreSQL.            |
| Помилка `alembic upgrade head`                | Перевірити `sqlalchemy.url` в `alembic.ini`. Переконатись, що база даних та користувач створені в PostgreSQL. |
| Помилки `BadRequest` при відправці повідомлень | Перевірити екранування спеціальних символів Markdown (`.`, `(`, `)`, `-` тощо) у текстах, що надсилаються. |
| Кнопки меню не працюють                      | Перевірити реєстрацію відповідних `MessageHandler` та `CallbackQueryHandler` у `bot/bot.py`.                    |
| Не працюють нагадування                      | Перевірити, чи запущено фоновий потік `reminder.py` та чи коректно працює `JobQueue`.                     |

---

## 🧾 Використані джерела / література

1.  Python 3.10 documentation ...
2.  `python-telegram-bot` Documentation ...
3.  PostgreSQL Documentation ...
4.  SQLAlchemy ORM Documentation ...
5.  Alembic Documentation ...
