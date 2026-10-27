#!/usr/bin/env python3
"""
2. ADIM — Foto post görsellerini üretir.

content.json'daki metinleri templates/post.html şablonuna yerleştirip Playwright (ücretsiz, başsız Chrome)
ile PNG'ye çevirir: out/YYYY-MM-DD/post_1.png .. post_3.png (1080x1350, feed/carousel).
Reel videosu ayrı: make_video.py

Kullanım: python3 scripts/render.py [YYYY-MM-DD]
"""
import html
import re
import sys
from datetime import date

from playwright.sync_api import sync_playwright

from common import ASSETS, TEMPLATES, date_label, day_dir, die, load_settings, log, read_json, today


def esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def emphasize(s: str) -> str:
    """Metinde *kelime* biçimindeki parçaları mavi vurguya çevirir; yoksa son kelimeyi vurgular."""
    s = esc(s)
    if "*" in s:
        return re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    words = s.split()
    if len(words) >= 4:
        return " ".join(words[:-1]) + " <em>" + words[-1] + "</em>"
    return s


def fill(template: str, mapping: dict) -> str:
    for k, v in mapping.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def render_post(page, content: dict, out_dir, settings: dict) -> list[str]:
    post = content["post"]
    if not post.get("enabled"):
        return []
    tpl = (TEMPLATES / "post.html").read_text(encoding="utf-8").replace("{{FONT_URL}}", font_url())
    slides = post["slides"]
    files = []
    label = date_label(date.fromisoformat(content["date"]))
    for i, slide in enumerate(slides, 1):
        first = i == 1
        page_html = fill(tpl, {
            "DATE_LABEL": label,
            "TAG": "GÜNÜN TEKNOLOJİ NOTU" if first else f"{i}/{len(slides)}",
            "TITLE": emphasize(post["headline"] if first else slide.get("title", "")),
            "SUBLINE": esc(post.get("subline", "")) if first else "",
            "BODY": "" if first else esc(slide.get("body", "")),
            "SOURCE": ("Kaynak: " + post["source"]) if post.get("source") else "",
            "COUNTER": f"{i} / {len(slides)}" if len(slides) > 1 else "",
            "SWIPE": "KAYDIR  →" if (first and len(slides) > 1) else "ARKESOFT",
        })
        page.set_viewport_size({"width": 1080, "height": 1350})
        tmp = out_dir / f"_post_{i}.html"
        tmp.write_text(page_html, encoding="utf-8")
        page.goto(tmp.resolve().as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        tmp.unlink(missing_ok=True)
        path = out_dir / f"post_{i}.png"
        page.screenshot(path=str(path), full_page=False)
        files.append(path.name)
        log("görsel:", path.name)
    return files


def main():
    settings = load_settings()
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else today(settings)
    out_dir = day_dir(d)
    content = read_json(out_dir / "content.json")
    if not content:
        die(f"{out_dir / 'content.json'} yok. Önce generate.py çalıştırın.")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=1)
        content["post"]["files"] = render_post(page, content, out_dir, settings)
        browser.close()

    from common import write_json
    write_json(out_dir / "content.json", content)
    log("Görseller hazır.")


def font_url() -> str:
    return (ASSETS / "fonts" / "InterVariable.ttf").resolve().as_uri()


if __name__ == "__main__":
    main()
