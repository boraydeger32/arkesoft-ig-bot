#!/usr/bin/env python3
"""
3. ADIM — Motion reel üretir (tamamen ücretsiz: Playwright + ffmpeg + macOS seslendirme).

templates/motion.html içindeki animasyonlu sahneleri (kinetik metin, dağınık arayüz pencereleri,
sayaç, ışıklı "tek merkez", dashboard, haber kartı, madde listesi, kapanış) content.json'daki
metinlerle doldurur, kare kare kaydeder, seslendirme + müzik ekler.

Çıktı: out/YYYY-MM-DD/reel.mp4 (1080x1920, 30 fps, H.264 + AAC) ve cover.jpg
Kullanım: python3 scripts/make_video.py [YYYY-MM-DD] [--fps 30] [--preview]  (--preview: 12 fps, hızlı kontrol)
"""
import json
import platform
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

import tts_engines
from common import ASSETS, TEMPLATES, day_dir, die, load_settings, log, read_json, today, write_json

MIN_DUR = {"title": 2.6, "chaos": 5.0, "counter": 5.5, "orb": 4.5, "dashboard": 5.5,
           "headline": 4.0, "list": 5.0, "outro": 3.5}
VOICE_GAP = 0.9     # seslendirme bittikten sonra sahnenin kalma payı (sn)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        die("Komut başarısız:\n" + " ".join(map(str, cmd)) + "\n" + p.stderr[-3000:])
    return p


def duration_of(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def tts(text: str, path: Path, settings: dict) -> Path | None:
    """Seslendirme; motor seçimi scripts/tts_engines.py içinde (ElevenLabs / Azure / Google / Edge / Piper / say)."""
    return tts_engines.synth(text, path, settings)


def pick_music(d: date) -> Path | None:
    tracks = sorted(p for p in (ASSETS / "music").glob("*") if p.suffix.lower() in {".mp3", ".m4a", ".wav", ".aac"})
    if not tracks:
        return None
    return tracks[sum(map(ord, d.isoformat())) % len(tracks)]


def build_timeline(reel: dict, work: Path, settings: dict):
    scenes, voices, t = [], [], 0.0
    for i, sc in enumerate(reel["scenes"]):
        kind = sc.get("type") if sc.get("type") in MIN_DUR else "title"
        v = tts(sc.get("voice", ""), work / f"voice_{i:02d}.wav", settings)
        dur = MIN_DUR[kind]
        if v:
            dur = max(dur, duration_of(v) + VOICE_GAP)
        else:
            dur += 1.0  # sessiz üretimde okumaya zaman bırak
        spec = {k: val for k, val in sc.items() if k != "voice"}
        spec.update(type=kind, start=round(t, 3), dur=round(dur, 3))
        scenes.append(spec)
        voices.append((v, dur))
        t += dur
    return scenes, voices, t


def render_frames(scenes, total: float, fps: int, frames_dir: Path):
    html = (TEMPLATES / "motion.html").read_text(encoding="utf-8").replace("{{FONT_URL}}", (ASSETS / "fonts" / "InterVariable.ttf").resolve().as_uri())
    html = html.replace("<script>", "<script>window.__SPEC=" + json.dumps({"scenes": scenes}, ensure_ascii=False) + ";</script><script>", 1)
    n = int(total * fps)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        tmp = frames_dir.parent / "motion.html"
        tmp.write_text(html, encoding="utf-8")
        page.goto(tmp.resolve().as_uri(), wait_until="load")
        page.wait_for_function("window.ready === true")
        page.evaluate("document.fonts.ready")
        for f in range(n):
            page.evaluate("t => window.seek(t)", f / fps)
            page.screenshot(path=str(frames_dir / f"f_{f:05d}.jpg"), type="jpeg", quality=92)
            if f % (fps * 5) == 0:
                log(f"  kare {f}/{n} ({f / fps:.0f}s)")
        browser.close()
    return n


def build_voice_track(voices, work: Path) -> Path | None:
    if not any(v for v, _ in voices):
        return None
    parts, lst = [], work / "voices.txt"
    for i, (v, dur) in enumerate(voices):
        seg = work / f"vseg_{i:02d}.wav"
        if v:
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(v), "-af", f"apad=whole_dur={dur:.3f}", "-t", f"{dur:.3f}", str(seg)])
        else:
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}", str(seg)])
        parts.append(seg)
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    out = work / "voice.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


