import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, Menu
import threading
import os
import glob
import wave
import io
import sys
import json
import time
import ctypes
import numpy as np
import platform
import re
import ssl
import requests
from bs4 import BeautifulSoup
import gc
import subprocess
import pyperclip
import shutil

ssl._create_default_https_context = ssl._create_unverified_context
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*tokenizer.*")

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ---------- Windows 11 Fluent: пары (светлая, тёмная) ----------
# --- Палитра в стиле MusicBee: нейтральные серые, голубое выделение, алый акцент ---
COLOR_BG = ("#f2f2f2", "#242424")            # фон окна
COLOR_PANEL = ("#ededed", "#2e2e2e")         # панели и карточки
COLOR_CARD = ("#e9e9e9", "#2a2a2a")          # карточки-поверхности
COLOR_CARD2 = ("#ffffff", "#1f1f1f")         # поля ввода и списки
COLOR_BORDER = ("#c4c4c4", "#4e4e4e")        # разделители и обводки
COLOR_ACCENT = ("#3a3a3a", "#e0e0e0")        # главные кнопки (тёмные, как транспорт MusicBee)
COLOR_ACCENT_HOVER = ("#262626", "#f0f0f0")
COLOR_ACCENT_SOFT = ("#e6e6e6", "#333333")   # мягкое нейтральное выделение
COLOR_SELECT = ("#dcdcdc", "#3a3a3a")        # выделенная строка / наведение (графит)
COLOR_SEG_ON = ("#3a3a3a", "#e0e0e0")        # активный пункт переключателя
COLOR_SEG_ON_HOVER = ("#262626", "#f0f0f0")
COLOR_SEG_ON_TEXT = ("#ffffff", "#1f1f1f")
COLOR_SELECT_TEXT = ("#d0d0d0", "#505050")   # фон выделения текста в полях
COLOR_HEAD = ("#1f1f1f", "#f2f2f2")          # заголовки
COLOR_TEXT_MAIN = ("#222222", "#e8e8e8")
COLOR_TEXT_SEC = ("#5c5c5c", "#b4b4b4")
COLOR_ON_ACCENT = ("#ffffff", "#1f1f1f")
COLOR_GREEN = ("#2e7d32", "#7bc67e")
COLOR_RED = ("#d94a4a", "#e57373")           # «сердце» MusicBee
COLOR_FILL_SOFT = ("#e2e2e2", "#3a3a3a")     # вторичные кнопки
COLOR_SWITCH_OFF = ("#c8c8c8", "#4a4a4a")

COMBO_W = 260
R_PANEL = 4
R_CARD = 3
FALLBACK_CHARS = 6000
MIN_CTX = 2048
VOX_BASE_SPEED = 2.0  # базовое ускорение VoxCPM2 через ресемпл

# CUDA-колесо torch для дополнения Vox: качаем сами, чтобы видеть проценты
TORCH_CU_WHL_NAME = "torch-2.5.1+cu121-cp312-cp312-win_amd64.whl"
TORCH_CU_WHL_URL = ("https://download.pytorch.org/whl/cu121/"
                    "torch-2.5.1%2Bcu121-cp312-cp312-win_amd64.whl")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Установленная версия: ресурсы лежат рядом с exe (в сборке — во внутренней папке),
# а всё, что приложение пишет само (настройки, модели, голоса), — в %LOCALAPPDATA%\FAIR:
# Program Files доступна только на чтение, и settings.json там не сохранится.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FAIR")
    try:
        for _sub in ("", "models", "models_llm", "voices"):
            os.makedirs(os.path.join(BASE_DIR, _sub), exist_ok=True)
    except Exception as _e:
        print(f"⚠️ папка данных: {_e}")

def _flog(msg):
    """Журнал первого запуска — чтобы потом было видно, что и почему не сработало."""
    try:
        with open(os.path.join(BASE_DIR, "fair_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


FONT_FAMILY = "Segoe UI Variable Text" if platform.system() == "Windows" else "San Francisco"
FONT_HEADER = (FONT_FAMILY, 18, "bold")
FONT_SUBHEADER = (FONT_FAMILY, 13, "bold")
FONT_NORMAL = (FONT_FAMILY, 12)
FONT_SMALL = (FONT_FAMILY, 11)
FONT_TINY = (FONT_FAMILY, 10)


def _hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(c1, c2, t):
    r1, g1, b1 = _hex_rgb(c1)
    r2, g2, b2 = _hex_rgb(c2)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t),
                              int(g1 + (g2 - g1) * t),
                              int(b1 + (b2 - b1) * t))


class Cancelled(Exception):
    pass


class TooLong(Exception):
    pass


try:
    import sounddevice as sd

    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False

try:
    from num2words import num2words

    NUM2WORDS_AVAILABLE = True
except ImportError:
    NUM2WORDS_AVAILABLE = False

try:
    from pypdf import PdfReader

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from docx import Document

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from piper import PiperVoice
except ImportError:
    print("❌ pip install piper-tts")
    exit(1)

try:
    from llama_cpp import Llama
except ImportError:
    print("❌ pip install llama-cpp-python")
    exit(1)

EN_RU_GLOSSARY = [
    ("ChatGPT", "Чат-джи-пи-ти"), ("GitHub", "Гитхаб"), ("Google", "Гугл"),
    ("YouTube", "Ютуб"), ("Microsoft", "Майкрософт"), ("Apple", "Эпл"),
    ("iPhone", "айфон"), ("Windows", "Виндовс"), ("Python", "Пайтон"),
    ("Discord", "Дискорд"), ("Twitter", "Твиттер"), ("Facebook", "Фейсбук"),
    ("Instagram", "Инстаграм"), ("TikTok", "ТикТок"), ("Steam", "Стим"),
    ("online", "онлайн"), ("offline", "офлайн"),
]

VOX_CANDIDATES = ["openbmb/VoxCPM2"]


DONATE_URL = "https://www.donationalerts.com/r/yaroslav_khmelev"

# варианты оценки: название, пояснение, цена для RU, цена для EN
DONATE_TIERS = [
    ("Работает как надо", "Без нареканий: открываю и слушаю.", "10 ₽", "$0.10"),
    ("Очень удобно", "Озвучка статей каждый день.", "100 ₽", "$1"),
    ("Экономит время", "Сжатие и озвучка делают своё дело.", "500 ₽", "$5"),
    ("Восторг", "Такого больше нигде нет, спасибо!", "1000 ₽", "$10"),
]


def _mode_color(color):
    """Цвет из пары (светлый, тёмный) для обычного tk-холста."""
    if isinstance(color, (tuple, list)):
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return color


