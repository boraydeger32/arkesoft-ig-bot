#!/usr/bin/env python3
"""
TEK SEFERLİK — Telegram bildirimlerini bağlar.

1) Telegram'da @BotFather'a yazın: /newbot → bir ad ve kullanıcı adı verin → size bir TOKEN verir.
2) Yeni botunuza Telegram'dan herhangi bir mesaj gönderin (örn. "merhaba").
3) Bu betiği çalıştırın:  python3 scripts/telegram_setup.py TOKEN
   Chat ID'nizi bulur, .env dosyasına yazar ve test mesajı yollar.
"""
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tok = sys.argv[1].strip()
    r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=30).json()
    if not r.get("ok"):
        sys.exit(f"HATA: token geçersiz görünüyor: {r}")
    chats = [u["message"]["chat"] for u in r.get("result", []) if "message" in u]
    if not chats:
        sys.exit("Henüz mesaj yok. Telegram'da botunuza 'merhaba' yazıp bu komutu tekrar çalıştırın.")
    chat = chats[-1]
    chat_id = str(chat["id"])
    name = chat.get("first_name") or chat.get("title") or chat_id
    env_path = ROOT / ".env"
    lines = [l for l in (env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else [])
             if not l.startswith(("TELEGRAM_BOT_TOKEN=", "TELEGRAM_CHAT_ID="))]
    lines += [f"TELEGRAM_BOT_TOKEN={tok}", f"TELEGRAM_CHAT_ID={chat_id}"]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                  data={"chat_id": chat_id, "text": "✅ Arkesoft Instagram botu bağlandı. Her sabah buradan haber vereceğim."}, timeout=30)
    print(f"✔ Bağlandı: {name} (chat id {chat_id}). Test mesajı gönderildi, .env güncellendi.")


if __name__ == "__main__":
    main()
