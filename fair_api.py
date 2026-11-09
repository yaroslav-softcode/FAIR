# -*- coding: utf-8 -*-
"""FAIR MCP API — локальный HTTP-сервер внутри приложения.

Через него Гермес подсаживается к FAIR: мост fair_mcp.py (MCP по stdio)
пересылает вызовы сюда. Слушает только 127.0.0.1; авторизация по токену,
который кладётся в fair_api_endpoint.json рядом с программой.

Эндпоинты:
  GET  /status   состояние приложения: движок, голоса, модель ИИ, занятость
  POST /speak    обработать и озвучить
       { "text": "...", "url": "https://...",      — одно из двух обязательно
         "prompt": "...",                          — инструкция для модели ИИ;
                                                      "none" — без ИИ, озвучить как есть
         "engine": "vox"|"piper",                  — по умолчанию как в приложении
         "voice": "название голоса",               — по умолчанию выбранный в окне
         "model": "имя.gguf",                      — по умолчанию выбранный в окне
         "ratio": 0.3,                             — сжать до 30% объёма
         "gpu": true,                              — анализ на видеокарте (llama-server)
         "speed": 1.1,                             — темп речи (временно)
         "play": false }                           — играть звук в колонки приложения
  -> {"ok": true, "audio_path": "C:\\...\\mcp_audio\\fair_...wav", "text": "...", ...}

  POST /tts      озвучить готовый текст для игры (drawosek и т.п.) — без ИИ-анализа
       { "text": "Не ведаю я про то.",
         "engine": "vox" | "vox_turbo" | "qwen" | "piper",
         "voice": "имя голоса",                   — список в GET /status
         "speed": 1.0, "play": false,
         "stream": true }                         — ответить сразу, звук по частям
  -> {"ok": true, "task": "142231_a1b2c3", "dir": "C:/.../game_audio/142231_a1b2c3"}
  GET  /tts/task/<id>   готовность реплики:
       {"done": 2, "total": 5, "fraction": 0.4,
        "segs": [{"i": 0, "file": ".../seg_000.wav", "sr": 48000,
                  "seconds": 1.9, "ready_after": 2.4}, ...],
        "finished": false, "error": null, "audio_path": "...", "seconds": 6.1}
       Правило игры: начинать воспроизведение, когда fraction >= 0.5 — первые
       чанки уже на диске, остальные досинтезываются во время речи.

Тяжёлую работу делают собственные методы приложения (summarize_text,
generate_and_play) — обработка по MCP не отличается от нажатия пользователем
«Запустить анализ» и «Озвучить». Кнопка «Стоп» в окне отменяет и MCP-запрос.
"""
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORTS = (8756, 8757, 8758, 8759)         # порт и запасные, если занят
ENDPOINT_NAME = "fair_api_endpoint.json"
MAX_CHARS_NO_LLM = 8000                  # без ИИ-обработки длиннее — много ждать


class ApiError(Exception):
    pass


class _Server(ThreadingHTTPServer):
    # Windows: с SO_REUSEADDR (включён в HTTPServer по умолчанию) второй экземпляр
    # приложения тоже «успешно» садится на занятый порт — и ответы уходят не тому
    # процессу (симптом: «нет токена FAIR»/401 при живом endpoint-файле, 30.10.26).
    allow_reuse_address = False


def endpoint_path(base_dir):
    return os.path.join(base_dir, ENDPOINT_NAME)


def load_endpoint(base_dir):
    try:
        with open(endpoint_path(base_dir), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def start(app, log=print):
    """Поднять сервер рядом с окном приложения. Возвращает сервер или None."""
    srv = None
    for port in PORTS:
        try:
            srv = _Server((HOST, port), _Handler)
            break
        except OSError:
            continue
    if srv is None:
        log(f"⚠️ FAIR API: все порты {PORTS} заняты — MCP недоступен")
        return None
    token = secrets.token_hex(16)
    srv.fair_app = app
    srv.fair_token = token
    app._api_server = srv
    meta = {"url": f"http://{HOST}:{srv.server_address[1]}",
            "port": srv.server_address[1], "token": token,
            "pid": os.getpid(), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        with open(endpoint_path(app.BASE_DIR), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"⚠️ FAIR API: не удалось записать {ENDPOINT_NAME}: {e}")
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5},
                     daemon=True).start()
    log(f"🔌 FAIR API для Гермеса: http://{HOST}:{srv.server_address[1]}")
    return srv