def _apply_dialog_icon(win):
    """Диалог: один и тот же значок FAIR — и в шапке окна, и в панели задач.

    Раньше в шапке ставилась пустая иконка, и Windows подставляла запасной значок Tk —
    он выглядел как «значок из старого приложения».
    """
    try:
        win.update_idletasks()
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.GetParent.restype = ctypes.c_void_p
        user32.GetParent.argtypes = [ctypes.c_void_p]
        user32.SendMessageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                        ctypes.c_void_p, ctypes.c_void_p]
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        LR_LOADFROMFILE, IMAGE_ICON, WM_SETICON = 0x0010, 1, 0x0080
        ico = os.path.join(base, "app.ico")
        if os.path.isfile(ico):
            # главное: Tk ставит значок сам и надёжно, WM_SETICON ниже — подстраховка
            try:
                win.iconbitmap(ico)
            except Exception:
                pass
        small = user32.LoadImageW(None, ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        big = user32.LoadImageW(None, ico, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        if small:
            user32.SendMessageW(hwnd, WM_SETICON, 0, ctypes.c_void_p(small))   # шапка окна
        if big:
            user32.SendMessageW(hwnd, WM_SETICON, 1, ctypes.c_void_p(big))     # панель задач
    except Exception:
        pass


def _http_get(url, **kwargs):
    """GET с проверкой сертификата, а при подмене сертификата прокси — без неё.

    Антивирусы и корпоративные прокси подсовывают свой корневой сертификат,
    и requests падает с CERTIFICATE_VERIFY_FAILED — в этом случае повторяем
    без проверки (данные всё равно сверяются по размеру и работают локально).
    """
    kwargs.setdefault("timeout", 60)
    kwargs.setdefault("allow_redirects", True)
    try:
        return requests.get(url, **kwargs)
    except requests.exceptions.SSLError:
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
        kwargs["verify"] = False
        return requests.get(url, **kwargs)


class DonateDialog(ctk.CTkToplevel):
    """Оценка приложения и переход на страницу донатов."""

    def __init__(self, parent, on_pay):
        super().__init__(parent)
        self.title(_tr("Благодарить"))
        self.geometry("440x430")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.after(0, lambda: _apply_lang(self))
        _apply_dialog_icon(self)                       # сразу, чтобы не мигал системный
        self.after(150, lambda: _apply_dialog_icon(self))
        self.configure(fg_color=COLOR_BG)
        self.on_pay = on_pay
        self._choice = ctk.IntVar(value=2)      # по умолчанию — «Экономит время»

        body = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text="Понравился Free AI Reader?", font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(14, 2))
        ctk.CTkLabel(body, text="Выбери, насколько он тебе помог.", font=FONT_TINY,
                     text_color=COLOR_TEXT_SEC).pack(pady=(0, 12))

        prices = [t[2] if UI_LANG == "ru" else t[3] for t in DONATE_TIERS]
        for i, tier in enumerate(DONATE_TIERS):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkRadioButton(row, text=tier[0], variable=self._choice, value=i,
                               font=FONT_NORMAL).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=prices[i], font=FONT_SUBHEADER,
                         text_color=COLOR_TEXT_MAIN).grid(row=0, column=1, sticky="e")
            ctk.CTkLabel(row, text=tier[1], font=FONT_TINY,
                         text_color=COLOR_TEXT_SEC).grid(row=1, column=0, columnspan=2,
                                                         sticky="w")

        ctk.CTkButton(body, text="Оплатить", height=36, corner_radius=R_PANEL,
                      font=FONT_SUBHEADER, fg_color="#c6763a", hover_color="#a95f2c",
                      text_color="#1f1f1f", command=self._pay).pack(fill="x", padx=16,
                                                                    pady=(14, 4))
        ctk.CTkLabel(body, text="Это добровольная поддержка: приложение остаётся бесплатным.",
                     font=FONT_TINY, text_color=COLOR_TEXT_SEC, wraplength=390,
                     justify="center").pack(pady=(0, 14))

    def _pay(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self.on_pay()


class VoiceRecorderDialog(ctk.CTkToplevel):
    """Запись/выбор образца голоса с сохранением в слот.

    Открывается заново — показывает то, что уже лежит в слоте: файл, длительность
    и текст образца. Переключение слота подгружает его содержимое.
    """

    DEFAULT_TEXT = "Привет! Это образец моего голоса для синтеза речи."

    def __init__(self, parent, on_save, slot_id=None, initial_name=None, existing=None):
        super().__init__(parent)
        self.title("Свой голос")
        self.geometry("470x612")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.after(0, lambda: _apply_lang(self))
        _apply_dialog_icon(self)                       # сразу, чтобы не мигал системный
        self.after(150, lambda: _apply_dialog_icon(self))
        self.configure(fg_color=COLOR_BG)

        self.on_save = on_save
        self.existing = existing or {}
        self.rec_fs = 24000
        self.recording = False
        self.stream = None
        self.frames = []
        self.audio_int16 = None
        self.selected_path = None
        self._loaded_path = None
        self.slot_id = str(slot_id) if slot_id is not None else None

        body = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=R_PANEL,
                            border_width=1, border_color=COLOR_BORDER)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text="Образец голоса", font=(FONT_FAMILY, 16, "bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(body, text="5–15 секунд чистой речи. Образец и текст сохраняются в слоте.",
                     font=FONT_SMALL, text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(body, text="Название голоса", font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                     anchor="w").pack(fill="x", padx=18)
        self.entry_name = ctk.CTkEntry(body, height=32, corner_radius=3, font=FONT_NORMAL,
                                       placeholder_text="Например: Мой голос",
                                       fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT_MAIN)
        self.entry_name.pack(fill="x", padx=18, pady=(4, 10))
        try:
            self.entry_name._entry.configure(selectbackground="#d0d0d0", selectforeground="#111111")
        except Exception:
            pass
        if initial_name:
            self.entry_name.insert(0, initial_name)

        sample_card = ctk.CTkFrame(body, fg_color=COLOR_CARD2, corner_radius=4,
                                   border_width=1, border_color=COLOR_BORDER)
        sample_card.pack(fill="x", padx=18, pady=(0, 10))

        self.lbl_sample = ctk.CTkLabel(sample_card, text="Образец ещё не записан", font=FONT_SMALL,
                                       text_color=COLOR_TEXT_SEC, anchor="w")
        self.lbl_sample.pack(fill="x", padx=14, pady=(10, 6))

        row = ctk.CTkFrame(sample_card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))
        row.grid_columnconfigure(0, weight=1)

        self.btn_rec = ctk.CTkButton(row, text="●  Начать запись", command=self.toggle_recording,
                                     height=34, corner_radius=3, font=(FONT_FAMILY, 12, "bold"),
                                     fg_color=COLOR_RED, hover_color=COLOR_RED, text_color="#ffffff")
        self.btn_rec.grid(row=0, column=0, sticky="ew")

        self.btn_play_sample = ctk.CTkButton(row, text="▶", width=40, height=34, corner_radius=3,
                                             font=FONT_NORMAL, fg_color=COLOR_FILL_SOFT,
                                             hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                                             command=self.play_sample)
        self.btn_play_sample.grid(row=0, column=1, padx=(6, 0))

        self.lbl_rec_time = ctk.CTkLabel(sample_card, text="Нажмите и говорите 5–15 секунд",
                                         font=FONT_TINY, text_color=COLOR_TEXT_SEC)
        self.lbl_rec_time.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_file = ctk.CTkButton(body, text="Выбрать WAV-файл", command=self.choose_file,
                                      height=34, corner_radius=3, font=FONT_NORMAL,
                                      fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                      text_color=COLOR_TEXT_MAIN)
        self.btn_file.pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(body, text="Текст образца — что именно произнесено", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=18)
        self.entry_text = ctk.CTkTextbox(body, height=76, corner_radius=3, font=FONT_NORMAL, wrap="word",
                                         fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                                         text_color=COLOR_TEXT_MAIN)
        self.entry_text.pack(fill="x", padx=18, pady=(4, 14))
        self.entry_text.insert("1.0", _tr(self.DEFAULT_TEXT))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(0, 16))
        btns.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btns, text="Сохранить", command=self.save_voice, height=36, corner_radius=3,
                      font=(FONT_FAMILY, 12, "bold"), fg_color=COLOR_ACCENT,
                      hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_ON_ACCENT).grid(row=0, column=0,
                                                                                       sticky="ew", padx=(0, 5))
        ctk.CTkButton(btns, text="Отмена", command=self.destroy, height=36, corner_radius=3,
                      font=FONT_NORMAL, fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_MAIN).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        tb = self.entry_text._textbox
        tb.configure(selectbackground="#d0d0d0", selectforeground="#111111",
                     inactiveselectbackground="#d0d0d0")
        tb.bind("<Button-3>", self._text_menu, add="+")
        for seq in ("<Control-v>", "<Control-V>", "<Control-Shift-v>", "<Control-Shift-V>",
                    "<Shift-Insert>", "<Control-Insert>"):
            tb.bind(seq, self._paste_event, add="+")
        tb.bind("<KeyPress>", self._paste_by_keycode, add="+")
        self._load_slot()
        self.after(120, self._focus_text)

    # ---------- слоты и образец ----------

    @staticmethod
    def _duration(path):
        try:
            with wave.open(path) as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return 0.0

    def _load_slot(self):
        self._stop_recording()
        self.audio_int16 = None
        self.selected_path = None
        self._loaded_path = None

        info = self.existing.get(self.slot_id) or {}
        path = info.get("path")

        if path and os.path.exists(path):
            self._loaded_path = path
            self.lbl_sample.configure(
                text=f"Текущий образец: {os.path.basename(path)} · {self._duration(path):.1f} с",
                text_color=COLOR_TEXT_MAIN)
        elif path:
            self.lbl_sample.configure(text=_tr(f"Файл не найден: {os.path.basename(path)}"), text_color=COLOR_RED)
        else:
            self.lbl_sample.configure(text=_tr("Образец ещё не записан"), text_color=COLOR_TEXT_SEC)

        self.entry_text.delete("1.0", "end")
        self.entry_text.insert("1.0", info.get("text") or _tr(self.DEFAULT_TEXT))
        self.btn_rec.configure(text=_tr("●  Начать запись"))
        self.lbl_rec_time.configure(text=_tr("Нажмите и говорите 5–15 секунд"))

    # ---------- запись ----------

    def toggle_recording(self):
        if not SD_AVAILABLE:
            messagebox.showerror("Микрофон", "Запись недоступна.\nУстановите: pip install sounddevice", parent=self)
            return
        if not self.recording:
            self.frames = []
            try:
                self.stream = sd.InputStream(samplerate=self.rec_fs, channels=1, dtype="int16",
                                             callback=self._audio_callback)
                self.stream.start()
            except Exception as e:
                messagebox.showerror("Микрофон", f"Не удалось открыть микрофон:\n{e}", parent=self)
                return
            self.recording = True
            self.rec_start = time.time()
            self.btn_rec.configure(text=_tr("■  Остановить запись"))
            self._tick()
        else:
            self._stop_recording()
            if self.frames:
                self.audio_int16 = np.concatenate(self.frames)
                self.selected_path = None
                secs = len(self.audio_int16) / self.rec_fs
                self.lbl_sample.configure(text=_tr(f"Записано {secs:.1f} с с микрофона"), text_color=COLOR_GREEN)
            self.btn_rec.configure(text=_tr("●  Записать заново"))

    def _stop_recording(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.recording = False

    def _audio_callback(self, indata, frames_count, t, status):
        self.frames.append(indata.copy())

    def _tick(self):
        if self.recording:
            self.lbl_rec_time.configure(text=_tr(f"Идёт запись… {time.time() - self.rec_start:.1f} с"))
            self.after(200, self._tick)

    def choose_file(self):
        path = filedialog.askopenfilename(title="WAV-файл (5–15 секунд чистой речи)",
                                          filetypes=[("WAV files", "*.wav"), ("All files", "*.*")], parent=self)
        if path:
            self.selected_path = path
            self.audio_int16 = None
            self.lbl_sample.configure(text=_tr(f"Файл: {os.path.basename(path)} · {self._duration(path):.1f} с"),
                                      text_color=COLOR_TEXT_MAIN)

    def play_sample(self):
        path = self.selected_path or self._loaded_path
        if not path or not os.path.exists(path):
            messagebox.showinfo("Образец", "Сначала запишите голос или выберите файл.", parent=self)
            return
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Звук", str(e), parent=self)

    # ---------- буфер обмена ----------

    def _paste(self):
        try:
            text = pyperclip.paste()
        except Exception:
            text = ""
        if not text:
            return
        try:
            self.entry_text._textbox.delete("sel.first", "sel.last")
        except Exception:
            pass
        self.entry_text._textbox.insert("insert", text)

    def _paste_event(self, event=None):
        self._paste()
        return "break"

    def _paste_by_keycode(self, event):
        """Ctrl+V / Shift+Insert независимо от раскладки (VK_V=86, VK_INSERT=45)."""
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        if (event.keycode == 86 and ctrl) or (event.keycode == 45 and (ctrl or shift)):
            return self._paste_event(event)
        return None

    def _focus_text(self):
        try:
            self.entry_text.focus_set()
            self.entry_text._textbox.mark_set("insert", "end-1c")
            self.entry_text._textbox.see("end-1c")
        except Exception:
            pass

    def _text_menu(self, event):
        menu = Menu(self, tearoff=0)
        menu.add_command(label=_tr("Вставить"), command=self._paste)
        menu.add_command(label=_tr("Выделить всё"),
                         command=lambda: self.entry_text._textbox.tag_add("sel", "1.0", "end-1c"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    # ---------- сохранение ----------

    def save_voice(self):
        text = self.entry_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Внимание", "Введите текст образца.", parent=self)
            return

        name = (self.entry_name.get() or "").strip()
        if not name:
            messagebox.showwarning("Внимание", "Введите название голоса.", parent=self)
            return

        if self.selected_path:
            final_path = self.selected_path
        elif self.audio_int16 is not None:
            secs = len(self.audio_int16) / self.rec_fs
            if secs < 2:
                messagebox.showwarning("Внимание", "Запись слишком короткая — нужно 5–15 секунд речи.", parent=self)
                return
            final_path = os.path.join(BASE_DIR, f"my_voice_{self.slot_id}.wav")
            with wave.open(final_path, "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(self.rec_fs)
                f.writeframes(self.audio_int16.tobytes())
        elif self._loaded_path:
            final_path = self._loaded_path
        else:
            messagebox.showwarning("Внимание", "Запишите голос с микрофона\nили выберите WAV-файл.", parent=self)
            return

        self.on_save(final_path, text, self.slot_id, name)
        self.destroy()


class PdfArticlesDialog(ctk.CTkToplevel):
    def __init__(self, parent, articles, on_pick):
        super().__init__(parent)
        self.title("Статьи в журнале")
        self.geometry("600x540")
        self.transient(parent)
        self.grab_set()
        self.after(0, lambda: _apply_lang(self))
        _apply_dialog_icon(self)                       # сразу, чтобы не мигал системный
        self.after(150, lambda: _apply_dialog_icon(self))
        self.configure(fg_color=COLOR_BG)

        body = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=R_PANEL,
                            border_width=1, border_color=COLOR_BORDER)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text=f"Найдено статей: {len(articles)}", font=(FONT_FAMILY, 16, "bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(body, text="Выберите, что вставить в поле текста", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=18, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(body, fg_color=COLOR_CARD, corner_radius=4,
                                        border_width=1, border_color=COLOR_BORDER,
                                        scrollbar_button_color=COLOR_BORDER)
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        for a in articles:
            ctk.CTkButton(scroll, text=a["title"][:90], anchor="w", height=34, corner_radius=3,
                          fg_color="transparent", hover_color=COLOR_ACCENT_SOFT,
                          text_color=COLOR_TEXT_MAIN, font=FONT_SMALL,
                          command=lambda a=a: (on_pick(a), self.destroy())).pack(fill="x", pady=2)


class SegmentToggle(ctk.CTkFrame):
    """Переключатель из 2+ пунктов: активный — тёмная заливка и белый текст."""

    def __init__(self, master, values, command=None, height=32, btn_width=None, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD2, corner_radius=3, border_width=1,
                         border_color=COLOR_BORDER, **kwargs)
        self._values = list(values)
        self._command = command
        self._buttons = {}
        self._current = self._values[0] if self._values else None
        self._height = max(20, height - 4)
        for i, val in enumerate(self._values):
            btn = ctk.CTkButton(self, text=val, height=self._height, corner_radius=2,
                                font=FONT_TINY, border_width=0,
                                width=140 if btn_width is None else btn_width,
                                fg_color="transparent", hover_color=COLOR_SELECT,
                                text_color=COLOR_TEXT_SEC,
                                command=lambda v=val: self._choose(v))
            btn.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
            self.grid_columnconfigure(i, weight=1)
            self._buttons[val] = btn
        self._refresh()

    def _choose(self, value):
        if value == self._current:
            return
        self._current = value
        self._refresh()
        if self._command:
            self._command(value)

    def _refresh(self):
        for val, btn in self._buttons.items():
            if val == self._current:
                btn.configure(fg_color=COLOR_SEG_ON, text_color=COLOR_SEG_ON_TEXT,
                              hover_color=COLOR_SEG_ON_HOVER)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_SEC,
                              hover_color=COLOR_SELECT)

    def set(self, value):
        if value in self._buttons:
            self._current = value
            self._refresh()

    def get(self):
        return self._current


class PresetDialog(ctk.CTkToplevel):
    """Свой уровень сжатия: название, доля объёма и промпт."""

    def __init__(self, parent, name="", ratio=0.5, prompt="", on_save=None, on_delete=None):
        super().__init__(parent)
        self.on_save = on_save
        self.on_delete = on_delete

        self.title("Свой уровень сжатия")
        self.geometry("480x520")
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)
        self.grab_set()
        self.after(0, lambda: _apply_lang(self))
        _apply_dialog_icon(self)                       # сразу, чтобы не мигал системный
        self.after(150, lambda: _apply_dialog_icon(self))
        self.attributes("-topmost", True)

        ctk.CTkLabel(self, text="Свой уровень сжатия", font=FONT_SUBHEADER,
                     text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", padx=18, pady=(16, 10))

        body = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=6,
                            border_width=1, border_color=COLOR_BORDER)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        ctk.CTkLabel(body, text="Название в списке", font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                     anchor="w").pack(fill="x", padx=14, pady=(12, 0))
        self.entry_name = ctk.CTkEntry(body, height=30, corner_radius=3, font=FONT_NORMAL,
                                       fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT_MAIN)
        self.entry_name.pack(fill="x", padx=14, pady=(4, 10))
        self.entry_name.insert(0, name)
        try:
            self.entry_name._entry.configure(selectbackground=COLOR_SELECT_TEXT[0],
                                             selectforeground="#111111")
        except Exception:
            pass

        ctk.CTkLabel(body, text="Сжатие до, % исходного текста", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=14)
        self.entry_pct = ctk.CTkEntry(body, height=30, corner_radius=3, font=FONT_NORMAL,
                                      fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                                      text_color=COLOR_TEXT_MAIN)
        self.entry_pct.pack(fill="x", padx=14, pady=(4, 10))
        self.entry_pct.insert(0, str(max(5, min(100, int(round(ratio * 100))))))

        ctk.CTkLabel(body, text="Промпт — что сделать с текстом", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=14)
        self.text_prompt = ctk.CTkTextbox(body, height=210, corner_radius=3, font=FONT_SMALL,
                                          wrap="word", fg_color=COLOR_CARD2, border_width=1,
                                          border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN)
        self.text_prompt.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        if prompt:
            self.text_prompt.insert("1.0", prompt)
        try:
            self.text_prompt._textbox.configure(selectbackground=COLOR_SELECT_TEXT[0],
                                                selectforeground="#111111")
        except Exception:
            pass

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(btns, text="Сохранить", height=32, corner_radius=3, font=FONT_NORMAL,
                      fg_color=COLOR_TEXT_MAIN, hover_color="#4a4a4a", text_color="#ffffff",
                      command=self._save).pack(side="right", fill="x", expand=True, padx=(6, 0))
        ctk.CTkButton(btns, text="Отмена", height=32, corner_radius=3, font=FONT_NORMAL,
                      fg_color=COLOR_CARD2, hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                      border_width=1, border_color=COLOR_BORDER,
                      command=self.destroy).pack(side="right", fill="x", expand=True, padx=(6, 0))
        if on_delete:
            ctk.CTkButton(btns, text="Удалить", height=32, corner_radius=3, font=FONT_NORMAL,
                          fg_color=COLOR_CARD2, hover_color="#e8d0d0", text_color="#8a2b2b",
                          border_width=1, border_color=COLOR_BORDER,
                          command=self._delete).pack(side="left", fill="x", expand=True)

    def _save(self):
        name = (self.entry_name.get() or "").strip()
        if not name:
            messagebox.showwarning("Внимание", "Введите название.", parent=self)
            return
        try:
            pct = int(float((self.entry_pct.get() or "").strip().replace("%", "").replace(",", ".")))
        except Exception:
            messagebox.showwarning("Внимание", "Укажите процент числом, например 40.", parent=self)
            return
        if pct < 5 or pct > 100:
            messagebox.showwarning("Внимание", "Процент должен быть от 5 до 100.", parent=self)
            return
        prompt = self.text_prompt.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showwarning("Внимание", "Напишите промпт — что сделать с текстом.", parent=self)
            return
        if self.on_save:
            self.on_save(name, pct / 100.0, prompt)
        self.destroy()

    def _delete(self):
        if messagebox.askyesno("Удалить", "Удалить этот уровень сжатия?", parent=self):
            if self.on_delete:
                self.on_delete()
            self.destroy()


# ==================== ЯЗЫК ИНТЕРФЕЙСА (RU / EN) ====================
# Переводится только интерфейс: надписи, кнопки, меню, окна сообщений и статусы.
# Название Free AI Reader, аббревиатура FAIR, имена голосов, пресеты и промпты
# модели остаются без изменений.
UI_LANG = "ru"

_PAIRS = [('ИСТОЧНИК', 'SOURCE'), ('МОДЕЛЬ ИИ', 'AI MODEL'), ('ОЗВУЧКА', 'VOICE'), ('Ссылка на статью', 'Article link'), ('Вставьте ссылку, текст или файл — либо наберите текст в поле справа.', 'Paste a link, text or file — or type in the field on the right.'), ('Вставьте текст статьи, ссылку или файл — или просто печатайте здесь.\n\n', 'Paste an article link, text or file — or just type here.\n\n'), ('Вставьте текст или ссылку', 'Paste text or a link'), ('Выберите, что вставить в поле текста', 'Choose what to insert into the text field'), ('Вставить', 'Paste'), ('Копировать', 'Copy'), ('Вырезать', 'Cut'), ('Выделить всё', 'Select all'), ('Другая модель', 'Another model'), ('Новый…', 'New…'), ('Удалить', 'Delete'), ('Контекст', 'Context'), ('Сжатие', 'Compression'), ('Скорость', 'Speed'), ('Запустить анализ', 'Run analysis'), ('Остановить', 'Stop'), ('Очистить', 'Clear'), ('Готово', 'Ready'), ('Сохранить', 'Save'), ('Отмена', 'Cancel'), ('Файл', 'File'), ('Промпт — что сделать с текстом', 'Prompt — what to do with the text'), ('Свой уровень сжатия', 'Custom compression level'), ('Сжатие до, % исходного текста', 'Compress to, % of the original text'), ('Название голоса', 'Voice name'), ('Название в списке', 'Name in the list'), ('Например: Мой голос', 'For example: My voice'), ('5–15 секунд чистой речи. Образец и текст сохраняются в слоте.', '5–15 seconds of clean speech. The sample and its text are saved in the slot.'), ('Нажмите и говорите 5–15 секунд', 'Press and speak for 5–15 seconds'), ('Образец ещё не записан', 'No sample recorded yet'), ('Образец голоса', 'Voice sample'), ('Текст образца — что именно произнесено', 'Sample text — what exactly is spoken'), ('Озвучивать сразу после анализа', 'Speak right after the analysis'), ('🎙  Образец голоса', '🎙  Voice sample'), ('●  Начать запись', '●  Start recording'), ('■  Остановить запись', '■  Stop recording'),        ('Озвучить', 'Speak'), ('■  Стоп', '■  Stop'), ('Пауза', 'Paused'), ('↩ Исходный текст', '↩ Original text'), ('Процессор', 'CPU'), ('Видеокарта', 'GPU'), ('Piper: процессор, видеокарта не нужна', 'Piper: CPU, no graphics card needed'), ('⚠ Vox требует видеокарту с 8 ГБ видеопамяти', '⚠ Vox needs a graphics card with 8 GB of video memory'), ('ОЗУ: —', 'RAM: —'), ('✅ Готово. Вставьте ссылку, текст или файл.', '✅ Ready. Paste a link, text or file.'), ('✅ Ссылка вставлена', '✅ Link inserted'), ('↩ Возвращён исходный текст', '↩ Original text restored'), ('Обработка…', 'Processing…'), ('Генерация текста…', 'Generating text…'), ('Воспроизведение…', 'Playing…'), ('Остановлено', 'Stopped'), ('Отменено', 'Cancelled'), ('Ошибка звука', 'Audio error'), ('⏳ Синтез...', '⏳ Synthesizing...'), ('❌ Ошибка', '❌ Error'), ('Загрузка статьи…', 'Loading the article…'), ('Анализ вашего текста…', 'Analyzing your text…'), ('Анализ нейросетью…', 'Neural analysis…'), ('Загрузка модели', 'Loading the model'), ('Загрузка на GPU', 'Loading to GPU'), ('Загрузка модели на видеокарту…', 'Loading the model onto the GPU…'), ('Загрузка модели на видеокарту', 'Loading the model onto the GPU'), ('Модель загружена', 'Model loaded'), ('Анализ завершён', 'Analysis finished'), ('Синтез завершён', 'Synthesis finished'), ('Модель GGUF', 'GGUF model'), ('Модель на GPU', 'Model on GPU'), ('Модель ИИ не загружена.', 'The AI model is not loaded.'), ('Модель для анализа не выбрана.', 'No analysis model selected.'), ('Выбрана модель. Загрузится при анализе.', 'Model selected. It loads when the analysis starts.'), ('Сканирование моделей…', 'Scanning models…'), ('Подготовка текста', 'Preparing the text'), ('Проверка объёма', 'Checking the length'), ('⏳ Загрузка VoxCPM2...', '⏳ Loading VoxCPM2...'), ('⏳ Загрузка VoxCPM2 (веса ~5 ГБ)...', '⏳ Loading VoxCPM2 (~5 GB of weights)...'), ('⏳ Подготовка текста…', '⏳ Preparing the text…'), ('⏹ Анализ отменён', '⏹ Analysis cancelled'), ('⏹ Синтез отменён', '⏹ Synthesis cancelled'), ('⏹ Остановлено', '⏹ Stopped'), ('♻️ Модель уже в памяти — переиспользую', '♻️ The model is already in memory — reusing it'), ('✅ VoxCPM2 готова (GPU)', '✅ VoxCPM2 ready (GPU)'), ('❌ VoxCPM2 недоступна', '❌ VoxCPM2 unavailable'), ('❌ Ошибка загрузки', '❌ Loading error'), ('❌ Файл голоса не найден', '❌ Voice file not found'), ('🧹 Видеопамять освобождена после анализа', '🧹 Video memory freed after the analysis'), ('🚀 GPU-сервер:', '🚀 GPU server:'), ('Режим: видеокарта (CUDA)', 'Mode: GPU (CUDA)'), ('Режим: процессор (CUDA выключена)', 'Mode: CPU (CUDA off)'), ('Движок: VoxCPM2 (GPU).', 'Engine: VoxCPM2 (GPU).'), ('Не выбран голос для озвучки: запишите образец «🎙 Образец голоса».', 'No voice selected for speech: record a sample with “🎙 Voice sample”.'), ('Воспроизведение недоступно.', 'Playback is unavailable.'), ('Запись невозможна.', 'Recording is unavailable.'), ('Внимание', 'Warning'), ('Ошибка TTS', 'TTS error'), ('Ошибка VoxCPM2', 'VoxCPM2 error'), ('Микрофон', 'Microphone'), ('Звук', 'Audio'), ('Буфер обмена', 'Clipboard'), ('Образец', 'Sample'), ('Анализ', 'Analysis'), ('Слишком длинный текст', 'Text too long'), ('WAV-файл (5–15 секунд чистой речи)', 'WAV file (5–15 seconds of clean speech)'), ('Выберите модель .gguf для анализа текста', 'Choose a .gguf model for text analysis'), ('Выберите файл (pdf, docx, txt)', 'Choose a file (pdf, docx, txt)'), ('Нечего анализировать', 'Nothing to analyze'), ('Текст слишком короткий или пустой', 'The text is too short or empty'), ('Буфер обмена пуст', 'The clipboard is empty'), ('Буфер пуст. Скопируйте текст для озвучки.', 'The clipboard is empty. Copy the text you want spoken.'), ('Нет текста для озвучки.', 'There is no text to speak.'), ('Голос не выбран.', 'No voice is selected.'), ('Сначала запишите голос или выберите файл.', 'Record a voice first or choose a file.'), ('Введите название голоса.', 'Enter the voice name.'), ('Введите название.', 'Enter a name.'), ('Введите текст образца.', 'Enter the sample text.'), ('Введите новый процент сжатия.', 'Enter the new compression percentage.'), ('Напишите промпт — что сделать с текстом.', 'Write a prompt — what to do with the text.'), ('Процент должен быть от 5 до 100.', 'The percentage must be from 5 to 100.'), ('Укажите процент числом, например 40.', 'Write the percentage as a number, for example 40.'), ('Выберите модель ИИ в карточке «МОДЕЛЬ ИИ»', 'Choose an AI model in the “AI MODEL” card'), ('Запись слишком короткая — нужно 5–15 секунд речи.', 'The recording is too short — 5–15 seconds of speech are needed.'), ('Запишите голос с микрофона\nили выберите WAV-файл.', 'Record a voice with the microphone\nor choose a WAV file.'), ('Запишите голос: «🎙 Образец голоса»', 'Record a voice: “🎙 Voice sample”'), ('Запись недоступна.\nУстановите: pip install sounddevice', 'Recording is unavailable.\nInstall: pip install sounddevice'), ('Старый формат .doc не поддерживается.\nСохраните документ как .docx.', 'The old .doc format is not supported.\nSave the document as .docx.'), ('Установите: pip install pypdf', 'Install: pip install pypdf'), ('Установите: pip install python-docx', 'Install: pip install python-docx'), ('В файле не найден текст (возможно, скан без текстового слоя).', 'No text found in the file (possibly a scan without a text layer).'), ('Нужен файл модели в формате .gguf', 'A model file in .gguf format is required'), ('Удалить этот уровень сжатия?', 'Delete this compression level?'), ('Нужен текст: вставьте ссылку, текст или файл.', 'Text is required: paste a link, text or file.'), ('Хорошо', 'OK')]

_PAIRS += [
    # заголовки отдельных окон и динамические подписи (с образцом значений —
    # числа, имена файлов и имена в кавычках подставляются вместо #)
    ("Свой голос", "Custom voice"),
    ("Статьи в журнале", "Articles in the journal"),
    ("📖 Весь журнал целиком", "📖 The whole journal"),
    ("Найдено статей: 3", "Articles found: 3"),
    ("Текущий образец: sample.wav · 6.4 с", "Current sample: sample.wav · 6.4 s"),
    ("Файл не найден: sample.wav", "File not found: sample.wav"),
    ("Файл: sample.wav · 6.4 с", "File: sample.wav · 6.4 s"),
    ("Записано 5.0 с с микрофона", "Recorded 5.0 s from the microphone"),
    ("Идёт запись… 3.2 с", "Recording… 3.2 s"),
    ("Голос «Мой голос» не найден. Нажмите «🎙 Образец голоса».",
     "Voice “My voice” not found. Press “🎙 Voice sample”."),
    ("✅ Голос «Мой голос» сохранён", "✅ Voice “My voice” saved"),
    ("✅ Голос «Мой голос» активен", "✅ Voice “My voice” is active"),
    ("✅ Уровень сжатия «Мой уровень» сохранён", "✅ Compression level “My level” saved"),
    ("🗑 Уровень «Мой уровень» удалён", "🗑 Level “My level” deleted"),
    ("Синтез 2/5", "Synthesis 2/5"),
    ("✅ Вставлено: article.txt. Анализ пойдёт по этому тексту.",
     "✅ Inserted: article.txt. The analysis will use this text."),
    ("✅ Воспроизводится (Vox, ×1.00)", "✅ Playing (Vox, ×1.00)"),
    ("Слот «Мой голос» пуст — запишите образец голоса.",
     "The slot “My voice” is empty — record a voice sample."),
    ("Уровень сжатия «Мой уровень»", "Compression level “My level”"),
]

_PAIRS += [
    ("●  Записать заново", "●  Record again"),
    ("ОЗУ: 7 ГБ (своб. 3)", "RAM: 7 GB (free 3)"),
    ("1 024 ток. · ≈ 1.2 ГБ", "1 024 tok · ≈ 1.2 GB"),
    ("1 234 зн.", "1 234 chars"),
    ("0 зн.", "0 chars"),
    ("✅ Воспроизводится (Piper, ×1.00)", "✅ Playing (Piper, ×1.00)"),
]

_PAIRS += [
    ("⚠️ Текст длиннее контекста модели", "⚠️ The text is longer than the model context"),
    ("Vox не синтезировал ни одной фразы — проверьте голос-образец.",
     "Vox did not synthesize a single phrase — check the voice sample."),
    ("Нет свободного порта для GPU-сервера (8123–8126 заняты)",
     "No free port for the GPU server (8123–8126 are busy)"),
]

_PAIRS += [
    ("Документы", "Documents"),
    ("Все файлы", "All files"),
    ("WAV-файлы", "WAV files"),
    ("Модель ИИ", "AI model"),
]

# —— названия уровней сжатия, слоты голосов, пример текста образца ——
_PAIRS += [
    ("Только суть (10%)", "Main point only (10%)"),
    ("Очень кратко (30%)", "Very short (30%)"),
    ("Кратко (50%)", "Short (50%)"),
    ("Подробно (80%)", "Detailed (80%)"),
    ("Речь для озвучки (100%)", "Speech for narration (100%)"),
    ("Перевод на английский (100%)", "Translate into English (100%)"),
    ("Новый 1", "New 1"),
    ("Свой 1", "Custom 1"),
    ("Привет! Это образец моего голоса для синтеза речи.",
     "Hello! This is a sample of my voice for speech synthesis."),
    ("Благодарить", "Donate"),
    ("Поддержка", "Support"),
    ("Понравился Free AI Reader?", "Like Free AI Reader?"),
    ("Выбери, насколько он тебе помог.", "Choose how much it helped you."),
    ("Работает как надо", "It works fine"),
    ("Без нареканий: открываю и слушаю.", "No complaints: I open it and listen."),
    ("Очень удобно", "Very convenient"),
    ("Озвучка статей каждый день.", "I listen to articles every day."),
    ("Экономит время", "It saves me time"),
    ("Сжатие и озвучка делают своё дело.", "Compression and narration do their job."),
    ("Восторг", "Delighted"),
    ("Такого больше нигде нет, спасибо!", "Nothing like this anywhere else, thank you!"),
    ("Оплатить", "Pay"),
    ("Это добровольная поддержка: приложение остаётся бесплатным.",
     "This is voluntary support: the app stays free."),
    ("10 ₽", "$0.10"),
    ("100 ₽", "$1"),
    ("500 ₽", "$5"),
    ("1000 ₽", "$10"),
    ("❤️ Открыта страница поддержки", "❤️ Support page opened"),
]

_PAIRS += [
    ("ТЕКСТ", "TEXT"),
    ("Контекст: 4096 токенов", "Context: 4096 tokens"),
    ("Движок: Piper (CPU). Голос: «Маша»", "Engine: Piper (CPU). Voice: “Masha”"),
    ("Движок: Piper (CPU).", "Engine: Piper (CPU)."),
    ("✅ Настройки восстановлены: Piper (CPU), «Маша».",
     "✅ Settings restored: Piper (CPU), “Masha”."),
    ("✅ Настройки восстановлены: Vox (GPU), «Маша».",
     "✅ Settings restored: Vox (GPU), “Masha”."),
    ("Вставьте текст статьи, ссылку или файл — или просто печатайте здесь.\n\n"
     "Ctrl+V — вставить из буфера. Всё, что есть в этом поле, считается источником:\n"
     "анализ пойдёт по нему, а не по ссылке.",
     "Paste an article link, text or file — or just type here.\n\n"
     "Ctrl+V — paste from the clipboard. Whatever is in this box is the source:\n"
     "the analysis uses it, not the link."),
    ("Модель для анализа: model.gguf — загрузится при запуске анализа.",
     "Analysis model: model.gguf — it loads when the analysis starts."),
    ("✅ Голос 'Маша' активен", "✅ Voice 'Masha' is active"),
]

_PAIRS += [
    # ---- v10: статусы и ошибки, которые оставались на русском
    ("✅ Настройки восстановлены: Vox, «Свой 1».",
     "✅ Settings restored: Vox, “Custom 1”."),
    ("✅ Настройки восстановлены: Piper, «Свой 1».",
     "✅ Settings restored: Piper, “Custom 1”."),
    ("⏳ Загрузка VoxCPM2 (cuda)...", "⏳ Loading VoxCPM2 (cuda)..."),
    ("⏳ Загрузка VoxCPM2 (auto)...", "⏳ Loading VoxCPM2 (auto)..."),
    ("✅ Модель на видеокарте (порт 8123)", "✅ Model is on the GPU (port 8123)"),
    ("Загрузка модели «Гугл» · контекст 8192…",
     "Loading model “Google” · context 8192…"),
    ("⏳ Синтез VoxCPM2 (GPU, ×1.00)...", "⏳ VoxCPM2 synthesis (GPU, ×1.00)..."),
    ("✅ Анализ завершён · 421 зн. · 30% от исходного",
     "✅ Analysis done · 421 chars · 30% of original"),
    ("421 зн. · 30% от исходного", "421 chars · 30% of original"),
    ("1234 токенов", "1234 tokens"),
    ("1.0 с", "1.0 s"),
    ("12.3 ток/с", "12.3 tok/s"),
    ("1234 зн.", "1234 chars"),
    ("123 ток. · ≈ 1.0 ГБ", "123 tok. · ≈ 1.0 GB"),
    ("Синтез 1/9", "Synthesis 1/9"),
    ("Анализ (видеокарта)", "Analysis (GPU)"),
    ("Записано 1.0 с с микрофона", "Recorded 1.0 s from the microphone"),
    ("Идёт запись… 1.0 с", "Recording… 1.0 s"),
    ("Файл: sample.wav · 1.0 с", "File: sample.wav · 1.0 s"),
    ("Голос «Свой 1» не найден. Нажмите «🎙 Образец голоса».",
     "Voice “Custom 1” not found. Click “🎙 Voice sample”."),
    ("Слот «Свой 1» пуст — запишите образец голоса.",
     "Slot “Custom 1” is empty — record a voice sample."),
    ("Модель уже в памяти", "Model is already in memory"),
    ("Piper не сгенерировал аудио", "Piper produced no audio"),
    ("Не удалось загрузить VoxCPM2", "Failed to load VoxCPM2"),
    ("GPU-сервер не ответил за 180 секунд",
     "The GPU server did not respond within 180 seconds"),
    ("Не удалось подключиться к серверу модели (CUDA). Проверьте, что он запущен.",
     "Could not connect to the model server (CUDA). Make sure it is running."),
]


_PAIRS += [
    ("VoxCPM не установлен.\n\npip install voxcpm\n"
     "или: pip install git+https://github.com/OpenBMB/VoxCPM.git",
     "VoxCPM is not installed.\n\npip install voxcpm\n"
     "or: pip install git+https://github.com/OpenBMB/VoxCPM.git"),
]

_PAIRS += [
    ("🎙 Образец голоса", "🎙 Voice sample"),
    # ---- диалог загрузки модели Gemma ----
    ("Модель ИИ", "AI model"),
    ("Нужна модель для анализа текста", "A model is needed for text analysis"),
    ("Модель не скачана", "Model not downloaded"),
    ("Нет модели — нажмите ⬇", "No model — press ⬇"),
    # ---- голоса Piper ----
    ("Голоса Piper", "Piper voices"),
    ("Установлен", "Installed"),
    ("Загрузка…", "Downloading…"),
    ("Закрыть", "Close"),
    ("Голос установлен", "Voice installed"),
    ("Голоса Irina и Ruslan — CC BY-NC-SA: только для личного использования, "
     "в публичную сборку не входят.",
     "Irina and Ruslan voices are CC BY-NC-SA: personal use only, "
     "not part of the public build."),
    ("Ирина · женский, русский", "Irina · female, Russian"),
    ("Руслан · мужской, русский", "Ruslan · male, Russian"),
    ("Amy · женский, английский", "Amy · female, English"),
    ("Alan · мужской, английский", "Alan · male, English"),
    ("Thorsten · мужской, немецкий", "Thorsten · male, German"),
    ("Устанавливаются голоса", "Installing voices"),
    ("Ирина и Руслан, ≈126 МБ — один раз, дальше работают без интернета.",
     "Irina and Ruslan, ≈126 MB — once, then they work offline."),
    ("Отменено", "Cancelled"),
    ("Голоса Ирина и Руслан установлены", "Irina and Ruslan voices are installed"),
    ("Установить дополнение Vox", "Install the Vox add-on"),
    ("Прошло", "Elapsed"),
    ("Vox установлен", "Vox installed"),
    ("Движок Vox", "Vox engine"),
    ("Дополнение Vox", "Vox add-on"),
    ("Устанавливается дополнение Vox", "Installing the Vox add-on"),
    ("Не получилось", "Failed"),
    ("Python, torch и VoxCPM ставятся в папку приложения. "
     "Первый раз это занимает 5–15 минут.",
     "Python, torch and VoxCPM are installed into the app folder. "
     "The first run takes 5–15 minutes."),
    ("Vox — нейроголос по образцу с микрофона.\n\n"
     "Нужен пакет дополнения: переносимый Python + torch + VoxCPM, "
     "≈1,5 ГБ загрузки и ~3 ГБ на диске.\n\nСкачать сейчас?",
     "Vox is a neural voice cloned from a microphone sample.\n\n"
     "It needs an add-on package: portable Python + torch + VoxCPM, "
     "≈1.5 GB download and ~3 GB on disk.\n\nDownload now?"),
    ("Для Vox нужно дополнение (переносимый Python + torch + VoxCPM, ≈1,5–2,5 ГБ).\n\n"
     "Скачать и установить сейчас?",
     "Vox needs an add-on (portable Python + torch + VoxCPM, ≈1.5–2.5 GB).\n\n"
     "Download and install it now?"),
    ("Дополнение Vox не установлено.\n\n"
     "Переключите «Озвучка» на Vox — приложение предложит скачать "
     "пакет (переносимый Python + torch + VoxCPM, ≈1,5–2,5 ГБ). "
     "До этого работает Piper с голосами Ирина и Руслан.",
     "The Vox add-on is not installed.\n\n"
     "Switch “Voice” to Vox — the app will offer to download the package "
     "(portable Python + torch + VoxCPM, ≈1.5–2.5 GB). "
     "Until then Piper works with the Irina and Ruslan voices."),
    ("Модель скачана", "Model downloaded"),
    ("Модель уже скачана", "Model already downloaded"),
    ("Скачать", "Download"),
    ("Позже", "Later"),
    ("Отмена", "Cancel"),
    ("Отмена…", "Cancelling…"),
    ("Продолжить", "Resume"),
    ("Повторить", "Retry"),
    ("МБ", "MB"),
    ("Ошибка загрузки", "Download failed"),
    ("Больше не предлагать", "Don't ask again"),
    ("Загрузка остановлена — можно продолжить позже", "Download stopped — you can resume later"),
    ("Gemma 4 E4B, ≈5 ГБ — скачивается один раз с Hugging Face.\n"
     "Дальше анализ идёт без интернета. Если прервать, докачается с места.",
     "Gemma 4 E4B, ≈5 GB — downloaded once from Hugging Face.\n"
     "Analysis then runs offline. If you stop, it resumes where it left off."),
]

TR_RU_EN = dict(_PAIRS)
TR_EN_RU = {en: ru for ru, en in _PAIRS}


def _shape(s):
    """Каркас строки и значения: числа, файлы и имена в кавычках -> #.

    Так одна и та же фраза со своими цифрами ("Синтез 3/9") узнаёт шаблон
    перевода ("Synthesis #/#"), а значения подставляются обратно по порядку.
    """
    vals = []

    def _put(m):
        vals.append(m.group(0))
        return "#"

    s = re.sub(r"[«\"'“]([^«»\"'”“]{1,80})[»\"'”]", _put, s)
    s = re.sub(r"[\w./\\:%-]+\.(wav|gguf|onnx|pdf|docx|txt|mp3|doc)", _put, s, flags=re.I)
    s = re.sub(r"\d[\d\s.,]*", _put, s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(), vals


def _fill(shape, vals):
    """Вставляет значения обратно в каркас по порядку."""
    parts = shape.split("#")
    if len(parts) - 1 != len(vals):
        return shape
    out = parts[0]
    for v, p in zip(vals, parts[1:]):
        out += v + p
    return out


TR_RU_EN_T = {}
TR_EN_RU_T = {}
for _ru, _en in _PAIRS:
    _sh_ru, _v_ru = _shape(_ru)
    _sh_en, _v_en = _shape(_en)
    if _sh_ru == _sh_en and _v_ru == _v_en:
        continue
    if len(_sh_en.split("#")) - 1 == len(_v_ru):
        TR_RU_EN_T.setdefault(_sh_ru, (_sh_en, len(_v_ru)))
    if len(_sh_ru.split("#")) - 1 == len(_v_en):
        TR_EN_RU_T.setdefault(_sh_en, (_sh_ru, len(_v_en)))


# Фразы-«обёртки»: после них идёт свободный текст (сообщение об ошибке и т.п.)
_PREFIX_PAIRS = [
    ("❌ Ошибка: ", "❌ Error: "),
    ("Не удалось загрузить VoxCPM2: ", "Failed to load VoxCPM2: "),
    ("VoxCPM2 generate не сработал: ", "VoxCPM2 generate failed: "),
    ("Не удалось запустить GPU-сервер: ", "Failed to start the GPU server: "),
    ("Ошибка сервера модели: ", "Model server error: "),
    ("Файл модели не найден: ", "Model file not found: "),
    ("Файл не найден: ", "File not found: "),
    ("Не удалось открыть микрофон:\n", "Could not open the microphone:\n"),
    ("CUDA-сборка llama.cpp не найдена:\n", "The CUDA build of llama.cpp was not found:\n"),
    ("GPU-сервер завершился при загрузке модели.\n",
     "The GPU server stopped while loading the model.\n"),
    ("VoxCPM не установлен.\n\npip install voxcpm\n", "VoxCPM is not installed.\n\npip install voxcpm\n"),
]

_GEN_PAT = (("Свой ", "Custom "), ("Новый ", "New "))


def _tr_gen(word):
    """Системные имена по образцу: Свой 3 <-> Custom 3, Новый 2 <-> New 2."""
    for ru, en in _GEN_PAT:
        if UI_LANG == "en" and word.startswith(ru) and word[len(ru):].isdigit():
            return en + word[len(ru):]
        if UI_LANG == "ru" and word.startswith(en) and word[len(en):].isdigit():
            return ru + word[len(en):]
    return None


def _tr_val(val):
    """Системное имя в статусе переводим, имя, которое придумал пользователь, оставляем."""
    if not isinstance(val, str) or len(val) < 3:
        return val
    table = TR_RU_EN if UI_LANG == "en" else TR_EN_RU
    for q_open, q_close in (("«", "»"), ("“", "”"), ('"', '\"'), ("'", "'")):
        if val.startswith(q_open) and val.endswith(q_close):
            inner = val[1:-1]
            hit = table.get(inner) or _tr_gen(inner)
            if hit:
                n_open, n_close = ("“", "”") if UI_LANG == "en" else ("«", "»")
                return n_open + hit + n_close
            return val
    return table.get(val) or _tr_gen(val) or val


def _tr(text, _deep=0):
    """Строка интерфейса на текущем языке: есть перевод — берёт его, иначе — как есть."""
    if not isinstance(text, str) or not text.strip():
        return text
    if UI_LANG == "en":
        table, ttable = TR_RU_EN, TR_RU_EN_T
    else:
        table, ttable = TR_EN_RU, TR_EN_RU_T
    hit = table.get(text)
    if hit is not None:
        return hit
    shape, vals = _shape(text)
    tgt, need = ttable.get(shape, (None, 0))
    if tgt is not None:
        if len(vals) != need:
            return _fill(tgt, [])
        return _fill(tgt, [_tr_val(v) for v in vals])
    if _deep < 2:                      # обёртку можно снять дважды: «Ошибка: …: …»
        for pre_ru, pre_en in _PREFIX_PAIRS:
            want, rep = (pre_ru, pre_en) if UI_LANG == "en" else (pre_en, pre_ru)
            if text.startswith(want):
                return rep + _tr(text[len(want):], _deep + 1)
    return text


def _lang_optmenu(om):
    """Список выбора: показываем значение на языке интерфейса, внутри — исходное."""
    try:
        lab = getattr(om, "_text_label", None)
        if lab is not None:
            lab.configure(text=_tr(om.get()))
    except Exception:
        pass
    dm = getattr(om, "_dropdown_menu", None)
    if dm is not None:
        try:
            for i, val in enumerate(list(om.cget("values"))):
                dm.entryconfigure(i, label=_tr(val))
        except Exception:
            pass


_om_set_orig = ctk.CTkOptionMenu.set


def _om_set_lang(self, value):
    _om_set_orig(self, value)
    _lang_optmenu(self)


ctk.CTkOptionMenu.set = _om_set_lang

_om_ddc_orig = ctk.CTkOptionMenu._dropdown_callback


def _om_ddc_lang(self, value):
    _om_ddc_orig(self, value)
    _lang_optmenu(self)


ctk.CTkOptionMenu._dropdown_callback = _om_ddc_lang

_om_conf_orig = ctk.CTkOptionMenu.configure


def _om_conf_lang(self, require_redraw=False, **kwargs):
    _om_conf_orig(self, require_redraw, **kwargs)
    if "values" in kwargs:
        _lang_optmenu(self)


ctk.CTkOptionMenu.configure = _om_conf_lang


def _apply_lang(root):
    """Обходит виджеты окна и ставит надписи на текущий язык интерфейса.

    Списки выбора (модели, голоса, уровни сжатия) не переводятся: их значения
    хранятся в настройках и служат ключами.
    """
    stack = [root]
    while stack:
        w = stack.pop()
        try:
            stack.extend(w.winfo_children())
        except Exception:
            pass
        if not isinstance(w, (ctk.CTkOptionMenu, ctk.CTkComboBox)):
            for attr in ("text", "placeholder_text"):
                try:
                    cur = w.cget(attr)
                except Exception:
                    continue
                if isinstance(cur, str) and cur:
                    new = _tr(cur)
                    if new != cur:
                        try:
                            w.configure(**{attr: new})
                        except Exception:
                            pass
        if isinstance(w, ctk.CTkOptionMenu):
            _lang_optmenu(w)
        if isinstance(w, ctk.CTkTextbox):
            try:
                cur = w.get("1.0", "end-1c")
                new = _tr(cur)
                if new != cur:
                    state = w.cget("state")
                    w.configure(state="normal")
                    w.delete("1.0", "end")
                    w.insert("1.0", new)
                    w.configure(state=state)
            except Exception:
                pass
        if isinstance(w, tk.Menu):
            try:
                last = w.index("end")
                last = int(last) if last is not None else -1   # пустое меню отдаёт None
            except Exception:
                last = -1
            for i in range(last + 1):
                try:
                    lab = w.entrycget(i, "label")
                    new = _tr(lab)
                    if new != lab:
                        w.entryconfigure(i, label=new)
                except Exception:
                    continue
        if isinstance(w, ctk.CTkToplevel):
            try:
                t = w.title()
                new = _tr(t)
                if t and new != t:
                    w.title(new)
            except Exception:
                pass


class _TrDialogs:
    """Стандартные окна Windows: заголовок и текст — на выбранном языке интерфейса."""

    def __init__(self, mod):
        self._mod = mod

    def __getattr__(self, name):
        fn = getattr(self._mod, name)

        def wrapper(*args, **kwargs):
            args = [_tr(a) if isinstance(a, str) else a for a in args]
            for key in ("title", "message"):
                if isinstance(kwargs.get(key), str):
                    kwargs[key] = _tr(kwargs[key])
            # подписи типов файлов в окне выбора ("Документы", "Модель GGUF")
            fts = kwargs.get("filetypes")
            if isinstance(fts, (list, tuple)):
                kwargs["filetypes"] = [
                    (_tr(label), pat) if isinstance(label, str) else (label, pat)
                    for label, pat in fts
                ]
            return fn(*args, **kwargs)
        return wrapper


_TK_MESSAGEBOX = messagebox
_TK_FILEDIALOG = filedialog
messagebox = _TrDialogs(_TK_MESSAGEBOX)
filedialog = _TrDialogs(_TK_FILEDIALOG)
# ===================================================================


class ModernTTSApp(ctk.CTk):
    REF_TEXT = "Привет! Это образец голоса для синтеза речи."
    ENGINE_VALUES = ["Piper (CPU)", "Vox (GPU)"]
    SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
    PLACEHOLDER = ("Вставьте текст статьи, ссылку или файл — или просто печатайте здесь.\n\n"
                   "Ctrl+V — вставить из буфера. Всё, что есть в этом поле, считается источником:\n"
                   "анализ пойдёт по нему, а не по ссылке.")
    PLACEHOLDER_EN = ("Paste an article link, text or file — or just type here.\n\n"
                      "Ctrl+V — paste from the clipboard. Whatever is in this box is the source:\n"
                      "the analysis uses it, not the link.")
    PRESET_VALUES = ["Только суть (10%)", "Очень кратко (30%)", "Кратко (50%)", "Подробно (80%)",
                     "Речь для озвучки (100%)", "Перевод на английский (100%)"]
    # Доля исходного объёма для каждого пресета (жёсткий лимит в знаках)
    PRESET_RATIOS = {
        "Только суть (10%)": 0.10,
        "Очень кратко (30%)": 0.30,
        "Кратко (50%)": 0.50,
        "Подробно (80%)": 0.80,
    }
    # Те же промпты для английского интерфейса: ключ — название уровня, как в PRESET_VALUES
    PRESET_PROMPTS_EN = {
        "Только суть (10%)":
            "Keep only the main point of the text — one or two short sentences, no more than "
            "10% of the volume. Drop examples, secondary details, repetitions and caveats. "
            "If the point becomes unclear without names or numbers, keep them.",
        "Очень кратко (30%)":
            "Shorten the text to ~30% of its volume: the key facts, the main arguments and the "
            "conclusion. Remove examples, explanations, preambles and repetitions, but keep all "
            "significant numbers, dates, names and titles.",
        "Кратко (50%)":
            "Cut the text by about half (~50% of the volume): the main facts, arguments and "
            "conclusions together with the key details that affect them. Keep the order of "
            "presentation as in the original text, without losing the logic.",
        "Подробно (80%)":
            "Compress the text to ~80% of its volume: keep the structure, the order of "
            "presentation and nearly all the details. Compress only the wording and remove "
            "repetitions — do not drop anything significant.",
        "Речь для озвучки (100%)":
            "Rewrite the whole text for narration, keeping all of the meaning, the structure and "
            "the order of presentation. Remove only the visual clutter: links, captions, headers "
            "and footers, page numbers and notes.",
        "Перевод на английский (100%)":
            "Translate the text into English. Keep all of the meaning, the structure and the "
            "order of presentation; do not shorten, add to or comment on it. Render terms, names "
            "and titles as is customary in English-language literature on the subject. Return "
            "only the translation, without explanations or preambles.",
    }
    # Признаки промптов прежней версии — их заменяем актуальными по выбранному пресету
    LEGACY_PROMPTS = (
        "Передай главную мысль текста объёмом не более 10%",
        "Сократи текст до ~30% исходного объёма",
        "Сократи текст так, чтобы итоговый объём составлял около 50%",
        "Составь подробное резюме объёмом около 80%",
        "Перескажи текст полностью (100% смысла)",
    )

    @staticmethod
    def _asset_path(name):
        """Файл рядом со скриптом или внутри onefile-сборки."""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, name)

    def _apply_app_icon(self):
        """Одна и та же иконка: окно, панель задач, диалоги."""
        try:
            ico = self._asset_path("app.ico")
            if not os.path.isfile(ico):
                return
            try:
                self.iconbitmap(default=ico)      # default — и для всех диалогов
            except Exception:
                self.iconbitmap(ico)
            try:
                from PIL import Image, ImageTk
                self._icon_img = ImageTk.PhotoImage(Image.open(ico).convert("RGBA").resize((256, 256)))
                self.iconphoto(True, self._icon_img)
            except Exception:
                pass
        except Exception:
            pass

    def _apply_titlebar_icon(self):
        """В шапке окна значка нет, в панели задач остаётся FAIR.

        В ICON_SMALL ставим картинку цвета заголовка Windows: она сливается с полосой,
        и значка перед надписью «FAIR» не видно. ICON_BIG оставляем настоящим — иначе
        пропадёт значок на панели задач и в Alt+Tab. Полностью прозрачную иконку
        ставить нельзя: Windows подставляет тогда запасной значок Tk.
        """
        try:
            self.update_idletasks()
            user32 = ctypes.windll.user32
            user32.LoadImageW.restype = ctypes.c_void_p
            user32.GetParent.restype = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.SendMessageW.restype = ctypes.c_void_p
            user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                            ctypes.c_void_p, ctypes.c_void_p]
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            LR_LOADFROMFILE, IMAGE_ICON, WM_SETICON = 0x0010, 1, 0x0080
            clear = self._asset_path("titlebar_clear.ico")
            ico = self._asset_path("app.ico")
            small = user32.LoadImageW(None, clear if os.path.isfile(clear) else ico,
                                      IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            big = user32.LoadImageW(None, ico, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if small:
                user32.SendMessageW(hwnd, WM_SETICON, 0, ctypes.c_void_p(small))
            if big:
                user32.SendMessageW(hwnd, WM_SETICON, 1, ctypes.c_void_p(big))
        except Exception as e:
            print(f"⚠️ иконка заголовка: {e}")

    def __init__(self):
        super().__init__()
        self._apply_app_icon()
        self.after(120, self._apply_titlebar_icon)

        self.BASE_DIR = BASE_DIR    # в установленной версии — %LOCALAPPDATA%\FAIR
        self.theme = self._load_theme()

        self.title("FAIR")
        self.geometry("1140x790")
        self.minsize(1000, 700)
        self.configure(fg_color=COLOR_BG)
        self._init_fonts()

        self.tts_voice = None
        self.vox_model = None
        self.vox_name = None
        self.current_engine = "Piper"
        self.current_tts_name = None
        self.speech_rate = 1.0
        self.vox_fast_var = ctk.BooleanVar(value=False)
        self._sd_stream = None

        # Воспроизведение с паузой по месту
        self._play_stream = None
        self._play_pos = 0
        self._play_paused = False
        self._play_done = True
        self._play_stop_req = False

        self.custom_voices = {}
        self.custom_presets = {}   # {название: {"ratio": 0.4, "prompt": "..."}} — свои уровни сжатия
        self._last_preset = "Кратко (50%)"
        self.box_is_source = False
        self.auto_play_var = ctk.BooleanVar(value=False)
        self.llm_gpu_var = ctk.BooleanVar(value=False)
        self._gpu_server = None
        self._gpu_server_port = None
        self._gpu_server_model = None
        self._gpu_server_ctx = None
        self._playing = False
        self._play_data = None
        self._play_sr = None
        self.cancel_event = threading.Event()

        self.llm_model = None
        self.llm_model_path = None
        self.llm_model_ctx = None
        self.is_processing = False
        self.tts_models = {}
        self.llm_models = {}
        self.llm_display = {}
        self.external_llms = {}  # GGUF-модели пользователя вне models_llm/
        self.model_meta = {}
        self.model_ctx = {}
        self.model_limits = {}
        self.ctx_choices = {}
        self._gen_stats = {}
        self._last_pct = -1

        self._placeholder_active = False
        self._suppress_box_events = False
        self._result_is_generated = False
        self._last_source = ""

        self.donate_done = self._read_donate_flag()   # нужен ещё до сборки шапки
        self._early_lang()          # язык прошлого раза — до сборки окна, чтобы не мигало
        self.setup_ui()
        self._polish_cursors()
        self._seed_bundled_voices()     # установленная версия: голос Piper из комплекта
        self.scan_models()
        self.load_settings()
        self._apply_language()
        # первый запуск установленной версии: голоса → дополнение Vox → модель
        if FROZEN:
            _flog(f"старт: BASE={self.BASE_DIR} модели={len(self.llm_models)}")
            self.after(700, self._first_run_chain)
        self._probe_model(self.llm_combo.get())

        self._show_placeholder()
        self._update_char_count()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _early_lang(self):
        """Язык интерфейса из прошлого запуска — читаем ДО сборки окна.

        Иначе окно сначала собирается с русскими подписями и только потом
        переводится: видно мигание, а при сбое чтения настроек язык теряется.
        """
        global UI_LANG
        try:
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                lang = str(json.load(f).get("ui_lang", "ru")).lower()
            if lang in ("ru", "en"):
                UI_LANG = lang
        except Exception:
            pass

    # ---------------- модель анализа: первая загрузка с докачкой ----------------
    MODEL_PACK = {
        "name": "gemma-4-E4B-it-Q4_K_M.gguf",
        "url": ("https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/"
                "resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"),
        "size": 4_977_171_584,
    }

    def _seed_bundled_voices(self):
        """Первый запуск установленной версии: голос Piper из комплекта → models/."""
        if not FROZEN:
            return
        try:
            src_dir = self._asset_path("piper")
            if not os.path.isdir(src_dir):
                return
            dst_dir = os.path.join(self.BASE_DIR, "models")
            os.makedirs(dst_dir, exist_ok=True)
            for name in sorted(os.listdir(src_dir)):
                if not (name.endswith(".onnx") or name.endswith(".onnx.json")):
                    continue        # из комплекта берём только голоса, не служебные файлы piper
                src = os.path.join(src_dir, name)
                dst = os.path.join(dst_dir, name)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        except Exception as e:
            print(f"⚠️ голос из комплекта: {e}")

    def _offer_model_download(self, force=False):
        """Нет модели для анализа — предлагаем скачать Gemma (≈5 ГБ) с докачкой."""
        if not force and (self.llm_models or getattr(self, "model_offer_muted", False)):
            return
        _flog("предлагаю модель анализа")
        old = getattr(self, "_dl_dialog", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except Exception:
            pass

        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Модель ИИ"))
        dlg.geometry("540x310")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        dlg.after(150, lambda: _apply_dialog_icon(dlg))
        self._dl_dialog = dlg
        self._dl_cancel = threading.Event()
        self._dl_thread = None

        def _chain_after_close(event=None):
            """Диалог модели закрыт любым способом — идём к следующему шагу первого запуска."""
            if event is None or getattr(event, "widget", None) is dlg:
                self.after(400, self._first_run_chain)

        dlg.bind("<Destroy>", _chain_after_close)

        body = ctk.CTkFrame(dlg, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text=_tr("Нужна модель для анализа текста"), font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(16, 4))
        ctk.CTkLabel(body, justify="left", wraplength=470, font=FONT_TINY,
                     text_color=COLOR_TEXT_SEC,
                     text=_tr("Gemma 4 E4B, ≈5 ГБ — скачивается один раз с Hugging Face.\n"
                              "Дальше анализ идёт без интернета. Если прервать, докачается с места.")
                     ).pack(padx=16, anchor="w")

        bar = ctk.CTkProgressBar(body, height=10, corner_radius=6, progress_color="#c6763a",
                                 fg_color=COLOR_CARD2)
        bar.set(0)
        bar.pack(fill="x", padx=16, pady=(16, 6))
        info = ctk.CTkLabel(body, text=_tr("Модель не скачана"), font=FONT_TINY,
                            text_color=COLOR_TEXT_SEC)
        info.pack(anchor="w", padx=16)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(12, 14), side="bottom")

        btn_go = ctk.CTkButton(row, text=_tr("Скачать"), width=150, height=34,
                               corner_radius=R_PANEL, font=FONT_SUBHEADER,
                               fg_color="#c6763a", hover_color="#a95f2c",
                               text_color="#ffffff",
                               command=lambda: self._start_model_download(dlg, bar, info, btn_go))
        btn_go.pack(side="left")

        def on_later():
            try:
                self._dl_cancel.set()
            except Exception:
                pass
            dlg.destroy()

        ctk.CTkButton(row, text=_tr("Позже"), width=110, height=34, corner_radius=R_PANEL,
                      font=FONT_NORMAL, fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      hover_color=COLOR_CARD, command=on_later).pack(side="left", padx=8)

        self._dl_mute = ctk.BooleanVar(value=bool(getattr(self, "model_offer_muted", False)))
        ctk.CTkCheckBox(row, text=_tr("Больше не предлагать"), variable=self._dl_mute,
                        font=FONT_TINY, checkbox_width=16, checkbox_height=16,
                        fg_color="#c6763a", hover_color="#a95f2c",
                        command=self._save_model_mute).pack(side="right")

    def _save_model_mute(self):
        try:
            self.model_offer_muted = bool(self._dl_mute.get())
            self.save_settings()
        except Exception:
            pass

    def _start_model_download(self, dlg, bar, info, btn):
        if self._dl_thread is not None and self._dl_thread.is_alive():
            self._dl_cancel.set()
            btn.configure(text=_tr("Отмена…"), state="disabled")
            return
        self._dl_cancel = threading.Event()
        btn.configure(text=_tr("Отмена"))
        self._dl_thread = threading.Thread(target=self._download_model,
                                           args=(dlg, bar, info, btn), daemon=True)
        self._dl_thread.start()

    def _download_model(self, dlg, bar, info, btn):
        """Качает GGUF в models_llm/<имя>.part и переименовывает по завершении."""
        pack = self.MODEL_PACK
        folder = os.path.join(self.BASE_DIR, "models_llm")
        os.makedirs(folder, exist_ok=True)
        final = os.path.join(folder, pack["name"])
        part = final + ".part"

        def ui(fn, *args):
            try:
                self.after(0, lambda: fn(*args))
            except Exception:
                pass

        def set_info(text):
            try:
                if dlg.winfo_exists():
                    info.configure(text=text)
            except Exception:
                pass

        def set_btn(text, state="normal"):
            try:
                if dlg.winfo_exists():
                    btn.configure(text=text, state=state)
            except Exception:
                pass

        try:
            have = os.path.getsize(part) if os.path.exists(part) else 0
            total = pack["size"]
            if have >= total:
                os.replace(part, final)
                self.after(0, self._model_ready, dlg, "Модель уже скачана")
                return
            headers = {"Range": f"bytes={have}-"} if have else {}
            with _http_get(pack["url"], headers=headers, stream=True) as r:
                r.raise_for_status()
                if r.status_code == 206:
                    total = have + int(r.headers.get("Content-Length") or 0)
                else:
                    have = 0
                    total = int(r.headers.get("Content-Length") or pack["size"])
                done = have
                drawn = 0.0
                ui(set_info, f"{done / 1048576:,.0f} / {total / 1048576:,.0f} " + _tr("МБ") + " · 0%")
                with open(part, "ab" if have else "wb") as f:
                    for chunk in r.iter_content(chunk_size=262144):
                        if self._dl_cancel.is_set():
                            ui(set_btn, _tr("Продолжить"))
                            ui(set_info, _tr("Загрузка остановлена — можно продолжить позже"))
                            return
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if now - drawn > 0.25:
                            drawn = now
                            pct = (done / total) if total else 0
                            ui(bar.set, min(pct, 1.0))
                            ui(set_info, f"{done / 1048576:,.0f} / {total / 1048576:,.0f} "
                                         + _tr("МБ") + f" · {pct * 100:.0f}%")
            ui(bar.set, 1.0)
            os.replace(part, final)
            self.after(0, self._model_ready, dlg, "Модель скачана")
        except Exception as e:
            ui(set_info, f"{_tr('Ошибка загрузки')}: {e}")
            ui(set_btn, _tr("Повторить"))

    def _model_ready(self, dlg, msg):
        try:
            if dlg is not None and dlg.winfo_exists():
                dlg.destroy()
        except Exception:
            pass
        self.scan_models()
        name = self.MODEL_PACK["name"]
        disp = next((d for d, a in self.llm_display.items() if a == name), None)
        if disp:
            self.llm_combo.set(disp)
            self.save_settings()
        self.update_status(f"✅ {_tr(msg)}")

    # ---------------- голоса Piper: скачивание и импорт ----------------
    PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    PIPER_VOICES = [
        ("ru_RU-irina-medium", "Ирина · женский, русский",
         "/ru/ru_RU/irina/medium/ru_RU-irina-medium", "CC BY-NC-SA"),
        ("ru_RU-ruslan-medium", "Руслан · мужской, русский",
         "/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium", "CC BY-NC-SA"),
        ("en_US-amy-medium", "Amy · женский, английский",
         "/en/en_US/amy/medium/en_US-amy-medium", "public domain"),
        ("en_GB-alan-medium", "Alan · мужской, английский",
         "/en/en_GB/alan/medium/en_GB-alan-medium", "public domain"),
        ("de_DE-thorsten-medium", "Thorsten · мужской, немецкий",
         "/de/de_DE/thorsten/medium/de_DE-thorsten-medium", "CC BY-NC-SA"),
    ]

    def _fetch_file(self, url, dest, on_bytes=None, cancel=None):
        """Скачать url в dest с докачкой через .part. True — файл на месте."""
        part = dest + ".part"
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        with _http_get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            if r.status_code == 206:
                total = have + int(r.headers.get("Content-Length") or 0)
            else:
                have = 0
                total = int(r.headers.get("Content-Length") or 0)
            done = have
            with open(part, "ab" if have else "wb") as f:
                for chunk in r.iter_content(chunk_size=262144):
                    if cancel is not None and cancel.is_set():
                        return False
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if on_bytes:
                        on_bytes(done, total)
        os.replace(part, dest)
        return True

    def _ui(self, fn, *args, **kwargs):
        """Обновить UI из фонового потока: молча, если окно уже закрыто."""
        try:
            self.after(0, lambda: fn(*args, **kwargs))
        except Exception:
            pass

    def _voice_file(self, name):
        return os.path.join(self.BASE_DIR, "models", name + ".onnx")

    # голоса, которые приложение ставит само при первом запуске
    AUTO_VOICES = (
        ("ru_RU-irina-medium", "/ru/ru_RU/irina/medium/ru_RU-irina-medium"),
        ("ru_RU-ruslan-medium", "/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium"),
    )

    def _first_run_chain(self):
        """Первый запуск: голоса → дополнение Vox → модель анализа (по одному шагу)."""
        if not FROZEN:
            return
        try:
            state = {n: os.path.isfile(self._voice_file(n)) for n, _ in self.AUTO_VOICES}
            _flog(f"цепочка: FROZEN={FROZEN} голоса={state} vox={self._vox_installed()} "
                  f"моделей={len(self.llm_models)} offered={getattr(self, '_vox_offered', False)}")
        except Exception as e:
            _flog(f"цепочка: диагностика упала: {type(e).__name__}: {e}")
        if not self.llm_models and not getattr(self, "_model_offered", False) \
                and not getattr(self, "model_offer_muted", False):
            self._model_offered = True            # сначала — модель анализа
            self._offer_model_download()
            return
        if any(not os.path.isfile(self._voice_file(n)) for n, _ in self.AUTO_VOICES) \
                and not getattr(self, "voices_seeded", False):
            self._auto_install_voices()
            return
        if not self._vox_installed() and not getattr(self, "_vox_offered", False):
            self._vox_offered = True
            self._offer_vox()
            return
        if not self.llm_models:
            self._offer_model_download()

    def _auto_install_voices(self):
        """Первый запуск: докачиваем русские голоса Ирина и Руслан (≈126 МБ)."""
        missing = [(n, s) for n, s in self.AUTO_VOICES if not os.path.isfile(self._voice_file(n))]
        if not missing or getattr(self, "voices_seeded", False):
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Голоса Piper"))
        dlg.geometry("520x215")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        dlg.after(150, lambda: _apply_dialog_icon(dlg))
        self._auto_voices_dialog = dlg
        self._voice_cancel = threading.Event()

        body = ctk.CTkFrame(dlg, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(body, text=_tr("Устанавливаются голоса"), font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(16, 4))
        ctk.CTkLabel(body, font=FONT_TINY, text_color=COLOR_TEXT_SEC, justify="left",
                     wraplength=460,
                     text=_tr("Ирина и Руслан, ≈126 МБ — один раз, дальше работают без интернета.")
                     ).pack(padx=16, anchor="w")
        bar = ctk.CTkProgressBar(body, height=10, corner_radius=6, progress_color="#c6763a",
                                 fg_color=COLOR_CARD2)
        bar.set(0)
        bar.pack(fill="x", padx=16, pady=(14, 6))
        info = ctk.CTkLabel(body, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC, anchor="w")
        info.pack(fill="x", padx=16)
        ctk.CTkButton(body, text=_tr("Отмена"), width=110, height=30, corner_radius=R_PANEL,
                      font=FONT_SMALL, fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      hover_color=COLOR_CARD,
                      command=lambda: self._voice_cancel.set()).pack(anchor="e", padx=16, pady=8)

        total_files = len(missing)

        def work():
            try:
                for idx, (name, suffix) in enumerate(missing, start=1):
                    if self._voice_cancel.is_set():
                        self.after(0, lambda: info.configure(text=_tr("Отменено")))
                        return
                    onnx = os.path.join(self.BASE_DIR, "models", name + ".onnx")

                    def progress(done, total, nm=name, i=idx):
                        base = (i - 1) / total_files
                        part = (done / total / total_files) if total else 0
                        self._ui(bar.set, min(base + part, 1.0))
                        self._ui(info.configure,
                                 text=f"{nm}: {done / 1048576:,.0f} / {total / 1048576:,.0f} "
                                      + _tr("МБ"))

                    ok = self._fetch_file(self.PIPER_BASE + suffix + ".onnx", onnx,
                                          progress, self._voice_cancel)
                    if ok:
                        ok = self._fetch_file(self.PIPER_BASE + suffix + ".onnx.json",
                                              onnx + ".json", None, self._voice_cancel)
                    if not ok:
                        return
                self.after(0, self._auto_voices_done)
            except Exception as e:
                msg = f"{_tr('Ошибка загрузки')}: {e}"
                self.after(0, lambda: info.configure(text=msg))

        threading.Thread(target=work, daemon=True).start()

    def _auto_voices_done(self):
        self.voices_seeded = True
        try:
            if getattr(self, "_auto_voices_dialog", None) is not None:
                self._auto_voices_dialog.destroy()
        except Exception:
            pass
        self._refresh_voices()
        self.update_status(f"✅ {_tr('Голоса Ирина и Руслан установлены')}")
        self.after(500, self._first_run_chain)   # дальше — Vox, потом модель анализа

    def _refresh_voices(self, select=None):
        """Пересобрать список голосов после установки нового."""
        self.scan_models()
        try:
            if self.current_engine == "Piper":
                self.tts_combo.configure(values=sorted(self.tts_models.keys()))
            else:
                self.tts_combo.configure(values=self.voice_values())
        except Exception:
            pass
        if select:
            try:
                self.tts_combo.set(select)
                self.current_tts_name = select
            except Exception:
                pass
        self.save_settings()

    def _open_piper_voices(self):
        """Окно «Голоса Piper»: скачать готовый голос или импортировать файл."""
        old = getattr(self, "_voices_dialog", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except Exception:
            pass

        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Голоса Piper"))
        dlg.geometry("580x470")
        dlg.resizable(False, True)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        dlg.after(150, lambda: _apply_dialog_icon(dlg))
        self._voices_dialog = dlg
        self._voice_cancel = threading.Event()

        body = ctk.CTkFrame(dlg, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text=_tr("Голоса Piper"), font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(14, 2))
        ctk.CTkLabel(body, font=FONT_TINY, text_color=COLOR_TEXT_SEC, justify="left",
                     wraplength=500,
                     text=_tr("Голоса Irina и Ruslan — CC BY-NC-SA: только для личного "
                              "использования, в публичную сборку не входят.")
                     ).pack(padx=16, anchor="w", pady=(0, 8))

        bar = ctk.CTkProgressBar(body, height=8, corner_radius=4, progress_color="#c6763a",
                                 fg_color=COLOR_CARD2)
        bar.set(0)
        bar.pack(fill="x", padx=16, pady=(0, 4))
        info = ctk.CTkLabel(body, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC, anchor="w")
        info.pack(fill="x", padx=16)

        rows = ctk.CTkScrollableFrame(body, fg_color="transparent", height=250)
        rows.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        rows.grid_columnconfigure(0, weight=1)

        for i, (name, caption, suffix, lic) in enumerate(self.PIPER_VOICES):
            installed = os.path.isfile(self._voice_file(name))
            row = ctk.CTkFrame(rows, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=caption, font=FONT_SMALL, anchor="w",
                         text_color=COLOR_TEXT_MAIN).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=lic, font=FONT_TINY, anchor="w",
                         text_color=COLOR_TEXT_SEC).grid(row=1, column=0, sticky="w")
            btn = ctk.CTkButton(row, text=_tr("Установлен") if installed else _tr("Скачать"),
                                width=110, height=26, corner_radius=R_PANEL, font=FONT_TINY,
                                fg_color=COLOR_FILL_SOFT if installed else "#c6763a",
                                hover_color=COLOR_SELECT if installed else "#a95f2c",
                                text_color=COLOR_TEXT_MAIN if installed else "#ffffff",
                                state="disabled" if installed else "normal")
            btn.configure(command=lambda n=name, s=suffix, b=btn: self._install_piper_voice(
                n, s, dlg, b, bar, info))
            btn.grid(row=0, column=1, rowspan=2, padx=(10, 0))

        foot = ctk.CTkFrame(body, fg_color="transparent")
        foot.pack(fill="x", padx=16, pady=(4, 14))
        ctk.CTkButton(foot, text=_tr("Закрыть"), width=100, height=30, corner_radius=R_PANEL,
                      font=FONT_SMALL, fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      hover_color=COLOR_CARD, command=dlg.destroy).pack(side="right")

    def _install_piper_voice(self, name, suffix, dlg, btn, bar, info):
        """Скачать голос (.onnx + .json) в models/ с прогрессом."""
        folder = os.path.join(self.BASE_DIR, "models")
        os.makedirs(folder, exist_ok=True)
        onnx = os.path.join(folder, name + ".onnx")
        cancel = self._voice_cancel

        def progress(done, total):
            pct = (done / total) if total else 0
            self._ui(bar.set, min(pct, 1.0))
            self._ui(info.configure,
                     text=f"{name}: {done / 1048576:,.0f} / {total / 1048576:,.0f} " + _tr("МБ"))

        def work():
            try:
                self._ui(btn.configure, text=_tr("Загрузка…"), state="disabled")
                ok = self._fetch_file(self.PIPER_BASE + suffix + ".onnx", onnx, progress, cancel)
                if ok:
                    ok = self._fetch_file(self.PIPER_BASE + suffix + ".onnx.json",
                                          onnx + ".json", None, cancel)
                if ok:
                    self.after(0, self._voice_ready, name, btn, info)
                else:
                    self._ui(btn.configure, text=_tr("Скачать"), state="normal")
            except Exception as e:
                msg = f"{_tr('Ошибка загрузки')}: {e}"
                self._ui(info.configure, text=msg)
                self._ui(btn.configure, text=_tr("Повторить"), state="normal")

        threading.Thread(target=work, daemon=True).start()

    def _voice_ready(self, name, btn, info):
        self._refresh_voices(select=name)
        try:
            btn.configure(text=_tr("Установлен"), state="disabled", fg_color=COLOR_FILL_SOFT,
                          text_color=COLOR_TEXT_MAIN)
        except Exception:
            pass
        info.configure(text=f"{_tr('Голос установлен')}: {name}")
        self.update_status(f"✅ {_tr('Голос установлен')}: «{name}»")

    def _init_fonts(self):
        global FONT_FAMILY, FONT_HEADER, FONT_SUBHEADER, FONT_NORMAL, FONT_SMALL, FONT_TINY
        fam = FONT_FAMILY
        try:
            import tkinter.font as tkfont
            families = set(tkfont.families(self))
            for cand in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
                if cand in families:
                    fam = cand
                    break
        except Exception:
            pass
        FONT_FAMILY = fam
        FONT_HEADER = (fam, 18, "bold")
        FONT_SUBHEADER = (fam, 13, "bold")
        FONT_NORMAL = (fam, 12)
        FONT_SMALL = (fam, 11)
        FONT_TINY = (fam, 10)

    def _load_theme(self):
        """Тёмная тема убрана — приложение всегда в светлом оформлении."""
        try:
            ctk.set_appearance_mode("light")
        except Exception:
            pass
        return "light"

    def _on_close(self):
        try:
            self.save_settings()
        except Exception:
            pass
        try:
            self._stop_gpu_server()
        except Exception:
            pass
        try:
            self._close_stream()
            self.unload_llm()
        except Exception:
            pass
        if SD_AVAILABLE:
            try:
                sd.stop()
            except Exception:
                pass
        self.destroy()

    # ================= ПАМЯТЬ (только ОЗУ) =================

    def _sys_mem_info(self):
        ram_total = ram_avail = None
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(st)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            ram_total, ram_avail = st.ullTotalPhys, st.ullAvailPhys
        except Exception:
            try:
                import psutil
                vm = psutil.virtual_memory()
                ram_total, ram_avail = vm.total, vm.available
            except Exception:
                pass
        return ram_total, ram_avail

    def _update_ram_label(self):
        rt, ra = self._sys_mem_info()
        if rt:
            self.ram_label.configure(text=_tr(f"ОЗУ: {round(rt / 1024 ** 3)} ГБ (своб. {ra / 1024 ** 3:.0f})"))
        else:
            self.ram_label.configure(text=_tr("ОЗУ: —"))

    # ================= CTRL+V ПО КОДУ КЛАВИШИ =================

    @staticmethod
    def _clip_text():
        try:
            return pyperclip.paste()
        except Exception:
            return ""

    @staticmethod
    def _style_text_selection(widget):
        """Нейтральное (серое) выделение текста вместо системного голубого."""
        inner = getattr(widget, "_textbox", None) or getattr(widget, "_entry", None) or widget
        try:
            inner.configure(selectbackground=COLOR_SELECT_TEXT[0],
                            selectforeground="#111111",
                            inactiveselectbackground=COLOR_SELECT_TEXT[0])
        except Exception:
            pass

    def _bind_ctrl_v(self, widget, handler):
        """Ctrl+V в любой раскладке.

        В русской раскладке Tk присылает keysym «Cyrillic_em», поэтому <Control-v>
        не срабатывает. Ловим ещё и по виртуальному коду: VK_V = 86, VK_INSERT = 45.
        """
        def on_paste(event=None):
            try:
                return handler(event)
            except Exception as e:
                print(f"⚠️ Вставка: {e}")
                return None

        def on_key(event):
            ctrl = bool(event.state & 0x0004)
            shift = bool(event.state & 0x0001)
            ks = (event.keysym or "").lower()
            if ctrl and (event.keycode == 86 or ks in ("v", "cyrillic_em")):
                return on_paste(event)
            if shift and (event.keycode == 45 or ks == "insert"):
                return on_paste(event)
            return None

        for seq in ("<Control-v>", "<Control-V>", "<Control-Shift-v>", "<Control-Shift-V>",
                    "<Shift-Insert>"):
            widget.bind(seq, on_paste, add="+")
        widget.bind("<KeyPress>", on_key, add="+")

    def _copy_from(self, widget, event=None):
        """Ctrl+C: копировать выделенное (в любой раскладке)."""
        try:
            text = widget.get("sel.first", "sel.last")
        except Exception:
            text = ""
        if text:
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
            except Exception:
                pass
        return "break"

    def _cut_from(self, widget, event=None):
        """Ctrl+X: вырезать выделенное."""
        self._copy_from(widget, event)
        try:
            widget.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def _select_all_in(self, widget, event=None):
        """Ctrl+A: выделить всё поле."""
        try:
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
        except Exception:
            try:
                widget.select_range(0, "end")
            except Exception:
                pass
        return "break"

    def _bind_clipboard_keys(self, widget):
        """Копировать/вырезать/выделить всё — с учётом русской раскладки (по keycode)."""
        for seq, fn in (("<Control-c>", self._copy_from), ("<Control-C>", self._copy_from),
                        ("<Control-x>", self._cut_from), ("<Control-X>", self._cut_from),
                        ("<Control-a>", self._select_all_in), ("<Control-A>", self._select_all_in),
                        ("<<Copy>>", self._copy_from), ("<<Cut>>", self._cut_from),
                        ("<<SelectAll>>", self._select_all_in)):
            widget.bind(seq, lambda e, f=fn: f(widget, e), add="+")

        def on_key(event):
            if not (event.state & 0x0004):      # только с Ctrl
                return None
            ks = (event.keysym or "").lower()
            if event.keycode == 67 or ks in ("c", "cyrillic_es"):
                return self._copy_from(widget, event)
            if event.keycode == 88 or ks in ("x", "cyrillic_che"):
                return self._cut_from(widget, event)
            if event.keycode == 65 or ks in ("a", "cyrillic_ef"):
                return self._select_all_in(widget, event)
            if event.keycode == 45 or ks == "insert":
                return self._copy_from(widget, event)
            return None

        widget.bind("<KeyPress>", on_key, add="+")

    def _attach_text_menu(self, widget, on_insert=None):
        """Правый клик: Вставить / Копировать / Вырезать / Выделить всё."""
        is_text = widget.winfo_class() == "Text"

        def get_selection():
            if is_text:
                return widget.get("sel.first", "sel.last")
            return widget.selection_get()

        def del_selection():
            widget.delete("sel.first", "sel.last")

        def paste():
            txt = self._clip_text()
            if not txt:
                return
            if on_insert is not None:
                on_insert(txt)
                return
            try:
                if not is_text:
                    del_selection()
            except Exception:
                pass
            widget.insert("insert", txt)

        def copy():
            try:
                self.clipboard_clear()
                self.clipboard_append(get_selection())
            except Exception:
                pass

        def cut():
            try:
                self.clipboard_clear()
                self.clipboard_append(get_selection())
                del_selection()
            except Exception:
                pass

        def select_all():
            try:
                if is_text:
                    widget.tag_add("sel", "1.0", "end-1c")
                    widget.mark_set("insert", "1.0")
                else:
                    widget.select_range(0, "end")
            except Exception:
                pass

        def popup(event):
            menu = Menu(self, tearoff=0)
            menu.add_command(label=_tr("Вставить"), command=paste)
            menu.add_command(label=_tr("Копировать"), command=copy)
            menu.add_command(label=_tr("Вырезать"), command=cut)
            menu.add_separator()
            menu.add_command(label=_tr("Выделить всё"), command=select_all)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        widget.bind("<Button-3>", popup, add="+")
        return popup

    # ================= ИНТЕРФЕЙС =================

    def _polish_cursors(self, widget=None):
        """Курсор-рука на всех кликабельных элементах — как у верхних списков."""
        parent = widget if widget is not None else self
        try:
            children = parent.winfo_children()
        except Exception:
            return
        for child in children:
            cls = child.__class__.__name__
            try:
                if cls in ("CTkButton", "CTkOptionMenu", "CTkSwitch", "CTkCheckBox"):
                    child.configure(cursor="hand2")
                elif cls == "CTkSegmentedButton":
                    for seg_btn in child._buttons_dict.values():  # внутренние кнопки
                        seg_btn.configure(cursor="hand2")
                elif cls == "CTkComboBox":
                    child._canvas.configure(cursor="hand2")
                    child._entry.configure(cursor="xterm")
                    self._attach_combo_hover(child)
            except Exception:
                pass
            self._polish_cursors(child)

    def _show_custom_voice(self, show):
        """Большая кнопка «Образец голоса» — показать/скрыть."""
        try:
            if show:
                self.btn_add_voice.pack(fill="x", padx=12, pady=(0, 10), before=self.rate_row)
            else:
                self.btn_add_voice.pack_forget()
        except Exception:
            pass

    def _attach_combo_hover(self, combo):
        """Подсветка кнопки-стрелки при наведении: в CTkComboBox её нет."""
        try:
            canvas = combo._canvas
            normal = combo._apply_appearance_mode(combo.cget("button_color"))
            hover = combo._apply_appearance_mode(combo.cget("button_hover_color"))

            def paint(color, cursor):
                try:
                    for tag in ("inner_parts_right", "border_parts_right"):
                        canvas.itemconfig(tag, outline=color, fill=color)
                    canvas.configure(cursor=cursor)
                except Exception:
                    pass

            canvas.bind("<Enter>", lambda e: paint(hover, "hand2"), add="+")
            canvas.bind("<Leave>", lambda e: paint(normal, "arrow"), add="+")
        except Exception as e:
            print(f"⚠️ combo hover: {e}")

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------- верхняя панель ----------------
        topbar = ctk.CTkFrame(self, fg_color="transparent", height=48)
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 0))
        topbar.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(topbar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")
        # значок перед названием (просил вернуть 24.10.26)
        try:
            from PIL import Image
            logo_path = self._asset_path("logo.png")
            if os.path.isfile(logo_path):
                self._logo_img = ctk.CTkImage(Image.open(logo_path).convert("RGBA"), size=(38, 38))
                self._logo_lbl = ctk.CTkLabel(brand, text="", image=self._logo_img)
                self._logo_lbl.pack(side="left", padx=(0, 10))
                self._logo_lbl.configure(cursor="hand2")
                self._logo_lbl.bind("<Button-1>", self._open_donate_page)
        except Exception as e:
            print(f"⚠️ логотип: {e}")
        # название в двух цветах значка: «AI» — темнее (медь), остальное — светлее (янтарь)
        _trow = ctk.CTkFrame(brand, fg_color="transparent")
        _trow.pack(side="left")
        _f = (FONT_FAMILY, 22, "bold")
        self._brand_lbls = [
            ctk.CTkLabel(_trow, text="Free", font=_f, text_color="#e0ac42"),
            ctk.CTkLabel(_trow, text="", width=7),
            ctk.CTkLabel(_trow, text="AI", font=_f, text_color="#c6763a"),
            ctk.CTkLabel(_trow, text="", width=7),
            ctk.CTkLabel(_trow, text="Reader", font=_f, text_color="#e0ac42"),
        ]
        for _lbl in self._brand_lbls:
            _lbl.pack(side="left")
            _lbl.configure(cursor="hand2")
            _lbl.bind("<Button-1>", self._open_donate_page)   # клик по названию — донаты

        # кнопка благодарности справа от названия; исчезает после перехода к оплате
        self.donate_btn = None
        if not getattr(self, "donate_done", False):
            self.donate_btn = ctk.CTkButton(brand, text="Благодарить", width=104, height=26,
                                            corner_radius=8, font=(FONT_FAMILY, 12, "bold"),
                                            fg_color="#c6763a", hover_color="#b0652f",
                                            text_color="#ffffff",
                                            command=self._open_donate_dialog)
            self.donate_btn.pack(side="left", padx=(16, 0))

        self.status_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        self.status_frame.grid(row=0, column=1, sticky="e", padx=(24, 14))
        self.status_label_main = ctk.CTkLabel(self.status_frame, text="Готово", font=FONT_TINY,
                                              text_color=COLOR_TEXT_SEC, anchor="e", justify="right")
        self.status_label_main.pack(side="right")

        self.ram_label = ctk.CTkLabel(topbar, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC, anchor="e")
        # кнопки языка — узкие, чтобы не растягивали шапку
        self.lang_toggle = SegmentToggle(topbar, values=["RU", "EN"], height=28,
                                          btn_width=34, command=self._set_lang)
        self.lang_toggle.set("EN" if UI_LANG == "en" else "RU")   # как в прошлый раз
        self.lang_toggle.grid(row=0, column=3, sticky="e", padx=(0, 4))
        self.ram_label.grid(row=0, column=2, sticky="e", padx=(0, 12))

        # ---------------- левая панель ----------------
        # карточки лежат прямо на фоне окна — без внешней панели и прокрутки
        self.sidebar = ctk.CTkFrame(self, width=330, fg_color="transparent")
        self.sidebar.grid(row=1, column=0, sticky="nsew", padx=(20, 8), pady=(8, 16))

        def make_card(title):
            card = ctk.CTkFrame(self.sidebar, fg_color=COLOR_CARD, corner_radius=R_CARD,
                                border_width=1, border_color=COLOR_BORDER)
            card.pack(fill="x", padx=2, pady=(0, 8))
            self._card_head(card, title)
            return card

        # ----- Источник -----
        src = make_card("ИСТОЧНИК")

        url_row = ctk.CTkFrame(src, fg_color="transparent")
        url_row.pack(fill="x", padx=12, pady=(0, 7))
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(url_row, placeholder_text="Ссылка на статью",
                                      font=FONT_NORMAL, height=32, corner_radius=3,
                                      fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                                      text_color=COLOR_TEXT_MAIN)
        self.url_entry.grid(row=0, column=0, sticky="ew")

        self.btn_paste = ctk.CTkButton(url_row, text="📋", width=34, height=32, corner_radius=3,
                                       font=FONT_SMALL, fg_color=COLOR_FILL_SOFT,
                                       hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                                       command=self.paste_url)
        self.btn_paste.grid(row=0, column=1, padx=(6, 0))

        try:
            # add="+" обязателен: без него перетирается обработчик customtkinter,
            # который убирает placeholder «Ссылка на статью» при фокусе
            self.url_entry._entry.bind("<FocusIn>", self._url_select_all, add="+")
            self.url_entry._entry.bind("<Button-1>", self._url_select_all, add="+")
            self._bind_ctrl_v(self.url_entry._entry, self._url_paste)
            self._attach_text_menu(self.url_entry._entry)
            self._bind_clipboard_keys(self.url_entry._entry)
        except Exception as e:
            print(f"⚠️ Привязки url: {e}")

        preset_row = ctk.CTkFrame(src, fg_color="transparent")
        preset_row.pack(fill="x", padx=12, pady=(0, 7))
        preset_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(preset_row, text="Сжатие", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC).grid(row=0, column=0, sticky="w")

        self.preset_menu = ctk.CTkOptionMenu(preset_row, values=self.preset_values(),
                                             command=self.on_preset_select,
                                             font=FONT_SMALL, height=30, corner_radius=3, width=150,
                                             fg_color=COLOR_CARD2, button_color=COLOR_FILL_SOFT,
                                             button_hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                                             dropdown_fg_color="#ffffff", dropdown_text_color=COLOR_TEXT_MAIN,
                                             dropdown_hover_color=COLOR_SELECT)
        self.preset_menu.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkButton(preset_row, text="＋", width=30, height=30, corner_radius=3, font=FONT_NORMAL,
                      fg_color=COLOR_CARD2, hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                      border_width=1, border_color=COLOR_BORDER,
                      command=self.edit_selected_preset).grid(row=0, column=2, sticky="e", padx=(6, 0))

        self.instruction_entry = ctk.CTkTextbox(src, height=74, corner_radius=3, font=FONT_SMALL, wrap="word",
                                                fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER,
                                                text_color=COLOR_TEXT_MAIN)
        self.instruction_entry.pack(fill="x", padx=12, pady=(0, 8))
        self._style_text_selection(self.instruction_entry)
        self.instruction_entry._textbox.bind("<FocusIn>", lambda e: self.instruction_entry.configure(height=150), add="+")
        self.instruction_entry._textbox.bind("<FocusOut>", lambda e: self.instruction_entry.configure(height=74), add="+")
        self._bind_ctrl_v(self.instruction_entry._textbox,
                          lambda e: self._paste_widget(self.instruction_entry, e))
        self._bind_clipboard_keys(self.instruction_entry._textbox)
        self._attach_text_menu(self.instruction_entry._textbox,
                               on_insert=lambda t: self.instruction_entry.insert("insert", t))

        run_row = ctk.CTkFrame(src, fg_color="transparent")
        run_row.pack(fill="x", padx=12, pady=(0, 5))
        run_row.grid_columnconfigure(0, weight=1)

        self.btn_process = ctk.CTkButton(run_row, text="Запустить анализ", command=self.start_full_process,
                                         height=34, corner_radius=3, font=(FONT_FAMILY, 12, "bold"),
                                         fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                                         text_color=COLOR_ON_ACCENT)
        self.btn_process.grid(row=0, column=0, sticky="ew")

        self.btn_cancel = ctk.CTkButton(run_row, text="Остановить", width=104, height=34, corner_radius=3,
                                        font=(FONT_FAMILY, 12), fg_color=COLOR_FILL_SOFT,
                                        hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                                        border_width=1, border_color=COLOR_BORDER,
                                        command=self.cancel_processes)
        self.btn_cancel.grid(row=0, column=1, padx=(6, 0))

        self.auto_play_cb = ctk.CTkSwitch(src, text="Озвучивать сразу после анализа", variable=self.auto_play_var,
                                          font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                                          progress_color=COLOR_ACCENT, fg_color=COLOR_SWITCH_OFF,
                                          button_color="#ffffff", button_hover_color="#ffffff",
                                          command=self.save_settings)
        self.auto_play_cb.pack(fill="x", padx=12, pady=(0, 9))

        # ----- Модель ИИ -----
        ai = make_card("МОДЕЛЬ ИИ")

        llm_row = ctk.CTkFrame(ai, fg_color="transparent")
        llm_row.pack(fill="x", padx=12, pady=(0, 3))
        llm_row.grid_columnconfigure(0, weight=1)

        # как верхний список «Сжатие»: тот же CTkOptionMenu и те же цвета
        self.llm_combo = ctk.CTkOptionMenu(llm_row, values=[], font=FONT_SMALL, height=30,
                                           corner_radius=3, command=self.on_llm_change,
                                           fg_color=COLOR_CARD2, button_color=COLOR_FILL_SOFT,
                                           button_hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                                           dropdown_fg_color="#ffffff", dropdown_text_color=COLOR_TEXT_MAIN,
                                           dropdown_hover_color=COLOR_SELECT)
        self.llm_combo.grid(row=0, column=0, sticky="ew")

        self.btn_llm_browse = ctk.CTkButton(llm_row, text="Другая модель", width=110, height=30,
                                            corner_radius=3, font=FONT_TINY,
                                            fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                            text_color=COLOR_TEXT_MAIN,
                                            command=self.pick_llm_file)
        self.btn_llm_browse.grid(row=0, column=2, padx=(6, 0))

        # компактная кнопка «скачать модель» — та же, что предлагается при первом запуске
        self.btn_llm_dl = ctk.CTkButton(llm_row, text="⬇", width=30, height=30,
                                        corner_radius=3, font=(FONT_FAMILY, 13, "bold"),
                                        fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                        text_color=COLOR_TEXT_MAIN,
                                        command=lambda: self._offer_model_download(force=True))
        self.btn_llm_dl.grid(row=0, column=1, padx=(6, 0))

        # Слева — процессор, справа — видеокарта: положение тумблера = где считает модель
        gpu_row = ctk.CTkFrame(ai, fg_color="transparent")
        gpu_row.pack(fill="x", padx=12, pady=(2, 2))

        self.lbl_mode_cpu = ctk.CTkLabel(gpu_row, text="Процессор", font=FONT_SMALL,
                                         text_color=COLOR_TEXT_MAIN, anchor="w")
        self.lbl_mode_cpu.pack(side="left")

        self.llm_gpu_cb = ctk.CTkSwitch(gpu_row, text="", variable=self.llm_gpu_var, width=40,
                                        progress_color=COLOR_TEXT_MAIN, fg_color=COLOR_SWITCH_OFF,
                                        button_color="#ffffff", button_hover_color="#ffffff",
                                        command=self._on_gpu_toggle)
        self.llm_gpu_cb.pack(side="left", padx=8)

        self.lbl_mode_gpu = ctk.CTkLabel(gpu_row, text="Видеокарта", font=FONT_SMALL,
                                         text_color=COLOR_TEXT_SEC, anchor="w")
        self.lbl_mode_gpu.pack(side="left")

        self.llm_limit_label = ctk.CTkLabel(ai, text="…", font=FONT_TINY,
                                            text_color=COLOR_TEXT_SEC, anchor="w")
        self.llm_limit_label.pack(fill="x", padx=12, pady=(0, 4))

        ctx_row = ctk.CTkFrame(ai, fg_color="transparent")
        ctx_row.pack(fill="x", padx=12, pady=(0, 7))
        ctx_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ctx_row, text="Контекст", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC).grid(row=0, column=0, sticky="w")

        self.ctx_slider = ctk.CTkSlider(ctx_row, from_=MIN_CTX, to=8192, number_of_steps=8192 - MIN_CTX,
                                        command=self._on_ctx_slider, height=16,
                                        progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
                                        button_hover_color=COLOR_ACCENT_HOVER, fg_color=COLOR_BORDER)
        self.ctx_slider.grid(row=0, column=1, sticky="ew", padx=7)

        self.ctx_entry = ctk.CTkEntry(ctx_row, font=FONT_TINY, width=78, justify="right", height=26,
                                      corner_radius=3, fg_color=COLOR_CARD2, border_width=1,
                                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN)
        self.ctx_entry.grid(row=0, column=2, sticky="e")
        self.ctx_entry.bind("<Return>", lambda e: self._apply_ctx_exact())
        self.ctx_entry.bind("<FocusOut>", lambda e: self._apply_ctx_exact())
        self._attach_text_menu(self.ctx_entry._entry)

        # ----- Озвучка -----
        tts = make_card("ОЗВУЧКА")

        self.engine_menu = SegmentToggle(tts, values=self.ENGINE_VALUES,
                                         command=self.on_engine_change, height=30)
        self.engine_menu.pack(fill="x", padx=12, pady=(0, 3))

        # Пояснение к выбранному движку (для Vox — требование к видеопамяти)
        self.engine_hint = ctk.CTkLabel(tts, text="", font=FONT_SMALL, text_color=COLOR_TEXT_MAIN,
                                        anchor="w", justify="left", wraplength=336)
        self.engine_hint.pack(fill="x", padx=12, pady=(0, 7))

        # дополнение Vox не стоит — рядом с движком кнопка, чтобы можно было поставить вручную
        self.btn_vox_install = ctk.CTkButton(
            tts, text="⬇ " + _tr("Установить дополнение Vox"), font=FONT_SMALL, height=28,
            corner_radius=3, fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_MAIN, command=self._offer_vox)
        if not self._vox_installed():
            self.btn_vox_install.pack(fill="x", padx=12, pady=(0, 7))

        voice_row = ctk.CTkFrame(tts, fg_color="transparent")
        voice_row.pack(fill="x", padx=12, pady=(0, 7))
        voice_row.grid_columnconfigure(0, weight=1)

        # как верхний список «Сжатие»: тот же CTkOptionMenu и те же цвета
        self.tts_combo = ctk.CTkOptionMenu(voice_row, values=[], font=FONT_SMALL, height=30,
                                           corner_radius=3, command=self.on_tts_change,
                                           fg_color=COLOR_CARD2, button_color=COLOR_FILL_SOFT,
                                           button_hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                                           dropdown_fg_color="#ffffff", dropdown_text_color=COLOR_TEXT_MAIN,
                                           dropdown_hover_color=COLOR_SELECT)
        self.tts_combo.grid(row=0, column=0, sticky="ew")

        # скачать/импортировать голос Piper (в установленной сборке идёт только один)
        self.btn_voice_pack = ctk.CTkButton(voice_row, text="⬇", width=30, height=30,
                                            corner_radius=3, font=(FONT_FAMILY, 13, "bold"),
                                            fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                            text_color=COLOR_TEXT_MAIN,
                                            command=self._open_piper_voices)
        self.btn_voice_pack.grid(row=0, column=1, padx=(6, 0))

        self.rate_row = ctk.CTkFrame(tts, fg_color="transparent")
        self.rate_row.pack(fill="x", padx=12, pady=(0, 10))
        self.rate_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.rate_row, text="Скорость", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC).grid(row=0, column=0, sticky="w")
        self.rate_slider = ctk.CTkSlider(self.rate_row, from_=0.5, to=1.5, number_of_steps=10,
                                         command=self._on_rate_slider, height=16,
                                         progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
                                         button_hover_color=COLOR_ACCENT_HOVER, fg_color=COLOR_BORDER)
        self.rate_slider.grid(row=0, column=1, sticky="ew", padx=7)
        self.rate_slider.set(1.0)
        self.rate_label = ctk.CTkLabel(self.rate_row, text="×1.0", font=(FONT_FAMILY, 10, "bold"),
                                       text_color=COLOR_TEXT_MAIN, width=36, anchor="e")
        self.rate_label.grid(row=0, column=2, sticky="e")

        # «Образец голоса» — отдельная большая кнопка во всю ширину
        self.btn_add_voice = ctk.CTkButton(tts, text="🎙  Образец голоса", height=30,
                                           corner_radius=3, font=FONT_SMALL,
                                           fg_color=COLOR_FILL_SOFT, hover_color=COLOR_SELECT,
                                           text_color=COLOR_TEXT_MAIN,
                                           border_width=1, border_color=COLOR_BORDER,
                                           command=lambda: self.add_custom_voice())
        self.btn_add_voice.pack(fill="x", padx=12, pady=(0, 10), before=self.rate_row)
        self.btn_add_voice.pack_forget()  # показываем только для кастомных голосов

        # ---------------- правая область ----------------
        self.main_area = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=R_PANEL,
                                      border_width=1, border_color=COLOR_BORDER)
        self.main_area.grid(row=1, column=1, sticky="nsew", padx=(8, 20), pady=(8, 16))
        self._add_gloss(self.main_area, height=60)
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main_area, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        header.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(header, text="ТЕКСТ", font=(FONT_FAMILY, 10, "bold"),
                     text_color=COLOR_TEXT_SEC).grid(row=0, column=0, sticky="w", padx=(8, 0))

        self.char_count_label = ctk.CTkLabel(header, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC)
        self.char_count_label.grid(row=0, column=1, padx=(10, 0), sticky="w")

        self.btn_paste_text = ctk.CTkButton(header, text="Вставить", command=self.paste_own_text,
                                            width=92, height=28, corner_radius=3, font=FONT_SMALL,
                                            fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                            text_color=COLOR_TEXT_MAIN)
        self.btn_paste_text.grid(row=0, column=3, padx=(6, 0))

        self.btn_file = ctk.CTkButton(header, text="Файл", command=self.insert_file,
                                      width=80, height=28, corner_radius=3, font=FONT_SMALL,
                                      fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                      text_color=COLOR_TEXT_MAIN)
        self.btn_file.grid(row=0, column=4, padx=(6, 0))

        self.btn_clear = ctk.CTkButton(header, text="Очистить", command=self._clear_box,
                                       width=90, height=28, corner_radius=3, font=FONT_SMALL,
                                       fg_color="transparent", hover_color=COLOR_FILL_SOFT,
                                       text_color=COLOR_TEXT_SEC)
        self.btn_clear.grid(row=0, column=5, padx=(6, 0))

        self.result_box = ctk.CTkTextbox(self.main_area, wrap="word", font=(FONT_FAMILY, 13),
                                         corner_radius=R_CARD, fg_color=COLOR_CARD,
                                         text_color=COLOR_TEXT_MAIN,
                                         border_width=1, border_color=COLOR_BORDER)
        self.result_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 4))
        self._style_text_selection(self.result_box)

        try:
            tb = self.result_box._textbox
            self._bind_ctrl_v(tb, lambda e: self._paste_result(e))
            self._bind_clipboard_keys(tb)
            self._attach_text_menu(tb, on_insert=lambda t: self._insert_result(t))
            tb.bind("<<Modified>>", self._on_box_modified, add="+")
            tb.bind("<FocusIn>", self._on_box_focus, add="+")
        except Exception as e:
            print(f"⚠️ Привязки result: {e}")

        stats_row = ctk.CTkFrame(self.main_area, fg_color="transparent")
        stats_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 4))
        stats_row.grid_columnconfigure(0, weight=1)

        self.stats_label = ctk.CTkLabel(stats_row, text="", font=FONT_TINY,
                                        text_color=COLOR_TEXT_SEC, anchor="w")
        self.stats_label.grid(row=0, column=0, sticky="w")

        self.btn_restore = ctk.CTkButton(stats_row, text="↩ Исходный текст", command=self._restore_source,
                                         width=136, height=24, corner_radius=3, font=FONT_TINY,
                                         fg_color="transparent", hover_color=COLOR_FILL_SOFT,
                                         text_color=COLOR_ACCENT)
        self.btn_restore.grid(row=0, column=1, sticky="e")
        self.btn_restore.grid_remove()

        self.audio_control_frame = ctk.CTkFrame(self.main_area, height=60, corner_radius=R_CARD,
                                                fg_color=COLOR_CARD2, border_width=1,
                                                border_color=COLOR_BORDER)
        self.audio_control_frame.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.audio_control_frame.grid_columnconfigure(3, weight=1)

        self.btn_play = ctk.CTkButton(self.audio_control_frame, text="Озвучить", command=self.play_result,
                                      width=140, height=36, corner_radius=3, font=(FONT_FAMILY, 12, "bold"),
                                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                                      text_color=COLOR_ON_ACCENT)
        self.btn_play.grid(row=0, column=0, padx=(14, 6), pady=12)

        # Стоп — в том же стиле, что Play/Pause: рисованный квадратик-иконка
        self._make_pp_icons()
        self.btn_stop = ctk.CTkButton(self.audio_control_frame, text="",
                                      image=self._stop_icon,
                                      width=44, height=36, corner_radius=3,
                                      fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                      text_color=COLOR_TEXT_MAIN,
                                      command=self.stop_playback)
        self.btn_stop.grid(row=0, column=1, padx=(0, 4), pady=12)

        # Play/Pause — комбинированный значок ⏯ (треугольник + две полосы, как клавиша ноутбука).
        # Значок статичный; когда играет — кнопка тёмная, на паузе — светлая.
        self.btn_pp = ctk.CTkButton(self.audio_control_frame, text="",
                                    image=self._pp_light,
                                    width=44, height=36, corner_radius=3,
                                    fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                    text_color=COLOR_TEXT_MAIN,
                                    command=self._toggle_play_pause)
        self.btn_pp.grid(row=0, column=2, padx=(0, 8), pady=12)

        self.progress_bar = ctk.CTkProgressBar(self.audio_control_frame, height=6, corner_radius=3,
                                               progress_color=COLOR_ACCENT, fg_color=COLOR_BORDER)
        self.progress_bar.grid(row=0, column=3, padx=14, pady=12, sticky="ew")
        self.progress_bar.set(0)

        self.lbl_audio_status = ctk.CTkLabel(self.audio_control_frame, text="Готово", font=FONT_SMALL,
                                             text_color=COLOR_TEXT_SEC)
        self.lbl_audio_status.grid(row=0, column=4, padx=14, sticky="e")

        self._update_ram_label()

        self.bind("<Control-Return>", lambda e: self.start_full_process())
        self.bind("<F5>", lambda e: self.play_result())
        self.after(40, self._place_window)

    def _place_window(self):
        """Ставит окно по центру экрана и не даёт содержимому его раздуть."""
        try:
            self.update_idletasks()
            w, h = 1140, 790
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            x = max(20, (sw - w) // 2)
            y = max(20, (sh - h) // 3)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _clear_box(self):
        self._set_box_text("", generated=False)
        self._show_placeholder()

    def _placeholder_text(self):
        """Заглушка пустого поля на языке интерфейса (переводим явно, без таблицы)."""
        return self.PLACEHOLDER_EN if UI_LANG == "en" else self.PLACEHOLDER

    def _show_placeholder(self):
        self._suppress_box_events = True
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", self._placeholder_text())
        try:
            self.result_box.configure(text_color=COLOR_TEXT_SEC)
        except Exception:
            pass
        self._suppress_box_events = False
        self._placeholder_active = True
        self._result_is_generated = False
        self.box_is_source = False
        try:
            self.result_box._textbox.edit_modified(False)
        except Exception:
            pass
        self._update_char_count()

    def _hide_placeholder(self):
        if not self._placeholder_active:
            return
        self._placeholder_active = False
        self._suppress_box_events = True
        self.result_box.delete("1.0", "end")
        self._suppress_box_events = False
        try:
            self.result_box.configure(text_color=COLOR_TEXT_MAIN)
        except Exception:
            pass

    def _on_box_focus(self, event=None):
        if self._placeholder_active:
            self._hide_placeholder()

    def _set_box_text(self, text, generated=False):
        self._suppress_box_events = True
        self._placeholder_active = False
        try:
            self.result_box.configure(text_color=COLOR_TEXT_MAIN)
        except Exception:
            pass
        self.result_box.delete("1.0", "end")
        if text:
            self.result_box.insert("1.0", text)
        self._suppress_box_events = False
        self._result_is_generated = bool(generated and text)
        self.box_is_source = bool(text) and not generated
        try:
            self.result_box._textbox.edit_modified(False)
            self.result_box._textbox.mark_set("insert", "1.0")
            self.result_box._textbox.see("1.0")
        except Exception:
            pass
        self._update_char_count()
        try:
            if self._last_source and generated:
                self.btn_restore.grid()
            else:
                self.btn_restore.grid_remove()
        except Exception:
            pass

    def _on_box_modified(self, event=None):
        try:
            tb = self.result_box._textbox
            if not tb.edit_modified():
                return
            tb.edit_modified(False)
        except Exception:
            pass
        if self._suppress_box_events:
            return
        if self._placeholder_active:
            self._hide_placeholder()
            self._update_char_count()
            return
        self._result_is_generated = False
        self.box_is_source = bool(self.result_box.get("1.0", "end-1c").strip())
        self._update_char_count()

    def _update_char_count(self):
        try:
            if self._placeholder_active:
                self.char_count_label.configure(text="")
                return
            n = len(self.result_box.get("1.0", "end-1c").strip())
            self.char_count_label.configure(
                text=_tr(f"{n:,} зн.".replace(",", " ")) if n else "")
        except Exception:
            pass

    def _restore_source(self):
        if self._last_source:
            self._set_box_text(self._last_source, generated=False)
            self.update_status("↩ Возвращён исходный текст")

    def _paste_widget(self, widget, event=None):
        text = self._clip_text()
        if text:
            self._insert_replacing_selection(widget, text)
        return "break"

    @staticmethod
    def _insert_replacing_selection(widget, text):
        """Вставка в поле: если что-то выделено — заменить выделенное, а не дописать в конец."""
        inner = getattr(widget, "_textbox", None) or getattr(widget, "_entry", None) or widget
        start = None
        try:
            start = inner.index("sel.first")
        except Exception:
            start = None
        if start is not None:
            try:
                inner.delete("sel.first", "sel.last")
                inner.insert(start, text)
                try:
                    inner.mark_set("insert", f"{start}+{len(text)}c")
                    inner.see("insert")
                except Exception:
                    pass
                return
            except Exception:
                pass
        try:
            widget.insert("insert", text)
        except Exception:
            try:
                widget.insert("end", text)
            except Exception:
                pass

    def _insert_result(self, text):
        if self._placeholder_active:
            self._hide_placeholder()
        self._insert_replacing_selection(self.result_box, text)
        self._result_is_generated = False
        self.box_is_source = bool(self.result_box.get("1.0", "end-1c").strip())
        self._update_char_count()

    def _paste_result(self, event=None):
        text = self._clip_text()
        if text:
            self._insert_result(text)
        return "break"

    def _url_select_all(self, event):
        try:
            self.url_entry._entry.after(0, lambda: self.url_entry._entry.select_range(0, "end"))
        except Exception:
            pass

    def create_section_header(self, parent, text, row):
        ctk.CTkLabel(parent, text=text, font=FONT_SUBHEADER, text_color=COLOR_HEAD, anchor="w").grid(row=row, column=0,
                                                                                                     padx=20,
                                                                                                     pady=(15, 5),
                                                                                                     sticky="w")
        ctk.CTkFrame(parent, height=2, fg_color=COLOR_BORDER).grid(row=row + 1, column=0, padx=20, pady=(0, 8),
                                                                   sticky="ew")

    def create_modern_combo(self, parent, label_text, row, command=None, width=None):
        ctk.CTkLabel(parent, text=label_text, font=FONT_NORMAL, text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=row,
                                                                                                             column=0,
                                                                                                             padx=20,
                                                                                                             pady=(5,
                                                                                                                   5),
                                                                                                             sticky="w")
        kwargs = {"values": [], "state": "readonly", "font": FONT_NORMAL, "command": command}
        if width:
            kwargs["width"] = width
        combo = ctk.CTkComboBox(parent, **kwargs)
        combo.grid(row=row + 1, column=0, padx=20, pady=5, sticky="ew")
        combo.configure(fg_color=COLOR_CARD2, dropdown_fg_color="#ffffff",
                        button_color=COLOR_FILL_SOFT, button_hover_color=COLOR_SELECT,
                        dropdown_hover_color=COLOR_SELECT,
                        border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN)
        self._attach_combo_hover(combo)
        return combo

    # ================= КОНТЕКСТ =================

    def _probe_model(self, disp):
        if not disp:
            return
        if disp in self.model_meta:
            self.refresh_model_info()
            return
        actual = self.llm_display.get(disp, disp)
        path = self.llm_models.get(actual)
        if not path:
            return

        def work():
            ctx, kv = None, 131072
            try:
                m = Llama(model_path=path, vocab_only=True, verbose=False)
                try:
                    ctx = int(m.n_ctx_train())
                except Exception:
                    ctx = None
                md = m.metadata
                if not ctx or ctx <= 0:
                    for k in ("llama.context_length", "qwen2.context_length",
                              "mistral.context_length", "phi3.context_length",
                              "gemma.context_length", "general.context_length"):
                        try:
                            ctx = int(md[k])
                            break
                        except Exception:
                            continue
                try:
                    arch = str(md["general.architecture"])
                    layers = int(md[f"{arch}.block_count"])
                    kv_heads = int(md[f"{arch}.attention.head_count_kv"])
                    heads = int(md[f"{arch}.attention.head_count"])
                    emb = int(md[f"{arch}.embedding_length"])
                    kv = 2 * layers * kv_heads * (emb // heads) * 2
                except Exception:
                    pass
                if not ctx or ctx <= 0:
                    try:
                        for key in list(md.keys()):
                            if str(key).endswith("context_length"):
                                ctx = int(md[key])
                                break
                    except Exception:
                        pass
            except Exception as e:
                print(f"⚠️ Не удалось прочитать метаданные: {e}")

            if not ctx or ctx <= 0:
                ctx = 4096
            try:
                fsize = os.path.getsize(path)
            except Exception:
                fsize = 0

            self.model_meta[disp] = {"ctx": ctx, "kv": kv, "file_size": fsize}
            print(f"📐 {disp}: родной контекст {ctx} токенов")
            self.after(0, self.refresh_model_info)

        threading.Thread(target=work, daemon=True).start()

    def refresh_model_info(self):
        disp = self.llm_combo.get()
        meta = self.model_meta.get(disp)
        if not meta:
            self.llm_limit_label.configure(text="…", text_color=COLOR_TEXT_SEC)
            return

        native = min(meta["ctx"], 262144)  # ограничение слайдера
        self.ctx_slider.configure(from_=MIN_CTX, to=native, number_of_steps=native - MIN_CTX)

        chosen = self.ctx_choices.get(self._actual_llm())
        used = min(int(chosen), native) if chosen else native
        used = max(MIN_CTX, used)
        self.ctx_slider.set(used)

        try:
            if self.ctx_entry.focus_get() != self.ctx_entry._entry:
                self.ctx_entry.delete(0, "end")
                self.ctx_entry.insert(0, f"{used:,}".replace(",", " "))
        except Exception:
            self.ctx_entry.delete(0, "end")
            self.ctx_entry.insert(0, f"{used:,}".replace(",", " "))

        chars = max(2000, int((used - 800) * 1.8))
        self.model_ctx[disp] = used
        self.model_limits[disp] = chars

        mem = meta["file_size"] * 1.05 + meta["kv"] * used
        gb = mem / (1024 ** 3)

        rt, ra = self._sys_mem_info()
        if ra:
            color = COLOR_GREEN if mem <= ra else COLOR_RED
        else:
            color = COLOR_TEXT_SEC
        self.llm_limit_label.configure(text=_tr(f"{used:,} ток. · ≈ {gb:.1f} ГБ").replace(",", " "),
                                       text_color=color)
        self._update_ram_label()

    def _on_ctx_slider(self, value):
        disp = self.llm_combo.get()
        if disp not in self.model_meta:
            return
        used = int(round(value))
        self.ctx_choices[self._actual_llm()] = str(used)
        self.refresh_model_info()
        self.save_settings()

    def _apply_ctx_exact(self):
        disp = self.llm_combo.get()
        meta = self.model_meta.get(disp)
        if not meta:
            return
        try:
            v = int(re.sub(r"\s+", "", self.ctx_entry.get()))
        except Exception:
            return
        native = min(meta["ctx"], 262144)
        v = max(MIN_CTX, min(v, native))
        self.ctx_choices[self._actual_llm()] = str(v)
        self.refresh_model_info()
        self.save_settings()
        self.update_status(f"Контекст: {v} токенов")

    def _on_rate_slider(self, value):
        self.speech_rate = round(value, 1)
        self.rate_label.configure(text=f"×{self.speech_rate:.1f}")
        self.save_settings()

    def set_progress(self, pct, label):
        pct = int(max(0, min(100, pct)))
        if self._last_pct != pct:
            self._last_pct = pct
            self.update_status(f"{_tr(label)} {pct}%")
        try:
            self.progress_bar.stop()          # выключаем «бегущую» анимацию
            self.progress_bar.set(pct / 100)  # показываем реальную долю
        except Exception:
            pass

    # ================= ВСТАВКА =================

    def _url_paste(self, event=None):
        self.paste_url()
        return "break"

    def paste_url(self):
        text = self._clip_text().strip()
        if text:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
            self.update_status("✅ Ссылка вставлена")
        else:
            self.update_status("Буфер обмена пуст")

    def paste_own_text(self):
        text = self._clip_text().strip()
        if not text:
            messagebox.showinfo("Буфер обмена", "Буфер пуст. Скопируйте текст для озвучки.")
            return
        self._put_source_text(text, "текст из буфера")

    def _put_source_text(self, text, name):
        self._last_source = text
        self._set_box_text(text, generated=False)
        self.update_status(f"✅ Вставлено: {name[:40]}. Анализ пойдёт по этому тексту.")

    # ================= ФАЙЛЫ PDF/DOC =================

    def insert_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл (pdf, docx, txt)",
            filetypes=[("Документы", "*.pdf *.docx *.doc *.txt"), ("All files", "*.*")])
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".pdf":
                if not PYPDF_AVAILABLE:
                    raise Exception("Установите: pip install pypdf")
                reader = PdfReader(path)
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
                articles = self._segment_articles(text)
                if len(articles) > 2:
                    PdfArticlesDialog(self, articles, self._pick_article)
                    return
            elif ext == ".docx":
                if not DOCX_AVAILABLE:
                    raise Exception("Установите: pip install python-docx")
                text = "\n".join(p.text for p in Document(path).paragraphs)
            elif ext == ".doc":
                raise Exception("Старый формат .doc не поддерживается.\nСохраните документ как .docx.")
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if len(text) < 100:
                raise Exception("В файле не найден текст (возможно, скан без текстового слоя).")
            self._put_source_text(text, os.path.basename(path))
        except Exception as e:
            messagebox.showerror("Файл", str(e))

    def _pick_article(self, article):
        self._put_source_text(article["text"], article["title"])

    def _segment_articles(self, full):
        full = re.sub(r"\n{3,}", "\n\n", full)
        articles = [{"title": "📖 Весь журнал целиком", "text": full}]
        matches = list(
            re.finditer(r"(?:^|\n)[^\n]{0,60}?(УДК\s*\d[\d.:]*|DOI:?\s*10\.\d{4,}/\S+)", full, re.IGNORECASE))
        if len(matches) > 2:
            starts = [m.start() for m in matches]
            for i, s in enumerate(starts):
                e = starts[i + 1] if i + 1 < len(starts) else len(full)
                block = full[s:e].strip()
                if len(block) < 300:
                    continue
                articles.append({"title": f"{len(articles)}. {self._extract_title(block)}", "text": block})
        elif len(matches) == 1:
            articles.append({"title": f"2. {self._extract_title(full[matches[0].start():])}",
                             "text": full[matches[0].start():]})
        return articles

    def _extract_title(self, block):
        lines = [l.strip() for l in block.split("\n")[:8] if l.strip()]
        for l in lines:
            if re.match(r"(УДК|DOI|©|ISSN|http)", l, re.I):
                continue
            if re.search(r"@[a-z0-9.-]+\.(ru|com|org|net)", l, re.I):
                continue
            if len(l) < 8 or len(l) > 120 or l.isdigit():
                continue
            return l
        return "Статья без названия"

    # ================= НОРМАЛИЗАЦИЯ =================

    def _num_match_to_ru(self, m):
        s = m.group(0).replace(',', '.')
        try:
            if '.' in s:
                return num2words(float(s), lang='ru')
            return num2words(int(s), lang='ru')
        except Exception:
            return s

    def normalize_for_tts(self, text: str) -> str:
        for en, ru in EN_RU_GLOSSARY:
            text = re.sub(rf"\b{re.escape(en)}\b", ru, text)
        if NUM2WORDS_AVAILABLE:
            text = re.sub(
                r"(?<![A-Za-zА-Яа-яЁё_])(\d+(?:[.,]\d+)?)\s*%",
                lambda m: self._num_match_to_ru(m) + " процентов", text)
            text = re.sub(
                r"(?<![A-Za-zА-Яа-яЁё_0-9])(\d+(?:[.,]\d+)?)(?![A-Za-zА-Яа-яЁё_0-9])",
                self._num_match_to_ru, text)
        return text

    # ================= ГОЛОСА-ОБРАЗЦЫ =================

    # --- слоты голосов: имя задаёт пользователь, количество не ограничено ---

    def _voice_items(self):
        """[(id, info)] в порядке номеров слотов."""
        def key(item):
            try:
                return (0, int(item[0]))
            except Exception:
                return (1, str(item[0]))
        return sorted(self.custom_voices.items(), key=key)

    def _find_voice(self, name):
        """(id, info) по названию голоса или (None, None)."""
        if not name:
            return None, None
        for vid, info in self._voice_items():
            if isinstance(info, dict) and (info.get("name") or "") == name:
                return vid, info
        return None, None

    def voice_values(self):
        """Названия всех слотов для списка «Озвучка»."""
        return [i.get("name") for _, i in self._voice_items() if isinstance(i, dict) and i.get("name")]

    def _next_voice_id(self):
        used = set()
        for vid, _ in self._voice_items():
            try:
                used.add(int(vid))
            except Exception:
                pass
        return str(max(used) + 1 if used else 1)

    def _first_empty_voice(self):
        for vid, info in self._voice_items():
            if isinstance(info, dict) and not (info.get("path") and os.path.exists(info.get("path") or "")):
                return vid, info
        return None, None

    def _ensure_empty_slot(self):
        """Всегда держим один незаполненный слот — в него запишется следующий голос."""
        vid, info = self._first_empty_voice()
        if info is not None:
            return vid, info
        vid = self._next_voice_id()
        info = {"name": f"Свой {vid}", "path": "", "text": ""}
        self.custom_voices[vid] = info
        return vid, info

    def get_ref(self, speaker):
        vid, info = self._find_voice(speaker)
        if info is None:
            raise Exception(f"Голос «{speaker}» не найден. Нажмите «🎙 Образец голоса».")
        path = info.get("path") or ""
        if not path or not os.path.exists(path):
            raise Exception(f"Слот «{speaker}» пуст — запишите образец голоса.")
        return path, info.get("text") or self.REF_TEXT

    # ================= VOXCPM2 (GPU) =================

    PY_EMBED_URL = ("https://www.python.org/ftp/python/3.12.10/"
                    "python-3.12.10-embed-amd64.zip")
    GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

    def _vox_paths(self):
        root = os.path.join(self.BASE_DIR, "vox")
        return root, os.path.join(root, "py"), os.path.join(root, "site")

    def _vox_syspath(self):
        """Подключить папку дополнения Vox (torch + voxcpm) к интерпретатору."""
        _, _, site_dir = self._vox_paths()
        if not os.path.isdir(site_dir):
            return False
        if site_dir not in sys.path:
            sys.path.insert(0, site_dir)
        for sub in ("torch/lib", "torchvision"):
            dll_dir = os.path.join(site_dir, *sub.split("/"))
            if os.path.isdir(dll_dir):
                try:
                    os.add_dll_directory(dll_dir)
                except Exception:
                    pass
        nvidia_root = os.path.join(site_dir, "nvidia")     # cuDNN/cuBLAS из pip-пакетов
        if os.path.isdir(nvidia_root):
            for mod in os.listdir(nvidia_root):
                bin_dir = os.path.join(nvidia_root, mod, "bin")
                if os.path.isdir(bin_dir):
                    try:
                        os.add_dll_directory(bin_dir)
                    except Exception:
                        pass
        return os.path.isdir(os.path.join(site_dir, "voxcpm"))

    def _run_py(self, args, on_line=None):
        """Запустить переносимый питон и вернуть (ok, хвост вывода)."""
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace",
                                  creationflags=flags) as proc:
                self._vox_proc = proc
                tail = []
                for line in proc.stdout:
                    if getattr(self, "_vox_cancelled", False):
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return False, "Отменено"
                    line = line.rstrip()
                    if not line:
                        continue
                    tail.append(line)
                    if len(tail) > 40:
                        tail.pop(0)
                    if on_line:
                        on_line(line)
                code = proc.wait()
            return code == 0, "\n".join(tail)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    def _torch_state(self, site_dir):
        """Что уже лежит в папке дополнения: none / cpu / cuda / mixed."""
        infos = [os.path.basename(p)
                 for p in glob.glob(os.path.join(site_dir, "torch-*.dist-info"))]
        if not infos:
            return "none"
        if len(infos) > 1:
            return "mixed"
        return "cuda" if "cu" in infos[0] else "cpu"

    def _vox_install_work(self, progress, on_line=None):
        """Поставить Vox: переносимый Python + pip + voxcpm в %BASE%/vox. (ok, текст)."""
        import zipfile
        root, py_dir, site_dir = self._vox_paths()
        os.makedirs(root, exist_ok=True)
        py_exe = os.path.join(py_dir, "python.exe")
        has_nvidia = bool(shutil.which("nvidia-smi"))

        if not os.path.isfile(py_exe):
            progress("Python…", 0.02)
            zip_path = os.path.join(root, "python-embed.zip")
            self._fetch_file(self.PY_EMBED_URL, zip_path,
                             lambda d, t: progress("Python…", 0.02 + 0.06 * (d / t if t else 0)))
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(py_dir)
            os.remove(zip_path)
            for name in os.listdir(py_dir):          # в embed-сборке site выключен
                if name.endswith("._pth"):
                    p = os.path.join(py_dir, name)
                    with open(p, encoding="utf-8") as f:
                        txt = f.read()
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(txt.replace("#import site", "import site"))

        # pip install --target не удаляет старые файлы: если в папке оказались две сборки
        # torch (или CPU-сборка на машине с видеокартой) — импорт падает прямо в процессе,
        # приложение вылетает. Такое окружение пересобираем с нуля.
        state = self._torch_state(site_dir)
        if state == "mixed" or (state == "cpu" and has_nvidia):
            progress("Чищу старую сборку torch…", 0.10)
            shutil.rmtree(site_dir, ignore_errors=True)
            os.makedirs(site_dir, exist_ok=True)
            state = "none"

        if not os.path.isdir(os.path.join(site_dir, "voxcpm")) or state == "none":
            def pip_step(extra, lo, hi, title):
                """Шаг pip: строки вида «Progress 12 of 100» превращаем в проценты."""
                def line_cb(line):
                    m = re.search(r"Progress (\d+) of (\d+)", line)
                    if m:
                        cur, tot = int(m.group(1)), max(1, int(m.group(2)))
                        frac = min(1.0, cur / tot)
                        progress(f"{title} — {int(frac * 100)}%", lo + (hi - lo) * frac)
                    elif on_line:
                        on_line(line)
                return self._run_py([py_exe, "-m", "pip", "install", "--no-warn-script-location",
                                     "--progress-bar", "raw", "--target", site_dir] + extra, line_cb)

            progress("pip…", 0.12)
            get_pip = os.path.join(root, "get-pip.py")
            if not os.path.isfile(get_pip):
                self._fetch_file(self.GET_PIP_URL, get_pip)
            ok, out = self._run_py([py_exe, get_pip, "--no-warn-script-location"], on_line)
            if not ok:
                return False, "pip не установился:\n" + out
            if self._vox_cancelled:
                return False, "Отменено"

            # voxcpm на PyPI — sdist: сборка идёт бэкендом в самом интерпретаторе,
            # поэтому setuptools ставим в питон, а не в папку --target
            progress("setuptools…", 0.14)
            ok, out = self._run_py([py_exe, "-m", "pip", "install", "--no-warn-script-location",
                                    "--progress-bar", "off", "--upgrade",
                                    "setuptools", "wheel"], on_line)
            if not ok:
                return False, "setuptools/wheel:\n" + out
            if self._vox_cancelled:
                return False, "Отменено"

            # torch для видеокарты качаем сами: pip при выводе в лог не рисует проценты,
            # и 2,4 ГБ выглядят как зависание
            whl_path = None
            if has_nvidia:
                whl_dir = os.path.join(root, "whl")
                os.makedirs(whl_dir, exist_ok=True)
                whl_path = os.path.join(whl_dir, TORCH_CU_WHL_NAME)
                need = 2_400_000_000
                if not (os.path.isfile(whl_path) and os.path.getsize(whl_path) >= need):
                    self._fetch_file(
                        TORCH_CU_WHL_URL, whl_path,
                        lambda done, total: progress(
                            f"torch для видеокарты — "
                            f"{int(100 * done / total) if total else 0}% "
                            f"({done // 1_048_576} из {total // 1_048_576} МБ)",
                            0.16 + 0.34 * (done / total if total else 0)))
                if self._vox_cancelled:
                    return False, "Отменено"

            # одна команда на всё: pip поставит torch из колеса и подберёт остальные
            # пакеты под него, поэтому второй сборки torch в папке не появится
            args = ["--no-build-isolation", "--upgrade"]
            if whl_path:
                args += [whl_path, "torchaudio==2.5.1",
                         "--extra-index-url", "https://download.pytorch.org/whl/cu121"]
            args += ["voxcpm", "transformers==4.49.0"]   # 5.x требует torch>=2.6 и отключает CUDA-сборку 2.5.1
            ok, out = pip_step(args, 0.50, 0.94, "torch + VoxCPM")
            if self._vox_cancelled:
                return False, "Отменено"
            if ok and whl_path:
                try:
                    os.remove(whl_path)               # колесо больше не нужно
                except Exception:
                    pass
            if not ok:
                return False, "pip install voxcpm:\n" + out
            if not os.path.isdir(os.path.join(site_dir, "voxcpm")):
                return False, "voxcpm не появился в папке дополнения"

        progress("Проверка…", 0.96)
        code = ("import sys; sys.path.insert(0, r'%s'); import torch, voxcpm; "
                "print('VOXOK', voxcpm.__file__, torch.__version__, "
                "torch.cuda.is_available())" % site_dir)
        ok, out = self._run_py([py_exe, "-c", code], on_line)
        return (ok and "VOXOK" in out), out[-600:]

    def _vox_installed(self):
        """Дополнение Vox на месте? (папка дополнения с пакетом voxcpm)"""
        _, _, site_dir = self._vox_paths()
        return os.path.isdir(os.path.join(site_dir, "voxcpm"))

    def _offer_vox(self):
        """Диалог «Поставить Vox?» — сам при первом запуске или из движка озвучки."""
        self.vox_offer_done = True
        self.save_settings()
        _flog("предлагаю дополнение Vox")
        if self.engine_menu.get().startswith("Vox"):
            self._vox_wanted = True
        if messagebox.askyesno(
                _tr("Движок Vox"),
                _tr("Vox — нейроголос по образцу с микрофона.\n\n"
                    "Нужен пакет дополнения: переносимый Python + torch + VoxCPM, "
                    "≈1,5 ГБ загрузки и ~3 ГБ на диске.\n\nСкачать сейчас?")):
            self._install_vox()
        else:
            self.after(300, self._first_run_chain)   # следом — модель анализа

    def _install_vox(self):
        """Установка дополнения Vox с прогрессом и логом pip."""
        old = getattr(self, "_vox_dialog", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except Exception:
            pass

        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Дополнение Vox"))
        dlg.geometry("560x330")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        dlg.after(150, lambda: _apply_dialog_icon(dlg))
        self._vox_dialog = dlg

        body = ctk.CTkFrame(dlg, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(body, text=_tr("Устанавливается дополнение Vox"), font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(16, 2))
        ctk.CTkLabel(body, font=FONT_TINY, text_color=COLOR_TEXT_SEC, justify="left",
                     wraplength=470,
                     text=_tr("Python, torch и VoxCPM ставятся в папку приложения. "
                              "Первый раз это занимает 5–15 минут.")
                     ).pack(padx=16, anchor="w")
        bar = ctk.CTkProgressBar(body, height=10, corner_radius=6, progress_color="#c6763a",
                                 fg_color=COLOR_CARD2)
        bar.set(0)
        bar.pack(fill="x", padx=16, pady=(14, 6))
        stage = ctk.CTkLabel(body, text="", font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w")
        stage.pack(fill="x", padx=16)
        log_lbl = ctk.CTkLabel(body, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC,
                               anchor="w", justify="left", wraplength=500)
        log_lbl.pack(fill="x", padx=16, pady=(2, 2))
        timer = ctk.CTkLabel(body, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC, anchor="w")
        timer.pack(fill="x", padx=16, pady=(0, 6))

        self._vox_cancelled = False
        self._vox_proc = None
        self._vox_t0 = time.time()

        def cancel():
            self._vox_cancelled = True
            proc = getattr(self, "_vox_proc", None)
            try:
                if proc is not None and proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
            try:
                dlg.destroy()
            except Exception:
                pass

        cancel_btn = ctk.CTkButton(body, text=_tr("Отмена"), width=110, height=28,
                                   corner_radius=3, font=FONT_SMALL,
                                   fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                   text_color=COLOR_TEXT_MAIN, command=cancel)
        cancel_btn.pack(pady=(0, 12))

        def tick():
            try:
                if dlg.winfo_exists():
                    secs = int(time.time() - self._vox_t0)
                    timer.configure(text=_tr("Прошло") + f" {secs // 60}:{secs % 60:02d}")
                    dlg.after(1000, tick)
            except Exception:
                pass

        dlg.after(1000, tick)

        def progress(text, value):
            self._ui(stage.configure, text=text)
            if value is not None:
                self._ui(bar.set, max(0.0, min(value, 1.0)))

        def on_line(line):
            self._ui(log_lbl.configure, text=line[:160])

        def work():
            try:
                ok, detail = self._vox_install_work(progress, on_line)
            except Exception as e:
                ok, detail = False, f"{type(e).__name__}: {e}"
            if ok:
                self.after(0, self._vox_ready)
            else:
                self._ui(progress, _tr("Не получилось"), None)
                self._ui(log_lbl.configure, text=detail[-400:])
                self._ui(cancel_btn.configure, text=_tr("Закрыть"), command=dlg.destroy)
                self.after(800, self._first_run_chain)   # могла остаться модель анализа

        threading.Thread(target=work, daemon=True).start()

    def _vox_ready(self):
        self.vox_installed = True
        self._vox_syspath()
        self.save_settings()
        try:
            if getattr(self, "_vox_dialog", None) is not None:
                self._vox_dialog.destroy()
        except Exception:
            pass
        self.update_status(f"✅ {_tr('Vox установлен')}")
        try:
            self.btn_vox_install.pack_forget()      # кнопка установки больше не нужна
        except Exception:
            pass
        if getattr(self, "_vox_wanted", False):
            self._vox_wanted = False
            try:
                self.engine_menu.set("Vox")
                self.on_engine_change("Vox")
            except Exception:
                pass
        self.after(600, self._first_run_chain)    # могла остаться модель анализа

    def _vox_local_weights(self):
        """Готовые веса VoxCPM2: свой models_vox или уже скачанный кэш huggingface."""
        local = os.path.join(self.BASE_DIR, "models_vox")
        if os.path.isdir(local) and os.listdir(local):
            return local
        hub = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
        snaps = os.path.join(hub, "models--openbmb--VoxCPM2", "snapshots")
        if os.path.isdir(snaps):
            for snap in sorted(os.listdir(snaps), reverse=True):
                path = os.path.join(snaps, snap)
                if os.path.isfile(os.path.join(path, "config.json")):
                    return path
        return None

    def load_vox(self, show_errors=False):
        if self.vox_model is not None:
            return True
        self._vox_syspath()
        # Антивирус/прокси подменяет сертификат — huggingface_hub без этого падает
        # на проверке ревизии модели ещё до загрузки весов.
        if not getattr(self, "_ssl_patched", False):
            try:
                import requests.adapters as _ra
                _orig_send = _ra.HTTPAdapter.send

                def _send(self, request, **kw):
                    kw["verify"] = False
                    return _orig_send(self, request, **kw)

                _ra.HTTPAdapter.send = _send
                self._ssl_patched = True
            except Exception:
                pass
        local_weights = self._vox_local_weights()
        if local_weights:
            os.environ["HF_HUB_OFFLINE"] = "1"      # веса на месте — сеть не нужна
        try:
            try:
                from voxcpm import VoxCPM
            except ImportError:
                try:
                    from voxcpm import VoxCPM2 as VoxCPM
                except ImportError:
                    raise Exception(_tr(
                        "Дополнение Vox не установлено.\n\n"
                        "Переключите «Озвучка» на Vox — приложение предложит скачать "
                        "пакет (переносимый Python + torch + VoxCPM, ≈1,5–2,5 ГБ). "
                        "До этого работает Piper с голосами Ирина и Руслан."))

            import torch
            cuda_ok = torch.cuda.is_available()
            print(f"🔎 torch {torch.__version__} · CUDA доступна: {cuda_ok}")

            names = [local_weights] if local_weights else []
            names += VOX_CANDIDATES

            # fp16 быстрее на 3070 Ti; если параметр не принят — пробуем дефолт (bf16)
            kw_list = [{"torch_dtype": torch.float16}, {"dtype": torch.float16}, {}]
            last_err = None
            for name in names:
                for dev in (["cuda", "auto"] if cuda_ok else ["auto"]):
                    for kw in kw_list:
                        try:
                            self.after(0, lambda n=name, d=dev: self.update_status(f"⏳ Загрузка VoxCPM2 ({d})..."))
                            self.vox_model = VoxCPM.from_pretrained(name, device=dev, **kw)
                            self.vox_name = name
                            self._print_vox_device()
                            print(
                                f"🎙 VoxCPM2 загружен: {name} · device={dev} · dtype={list(kw.keys()) or 'bf16 (default)'}")
                            return True
                        except TypeError:
                            continue  # неизвестный kwarg → пробуем следующий
                        except Exception as e:
                            last_err = e
                            print(f"⚠️ VoxCPM2 [{name}, {dev}]: {e}")
                            break  # ошибка устройства → следующий dev
            raise Exception(f"Не удалось загрузить VoxCPM2: {last_err}")
        except Exception as e:
            print(f"❌ Ошибка загрузки VoxCPM2: {e}")
            if show_errors:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Ошибка VoxCPM2", err))
            return False

    def _print_vox_device(self):
        try:
            m = self.vox_model
            dev = None
            # пробуем разные способы узнать устройство
            if hasattr(m, 'device'):
                dev = m.device
            elif hasattr(m, 'model') and hasattr(m.model, 'device'):
                dev = m.model.device
            elif hasattr(m, 'model') and hasattr(m.model, 'parameters'):
                try:
                    dev = next(m.model.parameters()).device
                except Exception:
                    pass
            else:
                try:
                    dev = next(m.parameters()).device
                except Exception:
                    pass

            # если всё равно None — проверяем, есть ли CUDA в логах загрузки
            if dev is None:
                try:
                    import torch
                    if torch.cuda.is_available():
                        dev = "cuda (из torch.cuda.is_available)"
                except Exception:
                    pass

            print(f"🎙 VoxCPM2 устройство: {dev}")
        except Exception as e:
            print(f"⚠️ Не удалось определить устройство VoxCPM2: {e}")

    def _vox_sr(self):
        m = self.vox_model
        for attr in ("sample_rate", "target_sample_rate", "sampling_rate", "sr"):
            v = getattr(m, attr, None)
            if isinstance(v, int) and v > 0:
                return v
        return 24000

    def _vox_generate(self, text, ref_path, ref_text, fast=False, actual_rate=1.0):
        m = self.vox_model
        t0 = time.time()

        # один раз выясняем, какие параметры реально работает
        if not hasattr(self, "_vox_step_key"):
            self._vox_step_key = None
            test_text = "тест"
            test_ref, test_rt = ref_path, ref_text
            for cand in ("num_inference_steps", "inference_steps", "diffusion_steps",
                         "num_steps", "steps", "n_steps", "max_steps",
                         "timesteps", "num_timesteps", "max_new_tokens"):
                try:
                    m.generate(text=test_text, prompt_wav_path=test_ref, prompt_text=test_rt,
                               **{cand: 4})
                    self._vox_step_key = cand
                    print(f"🎯 Найден параметр шагов: {cand}")
                    break
                except TypeError:
                    continue
                except Exception as e:
                    # TypeError — не тот аргумент; другие ошибки — попробовали, но что-то упало внутри
                    err = str(e).lower()
                    if "unexpected" in err or "argument" in err or "keyword" in err:
                        continue
                    # если ошибка внутренняя — значит, параметр принят, но значение не подошло
                    self._vox_step_key = cand
                    print(f"🎯 Параметр шагов (предположительно): {cand}")
                    break
            if self._vox_step_key is None:
                print("⚠️ Параметр шагов не найден — быстрый режим будет как обычный")

        # базовые комбинации аргументов
        base_variants = [
            dict(prompt_wav_path=ref_path, prompt_text=ref_text),
            dict(prompt_wav=ref_path, prompt_text=ref_text),
            dict(ref_wav_path=ref_path, ref_text=ref_text),
            dict(reference_wav=ref_path, reference_text=ref_text),
            dict(prompt_wav_path=ref_path),
            dict(),
        ]

        # для быстрого режима: сначала пробуем мало шагов, потом обычные
        extras_list = []
        if fast and self._vox_step_key:
            extras_list += [{self._vox_step_key: 20}, {self._vox_step_key: 30}]
        extras_list.append({})  # обычный режим — всегда в конце

        last = None
        for i, bv in enumerate(base_variants):
            for extra in extras_list:
                try:
                    out = m.generate(text=text, **bv, **extra)
                    tag = f" ⚡ {self._vox_step_key}={list(extra.values())[0]}" if extra else ""
                    print(f"⏱ VoxCPM2: фраза {len(text)} симв. за {time.time() - t0:.1f} сек · "
                          f"ускорение ×{actual_rate:.2f}{tag} (вариант {i + 1})")
                    return out
                except TypeError as e:
                    last = e
                    continue
                except Exception as e:
                    last = e
                    continue
        raise Exception(f"VoxCPM2 generate не сработал: {last}")

    def _vox_synth_chunk(self, ch_clean, ref_wav, ref_text, fast, actual_rate, depth=0):
        """Синтез фразы. Если Vox выдал подозрительно короткое аудио — фраза делится
        пополам и синтезируется по частям (на коротких фразах модель не глотает хвост)."""
        out = self._vox_generate(ch_clean, ref_wav, ref_text, fast=fast, actual_rate=actual_rate)
        arr, sr = self._vox_to_int16(out)
        need = int(sr * max(0.3, len(ch_clean) * 0.035))
        if len(arr) >= need or depth >= 2 or len(ch_clean) < 60:
            if len(arr) < need:
                print(f"⚠️ Фраза {len(ch_clean)} зн. → {len(arr) / sr:.1f} с (мало, но дробим предел)")
            return arr, sr

        mid = len(ch_clean) // 2
        cut = ch_clean.rfind(" ", 0, mid + 40)
        if cut < 30:
            cut = ch_clean.rfind(",", 0, mid + 40)
        if cut < 30:
            cut = mid
        left, right = ch_clean[:cut].strip(), ch_clean[cut:].strip()
        if not left or not right:
            return arr, sr
        if left[-1] not in ".!?…:;":
            left += "."
        print(f"✂️ Фраза {len(ch_clean)} зн. оборвалась ({len(arr) / sr:.1f} с) — делю на "
              f"{len(left)} + {len(right)} зн.")
        a1, sr = self._vox_synth_chunk(left, ref_wav, ref_text, fast, actual_rate, depth + 1)
        a2, _ = self._vox_synth_chunk(right, ref_wav, ref_text, fast, actual_rate, depth + 1)
        gap = np.zeros(int(sr * 0.12), dtype=np.int16)
        return np.concatenate([a1, gap, a2]), sr

    def _vox_to_int16(self, out):
        if isinstance(out, (str, os.PathLike)) and os.path.exists(str(out)):
            with wave.open(str(out)) as w:
                sr = w.getframerate()
                ch = w.getnchannels()
                raw = w.readframes(w.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16)
            if ch > 1:
                arr = arr.reshape(-1, ch).mean(axis=1).astype(np.int16)
            return arr, sr
        if isinstance(out, (bytes, bytearray)):
            with wave.open(io.BytesIO(bytes(out))) as w:
                sr = w.getframerate()
                ch = w.getnchannels()
                raw = w.readframes(w.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16)
            if ch > 1:
                arr = arr.reshape(-1, ch).mean(axis=1).astype(np.int16)
            return arr, sr
        if hasattr(out, "detach"):
            out = out.detach().cpu().numpy()
        if isinstance(out, (list, tuple)):
            out = out[0]
            if hasattr(out, "detach"):
                out = out.detach().cpu().numpy()
        arr = np.asarray(out, dtype=np.float32).reshape(-1)
        if arr.max() <= 1.5:
            arr = np.clip(arr * 32767.0, -32768, 32767)
        return arr.astype(np.int16), self._vox_sr()

    def _resample_int16(self, arr, rate):
        if rate == 1.0 or len(arr) == 0:
            return arr
        n_new = max(1, int(len(arr) / rate))
        x_old = np.linspace(0, 1, len(arr))
        x_new = np.linspace(0, 1, n_new)
        return np.interp(x_new, x_old, arr).astype(np.int16)

    def _stretch_int16(self, arr, rate):
        """Ускорение через resample (тон меняется, но скорость работает)."""
        if abs(rate - 1.0) < 0.01 or len(arr) == 0:
            return arr
        # простой ресемпл: ускорение = меньше сэмплов
        n_new = max(1, int(len(arr) / rate))
        x_old = np.linspace(0, 1, len(arr))
        x_new = np.linspace(0, 1, n_new)
        result = np.interp(x_new, x_old, arr.astype(np.float32))
        print(f"🎚 Ускорение: {len(arr)} сэмплов → {len(result)} (×{rate:.2f})")
        return result.astype(np.int16)

    @staticmethod
    def _join_chunks(segs, sr, gap_ms=70, fade_ms=25):
        """Склеить фразы: короткая пауза + кроссфейд, чтобы стык не щёлкал и тембр не прыгал."""
        segs = [np.asarray(x, dtype=np.int16) for x in segs if len(x)]
        if not segs:
            return np.zeros(0, dtype=np.int16)
        gap = np.zeros(int(sr * gap_ms / 1000), dtype=np.int16)
        fade = max(1, int(sr * fade_ms / 1000))
        out = segs[0]
        for nxt in segs[1:]:
            n = min(fade, len(out) // 3, len(nxt) // 3)
            if n > 4:
                w = np.linspace(0.0, 1.0, n, dtype=np.float32)
                mixed = (out[-n:].astype(np.float32) * (1 - w) +
                         nxt[:n].astype(np.float32) * w).astype(np.int16)
                out = np.concatenate([out[:-n], mixed, gap, nxt[n:]])
            else:
                out = np.concatenate([out, gap, nxt])
        return out

    def _close_stream(self):
        s = self._sd_stream
        if s is not None:
            try:
                s.stop();
                s.close()
            except Exception:
                pass
            self._sd_stream = None

    # ================= PIPER =================

    def load_tts_on_select(self):
        name = self.tts_combo.get()
        if not name:
            return
        if self.current_tts_name == name and self.tts_voice is not None:
            self.update_status(f"✅ Голос '{name}' активен")
            return
        path = self.tts_models.get(name)
        if not path or not os.path.exists(path):
            self.update_status("❌ Файл голоса не найден")
            return
        try:
            self.tts_voice = PiperVoice.load(path)
            self.current_tts_name = name
            self.update_status(f"✅ Голос '{name}' активен")
        except Exception as e:
            self.tts_voice = None
            self.update_status("❌ Ошибка загрузки")
            messagebox.showerror("Ошибка TTS", str(e))

    # ================= НАСТРОЙКИ =================

    def _walk_widgets(self, w):
        for c in w.winfo_children():
            yield c
            yield from self._walk_widgets(c)

    def _apply_language(self):
        """Перерисовывает подписи уже созданных виджетов под выбранный язык."""
        _apply_lang(self)
        try:
            self.btn_vox_install.configure(text="⬇ " + _tr("Установить дополнение Vox"))
        except Exception:
            pass
        for cv, title, height, indent in getattr(self, "_card_title_items", []):
            try:
                self._draw_card_head(cv, title, height, indent)
            except Exception:
                pass
        try:
            self._update_char_count()
        except Exception:
            pass
        if getattr(self, "_placeholder_active", False):
            try:
                self._show_placeholder()
            except Exception:
                pass

    def _set_lang(self, value):
        global UI_LANG
        UI_LANG = "en" if value == "EN" else "ru"
        try:
            self.lang_toggle.set(value)
        except Exception:
            pass
        self._apply_language()
        self.save_settings()

    def save_settings(self):
        try:
            data = {
                "engine": self.current_engine,
                "llm_model": self._actual_llm(),
                "tts_voice": self.tts_combo.get(),
                "preset": self.preset_menu.get(),
                "custom_presets": self.custom_presets,
                "instruction": self.instruction_entry.get("1.0", "end-1c").strip(),
                "auto_play": bool(self.auto_play_var.get()),
                "custom_voices": self.custom_voices,
                "ctx_choices": self.ctx_choices,
                "speech_rate": self.speech_rate,
                "vox_fast": bool(self.vox_fast_var.get()),
                "llm_gpu": bool(self.llm_gpu_var.get()),
                "external_llms": self.external_llms,
                "geometry": self.geometry(),
                "ui_lang": UI_LANG,
                "donate_done": bool(getattr(self, "donate_done", False)),
                "model_offer_muted": bool(getattr(self, "model_offer_muted", False)),
                "voices_seeded": bool(getattr(self, "voices_seeded", False)),
                "vox_offer_done": bool(getattr(self, "vox_offer_done", False)),
            }
            tmp = self.SETTINGS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.SETTINGS_FILE)  # файл не бьётся при сбое
        except Exception as e:
            print(f"⚠️ Настройки: {e}")

    def _migrate_voice(self, info):
        """Пути в settings.json могли остаться от старой машины — чиним по имени файла."""
        if not isinstance(info, dict):
            return info
        path = info.get("path") or ""
        if path and not os.path.exists(path):
            candidate = os.path.join(self.BASE_DIR, os.path.basename(path))
            if os.path.exists(candidate):
                info["path"] = candidate
        return info

    def load_settings(self):
        try:
            if not os.path.exists(self.SETTINGS_FILE):
                self._apply_engine("Piper")        # первый запуск — Piper по умолчанию
                self.preset_menu.set("Кратко (50%)")
                self.apply_preset("Кратко (50%)")
                self.update_status("✅ Готово. Вставьте ссылку, текст или файл.")
                return
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._apply_engine("Vox")
            self.preset_menu.set("Кратко (50%)")
            self.apply_preset("Кратко (50%)")
            return

        global UI_LANG
        lang = str(data.get("ui_lang", "ru")).lower()
        if lang in ("ru", "en"):
            UI_LANG = lang
            try:
                self.lang_toggle.set("EN" if lang == "en" else "RU")
            except Exception:
                pass

        geo = data.get("geometry")
        if isinstance(geo, str) and re.fullmatch(r"\d+x\d+([+-]-?\d+){2}", geo):
            try:
                self.geometry(geo)
            except Exception:
                pass

        if data.get("custom_voice_path") and data.get("custom_voice_text"):
            self.custom_voices["1"] = {"path": data["custom_voice_path"], "text": data["custom_voice_text"]}
        cv = data.get("custom_voices")
        if isinstance(cv, dict):
            for slot, info in cv.items():
                info = self._migrate_voice(dict(info) if isinstance(info, dict) else info)
                if not isinstance(info, dict):
                    info = {}
                if not info.get("name"):
                    info["name"] = f"Свой {slot}"  # старый формат — имя по номеру
                self.custom_voices[str(slot)] = info

        cc = data.get("ctx_choices")
        if isinstance(cc, dict):
            self.ctx_choices = cc

        self.auto_play_var.set(bool(data.get("auto_play", False)))
        self.model_offer_muted = bool(data.get("model_offer_muted", False))
        self.voices_seeded = bool(data.get("voices_seeded", False))
        self.vox_offer_done = bool(data.get("vox_offer_done", False))

        rate = data.get("speech_rate", 1.0)
        try:
            rate = round(min(1.5, max(0.5, float(rate))), 1)
        except Exception:
            rate = 1.0
        self.speech_rate = rate
        self.rate_slider.set(rate)
        self.rate_label.configure(text=f"×{rate:.1f}")
        self.vox_fast_var.set(bool(data.get("vox_fast", False)))
        self.llm_gpu_var.set(bool(data.get("llm_gpu", False)))
        self._update_gpu_labels()

        engine = data.get("engine", "Piper")   # по умолчанию — Piper: работает без дополнений
        if engine not in ("Piper", "Vox"):
            engine = "Piper"
        if engine == "Vox" and not self._vox_installed():
            engine = "Piper"                   # дополнение Vox не поставлено — молча на Piper
        self._apply_engine(engine)

        voice = data.get("tts_voice")
        allowed = list(self.tts_combo.cget("values"))
        if voice and voice in allowed:
            self.tts_combo.set(voice)
            self.current_tts_name = voice

        ex = data.get("external_llms")
        if isinstance(ex, dict):
            for nm, pth in ex.items():
                if isinstance(pth, str) and os.path.exists(pth):
                    self.external_llms[str(nm)] = os.path.abspath(pth)
                    self.llm_models.setdefault(str(nm), os.path.abspath(pth))
            self._rebuild_llm_menu()

        llm = data.get("llm_model")
        if llm and llm in self.llm_models:
            for disp, act in self.llm_display.items():
                if act == llm:
                    self.llm_combo.set(disp)
                    break

        cp = data.get("custom_presets")
        if isinstance(cp, dict):
            for name, info in cp.items():
                if not isinstance(info, dict) or not (info.get("prompt") or "").strip():
                    continue
                try:
                    ratio = float(info.get("ratio", 0.5))
                except Exception:
                    ratio = 0.5
                self.custom_presets[str(name)] = {
                    "ratio": max(0.05, min(1.0, ratio)),
                    "prompt": info.get("prompt") or "",
                }
        self._refresh_preset_menu()

        preset = data.get("preset")
        if preset in self.preset_values():
            self.preset_menu.set(preset)
            self._last_preset = preset
        else:
            preset = "Кратко (50%)"
            self.preset_menu.set(preset)
            self._last_preset = preset

        instruction = data.get("instruction")
        if instruction and "2–3 предложения, не более 10% объёма" in instruction:
            # старый промпт «Только суть»: 2–3 предложения спорили с лимитом 10% на коротких текстах
            instruction = instruction.replace("2–3 предложения",
                                              "одно-два коротких предложения")
        if instruction and any(marker in instruction for marker in self.LEGACY_PROMPTS):
            # промпт прежней версии — подставляем актуальный для выбранного пресета
            instruction = None

        self.instruction_entry.delete("1.0", "end")
        if instruction:
            self.instruction_entry.insert("1.0", instruction)
        else:
            self.apply_preset(preset)

        self.update_status(f"✅ Настройки восстановлены: {engine}, «{self.tts_combo.get()}».")

    def _apply_engine(self, value):
        self.current_engine = value
        if value == "Piper":
            self.engine_menu.set("Piper (CPU)")
        elif value == "Vox":
            self.engine_menu.set("Vox (GPU)")
        hint = getattr(self, "engine_hint", None)
        if hint is not None:
            if value == "Vox":
                hint.configure(text=_tr("⚠ Vox требует видеокарту с 8 ГБ видеопамяти"),
                               text_color=COLOR_TEXT_MAIN)
            else:
                hint.configure(text=_tr("Piper: процессор, видеокарта не нужна"),
                               text_color=COLOR_TEXT_SEC)
        if value == "Vox":
            self._show_custom_voice(True)
            self._ensure_empty_slot()
            self.tts_combo.configure(values=self.voice_values())
            names = self.voice_values()
            cur = self.current_tts_name if self.current_tts_name in names else ""
            if not cur:
                vid, info = self._first_empty_voice()
                filled = [i.get("name") for _, i in self._voice_items()
                          if isinstance(i, dict) and i.get("path") and os.path.exists(i.get("path") or "")]
                cur = filled[-1] if filled else (info.get("name") if info else (names[0] if names else ""))
            if cur:
                self.tts_combo.set(cur)
                self.current_tts_name = cur
        elif value == "Piper":
            self._show_custom_voice(False)
            self.tts_combo.configure(values=sorted(self.tts_models.keys()))
            names = sorted(self.tts_models.keys())
            default = next((n for n in names if "irina" in n.lower()), names[0] if names else "")
            self.tts_combo.set(default)
            self.current_tts_name = default or None
            if default:
                self.load_tts_on_select()

    def _actual_llm(self):
        return self.llm_display.get(self.llm_combo.get(), self.llm_combo.get())

    # ================= ОТМЕНА =================

    def cancel_processes(self):
        self.cancel_event.set()
        self.is_processing = False
        self.after(0, self.progress_bar.stop)
        self.after(0, lambda: self.btn_process.configure(state="normal", text=_tr("Запустить анализ")))
        self.after(0, lambda: self.update_status("⏹ Остановлено"))
        self.after(0, lambda: self.lbl_audio_status.configure(text=_tr("Отменено"), text_color=COLOR_RED))

    # ================= ОБРАБОТЧИКИ =================

    def on_engine_change(self, value):
        eng = "Vox" if value.startswith("Vox") else "Piper"
        if eng == "Vox" and not self._vox_installed():
            # дополнение Vox не стоит — вместо ошибки предлагаем поставить
            self.engine_menu.set("Piper")
            self._apply_engine("Piper")
            self.save_settings()
            self._vox_wanted = True
            if messagebox.askyesno(
                    _tr("Движок Vox"),
                    _tr("Для Vox нужно дополнение (переносимый Python + torch + VoxCPM, "
                        "≈1,5–2,5 ГБ).\n\nСкачать и установить сейчас?")):
                self._install_vox()
            return
        self._apply_engine(eng)
        if eng == "Vox":
            self.update_status("Движок: VoxCPM2 (GPU).")
            if self.vox_model is None:
                threading.Thread(target=self.load_vox_threaded, daemon=True).start()
        else:
            self.update_status(f"Движок: Piper (CPU). Голос: «{self.tts_combo.get()}»")
        self.save_settings()

    # ================= ВИДЕОКАРТА (CUDA) =================

    def _gpu_binary(self):
        for name in ("llama-server.exe", "llama-server"):
            path = os.path.join(self.BASE_DIR, "tools", "llama-cuda", name)
            if os.path.exists(path):
                return path
        return None

    def _port_free(self, port):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex(("127.0.0.1", port)) != 0

    def _stop_gpu_server(self):
        proc = self._gpu_server
        self._gpu_server = None
        self._gpu_server_port = None
        self._gpu_server_model = None
        self._gpu_server_ctx = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _ensure_gpu_server(self, model_path, n_ctx):
        """Поднимает llama-server на CUDA и ждёт, пока модель встанет на видеокарту."""
        exe = self._gpu_binary()
        if not exe:
            raise Exception("CUDA-сборка llama.cpp не найдена:\n"
                            + os.path.join(self.BASE_DIR, "tools", "llama-cuda"))

        if (self._gpu_server is not None and self._gpu_server.poll() is None
                and self._gpu_server_model == model_path and self._gpu_server_ctx == n_ctx):
            return self._gpu_server_port

        self._stop_gpu_server()

        port = next((p for p in (8123, 8124, 8125, 8126) if self._port_free(p)), None)
        if port is None:
            raise Exception("Нет свободного порта для GPU-сервера (8123–8126 заняты)")

        log_path = os.path.join(self.BASE_DIR, "tools", "llama-cuda", "server.log")
        log = open(log_path, "w", encoding="utf-8", errors="ignore")

        cmd = [exe, "-m", model_path, "-ngl", "999", "-c", str(int(n_ctx)),
               "--host", "127.0.0.1", "--port", str(port), "--jinja", "--no-warmup"]
        print("🚀 GPU-сервер:", " ".join(cmd))
        try:
            proc = subprocess.Popen(cmd, cwd=os.path.dirname(exe), stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=0x08000000)  # CREATE_NO_WINDOW
        except Exception as e:
            log.close()
            raise Exception(f"Не удалось запустить GPU-сервер: {e}")

        import urllib.request
        deadline = time.time() + 180
        while time.time() < deadline:
            if proc.poll() is not None:
                log.close()
                tail = ""
                try:
                    with open(log_path, encoding="utf-8", errors="ignore") as f:
                        tail = "".join(f.readlines()[-12:])
                except Exception:
                    pass
                raise Exception("GPU-сервер завершился при загрузке модели.\n" + tail.strip()[-600:])
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(1.0)
        else:
            log.close()
            raise Exception("GPU-сервер не ответил за 180 секунд")

        self._gpu_server = proc
        self._gpu_server_port = port
        self._gpu_server_model = model_path
        self._gpu_server_ctx = n_ctx
        self.after(0, lambda: self.update_status(f"✅ Модель на видеокарте (порт {port})"))
        return port

    def _update_gpu_labels(self):
        """Активный режим — тёмным, неактивный — серым."""
        on = bool(self.llm_gpu_var.get())
        if hasattr(self, "lbl_mode_cpu") and hasattr(self, "lbl_mode_gpu"):
            self.lbl_mode_cpu.configure(text_color=COLOR_TEXT_SEC if on else COLOR_TEXT_MAIN)
            self.lbl_mode_gpu.configure(text_color=COLOR_TEXT_MAIN if on else COLOR_TEXT_SEC)

    def _on_gpu_toggle(self):
        self.save_settings()
        self._update_gpu_labels()
        if not self.llm_gpu_var.get():
            self._stop_gpu_server()
            self.update_status("Режим: процессор (CUDA выключена)")
            return
        if not self._gpu_binary():
            messagebox.showwarning("Видеокарта",
                                   "Не найдена CUDA-сборка llama.cpp:\n"
                                   + os.path.join(self.BASE_DIR, "tools", "llama-cuda"))
            self.llm_gpu_var.set(False)
            self._update_gpu_labels()
            self.save_settings()
            return
        self.update_status("Режим: видеокарта (CUDA)")

    def load_vox_threaded(self):
        self._stop_gpu_server()  # освобождаем VRAM: модель анализа не должна мешать Vox
        self.after(0, lambda: self.update_status("⏳ Загрузка VoxCPM2 (веса ~5 ГБ)..."))
        if self.load_vox(show_errors=True):
            self.after(0, lambda: self.update_status("✅ VoxCPM2 готова (GPU)"))
        else:
            self.after(0, lambda: self.update_status("❌ VoxCPM2 недоступна"))

    def on_tts_change(self, value):
        if self.current_engine == "Piper":
            self.load_tts_on_select()
        elif self.current_engine == "Vox":
            vid, info = self._find_voice(value)
            if info is None:
                return
            path = info.get("path") or ""
            if not path or not os.path.exists(path):
                self.add_custom_voice(initial_slot=value)  # пустой слот — сразу на запись
                return
            self.current_tts_name = value
            self.update_status(f"✅ Голос «{value}» активен")
        self.save_settings()

    def add_custom_voice(self, initial_slot=None):
        """Записать/перезаписать образец: текущий слот, пустой слот или новый."""
        target = initial_slot or self.tts_combo.get()
        vid, info = self._find_voice(target)
        if info is None:
            vid, info = self._first_empty_voice()
        if info is None:
            vid = self._next_voice_id()
            info = {"name": f"Свой {vid}", "path": "", "text": ""}
            self.custom_voices[vid] = info
        VoiceRecorderDialog(self, self._apply_custom_voice, vid, info.get("name"), self.custom_voices)

    def _apply_custom_voice(self, path, text, slot_id, name):
        slot_id = str(slot_id)
        name = (name or "").strip() or f"Свой {slot_id}"
        # имена не должны совпадать — иначе в списке не выбрать нужный голос
        base, n = name, 2
        while any(isinstance(i, dict) and i.get("name") == name and k != slot_id
                  for k, i in self.custom_voices.items()):
            name = f"{base} ({n})"
            n += 1
        # пример-заглушку храним в исходном виде, каким бы языком интерфейса он ни был показан
        _sample = VoiceRecorderDialog.DEFAULT_TEXT
        if text.strip() in (_tr(_sample), _sample):
            text = _sample
        self.custom_voices[slot_id] = {"name": name, "path": path, "text": text}
        self._ensure_empty_slot()  # после записи появляется следующий пустой слот
        if self.current_engine == "Vox":
            self.tts_combo.configure(values=self.voice_values())
            self.tts_combo.set(name)
            self.current_tts_name = name
        self.update_status(f"✅ Голос «{name}» сохранён")
        self.save_settings()

    def on_llm_change(self, value):
        self.unload_llm()  # освобождаем память под новую модель
        self.update_status("Выбрана модель. Загрузится при анализе.")
        self._probe_model(value)
        self.save_settings()

    def scan_models(self):
        self.update_status("Сканирование моделей…")
        base = self.BASE_DIR
        tts_files = glob.glob(os.path.join(base, "*.onnx")) + glob.glob(os.path.join(base, "models", "*.onnx"))
        self.tts_models = {os.path.basename(f).replace(".onnx", ""): f for f in tts_files}

        llm_files = glob.glob(os.path.join(base, "*.gguf")) + glob.glob(os.path.join(base, "models_llm", "*.gguf"))
        self.llm_models = {os.path.basename(f): f for f in llm_files}
        for nm, pth in self.external_llms.items():
            if os.path.exists(pth):
                self.llm_models[nm] = pth

        self._rebuild_llm_menu()

    def _rebuild_llm_menu(self, keep=None):
        """Меню моделей: найденные в models_llm/ + добавленные пользователем вручную."""
        self.llm_display = {}
        seen = set()
        for actual in sorted(self.llm_models.keys()):
            disp = actual if len(actual) <= 32 else actual[:29] + "..."
            while disp in seen:
                disp += "_"
            seen.add(disp)
            self.llm_display[disp] = actual
        if not self.llm_display:
            # пустой список: без подсказки CTkOptionMenu показывает «CTkOptionMenu»
            self.llm_combo.configure(values=[], state="disabled")
            self.llm_combo.set(_tr("Нет модели — нажмите ⬇"))
            return
        self.llm_combo.configure(values=list(self.llm_display.keys()), state="normal")
        if keep and keep in self.llm_display:
            self.llm_combo.set(keep)
        elif self.llm_display:
            self.llm_combo.set(list(self.llm_display.keys())[0])

    def pick_llm_file(self):
        """Добавить свою GGUF-модель для анализа текста (из любой папки)."""
        start = os.path.join(self.BASE_DIR, "models_llm")
        path = filedialog.askopenfilename(
            title="Выберите модель .gguf для анализа текста",
            initialdir=start if os.path.isdir(start) else self.BASE_DIR,
            filetypes=[("Модель GGUF", "*.gguf"), ("Все файлы", "*.*")])
        if not path:
            return
        path = os.path.abspath(path)
        if not path.lower().endswith(".gguf"):
            messagebox.showwarning("Внимание", "Нужен файл модели в формате .gguf")
            return
        name = os.path.basename(path)
        known = self.llm_models.get(name)
        if known and os.path.abspath(known) != path:
            self.unload_llm()  # имя совпало, но файл другой — старую выгружаем
        self.llm_models[name] = path
        proj = os.path.normcase(os.path.abspath(self.BASE_DIR))
        if not os.path.normcase(path).startswith(proj + os.sep):
            self.external_llms[name] = path
        self._rebuild_llm_menu()
        disp = next((d for d, a in self.llm_display.items() if a == name), None)
        if disp:
            self.llm_combo.set(disp)
            self.on_llm_change(disp)
        self.update_status(f"Модель для анализа: {name} — загрузится при запуске анализа.")

    def _card_head(self, card, title, height=28, indent=20):
        """Шапка карточки: заливка-глянец во всю ширину, заголовок — с отступом слева.

        Заливка рисуется на собственном холсте, а не под надписью: подпись
        непрозрачна и съедала заливку, отчего та обрывалась, не доходя до границ.
        """
        cv = tk.Canvas(card, height=height, highlightthickness=0, bd=0,
                       bg=_mode_color(COLOR_CARD))
        cv.pack(fill="x")
        if getattr(self, "_card_title_items", None) is None:
            self._card_title_items = []
        self._card_title_items.append((cv, title, height, indent))
        cv.bind("<Configure>", lambda e: self._draw_card_head(cv, title, height, indent))
        self._draw_card_head(cv, title, height, indent)
        return cv

    def _draw_card_head(self, cv, title, height, indent):
        """Градиент сверху вниз + подпись; перерисовывается при смене языка и размера."""
        try:
            base = _mode_color(COLOR_CARD)
            top = "#4a4a4a" if ctk.get_appearance_mode() == "Dark" else "#ffffff"
            cv.delete("all")
            w = cv.winfo_width() or 400
            for i in range(height):
                t = (i / max(1, height - 1)) ** 1.5
                cv.create_line(0, i, w, i, fill=_blend(top, base, t))
            cv.create_line(0, 0, w, 0, fill=top, width=2)
            cv.create_text(indent, height // 2 + 1, text=_tr(title), anchor="w",
                           fill=_mode_color(COLOR_TEXT_SEC),
                           font=(FONT_FAMILY, 10, "bold"))
        except Exception as e:
            print(f"⚠️ шапка карточки: {e}")

    def _add_gloss(self, frame, height=30):
        """Мягкий вертикальный блик сверху панели — «глянец» в духе MusicBee.

        Вызывать сразу после создания фрейма, до наполнения контентом:
        блик ложится вниз по стопке и не перекрывает элементы.
        """
        try:
            base = frame.cget("fg_color")
            if isinstance(base, (tuple, list)):
                base = base[1] if ctk.get_appearance_mode() == "Dark" else base[0]
            if not isinstance(base, str) or not base.startswith("#") or len(base) != 7:
                return
            dark = ctk.get_appearance_mode() == "Dark"
            top = "#4a4a4a" if dark else "#ffffff"
            canvas = tk.Canvas(frame, height=height, highlightthickness=0, bd=0)
            canvas.place(x=1, y=1, relwidth=1, width=-2)
            for i in range(height):
                t = (i / max(1, height - 1)) ** 1.5
                canvas.create_line(0, i, 4000, i, fill=_blend(top, base, t))
            # плотная кромка блика
            canvas.create_line(0, 0, 4000, 0, fill=top, width=2)
        except Exception as e:
            print(f"⚠️ Глянец: {e}")

    # ---------------- свои уровни сжатия ----------------

    def preset_values(self):
        """Базовые уровни + свои + пункт создания нового."""
        values = list(self.PRESET_VALUES)
        for name in self.custom_presets:
            if name not in values:
                values.append(name)
        values.append("Новый…")
        return values

    def _refresh_preset_menu(self, select=None):
        if not hasattr(self, "preset_menu"):
            return
        values = self.preset_values()
        self.preset_menu.configure(values=values)
        target = select if select in values else (self._last_preset if self._last_preset in values
                                                  else self.PRESET_VALUES[2])
        self.preset_menu.set(target)
        self._last_preset = target

    def _preset_ratio(self, choice):
        if choice in self.custom_presets:
            try:
                return float(self.custom_presets[choice].get("ratio", 1.0))
            except Exception:
                return 1.0
        return self.PRESET_RATIOS.get(choice)

    def _next_preset_name(self):
        i = 1
        while f"Новый {i}" in self.custom_presets or f"Новый {i}" in self.PRESET_VALUES:
            i += 1
        return f"Новый {i}"

    def on_preset_select(self, choice):
        """Выбор в списке «Сжатие»."""
        if choice == "Новый…":
            self.preset_menu.set(self._last_preset)
            self.add_custom_preset()
            return
        self._last_preset = choice
        if choice in self.custom_presets:
            self.instruction_entry.delete("1.0", "end")
            self.instruction_entry.insert("1.0", self.custom_presets[choice].get("prompt", ""))
            self.save_settings()
            return
        self.apply_preset(choice)

    def add_custom_preset(self):
        """Новый свой уровень: имя, доля и промпт (текущий текст поля — как основа)."""
        prompt = self.instruction_entry.get("1.0", "end-1c").strip()
        ratio = self._preset_ratio(self._last_preset) or 0.5
        PresetDialog(self, name=self._next_preset_name(), ratio=ratio, prompt=prompt,
                     on_save=self._save_custom_preset)

    def edit_selected_preset(self):
        """Кнопка «＋»: изменить свой уровень или создать новый."""
        cur = self.preset_menu.get()
        if cur in self.custom_presets:
            info = self.custom_presets[cur]
            prompt = self.instruction_entry.get("1.0", "end-1c").strip() or info.get("prompt", "")
            PresetDialog(self, name=cur, ratio=info.get("ratio", 0.5), prompt=prompt,
                         on_save=lambda n, r, p: self._save_custom_preset(n, r, p, old_name=cur),
                         on_delete=lambda: self._delete_custom_preset(cur))
        else:
            self.add_custom_preset()

    def _save_custom_preset(self, name, ratio, prompt, old_name=None):
        name = (name or "").strip()
        if not name or name == "Новый…":
            return
        if name in self.PRESET_VALUES:
            messagebox.showwarning("Внимание",
                                   f"«{name}» — встроенный уровень. Выберите другое название.")
            return
        if old_name and old_name != name:
            self.custom_presets.pop(old_name, None)
        self.custom_presets[name] = {"ratio": float(ratio), "prompt": prompt}
        self._refresh_preset_menu(select=name)
        self.instruction_entry.delete("1.0", "end")
        self.instruction_entry.insert("1.0", prompt)
        self.update_status(f"✅ Уровень сжатия «{name}» сохранён")
        self.save_settings()

    def _delete_custom_preset(self, name):
        if self.custom_presets.pop(name, None) is None:
            return
        self._refresh_preset_menu(select=self.PRESET_VALUES[2])
        self.apply_preset(self.PRESET_VALUES[2])
        self.update_status(f"🗑 Уровень «{name}» удалён")
        self.save_settings()

    def apply_preset(self, choice):
        """Промпты уровней сжатия: что именно сохранить и что выбросить.

        Стилевые требования (речь без списков, цифры словами, без англицизмов)
        живут в system-промпте, поэтому здесь — только задача по содержанию.
        """
        prompts = {
            "Только суть (10%)":
                "Оставь только главную мысль текста — одно-два коротких предложения, не более 10% объёма. "
                "Отбрось примеры, второстепенные детали, повторы и оговорки. "
                "Если без имён или чисел мысль станет непонятной — сохрани их.",
            "Очень кратко (30%)":
                "Сократи текст до ~30% объёма: ключевые факты, главные аргументы и вывод. "
                "Убери примеры, пояснения, вступления и повторы, но сохрани все значимые "
                "числа, даты, имена и названия.",
            "Кратко (50%)":
                "Сократи текст примерно вдвое (~50% объёма): главные факты, аргументы и выводы "
                "вместе с ключевыми деталями, которые на них влияют. Порядок изложения — как "
                "в исходном тексте, без потери логики.",
            "Подробно (80%)":
                "Сожми текст до ~80% объёма: сохрани структуру, порядок изложения и почти все "
                "детали. Сжимай только формулировки и убирай повторы — ничего существенного "
                "не выбрасывай.",
            "Речь для озвучки (100%)":
                "Перепиши текст целиком для озвучки, сохранив весь смысл, структуру и порядок "
                "изложения. Убери только визуальный мусор: ссылки, подписи, колонтитулы, "
                "номера страниц и служебные пометки.",
            "Перевод на английский (100%)":
                "Переведи текст на английский язык. Сохрани весь смысл, структуру и порядок "
                "изложения, ничего не сокращай, не добавляй и не комментируй. Термины, имена "
                "и названия передавай так, как это принято в англоязычной литературе по теме. "
                "Верни только перевод, без пояснений и вступлений.",
        }
        prompt = prompts.get(choice, "")
        if UI_LANG == "en":
            prompt = self.PRESET_PROMPTS_EN.get(choice, prompt)
        self.instruction_entry.delete("1.0", "end")
        self.instruction_entry.insert("1.0", prompt)
        self.save_settings()

    def _read_donate_flag(self):
        """Флаг «к оплате уже переходили» — читается до сборки интерфейса."""
        try:
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                return bool(json.load(f).get("donate_done"))
        except Exception:
            return False

    def _open_donate_page(self, event=None):
        """Страница донатов в браузере (клик по названию или кнопке)."""
        try:
            import webbrowser
            webbrowser.open(DONATE_URL)
            self.update_status("❤️ Открыта страница поддержки")
        except Exception as e:
            messagebox.showerror("Поддержка", str(e), parent=self)

    def _open_donate_dialog(self):
        DonateDialog(self, self._donate_paid)

    def _donate_paid(self):
        """После «Оплатить» кнопка благодарности больше не показывается."""
        self.donate_done = True
        if self.donate_btn is not None:
            try:
                self.donate_btn.destroy()
            except Exception:
                pass
            self.donate_btn = None
        self.save_settings()
        self._open_donate_page()

    def update_status(self, text):
        text = _tr(str(text))
        if len(text) > 110:
            text = text[:107] + "…"
        try:
            self.status_label_main.configure(text=text, text_color=COLOR_TEXT_SEC)
        except Exception:
            pass

    def unload_llm(self):
        if self.llm_model is not None:
            try:
                del self.llm_model
            except Exception:
                pass
            self.llm_model = None
            self.llm_model_path = None
            self.llm_model_ctx = None
            gc.collect()

    # ================= ЛОГИКА =================

    def fetch_and_clean_text(self, url):
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return re.sub(r'\s+', ' ', soup.get_text()).strip()

    # ================= СЕРВЕР МОДЕЛИ (llama.cpp CUDA, OpenAI-совместимый API) =================

    def summarize_via_server(self, system_rules, user_content, url):
        headers = {"Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": system_rules},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.35,
            "stream": True
        }

        full_text = ""
        tokens_generated = 0
        t_start = time.time()

        try:
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            for line in response.iter_lines():
                if self.cancel_event.is_set():
                    break
                if line:
                    line_str = line.decode('utf-8')

                    # Более надежное удаление префикса 'data:' (с пробелом или без)
                    if line_str.startswith('data:'):
                        line_str = line_str[5:].strip()

                    if line_str == '[DONE]' or not line_str:
                        continue

                    try:
                        chunk = json.loads(line_str)
                        if chunk.get("choices"):
                            piece = chunk["choices"][0].get("delta", {}).get("content", "")
                            if piece:
                                full_text += piece
                                tokens_generated += 1
                                pct = 15 + min(80, tokens_generated // 6)
                                self.after(0, lambda p=pct: self.set_progress(p, "Анализ (видеокарта)"))
                    except json.JSONDecodeError:
                        print(f"⚠️ Ошибка парсинга строки сервера: {line_str}")
                        continue

        except requests.exceptions.ConnectionError:
            raise Exception("Не удалось подключиться к серверу модели (CUDA). Проверьте, что он запущен.")
        except Exception as e:
            raise Exception(f"Ошибка сервера модели: {e}")

        elapsed = time.time() - t_start
        self._gen_stats = {"tokens": tokens_generated, "elapsed": elapsed,
                           "tps": tokens_generated / elapsed if elapsed > 0 else 0}

        if not full_text:
            print("⚠️ Сервер модели вернул пустой ответ.")

        return full_text.strip()

    def summarize_text(self, raw_text, instruction, server_url=None):
        if not self.llm_model and not server_url:
            raise Exception("Модель ИИ не загружена.")
        system_rules = ("Ты профессиональный редактор, готовящий текст для озвучки диктором. "
                        "Отвечай ТОЛЬКО готовым текстом выжимки на русском языке, без вступлений и пояснений. "
                        "Все цифры, даты и проценты пиши словами; английские слова заменяй русскими аналогами; "
                        "пиши связной речью, без списков, маркеров, ссылок и скобок. "
                        "Используй только факты из исходного текста — ничего не додумывай и не добавляй. "
                        "Если задан лимит объёма — соблюдай его строго.")
        user_content = f"ИНСТРУКЦИЯ: {instruction}\nТЕКСТ: {raw_text}"

        # --- Модель на видеокарте: локальный CUDA-сервер llama.cpp ---
        if server_url:
            print(f"📡 Запрос к GPU-серверу: {server_url}")
            server_text = self.summarize_via_server(system_rules, user_content, server_url)
            return self.clean_summary(server_text)

        full_text = ""
        tokens_generated = 0
        t_start = time.time()

        def feed(piece):
            nonlocal full_text, tokens_generated
            if piece:
                full_text += piece
                tokens_generated += 1
                pct = 15 + min(80, tokens_generated // 6)
                self.after(0, lambda p=pct: self.set_progress(p, "Анализ"))

        stop_tokens = ["<|eot_id|>", "<|im_end|>", "</s>"]

        try:
            stream = self.llm_model.create_chat_completion(
                messages=[{"role": "system", "content": system_rules},
                          {"role": "user", "content": user_content}],
                max_tokens=4096,
                stop=stop_tokens,
                temperature=0.35,
                stream=True)
            for chunk in stream:
                if self.cancel_event.is_set():
                    break
                try:
                    piece = (chunk["choices"][0].get("delta", {}) or {}).get("content") \
                            or chunk["choices"][0].get("text", "")
                except Exception:
                    piece = ""
                feed(piece)
        except Exception as e:
            print(f"⚠️ Chat-шаблон недоступен ({e}) — запасной прямой промпт")
            full_text, tokens_generated = "", 0
            prompt = (f"<|start_header_id|>system<|end_header_id|>\n{system_rules}\n<|eot_id|>"
                      f"<|start_header_id|>user<|end_header_id|>\n{user_content}\n<|eot_id|>"
                      f"<|start_header_id|>assistant<|end_header_id|>\n")
            for chunk in self.llm_model(prompt, max_tokens=4096, stop=["<|eot_id|>"],
                                        echo=False, stream=True):
                if self.cancel_event.is_set():
                    break
                feed(chunk['choices'][0].get('text', ''))

        elapsed = time.time() - t_start
        if tokens_generated == 0 and full_text:
            tokens_generated = max(1, int(len(full_text) / 1.5))
        self._gen_stats = {"tokens": tokens_generated, "elapsed": elapsed,
                           "tps": tokens_generated / elapsed if elapsed > 0 else 0}
        return self.clean_summary(full_text.strip())

    def _fit_to_limit(self, summary, target, server_url=None, max_passes=3):
        """Если модель не уложилась в лимит — дожимаем повторным проходом."""
        for attempt in range(max_passes):
            if len(summary) <= target * 1.15:
                break
            need = int(target * 0.9)
            prev = dict(getattr(self, "_gen_stats", {}) or {})
            print(f"🔁 Добивка объёма ({attempt + 1}): {len(summary)} → цель {need} знаков")
            try:
                shorter = self.summarize_text(
                    summary,
                    f"Это жёсткое требование: весь ответ не длиннее {need} знаков "
                    f"(сейчас {len(summary)} знаков). Отбрось детали и примеры, оставь только "
                    f"главную мысль и ключевые факты. Верни только готовый текст, без пояснений "
                    f"и вступлений.",
                    server_url=server_url)
            except Exception as e:
                print(f"⚠️ Добивка не удалась: {e}")
                break
            if not shorter or len(shorter) >= len(summary):
                break
            summary = shorter
            # суммируем токены и время обоих проходов
            cur = dict(getattr(self, "_gen_stats", {}) or {})
            tokens = prev.get("tokens", 0) + cur.get("tokens", 0)
            elapsed = prev.get("elapsed", 0) + cur.get("elapsed", 0)
            self._gen_stats = {"tokens": tokens, "elapsed": elapsed,
                               "tps": tokens / elapsed if elapsed else 0}
        return summary

    def clean_summary(self, text):
        junk_starts = ["Вот сокращенный вариант", "Вот краткое содержание", "Вот выжимка", "Вам нужно", "Конечно",
                       "Хорошо"]
        lines = text.split("\n")
        while lines:
            first = lines[0].strip()
            if not first:
                lines.pop(0)
                continue
            if any(first.startswith(j) for j in junk_starts) or first.endswith(":"):
                lines.pop(0)
                continue
            break
        return "\n".join(lines).strip()

    def split_text_chunks(self, text, limit=1450):
        """Режем текст на фразы. Никогда не рвём слово: граница — точка, запятая, пробел."""
        text = (text or "").strip()
        if not text:
            return []
        if len(text) <= limit:
            return [text]

        def cut_point(s, lim):
            """Лучшая позиция разреза в пределах lim: конец предложения → запятая → пробел."""
            window = s[:lim]
            for pat in (r'(?<=[.!?…])\s', r'(?<=[,;:])\s', r'(?<=[—–-])\s', r'\s'):
                best = 0
                for m in re.finditer(pat, window):
                    best = m.start() + 1          # режем после знака/пробела
                if best > lim * 0.35:
                    return best
            return -1

        chunks, cur = [], ""
        for piece in re.split(r'(?<=[.!?…])\s+', text):
            piece = piece.strip()
            while piece:
                room = limit - (len(cur) + 1 if cur else 0)
                if len(piece) <= room:
                    cur = (cur + " " + piece).strip() if cur else piece
                    piece = ""
                    break
                if cur:
                    chunks.append(cur)
                    cur = ""
                    continue
                cut = cut_point(piece, limit)
                if cut <= 0:                      # нет ни пробела, ни знака — режем по лимиту
                    cut = limit
                chunks.append(piece[:cut].strip())
                piece = piece[cut:].strip()
            if cur and len(cur) >= limit * 0.6:
                chunks.append(cur)
                cur = ""
        if cur:
            chunks.append(cur)
        return [c for c in chunks if c.strip()]

    def start_full_process(self):
        if self.is_processing:
            return

        url = self.url_entry.get().strip()
        box_text = "" if self._placeholder_active else self.result_box.get("1.0", "end-1c").strip()
        source_text = "" if self._result_is_generated else box_text

        if not url and not source_text:
            messagebox.showwarning("Нечего анализировать",
                                   "Вставьте ссылку, текст или файл — либо наберите текст в поле справа.")
            return

        if source_text:
            self._last_source = source_text

        self._launch_analysis(url, source_text)

    def _launch_analysis(self, url, source_text):
        if self.is_processing:
            return

        llm_name = self.llm_combo.get()
        if not llm_name:
            messagebox.showwarning("Внимание", "Выберите модель ИИ в карточке «МОДЕЛЬ ИИ»")
            return

        if self.current_engine == "Vox":
            speaker = self.tts_combo.get()
            _, info = self._find_voice(speaker)
            if not speaker or info is None or not (info.get("path") and os.path.exists(info.get("path") or "")):
                messagebox.showwarning("Внимание", "Запишите голос: «🎙 Образец голоса»")
                return

        self.cancel_event.clear()
        self._last_pct = -1
        self.is_processing = True
        self.btn_process.configure(state="disabled", text="Обработка…")
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.lbl_audio_status.configure(text=_tr("Генерация текста…"), text_color=COLOR_ACCENT)
        self.update_status("⏳ Подготовка текста…")
        self.save_settings()

        threading.Thread(target=self.process_pipeline, args=(url, llm_name, source_text), daemon=True).start()

    def process_pipeline(self, url: str, llm_name: str, source_text: str):
        gpu_url = None  # адрес CUDA-сервера анализа (если модель считает на видеокарте)
        try:
            if self.cancel_event.is_set():
                raise Cancelled()

            self._last_pct = -1
            self.after(0, lambda: self.stats_label.configure(text=""))

            if source_text:
                text = re.sub(r'\s+', ' ', source_text).strip()
                self.after(0, lambda: self.update_status("Анализ вашего текста…"))
            else:
                self.after(0, lambda: self.update_status("Загрузка статьи…"))
                text = self.fetch_and_clean_text(url)
            self.after(0, lambda: self.set_progress(5, "Подготовка текста"))

            limit = self.model_limits.get(llm_name, FALLBACK_CHARS)
            n_chars = len(text)

            if n_chars > limit:
                msg = (f"Количество знаков {n_chars:,} — это больше поддерживаемого "
                       f"моделью {limit:,} знаков. Увеличьте контекст для модели ИИ.")
                self.after(0, lambda: messagebox.showwarning("Слишком длинный текст", msg.replace(",", " ")))
                raise TooLong(msg)
            self.after(0, lambda: self.set_progress(10, "Проверка объёма"))

            if len(text) < 100:
                raise Exception("Текст слишком короткий или пустой")

            if self.cancel_event.is_set():
                raise Cancelled()

            actual = self.llm_display.get(llm_name, llm_name)
            path = self.llm_models.get(actual)
            if not path or not os.path.exists(path):
                raise Exception(f"Файл модели не найден: {path}")

            n_ctx = self.model_ctx.get(llm_name, 4096)

            if self.llm_gpu_var.get():
                self.after(0, lambda: self.update_status("Загрузка модели на видеокарту…"))
                self.after(0, lambda: self.set_progress(12, "Загрузка на GPU"))
                port = self._ensure_gpu_server(path, n_ctx)
                gpu_url = f"http://127.0.0.1:{port}/v1/chat/completions"
                self.after(0, lambda: self.set_progress(15, "Модель на GPU"))
            else:
                if (self.llm_model is not None and self.llm_model_path == path
                        and self.llm_model_ctx == n_ctx):
                    print("♻️ Модель уже в памяти — переиспользую")
                    self.after(0, lambda: self.update_status("Модель уже в памяти"))
                else:
                    self.unload_llm()
                    self.after(0, lambda n=llm_name, c=n_ctx:
                               self.update_status(f"Загрузка модели «{n}» · контекст {c}…"))
                    self.after(0, lambda: self.set_progress(12, "Загрузка модели"))
                    self.llm_model = Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=0, n_threads=-1,
                                           flash_attn=True, verbose=False)
                    self.llm_model_path = path
                    self.llm_model_ctx = n_ctx
                self.after(0, lambda: self.set_progress(15, "Модель загружена"))

            if self.cancel_event.is_set():
                raise Cancelled()

            self.after(0, lambda: self.update_status("Анализ нейросетью…"))
            instruction = self.instruction_entry.get("1.0", "end-1c").strip()

            ratio = self._preset_ratio(self.preset_menu.get())
            target = None
            if ratio:
                target = max(60, int(len(text) * ratio))
                instruction = (instruction + f"\n\nОГРАНИЧЕНИЕ ОБЪЁМА: не более {target} знаков "
                               f"(около {int(ratio * 100)}% исходного текста). Это жёсткий лимит — "
                               f"если не укладываешься, сокращай дальше, сохраняя главное.")
                print(f"📏 Целевой объём: {target} знаков ({int(ratio * 100)}% от {len(text)})")

            summary = self.summarize_text(text, instruction, server_url=gpu_url)

            if target:
                summary = self._fit_to_limit(summary, target, server_url=gpu_url)

            stats = getattr(self, '_gen_stats', {}) or {}

            # Анализ закончен: модель анализа больше не нужна — освобождаем видеопамять,
            # чтобы Vox (GPU) мог загрузиться и не упирался в нехватку VRAM.
            if gpu_url:
                self._stop_gpu_server()
                gpu_url = None
                print("🧹 Видеопамять освобождена после анализа")

            if self.cancel_event.is_set():
                raise Cancelled()

            self.after(0, lambda: self.set_progress(100, "Готово"))
            self.after(0, lambda s=summary: self._set_box_text(s, generated=True))

            pct = round(len(summary) * 100 / max(1, len(text)))
            share = f"{len(summary)} зн. · {pct}% от исходного"
            if stats.get('tokens'):
                self.after(0, lambda s=share, st=stats: self.stats_label.configure(
                    text=" · ".join(_tr(p) for p in (
                        f"{st['tokens']} токенов", f"{st['elapsed']:.1f} с",
                        f"{st['tps']:.1f} ток/с", s))))
                self.after(0, lambda s=share, p=pct: self.update_status(
                    f"✅ Анализ завершён · {s}"))
            else:
                self.after(0, lambda s=share: self.update_status(f"✅ Анализ завершён · {s}"))
            if ratio and pct > int(ratio * 100) + 15:
                print(f"⚠️ Модель не уложилась в {int(ratio * 100)}%: получилось {pct}%")
            self.after(0, lambda: self.lbl_audio_status.configure(text=_tr("Готово"), text_color=COLOR_GREEN))
            self.box_is_source = False

            if self.auto_play_var.get() and not self.cancel_event.is_set():
                self.after(300, self.play_result)

        except TooLong:
            print("⚠️ Текст длиннее контекста модели — анализ не запускался")
            self.after(0, lambda: self.update_status("⚠️ Текст длиннее контекста модели"))
        except Cancelled:
            print("⏹ Анализ отменён")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка анализа: {error_msg}")
            self.after(0, lambda m=error_msg: messagebox.showerror("Анализ", m))
            self.after(0, lambda m=error_msg: self.update_status(f"❌ Ошибка: {m[:60]}"))
        finally:
            if gpu_url:
                self._stop_gpu_server()  # ошибка/отмена — VRAM всё равно освобождаем
                gpu_url = None
            self.is_processing = False
            self.after(0, self._update_char_count)
            self.after(0, lambda: self.btn_process.configure(state="normal", text=_tr("Запустить анализ")))
            self.after(0, self.progress_bar.stop)

    # ================= ВОСПРОИЗВЕДЕНИЕ =================

    def _play_wav(self, path):
        """Играет WAV внутри приложения, чтобы кнопка «Стоп» реально работала."""
        try:
            with wave.open(path) as w:
                sr = w.getframerate()
                ch = w.getnchannels()
                raw = w.readframes(w.getnframes())
            data = np.frombuffer(raw, dtype=np.int16)
            if ch > 1:
                data = data.reshape(-1, ch)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать WAV: {e}")
            try:
                os.startfile(path)
            except Exception:
                pass
            return

        if not SD_AVAILABLE:
            try:
                os.startfile(path)
            except Exception:
                pass
            return

        self._play_data = data
        self._play_sr = sr
        self._start_playback(data, sr)

    def _safe_ui(self, fn):
        """Обновление интерфейса из фонового потока — безопасно на любом этапе."""
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _close_play_stream(self):
        try:
            st = getattr(self, "_play_stream", None)
            if st is not None:
                st.abort()
                st.close()
        except Exception:
            pass
        self._play_stream = None

    def _make_pp_icons(self):
        """Рисует PNG-значки: ⏯ (треугольник + две полосы) и ■ (квадрат) — в одном стиле."""
        try:
            from PIL import Image, ImageDraw

            def icon(rgb, what="pp"):
                im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                col = (rgb[0], rgb[1], rgb[2], 255)
                if what == "stop":
                    try:
                        d.rounded_rectangle([13, 13, 51, 51], radius=5, fill=col)
                    except AttributeError:
                        d.rectangle([13, 13, 51, 51], fill=col)
                else:
                    d.polygon([(8, 10), (38, 32), (8, 54)], fill=col)
                    d.rectangle([43, 10, 49, 54], fill=col)
                    d.rectangle([53, 10, 59, 54], fill=col)
                return im.resize((32, 32), Image.LANCZOS)

            self._pp_light = ctk.CTkImage(light_image=icon((34, 34, 34)),
                                          dark_image=icon((232, 232, 232)), size=(16, 16))
            self._pp_dark = ctk.CTkImage(light_image=icon((255, 255, 255)),
                                         dark_image=icon((31, 31, 31)), size=(16, 16))
            self._stop_icon = ctk.CTkImage(light_image=icon((34, 34, 34), "stop"),
                                           dark_image=icon((232, 232, 232), "stop"), size=(15, 15))
        except Exception as e:
            print(f"⚠️ Иконки Play/Pause: {e}")
            self._pp_light = self._pp_dark = self._stop_icon = None

    def _pp_state(self, playing):
        """E-вариант: значок не меняется, состоянием управляет цвет кнопки."""
        try:
            if playing:
                self.btn_pp.configure(image=self._pp_dark, fg_color=COLOR_ACCENT,
                                      hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_ON_ACCENT)
            else:
                self.btn_pp.configure(image=self._pp_light, fg_color=COLOR_FILL_SOFT,
                                      hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN)
        except Exception:
            pass

    def _start_playback(self, data, sr):
        """Играем потоково (50-мс блоками) — чтобы можно было встать на паузу по месту."""
        self._close_play_stream()
        self._play_stop_req = False
        self._play_paused = False
        self._play_done = False
        self._play_pos = 0
        try:
            ch = 1 if data.ndim == 1 else int(data.shape[1])
            stream = sd.OutputStream(samplerate=sr, channels=ch, dtype="int16")
            stream.start()
            self._play_stream = stream
        except Exception as e:
            print(f"⚠️ Воспроизведение: {e}")
            self._playing = False
            self._play_done = True
            self._safe_ui(lambda: self.lbl_audio_status.configure(text=_tr("Ошибка звука"),
                                                                  text_color=COLOR_RED))
            return
        self._playing = True
        self._safe_ui(lambda: self.lbl_audio_status.configure(text=_tr("Воспроизведение…"),
                                                              text_color=COLOR_ACCENT))
        self._safe_ui(lambda: self._pp_state(True))
        threading.Thread(target=self._pump_playback, args=(stream, data, sr), daemon=True).start()

    def _pump_playback(self, stream, data, sr):
        block = max(1, int(sr * 0.05))
        try:
            while True:
                if self._play_stream is not stream or self._play_stop_req:
                    return
                if self._play_pos >= len(data):
                    break
                if self._play_paused:
                    time.sleep(0.05)
                    continue
                chunk = data[self._play_pos:self._play_pos + block]
                stream.write(chunk)
                self._play_pos += len(chunk)
            if self._play_stream is stream and not self._play_stop_req:
                self._play_done = True
                self._playing = False
                self._safe_ui(lambda: self._pp_state(False))
        except Exception as e:
            print(f"⚠️ Проигрывание: {e}")

    def _toggle_play_pause(self):
        """Play/Pause: пауза по месту → повтор с места паузы; после конца — с начала."""
        if self._playing and not self._play_done:
            self._play_paused = not self._play_paused
            if self._play_paused:
                self._safe_ui(lambda: self.lbl_audio_status.configure(text=_tr("Пауза"),
                                                                      text_color=COLOR_TEXT_SEC))
                self._safe_ui(lambda: self._pp_state(False))
            else:
                self._safe_ui(lambda: self.lbl_audio_status.configure(text=_tr("Воспроизведение…"),
                                                                      text_color=COLOR_ACCENT))
                self._pp_state(True)
            return
        # не играем или уже закончилось — играем готовый звук заново
        cached = getattr(self, "_last_audio", None)
        if cached and os.path.isfile(cached[4]):
            self._play_wav(cached[4])
        else:
            self.play_result()

    def stop_playback(self):
        """Стоп: глушит звук и прерывает синтез, если он ещё идёт."""
        self._play_stop_req = True
        self._play_paused = False
        self._close_play_stream()
        if SD_AVAILABLE:
            try:
                sd.stop()
            except Exception:
                pass
        self._playing = False
        self._play_done = True
        self.cancel_event.set()
        try:
            self.progress_bar.stop()
        except Exception:
            pass
        self.lbl_audio_status.configure(text=_tr("Остановлено"), text_color=COLOR_RED)
        self.update_status("⏹ Остановлено")
        self._safe_ui(lambda: self._pp_state(False))

    def play_result(self):
        if self.is_processing:
            return
        text = "" if self._placeholder_active else self.result_box.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Внимание", "Нет текста для озвучки.")
            return

        if self.current_engine == "Vox":
            speaker = self.tts_combo.get()
            _, info = self._find_voice(speaker)
            if not speaker or info is None or not (info.get("path") and os.path.exists(info.get("path") or "")):
                messagebox.showwarning("Внимание", "Запишите голос: «🎙 Образец голоса»")
                return
            self.current_tts_name = speaker
        else:  # Piper — голосовой объект должен быть готов до синтеза
            if not self.tts_voice:
                if self.tts_combo.get():
                    self.load_tts_on_select()
                if not self.tts_voice:
                    messagebox.showwarning("Внимание", "Голос не выбран.")
                    return

        voice_key = (self.current_tts_name or self.tts_combo.get()) \
            if self.current_engine == "Vox" else self.tts_combo.get()
        cached = getattr(self, "_last_audio", None)
        if (cached and cached[0] == text and cached[1] == self.current_engine
                and cached[2] == voice_key and abs(cached[3] - self.speech_rate) < 1e-9
                and os.path.isfile(cached[4])):
            # тот же текст, голос и скорость — играем готовый WAV без повторного синтеза
            self._last_pct = -1
            self.progress_bar.set(1.0)
            self._play_wav(cached[4])
            return

        self._synth_voice_key = voice_key
        self.cancel_event.clear()
        self._last_pct = -1
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.lbl_audio_status.configure(text=_tr("⏳ Синтез..."), text_color=COLOR_HEAD)
        threading.Thread(target=self.generate_and_play, args=(text,), daemon=True).start()

    # ================= СИНТЕЗ =================

    def generate_and_play(self, text: str):
        temp_file = os.path.join(self.BASE_DIR, "temp_output_pro.wav")
        try:
            orig_text = text
            text = self.normalize_for_tts(text)
            rate = self.speech_rate

            if self.current_engine == "Vox":
                if self.vox_model is None:
                    self.after(0, lambda: self.update_status("⏳ Загрузка VoxCPM2..."))
                    if not self.load_vox(show_errors=True):
                        raise Exception("Не удалось загрузить VoxCPM2")

                actual_rate = rate * VOX_BASE_SPEED
                fast = False
                self.after(0, lambda: self.update_status(f"⏳ Синтез VoxCPM2 (GPU, ×{actual_rate:.2f})..."))

                speaker = self.current_tts_name or self.tts_combo.get()
                if not speaker:
                    _, info = self._first_empty_voice()
                    filled = [i.get("name") for _, i in self._voice_items()
                              if isinstance(i, dict) and i.get("path") and os.path.exists(i.get("path") or "")]
                    speaker = filled[-1] if filled else ""
                if not speaker:
                    raise Exception("Не выбран голос для озвучки: запишите образец «🎙 Образец голоса».")
                ref_wav, ref_text = self.get_ref(speaker)
                # Vox «съедает» последнее слово, если фраза не закрыта знаком препинания
                text = text.strip()
                if text and text[-1] not in ".!?…:;»\"')":
                    text += "."
                # 200 знаков — компромисс: тембр держится, пауз между фразами немного
                chunks = self.split_text_chunks(text, limit=200)
                print(f"📚 Чанков для озвучки: {len(chunks)}")
                segs = []
                sr_out = None
                skipped = 0
                for i, ch in enumerate(chunks):
                    if self.cancel_event.is_set():
                        raise Cancelled()
                    self._safe_ui(lambda p=i, n=len(chunks): self.set_progress(
                        int(p * 95 / max(1, n)) + 3, f"Синтез {p + 1}/{n}"))
                    # убираем ведущие тире/кавычки/скобки/многоточия — фронтенд модели на них может дать пустоту
                    ch_clean = re.sub(r'^[^0-9A-Za-zА-Яа-яЁё]+', '', ch).strip()
                    if len(ch_clean) < 2:
                        continue
                    if ch_clean[-1] not in ".!?…:;":
                        ch_clean += "."
                    arr, sr = self._vox_synth_chunk(ch_clean, ref_wav, ref_text,
                                                    fast=fast, actual_rate=actual_rate)
                    # всё равно пусто — фиксируем пропуск в логе, а не молча
                    if len(arr) < int(sr * 0.1):
                        skipped += 1
                        print(f"❌ Чанк {i+1} пропущен (модель не дала аудио): {ch_clean[:70]}...")
                        continue
                    arr = self._stretch_int16(arr, actual_rate)
                    sr_out = sr
                    segs.append(arr)
                if skipped:
                    print(f"⚠️ Всего пропущено чанков: {skipped}")

                if not segs:
                    raise Exception("Vox не синтезировал ни одной фразы — проверьте голос-образец.")
                audio = self._join_chunks(segs, sr_out)
                with wave.open(temp_file, 'wb') as f:
                    f.setnchannels(1);
                    f.setsampwidth(2);
                    f.setframerate(sr_out)
                    f.writeframes(audio.tobytes())

                if self.cancel_event.is_set():
                    raise Cancelled()

                self._play_wav(temp_file)

            elif self.current_engine == "Piper":  # Piper (CPU)
                cfg = None
                if rate != 1.0:
                    try:
                        from piper import SynthesisConfig
                        cfg = SynthesisConfig(length_scale=1.0 / rate)
                    except Exception:
                        cfg = None

                pieces = self.split_text_chunks(text, limit=240) or [text]
                total = len(pieces)
                all_bytes = []
                sr, ch = None, None
                for idx, piece in enumerate(pieces):
                    if self.cancel_event.is_set():
                        raise Cancelled()
                    self._safe_ui(lambda i=idx, n=total: self.set_progress(
                        int(i * 95 / max(1, n)), f"Синтез {i + 1}/{n}"))
                    try:
                        gen = self.tts_voice.synthesize(piece, cfg) if cfg is not None else self.tts_voice.synthesize(piece)
                    except TypeError:
                        gen = self.tts_voice.synthesize(piece)
                        cfg = None
                    for chunk in gen:
                        if hasattr(chunk, 'audio_int16_bytes'):
                            all_bytes.append(chunk.audio_int16_bytes)
                            if sr is None: sr, ch = chunk.sample_rate, chunk.sample_channels
                        elif hasattr(chunk, 'audio_float_array'):
                            a = (chunk.audio_float_array * 32767).astype(np.int16)
                            all_bytes.append(a.tobytes())
                            if sr is None: sr, ch = chunk.sample_rate, chunk.sample_channels
                    if idx < total - 1:  # естественная пауза между фрагментами
                        all_bytes.append(np.zeros(int((sr or 22050) * 0.12), dtype=np.int16).tobytes())

                if not all_bytes:
                    raise Exception("Piper не сгенерировал аудио")

                data = b"".join(all_bytes)
                if rate != 1.0 and cfg is None:
                    arr = np.frombuffer(data, dtype=np.int16)
                    arr = self._stretch_int16(arr, rate)
                    data = arr.tobytes()

                with wave.open(temp_file, 'wb') as f:
                    f.setnchannels(ch);
                    f.setsampwidth(2);
                    f.setframerate(sr)
                    f.writeframes(data)

                if self.cancel_event.is_set():
                    raise Cancelled()

                self._play_wav(temp_file)

            if self.cancel_event.is_set():
                raise Cancelled()

            self._last_audio = (orig_text, self.current_engine,
                                getattr(self, "_synth_voice_key", self.tts_combo.get()),
                                rate, temp_file)
            self._safe_ui(lambda: self.set_progress(100, "Синтез завершён"))
            self.after(0, self.progress_bar.stop)
            final_rate = rate * (VOX_BASE_SPEED if self.current_engine == "Vox" else 1.0)
            self.after(0, lambda: self.lbl_audio_status.configure(
                text=f"✅ Воспроизводится ({self.current_engine}, ×{final_rate:.2f})", text_color=COLOR_GREEN))

        except Cancelled:
            print("⏹ Синтез отменён")
            self.after(0, self.progress_bar.stop)
            self.after(0, lambda: self.lbl_audio_status.configure(text=_tr("Отменено"), text_color=COLOR_RED))

        except Exception as e:
            msg = str(e)
            print(f"❌ Ошибка синтеза: {msg}")
            self.after(0, lambda: messagebox.showerror("Звук", msg))
            self.after(0, self.progress_bar.stop)
            self.after(0, lambda: self.lbl_audio_status.configure(text=_tr("❌ Ошибка"), text_color=COLOR_RED))


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FAIR.FreeAIReader")
    except Exception:
        pass
    app = ModernTTSApp()
    app.mainloop()