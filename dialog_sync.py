"""Match confirmation dialogs and replay only an explicit user decision."""
from __future__ import annotations

from dataclasses import dataclass
import time
import win_api as win


CHOICES = {"yes", "no", "ok", "cancel", "abort", "retry", "ignore",
           "да", "нет", "так", "ні", "ок", "отмена", "скасувати",
           "是", "否", "确定", "取消"}


def normalized(text):
    return " ".join((text or "").replace("&", "").split()).casefold()


@dataclass(frozen=True)
class Button:
    key: str
    rect: tuple[int, int, int, int]
    focused: bool = False
    default: bool = False
    enabled: bool = True

    def contains(self, point):
        x, y = point
        left, top, right, bottom = self.rect
        return left <= x < right and top <= y < bottom

    @property
    def center(self):
        a, b, c, d = self.rect
        return (a + c) // 2, (b + d) // 2


@dataclass(frozen=True)
class Confirmation:
    window: win.Window
    heading: str
    message: str
    buttons: tuple[Button, ...]

    @property
    def signature(self):
        return normalized(self.heading), normalized(self.message), tuple(sorted(button.key for button in self.buttons))

    def button(self, key):
        matches = [button for button in self.buttons if button.key == key and button.enabled]
        return matches[0] if len(matches) == 1 else None

    def at(self, point):
        return next((button for button in self.buttons if button.enabled and button.contains(point)), None)

    def enter_button(self):
        focused = [button for button in self.buttons if button.enabled and button.focused]
        if len(focused) == 1:
            return focused[0]
        defaults = [button for button in self.buttons if button.enabled and button.default]
        return defaults[0] if len(defaults) == 1 else None


