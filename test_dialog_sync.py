"""Confirmation matching, decision preservation and input-interception regression tests."""
import queue
import threading
import unittest
from unittest.mock import Mock, patch

import win_api as win
from automation import Engine
from dialog_sync import Button, Confirmation, DialogSync


def confirmation(hwnd, pid, message="Test operation. Continue?", focus="no"):
    return Confirmation(win.Window(hwnd, pid, "Confirmation", "test"), "Confirmation", message, (
        Button("yes", (10, 10, 30, 30), focused=focus == "yes"),
        Button("no", (40, 10, 60, 30), focused=focus == "no", default=True),
    ))


class DialogDecisions(unittest.TestCase):
    def coordinator(self):
        pair = win.Window(100, 1, "Example App", "a"), win.Window(200, 2, "Example App", "b")
        sync = DialogSync(Mock(), pair, Mock(), timeout=0)
        self.source, self.target = confirmation(301, 1), confirmation(401, 2)
        sync.read = Mock(return_value=self.source)
        sync.snapshots = Mock(return_value=((301, 401), (self.source, self.target)))
        return sync

    def test_focus_no_is_preserved_on_enter(self):
        sync = self.coordinator()
        with patch.object(win.Window, "valid", return_value=True), patch.object(win, "is_visible", return_value=True), patch.object(win, "mouse_message") as mouse:
            self.assertTrue(sync.request("dialog_enter", 301, lambda: True))
        clicks = [call.args for call in mouse.call_args_list if call.args[1] == win.WM_LUP]
        self.assertEqual([args[2] for args in clicks], [(50, 20), (50, 20)])

    def test_focus_overrides_default(self):
        source = confirmation(301, 1, focus="yes")
        self.assertEqual(source.enter_button().key, "yes")

    def test_enter_without_known_focus_or_default_does_not_guess_yes(self):
        source = Confirmation(win.Window(301, 1, "test", "test"), "test", "message", (
            Button("yes", (0, 0, 10, 10)), Button("no", (20, 0, 30, 10))))
        self.assertIsNone(source.enter_button())

    def test_mismatched_message_never_clicks(self):
        sync = self.coordinator()
        sync.snapshots.return_value = (301, 401), (self.source, confirmation(401, 2, "Different operation"))
        with patch.object(win, "mouse_message") as mouse, self.assertRaises(RuntimeError):
            sync.request("dialog_enter", 301, lambda: True)
        mouse.assert_not_called()

    def test_missing_counterpart_never_clicks(self):
        sync = self.coordinator()
        sync.snapshots.return_value = (301,), (self.source, None)
        with patch.object(win, "mouse_message") as mouse, self.assertRaises(RuntimeError):
            sync.request("dialog_enter", 301, lambda: True)
        mouse.assert_not_called()

    def test_stop_cancels_pending_confirmation(self):
        sync = self.coordinator()
        with patch.object(win, "mouse_message") as mouse:
            self.assertFalse(sync.request("dialog_enter", 301, lambda: False))
        mouse.assert_not_called()

    def test_clicked_yes_is_repeated_in_both_dialogs(self):
        sync = self.coordinator()
        self.assertFalse(sync.request("dialog_down", (301, (20, 20)), lambda: True))
        with patch.object(win.Window, "valid", return_value=True), patch.object(win, "is_visible", return_value=True), patch.object(win, "mouse_message") as mouse:
            self.assertTrue(sync.request("dialog_up", (301, (20, 20)), lambda: True))
        clicks = [call.args for call in mouse.call_args_list if call.args[1] == win.WM_LUP]
        self.assertEqual([(args[0].hwnd, args[2]) for args in clicks], [(401, (20, 20)), (301, (20, 20))])

    def test_dragging_off_button_cancels_both(self):
        sync = self.coordinator()
        sync.request("dialog_down", (301, (20, 20)), lambda: True)
        with patch.object(win, "mouse_message") as mouse:
            self.assertFalse(sync.request("dialog_up", (301, (90, 90)), lambda: True))
        mouse.assert_not_called()

    @patch.object(win, "foreground", return_value=301)
    @patch.object(win, "is_dialog_for", return_value=True)
    def test_one_physical_enter_queues_exactly_one_decision(self, *_):
        engine = Engine.__new__(Engine)
        engine.active = threading.Event()
        engine.active.set()
        engine.pair = win.Window(100, 1, "Example App", "a"), win.Window(200, 2, "Example App", "b")
        engine.keyboard = True
        engine.epoch = 1
        engine.events = queue.Queue()
        engine._dialog_return_held = False
        self.assertTrue(engine.on_key(win.WM_KEYDOWN, 13, 28, 0))
        self.assertTrue(engine.on_key(win.WM_KEYDOWN, 13, 28, 0))
        self.assertTrue(engine.on_key(win.WM_KEYUP, 13, 28, 0))
        self.assertEqual(engine.events.qsize(), 1)
        self.assertEqual(engine.events.get()[1:], ("dialog_enter", 301))


if __name__ == "__main__":
    unittest.main()
