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
                instruction += (f"\n\nОГРАНИЧЕНИЕ ОБЪЁМА: не более {target} знаков "
                                f"(около {int(ratio * 100)}% исходного текста). Это жёсткий лимит — "
                                f"если не укладываешься, сокращай дальше, сохраняя главное.")
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
        return self._send(404, {"ok": False, "error": "неизвестный путь"})
