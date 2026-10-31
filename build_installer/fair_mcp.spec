# -*- mode: python ; coding: utf-8 -*-
"""MCP-мост FAIR для Гермеса — отдельный консольный exe.

Мосту нужен только mcp + stdlib (он лишь пересылает HTTP-вызовы в FAIR),
поэтому тяжёлый стек приложения (torch/Vox, transformers, llama) исключаем —
иначе onefile раздувается с ~50 МБ до 2.7 ГБ (проверено 30.10.26).

Запуск:
  .venv\\Scripts\\pyinstaller.exe build_installer\\fair_mcp.spec --noconfirm --distpath dist_installer\\FAIR
"""
import os

SRC = r"C:\Users\Yar\Projects\Project5-TTS"

excludes = [
    # ИИ-стек приложения и дополнение Vox — мосту не нужны
    "torch", "torchaudio", "torchvision", "transformers", "voxcpm", "f5_tts",
    "llama_cpp", "piper", "onnxruntime", "onnx", "sounddevice", "pyperclip",
    "bitsandbytes", "lightning", "pytorch_lightning", "torchmetrics", "torchcodec",
    "ema_pytorch", "accelerate", "datasets", "tensorboard", "tensorflow", "keras",
    "scipy", "pandas", "matplotlib", "sklearn", "sympy", "numba", "cv2",
    "pyarrow", "botocore", "grpc", "IPython", "notebook", "jupyter",
    "tkinter.test", "test", "pydoc_data",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
]

a = Analysis(
    [os.path.join(SRC, "fair_mcp.py")],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name="fair_mcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,                      # stdio-транспорт MCP требует консольный ввод-вывод
)