class DialogSync:
    def __init__(self, uia, pair, notice, timeout=3.0):
        self.uia, self.pair, self.notice = uia, pair, notice
        self.timeout = timeout
        self.wait_started = None
        self.last_handles = ()
        self.state = "none"
        self.press = None

    def read(self, hwnd, owner):
        if not win.is_dialog_for(hwnd, owner):
            return None
        root = self.uia.root(hwnd)
        # Confirmation boxes contain a message and choices, not editable forms/file pickers.
        if any(self.uia.of_type(root, kind) for kind in (50003, 50004, 50016)):
            return None
        heading = win.title(hwnd)
        texts = [element.CurrentName for element in self.uia.of_type(root, 50020)]
        message = " ".join(text for text in texts if normalized(text) != normalized(heading))
        if not normalized(message):
            return None
        x, y, width, height = win.client_box(hwnd)
        buttons = []
        for element in self.uia.of_type(root, 50000):
            rect = element.CurrentBoundingRectangle
            center = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
            if not (x <= center[0] < x + width and y <= center[1] < y + height):
                continue  # exclude title-bar Close/Minimize, including localized caption buttons
            key = normalized(element.CurrentName)
            if key not in CHOICES:
                return None
            legacy = self.uia.pattern(element, 10018, "IUIAutomationLegacyIAccessiblePattern")
            state = int(legacy.CurrentState) if legacy else 0
            buttons.append(Button(key, (rect.left, rect.top, rect.right, rect.bottom),
                                  bool(element.CurrentHasKeyboardFocus or state & 0x4),
                                  bool(state & 0x100), bool(element.CurrentIsEnabled)))
        if not 1 <= len(buttons) <= 3 or len({button.key for button in buttons}) != len(buttons):
            return None
        return Confirmation(win.Window(hwnd, owner.pid, heading, owner.path), heading, message, tuple(buttons))

    def snapshots(self):
        handles = win.dialogs(self.pair)
        grouped = [[hwnd for hwnd in handles if win.pid_of(hwnd) == window.pid] for window in self.pair]
        if any(len(group) > 1 for group in grouped):
            raise RuntimeError("Открыто несколько диалогов. Обработайте их отдельно.")
        result = tuple(self.read(group[0], owner) if group else None for group, owner in zip(grouped, self.pair))
        if any(group and snapshot is None for group, snapshot in zip(grouped, result)):
            raise RuntimeError("Этот диалог не является простым подтверждением. Повтор выключен.")
        return tuple(handles), result

    def observe(self):
        handles, (source, target) = self.snapshots()
        if not handles:
            if self.state != "none":
                self.notice("Повтор включён: слева → направо")
            self.wait_started, self.last_handles, self.state = None, (), "none"
            return self.state
        if source and target:
            if source.signature != target.signature:
                raise RuntimeError("Текст или кнопки диалогов различаются. Повтор выключен.")
            if self.state != "paired":
                self.notice("Одинаковые подтверждения: Enter и Yes/No повторяются в обоих окнах.")
            self.wait_started, self.last_handles, self.state = None, handles, "paired"
            return self.state
        if handles != self.last_handles or self.wait_started is None:
            self.wait_started = time.monotonic()
            self.last_handles = handles
            self.notice("Ожидаю такое же подтверждение во втором окне…")
        self.state = "waiting"
        if time.monotonic() - self.wait_started >= self.timeout:
            raise RuntimeError("Во втором окне нет такого же подтверждения. Повтор выключен.")
        return self.state

    def request(self, kind, payload, allowed):
        if kind == "dialog_down":
            hwnd, point = payload
            source = self.read(hwnd, self.pair[0])
            if source is None:
                raise RuntimeError("Этот диалог нужно обработать вручную. Повтор выключен.")
            button = source.at(point)
            self.press = (source, button.key) if button else None
            return False
        if kind == "dialog_up":
            press, self.press = self.press, None
            if press is None:
                return False
            old, key = press
            hwnd, point = payload
            source = self.read(hwnd, self.pair[0])
            if source is None or source.window.hwnd != old.window.hwnd or source.signature != old.signature:
                raise RuntimeError("Диалог изменился во время нажатия. Повтор выключен.")
            button = source.at(point)
            if button is None or button.key != key:
                return False  # dragging off a button cancels a click
        elif kind == "dialog_enter":
            source = self.read(payload, self.pair[0])
            if source is None:
                raise RuntimeError("Этот диалог нужно обработать вручную. Повтор выключен.")
            button = source.enter_button()
            if button is None:
                raise RuntimeError("Не удалось определить кнопку Enter. Выберите Yes или No мышью.")
            key = button.key
        else:
            return False

        expected = source.signature
        original_hwnd = source.window.hwnd
        deadline = time.monotonic() + self.timeout
        while allowed():
            _handles, (source, target) = self.snapshots()
            if (source is None or source.window.hwnd != original_hwnd or source.signature != expected):
                raise RuntimeError("Исходное подтверждение изменилось. Повтор выключен.")
            if target:
                if target.signature != expected:
                    raise RuntimeError("Подтверждения не совпадают. Ни одна кнопка не нажата.")
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Второе подтверждение не появилось. Ни одна кнопка не нажата.")
            time.sleep(0.025)
        else:
            return False

        source_button, target_button = source.button(key), target.button(key)
        if source_button is None or target_button is None:
            raise RuntimeError("Во втором диалоге нет такой же доступной кнопки.")
        # Post complete clicks without waiting for a calibration/other operation to finish.
        # Never infer Yes: the key comes from the user's clicked/focused/default source button.
        for dialog, button in ((target, target_button), (source, source_button)):
            if not allowed():
                return False
            if not dialog.window.valid() or not win.is_visible(dialog.window.hwnd):
                raise RuntimeError("Одно из подтверждений закрылось до повтора.")
            win.mouse_message(dialog.window, win.WM_MOVE, button.center)
            win.mouse_message(dialog.window, win.WM_LDOWN, button.center, 1)
            win.mouse_message(dialog.window, win.WM_LUP, button.center, 0)
        self.wait_started = time.monotonic()
        return True
