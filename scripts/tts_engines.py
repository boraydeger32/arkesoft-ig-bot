"""
Seslendirme motorları. Hepsi aynı imzayı kullanır: synth(text, out_wav_path, settings) -> Path | None

Motor seçimi (settings.json → tts_engine):
  auto        .env'de hangi anahtar varsa onu kullanır: elevenlabs → azure → google; hiçbiri yoksa edge → piper → say
  elevenlabs  ELEVEN_API_KEY (+ eleven_voice_id)       en doğal; ücretsiz plan ticari kullanıma KAPALI, Starter ~5$/ay
  azure       AZURE_SPEECH_KEY + AZURE_SPEECH_REGION   Microsoft nöral sesler (Emel, Ahmet); F0 katmanı ücretsiz
  google      GOOGLE_TTS_API_KEY                        Google Chirp 3 HD / WaveNet; aylık 1M karakter ücretsiz
  edge        anahtar yok                               Microsoft Edge "sesli oku" servisi; resmi değil, bir gün kapanabilir
  piper       anahtar yok, internet yok                 açık kaynak, cihazda çalışır (kalitesi orta)
  say         sadece macOS                              sistem sesi
"""
import base64
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from common import ASSETS, die, log

try:
    import requests
except ImportError:  # requests yoksa cloud motorlar çalışmaz, yerel motorlar çalışır
    requests = None


def _run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        die("Komut başarısız:\n" + " ".join(map(str, cmd)) + "\n" + (p.stderr or p.stdout)[-1500:])
    return p


def _to_wav(src: Path, out: Path):
    """Her motorun çıktısını 48 kHz stereo, normalize edilmiş WAV'a çevirir."""
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", "48000", "-ac", "2",
          "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(out)])
    src.unlink(missing_ok=True)
    return out


def _need(name):
    v = os.environ.get(name, "")
    if not v:
        die(f"{name} tanımlı değil. .env dosyasına ekleyin (README → Seslendirme).")
    return v


# ---------------- ElevenLabs ----------------
def elevenlabs(text, out, s):
    key = _need("ELEVEN_API_KEY")
    voice = os.environ.get("ELEVEN_VOICE_ID") or s.get("eleven_voice_id") or "21m00Tcm4TlvDq8ikWAM"
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                      params={"output_format": "mp3_44100_128"},
                      headers={"xi-api-key": key, "Content-Type": "application/json"},
                      json={"text": text.replace("//", "... ").replace("|", ",").replace("*", ""), "model_id": s.get("eleven_model", "eleven_multilingual_v2"),
                            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.2, "use_speaker_boost": True}},
                      timeout=120)
    if r.status_code != 200:
        die(f"ElevenLabs hatası {r.status_code}: {r.text[:400]}")
    tmp = out.with_suffix(".mp3"); tmp.write_bytes(r.content)
    return _to_wav(tmp, out)


# ---------------- Azure (Microsoft) ----------------
# Ton ön ayarları: Claude her sahneye bir "tone" yazar, biz prosodiye çeviririz.
TONES = {
    "urgent":    dict(rate="+8%",  pitch="+4%",  volume="+10%"),   # sorun, gerilim
    "calm":      dict(rate="-6%",  pitch="-2%",  volume="+0%"),    # sakin, güven
    "warm":      dict(rate="-3%",  pitch="+2%",  volume="+0%"),    # samimi, sıcak
    "confident": dict(rate="+0%",  pitch="-3%",  volume="+6%"),    # kararlı, net
    "playful":   dict(rate="+5%",  pitch="+6%",  volume="+4%"),    # hafif mizah
    "excited":   dict(rate="+10%", pitch="+8%",  volume="+10%"),   # heyecan, iyi haber
    "neutral":   dict(rate="+0%",  pitch="+0%",  volume="+0%"),
}
# Ton → Azure express-as stili (destekleyen seslerde; desteklemeyen sesler görmezden gelir)
TONE_STYLES = {"urgent": "serious", "calm": "calm", "warm": "friendly", "confident": "newscast",
               "playful": "cheerful", "excited": "excited", "neutral": ""}


