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
import tempfile
import pyperclip
import shutil
import zipfile
import xml.etree.ElementTree as ET

ssl._create_default_https_context = ssl._create_unverified_context
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*tokenizer.*")

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ---------- «Книга и кожа»: пары (бумага, кожа) — палитра сайта FAIRSite (Енот, 27.10.26) ----------
# Токены сайта: --paper #f3ecdd, --paper-2 #ece2cd, --paper-edge #d8cdb6, --ink #2b231c,
# --ink-2 #5c4f40, --leather #1c1510, --leather-hi #2b2018, --brand #c6763a, --gold #b08a3c, --gold-hi #e0ac42
COLOR_BG = ("#f3ecdd", "#1c1510")            # фон окна — бумага сайта (тёмная тема — кожа)
COLOR_PANEL = ("#f9f2e4", "#2b2018")         # панели — чуть светлее фона, как на сайте
COLOR_CARD = ("#fbf6ea", "#241b13")          # карточки — тон сайта .panel (#fbf6ea)
COLOR_CARD2 = ("#fffdf6", "#17120d")         # поля ввода и списки — самый светлый ТЗ-тон #fffdf6
COLOR_BORDER = ("#d8cdb6", "#4a3a28")        # разделители и обводки (paper-edge)
COLOR_ACCENT = ("#2b2018", "#c6763a")        # главные кнопки — тёмная кожа (состояние «играет»)
COLOR_ACCENT_HOVER = ("#1a130c", "#a95f2c")
COLOR_ACCENT_SOFT = ("#f1e9d7", "#35281d")   # мягкое нейтральное выделение
COLOR_SELECT = ("#f0dfae", "#3a2b1a")        # выделенная строка / наведение — мягкое золото
COLOR_SEG_ON = ("#c6763a", "#c6763a")        # активный пункт переключателя — медь
COLOR_SEG_ON_HOVER = ("#a95f2c", "#8f4e22")
COLOR_SEG_ON_TEXT = ("#fffdf6", "#fffdf6")
COLOR_SELECT_TEXT = ("#e0ac42", "#e0ac42")   # фон выделения текста — золото (как ::selection на сайте)
COLOR_HEAD = ("#7d4a1e", "#e0ac42")          # заголовки — жжёный янтарь
COLOR_TEXT_MAIN = ("#2b231c", "#f3e7cf")     # чернила / крем
COLOR_TEXT_SEC = ("#5c4f40", "#a08a5f")      # ink-2 / приглушённое золото
COLOR_ON_ACCENT = ("#f3e7cf", "#1c1510")     # кремовый текст на тёмной коже
COLOR_GREEN = ("#2e7d32", "#7bc67e")
COLOR_RED = ("#a04b2a", "#c96a45")           # ржавчина вместо алого — в тон книги
COLOR_FILL_SOFT = ("#f4ecd9", "#35281d")     # вторичные кнопки
COLOR_SWITCH_OFF = ("#cbbd9e", "#4a3a28")
COLOR_BRAND = ("#c6763a", "#c6763a")         # фирменная медь сайта — главные CTA
COLOR_BRAND_HOVER = ("#a95f2c", "#8f4e22")
COLOR_GOLD = ("#b08a3c", "#b08a3c")          # золото сайта — линейки-разделители

# ---------- шапка окна в цвет приложения (Windows 11, DWM) ----------
# Полоса со свернуть/развернуть/закрыть рисуется Windows, не customtkinter —
# красим её через DwmSetWindowAttribute: фон как бумага, текст чернильный.
def _dwm_titlebar(widget):
    def ref(h):
        h = h.lstrip("#")
        return int(h[4:6] + h[2:4] + h[0:2], 16)        # COLORREF = 0x00BBGGRR
    try:
        widget.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(widget.winfo_id()) or widget.winfo_id()
        dwm = ctypes.windll.dwmapi
        for attr, val in ((34, "#d8cdb6"),   # DWMWA_BORDER_COLOR  — край окна
                          (35, "#f3ecdd"),   # DWMWA_CAPTION_COLOR — сама полоса
                          (36, "#2e2620")):  # DWMWA_TEXT_COLOR    — надпись
            v = ctypes.c_int32(ref(val))
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr,
                                      ctypes.byref(v), ctypes.sizeof(v))
    except Exception as e:
        print(f"⚠️ цвет шапки окна: {e}")

# все диалоги (CTkToplevel) получают такую же шапку, что и главное окно
_orig_ctk_tl_init = ctk.CTkToplevel.__init__
def _ctk_tl_init_patched(self, *a, **kw):
    _orig_ctk_tl_init(self, *a, **kw)
    self.after(80, lambda: _dwm_titlebar(self))
ctk.CTkToplevel.__init__ = _ctk_tl_init_patched

COMBO_W = 260
R_PANEL = 4
R_CARD = 3
FALLBACK_CHARS = 6000
MIN_CTX = 2048
VOX_BASE_SPEED = 2.0  # базовое ускорение VoxCPM2 через ресемпл


def _gguf_raw_meta(path):
    """Читает метаданные GGUF (KV-секцию заголовка) без ggml: работают любые
    квантизации, в т.ч. те, что llama_cpp не умеет грузить (PTQ1_0 и др.).
    Возвращает dict; {} при ошибке."""
    import struct

    def rs(f):
        n = struct.unpack("<Q", f.read(8))[0]
        return f.read(n).decode("utf-8", "replace")

    FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i",
           6: "<f", 7: "<B", 10: "<Q", 11: "<q", 12: "<d"}

    def rv(f):
        t = struct.unpack("<I", f.read(4))[0]
        if t == 8:
            return rs(f)
        if t == 9:
            at = struct.unpack("<I", f.read(4))[0]
            n = struct.unpack("<Q", f.read(8))[0]
            if at == 8:                          # массив строк: идём по длинам,
                for _ in range(n):               # не сохраняя (vocab ~260k шт.)
                    ln = struct.unpack("<Q", f.read(8))[0]
                    f.seek(ln, 1)
                return None
            fm = FMT.get(at)
            if fm is None:
                raise ValueError("gguf type %d" % at)
            sz = struct.calcsize(fm)
            if n * sz > 4096:                    # большие числа нам не нужны
                f.seek(n * sz, 1)
                return None
            return [struct.unpack(fm, f.read(sz))[0] for _ in range(n)]
        fm = FMT.get(t)
        if fm is None:
            raise ValueError("gguf type %d" % t)
        return struct.unpack(fm, f.read(struct.calcsize(fm)))[0]

    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return {}
            f.read(4 + 8)                       # версия, число тензоров
            nkv = struct.unpack("<Q", f.read(8))[0]
            out = {}
            for _ in range(nkv):
                k = rs(f)                  # порядок важен: в 3.12 правая часть
                out[k] = rv(f)             # присваивания вычисляется первой
            return out
    except Exception:
        return {}


def _gguf_kv_est(md):
    """Размер KV-кэша контекста: (байт на токен, фиксированных байт).
    Считается по точным размерностям модели (head_count_kv, key/value_length),
    а не на глазок. Слои со скользящим окном (gemma-семейство) с контекстом
    не растут — за них берётся окно × группа слоёв один раз."""
    arch = md.get("general.architecture") or ""

    def g(key, d=0):
        return md.get(arch + "." + key, d)

    try:
        n = int(g("block_count"))
        kvh = int(g("attention.head_count_kv"))
        kl = int(g("attention.key_length"))
        vl = int(g("attention.value_length"))
    except Exception:
        n = kvh = kl = vl = 0
    if not n or not kvh:
        return 131072, 0                        # запас для неизвестных архитектур
    if not kl or not vl:
        heads, emb = int(g("attention.head_count")), int(g("embedding_length"))
        kl = vl = (emb // heads) if heads and emb else 128
    win = int(g("attention.sliding_window"))
    pat = g("attention.sliding_window_pattern", [])
    nswa = 0
    mult = 1
    if win and isinstance(pat, list) and pat:
        run = best = 0
        for x in pat:
            run = run + 1 if x else 0
            best = max(best, run)
        mult = max(2, best)                     # llama.cpp держит окно × группа
        nswa = sum(1 for i in range(n) if i != n - 1 and pat[i % len(pat)])
    per = (n - nswa) * kvh * (kl + vl) * 2      # полные слои: растут с контекстом
    kl2 = int(g("attention.key_length_swa", kl))
    vl2 = int(g("attention.value_length_swa", vl))
    fixed = nswa * win * mult * kvh * (kl2 + vl2) * 2 if nswa else 0
    return per, fixed

# ---------------------------------------------------------------------------
# Эмоции для правки голоса (VoxCPM2 Style Control).
# name -> (инструкция для Vox на английском, фраза для записи образца).
# Официальной схеме тегов эмоций у VoxCPM2 нет: в docs Style Control управляется
# свободным описанием на естественном языке в скобках перед текстом. Значит
# «поддерживается» та эмоция, для которой у нас подобрана внятная инструкция;
# список в интерфейсе строится ровно из этих названий -> выбрать
# нерабочее нельзя.
# ---------------------------------------------------------------------------
def _emo_key(word):
    """Основа названия эмоции: «радостный», «радостно», «радость» -> «радос»."""
    w = re.sub(r"[^а-яёa-z]", "", (word or "").lower().replace("ё", "е"))
    return w[:5] if len(w) >= 5 else w


# ---------------------------------------------------------------------------
# Qwen3-TTS — третий движок озвучки (версия 1.5). Модели лежат в models_qwen\
# рядом с программой: CustomVoice — встроенные голоса, Base — клон по образцу,
# VoiceDesign — голос из текстового описания.
# Base (1.7B) — русско-ударный файн-тюн siriusfreak (Apache-2.0): модель слушает
# знаки ударения U+0301 в тексте («за́мок/замо́к»), голая Qwen-база следовала им
# лишь в 65% случаев. Репозиторий сам содержит speech_tokenizer.
# ---------------------------------------------------------------------------
QWEN_MODELS = {
    "base":   "siriusfreak/qwen3-tts-12hz-1.7b-ru-stress-cf",
    "custom": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}
# лёгкий движок: 0.6B — дешевле по GPU, но без режима «Дизайн голоса»
QWEN_MODELS_06 = {
    "base":   "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "custom": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
}
QWEN_GB = {"base": 4.5, "custom": 4.5, "design": 4.5}   # примерно, для предупреждения
QWEN_GB_06 = {"base": 2.6, "custom": 2.6}
QWEN_HF_TREE = "https://huggingface.co/api/models/{repo}/tree/main?recursive=true"
QWEN_HF_FILE = "https://huggingface.co/{repo}/resolve/main/{file}"
QWEN_EXT = (".safetensors", ".json", ".model", ".tiktoken", ".txt", ".py")
QWEN_BASE_SPEED = 1.0   # Qwen говорит в естественном темпе — ускорение только с ползунка
QWEN_LANGS = ["auto", "Russian", "English", "Chinese", "German", "French", "Spanish",
              "Portuguese", "Italian", "Japanese", "Korean"]
# встроенный голос CustomVoice: id модели -> (русское имя, род, описание)
QWEN_SPEAKERS = {
    "Vivian":   ("Вивиан", "женский", "яркий молодой женский, чуть резковатый"),
    "Serena":   ("Серена", "женский", "тёплый мягкий женский"),
    "Uncle_Fu": ("Дядюшка Фу", "мужской", "зрелый мужской, низкий бархатный"),
    "Dylan":    ("Дилан", "мужской", "чистый молодой мужской (Пекин)"),
    "Eric":     ("Эрик", "мужской", "живой мужской с лёгкой хрипотцой (Чэнду)"),
    "Ryan":     ("Райан", "мужской", "динамичный мужской, сильный ритм"),
    "Aiden":    ("Эйдан", "мужской", "солнечный американский мужской"),
    "Ono_Anna": ("Оно-Анна", "женский", "игривый лёгкий женский"),
    "Sohee":    ("Сонхи", "женский", "тёплый выразительный женский"),
}
QWEN_DISPLAY = {disp for _sid, (disp, _g, _d) in QWEN_SPEAKERS.items()}
QWEN_BY_DISPLAY = {disp: (sid, gen, desc) for sid, (disp, gen, desc) in QWEN_SPEAKERS.items()}

EMOTION_TAB = {
    # --- светлая часть ---
    "радостный": ("very cheerful, joyful, excited tone, almost laughing",
                  "Ура! Наконец-то получилось! Это же здорово, правда?"),
    "весёлый": ("cheerful, upbeat, smiling, energetic tone",
                "Ой, как здорово! Обожаю такие дни, просто праздник какой-то!"),
    "восторженный": ("deeply delighted and amazed, wonder-filled tone",
                     "Невероятно! Это лучшая новость за весь месяц!"),
    "нежный": ("gentle, soft, affectionate and warm tone",
               "Как же я тебя люблю… Ты мой самый родной человек."),
    "заботливый": ("caring, warm, protective tone",
                   "Ты поел? Надень шапку, на улице холодно. И шарф не забудь."),
    # --- тёмная часть ---
    "грустный": ("very sad, sorrowful, quiet tone, on the verge of tears",
                 "Мне так грустно… Всё как будто потухло, и ничего не радует."),
    "печальный": ("melancholic, wistful, slow and quiet tone",
                  "Как же это всё печально… Ничего уже не вернуть."),
    "плачущий": ("crying, tearful, voice breaking with tears",
                 "Ну как же так… Я не могу, я просто плачу от этого."),
    "злой": ("angry, sharp, irritated tone",
             "Сколько можно! Я уже сто раз это повторял!"),
    "гневный": ("furious, forceful tone, almost shouting",
                "Это возмутительно! Так с людьми поступать нельзя!"),
    "испуганный": ("frightened, scared, shaky voice",
                   "Господи… Что это было? Там кто-то есть, я слышала!"),
    "тревожный": ("nervous, anxious, slightly trembling tone",
                  "А вдруг не получится? Мне правда очень неспокойно."),
    # --- деловая и нейтральная часть ---
    "строгий": ("strict, stern, commanding, teacher-like tone",
                "Проверь за собой. Сделай как следует, потом я проверю."),
    "серьёзный": ("serious, firm, businesslike tone",
                  "Давай по делу. Вопрос серьёзный, и решать его будем сейчас."),
    "командный": ("firm commanding tone, decisive and authoritative",
                  "Все остановились и слушают. Работаем по плану, время пошло."),
    "спокойный": ("calm, relaxed, steady tone",
                  "Так. Спокойно. Всё под контролем, всё будет хорошо."),
    "монотонный": ("bored, flat, monotone delivery",
                   "Сегодня обычный день. Утро, работа, вечер. Всё своим чередом."),
    "усталый": ("tired, slow, drained tone",
                "Я выжат полностью… Давай отложим это до завтра."),
    "шёпотом": ("quiet whispering, intimate tone",
                "Тссс… Говорю совсем тихо, чтобы никто случайно не услышал."),
    # --- окраска речи ---
    "удивлённый": ("surprised, astonished, expressive tone",
                   "Не может быть! Это правда ты? Вот так сюрприз!"),
    "саркастичный": ("sarcastic, mocking, ironical tone",
                     "Ну конечно. Гениально. Как же я сразу не догадался."),
    "драматичный": ("dramatic, expressive storytelling tone",
                    "И тогда всё рухнуло… Осталось только ждать, что будет дальше."),
    # синонимы той же окраски — чтобы привычные названия не терялись
    "ироничный": ("sarcastic, mocking, ironical tone",
                  "Отличная работа. Просто идеально. В следующий раз будет лучше."),
    "ласковый": ("affectionate, warm, loving tone",
                 "Иди ко мне, родной. Я согрею тебя, всё уже хорошо."),
    "тоскливый": ("heavy-hearted, longing, mournful tone",
                  "Эх… Так не хватает прошлого вечера, всё как будто не так."),
    "возмущённый": ("indignant, outraged, firm disapproving tone",
                    "Это ни в какие ворота! Так поступать просто недопустимо."),
}

# названия для раскрывающихся списков в панели эмоций
EMOTION_NAMES = list(EMOTION_TAB)


def emotion_marker_rule(names):
    """Просьба к модели разметить текст эмоциями: только те имена, что есть у голоса."""
    return ("РАЗМЕТКА ЭМОЦИЯМИ: перед фразами, которые нужно прочитать с чувством, ставь маркер "
            "в круглых скобках и пробел: (имя_эмоции) текст. "
            "Разрешены ТОЛЬКО эти имена: " + ", ".join(names) + ". "
            "Ставь один-два маркера на абзац и только там, где эмоция уместна по смыслу; "
            "маркер действует до конца предложения. Придумывать другие имена в скобках нельзя.")


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


def _sox_stub_if_needed():
    """Пакет sox при импорте запускает os.popen('sox -h'); в pythonw без валидного
    stderr-хендла DuplicateHandle даёт OSError WinError 50 и рвёт весь импорт
    qwen_tts (проверено живым логом 05.11.26). Бинарного SoX в системе всё равно
    нет, а qwen_tts трогает sox.Transformer() только в конструкторе токенизатора
    v1 — путь синтеза его не дёргает (дымы CustomVoice/VoiceDesign/Clone прошли).
    поэтому при сбое импорта подставляем безобидную заглушку."""
    if "sox" in sys.modules:
        return
    try:
        import sox  # noqa: F401
    except Exception:
        import types
        fake = types.ModuleType("sox")

        class _NoSox:           # конструктор без требований (как у настоящего
            pass                # Transformer); вызовы методов дадут явную ошибку


        fake.Transformer = _NoSox
        fake.SoXController = _NoSox
        sys.modules["sox"] = fake


FONT_FAMILY = "Segoe UI Variable Text" if platform.system() == "Windows" else "San Francisco"
FONT_HEADER = (FONT_FAMILY, 18, "bold")
FONT_SUBHEADER = (FONT_FAMILY, 13, "bold")
FONT_NORMAL = (FONT_FAMILY, 12)
FONT_SMALL = (FONT_FAMILY, 11)
FONT_TINY = (FONT_FAMILY, 10)


def _style_tk_menu(menu):
    """Системное контекстное меню — в стиле сайта: бумага, чернила, золото."""
    try:
        menu.configure(bg="#fdf6e8", fg="#2b231c", bordercolor="#d8cdb6",
                       activebackground="#e0ac42", activeforeground="#2b231c")
    except Exception:
        pass


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


def _center_on_parent(win):
    """Поставить окно по центру главного окна программы, не выпуская его за его пределы.
    Размер берётся из уже заданной geometry — окно СРАЗУ появляется по центру,
    без мигания в углу (Ярослав, 05.11: окно сначала мелькало слева)."""
    try:
        g = (win.geometry() or "").strip()
        gm = re.fullmatch(r"(\d+)x(\d+)(?:[+-]\d+[+-]\d+)?", g)
        if gm:
            w, h = int(gm.group(1)), int(gm.group(2))
        else:
            w = max(win.winfo_width(), win.winfo_reqwidth())
            h = max(win.winfo_height(), win.winfo_reqheight())
        root = getattr(win, "master", None)
        if root is None or not root.winfo_exists() or root.winfo_width() < 10:
            return
        rx, ry = root.winfo_x(), root.winfo_y()
        rw, rh = root.winfo_width(), root.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        if w <= rw:
            x = max(rx, min(x, rx + rw - w))
        if h <= rh:
            y = max(ry, min(y, ry + rh - h))
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    except Exception:
        pass


class DonateDialog(ctk.CTkToplevel):
    """Оценка приложения и переход на страницу донатов."""

    def __init__(self, parent, on_pay):
        super().__init__(parent)
        self.title(_tr("Благодарить"))
        self.geometry("440x430")
        _center_on_parent(self)
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


class _EmoCombo(ctk.CTkComboBox):
    """Название эмоции: выбор из списка ИЛИ свой текст. CTkComboBox в 6.0 не умеет
    insert/delete — добавляю, чтобы строки эмоций работали как раньше."""

    def insert(self, index, text):
        self._entry.insert(index, text)

    def delete(self, first=0, last="end"):
        self._entry.delete(first, last)


class VoiceRecorderDialog(ctk.CTkToplevel):
    """Запись/выбор образца голоса с сохранением в слот.

    Открывается заново — показывает то, что уже лежит в слоте: файл, длительность
    и текст образца. Переключение слота подгружает его содержимое.
    """

    DEFAULT_TEXT = "Привет! Это образец моего голоса для синтеза речи."
    # фразы для записи эмоции: не общие, а сразу с нужной интонацией
    EMOTION_SAMPLE_TEXT = {_emo_key(n): p for n, (_, p) in EMOTION_TAB.items()}
    # те же фразы по-английски: если нейтральный образец голоса на английском,
    # эмоциональные образцы тоже пишем по-английски — так Vox передаёт эмоцию точнее
    EMOTION_SAMPLE_TEXT_EN = {_emo_key(n): p for n, p in (
        ("радостный", "We actually did it! I still can't believe how happy I am."),
        ("весёлый", "Ha! You really should have seen your own face then."),
        ("восторженный", "This is the most incredible thing I have ever seen!"),
        ("нежный", "Come here, everything is going to be all right."),
        ("заботливый", "Did you eat anything today? Please take care of yourself."),
        ("грустный", "I miss him so much that it actually hurts."),
        ("печальный", "It's over now, and nothing will ever be the same."),
        ("плачущий", "I'm sorry, I just can't stop crying about this."),
        ("тоскливый", "Another grey day, and nothing ever happens here."),
        ("злой", "How could you do this to me? Look at me and answer!"),
        ("гневный", "I am furious, and you deserve every single word."),
        ("возмущённый", "This is absolutely unacceptable, do you understand me?"),
        ("испуганный", "Please don't come any closer, I'm really scared."),
        ("тревожный", "Something is wrong, and I can't stop worrying."),
        ("строгий", "Sit down, stay quiet, and listen to me carefully."),
        ("серьёзный", "We need to talk about this, right now, seriously."),
        ("командный", "Everyone out through the side exit. Move, now!"),
        ("спокойный", "Let's take a breath and sort this out calmly."),
        ("монотонный", "The report is due on monday, the review on tuesday, then lunch."),
        ("усталый", "I'm so tired I can barely keep my eyes open."),
        ("шёпотом", "Keep your voice down, they might be listening to us."),
        ("удивлённый", "Wait, you actually remembered my birthday?"),
        ("саркастичный", "Oh, brilliant. Exactly what we needed more of."),
        ("ироничный", "Well, that went exactly as planned. Not at all."),
        ("ласковый", "Hey you, my favourite person in the entire world."),
        ("драматичный", "And then, in one awful moment, everything was gone."),
    )}
    _EMO_FALLBACK_RU = ("Вот так я говорю, когда во мне слышится эта эмоция. "
                        "Повтори эту фразу своей интонацией.")
    _EMO_FALLBACK_EN = ("This is how my voice sounds when it carries this feeling. "
                        "Say it your own way.")

    @staticmethod
    def _is_english(text):
        """Английский ли текст: примитив, но надёжный — латиницы больше, чем кириллицы."""
        text = text or ""
        cyr = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
        lat = sum(1 for ch in text if ch.lower() in "abcdefghijklmnopqrstuvwxyz")
        return lat > cyr and lat >= 3

    def _sample_lang(self):
        """Язык нейтрального образца текущего голоса: по нему подбираем и фразы эмоций."""
        try:
            info = self._cur_info() or {}
        except Exception:
            info = {}
        return "en" if self._is_english(info.get("text")) else "ru"

    @classmethod
    def _emo_sample_text(cls, label, lang="ru"):
        """Фраза для записи эмоции — под подобранную эмоцию, а не общая."""
        table = cls.EMOTION_SAMPLE_TEXT_EN if lang == "en" else cls.EMOTION_SAMPLE_TEXT
        low = (label or "").lower().replace("ё", "е")
        for stem, phrase in table.items():
            if stem in low:
                return phrase
        return cls._EMO_FALLBACK_EN if lang == "en" else cls._EMO_FALLBACK_RU

    @staticmethod
    def _emotion_filename(slot_id, label):
        """Отдельный файл образца эмоции — нейтральный my_voice_<слот>.wav не перезаписываем."""
        slug = re.sub(r"[^\w.-]+", "_", (label or "").strip().lower()).strip("_")[:24] or "emotion"
        return f"my_voice_{slot_id}_{slug}.wav"

    def __init__(self, parent, on_save, slot_id=None, initial_name=None, existing=None,
                 emotion_mode=False, voice_label=None, initial_text=None):
        super().__init__(parent)
        self.emotion_mode = bool(emotion_mode)
        self.voice_label = voice_label or ""
        self._pending_text = (initial_text or "").strip()
        # в режиме эмоции initial_name — это название эмоции, voice_label — имя голоса
        self._emo_hint_label = (initial_name or "") if self.emotion_mode and initial_name else (voice_label or "")
        self.title("Эмоция голоса" if emotion_mode else "Свой голос")
        self._emo_open = False    # раскрыта ли правая колонка эмоций
        self._emo_frame = None
        self._emo_rows = []
        self._emo_need = 0
        self._base_geo = "470x656" if not emotion_mode else "470x612"
        self.geometry(self._base_geo)
        _center_on_parent(self)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.after(0, lambda: _apply_lang(self))
        _apply_dialog_icon(self)                       # сразу, чтобы не мигал системный
        self.after(150, lambda: _apply_dialog_icon(self))
        _p = parent
        while getattr(_p, "master", None) is not None:
            _p = _p.master
        self.app = _p if hasattr(_p, "emotion_synth") else None
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
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=470)   # левая часть не сжимается
        self.grid_columnconfigure(1, weight=1)
        body.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self._body = body

        ctk.CTkLabel(body, text=("Эмоция голоса" if self.emotion_mode else "Образец голоса"),
                     font=(FONT_FAMILY, 16, "bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", padx=18, pady=(16, 2))
        _sub = ("5–15 секунд чистой речи. Образец добавится к голосу."
                if self.emotion_mode and not voice_label else
                (f"5–15 секунд чистой речи. Образец добавится к голосу «{voice_label}»."
                 if self.emotion_mode else
                 "5–15 секунд чистой речи. Образец и текст сохраняются в слоте."))
        ctk.CTkLabel(body, text=_sub, font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                     anchor="w", wraplength=360).pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(body, text=("Название эмоции" if self.emotion_mode else "Название голоса"),
                     font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                     anchor="w").pack(fill="x", padx=18)
        self.entry_name = ctk.CTkEntry(body, height=32, corner_radius=3, font=FONT_NORMAL,
                                       placeholder_text=("Например: радостный" if self.emotion_mode
                                                         else "Например: Мой голос"),
                                       fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT_MAIN)
        self.entry_name.pack(fill="x", padx=18, pady=(4, 10))
        try:
            self.entry_name._entry.configure(selectbackground="#e0ac42", selectforeground="#2b231c")
        except Exception:
            pass
        if initial_name:
            self.entry_name.insert(0, initial_name)

        sample_card = ctk.CTkFrame(body, fg_color=COLOR_CARD2, corner_radius=4,
                                   border_width=1, border_color=COLOR_BORDER)
        sample_card.pack(fill="x", padx=18, pady=(0, 10))

        self.lbl_sample = ctk.CTkLabel(sample_card, text="Образец ещё не записан", font=FONT_SMALL,
                                       text_color=COLOR_TEXT_SEC, anchor="w",
                                       wraplength=360)
        self.lbl_sample.pack(fill="x", padx=14, pady=(10, 6))

        row = ctk.CTkFrame(sample_card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))
        row.grid_columnconfigure(0, weight=1)

        self.btn_rec = ctk.CTkButton(row, text="●  Начать запись", command=self.toggle_recording,
                                     height=34, corner_radius=3, font=(FONT_FAMILY, 12, "bold"),
                                     fg_color=COLOR_RED, hover_color=COLOR_RED, text_color="#fffdf6")
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
        self.entry_text.insert("1.0", self._sample_hint())

        # переключатель Vox/Qwen из окна убран (Ярослав, 05.11): голос сам
        # привяжется к тому движку, под которым открыто окно
        self.engine_toggle = None

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", padx=18, pady=(0, 10))
        btns.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btns, text="Сохранить", command=self.save_voice, height=36, corner_radius=3,
                      font=(FONT_FAMILY, 12, "bold"), fg_color=COLOR_ACCENT,
                      hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_ON_ACCENT).grid(row=0, column=0,
                                                                                       sticky="ew", padx=(0, 5))
        ctk.CTkButton(btns, text="Отмена", command=self.destroy, height=36, corner_radius=3,
                      font=FONT_NORMAL, fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_MAIN).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # «🗑 Удалить голос» — прямо в окне образца (Ярослав, 05.11.26): видно,
        # когда слот уже заполнен и движок Vox/Qwen
        self.btn_del = None
        if (not self.emotion_mode and self.slot_id is not None
                and getattr(self.app, "current_engine", "") in ("Vox", "Qwen")
                and (self._cur_info() or {}).get("path")):
            self.btn_del = ctk.CTkButton(body, text="🗑  " + _tr("Удалить голос"),
                                         height=30, corner_radius=3, font=FONT_SMALL,
                                         fg_color="transparent", hover_color=COLOR_SELECT,
                                         text_color=COLOR_RED, border_width=1,
                                         border_color=COLOR_BORDER,
                                         command=self._delete_from_dialog)
            self.btn_del.pack(fill="x", padx=18, pady=(0, 8))
            self._base_geo = "470x" + str(int(self._base_geo.split("x")[1]) + 42)
            self.geometry(self._base_geo)

        self._build_emotion_column(body)   # доп. опция под «Сохранить»: кнопка + выезжающая колонка

        tb = self.entry_text._textbox
        tb.configure(selectbackground="#e0ac42", selectforeground="#2b231c",
                     inactiveselectbackground="#e0ac42")
        tb.bind("<Button-3>", self._text_menu, add="+")
        for seq in ("<Control-v>", "<Control-V>", "<Control-Shift-v>", "<Control-Shift-V>",
                    "<Shift-Insert>", "<Control-Insert>"):
            tb.bind(seq, self._paste_event, add="+")
        tb.bind("<KeyPress>", self._paste_by_keycode, add="+")
        self._load_slot()
        self.after(120, self._focus_text)

    # ---------- правая колонка эмоций ----------

    def _sample_hint(self):
        """Фраза-подсказка в поле текста: для эмоции — подобранная под эмоцию."""
        if self.emotion_mode:
            return self._pending_text or self._emo_sample_text(self._emo_hint_label,
                                                               lang=self._sample_lang())
        return _tr(self.DEFAULT_TEXT)

    _EMO_COL_W = 470        # сколько добавляем справа при раскрытии колонки
    _EMO_MIN_ROWS = 4       # три основные уже вписаны + одна пустая под свою
    EMO_PRESETS = ("радостный", "строгий", "грустный")
    # что можно выбрать в раскрывающемся списке: каждое имя подбирает свою фразу-образец
    EMO_CHOICES = EMOTION_NAMES  # из справочника EMOTION_TAB

    @staticmethod
    def _emo_btn_text(is_open):
        return "😊  " + _tr("Эмоции") + ("   ▾" if is_open else "   ▸")

    def _build_emotion_column(self, parent):
        """Компактная кнопка под «Сохранить» + правая колонка эмоций."""
        if self.emotion_mode:
            return
        if getattr(self.app, "current_engine", "") == "Qwen":
            # у Qwen эмоции задаёт движок (инструкция/маркеры в тексте) —
            # эмоциональных образцов не нужно (Ярослав, 04.11.26)
            return
        self.btn_emos = ctk.CTkButton(
            parent, text=self._emo_btn_text(False), width=260, height=32, corner_radius=4,
            font=(FONT_FAMILY, 11, "bold"), fg_color=COLOR_BRAND,
            hover_color=COLOR_BRAND_HOVER, text_color="#ffffff",
            command=self._toggle_emotions)
        self.btn_emos.pack(anchor="center", pady=(14, 20))
        self._emo_frame = ctk.CTkFrame(self, width=self._EMO_COL_W, fg_color=COLOR_PANEL,
                                       corner_radius=R_PANEL, border_width=1,
                                       border_color=COLOR_BORDER)
        self._emo_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._emo_frame, text="😊  " + _tr("Эмоции голоса"),
                     font=(FONT_FAMILY, 15, "bold"), text_color=COLOR_TEXT_MAIN).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(self._emo_frame,
                     text=_tr("Маркер в тексте: (радостный) фраза.\n"
                              "Без маркера — нейтральный голос. Запиши или синтезируй."),
                     font=FONT_TINY, text_color=COLOR_TEXT_SEC, justify="left").grid(
            row=1, column=0, sticky="w", padx=16, pady=(0, 10))
        # строк может быть до 10 — площадь с прокруткой, чтобы окно оставалось прежней высоты
        self._emo_rows_box = ctk.CTkScrollableFrame(self._emo_frame, fg_color="transparent",
                                                    height=524)
        self._emo_rows_box.grid(row=2, column=0, sticky="nsew", padx=(10, 4), pady=(0, 6))
        self._emo_rows_box.grid_columnconfigure(0, weight=1)
        self._emo_frame.grid_rowconfigure(2, weight=1)
        self._emo_rows = []
        for i in range(self._EMO_MIN_ROWS):
            self._make_emo_row(i)
        ctk.CTkLabel(self._emo_frame,
                     text=_tr("Запись с микрофона в этот же голос.") + "\n"
                          + _tr("Нейросинтез эмоции из нейтрального образца этого голоса.") + "\n"
                          + _tr("Сколько угодно эмоций — новая строка появляется сама."),
                     font=FONT_TINY, text_color=COLOR_TEXT_SEC, justify="left").grid(
            row=3, column=0, sticky="w", padx=16, pady=(0, 6))
        self._fill_existing_labels()
        self._rows_visibility()
        try:    # стрелка раскрывающегося списка подсвечивается при наведении, как в окне
            if self.app and hasattr(self.app, "_polish_cursors"):
                self.app._polish_cursors(self)
        except Exception:
            pass

    def _make_emo_row(self, i):
        """Одна строка эмоций: название + статус + кнопки. Строки создаются по
        мере надобности — список эмоций не ограничен в длине."""
        rowf = ctk.CTkFrame(self._emo_rows_box, fg_color=COLOR_CARD, corner_radius=8)
        rowf.grid(row=i, column=0, sticky="ew", padx=6, pady=(0, 10))
        self._emo_rows_box.grid_rowconfigure(i, weight=0)
        ent = _EmoCombo(
            rowf, values=list(self.EMO_CHOICES), font=FONT_SMALL, height=32,
            corner_radius=3, border_width=1, border_color=COLOR_BORDER,
            fg_color="#ffffff", button_color=COLOR_BRAND,
            button_hover_color=COLOR_BRAND_HOVER, dropdown_fg_color="#ffffff",
            dropdown_hover_color=COLOR_SELECT, dropdown_text_color=COLOR_TEXT_MAIN,
            text_color=COLOR_TEXT_MAIN,
            command=lambda val, i=i: self._combo_pick(i))
        try:    # подсказка как у остальных полей окна
            ent._entry.configure(
                placeholder_text=_tr("название эмоции (например: радостный)"))
        except Exception:
            pass
        ent.pack(fill="x", padx=10, pady=(10, 4))
        stat = ctk.CTkLabel(rowf, text="— " + _tr("не задана"), font=FONT_TINY,
                            text_color=COLOR_TEXT_SEC, anchor="w")
        stat.pack(fill="x", padx=12)
        brow = ctk.CTkFrame(rowf, fg_color="transparent")
        brow.pack(fill="x", padx=10, pady=(4, 10))
        brow.grid_columnconfigure(1, weight=1)
        rec = ctk.CTkButton(brow, text="🎙  " + _tr("Записать"), width=104, height=30,
                            corner_radius=3, font=FONT_SMALL,
                            fg_color=COLOR_FILL_SOFT, hover_color=COLOR_SELECT,
                            text_color=COLOR_TEXT_MAIN,
                            command=lambda i=i: self._emo_record(i))
        rec.grid(row=0, column=0, padx=(0, 6))
        syn = ctk.CTkButton(brow, text="✨  " + _tr("Синтезировать"), height=30,
                            corner_radius=3, font=FONT_SMALL,
                            fg_color=COLOR_BRAND, hover_color=COLOR_BRAND_HOVER,
                            text_color="#ffffff",
                            command=lambda i=i: self._emo_synth(i))
        syn.grid(row=0, column=1, sticky="ew")
        dlt = ctk.CTkButton(brow, text="🗑", width=36, height=30, corner_radius=3,
                            fg_color="transparent", hover_color=COLOR_SELECT,
                            border_width=1, border_color=COLOR_BORDER,
                            text_color=COLOR_TEXT_SEC,
                            command=lambda i=i: self._emo_delete(i))
        dlt.grid(row=0, column=2, padx=(6, 0))
        if i < len(self.EMO_PRESETS):
            ent.insert(0, self.EMO_PRESETS[i])   # три основные эмоции уже вписаны
        ent.bind("<KeyRelease>", lambda e: (self._rows_visibility(),
                                            self._refresh_emotions()))
        self._emo_rows.append({"frame": rowf, "ent": ent, "stat": stat, "rec": rec,
                               "syn": syn, "del": dlt, "label": ""})

    def _ensure_rows(self, n):
        """Достроить строк, чтобы их было не меньше n (списка-потолка нет)."""
        while len(self._emo_rows) < n:
            self._make_emo_row(len(self._emo_rows))

    def _fill_existing_labels(self):
        """Уже записанные эмоции этого голоса — в первые строки, основные — следом за ними."""
        have = list((self._cur_info().get("samples") or {}).keys())
        names = have + [p for p in self.EMO_PRESETS if p not in have]
        self._ensure_rows(max(self._EMO_MIN_ROWS, len(names) + 1))
        for row in self._emo_rows:      # иначе в скрытых строках остаются прошлые имена
            row["ent"].delete(0, "end")
            row["label"] = ""
        for i, nm in enumerate(names):
            row = self._emo_rows[i]
            row["ent"].delete(0, "end")
            row["ent"].insert(0, nm)
            row["label"] = nm

    def _rows_visibility(self):
        """Строк ровно столько, сколько вписано, плюс одна пустая (минимум — 4).
        Новые строки достраиваются на лету — количество эмоций не ограничено."""
        if not self._emo_rows:
            self._emo_need = 0
            return
        filled = sum(1 for r in self._emo_rows if (r["ent"].get() or "").strip())
        self._ensure_rows(max(self._EMO_MIN_ROWS, filled + 1))
        self._emo_need = max(self._EMO_MIN_ROWS, filled + 1)
        for i, r in enumerate(self._emo_rows):
            if i < self._emo_need:
                r["frame"].grid()
            else:
                r["frame"].grid_remove()
        self._update_combo_values()
        try:    # подсвечиваем только что появившуюся пустую строку
            if self._emo_need > 4:
                self._emo_rows_box._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _visible_rows(self):
        return self._emo_rows[:getattr(self, "_emo_need", 0)]

    def _combo_pick(self, i):
        """Выбрали эмоцию из списка: пересобираем списки и проверяем новую строку."""
        self._rows_visibility()
        self._refresh_emotions()

    def _update_combo_values(self):
        """В каждом раскрывающемся списке свои варианты: уже занятые в других строках скрыты."""
        if not self._emo_rows:
            return
        for i, r in enumerate(self._emo_rows):
            mine = (r["ent"].get() or "").strip()
            used = set()
            for j, o in enumerate(self._emo_rows):
                if j != i:
                    nm = (o["ent"].get() or "").strip()
                    if nm:
                        used.add(nm)
            vals = [c for c in self.EMO_CHOICES if c not in used]
            if mine and mine not in vals:
                vals.insert(0, mine)      # своё значение всегда видно
            try:
                r["ent"].configure(values=vals)
            except Exception:
                pass

    def _geo_now(self):
        """(ширина, высота) текущего окна — без позиции."""
        m = re.fullmatch(r"(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?", (self.geometry() or "").strip())
        if m:
            return int(m.group(1)), int(m.group(2))
        bw, bh = self._base_geo.split("x")
        return int(bw), int(bh)

    def _set_width(self, target):
        """Меняем ширину окна сразу: колонка появляется мгновенно, рекордер не меняется."""
        try:
            self.geometry(f"{int(target)}x{self._geo_now()[1]}")
            _center_on_parent(self)
        except Exception:
            pass

    def _toggle_emotions(self):
        """Развернуть/свернуть правую колонку эмоций — окно плавно выезжает вправо."""
        if self._emo_frame is None:
            self._build_emotion_column(self._body)
        base_w = int(self._base_geo.split("x")[0])
        if self._emo_open:
            self._emo_open = False
            self.btn_emos.configure(text=self._emo_btn_text(False))
            self._emo_frame.grid_forget()
            self._set_width(base_w)
        else:
            self._emo_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
            self._emo_open = True
            self.btn_emos.configure(text=self._emo_btn_text(True))
            self._refresh_emotions()
            self._set_width(min(base_w + self._EMO_COL_W,
                                int(self.winfo_screenwidth()) - 40))

    def _refresh_emotions(self):
        if self.app and self._emo_rows and hasattr(self.app, "refresh_emotion_rows"):
            self.app.refresh_emotion_rows(self._visible_rows(), self.slot_id)

    def _cur_info(self):
        """Инфо слота в этом окне: ключи custom_voices — строки, slot_id — число."""
        return (self.existing.get(self.slot_id)
                or self.existing.get(str(self.slot_id)) or {})

    def _delete_from_dialog(self):
        """Удалить голос прямо из окна «Образец голоса» (Ярослав, 05.11.26).
        Спросит один раз сам _delete_voice — не плодим второе подтверждение."""
        info = self._cur_info() or {}
        nm = info.get("name") or self.entry_name.get() or ""
        try:
            if self.app._delete_voice(vid=self.slot_id, name=nm):
                self.destroy()   # закрыли — удалили; отменил подтверждение — окно живёт
        except Exception:
            pass

    def _emo_has_neutral(self):
        info = self._cur_info()
        return bool(info.get("path")) and os.path.exists(info.get("path") or "")

    def _emo_record(self, idx):
        """Запись эмоции с микрофона — в тот же слот голоса."""
        if not self._emo_has_neutral():
            messagebox.showinfo(_tr("Внимание"),
                                _tr("Сначала запишите нейтральный образец голоса."),
                                parent=self)
            return
        info = self._cur_info()
        row = self._emo_rows[idx]
        pre = (row["ent"].get() or "").strip() or row["label"] or ""
        VoiceRecorderDialog(self, self._emotion_saved, self.slot_id, pre or None,
                            self.existing, emotion_mode=True,
                            voice_label=info.get("name") or "",
                            initial_text=self._emo_sample_text(pre, lang=self._sample_lang()))

    def _emotion_saved(self, path, text, slot_id, label):
        """Микрофонная запись эмоции: сначала persist в настройки голоса, потом колонка.
        Без _apply_emotion_voice запись уходила в файл, но в слот не попадала (баг 06.11.26)."""
        if self.app:
            try:
                self.app._apply_emotion_voice(path, text, slot_id, label)
            except Exception:
                pass
            self.existing = self.app.custom_voices
        row = next((r for r in self._emo_rows if (r["ent"].get() or "").strip() == label), None)
        if row is None:      # новой эмоции может и не быть в списке строк — берём первую пустую
            row = next((r for r in self._emo_rows if not (r["ent"].get() or "").strip()), None)
        if row is not None:
            row["ent"].delete(0, "end")
            row["ent"].insert(0, label)
        self._rows_visibility()
        self._refresh_emotions()

    def _emo_synth(self, idx):
        row = self._emo_rows[idx]
        label = (row["ent"].get() or "").strip()
        if not label:
            messagebox.showinfo(_tr("Внимание"),
                                _tr("Сначала выберите голос и впишите название эмоции."),
                                parent=self)
            return
        if self.app is None:
            return
        if not self._emo_has_neutral():
            messagebox.showinfo(
                _tr("Внимание"),
                _tr("Нейтральный образец не записан — не из чего синтезировать эмоцию."),
                parent=self)
            return
        self.app.emotion_synth(self.slot_id, label)

    def _emo_delete(self, idx):
        row = self._emo_rows[idx]
        label = (row["ent"].get() or "").strip()
        if not label or self.app is None:
            return
        if not messagebox.askyesno(_tr("Удалить"),
                                   _tr("Удалить") + f" «{label}»? "
                                   + _tr("Образец эмоции будет стёрт с диска."), parent=self):
            return
        self.app.delete_emotion(self.slot_id, label)
        self._refresh_emotions()


    # ---------- слоты и образец ----------

    @staticmethod
    def _duration(path):
        try:
            with wave.open(path) as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return 0.0

    @staticmethod
    def _short_name(name, keep=46):
        """Имя файла для подписи: у длинных режем середину, иначе карточка растягивает окно
        и кнопки «▶» / «Отмена» уезжают за его край."""
        name = name or ""
        if len(name) <= keep:
            return name
        stem, ext = os.path.splitext(name)
        if len(ext) > 8:
            ext = ext[:8]
        room = max(12, keep - len(ext) - 1)
        head, tail = (room + 1) // 2, room // 2
        return f"{stem[:head]}…{stem[-tail:]}{ext}"

    def _load_slot(self):
        self._stop_recording()
        self.audio_int16 = None
        self.selected_path = None
        self._loaded_path = None

        info = self.existing.get(self.slot_id) or {}
        path = None if self.emotion_mode else info.get("path")

        if path and os.path.exists(path):
            self._loaded_path = path
            self.lbl_sample.configure(
                text=f"Текущий образец: {self._short_name(os.path.basename(path))} · {self._duration(path):.1f} с",
                text_color=COLOR_TEXT_MAIN)
        elif path:
            self.lbl_sample.configure(
                text=_tr(f"Файл не найден: {self._short_name(os.path.basename(path))}"), text_color=COLOR_RED)
        else:
            self.lbl_sample.configure(text=_tr("Образец ещё не записан"), text_color=COLOR_TEXT_SEC)

        self.entry_text.delete("1.0", "end")
        self.entry_text.insert("1.0", self._sample_hint() if self.emotion_mode
                             else (info.get("text") or _tr(self.DEFAULT_TEXT)))
        self.btn_rec.configure(text=_tr("●  Начать запись"))
        self.lbl_rec_time.configure(text=_tr("Нажмите и говорите 5–15 секунд"))

    # ---------- запись ----------

    def toggle_recording(self):
        if not SD_AVAILABLE:
            messagebox.showerror("Микрофон", "Запись недоступна.\nУстановите: pip install sounddevice", parent=self)
            return
        self._stop_sample_play()      # новая запись — прежнее прослушивание ни к чему
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
            self.lbl_sample.configure(
                text=_tr(f"Файл: {self._short_name(os.path.basename(path))} · {self._duration(path):.1f} с"),
                text_color=COLOR_TEXT_MAIN)

    def play_sample(self):
        """Прослушать образец: запись с микрофона (ещё не сохранена — в памяти)
        или файл. Повторное нажатие ⏹ останавливает (Ярослав, 06.11.26)."""
        if getattr(self, "_sample_playing", False):
            self._stop_sample_play()
            return
        if self.audio_int16 is not None:
            if SD_AVAILABLE:
                threading.Thread(target=self._play_worker,
                                 args=(self.audio_int16, self.rec_fs),
                                 daemon=True).start()
                self._sample_playing = True
                try:
                    self.btn_play_sample.configure(text="⏹")
                except Exception:
                    pass
                return
            # нет sounddevice — пишем временный wav и открываем системный плеер
            try:
                tmp = os.path.join(BASE_DIR, "preview_sample_tmp.wav")
                with wave.open(tmp, "wb") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(self.rec_fs)
                    f.writeframes(self.audio_int16.tobytes())
                os.startfile(tmp)
            except Exception as e:
                messagebox.showerror("Звук", str(e), parent=self)
            return
        path = self.selected_path or self._loaded_path
        if not path or not os.path.exists(path):
            messagebox.showinfo("Образец", "Сначала запишите голос или выберите файл.", parent=self)
            return
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("Звук", str(e), parent=self)

    def _play_worker(self, data, fs):
        try:
            sd.play(data, samplerate=fs, blocking=True)
        except Exception:
            pass
        try:
            self.after(0, self._sample_done)
        except Exception:
            pass

    def _sample_done(self):
        self._sample_playing = False
        try:
            if self.winfo_exists():
                self.btn_play_sample.configure(text="▶")
        except Exception:
            pass

    def _stop_sample_play(self):
        if not getattr(self, "_sample_playing", False):
            return
        self._sample_playing = False
        try:
            sd.stop()
        except Exception:
            pass
        self._sample_done()

    def destroy(self):
        # закрыть окно — заглушить незавершённое прослушивание записи
        try:
            self._stop_sample_play()
        except Exception:
            pass
        super().destroy()

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
        _style_tk_menu(menu)
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
            messagebox.showwarning("Внимание",
                                   "Введите название эмоции." if self.emotion_mode
                                   else "Введите название голоса.", parent=self)
            return

        if self.selected_path:
            final_path = self.selected_path
        elif self.audio_int16 is not None:
            secs = len(self.audio_int16) / self.rec_fs
            if secs < 2:
                messagebox.showwarning("Внимание", "Запись слишком короткая — нужно 5–15 секунд речи.", parent=self)
                return
            fn = (self._emotion_filename(self.slot_id, name) if self.emotion_mode
                  else f"my_voice_{self.slot_id}.wav")
            final_path = os.path.join(BASE_DIR, fn)
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

        eng = self.engine_toggle.get() if getattr(self, "engine_toggle", None) is not None else None
        if eng is not None:
            self.on_save(final_path, text, self.slot_id, name, eng)
        else:
            self.on_save(final_path, text, self.slot_id, name)
        self.destroy()


