# -*- coding: utf-8 -*-
"""Чекер состава релизной сборки FAIR (dist_installer/FAIR).

Проверяет: (1) обязательные модули и методы приложения в PYZ;
(2) отсутствие dev-пакетов/движков, которые должны грузиться из GPU-среды (vox/site);
(3) отсутствие torch/flash/triton-бинарников и папок в бандле.

Запуск из корня проекта:  .venv\\Scripts\\python.exe scripts\\check_pyz.py
"""
import marshal
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "dist_installer", "FAIR", "FAIR.exe")
APP_DIR = os.path.join(ROOT, "dist_installer", "FAIR")

REQUIRED_MODULES = ["modern_app_v2", "fair_api"]
BANNED_MODULES = ["ruaccent", "voxcpm", "nanovllm_voxcpm", "flash_attn", "triton",
                  "torch", "torchaudio", "torchvision", "torchcodec", "qwen_tts", "f5_tts"]
REQUIRED_METHODS = ["_open_stress_dialog", "_vox_generate_turbo", "_load_vox_turbo",
                    "_build_mem_panel", "_center_on_parent", "_rutube_transcript"]
BANNED_STRINGS = ["RUAccent"]
REQUIRED_STRINGS = ["Убрать ударение"]


def main():
    ok = True
    if not os.path.isfile(EXE):
        print("Нет файла сборки:", EXE)
        return 2
    sys.path.insert(0, os.path.join(ROOT, ".venv", "Lib", "site-packages"))
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

    car = CArchiveReader(EXE)
    pyz_name = next(t for t in car.toc if t.lower().endswith(".pyz"))
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".pyz")
    tf.write(car.extract(pyz_name))
    tf.close()
    zar = ZlibArchiveReader(tf.name)
    mods = set(zar.toc.keys())

    for m in REQUIRED_MODULES:
        if m not in mods:
            ok = False
            print("FAIL: нет модуля", m)
    for m in BANNED_MODULES:
        hit = [x for x in mods if x == m or x.startswith(m + ".")]
        if hit:
            ok = False
            print(f"FAIL: запрещённый пакет в PYZ: {m} ({len(hit)} модулей, напр. {hit[:3]})")

    raw = zar.extract("modern_app_v2")
    code = raw if hasattr(raw, "co_name") else marshal.loads(raw if isinstance(raw, bytes) else raw[16:])
    names, strs = set(), set()

    def walk(c):
        names.add(c.co_name)
        for k in c.co_consts:
            if hasattr(k, "co_name"):
                walk(k)
            elif isinstance(k, str):
                strs.add(k)

    walk(code)
    for m in REQUIRED_METHODS:
        if m not in names:
            ok = False
            print("FAIL: нет метода", m, "в modern_app_v2")
    for s in BANNED_STRINGS:
        if any(s in x for x in strs):
            ok = False
            print("FAIL: запрещённая строка в UI:", s)
    for s in REQUIRED_STRINGS:
        if not any(s in x for x in strs):
            ok = False
            print("FAIL: нет строки", s)

    bad_files = []
    for dp, _dn, fn in os.walk(APP_DIR):
        for f in fn:
            if re.search(r"torch|cudnn|cublas|flash_attn|triton", f, re.I) and \
                    f.lower().endswith((".dll", ".pyd", ".exe")):
                bad_files.append(os.path.join(dp, f))
    if bad_files:
        ok = False
        print("FAIL: бинарники dev-пакетов:", bad_files[:5])
    for d in ("torch", "triton", "nanovllm_voxcpm", "ruaccent"):
        if os.path.isdir(os.path.join(APP_DIR, "_internal", d)):
            ok = False
            print(f"FAIL: папка _internal/{d} в сборке")

    print("CHECK_PYZ:", "PASS" if ok else "FAIL", "· модулей в PYZ:", len(mods))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
