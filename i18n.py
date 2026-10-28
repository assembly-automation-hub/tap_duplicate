"""English/Ukrainian interface strings. The first-run language is English."""
from dataclasses import dataclass, field
import re

LANGUAGES = {"en": "English", "uk": "Українська"}
STRINGS = {}
BACKEND = {}


def entry(key, english, ukrainian, original=None):
    STRINGS[key] = {"en": english, "uk": ukrainian}
    if original:
        BACKEND[original] = key


entry("app_name", "Tap Duplicator", "Тап дублікатор")
entry("language", "Language", "Мова")
entry("windows", "Windows", "Вікна")
entry("left", "Left window", "Ліве вікно")
entry("right", "Right window", "Праве вікно")
entry("refresh", "Refresh windows", "Оновити вікна")
entry("arrange", "Place side by side", "Розмістити поруч")
entry("typing", "Text input", "Введення в поля")
entry("scroll", "Scrolling", "Прокручування")
entry("start", "Mirror · F8", "Дублювати · F8")
entry("pause", "Pause · F8", "Пауза · F8")
entry("stop", "Stop · F9", "Стоп · F9")
entry("status_on", "Mirroring on: left → right", "Дублювання ввімкнено: ліве → праве")
entry("status_off", "Mirroring off", "Дублювання вимкнено")
entry("counter", "Clicks: {count}", "Натискань: {count}")
entry("starting", "Starting input handling…", "Запуск обробки введення…")
entry("windows_found", "Windows found: {count}. Open two application windows, then click Refresh windows.",
      "Знайдено вікон: {count}. Відкрийте два вікна програми та натисніть «Оновити вікна».")
entry("ready", "Select the windows, match their sizes and enable mirroring. F9 stops mirroring.",
      "Виберіть вікна, вирівняйте їхній розмір і ввімкніть дублювання. F9 зупиняє дублювання.")
entry("arranged", "Windows are side by side. Open the same tab and align their scroll positions.",
      "Вікна розміщено поруч. Відкрийте однакову вкладку та вирівняйте прокручування.")
entry("selection_changed", "Selection or options changed. Mirroring is off.",
      "Вибір або параметри змінено. Дублювання вимкнено.", "Выбор или параметры изменились. Повтор выключен.")
entry("select_two", "Open and select two application windows first.",
      "Спочатку відкрийте та виберіть два вікна програми.", "Сначала откройте и выберите два окна программы.")
entry("different_processes", "The source and target must be different application instances.",
      "Джерело й одержувач мають бути різними екземплярами програми.", "Источник и получатель должны быть разными процессами.")
entry("already_running", "Tap Duplicator is already running. Open its window from the taskbar.",
      "Тап дублікатор уже запущено. Відкрийте його вікно на панелі завдань.")

entry("repeat_off", "Mirroring off", "Дублювання вимкнено", "Повтор выключен")
entry("repeat_on", "Mirroring on: left → right", "Дублювання ввімкнено: ліве → праве", "Повтор включён: слева → направо")
entry("stopped_f9", "Stopped with F9", "Зупинено клавішею F9", "Остановлено клавишей F9")
entry("loading", "The helper is still starting. Please wait a few seconds.",
      "Помічник ще запускається. Зачекайте кілька секунд.", "Помощник ещё запускается. Подождите несколько секунд.")
entry("different_instances", "Select two different application instances.",
      "Виберіть два різні екземпляри програми.", "Выберите два разных экземпляра программы.")
entry("both_open", "Both windows must be open and not minimized.",
      "Обидва вікна мають бути відкриті й не згорнуті.", "Оба окна должны быть открыты и не свёрнуты.")
entry("size_mismatch", "Window sizes differ. Click Place side by side.",
      "Розміри вікон відрізняються. Натисніть «Розмістити поруч».", "Размеры окон различаются. Нажмите «Расположить рядом».")
