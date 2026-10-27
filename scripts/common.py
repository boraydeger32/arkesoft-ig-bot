"""Tüm betiklerin ortak kullandığı küçük yardımcılar."""
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
OUT = ROOT / "out"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"

WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def load_settings() -> dict:
    with open(CONFIG / "settings.json", encoding="utf-8") as f:
        return json.load(f)


def today(settings: dict | None = None) -> date:
    settings = settings or load_settings()
    return datetime.now(ZoneInfo(settings.get("timezone", "Europe/Istanbul"))).date()


def date_label(d: date) -> str:
    return f"{d.day} {MONTHS_TR[d.month - 1]} {d.year}"


def day_dir(d: date | str) -> Path:
    s = d if isinstance(d, str) else d.isoformat()
    p = OUT / s
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log(*a):
    print("[igbot]", *a, flush=True)


def die(msg: str, code: int = 1):
    print("[igbot] HATA:", msg, file=sys.stderr, flush=True)
    sys.exit(code)


def env(name: str, required: bool = True) -> str:
    v = os.environ.get(name, "")
    if required and not v:
        die(f"{name} ortam değişkeni tanımlı değil. README'deki 'Anahtarlar' bölümüne bakın.")
    return v
