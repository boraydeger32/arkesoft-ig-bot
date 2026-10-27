#!/usr/bin/env python3
"""
GÜNLÜK AKIŞ — her sabah GitHub Actions bunu çalıştırır (elle de çalıştırabilirsiniz).

  1. generate.py   Claude araştırır, içeriği yazar
  2. render.py     foto günü: görseller
  3. make_video.py reel günü: video
  4. git push      dosyalar GitHub Pages'te yayına girer (Instagram oradan çeker)
  5. publish.py    Instagram'a gönderir
  6. Telegram      her adımda haber verir; hata olursa hatayı yazar

Kullanım: python3 scripts/daily.py [YYYY-MM-DD] [--stage build|publish] [--no-push] [--dry-run]
  --stage build    sadece üret + Telegram önizleme + push   (GitHub Actions 1. adım)
  --stage publish  sadece yayınla + Telegram sonuç           (GitHub Actions, Pages yayınından sonra)
  (stage verilmezse ikisini art arda yapar)
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

from common import OUT, ROOT, WEEKDAYS_TR, load_settings, log, read_json, today
from notify import esc, tg_photo, tg_text, tg_video

KIND_TR = {"news": "günün haberi reeli", "trend": "trend reeli", "promo": "Arkesoft tanıtım reeli", "none": "foto post"}


def step(name: str, cmd: list[str]) -> str:
    log(f"▶ {name}")
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    sys.stdout.write(p.stdout)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout).strip().splitlines()[-12:]
        msg = f"❌ <b>Hata — {esc(name)}</b>\n<pre>{esc(chr(10).join(tail))[:1500]}</pre>"
        tg_text(msg)
        sys.exit(f"{name} başarısız.")
    return p.stdout


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def push(msg: str):
    git("config", "user.name", "igbot")
    git("config", "user.email", "igbot@users.noreply.github.com")
    git("add", "out/")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    git("commit", "-m", msg)
    for _ in range(3):
        if git("pull", "--rebase", check=False).returncode == 0 and git("push", check=False).returncode == 0:
            return
    tg_text("⚠️ GitHub'a push başarısız oldu; Actions logunu kontrol edin.")
    sys.exit("git push başarısız")


def main():
    args = sys.argv[1:]
    no_push, dry = "--no-push" in args, "--dry-run" in args
    stage = args[args.index("--stage") + 1] if "--stage" in args else "all"
    dates = [a for a in args if len(a) == 10 and a[4] == "-"]
    settings = load_settings()
    d = date.fromisoformat(dates[0]) if dates else today(settings)
    out_dir = OUT / d.isoformat()
    if stage == "publish":
        return publish_stage(d, out_dir, no_push, dry)
    kind = settings["reel_schedule"].get(str(d.weekday()), "none")
    label = f"{d.day:02d}.{d.month:02d} {WEEKDAYS_TR[d.weekday()]}"
    tg_text(f"🌅 <b>{label}</b> — plan: {KIND_TR.get(kind, kind)}. Üretim başladı.", silent=True)

    step("İçerik üretimi (Claude)", [sys.executable, "scripts/generate.py", d.isoformat()])
    content = read_json(out_dir / "content.json") or {}

    if content.get("post", {}).get("enabled"):
        step("Görseller", [sys.executable, "scripts/render.py", d.isoformat()])
    if content.get("reel", {}).get("enabled"):
        step("Video", [sys.executable, "scripts/make_video.py", d.isoformat()])
    content = read_json(out_dir / "content.json") or content

    # Önizlemeyi Telegram'a gönder
    post, reel = content.get("post", {}), content.get("reel", {})
    if reel.get("enabled") and (out_dir / "reel.mp4").exists():
        tg_video(out_dir / "reel.mp4", f"🎬 <b>Bugünün reeli</b> ({reel.get('duration', '?')} sn)\n{esc(reel.get('caption', ''))[:600]}")
    elif post.get("enabled") and post.get("files"):
        tg_photo(out_dir / post["files"][0], f"🖼 <b>{esc(post.get('headline', ''))}</b>\n{esc(post.get('caption', ''))[:600]}")

    if not content.get("publish", False):
        tg_text("⏸ <b>Onay bekliyor.</b> settings.json'da require_approval açık. GitHub'da "
                f"<code>out/{d.isoformat()}/content.json</code> içinde <code>\"publish\": true</code> yapınca bir sonraki çalışmada yayınlanır.")
        if not no_push:
            push(f"içerik (onay bekliyor): {d.isoformat()}")
        return

    if not no_push:
        push(f"içerik: {d.isoformat()}")
    if stage == "build":
        return
    publish_stage(d, out_dir, no_push, dry)


def publish_stage(d, out_dir, no_push, dry):
    content = read_json(out_dir / "content.json") or {}
    if not content:
        tg_text(f"ℹ️ {d.isoformat()} için içerik yok, yayın atlandı.")
        return
    if not content.get("publish", False):
        log("publish=false, yayın atlandı."); return
    step("Instagram'a yayınlama", [sys.executable, "scripts/publish.py", d.isoformat()] + (["--dry-run"] if dry else []))
    content = read_json(out_dir / "content.json") or content
    pub = content.get("published", {})
    links = [u for u in (pub.get("reel_url"), pub.get("post_url")) if u]
    if dry:
        tg_text("🧪 Prova tamamlandı (dry-run), Instagram'a gönderilmedi.")
    elif links:
        tg_text("✅ <b>Instagram'da yayında</b>\n" + "\n".join(links))
    else:
        tg_text("ℹ️ Yayınlanacak bir şey yoktu (daha önce yayınlanmış olabilir).")
    if not no_push:
        push(f"yayınlandı: {d.isoformat()}")


if __name__ == "__main__":
    main()
