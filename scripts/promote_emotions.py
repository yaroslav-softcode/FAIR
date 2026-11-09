#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Промоут эмоциональных образцов голоса в дистрибутив FAIR.

Правило Ярослава (04.11.26): в дистрибутив и git едут ТОЛЬКО образцы эмоций,
записанные с микрофона. Всё, что сделано кнопкой «Синтезировать» (флаг
"synth": true в settings.json), не берётся НИКОГДА.

Запуск (из папки проекта):
    .venv/Scripts/python.exe scripts/promote_emotions.py --voice "Алсу" [--apply]

Без --apply только показывает, что будет сделано.
"""
import argparse
import json
import os
import re
import shutil
import sys

PROJECT = os.environ.get("FAIR_PROJECT", r"C:/Users/Yar/Projects/Project5-TTS")
VB = os.path.join(PROJECT, "voices_builtin")
SETTINGS = os.path.join(PROJECT, "settings.json")

# транслит для имён файлов в дистрибутиве (латиница надёжнее в установщике)
_TR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
       "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
       "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
       "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
       "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}


def latin(label):
    s = "".join(_TR.get(ch, ch) for ch in label.lower().strip())
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "emotion"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True, help="имя голоса в настройках (например Алсу)")
    ap.add_argument("--prefix", default=None, help="префикс файла (по умолчанию из имени голоса)")
    ap.add_argument("--apply", action="store_true", help="реально копировать")
    a = ap.parse_args()

    data = json.load(open(SETTINGS, encoding="utf-8"))
    slots = data.get("custom_voices") or {}
    slot = None
    for key, v in slots.items():
        if v and str(v.get("name", "")).strip().lower() == a.voice.strip().lower():
            slot = v
            break
    if not slot:
        sys.exit(f"Голос «{a.voice}» не найден в {SETTINGS}")

    prefix = a.prefix or latin(a.voice)
    samples = slot.get("samples") or {}
    mic, synth, missing = [], [], []
    for label, s in samples.items():
        if not isinstance(s, dict):
            continue
        if s.get("synth"):
            synth.append(label)
            continue
        path = s.get("path") or ""
        if not os.path.exists(path):
            missing.append((label, path))
            continue
        mic.append((label, path, s.get("text") or ""))

    print(f"ГОЛОС: {a.voice}")
    print(f"  с микрофона (можно в дистрибутив): {len(mic)}")
    for label, path, text in sorted(mic):
        dst = os.path.join(VB, f"{prefix}_emo_{latin(label)}.wav")
        print(f"    + {label:<14} {os.path.basename(path):<34} -> voices_builtin/{os.path.basename(dst)}")
    print(f"  синтезированные (НИКОГДА в дистрибутив/git): {len(synth)} -> {', '.join(sorted(synth)) or 'нет'}")
    if missing:
        print(f"  ⚠ записаны, но файла нет: {missing}")

    # страховка: в voices_builtin не должно быть файлов из synth-сэмплов
    synth_paths = {os.path.normcase(os.path.abspath(s["path"])) for s in samples.values()
                   if isinstance(s, dict) and s.get("synth") and s.get("path")}
    bad = [f for f in os.listdir(VB)
           if os.path.normcase(os.path.abspath(os.path.join(VB, f))) in synth_paths]
    if bad:
        sys.exit(f"⛔ В voices_builtin лежат синтезированные файлы: {bad} — удалить руками, я не трогаю")

    if not mic:
        print("\nНечего продвигать (микрофонных образцов нет).")
        return

    print("\n--- строки для build_installer/fair.spec (datas) ---")
    for label, _p, _t in sorted(mic):
        fn = f"{prefix}_emo_{latin(label)}.wav"
        print(f'    (os.path.join(SRC, "voices_builtin", "{fn}"), "voices_builtin"),')
    print("\n--- фрагмент BUILTIN_VOX_VOICES (поле emos) ---")
    emo = {label: f"{prefix}_emo_{latin(label)}.wav" for label, _p, _t in mic}
    print(json.dumps({"name": a.voice, "emos": emo}, ensure_ascii=False, indent=4))

    if not a.apply:
        print("\nПоказал без изменений. Копирование: добавь --apply")
        return
    for label, path, _t in mic:
        dst = os.path.join(VB, f"{prefix}_emo_{latin(label)}.wav")
        shutil.copy2(path, dst)
        print(f"СКОПИРОВАН {os.path.basename(dst)}")


if __name__ == "__main__":
    main()
