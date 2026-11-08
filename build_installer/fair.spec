# -*- mode: python ; coding: utf-8 -*-
"""Сборка установочной версии FAIR (onedir, без консоли, без torch/Vox).

Запуск: .venv\\Scripts\\pyinstaller.exe build_installer\\fair.spec --noconfirm
"""
import glob
import os

from PyInstaller.utils.hooks import collect_data_files

SRC = r"C:\Users\Yar\Projects\Project5-TTS"

datas = []
datas += collect_data_files("customtkinter")          # темы, шрифты, иконки CTk
datas += collect_data_files("sounddevice")            # PortAudio DLL
datas += collect_data_files("piper")                  # espeak-ng-data (без него нет фонем)
try:                                                  # перетаскивание файлов в окно
    datas += collect_data_files("tkinterdnd2")        # tkdnd: tcl-скрипты и бинарники
except Exception:
    pass
datas += [
    (os.path.join(SRC, "app.ico"), "."),
    (os.path.join(SRC, "logo.png"), "."),
    (os.path.join(SRC, "titlebar_clear.ico"), "."),
    # голоса кладём в дистрибутив: английский (LJSpeech, public domain) и два русских
    # (Irina/Ruslan, CC BY-NC-SA — атрибуция в THIRD-PARTY.md, продажа запрещена)
    (os.path.join(SRC, "models", "en_US-ljspeech-high.onnx"), "piper"),
    (os.path.join(SRC, "models", "en_US-ljspeech-high.onnx.json"), "piper"),
    (os.path.join(SRC, "models", "ru_RU-irina-medium.onnx"), "piper"),
    (os.path.join(SRC, "models", "ru_RU-irina-medium.onnx.json"), "piper"),
    (os.path.join(SRC, "models", "ru_RU-ruslan-medium.onnx"), "piper"),
    (os.path.join(SRC, "models", "ru_RU-ruslan-medium.onnx.json"), "piper"),
    # встроенные образцы голосов Vox: «Алсу» и «Джон» —
    # приложение регистрирует их в слотах при первом запуске
    (os.path.join(SRC, "voices_builtin", "alsu_ref.wav"), "voices_builtin"),
    (os.path.join(SRC, "voices_builtin", "john_ref.wav"), "voices_builtin"),
    # MCP-мост к Гермесу: исходник кладём рядом с exe (отладка; рабочий — fair_mcp.exe)
    (os.path.join(SRC, "fair_mcp.py"), "."),
    # инструкция «как подключить FAIR к Hermes по MCP» — для другого компьютера
    (os.path.join(SRC, "MCP.md"), "."),
]

# у llama-cpp-python нет хука PyInstaller: без этих DLL импорт Llama падает
_LLAMA_LIB = os.path.join(SRC, ".venv", "Lib", "site-packages", "llama_cpp", "lib")
binaries = [(p, "llama_cpp/lib") for p in glob.glob(os.path.join(_LLAMA_LIB, "*.dll"))]

hiddenimports = ["llama_cpp", "piper", "onnxruntime", "sounddevice", "pyperclip", "psutil",
                 # шкалы видеопамяти в шапке (пакет nvidia-ml-py, импорт pynvml)
                 "pynvml",
                 # MCP-API для Гермеса (вшивается в сборку, поднимается из окна приложения)
                 "fair_api",
                 # стандартная библиотека, до которой тяжёлые пакеты дополнения Vox
                 # (torch, transformers) дотягиваются в рантайме — иначе ModuleNotFoundError
                 "unittest", "unittest.mock", "filecmp", "difflib", "pydoc", "doctest",
                 "pickle", "csv", "sqlite3", "cgi", "multiprocessing", "concurrent.futures",
                 "xml.etree.ElementTree", "email.mime.text", "http.cookiejar",
                 "urllib.request", "urllib.parse", "json", "argparse", "ast", "inspect",
                 # субтитры видео: YouTube и ВК/Rutube-запасной путь
                 "youtube_transcript_api", "yt_dlp", "defusedxml",
                 # drag&drop документов с рабочего стола
                 "tkinterdnd2",
                 "huggingface_hub", "tokenizers", "transformers",
                 "pycrfsuite", "razdel"]

excludes = [
    # piper содержит подпакет обучения (piper.train) — он тянет torch на 600 МБ,
    # а для синтеза речи нужен только onnxruntime. transformers с 1.6 НЕ исключается:
    # Сам torch и спутники остаются исключены — вспомогательные токенизаторы
    # живут без torch.
    "piper.train", "bitsandbytes", "lightning", "pytorch_lightning", "torchmetrics",
    "torch", "torchaudio", "torchvision", "torchcodec", "ema_pytorch",
    "voxcpm", "f5_tts", "pyarrow", "botocore", "grpc", "datasets", "accelerate",
    # Qwen3-TTS живёт в переносимой GPU-среде (vox/site), в exe не шьётся
    "qwen_tts",
    "matplotlib", "scipy", "pandas", "IPython", "notebook", "jupyter",
    "tkinter.test", "test", "pydoc_data",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
    "tensorflow", "onnx", "sympy", "numba", "cv2",
]

a = Analysis(
    [os.path.join(SRC, "fair_main.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FAIR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                     # оконное приложение
    icon=os.path.join(SRC, "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FAIR",
)
