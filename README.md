# ARKESOFT Instagram Botu — tamamen otomatik, tamamen ücretsiz

Her sabah **07:40**'ta bulutta (GitHub) kendi kendine çalışır:
günün yazılım/teknoloji gündemini araştırır → içeriği yazar → görsel ya da seslendirmeli motion video üretir → **~08:00'de Instagram'a paylaşır** → her adımda **Telegram'dan haber verir** (videoyu da gönderir).
Mac'inizin açık olmasına gerek yok. Sizin yapacağınız tek şey: **bir kerelik kurulum (bash setup.sh)**.

| Pzt | Sal | Çar | Per | Cum | Cmt | Paz |
|---|---|---|---|---|---|---|
| foto | **reel: Arkesoft tanıtımı** | foto | **reel: günün haberi** | foto | **reel: viral format** | foto |

(`config/settings.json` → `reel_schedule` / `post_days`. Her gün video istiyorsanız her güne bir tür yazın.)

```
 07:40  GitHub Actions (bulut, ücretsiz)
 ───────────────────────────────────────────────────────────────
 generate.py   Claude Code araştırır + yazar  (Max aboneliğiniz, API ücreti yok)
 render.py     foto günü: HTML şablon → PNG
 make_video.py reel günü: motion sahneleri → kare kare kayıt → seslendirme + müzik
 Pages         dosyalar GitHub Pages'te yayına girer (Instagram oradan çeker)
 publish.py    Meta Graph API ile Instagram'a gönderir
 Telegram      🌅 başladı → 🎬 işte video → ✅ yayında (link)  /  ❌ hata + sebebi
```

---

## Kurulum (bir kez, ~40 dk)

Zip'i açın, klasörü ev dizininize koyun, Terminal'de:

```bash
cd ~/arkesoft-ig-bot
bash setup.sh
```

Betik sırayla şunları yapar ve her adımda sizden sadece bir şey yapıştırmanızı ister:

