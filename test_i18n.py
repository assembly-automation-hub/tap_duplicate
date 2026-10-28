"""Language coverage, live switching and saved preferences without input hooks."""
import ast
import json
from pathlib import Path
import re
from string import Formatter
import tempfile
import threading
import tkinter as tk
import unittest
from unittest.mock import patch

import i18n
import tap_duplicate as gui


class Translations(unittest.TestCase):
    def test_default_is_english_even_with_invalid_preferences(self):
        for value in (None, "", "ru", 0, [], {}):
            self.assertEqual(i18n.language_code(value), "en")
        self.assertEqual(i18n.language_code("uk"), "uk")

    def test_languages_have_matching_format_fields_and_no_old_brand(self):
        for key, translations in i18n.STRINGS.items():
            with self.subTest(key=key):
                self.assertEqual(set(translations), {"en", "uk"})
                fields = [{name for _, name, _, _ in Formatter().parse(value) if name is not None}
                          for value in translations.values()]
                self.assertEqual(fields[0], fields[1])
                self.assertTrue(all("thermal" not in value.casefold() for value in translations.values()))

    def test_every_backend_message_is_translated(self):
        for filename in ("automation.py", "win_api.py", "dialog_sync.py", "tap_duplicate.py"):
            source = ast.parse(Path(__file__).with_name(filename).read_text(encoding="utf-8"))
            for node in ast.walk(source):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    message = node.value
                    # Short dialog button aliases and dynamic error prefixes are not full messages.
                    if re.search("[А-Яа-яЁё]", message) and len(message) > 20 and not message.endswith(": "):
                        if message.startswith("Клавиша F") or message.startswith(" занята другой программой"):
                            continue
                        with self.subTest(filename=filename, message=message):
                            self.assertNotEqual(i18n.render("en", message), message)
                            self.assertNotEqual(i18n.render("uk", message), message)

    def test_dynamic_errors_are_rendered_in_selected_language(self):
        self.assertEqual(i18n.render("en", "Ошибка мыши: Окно недоступно"),
                         "Mouse input error: The window is unavailable.")
        self.assertEqual(i18n.render("uk", "Клавиша F8 занята другой программой; используйте кнопки помощника."),
                         "F8 використовується іншою програмою. Скористайтеся кнопками помічника.")


class FakeEngine:
    def __init__(self, _notices):
        self.active = threading.Event()
        self.count = 0

    def pause(self, _reason=""):
        self.active.clear()

    def stop(self):
        self.pause()


class LanguagePreferences(unittest.TestCase):
    def test_live_switch_persists_and_retranslates_current_status(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(gui, "SETTINGS", Path(folder) / "settings.json"), \
             patch.object(gui, "Engine", FakeEngine), patch.object(gui.win, "windows", return_value=[]):
            root = tk.Tk()
            root.withdraw()
            app = gui.Application(root)
            self.assertEqual(root.title(), "Tap Duplicator")
            self.assertEqual(app.language.get(), "English")
            app.show_message("Повтор выключен")
            app.engine.active.set()
            app.engine.count = 7
            app.language.set("Українська")
            app.change_language()
            self.assertEqual(root.title(), "Тап дублікатор")
            self.assertEqual(app.heading.cget("text"), "Тап дублікатор")
            self.assertEqual(app.info.cget("text"), "Дублювання вимкнено")
            self.assertEqual(app.start_button.cget("text"), "Пауза · F8")
            self.assertEqual(app.count.cget("text"), "Натискань: 7")
            self.assertTrue(app.engine.active.is_set())
            self.assertEqual(json.loads(gui.SETTINGS.read_text())["language"], "uk")
            app.close()
            root = tk.Tk()
            root.withdraw()
            app = gui.Application(root)
            self.assertEqual(root.title(), "Тап дублікатор")
            self.assertEqual(app.language.get(), "Українська")
            app.language.set("English")
            app.change_language()
            self.assertEqual(app.info.cget("text"), i18n.text("en", "windows_found", count=0))
            app.close()

    def test_invalid_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(gui, "SETTINGS", Path(folder) / "settings.json"):
            for content in ("[]", "null", "invalid JSON"):
                gui.SETTINGS.write_text(content)
                self.assertEqual(gui.load_settings(), {})


if __name__ == "__main__":
    unittest.main()
