# -*- coding: utf-8 -*-
"""MCP-мост FAIR для Гермеса (stdio).

Гермес сам запускает этот файл (hermes mcp add fair ...), а мост пересылает
вызовы в запущенное приложение FAIR — локальный API fair_api.py на 127.0.0.1.
Так инструменты доступны Гермесу, даже когда FAIR ещё не открыт: вместо висящего
подключения мост честно отвечает «запустите FAIR».

Порт и токен мост берёт из fair_api_endpoint.json — приложение пишет его при старте.
"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
EP_NAME = "fair_api_endpoint.json"

from mcp.server.fastmcp import FastMCP

fair = FastMCP("fair", instructions=(
    "FAIR — приложение Ярослава: обрабатывает статьи и тексты локальной нейросетью "
    "и озвучивает их голосами Vox (клон голоса) или Piper. Аудио возвращается путём к wav-файлу "
    "на этом компьютере — отдавайте его пользователю строкой MEDIA:<путь>."))


def _endpoint_candidates():
    """Где искать endpoint-файл: переменная окружения, рядом с мостом,
    затем папка данных установленной версии (%LOCALAPPDATA%\\FAIR)."""
    out = []
    env = os.environ.get("FAIR_ENDPOINT")
    if env:
        out.append(env)
    out.append(os.path.join(HERE, EP_NAME))
    out.append(os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                            "FAIR", EP_NAME))
    return out


def _endpoint():
    for p in _endpoint_candidates():
        try:
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue
    return None


def _call(path, payload=None, timeout=900):
    ep = _endpoint()
    if not ep:
        return {"ok": False,
                "error": "FAIR не запущен: файл fair_api_endpoint.json не найден ни рядом с мостом, "
                         "ни в %LOCALAPPDATA%\\FAIR. Попросите пользователя запустить приложение FAIR."}
    url = str(ep.get("url", "")).rstrip("/") + path
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        method="POST" if payload is not None else "GET",
        headers={"X-FAIR-Token": ep.get("token", ""), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        try:
            body = json.loads(ex.read().decode("utf-8"))
        except Exception:
            body = {}
        if ex.code == 401:
            return {"ok": False, "error": "FAIR перезапустился и сменил токен — повторите запрос."}
        return {"ok": False, "error": body.get("error") or f"HTTP {ex.code} от FAIR"}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as ex:
        return {"ok": False,
                "error": f"Связь с FAIR не установлена (порт {ep.get('port')} молчит) — "
                         f"похоже, приложение закрыто. {ex}"}


@fair.tool()
def fair_status() -> str:
    """Состояние приложения FAIR: запущено ли, какой движок озвучки (Vox/Piper), голос,
    модель ИИ, занято ли оно, и списки доступных голосов и моделей. Вызывайте перед
    first обращением к fair_speak, чтобы выбрать voice/model."""
    return json.dumps(_call("/status", timeout=15), ensure_ascii=False, indent=1)


@fair.tool()
def fair_speak(text: str = "", url: str = "", prompt: str = "none", engine: str = "vox",
               voice: str = "", model: str = "", ratio: float = 0.0, gpu: bool = True,
               speed: float = 0.0, play: bool = False) -> str:
    """Обработать текст или статью и озвучить его через приложение FAIR.
    Вернёт JSON с audio_path — абсолютным путём к wav-файлу: отдайте файл
    пользователю строкой MEDIA:<audio_path> и перескажите text.

    Параметры:
      text   — сам текст для обработки/озвучки (или пуст, если задан url);
      url    — ссылка на статью в интернете: FAIR скачает и вычистит её сам;
      prompt — задание для нейросети (сжать, переписать простым языком, выделить главное...).
               "none" — без нейросети, озвучить текст как есть;
      engine — "vox" (клон голоса, GPU) или "piper" (быстрые готовые голоса, CPU);
      voice  — название голоса из fair_status (пусто = выбранный в окне FAIR);
      model  — имя gguf-модели ИИ из fair_status (пусто = выбранная в окне FAIR);
      ratio  — 0..1: уложить выжимку в этот доли объёма (0.3 = треть исходника); 0 — без лимита;
      gpu    — анализ на видеокарте (llama-server CUDA). false = на процессоре, медленнее;
      speed  — темп речи 0.2..3.0 (0 = как в приложении);
      play   — true: ещё и играть звук в колонки пользователя.
    Запрос не отменяется таймаутом Гермеса, если timeout велик; кнопка «Стоп» в окне
    FAIR отменяет озвучку. Приложение занято другой задачей — вернёт ошибку, повторите позже.
    """
    payload = {
        "text": text, "url": url, "prompt": prompt, "engine": engine,
        "voice": voice, "model": model, "ratio": ratio or None, "gpu": gpu,
        "speed": speed or None, "play": play,
    }
    return json.dumps(_call("/speak", payload, timeout=3600), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    fair.run()          # stdio-транспорт MCP
