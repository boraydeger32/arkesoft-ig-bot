#!/usr/bin/env python3
"""
Telegram bildirimleri. TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID yoksa sessizce hiçbir şey yapmaz.

Kullanım (betiklerden):  from notify import tg_text, tg_photo, tg_video
Kullanım (komut satırı): python3 scripts/notify.py "mesaj"
"""
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

from common import log


def _cfg():
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    return (tok, chat) if (tok and chat and requests) else (None, None)


def _post(method: str, **kw):
    tok, chat = _cfg()
    if not tok:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{tok}/{method}", data={"chat_id": chat, **kw.get("data", {})},
                          files=kw.get("files"), timeout=120)
        if r.status_code != 200:
            log("Telegram hatası:", r.text[:200])
        return r.status_code == 200
    except requests.RequestException as e:
        log("Telegram erişilemedi:", e)
        return False


def tg_text(text: str, silent: bool = False) -> bool:
    return _post("sendMessage", data={"text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": "true",
                                      "disable_notification": "true" if silent else "false"})


def tg_photo(path: Path, caption: str = "") -> bool:
    with open(path, "rb") as f:
        return _post("sendPhoto", data={"caption": caption[:1000], "parse_mode": "HTML"}, files={"photo": f})


def tg_video(path: Path, caption: str = "") -> bool:
    with open(path, "rb") as f:
        return _post("sendVideo", data={"caption": caption[:1000], "parse_mode": "HTML", "supports_streaming": "true"},
                     files={"video": f})


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    ok = tg_text(" ".join(sys.argv[1:]) or "Test: Arkesoft botu bağlı ✅")
    print("gönderildi" if ok else "gönderilemedi (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID eksik?)")
