"""Tap Duplicator — a local, one-way helper for two selected windows."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import queue
import sys
import tkinter as tk
from tkinter import ttk

import win_api as win
from automation import Engine
from i18n import LANGUAGES, Message, language_code, text, render


APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SETTINGS = APP_DIR / "settings.json"


def load_settings():
    try:
        saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


class Application:
    def __init__(self, root):
        self.root = root
        self.notices = queue.Queue()
        self.engine = Engine(self.notices)
        self.available = []
        self.closed = False
        self.ready = False
        saved = load_settings()
        self.language_code = language_code(saved.get("language"))
        self.language = tk.StringVar(value=LANGUAGES[self.language_code])
        self.translated_widgets = []
        self.last_message = Message("starting")
        self.root.title(self.tr("app_name"))
        self.root.geometry("630x430")
        self.root.configure(bg="white")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        icon = APP_DIR / "tap_duplicate.ico"
        if icon.exists():
            self.root.iconbitmap(str(icon))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", font=("Segoe UI", 10), padding=4,
                        fieldbackground="white", background="#eeeeee", foreground="#333333")
        style.map("TCombobox", fieldbackground=[("readonly", "white")],
                  selectbackground=[("readonly", "#eeeeee")],
                  selectforeground=[("readonly", "#333333")])
        body = tk.Frame(root, bg="white", padx=16, pady=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        header = tk.Frame(body, bg="white")
        header.grid(row=0, column=0, sticky="ew", pady=(2, 16))
        header.columnconfigure(0, weight=1)
        self.heading = self.translated(tk.Label(header, bg="white", fg="#333333",
                                                font=("Segoe UI", 18)), "app_name")
        self.heading.grid(row=0, column=0, sticky="w")
        self.translated(tk.Label(header, bg="white", fg="#777777", font=("Segoe UI", 9)),
                        "language").grid(row=0, column=1, padx=(12, 7))
        self.language_selector = ttk.Combobox(header, textvariable=self.language, state="readonly",
                                              values=list(LANGUAGES.values()), width=12)
        self.language_selector.grid(row=0, column=2, sticky="e")
        self.language_selector.bind("<<ComboboxSelected>>", self.change_language)
        selectors = self.translated(tk.LabelFrame(body, bg="white", fg="#555555",
                                  font=("Segoe UI", 10), padx=10, pady=9, bd=1, relief="solid"), "windows")
        selectors.grid(row=1, column=0, sticky="ew")
        selectors.columnconfigure(1, weight=1)
        self.translated(tk.Label(selectors, bg="white", fg="#444444", font=("Segoe UI", 10)),
                        "left").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.source = ttk.Combobox(selectors, state="readonly", width=38)
        self.source.grid(row=0, column=1, sticky="ew", pady=(0, 9))
        self.translated(tk.Label(selectors, bg="white", fg="#444444", font=("Segoe UI", 10)),
                        "right").grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.target = ttk.Combobox(selectors, state="readonly", width=38)
        self.target.grid(row=1, column=1, sticky="ew")
        self.source.bind("<<ComboboxSelected>>", self.selection_changed)
        self.target.bind("<<ComboboxSelected>>", self.selection_changed)

        def flat_button(parent, text, command):
            return tk.Button(parent, text=text, command=command, bg="white", fg="#333333",
                             activebackground="#eeeeee", activeforeground="#222222",
                             relief="solid", bd=1, highlightthickness=0, cursor="hand2",
                             font=("Segoe UI", 10), padx=10, pady=7)

        tools = tk.Frame(body, bg="white")
        tools.grid(row=2, column=0, sticky="ew", pady=(10, 8))
        tools.columnconfigure((0, 1), weight=1)
        self.refresh_button = self.translated(flat_button(tools, "", self.refresh), "refresh")
        self.refresh_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.arrange_button = self.translated(flat_button(tools, "", self.arrange), "arrange")
        self.arrange_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.keyboard = tk.BooleanVar(value=bool(saved.get("keyboard", True)))
        self.wheel = tk.BooleanVar(value=bool(saved.get("wheel", True)))
        options = tk.Frame(body, bg="white")
        options.grid(row=3, column=0, sticky="w", pady=(0, 8))
        for key, variable in (("typing", self.keyboard), ("scroll", self.wheel)):
            self.translated(tk.Checkbutton(options, variable=variable, command=self.selection_changed,
                           bg="white", fg="#555555", activebackground="white", selectcolor="white",
                           font=("Segoe UI", 9), bd=0), key).pack(side="left", padx=(0, 18))
        actions = tk.Frame(body, bg="white")
        actions.grid(row=4, column=0, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        self.start_button = flat_button(actions, self.tr("start"), self.toggle)
        self.start_button.configure(state="disabled")
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.translated(flat_button(actions, "", lambda: self.engine.pause()), "stop").grid(
            row=0, column=1, sticky="ew", padx=(5, 0))
        footer = tk.Frame(body, bg="white")
        footer.grid(row=5, column=0, sticky="ew", pady=(12, 4))
        footer.columnconfigure(0, weight=1)
        self.status = tk.Label(footer, text=self.tr("status_off"), bg="white", fg="#666666", font=("Segoe UI", 10))
        self.status.grid(row=0, column=0, sticky="w")
        self.count = tk.Label(footer, text=self.tr("counter", count=0), bg="white", fg="#888888", font=("Segoe UI", 9))
        self.count.grid(row=0, column=1, sticky="e")
        self.info = tk.Label(body, text=render(self.language_code, self.last_message), bg="white", fg="#777777",
                             font=("Segoe UI", 9), wraplength=560, height=3, anchor="nw", justify="left")
        self.info.grid(row=6, column=0, sticky="ew")
        self.root.bind("<Configure>", lambda event: self.info.configure(wraplength=max(300, self.root.winfo_width() - 40)))
        self.root.update_idletasks()
        required = max(405, body.winfo_reqheight())
        self.root.minsize(560, required)
        self.root.geometry(f"630x{required}")
        self.refresh()
        self.root.after(100, self.poll)

    def tr(self, key, **values):
        return text(self.language_code, key, **values)

    def translated(self, widget, key):
        self.translated_widgets.append((widget, key))
        widget.configure(text=self.tr(key))
        return widget

    def change_language(self, _event=None):
        self.language_code = next((code for code, label in LANGUAGES.items()
                                   if label == self.language.get()), "en")
        self.root.title(self.tr("app_name"))
        for widget, key in self.translated_widgets:
            widget.configure(text=self.tr(key))
        self.show_message(self.last_message)
        self.update_status()
        self.save_settings()

    def show_message(self, message):
        self.last_message = message
        self.info.configure(text=render(self.language_code, message))

    def save_settings(self):
        try:
            SETTINGS.write_text(json.dumps({"keyboard": self.keyboard.get(), "wheel": self.wheel.get(),
                                            "language": self.language_code}, indent=2), encoding="utf-8")
        except OSError:
            pass

    def selection_changed(self, _event=None):
        if self.engine.active.is_set():
            self.engine.pause("Выбор или параметры изменились. Повтор выключен.")

    def refresh(self):
        self.engine.pause("")
        previous = [self.available[combo.current()].hwnd if 0 <= combo.current() < len(self.available) else None
                    for combo in (self.source, self.target)]
        self.available = win.windows()
        values = [window.label for window in self.available]
        for index, combo in enumerate((self.source, self.target)):
            combo["values"] = values
            position = next((i for i, window in enumerate(self.available) if window.hwnd == previous[index]), index)
            if position < len(values):
                combo.current(position)
            else:
                combo.set("")
        if len(values) < 2:
            self.last_message = Message("windows_found", {"count": len(values)})
        else:
            self.last_message = Message("ready")
        self.show_message(self.last_message)
        self.update_status()

    def pair(self):
        indexes = self.source.current(), self.target.current()
        if any(index < 0 or index >= len(self.available) for index in indexes):
            raise ValueError("Сначала откройте и выберите два окна программы.")
        pair = tuple(self.available[index] for index in indexes)
        if pair[0].hwnd == pair[1].hwnd or pair[0].pid == pair[1].pid:
            raise ValueError("Источник и получатель должны быть разными процессами.")
        return pair

    def arrange(self):
        self.engine.pause("")
        try:
            win.arrange(self.pair())
            values = [window.label for window in self.available]
            self.source["values"] = self.target["values"] = values
            self.show_message(Message("arranged"))
            self.update_status()
        except Exception as error:
            self.error(error)

    def toggle(self):
        if self.engine.active.is_set():
            self.engine.pause()
            return
        try:
            self.engine.start(self.pair(), self.keyboard.get(), self.wheel.get())
        except Exception as error:
            self.error(error)

    def error(self, error):
        self.engine.pause("")
        self.show_message(str(error))
        self.update_status()

    def update_status(self):
        enabled = self.engine.active.is_set()
        self.status.configure(text=self.tr("status_on" if enabled else "status_off"),
                              bg="white", fg="#217a40" if enabled else "#666666")
        self.start_button.configure(text=self.tr("pause" if enabled else "start"))
        self.count.configure(text=self.tr("counter", count=self.engine.count))

    def poll(self):
        if self.closed:
            return
        for _ in range(100):
            try:
                kind, value = self.notices.get_nowait()
            except queue.Empty:
                break
            if kind == "toggle":
                self.toggle()
            elif kind == "ready":
                self.ready = True
                self.start_button.configure(state="normal")
                self.show_message(self.last_message)
            else:
                self.show_message(value)
        self.update_status()
        self.root.after(100, self.poll)

    def close(self):
        self.closed = True
        self.engine.stop()
        self.save_settings()
        self.root.destroy()


def main():
    win.dpi_awareness()
    mutex = win.api(win.K, "CreateMutexW", win.W.HANDLE, win.C.c_void_p, win.W.BOOL, win.W.LPCWSTR)(
        None, False, "Local\\TapDuplicator_4198C5ED")
    if not mutex:
        raise win.C.WinError(win.C.get_last_error())
    if win.C.get_last_error() == 183:
        language = language_code(load_settings().get("language"))
        win.api(win.U, "MessageBoxW", win.C.c_int, win.W.HWND, win.W.LPCWSTR, win.W.LPCWSTR, win.W.UINT)(
            None, text(language, "already_running"), text(language, "app_name"), 0x40)
        win.close_handle(mutex)
        return
    handler = RotatingFileHandler(APP_DIR / "diagnostics.log", maxBytes=250_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.WARNING)
    root = tk.Tk()
    app = Application(root)
    try:
        root.mainloop()
    except Exception:
        logging.exception("Application error")
        raise
    finally:
        app.engine.stop()
        win.close_handle(mutex)


if __name__ == "__main__":
    main()
