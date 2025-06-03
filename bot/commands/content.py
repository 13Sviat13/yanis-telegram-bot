import random
import os
import json


FOCUS_TIPS_JSON_PATH = "/Users/sviat13/PycharmProjects/telegram_bot_pt1/data/focus_tips.json"
_cached_focus_intro = None
_cached_focus_detailed_sections = []
MOOD_ADVICE_JSON_PATH = "/Users/sviat13/PycharmProjects/telegram_bot_pt1/data/mood_responses.json"
_cached_mood_advice_rules = []


def _load_mood_advice_from_json():
    """Завантажує правила для порад настрою з JSON файлу."""
    global _cached_mood_advice_rules
    _cached_mood_advice_rules = []

    script_dir = os.path.dirname('/data/mood_responses.json')
    file_path = os.path.join(script_dir, "data", MOOD_ADVICE_JSON_PATH)
    file_path = MOOD_ADVICE_JSON_PATH

    if not os.path.exists(file_path):
        print(f"ПОПЕРЕДЖЕННЯ: Файл з порадами для настрою '{file_path}' не знайдено.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                valid_rules = []
                for item in data:
                    if isinstance(item, dict) and \
                            "keywords" in item and isinstance(item["keywords"], list) and \
                            "advice" in item and isinstance(item["advice"], str):
                        valid_rules.append(item)
                    else:
                        print(f"ПОПЕРЕДЖЕННЯ: Неправильний формат запису в '{file_path}': {item}")

                _cached_mood_advice_rules = valid_rules
                if _cached_mood_advice_rules:
                    print(
                        f"Успішно завантажено {len(_cached_mood_advice_rules)} правил для порад настрою з '{file_path}'.")
                else:
                    print(f"ПОПЕРЕДЖЕННЯ: Не знайдено валідних правил у '{file_path}'.")
            else:
                print(f"ПОМИЛКА ФОРМАТУ: Файл '{file_path}' має містити JSON список (масив).")
    except json.JSONDecodeError as e:
        print(f"ПОМИЛКА JSON ДЕКОДУВАННЯ у файлі '{file_path}': {e}")
    except Exception as e:
        print(f"ПОМИЛКА при читанні файлу з порадами для настрою '{file_path}': {e}")


def get_mood_advice_rules() -> list:
    """Повертає список правил (словників) "ключові слова - порада".
       Завантажує з файлу, якщо кеш порожній.
    """
    if not _cached_mood_advice_rules:
        _load_mood_advice_from_json()
    return _cached_mood_advice_rules


def _load_focus_tips_from_json():
    global _cached_focus_intro, _cached_focus_detailed_sections
    _cached_focus_intro = None
    _cached_focus_detailed_sections = []
    file_path = FOCUS_TIPS_JSON_PATH

    if not os.path.exists(file_path):
        print(f"ПОПЕРЕДЖЕННЯ: Файл '{file_path}' не знайдено.")
        _cached_focus_intro = "Помилка: Вступ для порад з фокусування не знайдено."
        _cached_focus_detailed_sections.append("Помилка: Детальні поради з фокусування не знайдено.")
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and "introduction" in data and "detailed_sections" in data:
                _cached_focus_intro = data["introduction"]
                if isinstance(data["detailed_sections"], list):
                    _cached_focus_detailed_sections = data["detailed_sections"]
                else:
                    print(f"ПОПЕРЕДЖЕННЯ: 'detailed_sections' у '{file_path}' не є списком.")
                    _cached_focus_detailed_sections.append("Помилка: Неправильний формат детальних порад.")
                if _cached_focus_intro and _cached_focus_detailed_sections and not (
                        "Помилка" in _cached_focus_detailed_sections[0] if _cached_focus_detailed_sections else True):
                    print(
                        f"Успішно завантажено вступ та {len(_cached_focus_detailed_sections)} детальних порад з фокусування з '{file_path}'.")
                else:
                    if not _cached_focus_intro:
                        _cached_focus_intro = "Помилка завантаження вступу для фокус-порад."
                    if not _cached_focus_detailed_sections:
                        _cached_focus_detailed_sections.append(
                            "Помилка завантаження детальних фокус-порад."
                        )
            else:
                print(
                    f"ПОМИЛКА ФОРМАТУ: Файл '{file_path}' має містити об'єкт з ключами 'introduction' та 'detailed_sections'.")
                _cached_focus_intro = "Помилка формату файлу фокус-порад (вступ)."
                _cached_focus_detailed_sections.append("Помилка формату файлу фокус-порад (секції).")
    except json.JSONDecodeError as e:
        print(f"ПОМИЛКА JSON ДЕКОДУВАННЯ у файлі '{file_path}': {e}")
    except Exception as e:

        print(f"ПОМИЛКА при читанні файлу '{file_path}': {e}")


def get_structured_focus_tip() -> str:
    if _cached_focus_intro is None or not _cached_focus_detailed_sections:
        _load_focus_tips_from_json()
    if "Помилка" in (_cached_focus_intro or "") or \
            (_cached_focus_detailed_sections and "Помилка" in _cached_focus_detailed_sections[0]):
        return "Вибачте, поради з фокусування тимчасово недоступні."
    if not _cached_focus_detailed_sections:
        return f"{_cached_focus_intro.strip() if _cached_focus_intro else ''}\n\nНа жаль, детальні поради зараз недоступні.".strip()

    random_detailed_tip = random.choice(_cached_focus_detailed_sections)

    intro_text = _cached_focus_intro.strip() if _cached_focus_intro else ""
    return f"{intro_text}\n\n{random_detailed_tip.strip()}"


def get_random_tip() -> str:
    return get_structured_focus_tip()