# ---------- helpers: работа с окном из рабочего потока ----------

def _on_main(app, fn, timeout=10.0):
    """Выполнить fn в потоке интерфейса и дождаться результата."""
    ev = threading.Event()
    box = {}

    def run():
        try:
            box["v"] = fn()
        except Exception as e:
            box["e"] = e
        ev.set()

    app.after(0, run)
    if not ev.wait(timeout):
        raise ApiError("Приложение не отвечает (окно зависло?)")
    if "e" in box:
        raise box["e"]
    return box.get("v")


def _status(app, text):
    try:
        app.after(0, lambda t=text: app.update_status(t))
    except Exception:
        pass


# ---------- тела запросов ----------

def _status_body(app):
    cur = _on_main(app, lambda: {
        "engine": app.current_engine,
        "voice": app.tts_combo.get(),
        "llm": app.llm_combo.get(),
        "gpu": bool(app.llm_gpu_var.get()),
        "rate": app.speech_rate,
    })
    cur["ok"] = True
    cur["processing"] = bool(app.is_processing) or bool(getattr(app, "_mcp_busy", False))
    cur["vox_installed"] = app._vox_installed()
    cur["vox_loaded"] = app.vox_model is not None
    cur["vox_voices"] = [i.get("name") for _, i in app._voice_items()
                         if isinstance(i, dict) and i.get("name")
                         and i.get("path") and os.path.exists(i.get("path") or "")]
    cur["piper_voices"] = sorted(app.tts_models.keys())
    cur["llm_models"] = sorted(app.llm_models.keys())
    # игра (drawosek) по этим ключам рисует выбор движка и голоса
    import modern_app_v2 as mav
    cur["qwen_voices"] = sorted(getattr(mav, "QWEN_DISPLAY", set()))
    cur["vox_ready"] = bool(app._vox_installed())
    cur["nano_installed"] = bool(app._nano_installed())
    cur["qwen_installed"] = bool(app._qwen_installed())
    return cur