def main():
    args = sys.argv[1:]
    preview = "--preview" in args
    fps = 12 if preview else int(args[args.index("--fps") + 1]) if "--fps" in args else 30
    dates = [a for a in args if a[:1].isdigit() and "-" in a and len(a) == 10]
    settings = load_settings()
    d = date.fromisoformat(dates[0]) if dates else today(settings)
    out_dir = day_dir(d)
    content = read_json(out_dir / "content.json")
    if not content:
        die("content.json yok. Önce generate.py çalıştırın.")
    reel = content["reel"]
    if not reel.get("enabled"):
        log("Bugün reel yok, video atlandı.")
        return
    if not reel.get("scenes"):
        die("Reel sahnesi yok.")

    work = out_dir / "_work"
    frames = work / "frames"
    shutil.rmtree(work, ignore_errors=True)
    frames.mkdir(parents=True)

    log("1/3 Seslendirme ve zaman çizelgesi...")
    scenes, voices, total = build_timeline(reel, work, settings)
    for s in scenes:
        log(f"  {s['type']:<9} {s['dur']:5.1f}s  {str(s.get('title') or (s.get('lines') or [''])[0])[:50]}")
    log(f"  toplam {total:.1f} sn")
    if total > 89:
        die(f"Video {total:.0f} sn — Instagram Reels sınırı 90 sn. Sahne/voice metinlerini kısaltın.")

    log(f"2/3 Kareler kaydediliyor ({fps} fps)...")
    render_frames(scenes, total, fps, frames)

    log("3/3 Ses ve video birleştiriliyor...")
    voice = build_voice_track(voices, work)
    music = pick_music(d)
    final = out_dir / ("reel_preview.mp4" if preview else "reel.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "f_%05d.jpg")]
    fc, amap = [], None
    if voice and music:
        vol = settings.get("music_volume", 0.18)
        cmd += ["-i", str(voice), "-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[2:a]volume={vol},afade=t=in:d=1.2,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[m]")
        fc.append("[m][1:a]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[md]")   # konuşurken müzik kısılır
        fc.append("[md][1:a]amix=inputs=2:duration=first:normalize=0[a]")
        amap = "[a]"
    elif voice:
        cmd += ["-i", str(voice)]
        amap = "1:a"
    elif music:
        vol = settings.get("music_volume", 0.18) * 2
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        fc.append(f"[1:a]volume={vol},afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[a]")
        amap = "[a]"
    else:  # sessiz de olsa bir ses kanalı olsun (Instagram bazen sessiz videoyu reddeder)
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = "1:a"
    if fc:
        cmd += ["-filter_complex", ";".join(fc)]
    cmd += ["-map", "0:v"] + (["-map", amap] if amap else [])
    cmd += ["-t", f"{total:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(final)]
    run(cmd)

    cover_frame = frames / f"f_{min(int(1.6 * fps), int(total * fps) - 1):05d}.jpg"
    shutil.copy(cover_frame, out_dir / "cover.jpg")
    shutil.rmtree(work, ignore_errors=True)

    if not preview:
        reel["video_file"] = "reel.mp4"
        reel["cover_file"] = "cover.jpg"
        reel["duration"] = round(duration_of(final), 1)
        reel["timeline"] = [{"type": s["type"], "start": s["start"], "dur": s["dur"]} for s in scenes]
        write_json(out_dir / "content.json", content)
    if not music:
        log("assets/music/ boş → müziksiz. Telifsiz bir mp3 koyarsanız otomatik eklenir (konuşurken kısılır).")
    if not voice:
        log("Seslendirme yok. README → Seslendirme bölümünden bir motor seçin.")
    else:
        log("seslendirme motoru:", tts_engines.pick_engine(settings))
    log(f"Video hazır → {final} ({total:.1f} sn)")


if __name__ == "__main__":
    main()
