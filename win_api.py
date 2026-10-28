"""Windows input/window primitives. No input is sent on import."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import os
import threading

U = C.WinDLL("user32", use_last_error=True)
K = C.WinDLL("kernel32", use_last_error=True)
LRESULT = C.c_ssize_t
ULONG_PTR = C.c_size_t
HOOKPROC = C.WINFUNCTYPE(LRESULT, C.c_int, W.WPARAM, W.LPARAM)
ENUMPROC = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)


def api(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


enum_windows = api(U, "EnumWindows", W.BOOL, ENUMPROC, W.LPARAM)
is_window = api(U, "IsWindow", W.BOOL, W.HWND)
is_visible = api(U, "IsWindowVisible", W.BOOL, W.HWND)
is_iconic = api(U, "IsIconic", W.BOOL, W.HWND)
get_title = api(U, "GetWindowTextW", C.c_int, W.HWND, W.LPWSTR, C.c_int)
get_class = api(U, "GetClassNameW", C.c_int, W.HWND, W.LPWSTR, C.c_int)
get_pid = api(U, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
get_client_rect = api(U, "GetClientRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
get_window_rect = api(U, "GetWindowRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
client_to_screen = api(U, "ClientToScreen", W.BOOL, W.HWND, C.POINTER(W.POINT))
screen_to_client = api(U, "ScreenToClient", W.BOOL, W.HWND, C.POINTER(W.POINT))
window_from_point = api(U, "WindowFromPoint", W.HWND, W.POINT)
child_from_point = api(U, "ChildWindowFromPointEx", W.HWND, W.HWND, W.POINT, W.UINT)
ancestor = api(U, "GetAncestor", W.HWND, W.HWND, W.UINT)
get_owner = api(U, "GetWindow", W.HWND, W.HWND, W.UINT)
get_style = api(U, "GetWindowLongPtrW", C.c_ssize_t, W.HWND, C.c_int)
foreground = api(U, "GetForegroundWindow", W.HWND)
post_message = api(U, "PostMessageW", W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
get_async_key = api(U, "GetAsyncKeyState", C.c_short, C.c_int)
get_double_click_time = api(U, "GetDoubleClickTime", W.UINT)
get_metric = api(U, "GetSystemMetrics", C.c_int, C.c_int)
show_window = api(U, "ShowWindow", W.BOOL, W.HWND, C.c_int)
set_window_pos = api(U, "SetWindowPos", W.BOOL, W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT)
open_process = api(K, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
close_handle = api(K, "CloseHandle", W.BOOL, W.HANDLE)
query_image = api(K, "QueryFullProcessImageNameW", W.BOOL, W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))
get_module = api(K, "GetModuleHandleW", W.HMODULE, W.LPCWSTR)
thread_id = api(K, "GetCurrentThreadId", W.DWORD)

WM_MOVE = 0x200
WM_LDOWN, WM_LUP, WM_LDOUBLE = 0x201, 0x202, 0x203
WM_RDOWN, WM_RUP, WM_RDOUBLE = 0x204, 0x205, 0x206
WM_MDOWN, WM_MUP, WM_MDOUBLE = 0x207, 0x208, 0x209
WM_WHEEL, WM_HWHEEL = 0x20A, 0x20E
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_CHAR = 0x102
DOWN = {WM_LDOWN: 1, WM_RDOWN: 2, WM_MDOWN: 16}
UP = {WM_LUP: 1, WM_RUP: 2, WM_MUP: 16}
DOUBLE = {WM_LDOWN: WM_LDOUBLE, WM_RDOWN: WM_RDOUBLE, WM_MDOWN: WM_MDOUBLE}


def dpi_awareness():
    try:
        fn = api(U, "SetProcessDpiAwarenessContext", W.BOOL, C.c_void_p)
        fn(C.c_void_p(-4))
    except (AttributeError, OSError):
        pass


def title(hwnd):
    buf = C.create_unicode_buffer(1024)
    get_title(hwnd, buf, len(buf))
    return buf.value


def class_name(hwnd):
    buf = C.create_unicode_buffer(256)
    get_class(hwnd, buf, len(buf))
    return buf.value


def pid_of(hwnd):
    pid = W.DWORD()
    get_pid(hwnd, C.byref(pid))
    return pid.value


def process_path(pid):
    handle = open_process(0x1000, False, pid)
    if not handle:
        return ""
    try:
        buf, size = C.create_unicode_buffer(32768), W.DWORD(32768)
        return buf.value if query_image(handle, 0, buf, C.byref(size)) else ""
    finally:
        close_handle(handle)


def client_box(hwnd):
    rect, point = W.RECT(), W.POINT()
    if not get_client_rect(hwnd, C.byref(rect)) or not client_to_screen(hwnd, C.byref(point)):
        raise OSError("Окно недоступно")
    return point.x, point.y, rect.right - rect.left, rect.bottom - rect.top


def root_at(x, y):
    hwnd = window_from_point(W.POINT(x, y))
    return int(ancestor(hwnd, 2) or hwnd or 0)


def source_surface(hwnd, source):
    if hwnd == source.hwnd:
        return True
    # A combo-box popup can belong to the source process, but a captioned dialog cannot.
    return bool(hwnd and pid_of(hwnd) == source.pid and get_style(hwnd, -16) & 0x00C00000 != 0x00C00000)


@dataclass(frozen=True)
class Window:
    hwnd: int
    pid: int
    caption: str
    path: str

    def valid(self):
        return bool(is_window(self.hwnd) and pid_of(self.hwnd) == self.pid)

    @property
    def label(self):
        try:
            x, y, width, height = client_box(self.hwnd)
        except OSError:
            width = height = 0
        folder = os.path.basename(os.path.dirname(self.path)) or self.caption
        return f"PID {self.pid}  ·  {folder}  ·  {width}×{height}"


def windows():
    found = []

    @ENUMPROC
    def collect(hwnd, _):
        caption = title(hwnd)
        if (is_visible(hwnd) and get_style(hwnd, -16) & 0x00C00000 == 0x00C00000
                and caption.strip()
                and pid_of(hwnd) != os.getpid() and not get_owner(hwnd, 4)):
            pid = pid_of(hwnd)
            found.append(Window(int(hwnd), pid, caption, process_path(pid)))
        return True

    enum_windows(collect, 0)
    return sorted(found, key=lambda win: client_box(win.hwnd)[:2])


def dialogs(pair):
    found = []
    pids = {win.pid for win in pair}
    mains = {win.hwnd for win in pair}

    @ENUMPROC
    def collect(hwnd, _):
        if (int(hwnd) not in mains and is_visible(hwnd) and pid_of(hwnd) in pids
                and get_style(hwnd, -16) & 0x00C00000 == 0x00C00000 and get_owner(hwnd, 4)):
            found.append(int(hwnd))
        return True

    enum_windows(collect, 0)
    return found


def is_dialog_for(hwnd, main):
    return bool(hwnd and hwnd != main.hwnd and is_window(hwnd) and is_visible(hwnd)
                and pid_of(hwnd) == main.pid and get_style(hwnd, -16) & 0x00C00000 == 0x00C00000
                and get_owner(hwnd, 4))


def same_size(pair):
    a, b = (client_box(win.hwnd) for win in pair)
    return a[2:] == b[2:] and a[2] > 20 and a[3] > 20


def mapped_point(point, source_box, target_box):
    """Translate the same client-area point; intentionally do not scale unequal layouts."""
    if source_box[2:] != target_box[2:]:
        raise ValueError("Размеры окон различаются")
    return point[0] - source_box[0] + target_box[0], point[1] - source_box[1] + target_box[1]


def packed_point(x, y):
    return (int(x) & 0xFFFF) | ((int(y) & 0xFFFF) << 16)


def post(hwnd, message, wp=0, lp=0):
    if not post_message(hwnd, message, wp, lp):
        error = C.get_last_error()
        if error == 5:
            raise OSError("Разные права доступа. Запустите помощник и обе программы с одинаковыми правами.")
        raise C.WinError(error)


def mouse_message(target, message, point, buttons=0, wheel=0):
    x, y = point
    hwnd = target.hwnd
    if message not in (WM_WHEEL, WM_HWHEEL):
        for _ in range(16):
            pt = W.POINT(x, y)
            screen_to_client(hwnd, C.byref(pt))
            child = child_from_point(hwnd, pt, 1 | 2 | 4)
            if not child or child == hwnd:
                break
            hwnd = int(child)
        pt = W.POINT(x, y)
        screen_to_client(hwnd, C.byref(pt))
        lp = packed_point(pt.x, pt.y)
        wp = buttons
    else:
        lp, wp = packed_point(x, y), buttons | ((wheel & 0xFFFF) << 16)
    post(hwnd, message, wp, lp)


class MONITORINFO(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]


def arrange(pair):
    monitor_from = api(U, "MonitorFromWindow", W.HANDLE, W.HWND, W.DWORD)
    monitor_info = api(U, "GetMonitorInfoW", W.BOOL, W.HANDLE, C.POINTER(MONITORINFO))
    info = MONITORINFO(cbSize=C.sizeof(MONITORINFO))
    if not monitor_info(monitor_from(pair[0].hwnd, 2), C.byref(info)):
        raise C.WinError(C.get_last_error())
    rect = info.rcWork
    half, height = (rect.right - rect.left) // 2, rect.bottom - rect.top
    for index, win in enumerate(pair):
        show_window(win.hwnd, 9)
        if not set_window_pos(win.hwnd, None, rect.left + half * index, rect.top, half, height, 0x14):
            raise C.WinError(C.get_last_error())


class MouseData(C.Structure):
    _fields_ = [("pt", W.POINT), ("mouseData", W.DWORD), ("flags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KeyData(C.Structure):
    _fields_ = [("vkCode", W.DWORD), ("scanCode", W.DWORD), ("flags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]


class Hooks(threading.Thread):
    """Callbacks only enqueue bounded events. All COM/provider calls run elsewhere."""
    def __init__(self, mouse, key, hotkey, notice):
        super().__init__(name="input-hooks", daemon=True)
        self.mouse, self.key, self.hotkey, self.notice = mouse, key, hotkey, notice
        self.tid = 0
        self.ready = threading.Event()

    def run(self):
        install = api(U, "SetWindowsHookExW", W.HANDLE, C.c_int, HOOKPROC, W.HINSTANCE, W.DWORD)
        unhook = api(U, "UnhookWindowsHookEx", W.BOOL, W.HANDLE)
        next_hook = api(U, "CallNextHookEx", LRESULT, W.HANDLE, C.c_int, W.WPARAM, W.LPARAM)
        get_message = api(U, "GetMessageW", C.c_int, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
        peek = api(U, "PeekMessageW", W.BOOL, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT)
        register = api(U, "RegisterHotKey", W.BOOL, W.HWND, C.c_int, W.UINT, W.UINT)
        unregister = api(U, "UnregisterHotKey", W.BOOL, W.HWND, C.c_int)

        @HOOKPROC
        def mouse_cb(code, wp, lp):
            if code >= 0:
                try:
                    data = C.cast(lp, C.POINTER(MouseData)).contents
                    if self.mouse(int(wp), data.pt.x, data.pt.y, int(data.mouseData), int(data.time)):
                        return 1
                except Exception as error:
                    self.notice(f"Ошибка мыши: {error}")
            return next_hook(None, code, wp, lp)

        @HOOKPROC
        def key_cb(code, wp, lp):
            if code >= 0:
                try:
                    data = C.cast(lp, C.POINTER(KeyData)).contents
                    if self.key(int(wp), int(data.vkCode), int(data.scanCode), int(data.flags)):
                        return 1
                except Exception as error:
                    self.notice(f"Ошибка клавиатуры: {error}")
            return next_hook(None, code, wp, lp)

        self.callbacks = mouse_cb, key_cb
        self.tid = thread_id()
        msg = W.MSG()
        peek(C.byref(msg), None, 0, 0, 0)
        handles = []
        registered = []
        try:
            for kind, cb in ((14, mouse_cb), (13, key_cb)):
                handle = install(kind, cb, get_module(None), 0)
                if not handle:
                    raise C.WinError(C.get_last_error())
                handles.append(handle)
            for identifier, vk in ((1, 0x77), (2, 0x78)):
                if register(None, identifier, 0x4000, vk):
                    registered.append(identifier)
                else:
                    self.notice(f"Клавиша F{vk - 0x6F} занята другой программой; используйте кнопки помощника.")
            self.ready.set()
            while get_message(C.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x312:
                    self.hotkey(int(msg.wParam))
        except Exception as error:
            self.notice(f"Не удалось включить перехват ввода: {error}")
        finally:
            for identifier in registered:
                unregister(None, identifier)
            for handle in handles:
                unhook(handle)
            self.ready.set()

    def stop(self):
        if self.tid:
            api(U, "PostThreadMessageW", W.BOOL, W.DWORD, W.UINT, W.WPARAM, W.LPARAM)(self.tid, 0x12, 0, 0)