def _speak(app, p):
    import modern_app_v2 as mav          # круг импорта развязываем на ходу

    if getattr(app, "_mcp_busy", False):
        raise ApiError("FAIR уже выполняет другой MCP-запрос — дождитесь окончания")
    if app.is_processing:
        raise ApiError("Приложение занято другой задачей — попробуйте позже")
    app._mcp_busy = True
    t0 = time.time()
    gpu_url = None
    old_engine, old_rate = app.current_engine, app.speech_rate
    try:
        eng_wanted = (p.get("engine") or "").strip().lower()
        engine = {"vox": "Vox", "piper": "Piper"}.get(eng_wanted) or app.current_engine
        cur = _on_main(app, lambda: {"voice": app.tts_combo.get(),
                                     "llm": app.llm_combo.get(),
                                     "gpu": bool(app.llm_gpu_var.get())})

        # --- исходник ---
        text = (p.get("text") or "").strip()
        url = (p.get("url") or "").strip()
        if url:
            _status(app, "🤖 MCP: загрузка статьи…")
            try:
                text = app.fetch_and_clean_text(url)
            except Exception as e:
                raise ApiError(f"Не удалось загрузить статью: {e}")
        text = re.sub(r"\s+", " ", text or "").strip()
        if len(text) < 20:
            raise ApiError("Слишком мало текста (меньше 20 знаков)")

        prompt = (p.get("prompt") or "").strip()
        skip_llm = prompt.lower() in ("", "none", "raw", "нет", "без обработки")
        if skip_llm and len(text) > MAX_CHARS_NO_LLM:
            raise ApiError(f"Текст {len(text)} знаков слишком длинный для озвучки без ИИ-обработки. "
                           f"Задай prompt (сжать) или уменьши текст.")

        # --- анализ моделью ИИ ---
        out_text = text
        model_used = None
        if not skip_llm:
            llm_name = (p.get("model") or "").strip() or cur["llm"]
            actual = app.llm_display.get(llm_name, llm_name)
            path = app.llm_models.get(actual)
            if not path or not os.path.exists(path):
                raise ApiError(f"Модель ИИ «{llm_name}» не найдена — скачайте её в карточке «МОДЕЛЬ ИИ»")
            n_ctx = app.model_ctx.get(llm_name, 4096)
            limit = app.model_limits.get(llm_name, mav.FALLBACK_CHARS)
            if len(text) > limit:
                raise ApiError(f"Текст {len(text):,} знаков превышает лимит модели {limit:,} — "
                               f"увеличьте контекст в карточке «МОДЕЛЬ ИИ»")
            use_gpu = bool(cur["gpu"]) if p.get("gpu") is None else bool(p.get("gpu"))
            app.cancel_event.clear()
            app.is_processing = True
            if use_gpu:
                _status(app, "🤖 MCP: загрузка модели на видеокарту…")
                port_gpu = app._ensure_gpu_server(path, n_ctx)
                gpu_url = f"http://127.0.0.1:{port_gpu}/v1/chat/completions"
            else:
                if not (app.llm_model is not None and app.llm_model_path == path
                        and app.llm_model_ctx == n_ctx):
                    app.unload_llm()
                    _status(app, f"🤖 MCP: загрузка модели «{llm_name}» на процессор…")
                    app.llm_model = mav.Llama(model_path=path, n_ctx=n_ctx, n_gpu_layers=0,
                                              n_threads=-1, flash_attn=True, verbose=False)
                    app.llm_model_path = path
                    app.llm_model_ctx = n_ctx
            instruction = prompt
            ratio = p.get("ratio")
            target = None
            if isinstance(ratio, (int, float)) and 0 < ratio < 1:
                target = max(60, int(len(text) * ratio))
                floor = max(40, int(target * 0.8))
                instruction += (f"\n\nОГРАНИЧЕНИЕ ОБЪЁМА: от {floor} до {target} знаков "
                                f"(около {int(ratio * 100)}% исходного текста). Это жёсткие границы: "
                                f"не укладываешься в верхнюю — сокращай дальше, сохраняя главное; "
                                f"не добираешь нижнюю — возвращай пропущенные значимые детали, "
                                f"цифры и имена.")
            _status(app, "🤖 MCP: анализ нейросетью…")
            out_text = app.summarize_text(text, instruction, server_url=gpu_url)
            if target:
                out_text = app._fit_to_limit(out_text, target, server_url=gpu_url)
            model_used = llm_name
            if gpu_url:
                app._stop_gpu_server()      # освобождаем VRAM под Vox
                gpu_url = None

        if not out_text.strip():
            raise ApiError("После обработки ничего не осталось — нечем озвучивать")

        # --- настройки озвучки (только атрибуты, виджеты не трогаем) ---
        app.current_engine = engine
        speed = p.get("speed")
        if isinstance(speed, (int, float)) and 0.2 <= float(speed) <= 3.0:
            app.speech_rate = float(speed)

        voice_name = (p.get("voice") or "").strip() or cur["voice"]
        if engine == "Vox":
            if not app._vox_installed():
                raise ApiError("Дополнение Vox не установлено — включите движок Vox в окне FAIR")
            vid, info = app._find_voice(voice_name)
            if not info or not (info.get("path") and os.path.exists(info.get("path") or "")):
                filled = [i.get("name") for _, i in app._voice_items()
                          if isinstance(i, dict) and i.get("name")
                          and i.get("path") and os.path.exists(i.get("path") or "")]
                raise ApiError(f"Vox-голос «{voice_name}» не готов. Доступны: "
                               f"{', '.join(n for n in filled if n) or 'нет — запишите образец'}")
            app.current_tts_name = voice_name
        else:
            if not voice_name:
                raise ApiError("Голос не выбран")
            if app.tts_voice is None or app.current_tts_name != voice_name:
                vp = app.tts_models.get(voice_name)
                if not vp or not os.path.exists(vp):
                    raise ApiError(f"Piper-голос «{voice_name}» не найден. Доступны: "
                                   f"{', '.join(sorted(app.tts_models))}")
                _status(app, f"🤖 MCP: загрузка голоса «{voice_name}»…")
                app.tts_voice = mav.PiperVoice.load(vp)
                app.current_tts_name = voice_name
        app._synth_voice_key = voice_name

        # --- синтез тем же путём, что кнопка «Озвучить» ---
        if app.cancel_event.is_set():
            raise ApiError("Запрос отменён")
        _status(app, "🤖 MCP: синтез речи…")
        app.is_processing = True
        wav = app.generate_and_play(out_text, play=bool(p.get("play")))
        if not wav or not os.path.isfile(wav):
            raise ApiError("Синтез не получился (отменён кнопкой «Стоп» или ошибка — см. лог FAIR)")

        # копия в mcp_audio: её забирает Гермес, её не перезапишет следующая озвучка
        out_dir = os.path.join(app.BASE_DIR, "mcp_audio")
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, time.strftime("fair_%Y%m%d_%H%M%S.wav"))
        shutil.copyfile(wav, out_file)

        _status(app, "🤖 MCP: готово ✅")
        return {"ok": True,
                "audio_path": out_file,
                "text": out_text,
                "engine": engine,
                "voice": voice_name,
                "model": model_used or "без ИИ",
                "chars_source": len(text),
                "chars_speech": len(out_text),
                "seconds": round(time.time() - t0, 1)}
    finally:
        if gpu_url:
            try:
                app._stop_gpu_server()
            except Exception:
                pass
        app.current_engine, app.speech_rate = old_engine, old_rate
        app.is_processing = False
        app._mcp_busy = False


