#!/usr/bin/env python3
"""
4. ADIM — Instagram'a yayınlar (Meta'nın resmi, ücretsiz Graph API'si).

Gerekli ortam değişkenleri (README → Anahtarlar):
  IG_ACCESS_TOKEN  Sayfa erişim anahtarı (süresiz) veya uzun ömürlü kullanıcı anahtarı
  IG_USER_ID       Instagram profesyonel hesabınızın sayısal ID'si

Görseller ve video GitHub Pages üzerinden çekilir (out/ klasörü Pages'in kökü olarak yayınlanır):
  {public_base_url}/YYYY-MM-DD/post_1.png
  {public_base_url}/YYYY-MM-DD/reel.mp4
GitHub Actions'ta PUBLIC_BASE_URL ortam değişkeni otomatik verilir; yerelde settings.json → public_base_url.

Kullanım: python3 scripts/publish.py [YYYY-MM-DD] [--dry-run]
"""
import os
import sys
import time
from datetime import date

import requests

from common import day_dir, die, env, load_settings, log, read_json, today, write_json

GRAPH = "https://graph.facebook.com"


class IG:
    def __init__(self, token: str, user_id: str, version: str):
        self.token, self.user_id, self.v = token, user_id, version

    def _call(self, method: str, path: str, **params):
        params["access_token"] = self.token
        url = f"{GRAPH}/{self.v}/{path.lstrip('/')}"
        r = requests.request(method, url, params=params if method == "GET" else None,
                             data=None if method == "GET" else params, timeout=60)
        try:
            data = r.json()
        except ValueError:
            die(f"Meta beklenmeyen yanıt verdi ({r.status_code}): {r.text[:500]}")
        if "error" in data:
            e = data["error"]
            die(f"Meta API hatası ({e.get('code')}/{e.get('error_subcode')}): {e.get('message')}\n"
                f"  → {e.get('error_user_msg') or ''}")
        return data

    def get(self, path, **p):
        return self._call("GET", path, **p)

    def post(self, path, **p):
        return self._call("POST", path, **p)

    def wait_until_ready(self, container_id: str, max_wait: int = 420) -> None:
        waited = 0
        while waited < max_wait:
            s = self.get(container_id, fields="status_code,status")
            code = s.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                die(f"Medya işlenemedi: {s}")
            time.sleep(10)
            waited += 10
        die("Medya işleme zaman aşımına uğradı (7 dk). Daha sonra tekrar deneyin.")

    def publish(self, container_id: str) -> str:
        return self.post(f"{self.user_id}/media_publish", creation_id=container_id)["id"]

    def permalink(self, media_id: str) -> str:
        try:
            return self.get(media_id, fields="permalink").get("permalink", "")
        except SystemExit:
            return ""


def caption_of(block: dict) -> str:
    cap = (block.get("caption") or "").strip()
    tags = " ".join(block.get("hashtags") or [])
    return (cap + "\n\n" + tags).strip()[:2200]


def wait_for_url(url: str, tries: int = 12, delay: int = 30) -> None:
    """GitHub Pages yayını birkaç dakika gecikebilir; dosya erişilebilene kadar bekle."""
    for i in range(tries):
        try:
            r = requests.head(url, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                return
            log(f"{url} henüz hazır değil ({r.status_code}), {delay}s bekleniyor... [{i + 1}/{tries}]")
        except requests.RequestException as e:
            log(f"{url} erişilemedi ({e}), {delay}s bekleniyor... [{i + 1}/{tries}]")
        time.sleep(delay)
    die(f"Dosya herkese açık adreste bulunamadı: {url}\n"
        "GitHub Pages açık mı? settings.json → public_base_url doğru mu?")


def publish_post(ig: IG, content: dict, base: str, dry: bool) -> str | None:
    post = content["post"]
    if not post.get("enabled") or not post.get("files"):
        log("Görsel post yok, atlandı.")
        return None
    urls = [f"{base}/{f}" for f in post["files"]]
    caption = caption_of(post)
    log("Post yayınlanıyor:", post.get("headline"))
    if dry:
        log("  [dry-run] URL'ler:", urls)
        return "dry"
    for u in urls:
        wait_for_url(u)
    if len(urls) == 1:
        cid = ig.post(f"{ig.user_id}/media", image_url=urls[0], caption=caption)["id"]
    else:
        children = [ig.post(f"{ig.user_id}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
        cid = ig.post(f"{ig.user_id}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    ig.wait_until_ready(cid)
    media_id = ig.publish(cid)
    log("  ✔ Post yayında, id:", media_id)
    return media_id


def publish_reel(ig: IG, content: dict, base: str, dry: bool) -> str | None:
    reel = content["reel"]
    if not reel.get("enabled") or not reel.get("video_file"):
        log("Reel yok, atlandı.")
        return None
    video_url = f"{base}/{reel['video_file']}"
    cover_url = f"{base}/{reel['cover_file']}" if reel.get("cover_file") else None
    caption = caption_of(reel)
    first = (reel.get("scenes") or [{}])[0]
    log("Reel yayınlanıyor:", " ".join(first.get("lines") or [first.get("title", "")]))
    if dry:
        log("  [dry-run] video:", video_url)
        return "dry"
    wait_for_url(video_url)
    params = dict(media_type="REELS", video_url=video_url, caption=caption, share_to_feed="true")
    if cover_url:
        wait_for_url(cover_url)
        params["cover_url"] = cover_url
    cid = ig.post(f"{ig.user_id}/media", **params)["id"]
    log("  Instagram videoyu işliyor (1-5 dk)...")
    ig.wait_until_ready(cid)
    media_id = ig.publish(cid)
    log("  ✔ Reel yayında, id:", media_id)
    return media_id


def main():
    dry = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    settings = load_settings()
    d = date.fromisoformat(args[0]) if args else today(settings)
    out_dir = day_dir(d)
    content = read_json(out_dir / "content.json")
    if not content:
        log(f"{d} için içerik yok ({out_dir / 'content.json'}). Çıkılıyor.")
        return
    if not content.get("publish", False):
        log(f"{d}: content.json içinde publish=false → yayınlanmadı (onay bekliyor).")
        return

    public = os.environ.get("PUBLIC_BASE_URL") or settings["public_base_url"]
    base = public.rstrip("/") + f"/{d.isoformat()}"
    if "KULLANICIADI" in base and not dry:
        die("public_base_url ayarlı değil. GitHub Actions bunu otomatik verir; yerelde settings.json'a Pages adresinizi yazın.")

    ig = None if dry else IG(env("IG_ACCESS_TOKEN"), env("IG_USER_ID"), settings.get("instagram_api_version", "v26.0"))
    published = content.setdefault("published", {})

    if published.get("post"):
        log("Post daha önce yayınlanmış, atlandı.")
    else:
        mid = publish_post(ig, content, base, dry)
        if mid and not dry:
            published["post"] = mid
            published["post_url"] = ig.permalink(mid)
            write_json(out_dir / "content.json", content)

    if published.get("reel"):
        log("Reel daha önce yayınlanmış, atlandı.")
    else:
        mid = publish_reel(ig, content, base, dry)
        if mid and not dry:
            published["reel"] = mid
            published["reel_url"] = ig.permalink(mid)
            write_json(out_dir / "content.json", content)

    log("Bitti.")


if __name__ == "__main__":
    main()