class _SubCancelled(Exception):
    """Пользователь отменил выбор дорожки субтитров."""


class PdfArticlesDialog(ctk.CTkToplevel):
    def __init__(self, parent, articles, on_pick, win_title=None, count_text=None):
        super().__init__(parent)
        self.title(win_title or "Статьи в журнале")
        self.geometry("600x540")
        _center_on_parent(self)
        self.transient(parent)
        self.grab_set()
        self.after(0, lambda: _apply_lang(self))
        _apply_dialog_icon(self)                       # сразу, чтобы не мигал системный
        self.after(150, lambda: _apply_dialog_icon(self))
        self.configure(fg_color=COLOR_BG)

        body = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=R_PANEL,
                            border_width=1, border_color=COLOR_BORDER)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text=count_text or f"Найдено статей: {len(articles)}", font=(FONT_FAMILY, 16, "bold"),
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
        _center_on_parent(self)
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
                                             selectforeground="#2b231c")
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
                                                selectforeground="#2b231c")
        except Exception:
            pass

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(btns, text="Сохранить", height=32, corner_radius=3, font=FONT_NORMAL,
                      fg_color=COLOR_TEXT_MAIN, hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_ON_ACCENT,
                      command=self._save).pack(side="right", fill="x", expand=True, padx=(6, 0))
        ctk.CTkButton(btns, text="Отмена", height=32, corner_radius=3, font=FONT_NORMAL,
                      fg_color=COLOR_CARD2, hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                      border_width=1, border_color=COLOR_BORDER,
                      command=self.destroy).pack(side="right", fill="x", expand=True, padx=(6, 0))
        if on_delete:
            ctk.CTkButton(btns, text="Удалить", height=32, corner_radius=3, font=FONT_NORMAL,
                          fg_color=COLOR_CARD2, hover_color="#ecd6c8", text_color="#7d3418",
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

_PAIRS = [('ИСТОЧНИК', 'SOURCE'), ('МОДЕЛЬ ИИ', 'AI MODEL'), ('ОЗВУЧКА', 'VOICE'),
          ('ВР', 'VRAM'), ('ОЗУ', 'RAM'), ('нет', 'n/a'),
    ('Видеопамять занята', 'Video memory in use'),
    ('Видеопамять почти вся занята другой программой.', 'Video memory is almost entirely held by another program.'),
    ('Свободно', 'Free'), ('нужно', 'needed'),
    ('Если загрузить сейчас, видеокарта начнёт делить память между программами: загрузка и озвучка будут очень долгими, а чужое приложение будет тормозить.',
     'If you load now, the GPU starts splitting memory between programs: loading and speech become very slow, and the other app stalls.'),
    ('Закрой то, что держит видеокарту (LM Studio, ComfyUI, серверы моделей), или выбери движок Piper.',
     'Close whatever holds the GPU (LM Studio, ComfyUI, model servers), or pick the Piper engine.'),
    ('Всё равно попробовать загрузить?', 'Try loading anyway?'),
    ('Vox не загружен: мало видеопамяти', 'Vox not loaded: not enough video memory'),
    ('Не удалось загрузить VoxCPM2: видеокарту держит другое приложение (CUDA out of memory). Освободи видеопамять и попробуй снова.',
     'Failed to load VoxCPM2: the graphics card is held by another app (CUDA out of memory). Free video memory and try again.'), ('Ссылка на статью', 'Article link'), ('Вставьте ссылку на статью или видео, текст или файл — либо наберите текст в поле справа.', 'Paste an article or video link, text or file — or type in the field on the right.'), ('Вставьте ссылку на статью или видео, текст или файл — или просто печатайте здесь.\n\n', 'Paste an article or video link, text or file — or just type here.\n\n'), ('Вставьте текст или ссылку', 'Paste text or a link'), ('Выберите, что вставить в поле текста', 'Choose what to insert into the text field'), ('Вставить', 'Paste'), ('Копировать', 'Copy'), ('Вырезать', 'Cut'), ('Выделить всё', 'Select all'), ('Другая модель', 'Another model'), ('Новый…', 'New…'), ('Удалить', 'Delete'), ('Контекст', 'Context'), ('Сжатие', 'Compression'), ('Скорость', 'Speed'), ('Запустить анализ', 'Run analysis'), ('Остановить', 'Stop'), ('Очистить', 'Clear'), ('Готово', 'Ready'), ('Сохранить', 'Save'), ('Отмена', 'Cancel'), ('Файл', 'File'), ('Промпт — что сделать с текстом', 'Prompt — what to do with the text'), ('Свой уровень сжатия', 'Custom compression level'), ('Сжатие до, % исходного текста', 'Compress to, % of the original text'), ('Название голоса', 'Voice name'), ('Название в списке', 'Name in the list'), ('Например: Мой голос', 'For example: My voice'), ('5–15 секунд чистой речи. Образец и текст сохраняются в слоте.', '5–15 seconds of clean speech. The sample and its text are saved in the slot.'), ('Нажмите и говорите 5–15 секунд', 'Press and speak for 5–15 seconds'), ('Образец ещё не записан', 'No sample recorded yet'), ('Образец голоса', 'Voice sample'), ('Текст образца — что именно произнесено', 'Sample text — what exactly is spoken'), ('Озвучивать сразу после анализа', 'Speak right after the analysis'), ('Добавить эмоции', 'Add emotions'), ('🎙  Образец голоса', '🎙  Voice sample'), ('📂  Свой голос Piper…', '📂  Your Piper voice…'), ('Импорт голоса Piper', 'Import Piper voice'), ('Модель Piper (.onnx)', 'Piper model (.onnx)'), ('Все файлы', 'All files'), ('●  Начать запись', '●  Start recording'), ('■  Остановить запись', '■  Stop recording'),        ('Озвучить', 'Speak'), ('■  Стоп', '■  Stop'), ('Пауза', 'Paused'), ('↩ Исходный текст', '↩ Original text'), ('Процессор', 'CPU'), ('Видеокарта', 'GPU'), ('Piper: процессор, видеокарта не нужна', 'Piper: CPU, no graphics card needed'), ('⚠ Vox требует видеокарту с 8 ГБ видеопамяти', '⚠ Vox needs a graphics card with 8 GB of video memory'), ('ОЗУ: —', 'RAM: —'), ('✅ Готово. Вставьте ссылку на статью или видео, текст или файл.', '✅ Ready. Paste an article or video link, text or file.'), ('✅ Ссылка вставлена', '✅ Link inserted'), ('↩ Возвращён исходный текст', '↩ Original text restored'), ('Обработка…', 'Processing…'), ('Генерация текста…', 'Generating text…'), ('Воспроизведение…', 'Playing…'), ('Остановлено', 'Stopped'), ('Отменено', 'Cancelled'), ('Ошибка звука', 'Audio error'), ('⏳ Синтез...', '⏳ Synthesizing...'), ('❌ Ошибка', '❌ Error'), ('Загрузка статьи…', 'Loading the article…'), ('Анализ вашего текста…', 'Analyzing your text…'), ('Анализ нейросетью…', 'Neural analysis…'), ('Загрузка модели', 'Loading the model'), ('Загрузка на GPU', 'Loading to GPU'), ('Загрузка модели на видеокарту…', 'Loading the model onto the GPU…'), ('Загрузка модели на видеокарту', 'Loading the model onto the GPU'), ('Модель загружена', 'Model loaded'), ('Анализ завершён', 'Analysis finished'), ('Синтез завершён', 'Synthesis finished'), ('Модель GGUF', 'GGUF model'), ('Модель на GPU', 'Model on GPU'), ('Модель ИИ не загружена.', 'The AI model is not loaded.'), ('Модель для анализа не выбрана.', 'No analysis model selected.'), ('Выбрана модель. Загрузится при анализе.', 'Model selected. It loads when the analysis starts.'), ('Сканирование моделей…', 'Scanning models…'), ('Подготовка текста', 'Preparing the text'), ('Проверка объёма', 'Checking the length'), ('⏳ Загрузка VoxCPM2...', '⏳ Loading VoxCPM2...'), ('⏳ Загрузка VoxCPM2 (веса ~5 ГБ)...', '⏳ Loading VoxCPM2 (~5 GB of weights)...'), ('⏳ Подготовка текста…', '⏳ Preparing the text…'), ('⏹ Анализ отменён', '⏹ Analysis cancelled'), ('⏹ Синтез отменён', '⏹ Synthesis cancelled'), ('⏹ Остановлено', '⏹ Stopped'), ('♻️ Модель уже в памяти — переиспользую', '♻️ The model is already in memory — reusing it'), ('✅ VoxCPM2 готова (GPU)', '✅ VoxCPM2 ready (GPU)'), ('❌ VoxCPM2 недоступна', '❌ VoxCPM2 unavailable'), ('❌ Ошибка загрузки', '❌ Loading error'), ('❌ Файл голоса не найден', '❌ Voice file not found'), ('🧹 Видеопамять освобождена после анализа', '🧹 Video memory freed after the analysis'), ('🚀 GPU-сервер:', '🚀 GPU server:'), ('Режим: видеокарта (CUDA)', 'Mode: GPU (CUDA)'), ('Режим: процессор (CUDA выключена)', 'Mode: CPU (CUDA off)'), ('Движок: VoxCPM2 (GPU).', 'Engine: VoxCPM2 (GPU).'), ('Не выбран голос для озвучки: запишите образец «🎙 Образец голоса».', 'No voice selected for speech: record a sample with “🎙 Voice sample”.'), ('Воспроизведение недоступно.', 'Playback is unavailable.'), ('Запись невозможна.', 'Recording is unavailable.'), ('Внимание', 'Warning'), ('Ошибка TTS', 'TTS error'), ('Ошибка VoxCPM2', 'VoxCPM2 error'), ('Микрофон', 'Microphone'), ('Звук', 'Audio'), ('Буфер обмена', 'Clipboard'), ('Образец', 'Sample'), ('Анализ', 'Analysis'), ('Слишком длинный текст', 'Text too long'), ('WAV-файл (5–15 секунд чистой речи)', 'WAV file (5–15 seconds of clean speech)'), ('Выберите модель .gguf для анализа текста', 'Choose a .gguf model for text analysis'), ('Выберите файл (pdf, docx, epub, fb2, rtf, html, txt, md)', 'Choose a file (pdf, docx, epub, fb2, rtf, html, txt, md)'), ('Нечего анализировать', 'Nothing to analyze'), ('Текст слишком короткий или пустой', 'The text is too short or empty'), ('Буфер обмена пуст', 'The clipboard is empty'), ('Буфер пуст. Скопируйте текст для озвучки.', 'The clipboard is empty. Copy the text you want spoken.'), ('Нет текста для озвучки.', 'There is no text to speak.'), ('Голос не выбран.', 'No voice is selected.'), ('Сначала запишите голос или выберите файл.', 'Record a voice first or choose a file.'), ('Введите название голоса.', 'Enter the voice name.'), ('Введите название.', 'Enter a name.'), ('Введите текст образца.', 'Enter the sample text.'), ('Введите новый процент сжатия.', 'Enter the new compression percentage.'), ('Напишите промпт — что сделать с текстом.', 'Write a prompt — what to do with the text.'), ('Процент должен быть от 5 до 100.', 'The percentage must be from 5 to 100.'), ('Укажите процент числом, например 40.', 'Write the percentage as a number, for example 40.'), ('Выберите модель ИИ в карточке «МОДЕЛЬ ИИ»', 'Choose an AI model in the “AI MODEL” card'), ('Запись слишком короткая — нужно 5–15 секунд речи.', 'The recording is too short — 5–15 seconds of speech are needed.'), ('Запишите голос с микрофона\nили выберите WAV-файл.', 'Record a voice with the microphone\nor choose a WAV file.'), ('Запишите голос: «🎙 Образец голоса»', 'Record a voice: “🎙 Voice sample”'), ('Запись недоступна.\nУстановите: pip install sounddevice', 'Recording is unavailable.\nInstall: pip install sounddevice'), ('Старый формат .doc не поддерживается.\nСохраните документ как .docx.', 'The old .doc format is not supported.\nSave the document as .docx.'), ('Установите: pip install pypdf', 'Install: pip install pypdf'), ('Установите: pip install python-docx', 'Install: pip install python-docx'), ('В файле не найден текст (возможно, скан без текстового слоя).', 'No text found in the file (possibly a scan without a text layer).'), ('Нужен файл модели в формате .gguf', 'A model file in .gguf format is required'), ('Удалить этот уровень сжатия?', 'Delete this compression level?'), ('Нужен текст: вставьте ссылку на статью или видео, текст или файл.', 'Text is required: paste an article or video link, text or file.'), ('Хорошо', 'OK'), ('Голос Алсу установлен', 'Alsu voice installed'), ('Встроенный голос добавлен', 'Built-in voice added'), ('Озвучка сохранена', 'Spoken audio saved'), ('Нет озвучки для сохранения — сначала нажмите «Озвучить».', 'Nothing to save yet — press “Speak” first.'), ('Сохранить озвучку', 'Save spoken audio'), ('⏳ Синтез речи…', '⏳ Synthesizing speech…'),
('Ссылка на статью или видео (YouTube, Rutube, VK)', 'Article or video link (YouTube, Rutube, VK)'),
('⏳ Загрузка субтитров видео…', '⏳ Loading video subtitles…'),
('Видео', 'Video'),
('Субтитры — выберите язык', 'Subtitles — choose a language'),
('Субтитры пустые или слишком короткие — озвучивать нечего.',
 'Subtitles are empty or too short — nothing to speak.'),
('YouTube не отдал субтитры: у видео их нет, оно приватное или с возрастным ограничением.',
 'YouTube returned no subtitles: the video has none, is private or age-restricted.'),
('У этого видео на YouTube нет субтитров.', 'This YouTube video has no subtitles.'),
('Не найден модуль youtube-transcript-api. Установите: pip install youtube-transcript-api',
 'The youtube-transcript-api module is missing. Install: pip install youtube-transcript-api'),
('На Rutube у этого видео нет субтитров — Rutube почти не отдаёт субтитры. Попробуйте ссылку на этот же ролик с YouTube.',
 'This Rutube video has no subtitles — Rutube rarely provides them. Try the same clip on YouTube.'),
('Rutube: видео не найдено или недоступно.', 'Rutube: video not found or unavailable.'),
('Rutube: сервис недоступен.', 'Rutube: service unavailable.'),
('Для ВК нужен модуль yt-dlp. Установите: pip install yt-dlp',
 'VK needs the yt-dlp module. Install: pip install yt-dlp'),
('ВК: не удалось получить данные видео — ссылка неверная, ролик приватный или сервис недоступен.',
 'VK: could not fetch the video — bad link, private video, or the service is down.'),
('На ВК у этого видео нет доступных субтитров. Попробуйте ссылку на этот же ролик с YouTube.',
 'This VK video has no available subtitles. Try the same clip on YouTube.'),
('ВК: не удалось скачать файл субтитров.', 'VK: could not download the subtitle file.')]

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
    ("Главы книги", "Book chapters"),
    ("📖 Вся книга целиком", "📖 The whole book"),
    ("Найдено глав: 3", "Chapters found: 3"),
    ("В файле EPUB не найдено текста глав.", "No chapter text found in the EPUB file."),
    ("Файл EPUB повреждён: не читается ZIP-контейнер.", "The EPUB file is damaged: the ZIP container cannot be opened."),
    ("Файл EPUB повреждён: не найден контейнер.", "The EPUB file is damaged: container not found."),
    ("Файл EPUB повреждён: ошибка разбора OPF.", "The EPUB file is damaged: error parsing OPF."),
    ("В файле FB2 не найдено текста глав.", "No chapter text found in the FB2 file."),
    ("Файл FB2 повреждён: ошибка разбора XML.", "The FB2 file is damaged: XML parsing error."),
]