# ---------- озвучка для игр: /tts ----------
#
# Игра просит озвучить уже готовую реплику. ИИ-анализа и виджетов окна тут нет:
# движок жжёт текст чанками, каждый готовый чанк сразу ложится в отдельный wav,
# а игра через /tts/task/<id> видит долю готовности и начинает говорить пораньше.

TTS_DIR = "game_audio"
TTS_TASKS_MAX = 40
_tts_tasks = {}
_tts_lock = threading.Lock()


def _tts_prune(app):
    """Не копить старые папки игровых реплик: сутки полежала — и в мусор."""
    root = os.path.join(app.BASE_DIR, TTS_DIR)
    try:
        for name in os.listdir(root):
            d = os.path.join(root, name)
            try:
                if os.path.isdir(d) and time.time() - os.path.getmtime(d) > 86400:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass
    with _tts_lock:
        while len(_tts_tasks) > TTS_TASKS_MAX:
            _tts_tasks.pop(next(iter(_tts_tasks)))


def _tts_engine(app, wanted):
    """engine из запроса -> (движок, вариант Vox)."""
    w = (wanted or "").strip().lower()
    if w in ("vox", "vox_classic", "vox classic", "classic"):
        return "Vox", "classic"
    if w in ("vox_turbo", "turbo", "vox fast"):
        if not app._nano_installed():
            raise ApiError("Быстрый Vox не установлен — включите его в окне FAIR "
                           "или просите engine=vox")
        return "Vox", "turbo"
    if w in ("qwen", "qwen3", "qwen3-tts"):
        if not app._qwen_installed():
            raise ApiError("Qwen3-TTS не установлен — включите движок Qwen в окне FAIR "
                           "или просите engine=vox")
        return "Qwen", None
    if w == "piper":
        return "Piper", None
    raise ApiError("нужен engine: vox | vox_turbo | qwen | piper")


def _tts_voice(app, engine, name):
    """Голос проверить и при нужде загрузить. Выбранный в окне голос не трогаем."""
    import modern_app_v2 as mav
    if engine == "Vox":
        if not app._vox_installed():
            raise ApiError("Дополнение Vox не установлено — включите движок Vox в окне FAIR")
        _id, info = app._find_voice(name)
        if not info or not (info.get("path") and os.path.exists(info.get("path") or "")):
            filled = [i.get("name") for _, i in app._voice_items()
                      if isinstance(i, dict) and i.get("name")
                      and i.get("path") and os.path.exists(i.get("path") or "")]
            raise ApiError(f"Vox-голос «{name}» не готов. Доступны: "
                           f"{', '.join(n for n in filled if n) or 'нет — запишите образец'}")
        app.current_tts_name = name
    elif engine == "Qwen":
        if name not in mav.QWEN_DISPLAY:
            _id, info = app._find_voice(name)
            if not info or not (info.get("path") and os.path.exists(info.get("path") or "")):
                raise ApiError(f"Qwen-голос «{name}» не готов. Встроенные: "
                               f"{', '.join(sorted(mav.QWEN_DISPLAY))}, либо свой образец")
        app.current_tts_name = name
    else:
        path = app.tts_models.get(name)
        if not path or not os.path.exists(path):
            raise ApiError(f"Piper-голос «{name}» не найден. Доступны: "
                           f"{', '.join(sorted(app.tts_models))}")
        if app.tts_voice is None or app.current_tts_name != name:
            app.tts_voice = mav.PiperVoice.load(path)
            app.current_tts_name = name
    app._synth_voice_key = name


