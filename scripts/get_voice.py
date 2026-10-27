#!/usr/bin/env python3
"""
TEK SEFERLİK — Ücretsiz Türkçe seslendirme modelini (Piper) indirir.

Piper: açık kaynak, cihazda çalışan, internet gerektirmeyen TTS. Türkçe sesler:
  tr_TR-fahrettin-medium  (erkek, doğal)      ← varsayılan
  tr_TR-fettah-medium     (erkek, daha tok)
  tr_TR-dfki-medium       (kadın)

Kullanım: python3 scripts/get_voice.py [ses_adı]
Model assets/voices/<ses_adı>/ altına kurulur (~65 MB). Birden fazla indirip settings.json'dan seçebilirsiniz.
"""
import sys
import tarfile
import urllib.request
from pathlib import Path

from common import ASSETS, load_settings, log

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-{name}.tar.bz2"


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else load_settings().get("piper_voice", "tr_TR-fahrettin-medium")
    dest = ASSETS / "voices" / name
    if (dest / f"{name}.onnx").exists():
        log(f"{name} zaten kurulu: {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = BASE.format(name=name)
    tmp = dest.parent / f"{name}.tar.bz2"
    log(f"İndiriliyor: {url}")
    urllib.request.urlretrieve(url, tmp)
    log("Açılıyor...")
    with tarfile.open(tmp, "r:bz2") as tf:
        tf.extractall(dest.parent)
    (dest.parent / f"vits-piper-{name}").rename(dest)
    tmp.unlink()
    log(f"✔ Ses hazır: {dest}")
    log("Deneme: python3 -m piper -m assets/voices/%s/%s.onnx -f /tmp/deneme.wav <<< 'Merhaba, ben Arkesoft.'" % (name, name))


if __name__ == "__main__":
    main()
