"""Explicit desktop test fixture. Never connects to external applications or cameras.

Run with --controller. Commands/status are kept in .dialog_test.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import time
import tkinter as tk

import win_api as win

ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".dialog_test"
BODY = "TEST ONLY. No cameras are connected by this test. Repeat this answer in both test windows?"


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    for _ in range(30):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            time.sleep(0.01)
    raise RuntimeError(f"Status file is locked: {path.name}")


def fixture(role):
    win.dpi_awareness()
    root = tk.Tk()
    root.title(f"Tap Duplicate test {role} — NO CAMERAS")
    root.geometry(f"480x240+{60 if role == 'A' else 700}+80")
    root.configure(bg="white")
    label = tk.Label(root, text=f"Test window {role}\nNo camera commands. Waiting for test…", bg="white", font=("Segoe UI", 12))
    label.pack(expand=True)
    root.update_idletasks()
    hwnd = int(win.ancestor(root.winfo_id(), 2))
    state = {"pid": os.getpid(), "hwnd": hwnd, "answer": None, "count": 0}
    path = WORK / f"{role}.json"
    write(path, state)
    sequence = None

    def poll():
        nonlocal sequence
        try:
            command = json.loads((WORK / f"{role}_command.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            command = {}
        if command.get("sequence") != sequence:
            sequence = command.get("sequence")
            if command.get("action") == "show":
                answer = win.api(win.U, "MessageBoxW", C.c_int, win.W.HWND, win.W.LPCWSTR, win.W.LPCWSTR, win.W.UINT)(
                    hwnd, command.get("body", BODY), "Confirmation [TEST ONLY]", 0x4 | 0x20 | 0x100)
                state["answer"] = "yes" if answer == 6 else "no" if answer == 7 else "cancel"
                state["count"] += 1
                write(path, state)
                label.configure(text=f"Test window {role}\nAnswer: {state['answer']} · count: {state['count']}")
            elif command.get("action") == "quit":
                root.destroy()
                return
        root.after(80, poll)

    root.after(80, poll)
    root.mainloop()


def controller():
    from automation import Engine
    WORK.mkdir(exist_ok=True)
    for name in ("stop", "A.json", "B.json", "A_command.json", "B_command.json", "controller.json", "driver.json"):
        path = WORK / name
        if path.exists():
            path.unlink()
    processes = [subprocess.Popen([str(Path(sys.executable).with_name("pythonw.exe")), "-B", __file__, "--role", role], cwd=ROOT)
                 for role in ("A", "B")]
    notices = queue.Queue()
    engine = Engine(notices)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if all((WORK / f"{role}.json").exists() for role in ("A", "B")) and engine.ready.is_set() and engine.hooks.ready.is_set():
                break
            time.sleep(0.05)
        states = [json.loads((WORK / f"{role}.json").read_text(encoding="utf-8")) for role in ("A", "B")]
        pair = tuple(win.Window(state["hwnd"], state["pid"], f"Test {role}", "test_fixture") for state, role in zip(states, ("A", "B")))
        engine.start(pair)
        latest = "ready"
        driver_sequence = None
        while not (WORK / "stop").exists():
            try:
                while True:
                    kind, text = notices.get_nowait()
                    if kind != "toggle":
                        latest = text or kind
            except queue.Empty:
                pass
            dialogs = win.dialogs(pair)
            try:
                driver = json.loads((WORK / "driver.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                driver = {}
            if driver.get("sequence") != driver_sequence:
                driver_sequence = driver.get("sequence")
                if driver.get("kind") == "click":
                    point = tuple(driver["point"])
                    source_dialog = next(h for h in dialogs if win.pid_of(h) == pair[0].pid)
                    engine.enqueue("dialog_down", (source_dialog, point))
                    engine.enqueue("dialog_up", (source_dialog, point))
                elif driver.get("kind") == "enter":
                    source_dialog = next(h for h in dialogs if win.pid_of(h) == pair[0].pid)
                    engine.enqueue("dialog_enter", source_dialog)
            status = {"source_pid": pair[0].pid, "target_pid": pair[1].pid,
                      "source_root": pair[0].hwnd, "target_root": pair[1].hwnd,
                      "source_dialog": next((h for h in dialogs if win.pid_of(h) == pair[0].pid), None),
                      "target_dialog": next((h for h in dialogs if win.pid_of(h) == pair[1].pid), None),
                      "active": engine.active.is_set(), "notice": latest, "count": engine.count}
            write(WORK / "controller.json", status)
            time.sleep(0.05)
    finally:
        engine.stop()
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("A", "B"))
    parser.add_argument("--controller", action="store_true")
    args = parser.parse_args()
    try:
        if args.controller:
            controller()
        elif args.role:
            fixture(args.role)
    except Exception:
        import traceback
        WORK.mkdir(exist_ok=True)
        (WORK / f"error_{args.role or 'controller'}.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
