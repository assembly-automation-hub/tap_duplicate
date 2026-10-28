"""One-way, window-bound input replication with Qt control-value synchronization."""
from __future__ import annotations

import ctypes as C
import logging
import queue
import sys
import threading
import time
import win_api as win
from dialog_sync import DialogSync

sys.coinit_flags = 0
import comtypes


class Accessibility:
    def __init__(self):
        import sys
        sys.coinit_flags = 0
        import comtypes
        from comtypes.client import CreateObject, GetModule
        self.comtypes = comtypes
        comtypes.CoInitializeEx(0)
        self.A = GetModule("UIAutomationCore.dll")
        self.client = CreateObject(self.A.CUIAutomation, interface=self.A.IUIAutomation)
        self.walker = self.client.ControlViewWalker
        self.truth = self.client.CreateTrueCondition()

    def close(self):
        self.walker = self.client = None
        self.comtypes.CoUninitialize()

    def pattern(self, element, number, interface):
        try:
            return element.GetCurrentPattern(number).QueryInterface(getattr(self.A, interface))
        except Exception:
            return None

    def root(self, hwnd):
        return self.client.ElementFromHandle(hwnd)

    def at(self, point):
        return self.client.ElementFromPoint(self.A.tagPOINT(*point))

    def of_type(self, root, control_type, scope=4):
        condition = self.client.CreatePropertyCondition(30003, control_type)
        array = root.FindAll(scope, condition)
        return [array.GetElement(i) for i in range(min(array.Length, 1000))]

    def parent(self, element):
        return self.walker.GetParentElement(element)

    def control(self, element, types):
        for _ in range(5):
            if not element:
                return None
            if element.CurrentControlType in types:
                return element
            if element.CurrentControlType == 50032:  # do not climb out of a top-level window
                return None
            element = self.parent(element)
        return None

    def counterpart(self, element, source_hwnd, target_hwnd):
        source_root, target = self.root(source_hwnd), self.root(target_hwnd)
        path = []
        current = element
        for _ in range(32):
            if self.client.CompareElements(current, source_root):
                break
            parent = self.parent(current)
            if not parent:
                return None
            control_type = current.CurrentControlType
            siblings = self.of_type(parent, control_type, 2)
            index = next((i for i, sibling in enumerate(siblings)
                          if self.client.CompareElements(sibling, current)), None)
            if index is None:
                return None
            path.append((control_type, current.CurrentAutomationId or "", current.CurrentName or "", index))
            current = parent
        else:
            return None
        for control_type, identifier, name, index in reversed(path):
            candidates = self.of_type(target, control_type, 2)
            exact = [e for e in candidates if identifier and e.CurrentAutomationId == identifier]
            named = [e for e in candidates if name and e.CurrentName == name]
            if len(exact) == 1:
                target = exact[0]
            elif len(named) == 1:
                target = named[0]
            elif index < len(candidates):
                target = candidates[index]
            else:
                return None
        return target

    def text_value(self, element):
        value = self.pattern(element, 10002, "IUIAutomationValuePattern")
        if value:
            return value.CurrentValue
        legacy = self.pattern(element, 10018, "IUIAutomationLegacyIAccessiblePattern")
        return legacy.CurrentValue if legacy else None

    def set_text(self, source, target):
        if source.CurrentIsPassword or target.CurrentIsPassword:
            return False
        for element in (source, target):
            value_pattern = self.pattern(element, 10002, "IUIAutomationValuePattern")
            if value_pattern and value_pattern.CurrentIsReadOnly:
                return True  # never copy per-instance output paths or other read-only information
        value = self.text_value(source)
        if value is None or self.text_value(target) == value:
            return True
        pattern = self.pattern(target, 10002, "IUIAutomationValuePattern")
        if pattern and not pattern.CurrentIsReadOnly:
            pattern.SetValue(value)
            return True
        legacy = self.pattern(target, 10018, "IUIAutomationLegacyIAccessiblePattern")
        if legacy:
            legacy.SetValue(value)
            return True
        return False

    def selection(self, combo):
        items = self.of_type(combo, 50007)
        value = self.text_value(combo)
        if value is not None:
            for i, item in enumerate(items):
                if item.CurrentName == value:
                    return i, value, items
        for i, item in enumerate(items):
            pattern = self.pattern(item, 10010, "IUIAutomationSelectionItemPattern")
            if pattern and pattern.CurrentIsSelected:
                return i, item.CurrentName, items
        return None, value, items

    def set_selection(self, source, target, source_window, target_window, allowed):
        index, text, _items = self.selection(source)
        target_index, target_text, target_items = self.selection(target)
        if text is not None and text == target_text:
            return True
        matches = [item for item in target_items if text is not None and item.CurrentName == text]
        if len(matches) == 1:
            chosen = matches[0]
        elif text not in (None, ""):
            raise RuntimeError("В правом списке нет выбранного слева значения. Повтор остановлен.")
        elif index is not None and index < len(target_items):
            chosen = target_items[index]
        else:
            return False
        pattern = self.pattern(chosen, 10010, "IUIAutomationSelectionItemPattern")
        if pattern:
            pattern.Select()
        else:
            legacy = self.pattern(chosen, 10018, "IUIAutomationLegacyIAccessiblePattern")
            if not legacy:
                return False
            legacy.Select(2)
        if self.text_value(target) == text:
            return True
        # Qt 5's SelectionItem.Select only selects the hidden view row; it does not
        # activate QComboBox's value. Commit through the target's own popup after the
        # source popup has closed, so the two popup mouse grabs never compete.
        expand = self.pattern(target, 10005, "IUIAutomationExpandCollapsePattern")
        opener = self.pattern(target, 10018, "IUIAutomationLegacyIAccessiblePattern")
        if not (expand or opener) or not allowed():
            return False
        previous_foreground = int(win.foreground() or 0)
        if expand:
            expand.Expand()
        else:
            opener.DoDefaultAction()
        popup = None
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and allowed():
            visible = []

            @win.ENUMPROC
            def visit(hwnd, _):
                if (win.is_visible(hwnd) and win.pid_of(hwnd) == target_window.pid
                        and "Popup" in win.class_name(hwnd)):
                    visible.append(int(hwnd))
                return True

            win.enum_windows(visit, 0)
            if visible:
                popup = visible[0]
                break
            time.sleep(0.01)
        try:
            if not popup or not allowed():
                return False
            chosen_index = next(i for i, item in enumerate(target_items)
                                if self.client.CompareElements(item, chosen))
            if not chosen.CurrentIsEnabled:
                raise RuntimeError("Выбранный пункт недоступен в правом окне.")
            scroller = self.pattern(chosen, 10017, "IUIAutomationScrollItemPattern")
            if scroller:
                scroller.ScrollIntoView()
            if chosen.CurrentIsOffscreen:
                enabled_index = sum(bool(item.CurrentIsEnabled) for item in target_items[:chosen_index])
                for key in [0x24] + [0x28] * enabled_index:
                    if not allowed():
                        return False
                    win.post(popup, win.WM_KEYDOWN, key, 1)
                    win.post(popup, win.WM_KEYUP, key, 0xC0000001)
                time.sleep(0.03)
            rect = chosen.CurrentBoundingRectangle
            point = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
            if chosen.CurrentIsOffscreen or rect.right <= rect.left or not allowed():
                return False
            popup_window = win.Window(popup, target_window.pid, "", target_window.path)
            win.mouse_message(popup_window, win.WM_MOVE, point)
            win.mouse_message(popup_window, win.WM_LDOWN, point, 1)
            win.mouse_message(popup_window, win.WM_LUP, point, 0)
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline and allowed():
                if self.text_value(target) == text:
                    return True
                time.sleep(0.01)
            return self.text_value(target) == text
        finally:
            if popup and win.is_window(popup) and win.is_visible(popup):
                win.post(popup, win.WM_KEYDOWN, 0x1B, 1)
                win.post(popup, win.WM_KEYUP, 0x1B, 0xC0000001)
            current_foreground = int(win.foreground() or 0)
            if (previous_foreground == source_window.hwnd and current_foreground
                    and win.pid_of(current_foreground) == target_window.pid):
                self.root(source_window.hwnd).SetFocus()

    def sync_range(self, source, target):
        a = self.pattern(source, 10003, "IUIAutomationRangeValuePattern")
        b = self.pattern(target, 10003, "IUIAutomationRangeValuePattern")
        if not a or not b or b.CurrentIsReadOnly:
            return
        value = a.CurrentValue
        if value < b.CurrentMinimum or value > b.CurrentMaximum:
            raise RuntimeError("Диапазоны элементов управления различаются. Повтор остановлен.")
        if abs(b.CurrentValue - value) > 0.00001:
            b.SetValue(value)
        elif source.CurrentControlType == 50016 and self.text_value(source) != self.text_value(target):
            self.set_text(source, target)