| Adım | Betik ne yapar | Siz ne yaparsınız |
|---|---|---|
| 1 | Homebrew, git, node, python, gh, Claude Code'u kurar | Beklersiniz |
| 2 | `claude setup-token` çalıştırır | Tarayıcıda Max hesabınızla giriş → ekrandaki `sk-ant-oat…` anahtarını yapıştırırsınız |
| 3 | GitHub'a giriş, depoyu oluşturur, Pages'i açar | Tarayıcıda GitHub'a onay verirsiniz |
| 4 | Telegram'ı bağlar | Telefonda @BotFather → `/newbot` → TOKEN'ı yapıştırır, botunuza "merhaba" yazarsınız |
| 5 | Instagram anahtarını süresiz hale getirir | developers.facebook.com'da 4 tıklama (betik sayfaları açar ve anlatır) → App ID, App Secret, token yapıştırırsınız |
| 6 | Seslendirme anahtarı (isteğe bağlı) | Enter'a basıp geçebilirsiniz |
| 7 | Tüm anahtarları GitHub'a gizli olarak yükler | — |
| 8 | İlk provayı başlatır (Instagram'a göndermez) | 10-15 dk sonra Telegram'a gelen videoya bakarsınız |

Prova iyiyse **bitti**. Ertesi sabahtan itibaren kendi kendine paylaşır.
Hemen bugün gerçek paylaşım istiyorsanız: `gh workflow run daily.yml`

> Adım 5 (Meta) kurulumun tek "uğraştırıcı" kısmı. Instagram, hesabınıza paylaşım izni verecek anahtarı yalnızca hesap sahibi üretebilir; bu adımı sizin yerinize kimse yapamaz. 15 dakikadır, bir kere yapılır.

---

## Telegram'dan ne gelir?

- `🌅 27.10 Salı — plan: Arkesoft tanıtım reeli. Üretim başladı.`
- `🎬 Bugünün reeli (35 sn)` + videonun kendisi (foto gününde görselin kendisi)
- `✅ Instagram'da yayında` + paylaşımın linki
- Sorun olursa `❌ Hata — Video` + hatanın son satırları

Telegram'dan onay bekleme özelliği: `settings.json` → `"require_approval": true` yaparsanız bot üretir, Telegram'a gönderir, ama `"publish": true` yapana kadar paylaşmaz (GitHub'da dosyayı düzenlersiniz). Siz "hiçbir şey yapmayayım" dediğiniz için kapalı geliyor.

## Seslendirme

Hiçbir anahtar girmezseniz bot Microsoft Edge'in "sesli oku" servisini kullanır (Emel sesi, ücretsiz, anahtarsız) — resmi bir API değildir, bir gün kapanabilir; kapanırsa bot otomatik olarak Piper (açık kaynak, daha robotik) sesine düşer ve Telegram'dan haber verir.

Kalıcı ve daha iyi ses için (ikisi de ücretsiz, ticari kullanıma açık):

| Motor | Kurulum | Anahtar |
|---|---|---|
| **Azure Speech** (tavsiye) | portal.azure.com → "Speech" oluştur → Pricing tier **Free F0** → Keys and Endpoint | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` |
| **Google Cloud TTS** | console.cloud.google.com → Text-to-Speech API etkinleştir → API key | `GOOGLE_TTS_API_KEY` |
| ElevenLabs (ücretli, 5-6 $/ay) | elevenlabs.io → API key | `ELEVEN_API_KEY`, `ELEVEN_VOICE_ID` |

Anahtarı sonradan eklemek: `gh secret set AZURE_SPEECH_KEY -b "..."` ve `gh secret set AZURE_SPEECH_REGION -b "westeurope"`. Ses seçimi `settings.json` → `azure_voice` (`tr-TR-EmelNeural` kadın / `tr-TR-AhmetNeural` erkek), `edge_voice`, `google_voice`.

## Müzik

`assets/music/` klasörüne telifsiz mp3 koyup `git add . && git commit -m müzik && git push` yapın (Pixabay Music, YouTube Audio Library). Bot her gün birini seçer, konuşurken sesini kısar. Koymazsanız video sadece seslendirmeli olur.

## Reel videoları nasıl üretiliyor?

`templates/motion.html` içinde sizin tanıtım videonuzun kurgusuna benzer 8 animasyonlu sahne var:
`title` (kinetik metin) · `chaos` (uçuşan arayüz pencereleri + etiketler) · `counter` (kırmızı "boşa giden zaman" sayacı) · `orb` (ışıklı tek merkez) · `dashboard` (KPI + canlı grafik) · `headline` (haber kartı) · `list` (numaralı maddeler) · `outro` (logo + çağrı).

Claude her gün bu sahnelerden 5-7 tanesini seçip metinlerini ve seslendirme cümlelerini yazar (`prompts/daily.md`). `make_video.py` her sahneyi seslendirir, süreyi konuşmaya göre ayarlar, 30 fps kare kare kaydeder.

- Renkler: `motion.html` üstündeki `:root` (`--accent`, `--danger`...).
- Sahte pencere içerikleri (sipariş tablosu, Excel, WhatsApp...): aynı dosyada `WINDOWS`.
- Yeni sahne türü: `SCENES`'e fonksiyon + CSS, `prompts/daily.md` tablosuna bir satır.
- Marka sesi, hizmetler, yasaklar: `config/brand.md` — Claude her sabah okur.

Herhangi bir değişiklikten sonra `git add . && git commit -m "..." && git push`; ertesi sabah geçerli olur.

## Elle çalıştırma / kontrol

- GitHub → **Actions → Günlük Instagram paylaşımı → Run workflow** (`dry_run` işaretli = prova).
- Terminalden: `gh workflow run daily.yml` (gerçek) · `gh workflow run daily.yml -f dry_run=true` (prova) · `gh run list` (geçmiş).
- Mac'te yerel deneme (Claude Code kurulu ve giriş yapılmışsa): `source .venv/bin/activate && source .env && python3 scripts/daily.py --no-push --dry-run`

## Sorun çözme

| Telegram'da gelen / belirti | Çözüm |
|---|---|
| `❌ Hata — İçerik üretimi (Claude)` + "authentication" | `claude setup-token` yeniden çalıştırıp `gh secret set CLAUDE_CODE_OAUTH_TOKEN -b "..."` ile güncelleyin (anahtar yaklaşık 1 yıl geçerli). |
| `❌ Hata — Instagram'a yayınlama` + `(190)` | Instagram anahtarı geçersiz. `python3 scripts/setup_token.py ...` tekrar, sonra `gh secret set IG_ACCESS_TOKEN -b "..."`. |
| `Dosya herkese açık adreste bulunamadı` | GitHub → Settings → Pages → Source "GitHub Actions" olmalı. |
| `Medya işlenemedi` | Video 3-90 sn, 9:16, MP4 olmalı (bot zaten böyle). Müzik dosyası bozuksa kaldırın. |
| Ses robotik | Edge kapanmış, Piper devreye girmiş. Azure anahtarı ekleyin (yukarıda). |
| Hiç mesaj gelmedi | GitHub → Actions'ta çalışma var mı? Yoksa depo 60 gün hareketsiz kalınca GitHub zamanlayıcıyı kapatır; herhangi bir commit yeniden açar. |
| `Video ... sn — Instagram Reels sınırı 90 sn` | Claude uzun yazmış; `gh workflow run daily.yml` ile yeniden çalıştırın (yeniden üretir). |

## Güvenlik ve telif

- Anahtarlar yalnızca GitHub Secrets'ta ve Mac'teki `.env` dosyasında; depo herkese açık ama içinde anahtar yok.
- Bot viral videoları kopyalamaz; formatı kendi metniyle uyarlar (`brand.md` kural 3).
- Her haber paylaşımının altında "Kaynak: …" olur. İlk haftalarda Telegram'a gelen içeriklere göz atın; yapay zeka nadiren yanlış anlayabilir, `brand.md`'ye bir cümle ekleyerek düzeltirsiniz.
- Müzik: Instagram'ın kütüphanesindeki ticari parçalar API ile eklenemez; telifsiz kaynak kullanın.