def _tts_emotion_text(app, text, emotion, engine, voice):
    """Разметка эмоцией так, как её понимает движок FAIR.

    Маркер `(эмоция)` действует только до конца предложения — ставим его на каждое.
    Vox умеет эмоцию ТОЛЬКО через записанный образец речи: если у голоса эмоций нет,
    маркер озвучился бы вслух — тогда текст оставляем чистым (ремарка уже удалена
    вызывающей стороной). Qwen принимает разметку всегда — эмоция уходит в инструкцию
    из EMOTION_TAB. Piper эмоций не знает.
    """
    if not emotion:
        return text
    import modern_app_v2 as mav
    if emotion not in getattr(mav, "EMOTION_TAB", {}):
        raise ApiError(f"неизвестная эмоция «{emotion}» — ключи смотри в EMOTION_TAB")
    if engine == "Qwen":
        supported = True
    elif engine == "Vox":
        try:
            emos = app._emotion_samples(voice) or {}
            supported = app._emo_stem(emotion) in emos     # именно эта эмоция есть у голоса?
        except Exception:
            supported = False
    else:
        supported = False
    if not supported:
        print(f"⚠ эмоция «{emotion}»: движок {engine} её так не окрасит — говорю ровно")
        return text
    parts = [s for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    return " ".join(f"({emotion}) {s}" for s in parts)


def _tts(app, p):
    """Озвучить готовый текст для игры. stream=true — ответить сразу и отдавать
    реплику по чанкам; играть игра начинает по своему правилу (fraction >= 0.5)."""
    text = re.sub(r"\s+", " ", (p.get("text") or "")).strip()
    if len(text) < 2:
        raise ApiError("Пустой текст")
    if getattr(app, "_mcp_busy", False):
        raise ApiError("FAIR сейчас обрабатывает запрос через MCP — подожди немного")
    if getattr(app, "_tts_busy", False):
        raise ApiError("FAIR сейчас озвучивает другую реплику — подожди окончания")
    if app.is_processing:
        raise ApiError("Приложение занято другой задачей — попробуйте позже")

    engine, variant = _tts_engine(app, p.get("engine"))
    name = (p.get("voice") or "").strip()
    if not name:
        raise ApiError("Нужен voice=... (список голосов — в GET /status)")
    _tts_voice(app, engine, name)

    emotion = (p.get("emotion") or "").strip().lower() or None
    synth_text = _tts_emotion_text(app, text, emotion, engine, name)

    speed = p.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or not 0.2 <= float(speed) <= 3.0:
        raise ApiError("speed — число от 0.2 до 3.0")

    _tts_prune(app)
    tid = time.strftime("%H%M%S") + "_" + secrets.token_hex(3)
    tdir = os.path.join(app.BASE_DIR, TTS_DIR, tid)
    os.makedirs(tdir, exist_ok=True)
    task = {"id": tid, "dir": tdir, "engine": engine, "voice": name, "text": text,
            "emotion": emotion,
            "segs": [], "done": 0, "total": 0, "started": time.time(),
            "finished": False, "error": None, "audio_path": None, "seconds": None}
    with _tts_lock:
        _tts_tasks[tid] = task

    def hook(i, total, arr, sr, ch):
        # вызывается из потока синтеза: готовый чанк -> wav -> отчёт о прогрессе
        task["total"] = total
        path = os.path.join(tdir, f"seg_{i:03d}.wav")
        with wave.open(path, "wb") as f:
            f.setnchannels(ch)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(arr.tobytes())
        task["segs"].append({"i": i, "file": path, "sr": sr,
                             "seconds": round(len(arr) / float(sr), 2),
                             "ready_after": round(time.time() - task["started"], 2)})
        task["done"] = max(task["done"], i + 1)

    def run():
        app._tts_busy = True
        app._seg_hook = hook
        old = (app.current_engine, app.speech_rate)
        app.is_processing = True
        app.cancel_event.clear()
        try:
            app.current_engine = engine
            app.speech_rate = float(speed)
            if engine == "Vox":
                # Вариант переключаем ТОЛЬКО штатным путём: он выгружает чужой движок из
                # VRAM и держит в согласии «какой вариант выбран» с «какая модель реально
                # синтезирует». Классик без ×2-ресемпла (или турбо с ним) — ровно тот
                # случай «вдвое медленнее/быстрее», который чинили в окне FAIR.
                _eff = app._vox_variant_effective()
                need = variant != _eff
                if not need:
                    if variant == "turbo":
                        need = getattr(app, "vox_model", None) is not None   # просят турбо, а в памяти Classic
                    else:
                        need = getattr(app, "vox_turbo", None) is not None   # просят Classic, а в памяти Turbo
                if need:
                    try:
                        app._vox_set_variant(variant)
                    except Exception as e:
                        # не получилось — оставляем как есть: движок сам выберет работающий,
                        # а ×2-ресемпл достанется тому, кто в памяти (звук ровный)
                        print(f"⚠ /tts: переключение варианта Vox не удалось: {e}")
            task["audio_path"] = app.generate_and_play(synth_text, play=bool(p.get("play")))
            task["finished"] = True
        except Exception as e:
            task["error"] = str(e)
            task["finished"] = True
        finally:
            task["seconds"] = round(time.time() - task["started"], 1)
            app.current_engine, app.speech_rate = old
            app._seg_hook = None
            app.is_processing = False
            app._tts_busy = False

    if p.get("stream"):
        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "task": tid, "dir": tdir, "engine": engine, "voice": name,
                "how": f"опрашивай GET /tts/task/{tid} и начинай играть, "
                       f"когда fraction >= 0.5"}

    run()
    if task["error"]:
        raise ApiError(task["error"])
    return {"ok": True, "task": tid, "audio_path": task["audio_path"], "segs": task["segs"],
            "engine": engine, "voice": name, "emotion": emotion,
            "chars": len(text), "seconds": task["seconds"]}