class Engine:
    def __init__(self, notices):
        self.notices = notices
        self.active = threading.Event()
        self.closed = threading.Event()
        self.ready = threading.Event()
        self.events = queue.Queue(maxsize=1500)
        self.pair = None
        self.epoch = 0
        self.buttons = 0
        self.sent_buttons = 0
        self.keyboard = self.wheel = True
        self.count = 0
        self.last_move = 0.0
        self._dialog_mouse = None
        self._dialog_return_held = False
        self.hooks = win.Hooks(self.on_mouse, self.on_key, self.hotkey, self.notice)
        self.worker = threading.Thread(target=self.run, name="window-replay", daemon=True)
        self.worker.start()
        self.hooks.start()

    def notice(self, text):
        self.notices.put(("notice", text))

    def hotkey(self, identifier):
        if identifier == 2:
            self.pause("Остановлено клавишей F9")
        else:
            self.notices.put(("toggle", None))

    def start(self, pair, keyboard=True, wheel=True):
        if not self.ready.is_set() or not self.hooks.ready.is_set() or not self.hooks.is_alive():
            raise RuntimeError("Помощник ещё запускается. Подождите несколько секунд.")
        if len(pair) != 2 or pair[0].hwnd == pair[1].hwnd or pair[0].pid == pair[1].pid:
            raise ValueError("Выберите два разных экземпляра программы.")
        if not all(window.valid() and not win.is_iconic(window.hwnd) for window in pair):
            raise ValueError("Оба окна должны быть открыты и не свёрнуты.")
        if not win.same_size(pair):
            raise ValueError("Размеры окон различаются. Нажмите «Расположить рядом».")
        self.pause("")
        self.pair = tuple(pair)
        self.keyboard, self.wheel = keyboard, wheel
        self.count = 0
        self.active.set()
        self.notices.put(("state", "Повтор включён: слева → направо"))

    def pause(self, reason="Повтор выключен"):
        self.active.clear()
        self.epoch += 1
        buttons = self.buttons | self.sent_buttons
        self.buttons = self.sent_buttons = 0
        if buttons and self.pair and self.pair[1].valid():
            # Cancel a partial drag without clicking a button on emergency stop.
            try:
                win.post(self.pair[1].hwnd, 0x1F)
                for message, flag in win.UP.items():
                    if buttons & flag:
                        win.post(self.pair[1].hwnd, message, 0, win.packed_point(-1000, -1000))
            except OSError:
                pass
        if reason:
            self.notices.put(("state", reason))

    def enqueue(self, kind, payload):
        try:
            self.events.put_nowait((self.epoch, kind, payload))
        except queue.Full:
            self.pause("События не успевают обрабатываться. Повтор остановлен.")

    def on_mouse(self, message, x, y, data, timestamp):
        captured = getattr(self, "_dialog_mouse", None)
        if message == win.WM_LUP and captured:
            self._dialog_mouse = None
            hwnd, epoch = captured
            if self.active.is_set() and epoch == self.epoch:
                self.enqueue("dialog_up", (hwnd, (x, y)))
            return True
        if not self.active.is_set() or not self.pair:
            return
        source = self.pair[0]
        under = win.root_at(x, y)
        if message in win.DOWN and (under == self.pair[1].hwnd or win.is_dialog_for(under, self.pair[1])):
            self.pause("Вы нажали в правом окне. Повтор выключен, чтобы окна не рассинхронизировались.")
            return
        if message == win.WM_LDOWN and win.is_dialog_for(under, source):
            sx, sy, width, height = win.client_box(under)
            if sx <= x < sx + width and sy <= y < sy + height:
                self._dialog_mouse = under, self.epoch
                self.enqueue("dialog_down", (under, (x, y)))
                return True
        inside = win.source_surface(under, source)
        if under == source.hwnd:
            sx, sy, width, height = win.client_box(source.hwnd)
            inside = inside and sx <= x < sx + width and sy <= y < sy + height
        if message in win.DOWN:
            if not inside:
                return
            self.buttons |= win.DOWN[message]
        elif message in win.UP:
            if not self.buttons & win.UP[message]:
                return
            self.buttons &= ~win.UP[message]
        elif message == win.WM_MOVE:
            if not self.buttons or time.monotonic() - self.last_move < 0.012:
                return
            self.last_move = time.monotonic()
        elif message in (win.WM_WHEEL, win.WM_HWHEEL):
            if not inside or not self.wheel:
                return
        else:
            return
        self.enqueue("mouse", (message, x, y, data, timestamp, self.buttons, under))

    def on_key(self, message, vk, scan, flags):
        if vk == 13 and getattr(self, "_dialog_return_held", False):
            if message in (win.WM_KEYUP, win.WM_SYSKEYUP):
                self._dialog_return_held = False
            return True
        if not self.active.is_set() or not self.pair:
            return
        if vk in (0x77, 0x78, 0x5B, 0x5C):
            return
        active = int(win.foreground() or 0)
        if vk == 13 and message == win.WM_KEYDOWN and win.is_dialog_for(active, self.pair[0]):
            self._dialog_return_held = True
            self.enqueue("dialog_enter", active)
            return True
        if not self.keyboard:
            return
        if not win.source_surface(active, self.pair[0]):
            return
        if message in (win.WM_KEYDOWN, win.WM_KEYUP, win.WM_SYSKEYDOWN, win.WM_SYSKEYUP):
            self.enqueue("key", (message, vk, scan, flags))

    def allowed(self, epoch):
        return (self.active.is_set() and epoch == self.epoch and self.pair
                and all(window.valid() for window in self.pair))

    def check(self):
        if not all(window.valid() for window in self.pair):
            raise RuntimeError("Одно из выбранных окон закрыто. Выберите окна заново.")
        if any(win.is_iconic(window.hwnd) for window in self.pair):
            raise RuntimeError("Одно из окон свёрнуто. Повтор остановлен.")
        if not win.same_size(self.pair):
            raise RuntimeError("Размер окна изменился. Выровняйте окна и включите повтор заново.")

    def combo_popup(self):
        pid = self.pair[0].pid
        found = []

        @win.ENUMPROC
        def visit(hwnd, _):
            if win.is_visible(hwnd) and win.pid_of(hwnd) == pid and "Popup" in win.class_name(hwnd):
                found.append(hwnd)
            return True

        win.enum_windows(visit, 0)
        return bool(found)

    def describe(self, point):
        element = self.uia.at(point)
        return self.uia.control(element, {50003, 50004, 50015, 50016, 50014})

    def context(self, element):
        target = self.uia.counterpart(element, self.pair[0].hwnd, self.pair[1].hwnd)
        return (element, target) if target else None

    def run(self):
        try:
            self.uia = Accessibility()
        except Exception as error:
            logging.exception("Accessibility initialization failed")
            self.notice(f"Не удалось запустить обработку полей: {error}")
            return
        self.ready.set()
        self.notices.put(("ready", None))
        worker_epoch = -1
        edit = combo = slider = None
        suppress = False
        edit_due = combo_due = range_due = 0.0
        last_check = 0.0
        previous_down = None
        dialog_sync = None
        try:
            while not self.closed.is_set():
                if worker_epoch != self.epoch:
                    worker_epoch = self.epoch
                    edit = combo = slider = None
                    suppress = False
                    edit_due = combo_due = range_due = 0.0
                    previous_down = None
                    dialog_sync = None
                try:
                    epoch, kind, data = self.events.get(timeout=0.025)
                except queue.Empty:
                    epoch, kind, data = self.epoch, "tick", None
                if not self.allowed(epoch):
                    continue
                now = time.monotonic()
                try:
                    if dialog_sync is None or dialog_sync.pair != self.pair:
                        dialog_sync = DialogSync(self.uia, self.pair, self.notice)
                    if now - last_check >= 0.15:
                        self.check()
                        last_check = now
                    if kind.startswith("dialog_"):
                        if dialog_sync.request(kind, data, lambda: self.active.is_set() and epoch == self.epoch):
                            self.count += 1
                        edit = combo = slider = None
                        edit_due = combo_due = range_due = 0.0
                        continue
                    if kind == "mouse":
                        message, x, y, mouse_data, timestamp, buttons, under = data
                        if message in win.DOWN:
                            if under != self.pair[0].hwnd and combo:
                                suppress = True
                            else:
                                try:
                                    element = self.describe((x, y))
                                    control_type = element.CurrentControlType if element else 0
                                    context = self.context(element) if element else None
                                except Exception:
                                    control_type, context = 0, None
                                edit = context if control_type == 50004 else None
                                slider = context if control_type in (50014, 50015, 50016) else None
                                if control_type == 50003:
                                    if not context:
                                        raise RuntimeError("Не удалось найти такой же список справа. Повтор остановлен.")
                                    combo, suppress, combo_due = context, True, now + 0.08
                                else:
                                    combo, combo_due = None, 0.0
                                    suppress = False
                        if suppress and message in (win.WM_LDOWN, win.WM_LUP, win.WM_MOVE):
                            combo_due = now + 0.08
                            if message == win.WM_LUP:
                                suppress = False
                            continue
                        if message in (win.WM_WHEEL, win.WM_HWHEEL):
                            if under != self.pair[0].hwnd and combo:
                                combo_due = now + 0.08
                                continue
                            try:
                                element = self.describe((x, y))
                                if element and element.CurrentControlType == 50003:
                                    combo, combo_due = self.context(element), now + 0.08
                                    continue
                            except Exception:
                                pass
                        target_point = win.mapped_point((x, y), win.client_box(self.pair[0].hwnd),
                                                        win.client_box(self.pair[1].hwnd))
                        out_message = message
                        if message in win.DOWN:
                            if (previous_down and previous_down[0] == message
                                    and 0 <= timestamp - previous_down[3] <= win.get_double_click_time()
                                    and abs(x - previous_down[1]) <= win.get_metric(36)
                                    and abs(y - previous_down[2]) <= win.get_metric(37)):
                                out_message = win.DOUBLE[message]
                                previous_down = None
                            else:
                                previous_down = (message, x, y, timestamp)
                        if not self.allowed(epoch):
                            continue
                        modifiers = (4 if win.get_async_key(0x10) & 0x8000 else 0) | (8 if win.get_async_key(0x11) & 0x8000 else 0)
                        wheel = C.c_short((mouse_data >> 16) & 0xFFFF).value
                        win.mouse_message(self.pair[1], out_message, target_point, buttons | modifiers, wheel)
                        if message in win.DOWN:
                            self.sent_buttons |= win.DOWN[message]
                        elif message in win.UP:
                            self.sent_buttons &= ~win.UP[message]
                        if message in win.UP:
                            self.count += 1
                            edit_due, range_due = now + 0.05, now + 0.05
                        if message in (win.WM_WHEEL, win.WM_HWHEEL):
                            range_due = now + 0.08
                    elif kind == "key":
                        message, vk, scan, flags = data
                        try:
                            focused = self.uia.client.GetFocusedElement()
                            control = self.uia.control(focused, {50003, 50004, 50014, 50015, 50016})
                            if control and control.CurrentProcessId == self.pair[0].pid:
                                if control.CurrentControlType == 50004:
                                    edit = self.context(control)
                                    combo, combo_due = None, 0.0
                                elif control.CurrentControlType == 50003:
                                    combo = self.context(control)
                                    edit, edit_due = None, 0.0
                                else:
                                    slider = self.context(control)
                                    range_due = now + 0.05
                                    edit = combo = None
                                    edit_due = combo_due = 0.0
                        except Exception:
                            pass
                        if combo:
                            combo_due = now + 0.06
                        if edit:
                            edit_due = now + 0.04
                        # Text is copied as the field's resulting value, including Ctrl+A/paste/layouts.
                        # Navigation/commit keys also reach the target's own Qt focus widget.
                        if not combo and vk in (8, 9, 13, 27, 32, 33, 34, 35, 36, 37, 38, 39, 40, 46):
                            if not edit or vk in (9, 13):
                                lp = 1 | (scan << 16) | ((flags & 1) << 24)
                                if message in (win.WM_KEYUP, win.WM_SYSKEYUP):
                                    lp |= 0xC0000000
                                win.post(self.pair[1].hwnd, message, vk, lp)
                    if dialog_sync.observe() != "none":
                        edit = combo = slider = None
                        edit_due = combo_due = range_due = 0.0
                        continue
                    now = time.monotonic()
                    if edit and edit_due and now >= edit_due and self.allowed(epoch):
                        if not self.uia.set_text(*edit):
                            raise RuntimeError("Это поле не поддерживает повтор ввода. Повтор остановлен.")
                        edit_due = 0.0
                    if combo and combo_due and now >= combo_due and self.allowed(epoch):
                        if self.combo_popup():
                            combo_due = now + 0.08
                        else:
                            if not self.uia.set_selection(*combo, *self.pair, lambda: self.allowed(epoch)):
                                raise RuntimeError("Этот список не поддерживает повтор выбора. Повтор остановлен.")
                            combo_due = now + 0.12  # also track keyboard changes while the combo remains focused
                    if range_due and now >= range_due and self.allowed(epoch):
                        if slider:
                            self.uia.sync_range(*slider)
                        if self.wheel:
                            left = self.uia.of_type(self.uia.root(self.pair[0].hwnd), 50014)
                            right = self.uia.of_type(self.uia.root(self.pair[1].hwnd), 50014)
                            if len(left) == len(right):
                                for source, target in zip(left, right):
                                    self.uia.sync_range(source, target)
                        range_due = 0.0
                except Exception as error:
                    logging.warning("Replay paused: %s", type(error).__name__)
                    self.pause(str(error))
        finally:
            self.uia.close()

    def stop(self):
        self.pause("")
        self.closed.set()
        self.hooks.stop()
        if threading.current_thread() is not self.worker:
            self.worker.join(timeout=1.0)
