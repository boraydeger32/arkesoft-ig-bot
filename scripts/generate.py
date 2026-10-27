#!/usr/bin/env python3
"""
1. ADIM — İçerik üretimi.

Claude Code'u (Max aboneliğinizle, API ücreti olmadan) komut satırından çağırır,
günün teknoloji gündemini araştırtır ve out/YYYY-MM-DD/content.json dosyasını yazar.

Kullanım:
  python3 scripts/generate.py            # bugünün içeriği
  python3 scripts/generate.py 2026-10-28 # belirli bir gün için (test)
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date

from common import (ROOT, OUT, WEEKDAYS_TR, day_dir, die, load_settings, log,
                    read_json, today, write_json)

REQUIRED_TAGS = ["#arkesoft", "#yazılım", "#webtasarım"]

POST_INSTRUCTIONS = (
    "Bulduğun en ilgi çekici, güvenilir teknoloji/yazılım haberini seç. "
    "1-3 slaytlık bir 'bilgi kartı' yaz: ilk slayt vurucu başlık + alt başlık, sonraki slaytlar "
    "'ne oldu / neden önemli / bize ne söylüyor' gibi kısa açıklamalar. "
    "Mümkünse bir cümleyle KOBİ'ler veya yazılım ekipleri için anlamını yaz."
)

REEL_INSTRUCTIONS = {
    "news": (
        "Bugün bir 'news' reeli: günün en önemli teknoloji/yazılım haberini 25-40 saniyelik motion video olarak anlat "
        "(kurgu: title → headline → list → orb/dashboard → outro). Kaynağı headline sahnesine ve caption'a yaz."
    ),
    "trend": (
        "Bugün bir 'trend' reeli: araştırmada bulduğun, son günlerde Instagram/TikTok/X'te çok konuşulan bir video FORMATINI "
        "(ör. 'beklenti vs gerçek', '3 şey bilmeliydim', 'bunu kimse söylemiyor') yazılım ve dijital ajans dünyasına uyarla. "
        "Tamamen kendi metnimizle, kimseyi anmadan; mizah hafif. Kurgu: title → list/chaos → orb → outro."
    ),
    "promo": (
        "Bugün bir 'promo' reeli: ARKESOFT'u tanıtan, bir müşteri sorunuyla açılan dikkat çekici motion video "
        "(kurgu: title[danger] → chaos → counter → orb → dashboard → outro). brand.md'deki hizmetlerden BİRİNE odaklan; "
        "history.json'da son günlerde işlenen hizmeti tekrar etme. Satış baskısı yok, güven ver."
    ),
}
SCENE_TYPES = {"title", "chaos", "counter", "orb", "dashboard", "headline", "list", "outro"}

TREND_INSTRUCTION = (
    "Ayrıca sosyal medyada son günlerde popüler olan 1-2 kısa video formatını araştır "
    "(hangi kalıp/akış viral olmuş). Sadece FORMATI not al; kişi, hesap ve marka adı yazma."
)


def build_prompt(d: date, settings: dict) -> tuple[str, str]:
    weekday = d.weekday()
    reel_kind = settings["reel_schedule"].get(str(weekday), "none")
    post_enabled = weekday in settings["post_days"] and reel_kind == "none"   # günde tek paylaşım: reel günü foto yok

    tpl = (ROOT / "prompts" / "daily.md").read_text(encoding="utf-8")
    post_instr = POST_INSTRUCTIONS if post_enabled else "Bugün görsel post YOK. post.enabled=false yaz, diğer alanları boş bırak."
    if reel_kind == "none":
        reel_instr = "Bugün reel YOK. reel.enabled=false yaz, diğer alanları boş bırak."
        trend_instr = "Bugün trend araştırması gerekmiyor."
    else:
        reel_instr = REEL_INSTRUCTIONS[reel_kind]
        trend_instr = TREND_INSTRUCTION if reel_kind == "trend" else "Bugün trend araştırması gerekmiyor."

    prompt = (tpl.replace("{{DATE}}", d.isoformat())
                 .replace("{{WEEKDAY_TR}}", WEEKDAYS_TR[weekday])
                 .replace("{{POST_INSTRUCTION}}", post_instr)
                 .replace("{{REEL_INSTRUCTION}}", reel_instr)
                 .replace("{{TREND_INSTRUCTION}}", trend_instr)
                 .replace("{{REEL_KIND}}", reel_kind))
    return prompt, reel_kind


def run_claude(prompt: str, settings: dict) -> str:
    cmd_name = settings.get("claude_cmd", "claude")
    if not shutil.which(cmd_name):
        die(f"'{cmd_name}' komutu bulunamadı. Claude Code kurulu mu? (README → Kurulum → Adım 2)")
    schema = (ROOT / "prompts" / "schema.json").read_text(encoding="utf-8")
    cmd = [
        cmd_name, "-p", prompt,
        "--output-format", "json",
        "--json-schema", schema,
        "--model", settings.get("claude_model", "sonnet"),
        "--max-turns", str(settings.get("claude_max_turns", 40)),
        "--allowedTools", "WebSearch,WebFetch,Read",
        "--permission-mode", "dontAsk",
    ]
    log("Claude Code çalışıyor (araştırma + yazım, 1-3 dakika sürebilir)...")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200)
    if proc.returncode != 0:
        die(f"Claude Code hata verdi (kod {proc.returncode}):\n{proc.stderr[-2000:] or proc.stdout[-2000:]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout
    if isinstance(envelope, dict):
        if envelope.get("is_error"):
            die(f"Claude Code hata döndürdü: {envelope.get('result')}")
        if envelope.get("structured_output"):
            return json.dumps(envelope["structured_output"], ensure_ascii=False)
        return str(envelope.get("result", ""))
    return proc.stdout


def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        die("Claude'un çıktısında JSON bulunamadı:\n" + text[:1500])
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        die(f"JSON ayrıştırılamadı ({e}):\n" + text[:1500])


def tidy(content: dict, d: date, reel_kind: str, settings: dict) -> dict:
    content["date"] = d.isoformat()
    content["publish"] = not settings.get("require_approval", False)
    content["published"] = {}

    post = content.setdefault("post", {})
    post.setdefault("enabled", bool(post.get("headline")))
    post["slides"] = (post.get("slides") or [])[:3]
    if post["enabled"] and not post["slides"]:
        post["slides"] = [{"title": post.get("headline", ""), "body": post.get("subline", "")}]
    post["hashtags"] = merge_tags(post.get("hashtags"))

    reel = content.setdefault("reel", {})
    reel["kind"] = reel_kind
    scenes = [s for s in (reel.get("scenes") or []) if isinstance(s, dict) and s.get("type") in SCENE_TYPES][:8]
    if scenes and scenes[-1]["type"] != "outro":
        scenes.append({"type": "outro", "title": "Strateji, tasarım ve teknoloji. Aynı takımda.",
                       "cap": "Projenizi konuşalım · arkesoft.com", "voice": "Arkesoft. Projenizi konuşalım."})
    reel["scenes"] = scenes
    reel["enabled"] = reel_kind != "none" and len(scenes) >= 3
    if reel_kind != "none" and not reel["enabled"]:
        log("UYARI: reel sahnesi çok az (<3), reel kapatıldı.")
    reel["hashtags"] = merge_tags(reel.get("hashtags"))
    return content


def merge_tags(tags) -> list[str]:
    tags = [t if t.startswith("#") else "#" + t for t in (tags or []) if t]
    for r in REQUIRED_TAGS:
        if r.lower() not in [t.lower() for t in tags]:
            tags.append(r)
    return tags[:15]


def append_history(content: dict) -> None:
    hist_path = OUT / "history.json"
    hist = read_json(hist_path, [])
    hist = [h for h in hist if h.get("date") != content["date"]]
    hist.append({
        "date": content["date"],
        "post_headline": content["post"].get("headline", ""),
        "post_source": content["post"].get("source_url", ""),
        "reel_kind": content["reel"].get("kind", ""),
        "reel_hook": " / ".join((content["reel"].get("scenes") or [{}])[0].get("lines") or [(content["reel"].get("scenes") or [{}])[0].get("title", "")]),
        "note": content.get("history_note", ""),
    })
    write_json(hist_path, hist[-60:])


def main():
    settings = load_settings()
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else today(settings)
    out_dir = day_dir(d)
    target = out_dir / "content.json"
    if target.exists() and "--force" not in sys.argv:
        log(f"{target} zaten var, atlanıyor. Yeniden üretmek için --force ekleyin.")
        return

    prompt, reel_kind = build_prompt(d, settings)
    raw = run_claude(prompt, settings)
    content = tidy(extract_json(raw), d, reel_kind, settings)
    write_json(target, content)
    (out_dir / "claude_raw.txt").write_text(raw, encoding="utf-8")
    append_history(content)
    log(f"İçerik hazır → {target}")
    log("Post:", content["post"].get("headline") or "(yok)")
    log("Reel:", f'{content["reel"]["kind"]} · {len(content["reel"]["scenes"])} sahne' if content["reel"]["enabled"] else "(yok)")


if __name__ == "__main__":
    main()
