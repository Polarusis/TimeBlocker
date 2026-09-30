
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import threading
import time
import json
from pathlib import Path
from datetime import date
import csv
import io
import os
import sys
import shutil
import importlib
import ctypes
import winreg
# ============================================================
# АВТОМАТИЧНЕ ВСТАНОВЛЕННЯ ЗАЛЕЖНОСТЕЙ
# ============================================================

def ensure_package(package, import_name):

    try:
        importlib.import_module(import_name)
        return True

    except ImportError:

        try:

            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "--user",
                package
            ])

            return True

        except Exception as e:

            messagebox.showerror(
                "Помилка встановлення",
                f"Не вдалося встановити {package}.\n\n"
                f"Помилка:\n{e}"
            )

            return False


if not ensure_package("pystray", "pystray"):
    sys.exit()

if not ensure_package("Pillow", "PIL"):
    sys.exit()

import pystray

from PIL import Image, ImageDraw

# ============================================================
# ЗАБОРОНА ЗАПУСКУ ДРУГОЇ КОПІЇ
# ============================================================

MUTEX_NAME = "EXE_Time_Blocker_Single_Instance"

mutex = ctypes.windll.kernel32.CreateMutexW(
    None,
    False,
    MUTEX_NAME
)

if ctypes.windll.kernel32.GetLastError() == 183:
    # Програма вже запущена
    sys.exit(0)

if getattr(sys, "frozen", False):
    DATA_FILE = Path(sys.executable).resolve().parent / "limits.json"
else:
    DATA_FILE = Path(__file__).resolve().parent / "limits.json"

CHECK_INTERVAL = 0.5

# ============================================================
# ЗАВАНТАЖЕННЯ НАЛАШТУВАНЬ
# ============================================================

def load_data():

    try:

        if DATA_FILE.exists():

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # ------------------------------------------------
            # Сумісність зі старим форматом
            # ------------------------------------------------

            if "blocks" not in data:
                data["blocks"] = {}

            if "date" not in data:
                data["date"] = str(date.today())

            # ------------------------------------------------
            # Новий день
            # ------------------------------------------------

            if data.get("date") != str(date.today()):
                for block in data.get("blocks", {}).values():

                    block["used"] = 0

                data["date"] = str(date.today())

                save_data_direct(data)

            return data

    except Exception:
        pass


    # --------------------------------------------------------
    # Нова база
    # --------------------------------------------------------

    return {
        "date": str(date.today()),
        "blocks": {}
    }


def save_data_direct(current_data):

    try:

        with open(DATA_FILE, "w", encoding="utf-8") as f:

            json.dump(
                current_data,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception:
        pass


def save_data():

    save_data_direct(data)

def check_new_day():

    today = str(date.today())

    if data.get("date") != today:

        data["date"] = today

        for block in data.get("blocks", {}).values():
            block["used"] = 0

        save_data()

        return True

    return False

data = load_data()

running = True

# ============================================================
# РЕЖИМ ЗАПУСКУ
# ============================================================

START_IN_BACKGROUND = "--background" in sys.argv

# ============================================================
# АВТОЗАПУСК WINDOWS
# ============================================================

APP_NAME = "EXE Time Blocker"


def get_startup_folder():

    return Path(
        os.environ["APPDATA"]
    ) / (
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )


def get_exe_path():

    if getattr(sys, "frozen", False):

        return Path(sys.executable).resolve()

    return Path(__file__).resolve()


def enable_autostart():
    try:
        source = get_exe_path()

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )

        winreg.SetValueEx(
            key,
            APP_NAME,
            0,
            winreg.REG_SZ,
            f'"{source}" --background'
        )

        winreg.CloseKey(key)

        # Видаляємо старі способи автозапуску
        startup = get_startup_folder()

        for old_file in [
            startup / f"{APP_NAME}.bat",
            startup / f"{APP_NAME}.vbs",
            startup / f"{APP_NAME}.lnk"
        ]:
            if old_file.exists():
                old_file.unlink()

        return True

    except Exception as e:
        print("Помилка автозапуску:", e)
        return False

def disable_autostart():

    try:

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )

        try:

            winreg.DeleteValue(
                key,
                APP_NAME
            )

        except FileNotFoundError:

            pass

        winreg.CloseKey(key)

        # Видаляємо старі способи автозапуску
        startup = get_startup_folder()

        for old_file in [
            startup / f"{APP_NAME}.bat",
            startup / f"{APP_NAME}.vbs",
            startup / f"{APP_NAME}.lnk"
        ]:

            if old_file.exists():

                old_file.unlink()

        return True

    except Exception as e:

        print(
            "Помилка вимкнення автозапуску:",
            e
        )

        return False