def _voice_markup(text: str) -> str:
    """Metin içi işaretleri SSML'e çevirir:
       '...' veya ' | ' → kısa duraklama,  '//' → uzun duraklama,  *kelime* → vurgu."""
    import re
    t = _xml(text)
    t = re.sub(r"\s*//\s*", "<break time='700ms'/>", t)
    t = re.sub(r"\s*(\.\.\.|…|\|)\s*", "<break time='350ms'/>", t)
    t = re.sub(r"\*(.+?)\*", r"<prosody rate='-12%' pitch='+6%'>\1</prosody>", t)
    # cümle sonlarında doğal nefes payı
    t = re.sub(r"([.!?])\s+", r"\1<break time='180ms'/>", t)
    return t


def azure_ssml(text: str, voice: str, tone: str, s: dict) -> str:
    base_rate = s.get("cloud_rate", "+0%")
    hd = "DragonHD" in voice
    body = _voice_markup(text) if not hd else _xml(text)   # HD sesler prosody/break desteklemez, kendi tonlamasını yapar
    if not hd:
        p = TONES.get(tone or "neutral", TONES["neutral"])
        rate = p["rate"] if base_rate in ("", "+0%") else base_rate
        body = f"<prosody rate='{rate}' pitch='{p['pitch']}' volume='{p['volume']}'>{body}</prosody>"
        style = s.get("azure_style") or TONE_STYLES.get(tone or "neutral", "")
        if style and s.get("azure_use_styles", True):
            body = f"<mstts:express-as style='{style}' styledegree='1.3'>{body}</mstts:express-as>"
    params = f" parameters='temperature={s.get('azure_temperature', 0.7)}'" if hd else ""
    lang = "" if voice.startswith("tr-") else "<lang xml:lang='tr-TR'>"
    lang_end = "" if voice.startswith("tr-") else "</lang>"
    return ("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            "xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='tr-TR'>"
            f"<voice name='{voice}'{params}>{lang}{body}{lang_end}</voice></speak>")


def azure(text, out, s, voice=None, tone=None):
    key, region = _need("AZURE_SPEECH_KEY"), _need("AZURE_SPEECH_REGION")
    voice = voice or s.get("azure_voice", "tr-TR-EmelNeural")
    tone = tone or s.get("_tone") or "neutral"
    ssml = azure_ssml(text, voice, tone, s)
    r = requests.post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                      headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
                               "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm", "User-Agent": "arkesoft-igbot"},
                      data=ssml.encode("utf-8"), timeout=120)
    if r.status_code == 400 and "express-as" in ssml:
        # Ses stil desteklemiyor olabilir → stilsiz tekrar dene
        s2 = dict(s); s2["azure_use_styles"] = False
        return azure(text, out, s2, voice=voice, tone=tone)
    if r.status_code != 200:
        die(f"Azure Speech hatası {r.status_code}: {r.text[:400]}")
    tmp = out.with_name(out.stem + "_az.wav"); tmp.write_bytes(r.content)
    return _to_wav(tmp, out)


# ---------------- Google Cloud TTS ----------------
def google(text, out, s):
    key = _need("GOOGLE_TTS_API_KEY")
    voice = s.get("google_voice", "tr-TR-Chirp3-HD-Aoede")
    r = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": key},
                      json={"input": {"text": text.replace("//", ". ").replace("|", ",").replace("*", "")},
                            "voice": {"languageCode": "tr-TR", "name": voice},
                            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000,
                                            "speakingRate": float(s.get("google_rate", 1.0))}},
                      timeout=120)
    if r.status_code != 200:
        die(f"Google TTS hatası {r.status_code}: {r.text[:400]}")
    tmp = out.with_name(out.stem + "_gg.wav"); tmp.write_bytes(base64.b64decode(r.json()["audioContent"]))
    return _to_wav(tmp, out)


