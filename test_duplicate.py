"""Tests for the boundaries that prevent replay into the wrong window."""
import queue
import threading
import unittest
from unittest.mock import Mock, patch
import win_api as win
from automation import Engine


class WindowDiscovery(unittest.TestCase):
    def test_lists_application_windows_and_excludes_unsuitable_windows(self):
        captions = {100: "Text Editor", 200: "Image Viewer", 300: "Hidden App",
                    400: "Uncaptioned App", 500: "  ", 600: "Owned Dialog", 700: "Tap Duplicator"}

        def enumerate_windows(callback, _):
            for hwnd in captions:
                callback(hwnd, 0)
            return True

        with patch.multiple(win,
                            enum_windows=Mock(side_effect=enumerate_windows),
                            title=Mock(side_effect=captions.__getitem__),
                            is_visible=Mock(side_effect=lambda hwnd: hwnd != 300),
                            get_style=Mock(side_effect=lambda hwnd, _: 0 if hwnd == 400 else 0x00C00000),
                            pid_of=Mock(side_effect=lambda hwnd: 999 if hwnd == 700 else hwnd + 1),
                            get_owner=Mock(side_effect=lambda hwnd, _: 100 if hwnd == 600 else 0),
                            process_path=Mock(side_effect=lambda pid: f"C:/Apps/{pid}/app.exe"),
                            client_box=Mock(side_effect=lambda hwnd: (300 - hwnd, 0, 480, 320))), \
             patch.object(win.os, "getpid", return_value=999):
            found = win.windows()

        self.assertEqual([(window.hwnd, window.caption) for window in found],
                         [(200, "Image Viewer"), (100, "Text Editor")])
        self.assertEqual([window.path for window in found],
                         ["C:/Apps/201/app.exe", "C:/Apps/101/app.exe"])


class ReplayBoundaries(unittest.TestCase):
    def engine(self):
        engine = Engine.__new__(Engine)
        engine.active = threading.Event()
        engine.active.set()
        engine.pair = (win.Window(100, 1, "Example App", "a"), win.Window(200, 2, "Example App", "b"))
        engine.buttons = engine.sent_buttons = 0
        engine.keyboard = engine.wheel = True
        engine.epoch = 3
        engine.last_move = 0
        engine.events = queue.Queue(maxsize=20)
        engine.notices = queue.Queue()
        return engine

    def test_translation_tracks_moving_windows(self):
        self.assertEqual(win.mapped_point((-350, 160), (-500, 100, 480, 320), (40, 20, 480, 320)), (190, 80))

    def test_unequal_layouts_are_rejected(self):
        with self.assertRaises(ValueError):
            win.mapped_point((10, 10), (0, 0, 600, 400), (600, 0, 500, 400))

    def test_signed_drag_coordinates(self):
        self.assertEqual(win.packed_point(-1, -2), 0xFFFEFFFF)

    @patch.object(win, "client_box", return_value=(10, 40, 480, 320))
    @patch.object(win, "root_at", return_value=100)
    def test_titlebar_click_is_never_duplicated(self, *_):
        engine = self.engine()
        engine.on_mouse(win.WM_LDOWN, 100, 20, 0, 1)
        self.assertTrue(engine.events.empty())
        self.assertEqual(engine.buttons, 0)

    @patch.object(win, "pid_of", return_value=99)
    @patch.object(win, "get_style", return_value=0x00C00000)
    @patch.object(win, "root_at", return_value=999)
    def test_other_app_click_is_not_duplicated(self, *_):
        engine = self.engine()
        engine.on_mouse(win.WM_LDOWN, 50, 50, 0, 1)
        self.assertTrue(engine.events.empty())

    @patch.object(win, "client_box", return_value=(10, 40, 480, 320))
    @patch.object(win, "root_at", return_value=100)
    def test_source_client_click_is_queued_once(self, *_):
        engine = self.engine()
        engine.on_mouse(win.WM_LDOWN, 100, 80, 0, 1)
        engine.on_mouse(win.WM_LUP, 100, 80, 0, 2)
        self.assertEqual(engine.events.qsize(), 2)
        self.assertEqual(engine.buttons, 0)

    @patch.object(win, "foreground", return_value=999)
    @patch.object(win, "pid_of", return_value=99)
    @patch.object(win, "get_style", return_value=0x00C00000)
    def test_keyboard_outside_source_is_not_captured(self, *_):
        engine = self.engine()
        engine.on_key(win.WM_KEYDOWN, 65, 30, 0)
        self.assertTrue(engine.events.empty())

    def test_pause_invalidates_queued_events(self):
        engine = self.engine()
        engine.enqueue("mouse", ())
        old_epoch = engine.epoch
        engine.pause()
        self.assertFalse(engine.active.is_set())
        self.assertFalse(engine.allowed(old_epoch))
        self.assertNotEqual(engine.epoch, old_epoch)


if __name__ == "__main__":
    unittest.main()
