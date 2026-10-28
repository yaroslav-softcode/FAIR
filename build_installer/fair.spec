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
    # встроенный образец голоса Vox: «Алсу» —
    # приложение регистрирует его в слоте при первом запуске
    (os.path.join(SRC, "voices_builtin", "alsu_ref.wav"), "voices_builtin"),
]

# у llama-cpp-python нет хука PyInstaller: без этих DLL импорт Llama падает
_LLAMA_LIB = os.path.join(SRC, ".venv", "Lib", "site-packages", "llama_cpp", "lib")
binaries = [(p, "llama_cpp/lib") for p in glob.glob(os.path.join(_LLAMA_LIB, "*.dll"))]

hiddenimports = ["llama_cpp", "piper", "onnxruntime", "sounddevice", "pyperclip", "psutil",
                 # стандартная библиотека, до которой тяжёлые пакеты дополнения Vox
                 # (torch, transformers) дотягиваются в рантайме — иначе ModuleNotFoundError
                 "unittest", "unittest.mock", "filecmp", "difflib", "pydoc", "doctest",
                 "pickle", "csv", "sqlite3", "cgi", "multiprocessing", "concurrent.futures",
                 "xml.etree.ElementTree", "email.mime.text", "http.cookiejar",
                 "urllib.request", "urllib.parse", "json", "argparse", "ast", "inspect"]

excludes = [
    # piper содержит подпакет обучения (piper.train) — он тянет torch на 600 МБ,
    # а для синтеза речи нужен только onnxruntime
    "piper.train", "bitsandbytes", "lightning", "pytorch_lightning", "torchmetrics",
    "torch", "torchaudio", "torchvision", "transformers", "torchcodec", "ema_pytorch",
    "voxcpm", "f5_tts", "pyarrow", "botocore", "grpc", "datasets", "accelerate",
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