def _tts_task(tid):
    t = _tts_tasks.get(tid)
    if not t:
        raise ApiError("Задача не найдена — проверь id (или FAIR перезапускали)")
    return {"ok": True, "id": tid, "done": t["done"], "total": t["total"],
            "fraction": round(t["done"] / t["total"], 3) if t["total"] else 0.0,
            "segs": list(t["segs"]), "finished": t["finished"], "error": t["error"],
            "audio_path": t["audio_path"], "seconds": t["seconds"],
            "engine": t["engine"], "voice": t["voice"], "emotion": t.get("emotion"),
            "audio_seconds": round(sum(s["seconds"] for s in t["segs"]), 2)}


# ---------- HTTP ----------

class _Handler(BaseHTTPRequestHandler):
    server: "ThreadingHTTPServer"

    def log_message(self, fmt, *args):      # не сорить в консоль приложения
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self):
        tok = self.headers.get("X-FAIR-Token", "")
        return hmac.compare_digest(tok, getattr(self.server, "fair_token", ""))

    def do_GET(self):
        app = self.server.fair_app
        if not self._authed():
            return self._send(401, {"ok": False, "error": "нет токена FAIR (X-FAIR-Token)"})
        if self.path.split("?")[0] == "/status":
            try:
                return self._send(200, _status_body(app))
            except Exception as e:
                return self._send(200, {"ok": False, "error": str(e)})
        if self.path.startswith("/tts/task/"):
            try:
                return self._send(200, _tts_task(self.path.rstrip("/").split("/")[-1]))
            except ApiError as e:
                return self._send(200, {"ok": False, "error": str(e)})
        return self._send(404, {"ok": False, "error": "неизвестный путь"})

    def do_POST(self):
        app = self.server.fair_app
        if not self._authed():
            return self._send(401, {"ok": False, "error": "нет токена FAIR (X-FAIR-Token)"})
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            p = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return self._send(400, {"ok": False, "error": "тело — не JSON"})
        if path == "/speak":
            try:
                return self._send(200, _speak(app, p))
            except ApiError as e:
                _status(app, f"🤖 MCP: ошибка")
                return self._send(200, {"ok": False, "error": str(e)})
            except Exception as e:
                import traceback
                print(f"❌ FAIR API: {e}\n{traceback.format_exc()}")
                _status(app, "🤖 MCP: ошибка")
                return self._send(200, {"ok": False, "error": f"Внутренняя ошибка FAIR: {e}"})
        if path == "/tts":
            try:
                return self._send(200, _tts(app, p))
            except ApiError as e:
                return self._send(200, {"ok": False, "error": str(e)})
            except Exception as e:
                import traceback
                print(f"❌ FAIR API /tts: {e}\n{traceback.format_exc()}")
                return self._send(200, {"ok": False, "error": f"Внутренняя ошибка FAIR: {e}"})
        return self._send(404, {"ok": False, "error": "неизвестный путь"})
