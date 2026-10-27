#!/usr/bin/env python3
"""
SES SEÇİMİ — Aday sesleri aynı cümleyle okutur, out/voice_test/ klasörüne mp3 olarak koyar.
Dinleyin, beğendiğinizi settings.json → azure_voice'a yazın.

Kullanım:  source .venv/bin/activate && source .env && python3 scripts/voice_test.py
Sadece belirli sesler:  python3 scripts/voice_test.py tr-TR-AhmetNeural en-US-Ava:DragonHDOmniLatestNeural
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts_engines as T  # noqa: E402
from common import OUT, load_settings, log  # noqa: E402

SAMPLE = ("İşiniz büyüyor... ama sisteminiz büyümüyor. // Siparişler bir yerde, stoklar Excel'de, "
          "şikâyetler WhatsApp'ta. // Peki bunları birbirine bağlayan tek şey ne? // "
          "*Tek bir dijital merkez.* Arkesoft. Projenizi konuşalım.")

# Ücretsiz F0 katmanında çalışması beklenen adaylar (üstte en çok önerilenler)
CANDIDATES = [
    # Türkçe yerel sesler
    ("tr-TR-EmelNeural",                      "Türkçe · kadın · varsayılan"),
    ("tr-TR-AhmetNeural",                     "Türkçe · erkek"),
    # Çok dilli sesler (Türkçeyi doğal aksanla okur, tonlaması daha zengin)
    ("en-US-AvaMultilingualNeural",           "çok dilli · kadın · sıcak"),
    ("en-US-AndrewMultilingualNeural",        "çok dilli · erkek · güven veren"),
    ("en-US-BrianMultilingualNeural",         "çok dilli · erkek · genç"),
    ("en-US-EmmaMultilingualNeural",          "çok dilli · kadın · canlı"),
    ("de-DE-SeraphinaMultilingualNeural",     "çok dilli · kadın · yumuşak"),
    ("de-DE-FlorianMultilingualNeural",       "çok dilli · erkek · derin"),
    ("fr-FR-VivienneMultilingualNeural",      "çok dilli · kadın"),
    ("fr-FR-RemyMultilingualNeural",          "çok dilli · erkek"),
    # HD sesler (en doğal; F0'da kapalıysa 'HD yok' yazar, sorun değil)
    ("en-US-Ava:DragonHDLatestNeural",        "HD · kadın · duygu algılar"),
    ("en-US-Andrew:DragonHDLatestNeural",     "HD · erkek · duygu algılar"),
    ("de-DE-Seraphina:DragonHDLatestNeural",  "HD · kadın"),
    ("de-DE-Florian:DragonHDLatestNeural",    "HD · erkek"),
    ("en-US-Ava:DragonHDOmniLatestNeural",    "HD Omni · kadın · çok dilli"),
    ("en-US-Andrew:DragonHDOmniLatestNeural", "HD Omni · erkek · çok dilli"),
]


def main():
    s = load_settings()
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    cands = [(v, "") for v in want] if want else CANDIDATES
    out_dir = OUT / "voice_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    tones = ["urgent", "calm", "confident", "warm", "warm"]
    ok = []
    for voice, desc in cands:
        wav = out_dir / (voice.replace(":", "_") + ".wav")
        try:
            # Aynı sesi 3 farklı tonla art arda okut → tonlama farkını duyun
            parts = []
            for i, (sent, tone) in enumerate(zip(SAMPLE.split(" // "), tones)):
                part = out_dir / f"_{voice.replace(':', '_')}_{i}.wav"
                T.azure(sent, part, s, voice=voice, tone=tone)
                parts.append(part)
            lst = out_dir / "_list.txt"
            lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), str(wav)], check=True)
            mp3 = wav.with_suffix(".mp3")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(mp3)], check=True)
            for p in parts + [wav, lst]:
                p.unlink(missing_ok=True)
            ok.append(voice)
            log(f"✔ {voice:<42} {desc}")
        except SystemExit as e:
            msg = str(e)
            tag = "HD yok (ücretli katman)" if ("DragonHD" in voice and ("400" in msg or "403" in msg or "404" in msg)) else msg[:90]
            log(f"✗ {voice:<42} {tag}")
    log(f"\n{len(ok)} ses hazır → {out_dir}")
    log("Dinleyin; beğendiğinizi config/settings.json → \"azure_voice\" alanına yazın, sonra: git add . && git commit -m ses && git push")
    if sys.platform == "darwin":
        subprocess.run(["open", str(out_dir)])


if __name__ == "__main__":
    main()
