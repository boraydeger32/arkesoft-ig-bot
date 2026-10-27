#!/usr/bin/env python3
"""
TEK SEFERLİK KURULUM — Instagram anahtarlarını alır.

Graph API Explorer'dan aldığınız kısa ömürlü kullanıcı anahtarını,
süresi dolmayan bir SAYFA anahtarına çevirir ve Instagram hesap ID'nizi bulur.

Kullanım:
  python3 scripts/setup_token.py <APP_ID> <APP_SECRET> <KISA_OMURLU_KULLANICI_TOKENI>

Sonunda .env dosyasına IG_ACCESS_TOKEN ve IG_USER_ID yazar (bu dosya git'e gitmez).
Aynı değerleri GitHub → Settings → Secrets'a da ekleyeceksiniz (README).
"""
import sys
from pathlib import Path

import requests

V = "v26.0"
ROOT = Path(__file__).resolve().parent.parent


def get(path, **params):
    r = requests.get(f"https://graph.facebook.com/{V}/{path}", params=params, timeout=60)
    data = r.json()
    if "error" in data:
        sys.exit(f"HATA: {data['error'].get('message')}")
    return data


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    app_id, app_secret, short_token = sys.argv[1:4]

    print("1/3 Uzun ömürlü kullanıcı anahtarı alınıyor...")
    long_user = get("oauth/access_token", grant_type="fb_exchange_token",
                    client_id=app_id, client_secret=app_secret, fb_exchange_token=short_token)["access_token"]

    print("2/3 Facebook sayfalarınız listeleniyor...")
    pages = get("me/accounts", access_token=long_user, fields="id,name,access_token,instagram_business_account").get("data", [])
    pages = [p for p in pages if p.get("instagram_business_account")]
    if not pages:
        sys.exit("HATA: Instagram hesabına bağlı bir Facebook sayfası bulunamadı.\n"
                 "Instagram → Ayarlar → Hesap merkezi → Facebook sayfanızı bağlayın, sonra tekrar deneyin.")
    if len(pages) > 1:
        print("Birden fazla sayfa bulundu:")
        for i, p in enumerate(pages, 1):
            print(f"  {i}) {p['name']}")
        choice = int(input("Hangisi? (numara): ")) - 1
    else:
        choice = 0
    page = pages[choice]
    page_token = page["access_token"]      # uzun ömürlü kullanıcı anahtarından türetilen sayfa anahtarı süresiz olur
    ig_id = page["instagram_business_account"]["id"]

    print("3/3 Instagram hesabı doğrulanıyor...")
    ig = get(ig_id, access_token=page_token, fields="username,name")
    print(f"\n✔ Bağlı Instagram hesabı: @{ig.get('username')}  (ID: {ig_id})")

    env_path = ROOT / ".env"
    env_path.write_text(f"IG_ACCESS_TOKEN={page_token}\nIG_USER_ID={ig_id}\n", encoding="utf-8")
    print(f"✔ Anahtarlar yazıldı: {env_path}")
    print("\nŞimdi aynı iki değeri GitHub deposunda Settings → Secrets and variables → Actions'a ekleyin:")
    print(f"  IG_USER_ID      = {ig_id}")
    print(f"  IG_ACCESS_TOKEN = {page_token[:12]}... (.env dosyasındaki tam değer)")


if __name__ == "__main__":
    main()