entry("too_many_events", "Events cannot be processed fast enough. Mirroring stopped.",
      "Події не встигають оброблятися. Дублювання зупинено.", "События не успевают обрабатываться. Повтор остановлен.")
entry("target_clicked", "You clicked the right window. Mirroring is off to keep the windows aligned.",
      "Ви натиснули у правому вікні. Дублювання вимкнено, щоб вікна не розсинхронізувалися.",
      "Вы нажали в правом окне. Повтор выключен, чтобы окна не рассинхронизировались.")
entry("window_closed", "A selected window was closed. Select the windows again.",
      "Одне з вибраних вікон закрито. Виберіть вікна знову.", "Одно из выбранных окон закрыто. Выберите окна заново.")
entry("window_minimized", "A window was minimized. Mirroring stopped.",
      "Одне з вікон згорнуто. Дублювання зупинено.", "Одно из окон свёрнуто. Повтор остановлен.")
entry("window_resized", "A window was resized. Align the windows and enable mirroring again.",
      "Розмір вікна змінено. Вирівняйте вікна та ввімкніть дублювання знову.",
      "Размер окна изменился. Выровняйте окна и включите повтор заново.")
entry("list_not_found", "The matching list could not be found on the right. Mirroring stopped.",
      "Не вдалося знайти відповідний список праворуч. Дублювання зупинено.",
      "Не удалось найти такой же список справа. Повтор остановлен.")
entry("text_unsupported", "This field does not support mirrored input. Mirroring stopped.",
      "Це поле не підтримує дублювання введення. Дублювання зупинено.", "Это поле не поддерживает повтор ввода. Повтор остановлен.")
entry("list_unsupported", "This list does not support mirrored selection. Mirroring stopped.",
      "Цей список не підтримує дублювання вибору. Дублювання зупинено.", "Этот список не поддерживает повтор выбора. Повтор остановлен.")
entry("list_value_missing", "The selected value is missing from the right-hand list. Mirroring stopped.",
      "У правому списку немає вибраного значення. Дублювання зупинено.",
      "В правом списке нет выбранного слева значения. Повтор остановлен.")
entry("list_item_disabled", "The selected item is unavailable in the right window.",
      "Вибраний пункт недоступний у правому вікні.", "Выбранный пункт недоступен в правом окне.")
entry("range_mismatch", "The control ranges differ. Mirroring stopped.",
      "Діапазони елементів керування відрізняються. Дублювання зупинено.", "Диапазоны элементов управления различаются. Повтор остановлен.")
entry("window_unavailable", "The window is unavailable.", "Вікно недоступне.", "Окно недоступно")
entry("sizes_differ", "Window sizes differ.", "Розміри вікон відрізняються.", "Размеры окон различаются")
entry("access_mismatch", "Access levels differ. Run the helper and both applications with the same permissions.",
      "Рівні доступу відрізняються. Запустіть помічник і обидві програми з однаковими правами.",
      "Разные права доступа. Запустите помощник и обе программы с одинаковыми правами.")
entry("many_dialogs", "Several dialogs are open. Handle them separately.",
      "Відкрито кілька діалогів. Обробіть їх окремо.", "Открыто несколько диалогов. Обработайте их отдельно.")
entry("not_confirmation", "This dialog is not a simple confirmation. Mirroring is off.",
      "Цей діалог не є простим підтвердженням. Дублювання вимкнено.", "Этот диалог не является простым подтверждением. Повтор выключен.")
entry("different_dialogs", "The dialog messages or buttons differ. Mirroring is off.",
      "Текст або кнопки діалогів відрізняються. Дублювання вимкнено.", "Текст или кнопки диалогов различаются. Повтор выключен.")
entry("paired_dialogs", "Matching confirmations: Enter and Yes/No are mirrored in both windows.",
      "Однакові підтвердження: Enter та Yes/No дублюються в обох вікнах.",
      "Одинаковые подтверждения: Enter и Yes/No повторяются в обоих окнах.")