def autostart_enabled():

    try:

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )

        try:

            value, _ = winreg.QueryValueEx(
                key,
                APP_NAME
            )

            winreg.CloseKey(key)

            return bool(value)

        except FileNotFoundError:

            winreg.CloseKey(key)

            return False

    except Exception:

        return False

# ============================================================
# РОБОТА З ЧАСОМ
# ============================================================

def format_time(seconds):

    seconds = max(0, int(seconds))

    hours, remainder = divmod(seconds, 3600)

    minutes, seconds = divmod(remainder, 60)

    if hours:

        return f"{hours} год {minutes:02d} хв"

    return f"{minutes:02d}:{seconds:02d}"


# ============================================================
# ОТРИМАННЯ ЗАПУЩЕНИХ EXE
# ============================================================

import csv
import io


def get_process_names():

    try:

        result = subprocess.run(
            [
                "tasklist",
                "/FO",
                "CSV",
                "/NH"
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        processes = set()

        reader = csv.reader(
            io.StringIO(result.stdout)
        )

        for row in reader:

            if row:

                processes.add(
                    row[0].strip().lower()
                )

        return processes

    except Exception:

        return set()
# ============================================================
# ПРИМУСОВЕ ЗАКРИТТЯ EXE
# ============================================================

def kill_process(name):

    try:

        subprocess.run(
            [
                "taskkill",
                "/F",
                "/IM",
                name
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    except Exception:

        pass


# ============================================================
# ГОЛОВНЕ ВІКНО
# ============================================================

root = tk.Tk()

root.title("EXE Time Blocker")

root.geometry("850x560")

root.minsize(
    700,
    450
)

# ============================================================
# СИСТЕМНИЙ ТРЕЙ
# ============================================================

tray_icon = None


def create_tray_image():

    image = Image.new(
        "RGB",
        (64, 64),
        "white"
    )

    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (8, 8, 56, 56),
        outline="black",
        width=4
    )

    draw.line(
        (32, 16, 32, 32),
        fill="black",
        width=4
    )

    draw.line(
        (32, 32, 44, 38),
        fill="black",
        width=4
    )

    return image


def show_window(icon=None, item=None):

    root.after(
        0,
        lambda: (
            root.deiconify(),
            root.lift(),
            root.focus_force()
        )
    )


def hide_window():

    root.withdraw()


def exit_application(icon=None, item=None):

    global running

    running = False

    try:
        if icon:
            icon.stop()
    except Exception:
        pass

    save_data()

    root.after(
        0,
        root.destroy
    )


def toggle_autostart(icon=None, item=None):

    if autostart_enabled():
        disable_autostart()
    else:
        enable_autostart()


def start_tray():

    global tray_icon

    menu = pystray.Menu(

        pystray.MenuItem(
            "Відкрити",
            show_window,
            default=True
        ),

        pystray.MenuItem(
            "Автозапуск Windows",
            toggle_autostart,
            checked=lambda item: autostart_enabled()
        ),

        pystray.MenuItem(
            "Вийти",
            exit_application
        )
    )

    tray_icon = pystray.Icon(
        APP_NAME,
        create_tray_image(),
        APP_NAME,
        menu
    )

    tray_icon.run()

# ============================================================
# СТИЛЬ
# ============================================================

style = ttk.Style()

try:
    style.theme_use("vista")
except Exception:
    pass


# ============================================================
# ЗАГОЛОВОК
# ============================================================

title = ttk.Label(
    root,
    text="EXE Time Blocker",
    font=("Segoe UI", 18, "bold")
)

title.pack(
    pady=(15, 3)
)


info = ttk.Label(
    root,
    text="Ліміт блоку є спільним для всіх EXE всередині нього.",
    font=("Segoe UI", 10)
)

info.pack(
    pady=(0, 12)
)


# ============================================================
# ТАБЛИЦЯ
# ============================================================

columns = (
    "block",
    "programs",
    "limit",
    "used",
    "remaining",
    "status"
)


tree = ttk.Treeview(
    root,
    columns=columns,
    show="headings",
    height=16
)


tree.heading(
    "block",
    text="Блок"
)

tree.heading(
    "programs",
    text="EXE"
)

tree.heading(
    "limit",
    text="Ліміт / день"
)

tree.heading(
    "used",
    text="Використано"
)

tree.heading(
    "remaining",
    text="Залишилось"
)

tree.heading(
    "status",
    text="Статус"
)


tree.column(
    "block",
    width=150
)

tree.column(
    "programs",
    width=250
)

tree.column(
    "limit",
    width=110,
    anchor="center"
)

tree.column(
    "used",
    width=110,
    anchor="center"
)

tree.column(
    "remaining",
    width=110,
    anchor="center"
)

tree.column(
    "status",
    width=120,
    anchor="center"
)


tree.pack(
    fill="both",
    expand=True,
    padx=15
)


# ============================================================
# КНОПКИ
# ============================================================

buttons = ttk.Frame(root)

buttons.pack(
    pady=12
)


# ============================================================
# ОНОВЛЕННЯ ТАБЛИЦІ
# ============================================================

def refresh():
    # Запам'ятовуємо вибраний блок
    selected = tree.selection()
    selected_block = selected[0] if selected else None

    # Оновлюємо таблицю
    for item in tree.get_children():
        tree.delete(item)

    for block_name, block in data["blocks"].items():
        limit = block.get("limit", 0)
        used = block.get("used", 0)
        remaining = max(0, limit - used)

        status = "ЗАБЛОКОВАНО" if used >= limit else "дозволено"

        programs = block.get("programs", [])
        programs_text = ", ".join(programs)

        tree.insert(
            "",
            "end",
            iid=block_name,
            values=(
                block_name,
                programs_text,
                format_time(limit),
                format_time(used),
                format_time(remaining),
                status
            )
        )

    # Повертаємо вибір після оновлення
    if selected_block is not None and tree.exists(selected_block):
        tree.selection_set(selected_block)
        tree.focus(selected_block)


# ============================================================
# ДОДАТИ БЛОК
# ============================================================

def add_block():

    # --------------------------------------------------------
    # Назва блоку
    # --------------------------------------------------------

    block_name = simpledialog.askstring(
        "Новий блок",
        "Назва блоку:\nНаприклад: Ігри",
        parent=root
    )


    if not block_name:

        return


    block_name = block_name.strip()


    if not block_name:

        return


    # --------------------------------------------------------
    # Перевірка дубліката
    # --------------------------------------------------------

    if block_name in data["blocks"]:

        messagebox.showerror(
            "Помилка",
            "Блок з такою назвою вже існує."
        )

        return


    # --------------------------------------------------------
    # Ліміт
    # --------------------------------------------------------

    minutes = simpledialog.askinteger(
        "Денний ліміт",
        f"Скільки хвилин на день дозволити для блоку «{block_name}»?",
        initialvalue=60,
        minvalue=1,
        maxvalue=1440,
        parent=root
    )


    if minutes is None:

        return


    # --------------------------------------------------------
    # Створення блоку
    # --------------------------------------------------------

    data["blocks"][block_name] = {

        "limit": minutes * 60,

        "used": 0,

        "programs": []

    }


    save_data()

    refresh()


    # --------------------------------------------------------
    # Одразу запропонувати додати EXE
    # --------------------------------------------------------

    add_more = messagebox.askyesno(
        "Додати EXE",
        f"Блок «{block_name}» створено.\n\n"
        "Хочеш зараз додати EXE до цього блоку?"
    )


    if add_more:

        add_program_to_block(block_name)


# ============================================================
# ДОДАТИ EXE ДО БЛОКУ
# ============================================================

def add_program_to_block(block_name=None):

    if block_name is None:

        selected = tree.selection()

        if not selected:

            messagebox.showinfo(
                "Вибір",
                "Спочатку вибери блок."
            )

            return

        block_name = selected[0]


    if block_name not in data["blocks"]:

        return


    # --------------------------------------------------------
    # Запит EXE
    # --------------------------------------------------------

    exe = simpledialog.askstring(
        "Додати EXE",
        "Введи точну назву файлу:\n"
        "Наприклад: RobloxPlayerBeta.exe",
        parent=root
    )


    if not exe:

        return


    exe = exe.strip()


    # Якщо користувач не написав .exe

    if not exe.lower().endswith(".exe"):

        exe += ".exe"


    # --------------------------------------------------------
    # Перевірка, чи EXE вже є в цьому блоці
    # --------------------------------------------------------

    programs = data["blocks"][block_name]["programs"]


    for existing in programs:

        if existing.lower() == exe.lower():

            messagebox.showinfo(
                "Вже існує",
                f"{exe} вже є в цьому блоці."
            )

            return


    # --------------------------------------------------------
    # Перевірка, чи EXE вже знаходиться в іншому блоці
    # --------------------------------------------------------

    for other_block_name, other_block in data["blocks"].items():

        if other_block_name == block_name:

            continue


        for existing in other_block.get("programs", []):

            if existing.lower() == exe.lower():

                messagebox.showwarning(
                    "EXE вже використовується",
                    f"{exe} вже знаходиться у блоці "
                    f"«{other_block_name}».\n\n"
                    "Один EXE не може одночасно належати "
                    "двом блокам."
                )

                return


    # --------------------------------------------------------
    # Додати EXE
    # --------------------------------------------------------

    programs.append(exe)

    save_data()

    refresh()


    # --------------------------------------------------------
    # Запитати, чи додати ще
    # --------------------------------------------------------

    add_more = messagebox.askyesno(
        "Додати ще",
        f"{exe} додано до блоку «{block_name}».\n\n"
        "Додати ще один EXE?"
    )


    if add_more:

        add_program_to_block(block_name)


# ============================================================
# ЗМІНИТИ ЛІМІТ БЛОКУ
# ============================================================

def change_limit():

    selected = tree.selection()


    if not selected:

        messagebox.showinfo(
            "Вибір",
            "Спочатку вибери блок."
        )

        return


    block_name = selected[0]


    if block_name not in data["blocks"]:

        return


    old = data["blocks"][block_name]["limit"] // 60


    minutes = simpledialog.askinteger(
        "Змінити ліміт",
        f"Новий ліміт для блоку «{block_name}» (хвилини):",
        initialvalue=old,
        minvalue=1,
        maxvalue=1440,
        parent=root
    )


    if minutes is not None:

        data["blocks"][block_name]["limit"] = minutes * 60

        save_data()

        refresh()


# ============================================================
# ВИДАЛИТИ EXE З БЛОКУ
# ============================================================

def remove_program():

    selected = tree.selection()


    if not selected:

        messagebox.showinfo(
            "Вибір",
            "Спочатку вибери блок."
        )

        return


    block_name = selected[0]


    if block_name not in data["blocks"]:

        return


    programs = data["blocks"][block_name].get(
        "programs",
        []
    )


    if not programs:

        messagebox.showinfo(
            "Немає EXE",
            "У цьому блоці немає EXE."
        )

        return


    # --------------------------------------------------------
    # Вікно вибору EXE
    # --------------------------------------------------------

    program_window = tk.Toplevel(root)

    program_window.title(
        f"EXE у блоці — {block_name}"
    )

    program_window.geometry(
        "450x350"
    )

    program_window.transient(root)

    program_window.grab_set()


    label = ttk.Label(
        program_window,
        text="Вибери EXE, який потрібно прибрати:"
    )

    label.pack(
        pady=(15, 8)
    )


    listbox = tk.Listbox(
        program_window,
        font=("Segoe UI", 10)
    )

    listbox.pack(
        fill="both",
        expand=True,
        padx=15
    )


    for exe in programs:

        listbox.insert(
            tk.END,
            exe
        )


    def delete_selected():

        selection = listbox.curselection()


        if not selection:

            return


        index = selection[0]

        exe = programs[index]


        if messagebox.askyesno(
            "Видалити EXE",
            f"Прибрати {exe} з блоку «{block_name}»?",
            parent=program_window
        ):

            programs.pop(index)

            save_data()

            refresh()

            listbox.delete(index)


    ttk.Button(
        program_window,
        text="✕ Видалити вибраний EXE",
        command=delete_selected
    ).pack(
        pady=10
    )


# ============================================================
# СКИНУТИ ЧАС БЛОКУ
# ============================================================

def reset_selected():

    selected = tree.selection()


    if not selected:

        messagebox.showinfo(
            "Вибір",
            "Спочатку вибери блок."
        )

        return


    block_name = selected[0]


    if block_name not in data["blocks"]:

        return


    data["blocks"][block_name]["used"] = 0


    save_data()

    refresh()


# ============================================================
# ВИДАЛИТИ БЛОК
# ============================================================

def remove_block():

    selected = tree.selection()


    if not selected:

        messagebox.showinfo(
            "Вибір",
            "Спочатку вибери блок."
        )

        return


    block_name = selected[0]


    if messagebox.askyesno(
        "Видалити блок",
        f"Видалити блок «{block_name}»?\n\n"
        "Усі EXE будуть прибрані з цього блоку."
    ):

        del data["blocks"][block_name]

        save_data()

        refresh()


# ============================================================
# ПЕРЕЙМЕНУВАТИ БЛОК
# ============================================================

def rename_block():

    selected = tree.selection()


    if not selected:

        messagebox.showinfo(
            "Вибір",
            "Спочатку вибери блок."
        )

        return


    old_name = selected[0]


    new_name = simpledialog.askstring(
        "Перейменувати",
        "Нова назва блоку:",
        initialvalue=old_name,
        parent=root
    )


    if not new_name:

        return


    new_name = new_name.strip()


    if not new_name:

        return


    if new_name == old_name:

        return


    if new_name in data["blocks"]:

        messagebox.showerror(
            "Помилка",
            "Блок з такою назвою вже існує."
        )

        return


    data["blocks"][new_name] = data["blocks"].pop(old_name)


    save_data()

    refresh()


# ============================================================
# КНОПКИ
# ============================================================

ttk.Button(
    buttons,
    text="➕ Додати блок",
    command=add_block
).grid(
    row=0,
    column=0,
    padx=4
)


ttk.Button(
    buttons,
    text="➕ Додати EXE",
    command=add_program_to_block
).grid(
    row=0,
    column=1,
    padx=4
)


ttk.Button(
    buttons,
    text="⏱ Змінити ліміт",
    command=change_limit
).grid(
    row=0,
    column=2,
    padx=4
)


ttk.Button(
    buttons,
    text="↺ Скинути час",
    command=reset_selected
).grid(
    row=0,
    column=3,
    padx=4
)


ttk.Button(
    buttons,
    text="✕ Прибрати EXE",
    command=remove_program
).grid(
    row=0,
    column=4,
    padx=4
)


ttk.Button(
    buttons,
    text="🗑 Видалити блок",
    command=remove_block
).grid(
    row=0,
    column=5,
    padx=4
)


ttk.Button(
    buttons,
    text="✎ Перейменувати",
    command=rename_block
).grid(
    row=0,
    column=6,
    padx=4
)


# ============================================================
# СТАТУС
# ============================================================

status_label = ttk.Label(
    root,
    text="Працює",
    font=("Segoe UI", 9)
)

status_label.pack(
    pady=(0, 8)
)


# ============================================================
# ГОЛОВНИЙ МОНІТОР
# ============================================================

def monitor():

    last_check = time.monotonic()

    while running:

        # Перевірка нового дня
        today = str(date.today())

        if data.get("date") != today:

            data["date"] = today

            for block in data.get("blocks", {}).values():
                block["used"] = 0

            save_data()

            root.after(0, refresh)

        now = time.monotonic()

        delta = min(now - last_check, 2.0)
        last_check = now

        running_processes = get_process_names()

        changed = False

        for block_name, block in list(data["blocks"].items()):

            programs = block.get("programs", [])
            limit = block.get("limit", 0)
            used = block.get("used", 0)


            # -----------------------------------------------
            # Шукаємо реально запущені EXE цього блоку
            # -----------------------------------------------

            active_programs = []

            for exe in programs:

                if exe.lower() in running_processes:
                    active_programs.append(exe)


            # -----------------------------------------------
            # Ліміт вже використаний
            # -----------------------------------------------

            if used >= limit:

                for exe in active_programs:
                    kill_process(exe)

                continue


            # -----------------------------------------------
            # НІ ОДНОГО EXE НЕ ЗАПУЩЕНО
            # -----------------------------------------------

            if not active_programs:

                # НІЧОГО НЕ РАХУЄМО
                continue


            # -----------------------------------------------
            # EXE реально запущений
            # -----------------------------------------------

            block["used"] = used + delta


            # -----------------------------------------------
            # Ліміт закінчився
            # -----------------------------------------------

            if block["used"] >= limit:

                block["used"] = limit

                for exe in active_programs:
                    kill_process(exe)


        # Зберігаємо дані
        save_data()


        # Оновлюємо таблицю
        try:
            root.after(0, refresh)
        except Exception:
            pass


        time.sleep(CHECK_INTERVAL)
# ============================================================
# ЗАКРИТТЯ ПРОГРАМИ
# ============================================================

def on_close():

    # Хрестик лише ховає програму у трей.
    # Сам монітор продовжує працювати.

    root.withdraw()

root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# ПЕРШЕ ОНОВЛЕННЯ
# ============================================================

refresh()


# ============================================================
# ЗАПУСК МОНІТОРА
# ============================================================

threading.Thread(
    target=monitor,
    daemon=True
).start()

# ============================================================
# АВТОЗАПУСК
# ============================================================

# Увімкнути автозапуск автоматично при першому запуску
if not autostart_enabled():

    enable_autostart()


# ============================================================
# ЗАПУСК ТРЕЮ
# ============================================================

threading.Thread(
    target=start_tray,
    daemon=True
).start()


# ============================================================
# ПОКАЗ ВІКНА
# ============================================================

if START_IN_BACKGROUND:

    # Автозапуск Windows → працюємо приховано

    root.withdraw()

else:

    # Звичайний запуск → показуємо GUI

    root.deiconify()


# ============================================================
# ЗАПУСК GUI
# ============================================================

root.mainloop()