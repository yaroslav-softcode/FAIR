# -*- coding: utf-8 -*-
"""Точка входа установленной сборки FAIR.

Отдельный файл нужен из-за оконного режима: в сборке без консоли sys.stdout и
sys.stderr равны None, а приложение активно печатает отладочные строки — без
подмены на devnull любой print() уронил бы запуск.
"""
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# консоль Windows по умолчанию cp1251 — print() с эмодзи падал бы UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import ctypes
import json
import time
import traceback
import wave

import modern_app_v2 as app_module

MODULES = ("customtkinter", "numpy", "requests", "bs4", "pyperclip", "sounddevice",
           "piper", "onnxruntime", "llama_cpp", "psutil")


def _selfcheck():
    """Проверка установленной сборки: импорты, голос, синтез. Окно не открывается."""
    report = {}
    for name in MODULES:
        try:
            __import__(name)
            report[name] = "ok"
        except Exception as e:
            report[name] = f"ERR {type(e).__name__}: {e}"

    bundle = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    voice_path = os.path.join(bundle, "piper", "en_US-ljspeech-high.onnx")
    report["voice_file"] = os.path.isfile(voice_path)
    report["espeak_data"] = os.path.isdir(os.path.join(bundle, "piper", "espeak-ng-data"))
    report["data_dir"] = app_module.BASE_DIR
    report["model_expected"] = app_module.ModernTTSApp.MODEL_PACK["name"]
    report["frozen"] = app_module.FROZEN

    # настоящий синтез: проверяет espeak + onnxruntime + сам голос
    try:
        from piper import PiperVoice
        out_wav = os.path.join(os.environ.get("TEMP", "."), "fair_selfcheck.wav")
        voice = PiperVoice.load(voice_path)
        with wave.open(out_wav, "wb") as wf:
            voice.synthesize_wav("Hello, this is a test of Free AI Reader.", wf)
        report["synth"] = f"ok {os.path.getsize(out_wav)} bytes"
    except Exception:
        report["synth"] = traceback.format_exc()[-600:]

    try:
        from llama_cpp import Llama
        report["llama_import"] = "ok" if Llama else "?"
    except Exception:
        report["llama_import"] = traceback.format_exc()[-600:]

    out = os.path.join(os.environ.get("TEMP", "."), "fair_selfcheck.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return out


def _log_crash(text):
    """Падение приложения писать в журнал — в оконном режиме traceback иначе пропадает."""
    try:
        base = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "FAIR")
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "fair_log.txt"), "a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")
    except Exception:
        pass


def _excepthook(kind, value, tb):
    _log_crash("ПАДЕНИЕ " + "".join(traceback.format_exception(kind, value, tb)))


def _voxcheck():
    """Проверка дополнения Vox изнутри собранного приложения (FAIR_VOXCHECK=1)."""
    report = {}
    try:
        site = os.path.join(app_module.BASE_DIR, "vox", "site")
        report["site"] = site
        report["site_exists"] = os.path.isdir(site)
        report["voxcpm_dir"] = os.path.isdir(os.path.join(site, "voxcpm"))
        report["python"] = sys.version.split()[0]
        report["executable"] = sys.executable
        if site not in sys.path:
            sys.path.insert(0, site)
        dll = os.path.join(site, "torch", "lib")
        report["torch_lib"] = os.path.isdir(dll)
        if os.path.isdir(dll):
            try:
                os.add_dll_directory(dll)
            except Exception as e:
                report["add_dll"] = f"{type(e).__name__}: {e}"
        try:
            import torch
            report["torch"] = torch.__version__
            report["cuda"] = torch.cuda.is_available()
        except Exception:
            report["torch"] = traceback.format_exc()[-1200:]
        try:
            from voxcpm import VoxCPM
            report["voxcpm"] = "ok"
        except Exception:
            report["voxcpm"] = traceback.format_exc()[-1500:]
            return _write_voxcheck(report)

        if os.environ.get("FAIR_VOXCHECK") == "2":
            # полный прогон: загрузка весов на GPU и синтез образцом пользователя
            try:
                import glob
                import wave
                import numpy as np
                class _Shim:
                    BASE_DIR = app_module.BASE_DIR

                report["weights_dir"] = app_module.ModernTTSApp._vox_local_weights(_Shim)
                ref = os.path.join(app_module.BASE_DIR, "my_voice_1.wav")
                report["ref"] = os.path.isfile(ref)
                os.environ["HF_HUB_OFFLINE"] = "1"
                t0 = time.time()
                model = None
                for kw in ({"torch_dtype": torch.float16}, {"dtype": torch.float16}, {}):
                    try:
                        model = VoxCPM.from_pretrained(report["weights_dir"], device="cuda", **kw)
                        report["kw"] = str(list(kw))
                        break
                    except TypeError:
                        continue
                report["load_sec"] = round(time.time() - t0, 1)
                report["vram_gb"] = round(torch.cuda.memory_allocated() / 1e9, 2)
                ref_text = "Образец голоса"
                try:
                    with open(os.path.join(app_module.BASE_DIR, "settings.json"),
                              encoding="utf-8") as f:
                        cfg = json.load(f)
                    for v in (cfg.get("custom_voices") or {}).values():
                        if os.path.abspath(v.get("path") or "") == os.path.abspath(ref) \
                                and v.get("text"):
                            ref_text = v["text"]
                            break
                except Exception:
                    pass
                report["ref_text"] = ref_text
                t0 = time.time()
                out = model.generate(text="Проверка озвучки из нового приложения.",
                                     prompt_wav_path=ref, prompt_text=ref_text)
                report["gen_sec"] = round(time.time() - t0, 1)
                arr = np.asarray(out, dtype=np.float32).reshape(-1)
                if arr.max() <= 1.5:
                    arr = np.clip(arr * 32767.0, -32768, 32767)
                wav = os.path.join(os.environ.get("TEMP", "."), "fair_voxcheck.wav")
                with wave.open(wav, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(arr.astype(np.int16).tobytes())
                report["wav"] = f"{os.path.getsize(wav)} байт, {len(arr) / 16000:.1f} с"
            except Exception:
                report["synth"] = traceback.format_exc()[-1500:]
    except Exception:
        report["outer"] = traceback.format_exc()[-800:]
    return _write_voxcheck(report)


def _write_voxcheck(report):
    out = os.path.join(os.environ.get("TEMP", "."), "fair_voxcheck.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    if os.environ.get("FAIR_VOXCHECK") in ("1", "2"):
        _voxcheck()
        sys.exit(0)
    if os.environ.get("FAIR_SELFCHECK") == "1":
        _selfcheck()
        sys.exit(0)
    sys.excepthook = _excepthook
    try:
        import threading
        threading.excepthook = lambda a: _excepthook(a.exc_type, a.exc_value, a.exc_traceback)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FAIR.FreeAIReader")
    except Exception:
        pass
    try:
        app = app_module.ModernTTSApp()
        app.mainloop()
    except Exception:
        _log_crash("ПАДЕНИЕ при старте\n" + traceback.format_exc())
        raise