# ---------------- Edge (resmi olmayan, anahtarsız) ----------------
def edge(text, out, s):
    tmp = out.with_suffix(".mp3")
    p = TONES.get(s.get("_tone") or "neutral", TONES["neutral"])
    clean = text.replace("//", ". ").replace("|", ",").replace("*", "")
    _run([sys.executable, "-m", "edge_tts", "--voice", s.get("edge_voice", "tr-TR-EmelNeural"),
          "--rate", p["rate"], "--pitch", p["pitch"].replace("%", "Hz").replace("+0Hz", "+0Hz"), "--text", clean, "--write-media", str(tmp)])
    if not tmp.exists() or tmp.stat().st_size == 0:
        die("edge-tts ses üretemedi (servis değişmiş olabilir). Başka motor seçin: settings.json → tts_engine")
    return _to_wav(tmp, out)


# ---------------- Piper (yerel) ----------------
def piper_model(s):
    name = s.get("piper_voice", "tr_TR-fahrettin-medium")
    m = ASSETS / "voices" / name / f"{name}.onnx"
    return m if m.exists() else None


def piper(text, out, s):
    m = piper_model(s)
    if not m:
        die("Piper sesi kurulu değil: python3 scripts/get_voice.py")
    tmp = out.with_name(out.stem + "_pp.wav")
    _run([sys.executable, "-m", "piper", "-m", str(m), "-f", str(tmp),
          "--length-scale", str(s.get("piper_length_scale", 1.05)), "--sentence-silence", "0.25"],
         input=text.replace("//", ". ").replace("|", ",").replace("*", ""))
    return _to_wav(tmp, out)


# ---------------- macOS say ----------------
def say(text, out, s):
    if platform.system() != "Darwin" or not shutil.which("say"):
        die("'say' sadece macOS'ta var.")
    aiff = out.with_suffix(".aiff")
    _run(["say", "-v", s.get("voice", "Yelda"), "-r", str(s.get("voice_rate", 178)), "-o", str(aiff),
          text.replace("//", ". ").replace("|", ",").replace("*", "")])
    return _to_wav(aiff, out)


ENGINES = {"elevenlabs": elevenlabs, "azure": azure, "google": google, "edge": edge, "piper": piper, "say": say}


def candidates(s) -> list[str]:
    """Denenecek motorlar, sırayla."""
    e = s.get("tts_engine", "auto")
    if e != "auto":
        return [e]
    c = []
    if os.environ.get("ELEVEN_API_KEY"): c.append("elevenlabs")
    if os.environ.get("AZURE_SPEECH_KEY"): c.append("azure")
    if os.environ.get("GOOGLE_TTS_API_KEY"): c.append("google")
    try:
        import edge_tts  # noqa: F401
        c.append("edge")
    except ImportError:
        pass
    if piper_model(s): c.append("piper")
    if platform.system() == "Darwin" and shutil.which("say"): c.append("say")
    return c


_chosen = None


def pick_engine(s) -> str | None:
    c = candidates(s)
    return _chosen or (c[0] if c else None)


def synth(text: str, out: Path, s: dict, tone: str | None = None) -> Path | None:
    global _chosen
    if tone:
        s = dict(s); s["_tone"] = tone
    if not s.get("voice_enabled", True) or not (text or "").strip():
        return None
    order = [_chosen] if _chosen else candidates(s)
    if not order:
        return None
    for engine in order:
        if engine not in ENGINES:
            die(f"Bilinmeyen tts_engine: {engine}. Seçenekler: {', '.join(ENGINES)}")
        if engine in ("elevenlabs", "azure", "google") and requests is None:
            die("pip install requests")
        try:
            path = ENGINES[engine](text, out, s)
            _chosen = engine   # ilk başarılı motor, o günkü tüm sahnelerde kullanılır
            return path
        except (SystemExit, Exception) as e:  # ağ hatası dahil her şeyde sıradakine geç
            if len(order) == 1:
                raise
            log(f"{engine} başarısız, sıradaki motor deneniyor...")
    die("Hiçbir seslendirme motoru çalışmadı. README → Seslendirme motoru.")


def _xml(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