entry("waiting_dialog", "Waiting for the same confirmation in the other window…",
      "Очікування такого самого підтвердження в іншому вікні…", "Ожидаю такое же подтверждение во втором окне…")
entry("dialog_timeout", "The matching confirmation did not appear. Mirroring is off.",
      "Відповідне підтвердження не з’явилося. Дублювання вимкнено.", "Во втором окне нет такого же подтверждения. Повтор выключен.")
entry("manual_dialog", "Handle this dialog manually. Mirroring is off.",
      "Обробіть цей діалог вручну. Дублювання вимкнено.", "Этот диалог нужно обработать вручную. Повтор выключен.")
entry("dialog_changed", "The dialog changed during the click. Mirroring is off.",
      "Діалог змінився під час натискання. Дублювання вимкнено.", "Диалог изменился во время нажатия. Повтор выключен.")
entry("enter_unknown", "The Enter button could not be identified. Click the desired button instead.",
      "Не вдалося визначити кнопку Enter. Натисніть потрібну кнопку мишею.",
      "Не удалось определить кнопку Enter. Выберите Yes или No мышью.")
entry("source_dialog_changed", "The source confirmation changed. Mirroring is off.",
      "Початкове підтвердження змінилося. Дублювання вимкнено.", "Исходное подтверждение изменилось. Повтор выключен.")
entry("confirm_mismatch", "The confirmations do not match. No button was clicked.",
      "Підтвердження не збігаються. Жодну кнопку не натиснуто.", "Подтверждения не совпадают. Ни одна кнопка не нажата.")
entry("confirm_missing", "The second confirmation did not appear. No button was clicked.",
      "Друге підтвердження не з’явилося. Жодну кнопку не натиснуто.", "Второе подтверждение не появилось. Ни одна кнопка не нажата.")
entry("button_missing", "The matching button is unavailable in the other dialog.",
      "В іншому діалозі немає відповідної доступної кнопки.", "Во втором диалоге нет такой же доступной кнопки.")
entry("confirmation_closed", "A confirmation closed before its action could be mirrored.",
      "Одне з підтверджень закрилося до дублювання дії.", "Одно из подтверждений закрылось до повтора.")
entry("mouse_error", "Mouse input error: {error}", "Помилка введення мишею: {error}")
entry("keyboard_error", "Keyboard input error: {error}", "Помилка введення з клавіатури: {error}")
entry("hook_error", "Input handling could not start: {error}", "Не вдалося запустити обробку введення: {error}")
entry("accessibility_error", "Field synchronization could not start: {error}", "Не вдалося запустити синхронізацію полів: {error}")
entry("hotkey_busy", "F{number} is used by another application. Use the helper buttons.",
      "F{number} використовується іншою програмою. Скористайтеся кнопками помічника.")


@dataclass(frozen=True)
class Message:
    key: str
    values: dict = field(default_factory=dict)


def language_code(value):
    return value if isinstance(value, str) and value in LANGUAGES else "en"


def text(language, key, **values):
    return STRINGS[key][language_code(language)].format(**values)


def render(language, message):
    if isinstance(message, Message):
        return text(language, message.key, **message.values)
    message = str(message)
    if message in BACKEND:
        return text(language, BACKEND[message])
    for prefix, key in (("Ошибка мыши: ", "mouse_error"), ("Ошибка клавиатуры: ", "keyboard_error"),
                        ("Не удалось включить перехват ввода: ", "hook_error"),
                        ("Не удалось запустить обработку полей: ", "accessibility_error")):
        if message.startswith(prefix):
            return text(language, key, error=render(language, message[len(prefix):]))
    hotkey = re.fullmatch(r"Клавиша F(\d+) занята другой программой; используйте кнопки помощника\.", message)
    return text(language, "hotkey_busy", number=hotkey[1]) if hotkey else message