# —— названия уровней сжатия, слоты голосов, пример текста образца ——
_PAIRS += [
    ("Только суть (10%)", "Main point only (10%)"),
    ("Очень кратко (30%)", "Very short (30%)"),
    ("Кратко (50%)", "Short (50%)"),
    ("Подробно (80%)", "Detailed (80%)"),
    ("Речь для озвучки (100%)", "Speech for narration (100%)"),
    ("Перевод на английский (100%)", "Translate into English (100%)"),
    ("Без изменений", "Leave unchanged"),
    ("✅ Текст без изменений — нейросеть не вызывалась",
     "✅ Text left unchanged — the neural network was not called"),
    ("без изменений", "unchanged"),
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
    ("Вставьте ссылку на статью или видео, текст или файл — или просто печатайте здесь.\n\n"
     "Ctrl+V — вставить из буфера. Всё, что есть в этом поле, считается источником:\n"
     "анализ пойдёт по нему, а не по ссылке.",
     "Paste an article or video link, text or file — or just type here.\n\n"
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
    ("🗑 Удалить голос", "🗑 Delete voice"),
    ("Удалить голос", "Delete voice"),
    ("Голос удалён", "Voice deleted"),
    ("(образец-файл тоже удалён)", "(sample file deleted too)"),
    # ---- эмоции образцов голоса ----
    ("Эмоция голоса", "Voice emotion"),
    ("Название эмоции", "Emotion name"),
    ("Например: радостный", "e.g. cheerful"),
    ("5–15 секунд чистой речи. Образец добавится к голосу.", "5–15 seconds of clean speech. The sample is added to the voice."),
    ("Введите название эмоции.", "Enter the emotion name."),
    ("Сначала выберите голос, к которому добавить эмоцию.", "Select a voice first to add an emotion to."),
    ("Сначала запишите нейтральный образец голоса.", "Record the neutral voice sample first."),
    # ---- колонка эмоций в окне «Образец голоса» ----
    ("Эмоции синтезирует движок Vox — переключитесь на него.", "Emotions are synthesized by the Vox engine — switch to it."),
    ("Не знаю такую эмоцию. Напиши: радостный, грустный, злой…", "Unknown emotion. Try: joyful, sad, angry…"),
    ("Эмоция не синтезирована", "Emotion not synthesized"),
    ("Сначала выберите голос и впишите название эмоции.", "Choose the voice first and type an emotion name."),
    ("Нейтральный образец не записан — не из чего синтезировать эмоцию.", "No neutral sample recorded — nothing to synthesize an emotion from."),
    ("Запись с микрофона в этот же голос.", "Microphone recording into the same voice."),
    ("Нейросинтез эмоции из нейтрального образца этого голоса.", "Neural synthesis of the emotion from this voice's neutral sample."),
    ("Сколько угодно эмоций — новая строка появляется сама.", "Any number of emotions — a new row appears by itself."),
    ("не записана", "not recorded"),
    ("удалена", "deleted"),
    ("Маркер в тексте: (радостный) фраза.\nБез маркера — нейтральный голос. Запиши или синтезируй.", "Marker in text: (joyful) phrase.\nWithout a marker — neutral voice. Record or synthesize."),
    ("Эмоции голоса", "Voice emotions"),
    ("Эмоции", "Emotions"),
    ("Записать эмоцию нейросинтезом из нейтрального образца.",
     "Synthesize an emotion sample from the neutral sample."),
    ("Синтезировать", "Synthesize"),
    ("Записать", "Record"),
    ("название эмоции (например: радостный)", "emotion name (e.g. cheerful)"),
    ("не задана", "not set"),
    ("записана", "recorded"),
    ("синтезирована", "synthesized"),
    ("Синтез идёт — подожди.", "Synthesis is running — wait."),
    ("Синтез эмоции доступен для движка Vox.", "Emotion synthesis works with the Vox engine."),
    ("Название эмоции не в словаре. Опиши эмоцию по-английски для нейросети\n(например: very cheerful tone):",
     "The emotion name is unknown. Describe the emotion in English for the model\n(e.g. very cheerful tone):"),
    ("Описание эмоции", "Emotion description"),
    ("Удалить эмоцию", "Delete the emotion"),
    ("Синтез эмоции...", "Synthesizing emotion..."),
    ("VoxCPM2 недоступна", "VoxCPM2 is unavailable"),
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
    ("Свой Piper (.onnx)…", "Your Piper voice (.onnx)…"),
    ("Импорт голоса Piper", "Import Piper voice"),
    ("Модель Piper (.onnx)", "Piper model (.onnx)"),
    ("Для импорта голоса нужны два файла рядом: name.onnx и name.onnx.json — стандартный набор Piper.",
     "To import a voice you need two files side by side: name.onnx and name.onnx.json — the standard Piper set."),
    ("Конфиг голоса повреждён", "Voice config is corrupt"),
    ("Голос импортирован", "Voice imported"),
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
TR_RU_EN.update({
    "Qwen (GPU)": "Qwen (GPU)",
    "⚠ Qwen требует видеокарту с 6 ГБ видеопамяти": "⚠ Qwen requires a GPU with 6 GB of VRAM",
    "✨ Дизайн голоса": "✨ Design voice",
    "⚙ Настройки Qwen": "⚙ Qwen settings",
    "Дизайн голоса": "Voice design",
    "Настройки Qwen3-TTS": "Qwen3-TTS settings",
    "Движок Qwen": "Qwen engine",
    "Пакет qwen-tts не установлен — движок Qwen недоступен.":
        "The qwen-tts package is not installed — the Qwen engine is unavailable.",
    "Пакет qwen-tts не установлен.": "The qwen-tts package is not installed.",
    "GPU-среда для Qwen (≈2,5 ГБ)…": "GPU environment for Qwen (≈2.5 GB)…",
    "GPU-среда не установлена: ": "GPU environment not installed: ",
    "Пакет Qwen3-TTS (≈30 МБ)…": "Qwen3-TTS package (≈30 MB)…",
    "Пакет Qwen3-TTS": "Qwen3-TTS package",
    "Пакет qwen-tts не установлен: ": "The qwen-tts package failed to install: ",
    "Пакет qwen-tts не установлен. Скачать и установить его? (≈30 МБ)":
        "The qwen-tts package is not installed. Download and install it? (≈30 MB)",
    "✅ Пакет Qwen3-TTS установлен.": "✅ The Qwen3-TTS package is installed.",
    "Пакет qwen-tts не установлен — движок Qwen недоступен. Сначала нужна GPU-среда (движок Vox или первичная установка).":
        "The qwen-tts package is not installed — the Qwen engine is unavailable. "
        "First install the GPU environment (Vox engine or first-run setup).",
    "GPU-среда не установлена — сначала нужен движок Vox.":
        "The GPU environment is not installed — install the Vox engine first.",
    "Qwen3-TTS: модели на месте.": "Qwen3-TTS: models are in place.",
    "Qwen3-TTS: модели не скачаны — докачает при озвучке.":
        "Qwen3-TTS models are not downloaded — they will download when voicing.",
    "✅ Модели Qwen3-TTS скачаны.": "✅ Qwen3-TTS models downloaded.",
    "Заполни описание голоса и текст.": "Fill in the voice description and the text.",
    "Модель дала тишину — переформулируй описание.":
        "The model produced silence — rephrase the description.",
    "Готово — слушаю. Нравится — жми «Сохранить».":
        "Done — playing. If you like it, press “Save”.",
    "Сначала прослушай вариант.": "Listen to a take first.",
    "✅ Голос сохранён в списке — работает как клон.":
        "✅ Voice saved in the list — it works like a clone.",
    "Генерирую голос…": "Generating the voice…",
    "Опиши голос словами — модель его создаст.\n"
    "Например: «молодой энергичный мужчина, быстрая речь, с улыбкой»":
        "Describe the voice in words — the model will create it.\n"
        "Example: \"a young energetic man, fast speech, smiling\".",
    "Текст прослушки": "Preview text",
    "Имя голоса в списке": "Voice name in the list",
    "🔊 Сгенерировать и послушать": "🔊 Generate and listen",
    "💾 Сохранить": "💾 Save",
    "Закрыть": "Close",
    "Устройство": "Device",
    "Точность": "Precision",
    "Язык": "Language",
    "Фиксированное зерно": "Fixed seed",
    "Зерно (0 — каждый дуб новый)": "Seed (0 — new seed for every take)",
    "Максимум токенов на фразу": "Max tokens per phrase",
    "Освобождать память после озвучки": "Free memory after voicing",
    "✅ Настройки Qwen сохранены.": "✅ Qwen settings saved.",
    "📥 Скачать модели Qwen": "📥 Download Qwen models",
    "Освободить память GPU": "Free GPU memory",
})
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
    ("Нужна CUDA-сборка llama.cpp", "The CUDA build of llama.cpp is required"),
    ("llama.cpp для видеокарт NVIDIA, ≈630 МБ — докачивается автоматически и только один раз.\n"
     "Можно отменить: тогда режим вернётся на процессор.",
     "llama.cpp for NVIDIA graphics cards, ≈630 MB — downloaded automatically, only once.\n"
     "You may cancel: the mode then returns to the processor."),
    ("Сборка не скачана", "The build is not downloaded"),
    ("Распаковка…", "Extracting…"),
    ("CUDA-сборка установлена", "The CUDA build is installed"),
    ("Сборка не найдена после распаковки", "The build was not found after extraction"),
    ("Gemma 4 E4B и сборка для видеокарты NVIDIA, ≈5,6 ГБ — скачиваются один раз "
     "(Hugging Face и GitHub).\nДальше приложение работает без интернета. "
     "Если прервать, докачается с места.",
     "Gemma 4 E4B plus the NVIDIA GPU build, ≈5.6 GB — downloaded once "
     "(Hugging Face and GitHub).\nAfter that the app works offline. "
     "If interrupted, it resumes where it stopped."),
    ("Видеокарта · ", "GPU · "),
    ("Модель скачана — докачиваю сборку видеокарты…",
     "Model downloaded — fetching the GPU build…"),
    ("Модель и сборка для видеокарты установлены", "The model and the GPU build are installed"),
    ("Сборка видеокарты не докачана — приложение докачает её при включении GPU",
     "The GPU build is incomplete — the app will fetch it when the GPU mode is switched on"),
    ("Видеокарта", "Video card"),
    ("Для режима «Видеокарта» нужна видеокарта NVIDIA — она не найдена.\n"
     "Режим возвращён на процессор.",
     "The “Video card” mode requires an NVIDIA graphics card — none was found.\n"
     "The mode has been returned to the processor."),
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
        if isinstance(w, ctk.CTkTextbox) and not getattr(w, "_no_auto_tr", False):
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


try:                            # drag&drop документов с рабочего стола (tkdnd)
    from tkinterdnd2 import TkinterDnD, DND_FILES
    # DnDWrapper обязан быть ДО CTk в базовых классах: иначе его __init__
    # не вызывается в MRO и tkdnd не инициализируется (TkdndVersion = None)
    _APP_BASE = (TkinterDnD.DnDWrapper, ctk.CTk)
    _DND_OK = True
except Exception:               # tkinterdnd2 нет — окно обычное, DnD просто молчит
    _APP_BASE = (ctk.CTk,)
    _DND_OK = False


class ModernTTSApp(*_APP_BASE):
    REF_TEXT = "Привет! Это образец голоса для синтеза речи."
    ENGINE_VALUES = ["Piper (CPU)", "Vox (GPU)", "Qwen (GPU)"]
    SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
    PLACEHOLDER = ("Вставьте ссылку на статью или видео, текст — или перетащите сюда файл "
                   "(pdf, docx, epub, fb2, txt...).\n\n"
                   "Ctrl+V — вставить из буфера. Всё, что есть в этом поле, считается источником:\n"
                   "анализ пойдёт по нему, а не по ссылке.")
    PLACEHOLDER_EN = ("Paste an article or video link, text or file — or just type here.\n\n"
                      "Ctrl+V — paste from the clipboard. Whatever is in this box is the source:\n"
                      "the analysis uses it, not the link.")
    # «Без изменений»: текст идёт в озвучку дословно. Нейросеть к нему подключается
    # только ради постановки эмоций — тогда она не трогает текст, а лишь ставит маркеры.
    NO_PROCESS = "Без изменений"
    PRESET_VALUES = ["Только суть (10%)", "Очень кратко (30%)", "Кратко (50%)", "Подробно (80%)",
                     "Речь для озвучки (100%)", "Перевод на английский (100%)", NO_PROCESS]
    # Доля исходного объёма для каждого пресета (жёсткий лимит в знаках)
    PRESET_RATIOS = {
        "Только суть (10%)": 0.10,
        "Очень кратко (30%)": 0.30,
        "Кратко (50%)": 0.50,
        "Подробно (80%)": 0.80,
    }
    PRESET_PROMPTS_RU = {
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
        NO_PROCESS:
            "Верни этот текст дословно: не пересказывай, не сокращай, не перефразируй, "
            "не меняй порядок и формулировки. Единственная допустимая правка — расставить "
            "маркеры эмоций перед фразами, если это запрошено отдельно. Если разметка "
            "эмоциями не запрошена — верни текст без единой правки.",
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
        NO_PROCESS:
            "Return this text verbatim: do not retell, shorten, rephrase or reorder it, and "
            "do not change its wording. The only edit allowed is placing emotion markers "
            "before phrases, if that is requested separately. If no emotion markup is "
            "requested — return the text without a single change.",
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
        if _DND_OK:
            # в tkinterdnd2 0.4+ миксин DnDWrapper не инициализирует tkdnd сам —
            # грузим tcl-пакет tkdnd вручную (без этого drop_target_register падает)
            try:
                from tkinterdnd2.TkinterDnD import _require
                self.TkdndVersion = _require(self)
            except Exception:
                pass
        self._apply_app_icon()
        self.after(120, self._apply_titlebar_icon)
        self.after(160, lambda: _dwm_titlebar(self))    # бумажная шапка Windows 11

        self.BASE_DIR = BASE_DIR    # в установленной версии — %LOCALAPPDATA%\FAIR
        self.theme = self._load_theme()

        self.title("FAIR")
        self.geometry("1140x850")
        self.minsize(1000, 700)
        self.configure(fg_color=COLOR_BG)
        self._init_fonts()

        self.tts_voice = None
        self.vox_model = None
        self.vox_name = None
        self.current_engine = "Piper"
        self.current_tts_name = None
        # --- Qwen3-TTS (третий движок) ---
        self._qwen_models = {}          # kind -> объект модели (держим в VRAM)
        self._qwen_prompt_cache = {}    # ключ голоса -> готовый промпт клона
        self._qwen_runs = 0
        self._qwen_run_seed = 0
        self.qwen_size = "1.7B"   # размер движка Qwen: "0.6B" (лёгкий) или "1.7B"
        self.qwen_cfg = {
            "device": "auto", "precision": "bf16", "language": "auto",
            "max_new_tokens": 512, "top_p": 0.9, "top_k": 50,
            "temperature": 0.8, "repetition_penalty": 1.1,
            "free_after": False,
        }
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
        self.engine_voices = {}      # последний выбранный голос каждого движка
        self.custom_presets = {}   # {название: {"ratio": 0.4, "prompt": "..."}} — свои уровни сжатия
        self._last_preset = "Кратко (50%)"
        self.box_is_source = False
        self.auto_play_var = ctk.BooleanVar(value=False)
        self.emo_auto_var = ctk.BooleanVar(value=False)   # «Добавить эмоции» (работает на Vox)
        self._emo_pref = False       # что выбрал пользователь, когда движок Vox
        self._emo_markers_on = False
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
        self._analysis_thread = None
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
        elif getattr(self, "setup_preview", False):   # однократное превью мастера в dev-сборке
            def _prev_once():
                self.setup_preview = False
                try:
                    self.save_settings()
                except Exception:
                    pass
                try:
                    self._first_run_setup()
                except Exception:
                    import traceback
                    print("❌ мастер превью:", traceback.format_exc())
            self.after(900, _prev_once)
        self._probe_model(self.llm_combo.get())

        self._show_placeholder()
        self._update_char_count()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---- MCP: локальный HTTP API для Гермеса (мост fair_mcp.py) ----
        self._mcp_busy = False
        self._api_server = None
        self.after(1500, self._start_api_server)

    def _start_api_server(self):
        """Поднимает fair_api: Гермес ходит в приложение по 127.0.0.1 через MCP-мост."""
        try:
            import fair_api
            fair_api.start(self, log=print)
        except Exception as e:
            print(f"⚠️ MCP API не поднят: {e}")

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
        _center_on_parent(dlg)
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
        if self._cuda_wanted():
            mtxt = _tr("Gemma 4 E4B и сборка для видеокарты NVIDIA, ≈5,6 ГБ — скачиваются один раз "
                       "(Hugging Face и GitHub).\nДальше приложение работает без интернета. "
                       "Если прервать, докачается с места.")
        else:
            mtxt = _tr("Gemma 4 E4B, ≈5 ГБ — скачивается один раз с Hugging Face.\n"
                       "Дальше анализ идёт без интернета. Если прервать, докачается с места.")
        ctk.CTkLabel(body, justify="left", wraplength=470, font=FONT_TINY,
                     text_color=COLOR_TEXT_SEC, text=mtxt).pack(padx=16, anchor="w")

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
        """Качает GGUF в models_llm/<имя>.part, затем — сборку видеокарты (пакетом, один раз)."""
        pack = self.MODEL_PACK
        folder = os.path.join(self.BASE_DIR, "models_llm")
        os.makedirs(folder, exist_ok=True)
        final = os.path.join(folder, pack["name"])
        part = final + ".part"
        zips = self.LLAMA_CUDA_ZIPS
        cuda_approx = sum(a for _, _, a in zips)
        need_cuda = self._cuda_wanted()

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
            if have < total:
                headers = {"Range": f"bytes={have}-"} if have else {}
                with _http_get(pack["url"], headers=headers, stream=True) as r:
                    r.raise_for_status()
                    if r.status_code == 206:
                        total = have + int(r.headers.get("Content-Length") or 0)
                    else:
                        have = 0
                        total = int(r.headers.get("Content-Length") or pack["size"])
                    done = have
                    grand = total + (cuda_approx if need_cuda else 0)
                    drawn = 0.0
                    ui(set_info, f"{done / 1048576:,.0f} / {grand / 1048576:,.0f} "
                                 + _tr("МБ") + " · 0%")
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
                                pct = (done / grand) if grand else 0
                                ui(bar.set, min(pct, 1.0))
                                ui(set_info, f"{done / 1048576:,.0f} / {grand / 1048576:,.0f} "
                                             + _tr("МБ") + f" · {pct * 100:.0f}%")
            os.replace(part, final)
            if not need_cuda:
                self.after(0, self._model_ready, dlg, "Модель скачана")
                return
            # ---- этап 2: сборка для видеокарты — тот же пакет, тот же прогресс ----
            ui(set_info, _tr("Модель скачана — докачиваю сборку видеокарты…"))
            base0 = os.path.getsize(final)
            grand = base0 + cuda_approx
            drawn = [0.0]

            def cb(i, d, t):
                now = time.time()
                if now - drawn[0] > 0.25 or d >= t:
                    drawn[0] = now
                    acc = base0 + sum(a for _, _, a in zips[:i]) + d
                    pct = (acc / grand) if grand else 0
                    ui(set_info, _tr("Видеокарта · ") + f"{acc / 1048576:,.0f} / "
                                       f"{grand / 1048576:,.0f} " + _tr("МБ") +
                         f" · {min(pct, 1.0) * 100:.0f}%")
                    ui(bar.set, min(pct, 1.0))

            ok_cuda = self._fetch_cuda_pack(cb, self._dl_cancel,
                                            on_extract=lambda: ui(set_info, _tr("Распаковка…")))
            ui(bar.set, 1.0)
            if not ok_cuda:
                if not self._dl_cancel.is_set():
                    raise Exception(_tr("Сборка не найдена после распаковки"))
                # Модель на месте, сборку отложили — докачаем при включении GPU
                self.after(0, self._model_ready, dlg, "Модель скачана")
                return
            self.after(0, self._model_ready,
                       dlg, "Модель и сборка для видеокарты установлены")
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

    # встроенные образцы голосов Vox — лежат в voices_builtin/ (входят в установщик),
    # регистрируются в слотах при первом запуске (_seed_builtin_vox_voices)
    BUILTIN_VOX_VOICES = (
        {"name": "Алсу", "file": "alsu_ref.wav",
         "text": "Привет. Это образец моего голоса для синтеза речи."},
        {"name": "Джон", "file": "john_ref.wav",
         "text": "What is something that recently moved you?"},
    )

    def _seed_builtin_vox_voices(self):
        """Регистрирует встроенные голоса («Алсу», «Джон»).

        Учёт по ИМЕНАМ в seeded_builtin_voices: новый встроенный голос доезжает
        к существующему пользователю при обновлении, а голос, который он удалил
        сам, обратно не возвращается. Старый общий флаг builtin_vox_seeded читается
        как «Алсу уже сеялась» — так настройки прежних версий не ломаются.
        """
        try:
            seeded = [str(n).strip() for n in (getattr(self, "seeded_builtin_voices", None) or [])
                      if str(n).strip()]
            if not seeded and getattr(self, "builtin_vox_seeded", False):
                seeded = ["Алсу"]          # миграция со старого флага
            low = {s.lower() for s in seeded}
            have = {str(i.get("name", "")).strip().lower()
                    for i in self.custom_voices.values() if isinstance(i, dict)}
            added = []
            for v in self.BUILTIN_VOX_VOICES:
                name = v["name"].strip()
                if name.lower() in low:
                    continue
                if name.lower() in have:   # у пользователя уже есть голос с таким именем
                    seeded.append(name)
                    low.add(name.lower())
                    continue
                wav = os.path.join(self._asset_path("voices_builtin"), v["file"])
                if not os.path.isfile(wav):
                    continue
                slot = next(str(k) for k in range(1, 100) if str(k) not in self.custom_voices)
                self.custom_voices[slot] = {"name": name, "path": wav, "text": v["text"]}
                seeded.append(name)
                low.add(name.lower())
                added.append(name)
            self.seeded_builtin_voices = seeded
            self.builtin_vox_seeded = True
            if added:
                self.update_status(f"✅ {_tr('Встроенный голос добавлен')}: {', '.join(added)}")
        except Exception as e:
            print(f"⚠️ Встроенные голоса: {e}")

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
        if not getattr(self, "_setup_offered", False):
            if getattr(self, "setup_done", False):
                pass                              # мастер уже проходили
            elif self.llm_models and all(os.path.isfile(self._voice_file(n))
                                         for n, _ in self.AUTO_VOICES):
                self.setup_done = True            # обновлённая установка: всё на месте
                self.save_settings()
            else:
                self._setup_offered = True
                self._first_run_setup()
                return
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

    def _mark_setup_done(self):
        self.setup_done = True
        self.save_settings()

    def _gpu_summary(self):
        """(имя видеокарты, ГБ видеопамяти) или (None, None)."""
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            nm = pynvml.nvmlDeviceGetName(h)
            if isinstance(nm, bytes):
                nm = nm.decode("utf-8", "replace")
            total = pynvml.nvmlDeviceGetMemoryInfo(h).total / 1024 ** 3
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            return (str(nm).strip() or None, total)
        except Exception:
            return None, None

    def _first_run_setup(self):
        """Первичная установка: одно окно на три строки — модель анализа (обязательно),
        Vox (галочка), Qwen3-TTS (выбор размера движка). Видеокарта показана сразу."""
        old = getattr(self, "_setup_dialog", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except Exception:
            pass
        gname, gvram = self._gpu_summary()
        print(f"🧭 мастер: окно, gpu={gname!r} vram={gvram}")
        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Первичная установка"))
        dlg.geometry("640x430")
        _center_on_parent(dlg)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        dlg.after(150, lambda: _apply_dialog_icon(dlg))
        self._setup_dialog = dlg
        self._setup_cancel = threading.Event()

        def _after_close(event=None):
            if event is None or getattr(event, "widget", None) is dlg:
                self.after(400, self._first_run_chain)
        dlg.bind("<Destroy>", _after_close)

        body = ctk.CTkFrame(dlg, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(body, text=_tr("Первичная установка FAIR"), font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(10, 3))
        if gname:
            gpu_txt = f"\U0001F5A5 {gname} \u2014 {gvram:.1f} {_tr('ГБ видеопамяти')}"
            gcol = COLOR_GOLD
        else:
            gpu_txt = _tr("Видеокарта не найдена: анализ пойдёт на процессоре, "
                          "голосовые движки Vox и Qwen требуют видеокарту.")
            gcol = COLOR_RED
        ctk.CTkLabel(body, text=gpu_txt, font=FONT_SMALL, text_color=gcol,
                     wraplength=580, justify="left").pack(padx=16, anchor="w", pady=(0, 3))

        r1 = ctk.CTkFrame(body, fg_color=COLOR_CARD, corner_radius=R_CARD)
        r1.pack(fill="x", padx=12, pady=(4, 3))
        done1 = " \u2705" if self.llm_models else ""
        ctk.CTkLabel(r1, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w",
                     justify="left", wraplength=580,
                     text=_tr("1. Модель для анализа Gemma 4 E4B и сборка для "
                              "видеокарты (\u22485,6 ГБ) \u2014 обязательная часть "
                              "программы") + done1
                              ).pack(fill="x", padx=10, pady=3)

        r2 = ctk.CTkFrame(body, fg_color=COLOR_CARD, corner_radius=R_CARD)
        r2.pack(fill="x", padx=12, pady=3)
        self._setup_vox = ctk.BooleanVar(value=bool(gvram and gvram >= 7.5))
        cb2 = ctk.CTkCheckBox(r2, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN,
                              checkbox_width=18, checkbox_height=18, fg_color="#c6763a",
                              hover_color="#a95f2c",
                              text=_tr("2. Голосовой движок VoxCPM2 (\u22484,5 ГБ) \u2014 "
                                       "нужно 8 ГБ видеопамяти"),
                              variable=self._setup_vox)
        cb2.pack(fill="x", padx=10, pady=(4, 1))
        if self._vox_installed():
            cb2.select()
            cb2.configure(state="disabled")
            ctk.CTkLabel(r2, text="   \u2705 " + _tr("уже установлен"), font=FONT_TINY,
                         text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=10, pady=(0, 4))
        elif gvram and gvram < 7.5:
            cb2.deselect()
            ctk.CTkLabel(r2, text="   \u26A0 " + _tr("видеопамяти меньше 8 ГБ \u2014 "
                                                     "Vox может не потянуться, лучше снять галочку"),
                         font=FONT_TINY, text_color=COLOR_RED, anchor="w",
                         wraplength=560, justify="left").pack(fill="x", padx=10, pady=(0, 4))
        elif not gvram:
            cb2.deselect()
            cb2.configure(state="disabled")
            ctk.CTkLabel(r2, text="   \u26A0 " + _tr("нет видеокарты \u2014 Vox недоступен"),
                         font=FONT_TINY, text_color=COLOR_RED, anchor="w"
                         ).pack(fill="x", padx=10, pady=(0, 4))

        r3 = ctk.CTkFrame(body, fg_color=COLOR_CARD, corner_radius=R_CARD)
        r3.pack(fill="x", padx=12, pady=(3, 4))
        ctk.CTkLabel(r3, font=FONT_SMALL, text_color=COLOR_TEXT_MAIN, anchor="w",
                     text=_tr("3. Голосовой движок Qwen3-TTS \u2014 клон голоса по образцу")
                     ).pack(anchor="w", padx=10, pady=(4, 0))
        self._setup_qwen = ctk.StringVar(
            value=("1.7B" if (gvram or 0) >= 5.5 else
                   "0.6B" if (gvram or 0) >= 3.5 else "нет"))
        qr = {}
        _B = (FONT_FAMILY, 10, "bold")
        for val, segs in (("нет", ((_tr("не устанавливать"), False),)),
                          ("0.6B", ((_tr("0.6B \u2014 лёгкий (\u22485 ГБ), "), False),
                                    (_tr("нужно 4 ГБ видеопамяти"), True))),
                          ("1.7B", ((_tr("1.7B \u2014 качество выше (\u224813,5 ГБ), "), False),
                                    (_tr("нужно 6\u20138 ГБ видеопамяти"), True),
                                    (_tr("; «Дизайн голоса» только у 1.7B"), False)))):
            fr = ctk.CTkFrame(r3, fg_color="transparent")
            fr.pack(anchor="w", padx=18, pady=2)
            rb = ctk.CTkRadioButton(fr, text=segs[0][0], variable=self._setup_qwen, value=val,
                                    font=FONT_TINY, text_color=COLOR_TEXT_MAIN,
                                    fg_color="#c6763a", hover_color="#a95f2c",
                                    radiobutton_width=16, radiobutton_height=16)
            rb.pack(side="left")
            for txt, bold in segs[1:]:
                ctk.CTkLabel(fr, text=txt, font=_B if bold else FONT_TINY,
                             text_color=COLOR_TEXT_MAIN).pack(side="left")
            qr[val] = rb
        if not gvram or gvram < 3.5:
            for val in ("0.6B", "1.7B"):
                qr[val].configure(state="disabled")
            self._setup_qwen.set("нет")
        elif gvram < 5.5:
            qr["1.7B"].configure(state="disabled")

        bar = ctk.CTkProgressBar(body, height=10, corner_radius=6, progress_color="#c6763a",
                                 fg_color=COLOR_CARD2)
        bar.set(0)
        bar.pack(fill="x", padx=16, pady=(8, 2))
        info = ctk.CTkLabel(body, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC,
                            anchor="w", justify="left", wraplength=590)
        info.pack(fill="x", padx=16)

        rowb = ctk.CTkFrame(body, fg_color="transparent")
        rowb.pack(fill="x", padx=16, pady=(6, 8))
        btn_go = ctk.CTkButton(rowb, text=_tr("Установить выбранное"), width=200, height=34,
                               corner_radius=R_PANEL, font=FONT_SUBHEADER,
                               fg_color="#c6763a", hover_color="#a95f2c",
                               text_color="#ffffff")
        btn_go.pack(side="left")
        ctk.CTkButton(rowb, text=_tr("Закрыть"), width=110, height=34, corner_radius=R_PANEL,
                      font=FONT_NORMAL, fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      hover_color=COLOR_CARD,
                      command=lambda: (self._setup_cancel.set(), dlg.destroy())
                      ).pack(side="left", padx=8)

        def set_info(t):
            try:
                if dlg.winfo_exists():
                    info.configure(text=str(t))
            except Exception:
                pass

        def set_bar(v):
            try:
                if dlg.winfo_exists():
                    bar.set(max(0.0, min(float(v), 1.0)))
            except Exception:
                pass

        def work():
            try:
                gguf_final = os.path.join(self.BASE_DIR, "models_llm", self.MODEL_PACK["name"])
                if not os.path.isfile(gguf_final) and not self._setup_cancel.is_set():
                    set_info(_tr("1 · Gemma 4 E4B + сборка для видеокарты (≈5,6 ГБ)…"))
                    holder = ctk.CTkToplevel(self)
                    holder.withdraw()
                    btnfake = ctk.CTkButton(holder, text="")
                    self._dl_cancel = self._setup_cancel
                    self._download_model(holder, bar, info, btnfake)

                    def _kill_holder():
                        try:
                            if holder.winfo_exists():
                                holder.destroy()
                        except Exception:
                            pass
                    self._ui(_kill_holder)
                    if self._setup_cancel.is_set():
                        set_info(_tr("Установка прервана — продолжите позже"))
                        return
                    if not os.path.isfile(gguf_final):
                        set_info(_tr("Модель анализа не докачалась — попробуйте ещё раз"))
                        return
                if self._setup_vox.get() and not self._vox_installed() \
                        and not self._setup_cancel.is_set():
                    set_info(_tr("2 · Дополнение Vox: установка…"))
                    self._vox_cancelled = False

                    def vprog(t, v):
                        set_info("Vox · " + str(t))
                        if v is not None:
                            set_bar(v)

                    def vline(line):
                        if self._setup_cancel.is_set():
                            self._vox_cancelled = True
                            p = getattr(self, "_vox_proc", None)
                            try:
                                if p is not None and p.poll() is None:
                                    p.kill()
                            except Exception:
                                pass
                        set_info("Vox · " + str(line)[:120])

                    ok, detail = self._vox_install_work(vprog, vline)
                    if ok:
                        self._ui(self._vox_ready)
                    elif not self._setup_cancel.is_set():
                        set_info(_tr("Vox не установлен: ") + str(detail)[-160:])
                if self._setup_qwen.get() in ("0.6B", "1.7B") and not self._setup_cancel.is_set():
                    self.qwen_size = self._setup_qwen.get()
                    self.save_settings()
                    set_info(f"Qwen3-TTS {self.qwen_size}…")

                    if not self._qwen_installed() and not self._setup_cancel.is_set():
                        if not self._vox_installed():
                            set_info(_tr("GPU-среда для Qwen (≈2,5 ГБ)…"))
                            self._vox_cancelled = False

                            def qenv_prog(t, v):
                                set_info("Qwen · " + str(t))
                                if v is not None:
                                    set_bar(v)

                            def qenv_line(line):
                                if self._setup_cancel.is_set():
                                    self._vox_cancelled = True
                                    p = getattr(self, "_vox_proc", None)
                                    try:
                                        if p is not None and p.poll() is None:
                                            p.kill()
                                    except Exception:
                                        pass
                                set_info("Qwen · " + str(line)[:120])

                            ok_env, detail_env = self._vox_install_work(qenv_prog, qenv_line)
                            if ok_env:
                                self._ui(self._vox_ready)
                            elif not self._setup_cancel.is_set():
                                set_info(_tr("GPU-среда не установлена: ")
                                         + str(detail_env)[-160:])
                                return
                        if not self._setup_cancel.is_set():
                            set_info(_tr("Пакет Qwen3-TTS (≈30 МБ)…"))

                            def qpkg_line(line):
                                if self._setup_cancel.is_set():
                                    return
                                m = re.search(r"Progress (\d+) of (\d+)", line)
                                if m:
                                    cur, tot = int(m.group(1)), max(1, int(m.group(2)))
                                    set_info(_tr("Пакет Qwen3-TTS") + f" {int(100 * cur / tot)}%")
                                else:
                                    set_info("Qwen · " + str(line)[:120])

                            ok_pkg, detail_pkg = self._qwen_pip_install(qpkg_line)
                            if not ok_pkg and not self._setup_cancel.is_set():
                                set_info(_tr("Пакет qwen-tts не установлен: ")
                                         + str(detail_pkg)[-160:])

                    def qprog(p, name):
                        set_info(f"Qwen {self.qwen_size}: {p:.0f}% · {name}")
                        set_bar(p / 100.0)

                    self._qwen_fetch(list(self._qwen_repos().keys()),
                                     on_progress=qprog, cancel=self._setup_cancel)
                if self._setup_cancel.is_set():
                    return
                self._ui(self._refresh_voices)
                self._ui(self._mark_setup_done)
                set_info("\u2705 " + _tr("Установка завершена — можно работать"))
                try:
                    if dlg.winfo_exists():
                        btn_go.configure(state="disabled")
                except Exception:
                    pass
            except Cancelled:
                set_info(_tr("Установка прервана — продолжите позже"))
            except Exception as e:
                print(f"\u274c Первичная установка: {e}")
                set_info(f"\u274c {e}")

        btn_go.configure(command=lambda: threading.Thread(target=work, daemon=True).start())
        dlg.update_idletasks()
        try:
            dlg.geometry(f"640x{max(330, dlg.winfo_reqheight())}")
        except Exception:
            pass
        _center_on_parent(dlg)

    def _auto_install_voices(self):
        """Первый запуск: докачиваем русские голоса Ирина и Руслан (≈126 МБ)."""
        missing = [(n, s) for n, s in self.AUTO_VOICES if not os.path.isfile(self._voice_file(n))]
        if not missing or getattr(self, "voices_seeded", False):
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Голоса Piper"))
        dlg.geometry("520x215")
        _center_on_parent(dlg)
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
                self.tts_combo.configure(values=self.voice_values(
                    self.current_engine if self.current_engine in ("Vox", "Qwen") else None))
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
        _center_on_parent(dlg)
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
        ctk.CTkButton(foot, text=_tr("Свой Piper (.onnx)…"), width=200, height=30,
                      corner_radius=R_PANEL, font=FONT_SMALL, fg_color="#c6763a",
                      hover_color="#a95f2c", text_color="#ffffff",
                      command=lambda: self._import_piper_voice(dlg, info)).pack(side="left")

    def _import_piper_voice(self, dlg, info):
        """Свой голос Piper: выбрать на компьютере name.onnx (+ name.onnx.json рядом)."""
        path = filedialog.askopenfilename(
            parent=dlg, title=_tr("Импорт голоса Piper"),
            filetypes=[(_tr("Модель Piper (.onnx)"), "*.onnx"), (_tr("Все файлы"), "*.*")])
        if not path:
            return
        src = os.path.abspath(path)
        name = os.path.splitext(os.path.basename(src))[0]
        name = re.sub(r"[^\w.\-]", "_", name) or "my_voice"

        cfg = os.path.splitext(src)[0] + ".onnx.json"     # стандарт Piper
        if not os.path.isfile(cfg):
            cfg = src + ".json"
        if not os.path.isfile(cfg):
            messagebox.showwarning("FAIR", _tr(
                "Для импорта голоса нужны два файла рядом: name.onnx и name.onnx.json "
                "— стандартный набор Piper."))
            return
        try:
            json.loads(open(cfg, encoding="utf-8").read())
        except Exception:
            messagebox.showwarning("FAIR",
                                   f"{_tr('Конфиг голоса повреждён')}: {os.path.basename(cfg)}")
            return

        folder = os.path.join(self.BASE_DIR, "models")
        os.makedirs(folder, exist_ok=True)
        dst = self._voice_file(name)
        n = 2
        while os.path.exists(dst):
            dst = self._voice_file(f"{name}-{n}")
            n += 1
        name = os.path.splitext(os.path.basename(dst))[0]
        try:
            shutil.copy2(src, dst)
            shutil.copy2(cfg, dst + ".json")
        except Exception as e:
            messagebox.showwarning("FAIR", f"{_tr('Ошибка загрузки')}: {e}")
            return
        self._refresh_voices(select=name)
        try:
            info.configure(text=f"{_tr('Голос импортирован')}: {name}")
        except Exception:
            pass
        self.update_status(f"✅ {_tr('Голос импортирован')}: «{name}»")

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
            if getattr(self, "_api_server", None):
                self._api_server.shutdown()
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

    def _build_mem_panel(self, parent):
        """Карточка памяти внизу левого столбца: видеопамять и ОЗУ в одну строку
        (макет Ярослава 06.11). Подписи — прошлые, серым; значения «занято/всего»;
        полосы короткие, перед второй подписи — большой зазор. По бокам карточки
        те же «грани», что у верхних панелей."""
        p = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=R_CARD,
                         border_width=1, border_color=COLOR_BORDER)
        p.pack(fill="x", padx=2, pady=(0, 8))
        self._add_side_edges(p)          # вертикальные «грани» слева и справа
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=8)
        specs = ((_tr("Видеопамять"), "gpu", COLOR_RED, (0, 0)),
                 (_tr("Память (ОЗУ)"), "ram", COLOR_GOLD, (20, 0)))
        for cap, key, col, pl in specs:
            ctk.CTkLabel(row, text=cap, font=FONT_TINY, text_color=COLOR_TEXT_SEC,
                         anchor="w").pack(side="left", padx=pl)
            bar = ctk.CTkProgressBar(row, height=8, corner_radius=4, width=97,
                                     fg_color=COLOR_BORDER, progress_color=col)
            bar.set(0)
            bar.pack(side="left", padx=(3, 0))
            val = ctk.CTkLabel(row, text="…", font=FONT_TINY,
                               text_color=COLOR_TEXT_MAIN, anchor="e")
            val.pack(side="left", padx=(4, 0))
            setattr(self, f"{key}_val", val)
            setattr(self, f"{key}_bar", bar)
        return p

    def _gpu_mem_probe(self):
        """(занято, всего) видеопамяти или (None, None). NVML не создаёт CUDA-контекст."""
        h = getattr(self, "_nvml_h", None)
        if h is None:
            if getattr(self, "_nvml_bad", False):
                return (None, None)
            try:
                import pynvml
                pynvml.nvmlInit()
                self._nvml_h = pynvml.nvmlDeviceGetHandleByIndex(0)
                h = self._nvml_h
            except Exception:
                self._nvml_bad = True
                return (None, None)
        try:
            import pynvml
            mi = pynvml.nvmlDeviceGetMemoryInfo(h)
            return (mi.used, mi.total)
        except Exception:
            return (None, None)

    def _update_ram_label(self):
        """Перерисовывает панель памяти: видеопамять — ржавчина, ОЗУ — золото."""
        gu, gt = self._gpu_mem_probe()
        if gu is not None and gt:
            self.gpu_val.configure(text=f"{gu / 2**30:.0f}/{gt / 2**30:.0f} ГБ")
            self.gpu_bar.set(min(1.0, gu / gt))
        else:
            self.gpu_val.configure(text="—")
            self.gpu_bar.set(0)
        rt, ra = self._sys_mem_info()
        if rt:
            used = rt - ra
            self.ram_val.configure(text=f"{used / 2**30:.0f}/{rt / 2**30:.0f} ГБ")
            self.ram_bar.set(min(1.0, used / rt))
        else:
            self.ram_val.configure(text="—")
            self.ram_bar.set(0)

    def _mem_tick(self):
        """Опрос раз в 2.5 с; после закрытия окна цикл сам гаснет."""
        try:
            self._update_ram_label()
            self.after(2500, self._mem_tick)
        except Exception:
            pass

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
                            selectforeground="#2b231c",
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
            _style_tk_menu(menu)
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
                elif isinstance(child, ctk.CTkComboBox):
                    child._canvas.configure(cursor="hand2")
                    child._entry.configure(cursor="xterm")
                    self._attach_combo_hover(child)
            except Exception:
                pass
            self._polish_cursors(child)

    def _show_custom_voice(self, show):
        """Большая кнопка «Образец голоса». Эмоции — внутри окна образца."""
        try:
            if show:
                # под Qwen кнопка встаёт сразу за рядами «Дизайн/Настройки»,
                # у Vox — на привычном месте над ползунком скорости (Ярослав, 04.11.26)
                anchor = (self._tts_voice_row
                          if getattr(self, "current_engine", "") == "Qwen" else self.rate_row)
                self.btn_add_voice.pack(fill="x", padx=12, pady=(0, 10), before=anchor)
            else:
                self.btn_add_voice.pack_forget()
        except Exception:
            pass

    def _show_piper_import(self, show):
        """Кнопка «📂 Свой голос Piper…» — только для движка Piper."""
        try:
            if show:
                self.btn_import_piper.pack(fill="x", padx=12, pady=(0, 10), before=self.rate_row)
            else:
                self.btn_import_piper.pack_forget()
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

        # кнопки языка — узкие, чтобы не растягивали шапку
        self.lang_toggle = SegmentToggle(topbar, values=["RU", "EN"], height=28,
                                          btn_width=34, command=self._set_lang)
        self.lang_toggle.set("EN" if UI_LANG == "en" else "RU")   # как в прошлый раз
        self.lang_toggle.grid(row=0, column=2, sticky="e", padx=(0, 4))

        # ---------------- левая панель ----------------
        # карточки лежат прямо на фоне окна — без внешней панели и прокрутки
        self.sidebar = ctk.CTkFrame(self, width=330, fg_color="transparent")
        self.sidebar.grid(row=1, column=0, sticky="nsew", padx=(20, 8), pady=(8, 16))

        def make_card(title):
            card = ctk.CTkFrame(self.sidebar, fg_color=COLOR_CARD, corner_radius=R_CARD,
                                border_width=1, border_color=COLOR_BORDER)
            card.pack(fill="x", padx=2, pady=(0, 8))
            self._card_head(card, title)
            self._add_side_edges(card)      # вертикальные «грани» слева и справа
            return card

        # ----- Источник -----
        src = make_card("ИСТОЧНИК")

        url_row = ctk.CTkFrame(src, fg_color="transparent")
        url_row.pack(fill="x", padx=12, pady=(0, 7))
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(url_row, placeholder_text="Ссылка на статью или видео (YouTube, Rutube, VK)",
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
            # который убирает placeholder «Ссылка на статью или видео» при фокусе
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
                                             dropdown_fg_color="#fffdf6", dropdown_text_color=COLOR_TEXT_MAIN,
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
        # текст промпта переводит _translate_instruction, а не общий обход _apply_lang
        # (иначе обход подменял в нём отдельные слова вроде «Скорость» или «Готово»)
        self.instruction_entry._no_auto_tr = True
        self._style_text_selection(self.instruction_entry)
        self.instruction_entry._textbox.bind("<FocusIn>", lambda e: self.instruction_entry.configure(height=150), add="+")
        self.instruction_entry._textbox.bind("<FocusOut>", lambda e: self.instruction_entry.configure(height=74), add="+")
        self._bind_ctrl_v(self.instruction_entry._textbox,
                          lambda e: self._paste_widget(self.instruction_entry, e))
        self._bind_clipboard_keys(self.instruction_entry._textbox)
        self._dnd_attach(self.instruction_entry)
        self._attach_text_menu(self.instruction_entry._textbox,
                               on_insert=lambda t: self.instruction_entry.insert("insert", t))

        run_row = ctk.CTkFrame(src, fg_color="transparent")
        run_row.pack(fill="x", padx=12, pady=(0, 5))
        run_row.grid_columnconfigure(0, weight=1)

        self.btn_process = ctk.CTkButton(run_row, text="Запустить анализ", command=self.start_full_process,
                                         height=34, corner_radius=3, font=(FONT_FAMILY, 12, "bold"),
                                         fg_color=COLOR_BRAND, hover_color=COLOR_BRAND_HOVER,
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
                                          progress_color=COLOR_BRAND, fg_color=COLOR_SWITCH_OFF,
                                          button_color="#fffdf6", button_hover_color="#fffdf6",
                                          command=self.save_settings)
        self.auto_play_cb.pack(fill="x", padx=12, pady=(0, 0))

        # Разметка эмоциями нужна только движку Vox (образцы эмоций живут в его голосе),
        # поэтому на Piper переключатель гаснет — см. _sync_emo_auto().
        self.emo_auto_cb = ctk.CTkSwitch(src, text="Добавить эмоции", variable=self.emo_auto_var,
                                         font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                                         progress_color="#F2C94C", fg_color=COLOR_SWITCH_OFF,
                                         button_color="#fffdf6", button_hover_color="#fffdf6",
                                         command=self._on_emo_auto_toggle)
        self.emo_auto_cb.pack(fill="x", padx=12, pady=(0, 9))

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
                                           dropdown_fg_color="#fffdf6", dropdown_text_color=COLOR_TEXT_MAIN,
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
                                        progress_color=COLOR_BRAND, fg_color=COLOR_SWITCH_OFF,
                                        button_color="#fffdf6", button_hover_color="#fffdf6",
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
                                        progress_color=COLOR_BRAND, button_color=COLOR_BRAND,
                                        button_hover_color=COLOR_BRAND_HOVER, fg_color=COLOR_BORDER)
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
        self._tts_voice_row = voice_row

        # ----- Qwen3-TTS: инструменты движка (видны только когда выбран Qwen) -----
        self.qwen_row = ctk.CTkFrame(tts, fg_color="transparent")
        self.qwen_row.grid_columnconfigure(0, weight=1)
        self.qwen_row.grid_columnconfigure(1, weight=1)
        self.btn_qwen_design = ctk.CTkButton(
            self.qwen_row, text=_tr("✨ Дизайн голоса"), height=28, corner_radius=3,
            font=FONT_SMALL, fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_MAIN, command=self._qwen_design_dialog)
        self.btn_qwen_design.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_qwen_design.bind("<Button-3>", self._qwen_size_menu)
        self.btn_qwen_cfg = ctk.CTkButton(
            self.qwen_row, text=_tr("⚙ Настройки Qwen"), height=28, corner_radius=3,
            font=FONT_SMALL, fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_MAIN, command=self._qwen_settings_dialog)
        self.btn_qwen_cfg.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.btn_qwen_cfg.bind("<Button-3>", self._qwen_size_menu)
        self.btn_qwen_cfg.bind("<Button-3>", self._qwen_size_menu)
        self.qwen_instruct_row = ctk.CTkFrame(tts, fg_color="transparent")
        self.qwen_instruct_row.grid_columnconfigure(1, weight=1)
        self.qwen_instruct = ctk.CTkEntry(
            self.qwen_instruct_row, font=FONT_TINY, height=26, corner_radius=3,
            fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_SEC, state="readonly",
            placeholder_text=_tr("характер задаётся в «✨ Дизайн голоса»"))
        self.qwen_instruct.grid(row=0, column=1, sticky="ew")
        self.qwen_seed_var = ctk.StringVar(value="0")
        self.qwen_fixed_var = ctk.BooleanVar(value=False)

        # как верхний список «Сжатие»: тот же CTkOptionMenu и те же цвета
        self.tts_combo = ctk.CTkOptionMenu(voice_row, values=[], font=FONT_SMALL, height=30,
                                           corner_radius=3, command=self.on_tts_change,
                                           fg_color=COLOR_CARD2, button_color=COLOR_FILL_SOFT,
                                           button_hover_color=COLOR_SELECT, text_color=COLOR_TEXT_MAIN,
                                           dropdown_fg_color="#fffdf6", dropdown_text_color=COLOR_TEXT_MAIN,
                                           dropdown_hover_color=COLOR_SELECT)
        self.tts_combo.grid(row=0, column=0, sticky="ew")

        self.rate_row = ctk.CTkFrame(tts, fg_color="transparent")
        self.rate_row.pack(fill="x", padx=12, pady=(0, 10))
        self.rate_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.rate_row, text="Скорость", font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC).grid(row=0, column=0, sticky="w")
        self.rate_slider = ctk.CTkSlider(self.rate_row, from_=0.5, to=1.5, number_of_steps=10,
                                         command=self._on_rate_slider, height=16,
                                         progress_color=COLOR_BRAND, button_color=COLOR_BRAND,
                                         button_hover_color=COLOR_BRAND_HOVER, fg_color=COLOR_BORDER)
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

        # загрузить СВОЙ файл голоса Piper — та же кнопка-слот, что «Образец голоса» у Vox
        self.btn_import_piper = ctk.CTkButton(tts, text=_tr("📂  Свой голос Piper…"), height=30,
                                              corner_radius=3, font=FONT_SMALL,
                                              fg_color=COLOR_FILL_SOFT, hover_color=COLOR_SELECT,
                                              text_color=COLOR_TEXT_MAIN,
                                              border_width=1, border_color=COLOR_BORDER,
                                              command=lambda: self._import_piper_voice(None, None))
        self.btn_import_piper.pack(fill="x", padx=12, pady=(0, 10), before=self.rate_row)
        self.btn_import_piper.pack_forget()  # показываем только для Piper

        # ---- карточка памяти: последней в левом столбце, под «ОЗВУЧКОЙ» (макет Ярослава) ----
        self.mem_panel = self._build_mem_panel(self.sidebar)

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
        self._dnd_attach(self.result_box)      # брось документ сюда — он откроется

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
                                      fg_color=COLOR_BRAND, hover_color=COLOR_BRAND_HOVER,
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
                                               progress_color=COLOR_BRAND, fg_color=COLOR_BORDER)
        self.progress_bar.grid(row=0, column=3, padx=14, pady=12, sticky="ew")
        self.progress_bar.set(0)

        # «Сохранить озвучку» — значок ⬇: сохраняет WAV последней озвучки в файл.
        # Заменил собой строку состояния справа (её убрали по просьбе Ярослава).
        self.btn_save_audio = ctk.CTkButton(self.audio_control_frame, text="",
                                            image=self._save_icon,
                                            width=44, height=36, corner_radius=3,
                                            fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                                            text_color=COLOR_TEXT_MAIN,
                                            command=self._save_last_audio)
        self.btn_save_audio.grid(row=0, column=4, padx=(6, 14), pady=12)

        self._mem_tick()

        self.bind("<Control-Return>", lambda e: self.start_full_process())
        self.bind("<F5>", lambda e: self.play_result())
        self.after(40, self._place_window)

    def _place_window(self):
        """Ставит окно по центру экрана и не даёт содержимому его раздуть."""
        try:
            self.update_idletasks()
            w, h = 1140, 850
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
        combo.configure(fg_color=COLOR_CARD2, dropdown_fg_color="#fffdf6",
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
            ctx, kv, kvfix = None, 131072, 0
            md = _gguf_raw_meta(path)           # заголовок GGUF: читаем без ggml
            arch = md.get("general.architecture")
            if arch:
                try:
                    ctx = int(md[arch + ".context_length"])
                except Exception:
                    ctx = None
                kv, kvfix = _gguf_kv_est(md)    # точная формула по размерности KV
            if not ctx or ctx <= 0:
                try:                            # запасной путь — llama_cpp
                    m = Llama(model_path=path, vocab_only=True, verbose=False)
                    try:
                        ctx = int(m.n_ctx_train())
                    except Exception:
                        ctx = None
                    if not ctx or ctx <= 0:
                        for key in list(m.metadata or {}):
                            if str(key).endswith("context_length"):
                                try:
                                    ctx = int(m.metadata[key])
                                except Exception:
                                    continue
                                break
                except Exception as e:
                    print(f"⚠️ Не удалось прочитать метаданные: {e}")
            if not ctx or ctx <= 0:
                ctx = 4096
            try:
                fsize = os.path.getsize(path)
            except Exception:
                fsize = 0

            self.model_meta[disp] = {"ctx": ctx, "kv": kv, "kvfix": kvfix,
                                     "file_size": fsize}
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
        # значение из поля может быть БОЛЬШЕ родного контекста — не обрезаем его;
        # ползунок физически упирается в свой максимум (CTkSlider.set клипует сам)
        used = int(chosen) if chosen else native
        used = max(MIN_CTX, used)
        self.ctx_slider.set(min(used, native))

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

        weights = meta["file_size"]
        kvn = meta["kv"] * used + meta.get("kvfix", 0)   # KV-кэш выбранного контекста
        gib = lambda b: b / (1024 ** 3)
        free_v, vram = None, None
        if self.llm_gpu_var.get():
            # режим «видеокарта»: веса и KV-кэш живут в видеопамяти (весы могут
            # оставаться частично в отображённом файле), в ОЗУ — служебная часть
            vram = weights + kvn + int(0.30 * 2**30)
            ram = int(0.75 * 2**30) + weights * 0.55 + kvn * 0.25
            txt = _tr(f"{used:,} ток. · VRAM ≈ {gib(vram):.1f} · ОЗУ ≈ {gib(ram):.1f} ГБ")
            gu, gt = self._gpu_mem_probe()
            if gu is not None and gt:
                free_v = gt - gu
        else:
            # режим «процессор»: всё — и веса, и кэш — лежит в системной ОЗУ
            ram = weights * 1.05 + kvn + int(0.35 * 2**30)
            txt = _tr(f"{used:,} ток. · ОЗУ ≈ {gib(ram):.1f} ГБ")

        rt, ra = self._sys_mem_info()
        known = bool(ra) or free_v is not None
        ok = True
        if ra:
            ok = ok and ram <= ra
        if free_v is not None:
            ok = ok and (vram or 0) <= free_v
        color = (COLOR_GREEN if ok else COLOR_RED) if known else COLOR_TEXT_SEC
        self.llm_limit_label.configure(text=txt.replace(",", " "), text_color=color)
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
        # сверху не ограничиваем: можно ввести любое число больше родного контекста
        v = max(MIN_CTX, v)
        self.ctx_choices[self._actual_llm()] = str(v)
        self.refresh_model_info()
        self.save_settings()
        self.update_status(f"Контекст: {v:,} токенов".replace(",", " "))

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

    # ============= ФАЙЛЫ PDF/DOC/MD/FB2/EPUB/RTF/HTML =============

    def insert_file(self):
        path = filedialog.askopenfilename(
            title="Выберите файл (pdf, docx, epub, fb2, rtf, html, txt, md)",
            filetypes=[("Документы", "*.pdf *.docx *.doc *.txt *.md *.fb2 *.epub *.rtf *.html *.htm"), ("All files", "*.*")])
        if not path:
            return
        self.insert_path(path)

    def insert_path(self, path):
        """Загрузить документ в поле текста: кнопка «Файл» и перетаскивание."""
        ext = os.path.splitext(path)[1].lower()
        src_name = None
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
            elif ext == ".md":
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = self._clean_markdown(f.read())
            elif ext in (".fb2", ".epub"):
                chapters, book_title = (self._parse_fb2 if ext == ".fb2" else self._parse_epub)(path)
                if not chapters:
                    raise Exception("В файле EPUB не найдено текста глав." if ext == ".epub" else "В файле FB2 не найдено текста глав.")
                if len(chapters) > 2:
                    self._book_dialog(chapters, book_title, path)
                    return
                text = "\n\n".join(c["text"] for c in chapters).strip()
                src_name = book_title or os.path.basename(path)
            elif ext == ".rtf":
                text = self._rtf_to_text(path)
            elif ext in (".html", ".htm"):
                text = self._html_to_text(path)
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if len(text) < 100:
                raise Exception("В файле не найден текст (возможно, скан без текстового слоя).")
            self._put_source_text(text, src_name or os.path.basename(path))
        except Exception as e:
            messagebox.showerror("Файл", str(e))

    def _pick_article(self, article):
        self._put_source_text(article["text"], article["title"])

    # ---------------- ПЕРЕТАСКИВАНИЕ ФАЙЛОВ В ПОЛЕ ТЕКСТА ----------------

    def _dnd_attach(self, widget):
        """Разрешает бросить файл в виджет — он откроется как документ."""
        if not _DND_OK:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_file_drop)
        except Exception:
            pass

    def _on_file_drop(self, event):
        """Бросили файл(ы) в поле источника — грузим первый поддерживаемый."""
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [str(getattr(event, "data", "") or "").strip()]
        for p in paths:
            p = p.strip()
            if p and os.path.isfile(p):
                self.insert_path(p)
                return

    # ---------------- видео: YouTube / Rutube / VK ----------------
    _YT_HOSTS = ("youtube.com", "youtu.be", "m.youtube.com", "www.youtube.com",
                 "music.youtube.com", "youtube-nocookie.com")

    def _video_kind(self, url):
        """Видеоссылка? -> (платформа, id/ссылка), иначе None."""
        try:
            from urllib.parse import urlparse, parse_qs
            p = urlparse(url if "://" in url else "https://" + url)
            host = (p.netloc or "").lower()
            if any(host == h or host.endswith("." + h) for h in self._YT_HOSTS):
                vid = (parse_qs(p.query).get("v") or [None])[0]
                if not vid:
                    m = re.match(r"^/(?:shorts|live|embed|v)/([A-Za-z0-9_-]{6,20})", p.path)
                    if m: vid = m.group(1)
                if not vid and "youtu.be" in host:
                    vid = p.path.strip("/").split("/")[0]
                if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
                    return ("youtube", vid)
            elif "rutube" in host:
                m = re.search(r"/(?:video|embed|play)/([a-f0-9]{32})", p.path)
                if m: return ("rutube", m.group(1))
            elif any(s in host for s in ("vk.com", "vkvideo.ru", "vk.ru")):
                if re.search(r"/(video-?\d+_\d+|clip-?\d+_\d+)", p.path):
                    return ("vk", url)
        except Exception:
            pass
        return None

    def _ask_choice(self, title, subtitle, labels):
        """Модальный выбор одной строки из списка; None — отмена."""
        box = ctk.CTkToplevel(self)
        box.title(title); box.geometry("480x430"); box.transient(self); box.grab_set()
        _center_on_parent(box)
        self.after(0, lambda: _apply_lang(box))
        _apply_dialog_icon(box)
        box.configure(fg_color=COLOR_BG)
        body = ctk.CTkFrame(box, fg_color=COLOR_PANEL, corner_radius=R_PANEL,
                            border_width=1, border_color=COLOR_BORDER)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(body, text=title, font=(FONT_FAMILY, 16, "bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(body, text=subtitle, font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                     anchor="w").pack(fill="x", padx=18, pady=(0, 10))
        scroll = ctk.CTkScrollableFrame(body, fg_color=COLOR_CARD, corner_radius=4,
                                        border_width=1, border_color=COLOR_BORDER,
                                        scrollbar_button_color=COLOR_BORDER)
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        result = {"i": None}
        for i, lab in enumerate(labels):
            ctk.CTkButton(scroll, text=lab[:110], anchor="w", height=34, corner_radius=3,
                          fg_color="transparent", hover_color=COLOR_ACCENT_SOFT,
                          text_color=COLOR_TEXT_MAIN, font=FONT_SMALL,
                          command=lambda i=i: (result.update(i=i), box.destroy())).pack(fill="x", pady=2)
        ctk.CTkButton(body, text="Отмена", height=30, width=120, corner_radius=3,
                      fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_SEC, font=FONT_SMALL,
                      command=box.destroy).pack(pady=(0, 12))
        self.wait_window(box)
        return result["i"]

    def _fetch_video_transcript(self, kind, ident):
        """Текст субтитров видео -> (text, title). Отмена выбора -> _SubCancelled."""
        if kind == "youtube":
            return self._youtube_transcript(ident)
        if kind == "rutube":
            return self._rutube_transcript(ident)
        return self._ytdlp_transcript(ident, "ВК")

    def _youtube_title(self, vid):
        try:
            r = requests.get("https://www.youtube.com/oembed",
                             params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"},
                             timeout=10)
            if r.ok: return (r.json().get("title") or "").strip()
        except Exception:
            pass
        return ""

    def _youtube_transcript(self, vid):
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            raise Exception("Не найден модуль youtube-transcript-api. "
                            "Установите: pip install youtube-transcript-api")
        try:
            tracks = list(YouTubeTranscriptApi().list(vid))
        except Exception:
            raise Exception("YouTube не отдал субтитры: у видео их нет, оно приватное "
                            "или с возрастным ограничением.")
        if not tracks:
            raise Exception("У этого видео на YouTube нет субтитров.")
        uniq = {}
        for t in sorted(tracks, key=lambda t: bool(t.is_generated)):  # авторские вперёд
            uniq.setdefault(t.language_code or "?", t)
        cand = sorted(uniq.values(),
                      key=lambda t: (0 if (t.language_code or "").split("-")[0] == "ru" else 1))
        if len(cand) == 1:
            tr = cand[0]
        else:
            labels = [f"{t.language or t.language_code}" +
                      (" — автосубтитры" if t.is_generated else " — авторские") for t in cand]
            i = self._ask_choice("Субтитры — выберите язык",
                                 f"У видео {len(cand)} дорожек субтитров", labels)
            if i is None:
                raise _SubCancelled()
            tr = cand[i]
        got = tr.fetch()
        text = self._vtt_to_text("\n".join((s.text or "").strip() for s in got))
        return text, (self._youtube_title(vid) or f"YouTube {vid}")

    def _rutube_transcript(self, vid):
        try:
            r = requests.get(f"https://rutube.ru/api/play/options/{vid}/",
                             params={"no_404": "true"},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        except Exception:
            raise Exception("Rutube: сервис недоступен.")
        if not r.ok:
            raise Exception("Rutube: видео не найдено или недоступно.")
        j = r.json()
        # Rutube отдаёт субтитры в поле captions (список {code, file, format}), а не subtitles
        raw = j.get("subtitles") or j.get("captions") or {}
        items = []
        if isinstance(raw, dict):
            items = [(str(c), u) for c, u in raw.items() if isinstance(u, str) and u]
        elif isinstance(raw, list):
            items = [(str(x.get("code") or x.get("language_code") or ""),
                      x.get("file") or x.get("url") or "")
                     for x in raw if isinstance(x, dict)]
            items = [(c, u) for c, u in items if u]
        if not items:
            raise Exception("На Rutube у этого видео нет субтитров — Rutube почти не отдаёт субтитры. "
                            "Попробуйте ссылку на этот же ролик с YouTube.")
        cand = sorted(items, key=lambda it: (0 if it[0].split("-")[0] == "ru" else 1))
        if len(cand) == 1:
            code, u = cand[0]
        else:
            i = self._ask_choice("Субтитры — выберите язык",
                                 f"У видео {len(cand)} дорожки субтитров", [c for c, _ in cand])
            if i is None:
                raise _SubCancelled()
            code, u = cand[i]
        rr = requests.get(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                 "Chrome/131.0.0.0 Safari/537.36"}, timeout=20)
        txt = rr.content.decode("utf-8", "replace")
        return self._vtt_to_text(txt), (j.get("title") or f"Rutube {vid[:8]}")

    def _ytdlp_transcript(self, url, platform="ВК"):
        try:
            import yt_dlp
        except ImportError:
            raise Exception(f"Для {platform} нужен модуль yt-dlp. Установите: pip install yt-dlp")
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                                   "socket_timeout": 25, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            raise Exception(f"{platform}: не удалось получить данные видео — ссылка неверная, "
                            "ролик приватный или сервис недоступен.")
        if info.get("_type") == "playlist":
            info = (info.get("entries") or [{}])[0] or {}
        pool = info.get("subtitles") or info.get("automatic_captions") or {}

        def pick_fmt(fmts):
            for ext in ("vtt", "srv3", "srv1", "ttml"):
                for f in fmts:
                    if f.get("ext") == ext or f.get("format_id") == ext:
                        return f.get("url")
            return (fmts[0].get("url") if fmts else None)

        items = []
        for code, fmts in pool.items():
            if code in ("live_chat", "json3"): continue
            u = pick_fmt(fmts or [])
            if u: items.append((str(code), u))
        if not items:
            raise Exception(f"На {platform} у этого видео нет доступных субтитров. "
                            "Попробуйте ссылку на этот же ролик с YouTube.")
        cand = sorted(items, key=lambda it: (0 if it[0].split("-")[0] == "ru" else 1))[:12]
        if len(cand) == 1:
            code, u = cand[0]
        else:
            i = self._ask_choice("Субтитры — выберите язык",
                                 f"У видео {len(cand)} дорожек субтитров", [c for c, _ in cand])
            if i is None:
                raise _SubCancelled()
            code, u = cand[i]
        try:
            # VK-CDN (okcdn) отдаёт 400 на короткий User-Agent — нужен полноценный браузерный
            hdr = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                   "Referer": "https://vkvideo.ru/"}
            rr = requests.get(u, headers=hdr, timeout=30)
            txt = rr.content.decode("utf-8", "replace")  # VK не пишет charset в content-type
        except Exception:
            raise Exception(f"{platform}: не удалось скачать файл субтитров.")
        return self._vtt_to_text(txt), (info.get("title") or platform)

    def _vtt_to_text(self, raw):
        """WebVTT / SRV3 / список реплик -> чистый текст с дедупликацией бегущих строк."""
        raw = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
        if re.search(r"<(?:transcript|tt|webvtt)[ >]", raw[:500], re.I):
            raw = re.sub(r"<[^>]+>", "\n", raw)
        out, prev = [], None
        for ln in raw.split("\n"):
            ln = re.sub(r"<[^>]+>", "", ln).strip()
            if not ln or "-->" in ln or re.fullmatch(r"\d+", ln): continue
            if ln == "WEBVTT" or ln.split(" ")[0] in ("Kind:", "Language:", "NOTE", "STYLE", "region") \
                    or ln.startswith(("/*", "}", "region ")):
                continue
            if prev is not None:
                if ln == prev: continue
                if ln.startswith(prev):
                    tail = ln[len(prev):].strip()
                    if tail:
                        out.append(tail); prev = ln
                    continue
            out.append(ln); prev = ln
        return re.sub(r"\s{2,}", " ", " ".join(out)).strip()

    def _clean_markdown(self, text):
        """Markdown в обычный текст для озвучки: разметка убрана, текст (и код) остались."""
        text = re.sub(r"^\s*(?:```|~~~)[^\n]*$", "", text, flags=re.M)          # строки-ограничители код-блоков
        text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)               # картинки -> подпись
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)                # ссылки -> текст ссылки
        text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)              # ссылки по сноскам
        text = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+", "", text, flags=re.M)        # заголовки
        text = re.sub(r"^[ \t]*(?:[-*_][ \t]*){3,}[ \t]*$", "", text, flags=re.M)  # разделители ---
        text = re.sub(r"^[ \t]*\|?[ \t:|-]*-{2,}[ \t:|-]*\|?[ \t]*$", "", text, flags=re.M)  # строка |---|---|
        text = re.sub(r"^[ \t]*\|(.*)\|[ \t]*$",
                      lambda m: "  ".join(c.strip() for c in m.group(1).split("|") if c.strip()),
                      text, flags=re.M)                                          # таблица -> строки слов
        text = re.sub(r"^[ \t]*>[ \t]?", "", text, flags=re.M)                 # цитаты
        text = re.sub(r"^([ \t]*)[-*+][ \t]+", r"\1", text, flags=re.M)       # маркеры списков
        text = re.sub(r"^([ \t]*)\d{1,3}[.)][ \t]+", r"\1", text, flags=re.M)  # нумерованные списки
        text = re.sub(r"`([^`\n]+)`", r"\1", text)                             # инлайн-код
        text = re.sub(r"<(https?://[^>\s]+)>", r"\1", text)                    # авто-ссылки <url>
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
        text = re.sub(r"___(.+?)___", r"\1", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"~~(.+?)~~", r"\1", text)
        text = re.sub(r"(?<!\w)\*(?=\S)(.+?)(?<=\S)\*(?!\w)", r"\1", text)
        text = re.sub(r"(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)", r"\1", text)
        return text

    def _parse_fb2(self, path):
        """FB2 -> (главы [{"title","text"}], заголовок книги). Только <body>: без аннотаций, эпиграфов и сносок."""
        try:
            with open(path, "rb") as f:
                raw = f.read()
            # защитный разбор: обычный FB2 не содержит DTD/сущностей — их присутствие признак вредоносного XML (XXE, billion laughs)
            head = raw[:4096] + raw[-4096:] if len(raw) > 8192 else raw
            if re.search(rb"(?i)<!(DOCTYPE|ENTITY)", head) or re.search(rb"(?i)<!ENTITY", raw):
                raise Exception("Файл FB2 повреждён: ошибка разбора XML.")
            root = ET.fromstring(raw)
        except ET.ParseError:
            raise Exception("Файл FB2 повреждён: ошибка разбора XML.")

        def loc(el):
            return el.tag.split("}")[-1].lower()

        def flat(el):
            return re.sub(r"\s+", " ", "".join(el.itertext())).strip()

        book_title = ""
        for el in root:
            if loc(el) != "description":
                continue
            for ti in el:                                  # description -> title-info -> book-title
                if loc(ti) != "title-info":
                    continue
                for t in ti:
                    if loc(t) == "book-title":
                        book_title = flat(t)

        def own_text(sec, skip_title=False, fold_sections=True):
            parts = []
            for el in sec:
                tag = loc(el)
                if tag == "section":
                    if not fold_sections:                  # для body: разделы считаются главами отдельно
                        continue
                                                           # подраздел -> его заголовок + текст внутрь главы
                    t = next((x for x in el if loc(x) == "title"), None)
                    sub = flat(t) if t is not None else ""
                    sub_txt = own_text(el, skip_title=True)
                    if sub_txt:
                        parts.append((sub + "\n\n" + sub_txt) if sub else sub_txt)
                    continue
                if tag == "epigraph" or (skip_title and tag == "title"):
                    continue
                if tag == "empty-line":
                    parts.append("")
                    continue
                t = flat(el)
                if t:
                    parts.append(t)
            return "\n".join(parts).strip()

        chapters = []
        for body in [el for el in root if loc(el) == "body"]:
            has_secs = any(loc(s) == "section" for s in body)
            # преамбула level-body (автор, реклама библиотеки) берётся только если разделов нет вовсе
            intro = "" if has_secs else own_text(body, fold_sections=False)
            if len(intro) >= 100:
                chapters.append({"title": "", "text": intro})
            for sec in body:
                if loc(sec) != "section":
                    continue
                t = next((x for x in sec if loc(x) == "title"), None)
                title = flat(t) if t is not None else ""
                txt = own_text(sec, skip_title=True)
                if len(txt) < 50:
                    continue
                chapters.append({"title": title, "text": (title + "\n\n" + txt) if title else txt})
        for i, c in enumerate(chapters, 1):
            if not c["title"]:
                c["title"] = f"Глава {i}"
        return chapters, book_title


    def _book_dialog(self, chapters, book_title, path):
        """Диалог выбора глав для книг (FB2/EPUB): вся книга целиком или одна глава."""
        base = book_title or os.path.basename(path)
        whole = "\n\n".join(c["text"] for c in chapters).strip()
        items = [{"title": "📖 Вся книга целиком", "text": whole, "name": base}]
        for i, c in enumerate(chapters, 1):
            t = c["title"]
            lab = t if re.match(r"^(\d+[.)\s]|глав[аы]\b)", t, re.I) else f"{i}. {t}"
            items.append({"title": lab, "text": c["text"], "name": f"{base} — {t}"})
        PdfArticlesDialog(self, items, lambda a: self._put_source_text(a["text"], a["name"]),
                          win_title="Главы книги",
                          count_text=f"Найдено глав: {len(chapters)}")

    def _parse_epub(self, path):
        """EPUB -> (главы [{"title","text"}], заголовок книги); главы в порядке spine, навигация пропущена."""
        from urllib.parse import unquote
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            raise Exception("Файл EPUB повреждён: не читается ZIP-контейнер.")
        try:
            cont = z.read("META-INF/container.xml").decode("utf-8", "ignore")
        except KeyError:
            raise Exception("Файл EPUB повреждён: не найден контейнер.")
        m = re.search(r'full-path="([^"]+)"', cont)
        if not m:
            raise Exception("Файл EPUB повреждён: не найден контейнер.")
        opf_name = unquote(m.group(1)).lstrip("/")
        opf_dir = opf_name.rsplit("/", 1)[0] if "/" in opf_name else ""
        try:
            opf_bytes = z.read(opf_name)
            if re.search(rb"(?i)<!(DOCTYPE|ENTITY)", opf_bytes):   # как в FB2: чистый OPF без DTD/сущностей
                raise Exception("Файл EPUB повреждён: ошибка разбора OPF.")
            opf = ET.fromstring(opf_bytes)
        except ET.ParseError:
            raise Exception("Файл EPUB повреждён: ошибка разбора OPF.")

        def loc(el):
            return el.tag.split("}")[-1].lower()

        book_title = ""
        manifest, spine = {}, []
        for el in opf.iter():
            tag = loc(el)
            if tag == "title":
                if not book_title:
                    book_title = (el.text or "").strip()
            elif tag == "item":
                manifest[el.get("id")] = (el.get("href") or "", (el.get("properties") or ""))
            elif tag == "itemref":
                spine.append(el.get("idref") or "")

        chapters = []
        for rid in spine:
            href, props = manifest.get(rid, ("", ""))
            href = unquote(href)
            if "nav" in props.split() or not href.lower().rsplit(".", 1)[-1] in ("xhtml", "html", "htm"):
                continue
            full = (opf_dir + "/" + href.split("#")[0]) if opf_dir else href.split("#")[0]
            segs = []
            for p in full.split("/"):                       # нормализация ./ и ../ внутри архива
                if p == "..":
                    if segs:
                        segs.pop()
                elif p not in (".", ""):
                    segs.append(p)
            try:
                raw = z.read("/".join(segs))
            except KeyError:
                continue
            soup = BeautifulSoup(raw, "html.parser")
            for bad in soup(["script", "style", "head"]):
                bad.decompose()
            h = soup.find(re.compile(r"^h[1-3]$"))
            title = re.sub(r"\s+", " ", h.get_text()).strip() if h else ""
            txt = soup.get_text("\n")
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n\s*\n+", "\n\n", txt).strip()
            if len(txt) < 100:
                continue
            chapters.append({"title": title, "text": (title + "\n\n" + txt) if title else txt})
        for i, c in enumerate(chapters, 1):
            if not c["title"]:
                c["title"] = f"Глава {i}"
        return chapters, book_title

    def _rtf_to_text(self, path):
        r"""RTF -> текст: группы-приёмники {\*…}, управляемые слова/символы убраны, \'hh и \uN раскодированы."""
        with open(path, "rb") as f:
            s = f.read()
        prev = None
        while prev != s:                                   # {\* …} и известные служебные группы: шрифты, стили,
            prev = s                                       # колонтитулы, списки, картинки — всё мимо текста
            s = re.sub(rb"\{\\\*[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", b"", s)
            s = re.sub(rb"\{\\(?:fonttbl|stylesheet|info|colortbl|filetbl|listtable|listtemplate\w*|list\w*"
                       rb"|pict|shppict|nonshppict|xmlsect\w*|themedata|colorschememapping|latentstyles|datastore"
                       rb"|header\d*|footer\d*|bkmk\w+|generator|template|mmask)\b[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", b"", s)
        s = re.sub(rb"\\par[d]?\s?", b"\n", s)
        s = re.sub(rb"\\(line|nestcell|nestrow|row|cell)\d?\s?", b"\n", s)
        s = re.sub(rb"\\tab\s?", b"\t", s)
        s = re.sub(rb"\\'([0-9a-fA-F]{2})", lambda mo: bytes([int(mo.group(1), 16)]), s)

        def _u(mo):                                        # \uNNNN — юникод; байт-фолбэк после него съедается общим правилом ниже
            v = int(mo.group(1))
            if v < 0:
                v += 65536
            try:
                b = chr(v).encode("cp1251", "ignore")
            except Exception:
                b = b""
            return b or b"?"
        s = re.sub(rb"\\u(-?\d+)\s?", _u, s)
        s = re.sub(rb"\\[a-zA-Z]{1,32}\s?", b"", s)
        s = re.sub(rb"\\.", b"", s)
        s = s.replace(b"{", b"").replace(b"}", b"")
        t = s.decode("cp1251", "ignore")
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n\n", t)
        return t.strip()

    def _html_to_text(self, path):
        """HTML/HTM -> текст: скрипты/стили/теги убраны, сущности раскодированы, кодировка из meta."""
        with open(path, "rb") as f:
            raw = f.read()
        enc = "utf-8"
        m = re.search(rb'charset\s*=\s*["\']?\s*([A-Za-z0-9_-]+)', raw[:3000])
        if m:
            cand = m.group(1).decode("ascii", "ignore")
            try:
                "".encode(cand)
                enc = cand
            except LookupError:
                pass
        soup = BeautifulSoup(raw.decode(enc, "ignore"), "html.parser")
        for bad in soup(["script", "style"]):
            bad.decompose()
        t = soup.get_text("\n")
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n\n", t)
        return t.strip()

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

    def _voice_engine(self, info):
        """К какому движку принадлежит голос (своя метка engine, иначе — по следам в данных)."""
        if not isinstance(info, dict):
            return "Vox"
        e = info.get("engine")
        if e in ("Vox", "Qwen"):
            return e
        if info.get("instruct"):
            return "Qwen"                       # дизайн-голос — это Qwen
        return "Vox"

    def voice_values(self, engine=None):
        """Названия слотов для списка «Озвучка». Указал engine — только голоса этого
        движка плюс пустые слоты (пустой заполнится тем движком, что запишет)."""
        out = []
        for _vid, i in self._voice_items():
            if not isinstance(i, dict) or not i.get("name"):
                continue
            if engine and i.get("path") and self._voice_engine(i) != engine:
                continue
            out.append(i.get("name"))
        return out

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

    # --- эмоции образцов: маркер (эмоция) переключает образец голоса на ОДНО предложение ---

    @staticmethod
    def _emo_stem(word):
        """Основа названия эмоции — то же правило, что у справочника EMOTION_TAB."""
        return _emo_key(word)

    def _emotion_samples(self, speaker):
        """{основа: (название, путь, текст)} — образцы эмоций выбранного голоса."""
        out = {}
        _, info = self._find_voice(speaker)
        if isinstance(info, dict):
            for label, smp in (info.get("samples") or {}).items():
                path = (smp or {}).get("path") if isinstance(smp, dict) else ""
                if path and os.path.exists(path):
                    out[self._emo_stem(label)] = (
                        label, path, smp.get("text") or info.get("text") or self.REF_TEXT)
        return out

    def _split_emotion_segments(self, text, speaker):
        """[(эмоция|None, кусок текста)] — маркер (эмоция) окрашивает ТОЛЬКО своё
        предложение; со следующего предложения снова нейтральный голос."""
        emos = self._emotion_samples(speaker)
        if not emos:
            return [(None, text)]
        parts, pos, cur = [], 0, None
        for m in re.finditer(r"\(([^()]{1,40})\)", text):
            word = (re.split(r"[\s,;:]+", m.group(1).strip()) or [""])[0]
            hit = emos.get(self._emo_stem(word)) if word else None
            if not hit:
                continue                     # не наша эмоция — скобки остаются в тексте
            frag = text[pos:m.start()]
            if frag.strip():
                parts.append((cur, frag))
            cur, pos = hit[0], m.end()
        rest = text[pos:]
        if rest.strip():
            parts.append((cur, rest))
        if not parts:
            return [(None, text)]
        # эмоция живёт только до конца предложения
        out = []
        for emo, frag in parts:
            if not emo:
                out.append((None, frag))
                continue
            sentences = [s for s in re.split(r"(?<=[.!?…])[ \t]+", frag) if s.strip()]
            if sentences:
                out.append((emo, sentences[0]))
                out.extend((None, s) for s in sentences[1:])
        return out or [(None, text)]

    def get_ref(self, speaker, emotion=None):
        vid, info = self._find_voice(speaker)
        if info is None:
            raise Exception(f"Голос «{speaker}» не найден. Нажмите «🎙 Образец голоса».")
        text = info.get("text") or self.REF_TEXT
        if emotion:
            smp = (info.get("samples") or {}).get(emotion) or {}
            if isinstance(smp, dict) and smp.get("path") and os.path.exists(smp.get("path") or ""):
                return smp["path"], smp.get("text") or text
        path = info.get("path") or ""
        if path and os.path.exists(path):
            return path, text
        for smp in (info.get("samples") or {}).values():   # нейтрального нет — любой образец
            if isinstance(smp, dict) and smp.get("path") and os.path.exists(smp.get("path") or ""):
                return smp["path"], smp.get("text") or self.REF_TEXT
        raise Exception(f"Слот «{speaker}» пуст — запишите образец голоса.")

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
        _center_on_parent(dlg)
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

    VOX_MIN_FREE_GB = 6.0   # 4,7 ГБ весов VoxCPM2 + резерв на диффузию и активации

    def _ask_low_vram(self, free_gb, total_gb):
        """Спросить из любого потока: грузить Vox при почти занятой видеопамяти?
        False — пользователь отказался (баг «загружается и не может загрузиться», 06.11.26)."""
        def ask():
            return messagebox.askyesno(
                _tr("Видеопамять занята"),
                _tr("Видеопамять почти вся занята другой программой.")
                + f"\n{_tr('Свободно')} {free_gb:.1f} ГБ, {_tr('нужно')} ≈{self.VOX_MIN_FREE_GB:.0f} ГБ.\n\n"
                + _tr("Если загрузить сейчас, видеокарта начнёт делить память между программами: "
                      "загрузка и озвучка будут очень долгими, а чужое приложение будет тормозить.")
                + "\n\n"
                + _tr("Закрой то, что держит видеокарту (LM Studio, ComfyUI, серверы моделей), "
                      "или выбери движок Piper.")
                + "\n\n" + _tr("Всё равно попробовать загрузить?"))
        if threading.current_thread() is threading.main_thread():
            return ask()
        res, ev = {}, threading.Event()

        def go():
            try:
                res["v"] = ask()
            except Exception:
                res["v"] = False
            ev.set()
        try:
            self.after(0, go)
        except Exception:
            return False
        ev.wait(900)
        return bool(res.get("v"))

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
            _flog(f"vox: загрузка начата · CUDA={cuda_ok}")

            # VRAM-гейт: при занятой карте torch молча «льёт» веса в ОЗУ через WDDM —
            # загрузка ~1 мин и синтез в разы медленнее. Спросим честно (06.11.26).
            if cuda_ok:
                _u, _t = self._gpu_mem_probe()
                if _u is not None and _t:
                    _free = (_t - _u) / 2 ** 30
                    _flog(f"vox: свободно VRAM {_free:.1f}/{_t / 2 ** 30:.1f} GiB")
                    if _free < self.VOX_MIN_FREE_GB:
                        if not self._ask_low_vram(_free, _t / 2 ** 30):
                            _flog("vox: пользователь отказался грузить (мало VRAM)")
                            self.after(0, lambda: self.update_status(
                                "⏸ " + _tr("Vox не загружен: мало видеопамяти")))
                            return False
                        self.after(0, lambda: self.update_status(
                            "⏳ " + _tr("Загрузка VoxCPM2 (веса ~5 ГБ)...")))

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
                            _flog(f"vox: from_pretrained dev={dev} kwargs={list(kw) or ['default']}")
                            t0 = time.time()
                            self.vox_model = VoxCPM.from_pretrained(name, device=dev, **kw)
                            self.vox_name = name
                            self._print_vox_device()
                            _flog(f"vox: загружен за {time.time() - t0:.0f} с")
                            print(
                                f"🎙 VoxCPM2 загружен: {name} · device={dev} · dtype={list(kw.keys()) or 'bf16 (default)'}")
                            return True
                        except TypeError:
                            continue  # неизвестный kwarg → пробуем следующий
                        except Exception as e:
                            last_err = e
                            _flog(f"vox: [{name}, {dev}] {type(e).__name__}: {e}")
                            print(f"⚠️ VoxCPM2 [{name}, {dev}]: {e}")
                            break  # ошибка устройства → следующий dev
            _err_txt = str(last_err or "")
            if "out of memory" in _err_txt.lower():
                raise Exception(_tr(
                    "Не удалось загрузить VoxCPM2: видеокарту держит другое приложение "
                    "(CUDA out of memory). Освободи видеопамять и попробуй снова."))
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

    # ================= QWEN3-TTS (GPU) =================

    def _qwen_combo_values(self):
        """Список голосов: встроенные тембры CustomVoice + слоты образцов."""
        return [QWEN_SPEAKERS[s][0] for s in QWEN_SPEAKERS] + self.voice_values("Qwen")

    def _show_qwen_tools(self, show):
        if show:
            self.qwen_row.pack(fill="x", padx=12, pady=(0, 6), before=self._tts_voice_row)
            try:   # у лёгкого 0.6B дизайна нет — кнопка затемнена, клик предложит сменить движок
                if "design" in self._qwen_repos():
                    self.btn_qwen_design.configure(fg_color=COLOR_FILL_SOFT,
                                                   hover_color=COLOR_BORDER,
                                                   text_color=COLOR_TEXT_MAIN)
                else:
                    self.btn_qwen_design.configure(fg_color=COLOR_CARD,
                                                   hover_color=COLOR_CARD,
                                                   text_color=COLOR_TEXT_SEC)
            except Exception:
                pass
            # «🎙 Образец голоса» — сразу после кнопок «Дизайн голоса»/«Настройки Qwen»
            self._show_custom_voice(True)
            # строка инструкции характера — под списком голосов, только для чтения
            self.qwen_instruct_row.pack(fill="x", padx=12, pady=(0, 6), before=self.rate_row)
            self._sync_qwen_instruct()
        else:
            self.qwen_row.pack_forget()
            self.qwen_instruct_row.pack_forget()

    def _sync_qwen_instruct(self):
        """Поле инструкции в карточке — read-only зеркало паспорта текущего голоса."""
        e = getattr(self, "qwen_instruct", None)
        if e is None:
            return
        txt = ""
        try:
            if getattr(self, "current_engine", "") == "Qwen":
                name = self.current_tts_name or self.tts_combo.get()
                if name in QWEN_BY_DISPLAY:
                    # встроенный тембр: его паспорт — пол и характер из справочника
                    _sid, gen, desc = QWEN_BY_DISPLAY[name]
                    txt = f"{gen}, {desc}"
                else:
                    _vid, info = self._find_voice(name)
                    if isinstance(info, dict):
                        txt = str(info.get("instruct") or "")
        except Exception:
            txt = ""
        try:
            e.configure(state="normal")
            e.delete(0, "end")
            if txt:
                e.insert(0, txt[:200])
            e.configure(state="readonly")
        except Exception:
            pass

    def _qwen_installed(self):
        if getattr(self, "_qwen_inst_ok", False):
            return True
        self._vox_syspath()       # пакет живёт в переносимой GPU-среде (vox/site)
        _sox_stub_if_needed()     # sox рвёт импорт qwen_tts в pythonw (WinError 50)
        try:
            import qwen_tts  # noqa: F401
            self._qwen_inst_ok = True
            return True
        except Exception as e:
            # импорт споткнулся (гонка потоков, временный сбой) — проверяем пакет
            # прямо на диске: если он стоит, НЕ показываем «не установлен»
            on_disk = False
            try:
                _, _, site_dir = self._vox_paths()
                cands = [os.path.join(site_dir, "qwen_tts")]
                cands += [os.path.join(p, "qwen_tts") for p in sys.path
                          if p.endswith("site-packages")]
                on_disk = any(os.path.isdir(c) for c in cands)
            except Exception:
                pass
            if not getattr(self, "_qwen_tb_logged", False):
                self._qwen_tb_logged = True   # один полный трейс — не спамить журнал
                import traceback as _tb
                _flog("qwen_tts импорт не прошёл | на диске=%s\n%s"
                      % (on_disk, _tb.format_exc()))
            return bool(on_disk)

    # что ставим в переносимую GPU-среду вместе с движком Qwen.
    # torch не трогаем НИКОГДА: pip иначе тянет свежий CPU-торч поверх рабочей
    # сборки 2.5.1+cu121 и ломает Vox (проверено на живом окружении)
    QWEN_PKG_PINS = ["qwen-tts==0.1.1", "transformers==4.57.3",
                     "tokenizers==0.22.2", "accelerate==1.12.0",
                     "huggingface-hub==0.36.2", "safetensors==0.8.0"]
    # каталоги этих пакетов в оверлее — их чистим перед установкой
    QWEN_PKG_DIRS = ["qwen_tts", "transformers", "tokenizers", "accelerate",
                     "huggingface_hub", "safetensors"]
    QWEN_PKG_EXTRA = ["librosa", "einops", "onnxruntime", "gradio",
                      "sox", "soxr", "pydub", "soundfile"]

    def _qwen_pip_install(self, on_line=None):
        """Поставить пакет qwen-tts в переносимую GPU-среду (vox/site). (ok, хвост)"""
        _, py_dir, site_dir = self._vox_paths()
        py_exe = os.path.join(py_dir, "python.exe")
        if not os.path.isfile(py_exe):
            return False, _tr("GPU-среда не установлена — сначала нужен движок Vox.")
        # 0) pip --target НЕ перезаписывает готовые каталоги: старый пакет остался бы
        #    лежать рядом с новым dist-info и отравил бы среду. Вычищаем только свои
        #    пинованные пакеты — torch и пакеты Vox не трогаем НИКОГДА.
        for nm in self.QWEN_PKG_DIRS:
            for d in (os.path.join(site_dir, nm),):
                if os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
            for di in glob.glob(os.path.join(site_dir, nm + "-*.dist-info")):
                shutil.rmtree(di, ignore_errors=True)
        # 1) пинованные пакеты: --no-deps, чтобы pip не притащил свежий torch
        ok, out = self._run_py(
            [py_exe, "-m", "pip", "install", "--no-warn-script-location",
             "--progress-bar", "raw", "--upgrade", "--no-deps",
             "--target", site_dir] + self.QWEN_PKG_PINS,
            on_line)
        if not ok:
            return False, "pip install qwen-tts:\n" + out
        # 2) вспомогательные библиотеки qwen-tts (torch не тянут): добираем недостающие
        self._run_py(
            [py_exe, "-m", "pip", "install", "--no-warn-script-location",
             "--progress-bar", "raw", "--target", site_dir] + self.QWEN_PKG_EXTRA,
            on_line)
        if not ok:
            return False, "pip install qwen-tts:\n" + out
        code = ("import sys; sys.path.insert(0, r'%s'); import qwen_tts; "
                "print('QWENOK', qwen_tts.__file__)" % site_dir)
        ok, out = self._run_py([py_exe, "-c", code], on_line)
        if ok and "QWENOK" in out:
            self._vox_syspath()   # чтобы импорт был виден и окну приложения
        return (ok and "QWENOK" in out), out[-600:]

    def _qwen_check_import(self):
        if not self._qwen_installed():
            raise Exception(_tr("Пакет qwen-tts не установлен — движок Qwen недоступен."))

    def _qwen_dir(self):
        return os.path.join(self.BASE_DIR, "models_qwen")

    def _qwen_repos(self):
        """Репозитории чекпойнтов для текущего размера движка (0.6B — без дизайна)."""
        return QWEN_MODELS_06 if self.qwen_size == "0.6B" else QWEN_MODELS

    def _qwen_path(self, kind):
        return os.path.join(self._qwen_dir(), self._qwen_repos()[kind].split("/")[-1])

    def _qwen_ready(self, kind):
        if kind not in self._qwen_repos():
            return False
        d = self._qwen_path(kind)
        return bool(os.path.exists(os.path.join(d, ".qwen_ok"))
                    and os.path.exists(os.path.join(d, "config.json")))

    def _qwen_fetch(self, kinds, on_progress=None, cancel=None):
        """Скачать недостающие модели Qwen с Hugging Face в models_qwen (качка через .part)."""
        import json as _json
        kinds = [k for k in kinds if k in self._qwen_repos() and not self._qwen_ready(k)]
        if not kinds:
            return
        os.makedirs(self._qwen_dir(), exist_ok=True)
        for kind in kinds:
            repo = self._qwen_repos()[kind]
            d = self._qwen_path(kind)
            os.makedirs(d, exist_ok=True)
            try:
                r = _http_get(QWEN_HF_TREE.format(repo=repo), timeout=30)
                entries = _json.loads(r.text)
            except Exception as e:
                raise Exception(f"Не удалось получить список файлов модели Qwen: {e}")
            files = [(e["path"], int(e.get("size") or 0)) for e in entries
                     if e.get("type") in ("blob", "file")
                     and e["path"].lower().endswith(QWEN_EXT)]
            if not files:
                raise Exception("Qwen: сервер вернул пустой список файлов.")
            total = sum(sz for _n, sz in files) or 1
            prog = {"done": 0}
            for name, size in files:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                dest = os.path.join(d, *name.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if os.path.exists(dest) and size and os.path.getsize(dest) == size:
                    prog["done"] += size
                    continue
                if on_progress:
                    on_progress(min(99.0, 100.0 * prog["done"] / total), name)
                print(f"⬇ Qwen {kind}: {name}")

                def _tick(n, _name=name):
                    prog["done"] += n
                    if on_progress:
                        on_progress(min(99.0, 100.0 * prog["done"] / total), _name)

                self._fetch_file(QWEN_HF_FILE.format(repo=repo, file=name), dest,
                                 on_bytes=_tick, cancel=cancel)
            with open(os.path.join(d, ".qwen_ok"), "w", encoding="utf-8") as f:
                f.write(repo)
            print(f"✅ Модель Qwen {kind} на месте")

    def _qwen_prepare(self):
        """Выбран движок Qwen: проверить модели, предложить докачать."""
        if not self._qwen_installed():
            return
        missing = [k for k in ("custom", "base", "design")
                   if k in self._qwen_repos() and not self._qwen_ready(k)]
        if not missing:
            self.update_status(_tr("Qwen3-TTS: модели на месте."))
            return
        gmap = QWEN_GB_06 if self.qwen_size == "0.6B" else QWEN_GB
        gb = sum(gmap[k] for k in missing)
        names = ", ".join(self._qwen_repos()[k].split("/")[-1] for k in missing)
        if not messagebox.askyesno(
                _tr("Движок Qwen"),
                _tr("Не скачаны модели Qwen3-TTS (~{gb} ГБ):\n{names}\n\n"
                    "Скачать сейчас в папку models_qwen?").format(gb=gb, names=names)):
            self.update_status(_tr("Qwen3-TTS: модели не скачаны — докачает при озвучке."))
            return

        def work():
            try:
                self._qwen_fetch(missing, on_progress=lambda p, name: self._safe_ui(
                    lambda p=p, name=name: self.set_progress(int(p), f"Модель Qwen: {name}")))
                self._safe_ui(lambda: self.set_progress(0, ""))
                self._safe_ui(lambda: self.update_status(_tr("✅ Модели Qwen3-TTS скачаны.")))
            except Exception as e:
                print(f"❌ Загрузка Qwen: {e}")
                self._safe_ui(lambda e=e: self.update_status(f"❌ Qwen: {e}"))
                self._safe_ui(lambda: self.set_progress(0, ""))
        threading.Thread(target=work, daemon=True).start()

    def _qwen_device_dtype(self):
        import torch
        want = str(self.qwen_cfg.get("device") or "auto")
        has_gpu = torch.cuda.is_available()
        if want == "cpu" or not has_gpu:
            return "cpu", torch.float32
        prec = str(self.qwen_cfg.get("precision") or "bf16")
        if prec == "fp32":
            return "cuda", torch.float32
        if prec == "fp16":
            return "cuda", torch.float16
        return "cuda", torch.bfloat16

    def _qwen_model(self, kind):
        if kind not in self._qwen_repos():
            raise Exception(_tr("Режим недоступен на лёгком движке Qwen 0.6B — "
                                "поставьте 1.7B в «Настройки Qwen»."))
        if not self._qwen_ready(kind):
            raise Exception(f"Модель Qwen {kind} не скачана.")
        cached = self._qwen_models.get(kind)
        if cached is not None:
            return cached
        dev, dt = self._qwen_device_dtype()
        self._safe_ui(lambda: self.update_status("⏳ Загрузка Qwen3-TTS (веса ~5 ГБ)..."))
        try:
            _sox_stub_if_needed()
            from qwen_tts import Qwen3TTSModel
        except Exception:
            import traceback as _tb
            _flog("Qwen3TTSModel импорт не прошёл\n" + _tb.format_exc())
            raise
        path = self._qwen_path(kind)
        try:
            m = Qwen3TTSModel.from_pretrained(path, device_map=dev, torch_dtype=dt)
        except Exception as e:
            if dev != "cpu":
                print(f"⚠️ Qwen на GPU не поднялся ({e}) — пробую CPU")
                import torch as _t
                m = Qwen3TTSModel.from_pretrained(path, device_map="cpu", torch_dtype=_t.float32)
            else:
                raise
        self._qwen_models[kind] = m
        self._qwen_prompt_cache.clear()   # промпты старого экземпляра модели невалидны
        self._safe_ui(lambda k=kind: self.update_status(f"✅ Qwen3-TTS ({k}) готова ({dev})."))
        return m

    def _qwen_free(self):
        """Отпустить VRAM/CUDA-кэш: модели Qwen тяжёлые."""
        import gc
        self._qwen_models.clear()
        self._qwen_prompt_cache.clear()
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _qwen_prompt(self, model, vid, info):
        """Готовый промпт клона для голоса-образца (кэшируется: создаётся 1 раз на голос)."""
        path = (info or {}).get("path") or ""
        if not path or not os.path.exists(path):
            raise Exception("Образец голоса не найден — перезапишите его через «🎙 Образец голоса».")
        key = f"{vid}|{path}|{bool((info or {}).get('text'))}"
        cache = self._qwen_prompt_cache
        if key in cache:
            return cache[key]
        ref_text = ((info or {}).get("text") or "").strip()
        if ref_text:
            try:
                prompt = model.create_voice_clone_prompt(ref_audio=path, ref_text=ref_text)
            except Exception as e:
                print(f"⚠️ Промпт клона по образцу+тексту не принят ({e}) — режим x-vector")
                prompt = model.create_voice_clone_prompt(ref_audio=path, x_vector_only_mode=True)
        else:
            prompt = model.create_voice_clone_prompt(ref_audio=path, x_vector_only_mode=True)
        cache.clear()   # держим промпт только текущего голоса: чужой промпт портит тембр
        cache[key] = prompt
        return prompt

    def _qwen_to_int16(self, wavs):
        w = wavs[0] if isinstance(wavs, (list, tuple)) and wavs else wavs
        if hasattr(w, "detach"):
            w = w.detach().cpu().numpy()
        arr = np.asarray(w, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            return arr.astype(np.int16)
        peak = float(np.abs(arr).max())
        if peak <= 1.5:
            gain = (32767.0 / max(peak, 1e-6)) if peak < 0.5 else 32767.0
            arr = np.clip(arr * gain, -32768, 32767)
        return arr.astype(np.int16)

    def _qwen_seed_saved(self):
        try:
            return max(0, min(2_000_000_000, int(self.qwen_seed_var.get() or 0)))
        except Exception:
            return 0

    def _qwen_new_run_seed(self):
        """Зерно на прогон: фиксированное из настроек или новое, чтобы дубли различались."""
        base = self._qwen_seed_saved()
        if base and bool(self.qwen_fixed_var.get()):
            self._qwen_run_seed = base
        else:
            self._qwen_runs += 1
            self._qwen_run_seed = (base + self._qwen_runs * 7919) % 2_000_000_000
        try:
            import torch
            torch.manual_seed(self._qwen_run_seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(self._qwen_run_seed)
        except Exception:
            pass
        print(f"🎲 Qwen seed: {self._qwen_run_seed}"
              + (" (фикс.)" if base and bool(self.qwen_fixed_var.get()) else ""))

    def _qwen_call(self, fn, **kw):
        """Вызов API пакета со срезанием kwargs, которых нет в этой версии пакета."""
        while True:
            try:
                return fn(**kw)
            except TypeError as e:
                msg = str(e)
                dropped = False
                for bad in ("instruct", "language", "voice_clone_prompt", "non_streaming_mode"):
                    if bad in msg and bad in kw:
                        kw.pop(bad)
                        dropped = True
                        print(f"⚠️ qwen-tts не принимает {bad} — пробую без него")
                        break
                if not dropped:
                    raise

    def _qwen_instruct_for(self, emo_label, user_instr, vpack=None):
        parts = []
        if emo_label:
            parts.append(EMOTION_TAB.get(emo_label, ("", ""))[0])
        info = (vpack or (None, None))[1] or {}
        own = (info.get("instruct") or "").strip()   # «паспорт» голоса из Дизайна
        if own:
            parts.append(own)
        if user_instr:
            parts.append(user_instr)
        s = ", ".join(p for p in parts if p).strip()
        return s or None

    def _split_emotion_segments_qwen(self, text):
        """[(метка эмоции|None, кусок)] — как у Vox, но эмоция подмешивается в instruct,
        а не в образец голоса: EMOTION_TAB даёт английскую инструкцию прямо из справочника."""
        if not EMOTION_TAB:
            return [(None, text)]
        by_stem = {self._emo_stem(label): label for label in EMOTION_TAB}
        parts, pos, cur = [], 0, None
        for m in re.finditer(r"\(([^()]{1,40})\)", text):
            word = (re.split(r"[\s,;:]+", m.group(1).strip()) or [""])[0]
            label = by_stem.get(self._emo_stem(word)) if word else None
            if not label:
                continue                     # не наша эмоция — скобки остаются в тексте
            frag = text[pos:m.start()]
            if frag.strip():
                parts.append((cur, frag))
            cur, pos = label, m.end()
        rest = text[pos:]
        if rest.strip():
            parts.append((cur, rest))
        if not parts:
            return [(None, text)]
        out = []
        for emo, frag in parts:
            if not emo:
                out.append((None, frag))
                continue
            sentences = [s for s in re.split(r"(?<=[.!?…])[ \t]+", frag) if s.strip()]
            if sentences:
                out.append((emo, sentences[0]))
                out.extend((None, s) for s in sentences[1:])
        return out or [(None, text)]

    def _qwen_synth_chunk(self, model, spk_id, vpack, ch_clean, emo_label, user_instr, lang):
        instruct = self._qwen_instruct_for(emo_label, user_instr, vpack)
        cfg = self.qwen_cfg
        common = dict(do_sample=True,
                      max_new_tokens=int(cfg["max_new_tokens"]),
                      top_p=float(cfg["top_p"]), top_k=int(cfg["top_k"]),
                      temperature=float(cfg["temperature"]),
                      repetition_penalty=float(cfg["repetition_penalty"]),
                      non_streaming_mode=True)
        if spk_id:   # встроенный тембр CustomVoice
            wavs, sr = self._qwen_call(model.generate_custom_voice, text=ch_clean,
                                       speaker=spk_id, language=lang, instruct=instruct,
                                       **common)
        else:        # клон по образцу (Base)
            vid, info = vpack
            prompt = self._qwen_prompt(model, str(vid), info or {})
            wavs, sr = self._qwen_call(model.generate_voice_clone, text=ch_clean,
                                       voice_clone_prompt=prompt, instruct=instruct,
                                       language=lang, **common)
        return self._qwen_to_int16(wavs), int(sr)

    def _qwen_size_menu(self, event):
        """ПКМ по «Дизайн голоса»: выбор движка Qwen — 4 ГБ или 6–8 ГБ."""
        menu = Menu(self, tearoff=0)
        _style_tk_menu(menu)
        cur = self.qwen_size
        menu.add_command(label=("\u2705 " if cur == "0.6B" else "    ") +
                         _tr("Движок 0.6B \u2014 нужно 4 ГБ (\u22485 ГБ)"),
                         command=lambda: self._qwen_switch_size("0.6B"))
        menu.add_command(label=("\u2705 " if cur == "1.7B" else "    ") +
                         _tr("Движок 1.7B \u2014 нужно 6\u20138 ГБ (\u224813,5 ГБ)"),
                         command=lambda: self._qwen_switch_size("1.7B"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _qwen_switch_size(self, size):
        """Сменить размер движка Qwen; если модели не скачаны — сначала спросить."""
        if size == self.qwen_size:
            return
        self.qwen_size = size
        missing = [k for k in self._qwen_repos() if not self._qwen_ready(k)]
        if missing:
            self.qwen_size = "1.7B" if size == "0.6B" else "0.6B"
            self._qwen_size_dl_offer(size, missing)
            return
        self._qwen_apply_size(size)

    def _qwen_apply_size(self, size):
        """Применить размер движка и докачать недостающие модели в фоне."""
        self.qwen_size = size
        self.save_settings()
        if self.current_engine == "Qwen":
            self._show_qwen_tools(True)
        missing = [k for k in self._qwen_repos() if not self._qwen_ready(k)]
        if not missing:
            self._ui(self.update_status, f"\u2705 Qwen {size}")
            return

        def work():
            try:
                if not self._qwen_installed():
                    ok_pkg, out_pkg = self._qwen_pip_install()
                    if not ok_pkg:
                        self._ui(self.update_status,
                                 f"\u274c qwen-tts: {out_pkg[-140:]}")

                def qprog(p, name):
                    self._ui(self.update_status,
                             f"Qwen {size}: {p:.0f}% \u00b7 {name}")
                self._qwen_fetch(missing, on_progress=qprog)
                self._ui(self.update_status, f"\u2705 Qwen {size} \u2713")
                self._ui(self._refresh_voices)
            except Cancelled:
                self._ui(self.update_status, _tr("Qwen докачка отменена"))
            except Exception as e:
                self._ui(self.update_status, f"\u274c Qwen: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _qwen_size_dl_offer(self, size, missing):
        """Движок {size} не скачан: предложить скачать, показав объём и VRAM."""
        gb_map = QWEN_GB_06 if size == "0.6B" else QWEN_GB
        total = sum(gb_map.get(k, 0.0) for k in missing)
        vram_need = _tr("\u043d\u0443\u0436\u043d\u043e 4 \u0413\u0411 \u0432\u0438\u0434\u0435\u043e\u043f\u0430\u043c\u044f\u0442\u0438") \
            if size == "0.6B" else \
            _tr("\u043d\u0443\u0436\u043d\u043e 6\u20138 \u0413\u0411 \u0432\u0438\u0434\u0435\u043e\u043f\u0430\u043c\u044f\u0442\u0438")
        gname, gvram = self._gpu_summary()
        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Скачать движок Qwen?"))
        dlg.geometry("540x250")
        _center_on_parent(dlg)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        ctk.CTkLabel(dlg, text=f"{_tr('Движок Qwen')} {size} {_tr('ещё не скачан')}",
                     font=FONT_SUBHEADER, text_color=COLOR_HEAD).pack(pady=(12, 4))
        ctk.CTkLabel(dlg, text=_tr("Скачать (\u2248{t:.1f} ГБ)?").format(t=total),
                     font=(FONT_FAMILY, 13, "bold"),
                     text_color=COLOR_TEXT_MAIN).pack()
        ctk.CTkLabel(dlg, text=vram_need, font=(FONT_FAMILY, 12, "bold"),
                     text_color=COLOR_TEXT_MAIN).pack(pady=(2, 0))
        if gname:
            need_min = 2.0 if size == "0.6B" else 5.5
            ok = gvram >= need_min
            ctk.CTkLabel(dlg, text=f"\U0001f5a5 {gname} \u2014 {gvram:.1f} "
                                   + _tr("ГБ видеопамяти"),
                         font=FONT_SMALL,
                         text_color=COLOR_GOLD if ok else COLOR_RED).pack(pady=(8, 1))
            if not ok:
                ctk.CTkLabel(dlg, text=_tr("Вашей видеопамяти может не хватить"),
                             font=FONT_TINY, text_color=COLOR_RED).pack()
        else:
            ctk.CTkLabel(dlg, text=_tr("\U0001f5a5 Видеокарта не найдена"),
                         font=FONT_SMALL, text_color=COLOR_RED).pack(pady=(8, 1))
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(pady=(12, 10))
        ctk.CTkButton(row, text=_tr("Скачать"), width=160, height=32,
                      corner_radius=3, font=FONT_SMALL,
                      fg_color="#c6763a", hover_color="#a95f2c",
                      text_color=COLOR_TEXT_MAIN,
                      command=lambda: (self._qwen_apply_size(size),
                                       dlg.destroy())).pack(side="left")
        ctk.CTkButton(row, text=_tr("Отмена"), width=100, height=32,
                      corner_radius=3, font=FONT_SMALL, fg_color=COLOR_FILL_SOFT,
                      hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      command=dlg.destroy).pack(side="left", padx=8)

        def _fit():
            try:
                if dlg.winfo_exists():
                    dlg.geometry(f"540x{max(190, dlg.winfo_reqheight())}")
            except Exception:
                pass
        dlg.after(60, _fit)

    def _qwen_design_size_offer(self):
        """Дизайн голоса требует движок 1.7B: показать требования и VRAM пользователя."""
        gname, gvram = self._gpu_summary()
        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Дизайн голоса"))
        dlg.geometry("540x230")
        _center_on_parent(dlg)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        ctk.CTkLabel(dlg, text=_tr("Дизайн голоса доступен у движка Qwen 1.7B"),
                     font=FONT_SUBHEADER, text_color=COLOR_HEAD).pack(pady=(12, 4))
        ctk.CTkLabel(dlg, text=_tr("Нужно 6\u20138 ГБ видеопамяти"),
                     font=(FONT_FAMILY, 13, "bold"),
                     text_color=COLOR_TEXT_MAIN).pack()
        if gname:
            ok = gvram >= 5.5
            ctk.CTkLabel(dlg, text=f"\U0001f5a5 {gname} \u2014 {gvram:.1f} "
                                   + _tr("ГБ видеопамяти"),
                         font=FONT_SMALL,
                         text_color=COLOR_GOLD if ok else COLOR_RED).pack(pady=(8, 1))
            if not ok:
                ctk.CTkLabel(dlg, text=_tr("Вашей видеопамяти может не хватить"),
                             font=FONT_TINY, text_color=COLOR_RED).pack()
        else:
            ctk.CTkLabel(dlg, text=_tr("\U0001f5a5 Видеокарта не найдена \u2014 "
                                       "дизайн голоса не сможет работать"),
                         font=FONT_SMALL, text_color=COLOR_RED).pack(pady=(8, 1))
        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(pady=(12, 10))
        ctk.CTkButton(row, text=_tr("Установить движок 1.7B (\u224813,5 ГБ)"),
                      width=240, height=32, corner_radius=3, font=FONT_SMALL,
                      fg_color="#c6763a", hover_color="#a95f2c",
                      text_color=COLOR_TEXT_MAIN,
                      command=lambda: (self._qwen_switch_size("1.7B"),
                                       dlg.destroy())).pack(side="left")
        ctk.CTkButton(row, text=_tr("Закрыть"), width=100, height=32,
                      corner_radius=3, font=FONT_SMALL, fg_color=COLOR_FILL_SOFT,
                      hover_color=COLOR_BORDER, text_color=COLOR_TEXT_MAIN,
                      command=dlg.destroy).pack(side="left", padx=8)

        def _fit():
            try:
                if dlg.winfo_exists():
                    dlg.geometry(f"540x{max(180, dlg.winfo_reqheight())}")
            except Exception:
                pass
        dlg.after(60, _fit)

    def _qwen_design_dialog(self):
        if "design" not in self._qwen_repos():
            self._qwen_design_size_offer()
            return
        """✨ Дизайн голоса: VoiceDesign-модель создаёт голос по текстовому описанию."""
        if not self._qwen_installed():
            messagebox.showwarning(_tr("Дизайн голоса"), _tr("Пакет qwen-tts не установлен."))
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Дизайн голоса"))
        dlg.geometry("440x490")
        _center_on_parent(dlg)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)   # фон окна в палитре приложения
        try:
            dlg.attributes("-topmost", True)
            dlg.after(500, lambda: dlg.attributes("-topmost", False))
        except Exception:
            pass
        ctk.CTkLabel(dlg, text=_tr("Опиши голос словами — модель его создаст.\n"
                                   "Например: «молодой энергичный мужчина, быстрая речь, с улыбкой»"),
                     font=FONT_SMALL, text_color=COLOR_TEXT_SEC, justify="left",
                     anchor="w").pack(fill="x", padx=16, pady=(14, 6))
        ins = ctk.CTkEntry(dlg, font=FONT_SMALL, height=58, corner_radius=3,
                           fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                           text_color=COLOR_TEXT_MAIN,
                           placeholder_text="мужчина, 25 лет, энергичный, с улыбкой, быстрая речь…")
        ins.pack(fill="x", padx=16)
        ctk.CTkLabel(dlg, text=_tr("Текст прослушки"), font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=16, pady=(10, 2))
        txt = ctk.CTkEntry(dlg, font=FONT_SMALL, height=34, corner_radius=3,
                           fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                           text_color=COLOR_TEXT_MAIN)
        txt.insert(0, VoiceRecorderDialog.DEFAULT_TEXT)
        txt.pack(fill="x", padx=16)
        ctk.CTkLabel(dlg, text=_tr("Имя голоса в списке"), font=FONT_SMALL,
                     text_color=COLOR_TEXT_SEC, anchor="w").pack(fill="x", padx=16, pady=(10, 2))
        name_e = ctk.CTkEntry(dlg, font=FONT_SMALL, height=30, corner_radius=3,
                              fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                              text_color=COLOR_TEXT_MAIN, placeholder_text="Дизайн 1")
        name_e.pack(fill="x", padx=16)
        status = ctk.CTkLabel(dlg, text="", font=FONT_SMALL, text_color=COLOR_TEXT_SEC,
                              anchor="w", justify="left", wraplength=400)
        status.pack(fill="x", padx=16, pady=(10, 6))
        state = {"wav": None, "ins": "", "sample": ""}

        def gen():
            d = (ins.get() or "").strip()
            t = (txt.get() or "").strip()
            if not d or not t:
                status.configure(text=_tr("Заполни описание голоса и текст."))
                return

            def work():
                try:
                    self._qwen_fetch(["design"])
                    model = self._qwen_model("design")
                    self._qwen_new_run_seed()
                    cfg = self.qwen_cfg
                    wavs, sr = self._qwen_call(
                        model.generate_voice_design, text=t, instruct=d, language=None,
                        do_sample=True, max_new_tokens=int(cfg["max_new_tokens"]),
                        top_p=float(cfg["top_p"]), top_k=int(cfg["top_k"]),
                        temperature=float(cfg["temperature"]),
                        repetition_penalty=float(cfg["repetition_penalty"]),
                        non_streaming_mode=True)
                    arr = self._qwen_to_int16(wavs)
                    if len(arr) < int(sr * 0.2):
                        self._safe_ui(lambda: status.configure(
                            text=_tr("Модель дала тишину — переформулируй описание.")))
                        return
                    path = os.path.join(self.BASE_DIR, "temp_qwen_design.wav")
                    with wave.open(path, "wb") as wf:
                        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(int(sr))
                        wf.writeframes(arr.tobytes())
                    state.update(wav=path, ins=d, sample=t)

                    def ok():
                        status.configure(text=_tr("Готово — слушаю. Нравится — жми «Сохранить»."))
                        self._play_wav(path)
                    self._safe_ui(ok)
                except Exception as e:
                    print(f"❌ Дизайн Qwen: {e}")
                    self._safe_ui(lambda e=e: status.configure(text=f"Ошибка: {e}"))
            status.configure(text=_tr("Генерирую голос…"))
            threading.Thread(target=work, daemon=True).start()

        def keep():
            if not state["wav"]:
                status.configure(text=_tr("Сначала прослушай вариант."))
                return
            vid, _info = self._first_empty_voice()
            if vid is None:
                vid = self._next_voice_id()
            wav = os.path.join(self.BASE_DIR, "voices_qwen", f"design_{vid}.wav")
            try:
                os.makedirs(os.path.dirname(wav), exist_ok=True)
                shutil.copyfile(state["wav"], wav)
            except Exception as e:
                status.configure(text=f"Не удалось сохранить: {e}")
                return
            label = (name_e.get() or "").strip() or "Дизайн"
            self._apply_custom_voice(wav, state["sample"], vid, label)
            info = self.custom_voices.get(str(vid))
            if isinstance(info, dict):
                info["instruct"] = state["ins"]   # паспорт голоса: подмешивается в каждое озвучивание
                self.save_settings()
            if self.current_engine == "Qwen":
                self.tts_combo.configure(values=self._qwen_combo_values())
                nm = info.get("name") if isinstance(info, dict) else label
                self.tts_combo.set(nm)
                self.current_tts_name = nm
                self._sync_qwen_instruct()
            status.configure(text=_tr("✅ Голос сохранён в списке — работает как клон."))

        ctk.CTkButton(dlg, text="🔊 " + _tr("Сгенерировать и послушать"), height=30,
                      corner_radius=3, fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_MAIN, command=gen).pack(fill="x", padx=16, pady=(2, 4))
        ctk.CTkButton(dlg, text="💾 " + _tr("Сохранить"), height=30, corner_radius=3,
                      fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_MAIN, command=keep).pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkButton(dlg, text=_tr("Закрыть"), height=26, corner_radius=3,
                      fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_MAIN, command=dlg.destroy).pack(fill="x", padx=16,
                                                                            pady=(0, 12))
        # окно по высоте содержимого — без пустого «подвала» (Ярослав, 04.11.26)
        dlg.update_idletasks()
        try:
            dlg.geometry(f"440x{max(200, dlg.winfo_reqheight())}")
            _center_on_parent(dlg)
        except Exception:
            pass

    def _qwen_settings_dialog(self):
        """⚙ Настройки движка Qwen: устройство, точность, язык, сэмплирование, память."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Настройки Qwen3-TTS"))
        dlg.geometry("400x560")
        _center_on_parent(dlg)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)   # фон окна в палитре приложения
        try:
            dlg.attributes("-topmost", True)
            dlg.after(500, lambda: dlg.attributes("-topmost", False))
        except Exception:
            pass

        def row():
            f = ctk.CTkFrame(dlg, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=3)
            f.grid_columnconfigure(0, weight=1)
            return f

        def label(parent, text, font=FONT_SMALL):
            ctk.CTkLabel(parent, text=text, font=font, text_color=COLOR_TEXT_SEC,
                         anchor="w").grid(row=0, column=0, sticky="w")

        def menu(parent, values, var, width=120):
            ctk.CTkOptionMenu(parent, values=values, variable=var, width=width, height=26,
                              corner_radius=3, font=FONT_TINY, fg_color=COLOR_CARD2,
                              button_color=COLOR_FILL_SOFT, button_hover_color=COLOR_SELECT,
                              text_color=COLOR_TEXT_MAIN).grid(row=0, column=1, sticky="e")

        r = row(); label(r, _tr("Устройство")); dev_var = ctk.StringVar(value=self.qwen_cfg["device"])
        menu(r, ["auto", "gpu", "cpu"], dev_var)
        r = row(); label(r, _tr("Точность")); prec_var = ctk.StringVar(value=self.qwen_cfg["precision"])
        menu(r, ["bf16", "fp16", "fp32"], prec_var)
        # живая подсказка под выбором точности (Ярослав, 05.11.26): меняем текст
        # вместе с пунктом меню — пользователь видит цену выбора до сохранения
        _ph = {
            "bf16": "Родной формат Qwen3-TTS: веса уже лежат в нём, ~3.8 ГБ видеопамяти, "
                    "широкий диапазон чисел — без «выпаданий» в шум. Ставь его, если нет особой причины.",
            "fp16": "Та же память и почти та же скорость, что bf16, но узкий диапазон чисел: "
                    "иногда возможны шум и артефакты звука. Пробуй ради скорости — появятся шумы, верни bf16.",
            "fp32": "Полная точность: вдвое больше видеопамяти (~7.6 ГБ) и медленнее. Нужна на CPU "
                    "или старых видеокартах без bf16 (GTX 10xx и старше), либо для поиска причины артефактов.",
        }
        _ph_lbl = ctk.CTkLabel(r, text="", font=FONT_TINY, text_color=COLOR_TEXT_SEC,
                               anchor="w", justify="left", wraplength=356)
        _ph_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        prec_var.trace_add("write", lambda *_x: _ph_lbl.configure(
            text=_ph.get(str(prec_var.get()).lower(), "")))
        _ph_lbl.configure(text=_ph.get(str(prec_var.get()).lower(), ""))
        r = row(); label(r, _tr("Язык")); lang_var = ctk.StringVar(value=self.qwen_cfg["language"])
        menu(r, QWEN_LANGS, lang_var, width=140)
        r = row(); label(r, _tr("Фиксированное зерно"))
        fixed_var = ctk.BooleanVar(value=bool(self.qwen_fixed_var.get()))
        ctk.CTkSwitch(r, text="", variable=fixed_var).grid(row=0, column=1, sticky="e")
        r = row(); label(r, _tr("Зерно (0 — каждый дуб новый)"))
        seed_e = ctk.CTkEntry(r, width=120, height=26, corner_radius=3, font=FONT_TINY,
                              fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                              text_color=COLOR_TEXT_MAIN)
        seed_e.insert(0, self.qwen_seed_var.get() or "0")
        seed_e.grid(row=0, column=1, sticky="e")
        num_fields = {}
        for key, text in (("max_new_tokens", _tr("Максимум токенов на фразу")),
                          ("top_k", "top_k"), ("top_p", "top_p"),
                          ("temperature", "temperature"),
                          ("repetition_penalty", "repetition_penalty")):
            r = row(); label(r, text, font=FONT_TINY)
            e = ctk.CTkEntry(r, width=90, height=24, corner_radius=3, font=FONT_TINY,
                             fg_color=COLOR_CARD2, border_width=1, border_color=COLOR_BORDER,
                             text_color=COLOR_TEXT_MAIN)
            e.insert(0, str(self.qwen_cfg[key]))
            e.grid(row=0, column=1, sticky="e")
            num_fields[key] = e
        r = row(); label(r, _tr("Освобождать память после озвучки"))
        free_var = ctk.BooleanVar(value=bool(self.qwen_cfg.get("free_after")))
        ctk.CTkSwitch(r, text="", variable=free_var).grid(row=0, column=1, sticky="e")
        r = row(); label(r, _tr("Размер движка"))
        size_seg = SegmentToggle(r, values=["0.6B", "1.7B"], height=26, btn_width=70)
        size_seg.set(self.qwen_size if self.qwen_size in ("0.6B", "1.7B") else "1.7B")
        size_seg.grid(row=0, column=1, sticky="e")

        def save():
            try:
                if size_seg.get() in ("0.6B", "1.7B"):
                    # переключение через общую процедуру: если модели нет — предложим скачать
                    self._qwen_switch_size(size_seg.get())
            except Exception:
                pass
            changed = (dev_var.get() != self.qwen_cfg["device"]
                       or prec_var.get() != self.qwen_cfg["precision"])
            self.qwen_cfg["device"] = dev_var.get()
            self.qwen_cfg["precision"] = prec_var.get()
            self.qwen_cfg["language"] = lang_var.get()
            lim = {"max_new_tokens": (64, 2048, int), "top_k": (1, 200, int),
                   "top_p": (0.1, 1.0, float), "temperature": (0.1, 2.0, float),
                   "repetition_penalty": (0.5, 2.0, float)}
            for key, (lo, hi, cast) in lim.items():
                try:
                    self.qwen_cfg[key] = max(lo, min(hi, cast(num_fields[key].get())))
                except Exception:
                    pass
            self.qwen_fixed_var.set(bool(fixed_var.get()))
            try:
                self.qwen_seed_var.set(str(max(0, min(2_000_000_000, int(seed_e.get() or 0)))))
            except Exception:
                pass
            self.qwen_cfg["free_after"] = bool(free_var.get())
            if changed:
                self._qwen_free()   # смена устройства/точности — модель перезагрузится
            self.save_settings()
            self.update_status(_tr("✅ Настройки Qwen сохранены."))
            dlg.destroy()

        ctk.CTkButton(dlg, text="💾 " + _tr("Сохранить"), height=30, corner_radius=3,
                      fg_color=COLOR_FILL_SOFT, hover_color=COLOR_BORDER,
                      text_color=COLOR_TEXT_MAIN, command=save).pack(fill="x", padx=16, pady=(10, 12))
        # после удаления кнопок окно стало длиннее содержимого — подгоняем под него
        dlg.update_idletasks()
        try:
            dlg.geometry(f"400x{max(200, dlg.winfo_reqheight())}")
            _center_on_parent(dlg)
        except Exception:
            pass

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
        self._translate_instruction()   # название уровня и сам промпт — на одном языке
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
                "emo_auto": bool(self.emo_auto_var.get() if self.current_engine in ("Vox", "Qwen")
                                  else self._emo_pref),
                "custom_voices": self.custom_voices,
                "engine_voices": self.engine_voices,
                "ctx_choices": self.ctx_choices,
                "speech_rate": self.speech_rate,
                "vox_fast": bool(self.vox_fast_var.get()),
                "qwen_cfg": dict(self.qwen_cfg),
                "qwen_size": self.qwen_size,
                "setup_preview": bool(getattr(self, "setup_preview", False)),
                "setup_done": bool(getattr(self, "setup_done", False)),
                "qwen_instruct": (self.qwen_instruct.get()
                                  if getattr(self, "qwen_instruct", None) is not None else ""),
                "qwen_seed_fixed": self._qwen_seed_saved(),
                "qwen_seed_on": bool(self.qwen_fixed_var.get()),
                "llm_gpu": bool(self.llm_gpu_var.get()),
                "external_llms": self.external_llms,
                "geometry": self.geometry(),
                "ui_lang": UI_LANG,
                "donate_done": bool(getattr(self, "donate_done", False)),
                "model_offer_muted": bool(getattr(self, "model_offer_muted", False)),
                "voices_seeded": bool(getattr(self, "voices_seeded", False)),
                "builtin_vox_seeded": bool(getattr(self, "builtin_vox_seeded", False)),
                "seeded_builtin_voices": list(getattr(self, "seeded_builtin_voices", None) or []),
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
        # у старых голосов метки движка нет: instruct — дизайн Qwen, остальные — Vox.
        # пустой слот не мигрируем: он достанется тому движку, который первым запишет
        if info.get("path") and info.get("engine") not in ("Vox", "Qwen"):
            info["engine"] = "Qwen" if info.get("instruct") else "Vox"
        return info

    def load_settings(self):
        try:
            if not os.path.exists(self.SETTINGS_FILE):
                self._apply_engine("Piper")        # первый запуск — Piper по умолчанию
                self.preset_menu.set("Кратко (50%)")
                self.apply_preset("Кратко (50%)")
                self._seed_builtin_vox_voices()    # «Алсу» — сразу в слоте
                self.update_status("✅ Готово. Вставьте ссылку на статью или видео, текст или файл.")
                return
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._apply_engine("Vox")
            self.preset_menu.set("Кратко (50%)")
            self.apply_preset("Кратко (50%)")
            self._seed_builtin_vox_voices()
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
        ev = data.get("engine_voices")
        if isinstance(ev, dict):
            self.engine_voices = {k: v for k, v in ev.items()
                                  if k in ("Vox", "Qwen", "Piper") and isinstance(v, str) and v}

        # встроенные голоса («Алсу», «Джон»): добавляем в свободные слоты, если их ещё нет
        # (до _apply_engine — список голосов он построит уже с ними)
        self.builtin_vox_seeded = bool(data.get("builtin_vox_seeded", False))
        self.seeded_builtin_voices = [str(x) for x in (data.get("seeded_builtin_voices") or [])
                                      if str(x).strip()]
        self._seed_builtin_vox_voices()

        cc = data.get("ctx_choices")
        if isinstance(cc, dict):
            self.ctx_choices = cc

        self.auto_play_var.set(bool(data.get("auto_play", False)))
        self._emo_pref = bool(data.get("emo_auto", False))
        self.emo_auto_var.set(self._emo_pref and self.current_engine == "Vox")
        self.model_offer_muted = bool(data.get("model_offer_muted", False))
        self.voices_seeded = bool(data.get("voices_seeded", False))
        self.vox_offer_done = bool(data.get("vox_offer_done", False))
        self.qwen_size = str(data.get("qwen_size") or "1.7B")
        if self.qwen_size not in ("0.6B", "1.7B"):
            self.qwen_size = "1.7B"
        self.setup_preview = bool(data.get("setup_preview", False))
        self.setup_done = bool(data.get("setup_done", False))

        rate = data.get("speech_rate", 1.0)
        try:
            rate = round(min(1.5, max(0.5, float(rate))), 1)
        except Exception:
            rate = 1.0
        self.speech_rate = rate
        self.rate_slider.set(rate)
        self.rate_label.configure(text=f"×{rate:.1f}")
        self.vox_fast_var.set(bool(data.get("vox_fast", False)))
        qc = data.get("qwen_cfg")
        if isinstance(qc, dict):   # подкрученные параметры движка Qwen
            for key in ("device", "precision", "language"):
                if isinstance(qc.get(key), str):
                    self.qwen_cfg[key] = qc[key]
            for key, lo, hi, cast in (("max_new_tokens", 64, 2048, int), ("top_k", 1, 200, int),
                                      ("top_p", 0.1, 1.0, float), ("temperature", 0.1, 2.0, float),
                                      ("repetition_penalty", 0.5, 2.0, float)):
                try:
                    self.qwen_cfg[key] = max(lo, min(hi, cast(qc.get(key, self.qwen_cfg[key]))))
                except Exception:
                    pass
        # legacy-ключ qwen_instruct больше не вставляем: строка в карточке — зеркало
        # паспорта голоса, оно заполнится при выборе голоса/движка (в readonly нельзя и programmatically)
        try:
            self.qwen_seed_var.set(str(max(0, min(2_000_000_000, int(data.get("qwen_seed_fixed", 0) or 0)))))
        except Exception:
            pass
        self.qwen_fixed_var.set(bool(data.get("qwen_seed_on", False)))
        self.llm_gpu_var.set(bool(data.get("llm_gpu", False)))
        self._update_gpu_labels()

        engine = data.get("engine", "Piper")   # по умолчанию — Piper: работает без дополнений
        if engine not in ("Piper", "Vox", "Qwen"):
            engine = "Piper"
        if engine == "Qwen" and not self._qwen_installed():
            engine = "Piper"                   # пакет qwen-tts не установлен — тихий откат
        if engine == "Vox" and not self._vox_installed():
            engine = "Piper"                   # дополнение Vox не поставлено — молча на Piper
        self._apply_engine(engine)

        voice = data.get("tts_voice")
        allowed = list(self.tts_combo.cget("values"))
        if voice and voice in allowed:
            self.tts_combo.set(voice)
            self.current_tts_name = voice
            self.engine_voices.setdefault(engine, voice)
            self._sync_qwen_instruct()

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
            self._translate_instruction()   # промпт мог сохраниться на другом языке
        else:
            self.apply_preset(preset)

        self.update_status(f"✅ Настройки восстановлены: {engine}, «{self.tts_combo.get()}».")

    def _apply_engine(self, value):
        self.current_engine = value
        if value == "Piper":
            self.engine_menu.set("Piper (CPU)")
        elif value == "Vox":
            self.engine_menu.set("Vox (GPU)")
        elif value == "Qwen":
            self.engine_menu.set("Qwen (GPU)")
        hint = getattr(self, "engine_hint", None)
        if hint is not None:
            if value == "Vox":
                hint.configure(text=_tr("⚠ Vox требует видеокарту с 8 ГБ видеопамяти"),
                               text_color=COLOR_TEXT_MAIN)
            elif value == "Qwen":
                hint.configure(text=_tr("⚠ Qwen требует видеокарту с 6 ГБ видеопамяти"),
                               text_color=COLOR_TEXT_MAIN)
            else:
                hint.configure(text=_tr("Piper: процессор, видеокарта не нужна"),
                               text_color=COLOR_TEXT_SEC)
        if value == "Qwen":
            self._show_piper_import(False)
            self._ensure_empty_slot()
            names = self._qwen_combo_values()
            self.tts_combo.configure(values=names)
            cur = self.engine_voices.get("Qwen") or ""      # голос, выбранный на Qwen раньше
            if cur not in names:
                cur = self.current_tts_name if self.current_tts_name in names else ""
            if not cur:
                tv = self.tts_combo.get()
                cur = tv if tv in names else "Вивиан"
            if cur:
                self.tts_combo.set(cur)
                self.current_tts_name = cur
        elif value == "Vox":
            self._show_custom_voice(True)
            self._show_piper_import(False)
            self._ensure_empty_slot()
            names = self.voice_values("Vox")
            self.tts_combo.configure(values=names)
            cur = self.engine_voices.get("Vox") or ""       # голос, выбранный на Vox раньше
            if cur not in names:
                cur = self.current_tts_name if self.current_tts_name in names else ""
            if not cur:
                vid, info = self._first_empty_voice()
                filled = [i.get("name") for _, i in self._voice_items()
                          if isinstance(i, dict) and i.get("path") and os.path.exists(i.get("path") or "")
                          and self._voice_engine(i) == "Vox"]
                cur = filled[-1] if filled else (info.get("name") if info else (names[0] if names else ""))
            if cur:
                self.tts_combo.set(cur)
                self.current_tts_name = cur
        elif value == "Piper":
            self._show_custom_voice(False)
            self._show_piper_import(True)
            self.tts_combo.configure(values=sorted(self.tts_models.keys()))
            names = sorted(self.tts_models.keys())
            default = next((n for n in names if "irina" in n.lower()), names[0] if names else "")
            self.tts_combo.set(default)
            self.current_tts_name = default or None
            if default:
                self.engine_voices["Piper"] = default
                self.load_tts_on_select()
        self._show_qwen_tools(value == "Qwen")
        self._sync_emo_auto()

    def _sync_emo_auto(self):
        """«Добавить эмоции» имеет смысл только на Vox: на Piper переключатель гаснет."""
        cb = getattr(self, "emo_auto_cb", None)
        if cb is None:
            return
        if self.current_engine in ("Vox", "Qwen"):
            cb.configure(state="normal")
            self.emo_auto_var.set(bool(self._emo_pref))
        else:
            self._emo_pref = bool(self.emo_auto_var.get())
            cb.configure(state="disabled")
            self.emo_auto_var.set(False)

    def _on_emo_auto_toggle(self):
        """Включили «Добавить эмоции»: предупреждаем, если у голоса нет записанных эмоций."""
        self._emo_pref = bool(self.emo_auto_var.get())
        self.save_settings()
        if not self.emo_auto_var.get():
            return
        names = self._auto_emotion_names(self.tts_combo.get())
        if names:
            if self.current_engine == "Qwen":
                self.update_status("🎭 Разметю текст эмоциями — у Qwen весь справочник без записей")
            else:
                self.update_status("🎭 Разметю текст эмоциями: " + ", ".join(names))
        else:
            messagebox.showinfo(
                _tr("Добавить эмоции"),
                _tr("У голоса «{v}» пока нет записанных эмоций.\n\n"
                    "Нажми «🎙 Образец голоса» → «😊 Эмоции» и синтезируй их кнопкой ✨: "
                    "только записанные эмоции нейросеть и сможет ставить в скобках."
                    ).format(v=self.tts_combo.get()))

    def _auto_emotion_names(self, speaker):
        """Эмоции, которые реально сработают для этого голоса (образец записан)."""
        if self.current_engine == "Qwen":
            # Qwen не требует образцов-эмоций: маркеры из всего справочника
            # движок сам превращает в интонацию (_split_emotion_segments_qwen)
            return list(EMOTION_TAB.keys())
        if self.current_engine != "Vox":
            return []
        names = []
        for label, _path, _text in self._emotion_samples(speaker).values():
            if label not in names:
                names.append(label)
        return names

    _MARKER_LIKE = re.compile(r"\(\s*([A-Яа-яЁёA-Za-z][A-Яа-яЁёA-Za-z\s,;:-]{0,39})\s*\)")

    def _strip_unknown_markers(self, text, speaker):
        """Маркер эмоции, которой нет у голоса, вырезаем: иначе синтез прочитает
        «(радостный)» словами вместо интонации."""
        if self.current_engine == "Qwen":
            # у Qwen эмоции задаются инструкцией, а не образцом — годится весь справочник
            emos = {self._emo_stem(k): (k, "", "") for k in EMOTION_TAB}
        else:
            emos = self._emotion_samples(speaker)

        def fix(m):
            word = (re.split(r"[\s,;:]+", m.group(1).strip()) or [""])[0]
            return m.group(0) if word and emos.get(self._emo_stem(word)) else ""

        out = self._MARKER_LIKE.sub(fix, text or "")
        return re.sub(r"[ \t]{2,}", " ", out).strip()

    def _actual_llm(self):
        return self.llm_display.get(self.llm_combo.get(), self.llm_combo.get())

    # ================= ОТМЕНА =================

    def cancel_processes(self):
        self.cancel_event.set()
        # is_processing НЕ снимаем: рабочий поток ещё в цикле. Если разрешить запуск
        # сразу, второй поток дёрнет ту же модель — llama.cpp падает с GGML_ASSERT
        # (проверено: два потока на одном Llama = SIGSEGV). Флаг снимет finally потока.
        self.after(0, self.progress_bar.stop)
        self.after(0, lambda: self.update_status("⏹ Останавливаю…"))

    # ================= ОБРАБОТЧИКИ =================

    def on_engine_change(self, value):
        if value.startswith("Qwen"):
            eng = "Qwen"
        elif value.startswith("Vox"):
            eng = "Vox"
        else:
            eng = "Piper"
        if eng == "Qwen" and not self._qwen_installed():
            if self._vox_installed() and messagebox.askyesno(
                    _tr("Движок Qwen"),
                    _tr("Пакет qwen-tts не установлен. Скачать и установить его? (≈30 МБ)")):
                self._apply_engine("Qwen")
                self.save_settings()

                def qwork():
                    ok, out = self._qwen_pip_install()
                    if ok:
                        self._safe_ui(lambda: self.update_status(
                            _tr("✅ Пакет Qwen3-TTS установлен.")))
                        self._safe_ui(self._qwen_prepare)
                    else:
                        self._safe_ui(lambda out=out: self.update_status(
                            f"❌ qwen-tts: {out[-140:]}"))

                        def back():
                            self.engine_menu.set("Piper (CPU)")
                            self._apply_engine("Piper")
                            self.save_settings()
                        self._safe_ui(back)
                threading.Thread(target=qwork, daemon=True).start()
            else:
                self.engine_menu.set("Piper (CPU)")
                self._apply_engine("Piper")
                self.save_settings()
                messagebox.showwarning(
                    _tr("Движок Qwen"),
                    _tr("Пакет qwen-tts не установлен — движок Qwen недоступен. "
                        "Сначала нужна GPU-среда (движок Vox или первичная установка)."))
            return
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
        elif eng == "Qwen":
            self.update_status("Движок: Qwen3-TTS (GPU).")
            self._qwen_prepare()
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
        self.refresh_model_info()     # оценка памяти зависит от режима (ОЗУ/VRAM)
        if not self.llm_gpu_var.get():
            self._stop_gpu_server()
            self.update_status("Режим: процессор (CUDA выключена)")
            return
        if not self._gpu_binary():
            self._offer_cuda_download()
            return
        self.update_status("Режим: видеокарта (CUDA)")

    # ---------------- CUDA-сборка llama.cpp: авто-докачка ----------------
    # Та же сборка, что лежит в dev-папке tools/llama-cuda (проверена на NVIDIA RTX).
    # Сборка и CUDA-рантайм (cublas/cudart) — два отдельных архива на GitHub.
    LLAMA_CUDA_TAG = "b11829"
    LLAMA_CUDA_ZIPS = (
        ("llama-cuda-main.zip",
         "https://github.com/ggml-org/llama.cpp/releases/download/b11829/"
         "llama-b11829-bin-win-cuda-12.4-x64.zip", 273_000_000),
        ("llama-cuda-cudart.zip",
         "https://github.com/ggml-org/llama.cpp/releases/download/b11829/"
         "cudart-llama-bin-win-cuda-12.4-x64.zip", 391_000_000),
    )

    def _gpu_rollback(self):
        """CUDA-сборка не получена — переключаем режим обратно на процессор."""
        self.llm_gpu_var.set(False)
        self._update_gpu_labels()
        self.save_settings()

    def _has_nvidia(self):
        return bool(shutil.which("nvidia-smi"))

    def _cuda_wanted(self):
        """Нужна ли сборка видеокарты в пакет модели: NVIDIA есть, самой сборки нет."""
        return self._has_nvidia() and not self._gpu_binary()

    def _fetch_cuda_pack(self, cb, cancel, on_extract=None):
        """Общее: качает оба архива в tools/ и распаковывает в tools/llama-cuda.
        cb(номер_файла, скачано, всего) — прогресс. True — сборка на месте,
        False — скачивание отменено. Оборванное продолжается с места (.part)."""
        import zipfile
        zips = self.LLAMA_CUDA_ZIPS
        tools = os.path.join(self.BASE_DIR, "tools")
        target = os.path.join(tools, "llama-cuda")
        os.makedirs(target, exist_ok=True)
        for i, (zname, url, _approx) in enumerate(zips):
            if not self._fetch_file(url, os.path.join(tools, zname),
                                    on_bytes=(lambda d, t, _i=i: cb(_i, d, t)),
                                    cancel=cancel):
                return False
        if on_extract is not None:
            try:
                on_extract()
            except Exception:
                pass
        for zname, _url, _approx in zips:
            zp = os.path.join(tools, zname)
            with zipfile.ZipFile(zp) as z:
                for n in z.namelist():
                    parts = n.replace("\\", "/").split("/")
                    if not parts[-1] or ".." in parts:
                        continue
                    with z.open(n) as src, open(os.path.join(target, parts[-1]), "wb") as dst:
                        shutil.copyfileobj(src, dst, 262144)
            os.remove(zp)
        return self._gpu_binary()

    def _offer_cuda_download(self):
        """GPU включили, а сборки нет. NVIDIA есть — докачиваем сами сразу, без
        предложений (сборка ставится один раз — она идёт в пакете вместе с моделью ИИ).
        NVIDIA нет — докачка не поможет: возвращаем режим на процессор."""
        if not self._has_nvidia():
            messagebox.showwarning(
                _tr("Видеокарта"),
                _tr("Для режима «Видеокарта» нужна видеокарта NVIDIA — она не найдена.\n"
                    "Режим возвращён на процессор."))
            self._gpu_rollback()
            return
        old = getattr(self, "_cuda_dialog", None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except Exception:
            pass

        dlg = ctk.CTkToplevel(self)
        dlg.title(_tr("Видеокарта"))
        dlg.geometry("540x330")
        _center_on_parent(dlg)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.configure(fg_color=COLOR_BG)
        _apply_dialog_icon(dlg)
        dlg.after(150, lambda: _apply_dialog_icon(dlg))
        self._cuda_dialog = dlg
        self._cuda_cancel = threading.Event()
        self._cuda_thread = None

        def _on_close(event=None):
            if event is None or getattr(event, "widget", None) is dlg:
                self._cuda_cancel.set()
                if not self._gpu_binary():
                    self._gpu_rollback()

        dlg.bind("<Destroy>", _on_close)

        body = ctk.CTkFrame(dlg, fg_color=COLOR_PANEL, corner_radius=R_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(body, text=_tr("Нужна CUDA-сборка llama.cpp"), font=FONT_SUBHEADER,
                     text_color=COLOR_HEAD).pack(pady=(16, 4))
        ctk.CTkLabel(body, justify="left", wraplength=470, font=FONT_TINY,
                     text_color=COLOR_TEXT_SEC,
                     text=_tr("llama.cpp для видеокарт NVIDIA, ≈630 МБ — докачивается автоматически "
                              "и только один раз.\nМожно отменить: тогда режим вернётся на процессор.")
                     ).pack(padx=16, anchor="w")

        bar = ctk.CTkProgressBar(body, height=10, corner_radius=6, progress_color="#c6763a",
                                 fg_color=COLOR_CARD2)
        bar.set(0)
        bar.pack(fill="x", padx=16, pady=(16, 6))
        info = ctk.CTkLabel(body, text=_tr("Сборка не скачана"), font=FONT_TINY,
                            text_color=COLOR_TEXT_SEC)
        info.pack(anchor="w", padx=16)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(12, 14), side="bottom")

        btn_go = ctk.CTkButton(row, text=_tr("Отмена"), width=150, height=34,
                               corner_radius=R_PANEL, font=FONT_SUBHEADER,
                               fg_color="#c6763a", hover_color="#a95f2c",
                               text_color="#ffffff",
                               command=lambda: self._start_cuda_download(dlg, bar, info, btn_go))
        btn_go.pack(side="left")
        self._start_cuda_download(dlg, bar, info, btn_go)

    def _start_cuda_download(self, dlg, bar, info, btn):
        if self._cuda_thread is not None and self._cuda_thread.is_alive():
            self._cuda_cancel.set()
            btn.configure(text=_tr("Отмена…"), state="disabled")
            return
        self._cuda_cancel = threading.Event()
        btn.configure(text=_tr("Отмена"))
        self._cuda_thread = threading.Thread(target=self._download_cuda_pack,
                                             args=(dlg, bar, info, btn), daemon=True)
        self._cuda_thread.start()

    def _download_cuda_pack(self, dlg, bar, info, btn):
        """Качает сборку и CUDA-рантайм в tools/, распаковывает в tools/llama-cuda."""
        zips = self.LLAMA_CUDA_ZIPS
        total_all = sum(a for _, _, a in zips)

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

        drawn = [0.0]

        def cb(i, d, t):
            now = time.time()
            if now - drawn[0] > 0.25 or d >= t:
                drawn[0] = now
                acc = sum(a for _, _, a in zips[:i]) + d
                pct = acc / total_all if total_all else 0
                self._ui(set_info, f"{i + 1}/{len(zips)} · {d / 1048576:,.0f} / "
                                   f"{t / 1048576:,.0f} " + _tr("МБ") +
                         f" · {pct * 100:.0f}%")
                self._ui(bar.set, min(pct, 1.0))

        try:
            if not self._fetch_cuda_pack(cb, self._cuda_cancel,
                                         on_extract=lambda: self._ui(set_info,
                                                                     _tr("Распаковка…"))):
                if not self._cuda_cancel.is_set():
                    raise Exception(_tr("Сборка не найдена после распаковки"))
                self._ui(set_btn, _tr("Продолжить"))
                self._ui(set_info, _tr("Загрузка остановлена — можно продолжить позже"))
                self._gpu_rollback()
                return
            self._ui(bar.set, 1.0)
            try:
                if dlg.winfo_exists():
                    dlg.destroy()
            except Exception:
                pass
            self.after(0, lambda: self.update_status("✅ " + _tr("CUDA-сборка установлена")))
        except Exception as e:
            self._ui(set_info, f"{_tr('Ошибка загрузки')}: {e}")
            self._ui(set_btn, _tr("Повторить"))
            self._gpu_rollback()

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
        elif self.current_engine == "Qwen":
            if value in QWEN_DISPLAY:
                _sid, _gen, desc = QWEN_BY_DISPLAY[value]
                self.current_tts_name = value
                self.update_status(f"✅ Голос «{value}» — встроенный Qwen ({desc})")
                self._sync_qwen_instruct()
            else:
                vid, info = self._find_voice(value)
                if info is None:
                    return
                path = info.get("path") or ""
                if not path or not os.path.exists(path):
                    self.add_custom_voice(initial_slot=value)  # пустой слот — сразу на запись
                    return
                self.current_tts_name = value
                self.update_status(f"✅ Голос «{value}» — клон Qwen по образцу")
                self._sync_qwen_instruct()
        elif self.current_engine == "Vox":
            vid, info = self._find_voice(value)
            if info is None:
                return
            path = info.get("path") or ""
            if not path or not os.path.exists(path):
                self.add_custom_voice(initial_slot=value)  # пустой слот — сразу на запись
                return
            self.current_tts_name = value
            emos = [lbl for lbl, _p, _t in self._emotion_samples(value).values()]
            hint = f" · эмоции: {', '.join(emos)}" if emos else ""
            self.update_status(f"✅ Голос «{value}» активен{hint}")
        if value:
            self.engine_voices[self.current_engine] = value   # у каждого движка свой голос
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
        self.voice_dialog = VoiceRecorderDialog(self, self._apply_custom_voice, vid,
                                                info.get("name"), self.custom_voices)

    def _apply_custom_voice(self, path, text, slot_id, name, engine=None):
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
        prev = self.custom_voices.get(slot_id)
        info = {"name": name, "path": path, "text": text}
        if isinstance(prev, dict) and prev.get("samples"):
            info["samples"] = prev["samples"]   # эмоции живут в том же слоте — не теряем
        if isinstance(prev, dict) and prev.get("instruct"):
            info["instruct"] = prev["instruct"] # паспорт дизайн-голоса — не теряем
        # голос принадлежит движку, под которым записан: списки голосов разделены (Ярослав 05.11)
        eng = engine if engine in ("Vox", "Qwen") else (
            self.current_engine if self.current_engine in ("Vox", "Qwen") else "Vox")
        info["engine"] = eng
        self.custom_voices[slot_id] = info
        self._ensure_empty_slot()  # после записи появляется следующий пустой слот
        if self.current_engine == "Qwen":
            self.tts_combo.configure(values=self._qwen_combo_values())
        elif self.current_engine == "Vox":
            self.tts_combo.configure(values=self.voice_values("Vox"))
        if eng == self.current_engine:
            # голос сохранён для текущего движка — сразу делаем его текущим
            self.tts_combo.set(name)
            self.current_tts_name = name
            self.engine_voices[self.current_engine] = name
        else:
            self.update_status(f"✅ Голос «{name}» сохранён для движка {eng}")
        self.update_status(f"✅ Голос «{name}» сохранён")
        self.save_settings()

    def _delete_voice(self, vid=None, name=None):
        """Убрать свой голос из списка (Vox/Qwen): указанный слот vid+name или
        текущий выбранный. Файл образца сносим, только если он лежит в
        хранилище приложения; чужие файлы не трогаем."""
        try:
            if vid is None:
                name = self.tts_combo.get()
                vid, info = self._find_voice(name)
            else:
                vid = str(vid)
                info = self.custom_voices.get(vid)
                name = name or (info or {}).get("name") or ""
            if vid is None or not isinstance(info, dict) or not info.get("path"):
                return
            if not messagebox.askyesno(_tr("Удалить"),
                                       f"{_tr('Удалить голос')} «{name}»?", parent=self):
                return
            path = (info.get("path") or "").strip()
            gone = ""
            try:
                p = os.path.abspath(path)
                root_app = os.path.abspath(self.BASE_DIR)
                inside = p.lower().startswith(root_app.lower() + os.sep)
                builtin = (os.sep + "voices_builtin" + os.sep).lower() in p.lower()
                if inside and not builtin and os.path.isfile(p):
                    os.remove(p)
                    gone = f" {_tr('(образец-файл тоже удалён)')}"
            except Exception:
                pass
            del self.custom_voices[vid]
            self.engine_voices = {k: v for k, v in self.engine_voices.items() if v != name}
            if self.current_tts_name == name:
                self.current_tts_name = None
            self._ensure_empty_slot()
            eng = self.current_engine
            names = (self._qwen_combo_values() if eng == "Qwen"
                     else self.voice_values("Vox") if eng == "Vox" else [])
            self.tts_combo.configure(values=names)
            filled = [i.get("name") for _, i in self._voice_items()
                      if isinstance(i, dict) and i.get("path")
                      and os.path.exists(i.get("path") or "")
                      and self._voice_engine(i) == eng]
            nxt = filled[-1] if filled else (names[0] if names else "")
            if nxt:
                self.tts_combo.set(nxt)
                self.current_tts_name = nxt
                self.engine_voices[eng] = nxt
                if eng == "Qwen":
                    self._sync_qwen_instruct()
            self.save_settings()
            self.update_status(f"🗑 {_tr('Голос удалён')}: {name}{gone}")
            return True
        except Exception as e:
            self.update_status(f"❌ Ошибка: {e}")
        return False

    def _apply_emotion_voice(self, path, text, slot_id, label):
        """Сохранить образец эмоции внутри существующего голоса."""
        slot_id = str(slot_id)
        info = self.custom_voices.get(slot_id)
        if not isinstance(info, dict):
            return
        label = (label or "").strip()
        if not label:
            return
        samples = info.get("samples")
        if not isinstance(samples, dict):
            samples = info["samples"] = {}
        stem = self._emo_stem(label)
        for old in [k for k in samples if self._emo_stem(k) == stem and k != label]:
            samples.pop(old, None)          # «радостно» и «радостный» — одна эмоция, перезапись
        _sample = VoiceRecorderDialog.DEFAULT_TEXT
        if text.strip() in (_tr(_sample), _sample):
            text = _sample
        samples[label] = {"path": path, "text": text}
        self.update_status(f"✅ Эмоция «{label}» добавлена к голосу «{info.get('name')}»")
        self.save_settings()

    # ---------------- панель эмоций (правая колонка, Vox) ----------------

    # русское название эмоции (по 5 первым буквам, как _emo_stem) ->
    # инструкция для VoxCPM2 на английском (контролируемое клонирование:
    # тембр из нейтрального образца, интонация — из описания в скобках)
    EMOTION_INSTR = {_emo_key(n): i for n, (i, _) in EMOTION_TAB.items()}

    # ---------------- эмоции голоса (API для колонки в окне «Образец голоса») ----------------

    _emo_busy = False
    voice_dialog = None     # открытое окно «Образец голоса» — обновляем колонку после синтеза

    def _refresh_voice_dialog(self):
        d = self.voice_dialog
        try:
            if d is not None and d.winfo_exists():
                d._refresh_emotions()
        except Exception:
            pass

    def _emo_neutral(self, slot_id):
        """Нейтральный образец слота (путь, текст) — база для синтеза эмоции."""
        info = self.custom_voices.get(str(slot_id)) or {}
        path = info.get("path") or ""
        if not path or not os.path.exists(path):
            return None
        return path, (info.get("text") or VoiceRecorderDialog.DEFAULT_TEXT)

    def refresh_emotion_rows(self, rows, slot_id):
        """Окно образца спрашивает, что уже есть в слоте по эмоциям."""
        info = self.custom_voices.get(str(slot_id)) or {}
        samples = info.get("samples") or {}
        for row in rows:
            label = (row["ent"].get() or "").strip()
            row["label"] = label
            if not label:
                row["stat"].configure(text="— " + _tr("не задана"))
                for b in (row["rec"], row["syn"], row["del"]):
                    b.configure(state="disabled")
                continue
            smp = samples.get(label)
            if smp and os.path.exists(smp.get("path") or ""):
                row["stat"].configure(text="✅ " + _tr("записана"))
                for b in (row["rec"], row["syn"], row["del"]):
                    b.configure(state="normal")
            else:
                row["stat"].configure(text="— " + _tr("не записана"))
                row["rec"].configure(state="normal")
                row["syn"].configure(state="normal")
                row["del"].configure(state="disabled")

    def emotion_synth(self, slot_id, label):
        """Синтез эмоционального образца нейросетью из нейтрального образца этого голоса."""
        if self._emo_busy:
            self.update_status(_tr("Синтез идёт — подожди."))
            return
        if self.current_engine != "Vox":
            self.update_status("❌ " + _tr("Эмоции синтезирует движок Vox — переключитесь на него."))
            return
        base = self._emo_neutral(slot_id)
        if base is None:
            self.update_status("❌ " + _tr("Сначала запишите нейтральный образец голоса."))
            return
        label = (label or "").strip()
        instr = self.EMOTION_INSTR.get(self._emo_stem(label))
        if not instr:
            self.update_status("❌ " + _tr("Не знаю такую эмоцию. Напиши: радостный, грустный, злой…"))
            return
        ref_wav, ref_text = base
        _lang = "en" if VoiceRecorderDialog._is_english(ref_text) else "ru"
        phrase = VoiceRecorderDialog._emo_sample_text(label, lang=_lang)
        if phrase in (VoiceRecorderDialog._EMO_FALLBACK_RU, VoiceRecorderDialog._EMO_FALLBACK_EN):
            phrase = ref_text      # эмоция вне справочника — берём текст самого образца
        self._emo_busy = True
        self.update_status(f"⏳ {_tr('Синтез эмоции')} «{label}»...")

        def work():
            try:
                if not self.load_vox(show_errors=True):
                    raise Exception(_tr("VoxCPM2 недоступна"))
                m = self.vox_model
                text = f"({instr}){phrase}"
                out, last = None, None
                for kw in ({"cfg_value": 2.0, "inference_timesteps": 10},
                           {"cfg_value": 2.0}, {}):
                    try:
                        out = m.generate(text=text, reference_wav_path=ref_wav, **kw)
                        break
                    except TypeError as e:
                        last = e
                    except Exception as e:
                        last = e
                        break
                if out is None:
                    raise Exception(f"VoxCPM2: {last}")
                arr, sr = self._vox_to_int16(out)
                if len(arr):
                    f32 = arr.astype(np.float32) / 32768.0
                    peak = float(np.max(np.abs(f32)))
                    if peak > 0.95:
                        f32 *= 0.95 / peak
                    arr = (np.clip(f32, -1.0, 1.0) * 32767).astype(np.int16)
                # как просит Ярослав: та же автоподтяжка скорости, что и во всей озвучке FAIR
                if len(arr):
                    print(f"🎚 Эмоция «{label}»: {(len(arr) / sr):.2f} с → ускоряем "
                          f"×{VOX_BASE_SPEED:g}, как обычный синтез текста")
                    arr = self._stretch_int16(arr, VOX_BASE_SPEED)
                fp = os.path.join(BASE_DIR,
                                  VoiceRecorderDialog._emotion_filename(slot_id, label))
                with wave.open(fp, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(sr)
                    w.writeframes(arr.tobytes())
                secs = len(arr) / max(sr, 1)
                self.after(0, lambda: self._emotion_synth_ok(slot_id, label, fp, phrase, secs))
            except Exception as e:
                self.after(0, lambda e=e: self._emotion_synth_fail(e))

        threading.Thread(target=work, daemon=True).start()

    def _emotion_synth_ok(self, slot_id, label, fp, phrase, secs):
        self._emo_busy = False
        info = self.custom_voices.get(str(slot_id))
        if isinstance(info, dict):
            samples = info.setdefault("samples", {})
            stem = self._emo_stem(label)
            for old in [k for k in samples
                        if self._emo_stem(k) == stem and k != label]:
                samples.pop(old, None)
            samples[label] = {"path": fp, "text": phrase, "synth": True}
            self.save_settings()
        self._refresh_voice_dialog()
        self.update_status(f"✨ «{label}» — {_tr('синтезирована')} ({secs:.1f} с)")

    def _emotion_synth_fail(self, err):
        self._emo_busy = False
        self.update_status(f"❌ {_tr('Эмоция не синтезирована')}: {str(err)[:160]}")
        self._refresh_voice_dialog()

    def delete_emotion(self, slot_id, label):
        """Убрать эмоцию из слота (файл синтезированной эмоции тоже удаляем)."""
        info = self.custom_voices.get(str(slot_id))
        if not isinstance(info, dict):
            return
        smp = (info.get("samples") or {}).get(label)
        if not isinstance(smp, dict):
            return
        info["samples"].pop(label, None)
        try:
            p = (smp.get("path") or "").replace("\\", "/")
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        self.save_settings()
        self.update_status(f"🗑 {_tr('Эмоция')} «{label}» — {_tr('удалена')}")
        self._refresh_voice_dialog()

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

    def _add_side_edges(self, card, width=11):
        """Вертикальные «грани» карточки: полоска рамки + золотая кромка + градиент.

        Полоска рисуется по всей высоте карточки, но её низ жёстко привязан
        к нижней линии рамки: последняя строка красится цветом рамки, а всё,
        что оказалось НИЖЕ рамки из-за дробной раскладки (у карточек разная
        высота, округление даёт ±1 px), закрашивается цветом фона — перебег
        становится невидимым. Так срез замкнут и не «торчит» ни на пиксель.
        """
        try:
            base = _mode_color(COLOR_CARD)
            edge = _mode_color(COLOR_BORDER)
            bgc = _mode_color(COLOR_BG)
            dark = ctk.get_appearance_mode() == "Dark"
            outer = "#120d08" if dark else "#e0d2b4"   # тон у самого края — «срез страницы»
            hair = "#2f2419" if dark else "#cbb68d"    # золотая кромка
            paints = []
            canvases = []
            for side in ("left", "right"):
                cv = tk.Canvas(card, width=width, highlightthickness=0, bd=0, bg=base)
                # height=+1 даёт запас в одну строку ниже карточки; лишнее закрасим фоном
                if side == "left":
                    cv.place(x=0, y=1, relheight=1, height=1, width=width)
                else:
                    cv.place(relx=1, x=0, y=1, relheight=1, height=1, width=width, anchor="ne")

                def paint(_cv=cv, _side=side):
                    try:
                        h = _cv.winfo_height() or 500
                        # Строка нижней линии рамки карточки в координатах холста.
                        # Берём ГАБАРИТ реально нарисованной рамки (tag border_parts) на
                        # внутреннем холсте карточки — это единственный способ, который не
                        # зависит от округления высоты: у карточек с чётной/нечётной высотой
                        # рамка ложится то на последнюю, то на предпоследнюю строку.
                        t = None
                        try:
                            fcv = card._canvas
                            bb = fcv.bbox("inner_parts")      # фактическая заливка карточки
                            if bb:
                                # последняя залитая строка = строка нижней линии рамки
                                t = (fcv.winfo_rooty() + bb[3] - 1) - _cv.winfo_rooty()
                        except Exception:
                            t = None
                        if t is None:
                            try:
                                t = (card.winfo_rooty() + card.winfo_height() - 2) - _cv.winfo_rooty()
                            except Exception:
                                t = h - 2
                        t = max(1, min(t, h - 1))
                        _cv.delete("all")
                        for x in range(width):
                            if _side == "right":
                                d = (width - 1 - x) / max(1, width - 3)   # 0 — внешний край
                            else:
                                d = x / max(1, width - 3)
                            if d <= 0:
                                col = edge            # рамка карточки
                            elif d <= 1.0 / (width - 3):
                                col = hair            # золотая кромка
                            else:
                                col = _blend(outer, base, (d - 1.0 / (width - 3)) ** 0.7)
                            _cv.create_line(x, 0, x, t, fill=col)
                            _cv.create_line(x, t, x, t + 1, fill=edge)   # замыкаем срез
                        if t + 1 < h:
                            _cv.create_rectangle(0, t + 1, width + 1, h + 1,
                                                 fill=bgc, outline=bgc)  # перебег — в цвет фона
                    except Exception as e:
                        print(f"⚠️ грань {_side}: {e}")

                paints.append(paint)
                canvases.append(cv)
                cv.bind("<Configure>", lambda e, p=paint: p())
                paint()

            def repaint_all(event=None):
                for p in paints:
                    p()

            card.bind("<Configure>", repaint_all, add="+")
            card.after(120, repaint_all)   # после того как карточка набрала высоту
            card.after(400, repaint_all)   # контрольный проход после полной раскладки

            if os.environ.get("FAIR_DEBUG_EDGES"):
                def _dump():
                    try:
                        fcv = card._canvas
                        rec = {
                            "title": getattr(card, "_card_title", ""),
                            "card": [card.winfo_rootx(), card.winfo_rooty(),
                                     card.winfo_width(), card.winfo_height()],
                            "fcv": [fcv.winfo_rootx(), fcv.winfo_rooty(),
                                    fcv.winfo_width(), fcv.winfo_height()],
                            "bbox_border": list(fcv.bbox("border_parts") or ()),
                            "bbox_inner": list(fcv.bbox("inner_parts") or ()),
                            "strips": [[c.winfo_rootx(), c.winfo_rooty(),
                                        c.winfo_width(), c.winfo_height()] for c in canvases],
                        }
                        with open(os.path.join(tempfile.gettempdir(), "fair_edges_debug.jsonl"),
                                  "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(rec) + "\n")
                    except Exception as e:
                        print("dump:", e)
                card.after(2000, _dump)
        except Exception as e:
            print(f"⚠️ грани карточки: {e}")

    def _draw_card_head(self, cv, title, height, indent):
        """Градиент сверху вниз + подпись; перерисовывается при смене языка и размера."""
        try:
            base = _mode_color(COLOR_CARD)
            top = "#3a2c1e" if ctk.get_appearance_mode() == "Dark" else "#fffdf6"
            cv.delete("all")
            w = cv.winfo_width() or 400
            for i in range(height):
                t = (i / max(1, height - 1)) ** 1.5
                cv.create_line(0, i, w, i, fill=_blend(top, base, t))
            cv.create_line(0, 0, w, 0, fill="#b08a3c", width=1)
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
            top = "#3a2c1e" if dark else "#fffdf6"
            canvas = tk.Canvas(frame, height=height, highlightthickness=0, bd=0)
            canvas.place(x=1, y=1, relwidth=1, width=-2)
            for i in range(height):
                t = (i / max(1, height - 1)) ** 1.5
                canvas.create_line(0, i, 4000, i, fill=_blend(top, base, t))
            # плотная кромка блика
            canvas.create_line(0, 0, 4000, 0, fill="#c9b78d", width=1)
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
        table = self.PRESET_PROMPTS_EN if UI_LANG == "en" else self.PRESET_PROMPTS_RU
        prompt = table.get(choice) or self.PRESET_PROMPTS_RU.get(choice, "")
        if not prompt and choice in self.custom_presets:
            prompt = self.custom_presets[choice].get("prompt", "")
        self._set_instruction(prompt)
        self.save_settings()

    def _set_instruction(self, text):
        """Заменить текст в поле промпта целиком."""
        try:
            self.instruction_entry.delete("1.0", "end")
            if text:
                self.instruction_entry.insert("1.0", text)
        except Exception as e:
            print(f"⚠️ Промпт: {e}")

    @staticmethod
    def _norm_prompt(text):
        return " ".join((text or "").split())

    def _translate_instruction(self):
        """Смена языка интерфейса переводит и сам промпт.

        Переводим только стандартные промпты уровней (сравнение по тексту, а не по
        названию): свой текст, набранный руками, не трогаем. Промпты прежней версии
        заменяем актуальным для выбранного уровня.
        """
        try:
            cur = self.instruction_entry.get("1.0", "end-1c")
        except Exception:
            return
        if not cur.strip():
            return
        norm = self._norm_prompt
        target = self.PRESET_PROMPTS_EN if UI_LANG == "en" else self.PRESET_PROMPTS_RU

        for table in (self.PRESET_PROMPTS_RU, self.PRESET_PROMPTS_EN):
            for key, text in table.items():
                if norm(cur) == norm(text):
                    new = target.get(key, "")
                    if new and norm(new) != norm(cur):
                        self._set_instruction(new)
                    return

        if any(marker in cur for marker in self.LEGACY_PROMPTS):
            self.apply_preset(self.preset_menu.get())
            return
        # свой промпт — оставляем как есть

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

    def summarize_via_server(self, system_rules, user_content, url, expected_chars=None):
        headers = {"Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": system_rules},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.35,
            "stream": True,
            # Gemma 4 и другие reasoning-модели по умолчанию «думают» вслух: весь ответ
            # уходит в reasoning_content, а content приходит пустым или обрезанным.
            # Шаблон чата понимает этот флаг; обычные модели его просто игнорируют.
            "chat_template_kwargs": {"enable_thinking": False}
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
                                # Прогресс по реальному объёму текста, а не по числу
                                # кусков: иначе 95% набегает в начале генерации.
                                pct = self._progress_pct(len(full_text), expected_chars,
                                                         tokens_generated)
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

        if not full_text.strip() and not self.cancel_event.is_set():
            # Раньше здесь молча возвращался пустой текст: при включённых «размышлениях»
            # модель тратила на них весь лимит токенов, а content приходил пустым.
            raise Exception("Модель не вернула текст — попробуйте запустить анализ ещё раз.")

        return full_text.strip()

    # Слова, которыми инструкция просит перевести текст. Если они есть, язык результата
    # задаёт инструкция, а не правило «пиши по-русски».
    TRANSLATE_MARKERS = ("перевед", "перевод", "перевест", "переведи", "translate", "translation")

    # названия языков в промпте и в правилах
    LANG_NAMES = {"ru": "русском", "en": "английском", "de": "немецком",
                  "fr": "французском", "es": "испанском", "it": "итальянском"}
    LANG_MARKERS = {
        "ru": ("по-русски", "на русском", "русск", "russian"),
        "en": ("по-английски", "на английском", "английск", "english"),
        "de": ("по-немецки", "на немецком", "немецк", "german", "deutsch"),
        "fr": ("по-французски", "на французском", "французск", "french", "français"),
        "es": ("по-испански", "на испанском", "испанск", "spanish", "español"),
        "it": ("по-итальянски", "на итальянском", "итальянск", "italian", "italiano"),
    }

    @staticmethod
    def _detect_text_lang(text):
        """Язык исходного текста по алфавиту и частым словам (ru/en/de/fr/es/it)."""
        sample = (text or "")[:3000].lower().replace("ё", "е")
        cyr = sum(1 for ch in sample if "а" <= ch <= "я")
        lat = sum(1 for ch in sample if "a" <= ch <= "z")
        if cyr > 3 and cyr >= lat * 0.5:
            return "ru"
        if lat < 5:
            return ""
        words = set(re.findall(r"[a-z']+", sample))
        hints = {
            "en": ("the", "and", "of", "to", "in", "is", "that", "for", "with", "was"),
            "de": ("der", "die", "und", "ist", "den", "von", "mit", "nicht", "auf", "das"),
            "fr": ("les", "des", "une", "est", "pour", "dans", "avec", "pas", "sur", "qui"),
            "es": ("los", "las", "una", "para", "con", "por", "del", "que", "como", "más"),
            "it": ("gli", "della", "sono", "per", "con", "non", "che", "una", "del", "come"),
        }
        scores = {code: sum(w in words for w in ws) for code, ws in hints.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] >= 2 else ""

    def _lang_in_instruction(self, instruction):
        low = (instruction or "").lower().replace("ё", "е")
        for code, keys in self.LANG_MARKERS.items():
            if any(k in low for k in keys):
                return code
        return ""

    def _system_rules(self, instruction, source_text=""):
        """Системные правила для модели. Язык ответа определяет инструкция, а не правило.

        Раньше здесь жёстко стояло «отвечай на русском, английские слова заменяй русскими»:
        просьба «переведи на английский» проигрывала этому правилу, а английский текст
        при просьбе «сократи» пересказывался по-русски. Поэтому язык берём из инструкции,
        а если она его не называет — определяем по самому исходному тексту и называем явно
        (малая модель слушает «пиши по-английски», но игнорирует «на языке исходного текста»).
        """
        low = (instruction or "").lower().replace("ё", "е")
        if any(marker in low for marker in self.TRANSLATE_MARKERS):
            language_rule = ("Язык результата задаёт ИНСТРУКЦИЯ: переведи на требуемый ею язык и верни "
                             "только перевод — без исходного текста, пояснений, вариантов и комментариев. "
                             "Не оставляй в ответе слов языка оригинала, кроме имён собственных. ")
        else:
            code = self._lang_in_instruction(instruction) or self._detect_text_lang(source_text)
            if code in self.LANG_NAMES:
                language_rule = (f"Язык ответа — {self.LANG_NAMES[code]}: текст написан на этом языке, "
                                 f"поэтому и результат должен быть на нём. Не переводи текст на другой "
                                 f"язык и не меняй язык, если инструкция прямо не просит перевода. ")
            else:
                language_rule = ("Язык ответа — язык исходного текста. Не переводи текст, не меняй "
                                 "язык и не пересказывай его по-русски, если инструкция прямо не просит "
                                 "перевода. ")
        if getattr(self, "_verbatim_mode", False):
            # «Без изменений»: модель только размечает эмоции, текст не трогает
            style_rule = (
                "Сохраняй текст дословно: те же формулировки, порядок, абзацы, цифры и имена, "
                "что в исходнике; не сокращай, не пересказывай и не переоформляй. Единственная "
                "допустимая правка — маркеры эмоций вида (имя_эмоции) перед фразами, если они "
                "запрошены в инструкции; других скобок быть не должно. Если разметка эмоциями "
                "не запрошена — верни текст без единой правки. ")
        else:
            style_rule = (
                "Все цифры, даты и проценты пиши словами; пиши связной речью, "
                "без списков, маркеров, ссылок" + (
                    ", кроме скобок с названием эмоции" if getattr(self, "_emo_markers_on", False)
                    else " и скобок") + ". ")
        return ("Ты профессиональный редактор, готовящий текст для озвучки диктором. "
                "Отвечай ТОЛЬКО готовым текстом, без вступлений и пояснений. "
                + language_rule + style_rule +
                "Используй только факты из исходного текста — ничего не додумывай и не добавляй. "
                "Если задан диапазон объёма — соблюдай его строго: не больше верхней "
                "границы и не меньше нижней.")

    @staticmethod
    def _progress_pct(produced, expected_chars=None, chunks=0):
        """Прогресс анализа: 15% — старт, 95% — предел до финального «Готово».

        Считается по объёму готового текста относительно ожидаемого (лимит пресета
        или длина исходника), а не по числу пришедших кусков: иначе 95% набегало
        в начале генерации и последние 5% тянулись половину времени.
        """
        if expected_chars:
            share = produced / max(1, int(expected_chars))
        else:
            share = chunks / 480.0
        return 15 + min(80, int(80 * share))

    def summarize_text(self, raw_text, instruction, server_url=None, expected_chars=None):
        if not self.llm_model and not server_url:
            raise Exception("Модель ИИ не загружена.")
        system_rules = self._system_rules(instruction, raw_text)
        user_content = f"ИНСТРУКЦИЯ: {instruction}\nТЕКСТ: {raw_text}"

        # --- Модель на видеокарте: локальный CUDA-сервер llama.cpp ---
        if server_url:
            print(f"📡 Запрос к GPU-серверу: {server_url}")
            server_text = self.summarize_via_server(system_rules, user_content, server_url,
                                                    expected_chars=expected_chars)
            return self.clean_summary(server_text)

        full_text = ""
        tokens_generated = 0
        t_start = time.time()

        def feed(piece):
            nonlocal full_text, tokens_generated
            if piece:
                full_text += piece
                tokens_generated += 1
                # Прогресс по объёму готового текста: 95% больше не набегает в начале.
                pct = self._progress_pct(len(full_text), expected_chars, tokens_generated)
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
        result = self.clean_summary(full_text.strip())
        if not result and not self.cancel_event.is_set():
            raise Exception("Модель не вернула текст — попробуйте запустить анализ ещё раз.")
        return result

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
                    server_url=server_url, expected_chars=need)
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
                       "Хорошо",
                       # английские вступления того же рода (перевод и EN-интерфейс)
                       "Here is", "Here's", "Here’s", "Sure", "Certainly", "Of course",
                       "Translation", "Translated"]
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
                                   "Вставьте ссылку на статью или видео, текст или файл — либо наберите текст в поле справа.")
            return

        # видеоссылки (YouTube / Rutube / VK) — сначала берём субтитры как текст
        if url and not source_text:
            video = self._video_kind(url)
            if video:
                self.update_status("⏳ Загрузка субтитров видео…")
                self.update_idletasks()
                try:
                    text, vtitle = self._fetch_video_transcript(*video)
                except _SubCancelled:
                    self.update_status("✅ Готово. Вставьте ссылку на статью или видео, текст или файл.")
                    return
                except Exception as e:
                    messagebox.showerror("Видео", str(e))
                    self.update_status("✅ Готово. Вставьте ссылку на статью или видео, текст или файл.")
                    return
                if len(text) < 40:
                    messagebox.showwarning("Видео", "Субтитры пустые или слишком короткие — озвучивать нечего.")
                    return
                self._put_source_text(text, vtitle)
                source_text = text
                url = ""

        if source_text:
            self._last_source = source_text

        self._launch_analysis(url, source_text)

    def _launch_analysis(self, url, source_text):
        # Живой поток анализа — стоп: две генерации на одной модели роняют llama.cpp.
        if self.is_processing or (self._analysis_thread is not None
                                  and self._analysis_thread.is_alive()):
            return

        llm_name = self.llm_combo.get()
        if not llm_name and not (self.preset_menu.get() == self.NO_PROCESS
                                 and not self.emo_auto_var.get()):
            messagebox.showwarning("Внимание", "Выберите модель ИИ в карточке «МОДЕЛЬ ИИ»")
            return

        if self.current_engine == "Qwen":
            speaker = self.tts_combo.get()
            if speaker not in QWEN_DISPLAY:
                _, info = self._find_voice(speaker)
                if not speaker or info is None or not (info.get("path") and os.path.exists(info.get("path") or "")):
                    messagebox.showwarning("Внимание", "Выбери голос Qwen из списка или запиши свой: «🎙 Образец голоса».")
                    return
            self.current_tts_name = speaker
        elif self.current_engine == "Vox":
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
        self.update_status("⏳ Подготовка текста…")
        self.save_settings()

        self._analysis_thread = threading.Thread(target=self.process_pipeline,
                                                 args=(url, llm_name, source_text), daemon=True)
        self._analysis_thread.start()

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

            # «Без изменений»: без авто-эмоций текст идёт в озвучку как есть, модель не нужна.
            # С «Добавить эмоции» остаётся тот же дословный формат: модель лишь расставляет
            # маркеры (правило разметки добавляется ниже, стилевая перезапись снята).
            self._verbatim_mode = (self.preset_menu.get() == self.NO_PROCESS)
            if self._verbatim_mode and not self.emo_auto_var.get():
                if len(text) < 100:
                    raise Exception("Текст слишком короткий или пустой")
                if not source_text:
                    # текст уже в поле — не трогаем его даже пробелами; при ссылке — кладём статью
                    self.after(0, lambda s=text: self._set_box_text(s, generated=False))
                self.after(0, lambda n=len(text): self.stats_label.configure(
                    text=f"{n} зн. · {_tr('без изменений')}"))
                self.after(0, lambda: self.set_progress(100, "Готово"))
                self.after(0, lambda: self.update_status(
                    _tr("✅ Текст без изменений — нейросеть не вызывалась")))
                if self.auto_play_var.get() and not self.cancel_event.is_set():
                    self.after(300, self.play_result)
                return

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
                floor = max(40, int(target * 0.8))
                instruction = (instruction + f"\n\nОГРАНИЧЕНИЕ ОБЪЁМА: от {floor} до {target} знаков "
                               f"(около {int(ratio * 100)}% исходного текста). Это жёсткие границы: "
                               f"не укладываешься в верхнюю — сокращай дальше, сохраняя главное; "
                               f"не добираешь нижнюю — возвращай пропущенные значимые детали, "
                               f"цифры и имена.")
                print(f"📏 Целевой объём: {floor}–{target} знаков ({int(ratio * 100)}% от {len(text)})")

            # «Добавить эмоции»: модель сама ставит (эмоцию) перед фразами. Список берём
            # из записанных образцов голоса — иная скобка ни на что не повлияла бы.
            self._emo_markers_on = bool(self.emo_auto_var.get())
            emo_names = self._auto_emotion_names(self.tts_combo.get()) if self._emo_markers_on else []
            if self._emo_markers_on and emo_names:
                instruction = instruction + "\n\n" + emotion_marker_rule(emo_names)
                print(f"🎭 Авто-эмоции: доступно {len(emo_names)}: {', '.join(emo_names)}")
            else:
                self._emo_markers_on = False

            summary = self.summarize_text(text, instruction, server_url=gpu_url,
                                          expected_chars=target or len(text))

            if target:
                summary = self._fit_to_limit(summary, target, server_url=gpu_url)

            if self._emo_markers_on:
                summary = self._strip_unknown_markers(summary, self.tts_combo.get())
                self._emo_markers_on = False

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
            self.box_is_source = False

            if self.auto_play_var.get() and not self.cancel_event.is_set():
                self.after(300, self.play_result)

        except TooLong:
            print("⚠️ Текст длиннее контекста модели — анализ не запускался")
            self.after(0, lambda: self.update_status("⚠️ Текст длиннее контекста модели"))
        except Cancelled:
            print("⏹ Анализ отменён")
            self.after(0, lambda: self.update_status("⏹ Анализ отменён"))
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
                elif what == "save":
                    # ⬇ стрелка вниз в поддон — «сохранить файл»
                    d.rectangle([30, 6, 34, 33], fill=col)
                    d.polygon([(17, 27), (47, 27), (32, 44)], fill=col)
                    try:
                        d.rounded_rectangle([13, 49, 51, 54], radius=2, fill=col)
                    except AttributeError:
                        d.rectangle([13, 49, 51, 54], fill=col)
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
            self._save_icon = ctk.CTkImage(light_image=icon((34, 34, 34), "save"),
                                           dark_image=icon((232, 232, 232), "save"), size=(17, 17))
        except Exception as e:
            print(f"⚠️ Иконки Play/Pause: {e}")
            self._pp_light = self._pp_dark = self._stop_icon = self._save_icon = None

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
            self._safe_ui(lambda: self._pp_state(False))
            return
        self._playing = True
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
                self._safe_ui(lambda: self._pp_state(False))
            else:
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
        self.update_status("⏹ Остановлено")
        self._safe_ui(lambda: self._pp_state(False))

    def play_result(self):
        if self.is_processing:
            return
        text = "" if self._placeholder_active else self.result_box.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Внимание", "Нет текста для озвучки.")
            return

        if self.current_engine == "Qwen":
            speaker = self.tts_combo.get()
            if speaker not in QWEN_DISPLAY:
                _, info = self._find_voice(speaker)
                if not speaker or info is None or not (info.get("path") and os.path.exists(info.get("path") or "")):
                    messagebox.showwarning("Внимание", "Выбери голос Qwen из списка или запиши свой: «🎙 Образец голоса».")
                    return
            self.current_tts_name = speaker
        elif self.current_engine == "Vox":
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
            if self.current_engine in ("Vox", "Qwen") else self.tts_combo.get()
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
        self.update_status("⏳ Синтез речи…")
        threading.Thread(target=self.generate_and_play, args=(text,), daemon=True).start()

    def _save_last_audio(self):
        """Кнопка ⬇: сохранить WAV последней озвучки в выбранный файл."""
        src = None
        cached = getattr(self, "_last_audio", None)
        if cached:
            try:
                src = cached[4]
            except Exception:
                src = None
        if not src or not os.path.isfile(src):
            src = os.path.join(BASE_DIR, "temp_output_pro.wav")
        if not os.path.isfile(src):
            messagebox.showwarning("Внимание", "Нет озвучки для сохранения — сначала нажмите «Озвучить».")
            return
        try:
            out = filedialog.asksaveasfilename(
                parent=self, title="Сохранить озвучку",
                defaultextension=".wav", filetypes=[("WAV", "*.wav"), ("Все файлы", "*.*")],
                initialfile=time.strftime("FAIR_озвучка_%Y-%m-%d_%H-%M.wav"))
            if not out:
                return
            shutil.copyfile(src, out)
            self.update_status(f"✅ {_tr('Озвучка сохранена')}: {os.path.basename(out)}")
        except Exception as e:
            messagebox.showerror("Ошибка TTS", str(e))

    # ================= СИНТЕЗ =================

    def generate_and_play(self, text: str, play: bool = True):
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
                # маркер (эмоция) переключает образец голоса на одно предложение;
                # по умолчанию (без маркера) — нейтральный образец слота
                ref_by_emo = {None: (ref_wav, ref_text)}
                chunks = []
                for emo, frag in self._split_emotion_segments(text, speaker):
                    if emo and emo not in ref_by_emo:
                        ref_by_emo[emo] = self.get_ref(speaker, emo)
                    # 200 знаков — компромисс: тембр держится, пауз между фразами немного
                    chunks += [(emo, c) for c in self.split_text_chunks(frag, limit=200)]
                print(f"📚 Чанков для озвучки: {len(chunks)}"
                      + (f" · эмоции: {', '.join(e for e in ref_by_emo if e)}" if len(ref_by_emo) > 1 else ""))
                segs = []
                sr_out = None
                skipped = 0
                for i, (emo, ch) in enumerate(chunks):
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
                    chunk_ref_wav, chunk_ref_text = ref_by_emo[emo]
                    arr, sr = self._vox_synth_chunk(ch_clean, chunk_ref_wav, chunk_ref_text,
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

                if play:
                    self._play_wav(temp_file)

            elif self.current_engine == "Qwen":
                actual_rate = rate * QWEN_BASE_SPEED
                self._qwen_check_import()
                speaker = self.current_tts_name or self.tts_combo.get()
                spk_id, vpack, need_kind = None, None, "custom"
                if speaker not in QWEN_DISPLAY:
                    if not speaker:
                        _v, _info = self._first_empty_voice()
                        filled = [i.get("name") for _, i in self._voice_items()
                                  if isinstance(i, dict) and i.get("path") and os.path.exists(i.get("path") or "")]
                        speaker = filled[-1] if filled else ""
                    _vid, _info = self._find_voice(speaker)
                    if not _info or not (_info.get("path") and os.path.exists(_info.get("path") or "")):
                        raise Exception("Не выбран голос: возьми встроенный голос Qwen или запишите образец «🎙 Образец голоса».")
                    spk_id, vpack, need_kind = None, (_vid, _info), "base"
                else:
                    spk_id = QWEN_BY_DISPLAY[speaker][0]
                if not self._qwen_ready(need_kind):
                    self._safe_ui(lambda: self.update_status("⏳ Скачиваю модель Qwen3-TTS..."))
                    self._qwen_fetch([need_kind], cancel=self.cancel_event)
                self.after(0, lambda: self.update_status(f"⏳ Синтез Qwen3-TTS (×{actual_rate:.2f})..."))
                model = self._qwen_model(need_kind)
                lang = self.qwen_cfg.get("language") or "auto"
                lang = None if lang == "auto" else lang
                # поле инструкции в карточке — только зеркало; характер живёт
                # в паспорте голоса (vpack) и подмешивается в _qwen_instruct_for
                user_instr = ""
                # как у Vox: незакрытая пунктуацией фраза «съедает» хвост фразы — закрываем знаком
                text = text.strip()
                if text and text[-1] not in ".!?…:;»\"')":
                    text += "."
                chunks = []
                for emo, frag in self._split_emotion_segments_qwen(text):
                    chunks += [(emo, c) for c in self.split_text_chunks(frag, limit=220)]
                print(f"📚 Чанков Qwen: {len(chunks)}"
                      + (f" · эмоции: {', '.join(dict.fromkeys(e for e, _ in chunks if e))}"
                         if any(e for e, _ in chunks) else ""))
                self._qwen_new_run_seed()
                segs = []
                sr_out = None
                skipped = 0
                for i, (emo, ch) in enumerate(chunks):
                    if self.cancel_event.is_set():
                        raise Cancelled()
                    self._safe_ui(lambda p=i, n=len(chunks): self.set_progress(
                        int(p * 95 / max(1, n)) + 3, f"Синтез {p + 1}/{n}"))
                    ch_clean = re.sub(r'^[^0-9A-Za-zА-Яа-яЁё]+', '', ch).strip()
                    if len(ch_clean) < 2:
                        continue
                    if ch_clean[-1] not in ".!?…:;":
                        ch_clean += "."
                    arr, sr = self._qwen_synth_chunk(model, spk_id, vpack, ch_clean,
                                                     emo, user_instr, lang)
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
                    raise Exception("Qwen не синтезировал ни одной фразы.")
                audio = self._join_chunks(segs, sr_out)
                with wave.open(temp_file, 'wb') as f:
                    f.setnchannels(1);
                    f.setsampwidth(2);
                    f.setframerate(sr_out)
                    f.writeframes(audio.tobytes())
                if self.cancel_event.is_set():
                    raise Cancelled()
                if self.qwen_cfg.get("free_after"):
                    self._qwen_free()
                if play:
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

                if play:
                    self._play_wav(temp_file)

            if self.cancel_event.is_set():
                raise Cancelled()

            self._last_audio = (orig_text, self.current_engine,
                                getattr(self, "_synth_voice_key", self.tts_combo.get()),
                                rate, temp_file)
            self._safe_ui(lambda: self.set_progress(100, "Синтез завершён"))
            self.after(0, self.progress_bar.stop)
            return temp_file

        except Cancelled:
            print("⏹ Синтез отменён")
            self.after(0, self.progress_bar.stop)
            return None

        except Exception as e:
            msg = str(e)
            print(f"❌ Ошибка синтеза: {msg}")
            self.after(0, lambda: messagebox.showerror("Звук", msg))
            self.after(0, self.progress_bar.stop)
            return None


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FAIR.FreeAIReader")
    except Exception:
        pass
    app = ModernTTSApp()
    app.mainloop()