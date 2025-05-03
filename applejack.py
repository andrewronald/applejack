#!/usr/bin/env python3
"""
apple_music_yt_dl_cli.py

Convert an Apple Music / iTunes `Library.xml` into a folder of high‑quality
audio‑only MP3s via YouTube (yt‑dlp).

Highlights
----------
• Duration‑validated search with configurable tolerance (`--tolerance`, default 5 s).
• Pinned tqdm progress bar (no scrolling).
• Log file lives next to the script (`apple_music_dl.log`), console is quiet by
  default but you can show SKIP spam with `--verbose-skips`.
"""

from __future__ import annotations

import argparse
import json
import logging
import plistlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# ── tqdm setup ───────────────────────────────────────────────────────────────
try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # stub fallback if tqdm missing
    def tqdm(iterable=None, **kwargs):
        return iterable if iterable is not None else range(0)
    tqdm.write = print  # type: ignore  # noqa: A001

# ── logging handler that keeps bar pinned ───────────────────────────────────
class TqdmStreamHandler(logging.StreamHandler):
    """Route log records through tqdm.write so the bar stays pinned."""
    def emit(self, record):  # type: ignore[override]
        try:
            tqdm.write(self.format(record))
            self.flush()
        except Exception:  # pragma: no cover
            self.handleError(record)

# ── helper funcs ────────────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    invalid = r"/\\?%*:|\"<>"
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()[:200]


def build_search_query(track: Dict) -> str:
    title = track.get("Name", "")
    artist = track.get("Artist", "")
    album = track.get("Album", "")
    parts = [artist, "-", title]
    if album:
        parts.extend(["album", album])
    return " ".join(filter(None, parts)).strip()


def read_library(xml_path: Path) -> List[Dict]:
    with xml_path.open("rb") as fp:
        plist = plistlib.load(fp)
    return list(plist["Tracks"].values())

# ── youtube search / duration validation ───────────────────────────────────
def pick_video(track: Dict, base_tol: float, max_results: int = 10) -> Tuple[str, bool]:
    query = build_search_query(track)
    cmd = ["yt-dlp", "--dump-json", "--skip-download", f"ytsearch{max_results}:{query}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = proc.stdout.strip().splitlines()
    except subprocess.CalledProcessError as e:
        logging.error("yt-dlp search failed for %s: %s", query, e)
        return (f"ytsearch1:{query}", False)

    target_ms = track.get("Total Time") or 0
    if not target_ms:
        return (f"ytsearch1:{query}", False)
    target_s = target_ms / 1000.0
    tol = max(base_tol, target_s * 0.05)

    for ln in lines:
        try:
            meta = json.loads(ln)
            dur = meta.get("duration")
            if dur is None:
                continue
            if abs(dur - target_s) <= tol:
                url = meta.get("webpage_url") or f"https://youtu.be/{meta['id']}"
                return (url, True)
        except json.JSONDecodeError:
            continue

    if lines:
        try:
            meta0 = json.loads(lines[0])
            url = meta0.get("webpage_url") or f"https://youtu.be/{meta0['id']}"
            return (url, False)
        except Exception:
            pass
    return (f"ytsearch1:{query}", False)

# ── downloader ───────────────────────────────────────────────────────────────
def download_track(track: Dict, out_dir: Path, base_tol: float, dry: bool = False) -> Tuple[bool, bool]:
    title  = track.get("Name",   "Unknown Title")
    artist = track.get("Artist", "Unknown Artist")
    fname  = sanitize_filename(f"{artist} - {title}.mp3")
    dest   = out_dir / fname

    if dest.exists():
        logging.debug("SKIP existing %s", fname)
        return (True, True)

    url, valid = pick_video(track, base_tol)

    ytdlp_cmd = [
        "yt-dlp", "--no-playlist",
        "--format", "bestaudio/best",
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-thumbnail", "--embed-metadata", "--add-metadata",
        "--metadata-from-title", "%(artist)s - %(title)s",
        "--output", str(dest.with_suffix(".%(ext)s")),
        url,
    ]

    if dry:
        logging.info("DRY‑RUN   %s – %s", artist, title)
        return (True, valid)

    try:
        subprocess.run(ytdlp_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        logging.info("DL ok     %s – %s", artist, title)
        return (True, valid)
    except subprocess.CalledProcessError as e:
        logging.error("DL fail   %s – %s: %s", artist, title, e)
        return (False, False)

# ── logging setup ───────────────────────────────────────────────────────────
def setup_logging(log_file: Path, verbose_skips: bool) -> None:
    file_fmt    = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    console_fmt = logging.Formatter("%(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(file_fmt)
    fh.setLevel(logging.DEBUG)  # everything to file

    ch = TqdmStreamHandler()
    ch.setFormatter(console_fmt)
    ch.setLevel(logging.DEBUG if verbose_skips else logging.INFO)

    logging.basicConfig(level=logging.DEBUG, handlers=[fh, ch])
    logging.info("===== Run started %s =====", datetime.now().isoformat(timespec="seconds"))

# ── CLI ─────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(description="Download MP3s from an Apple Music Library.xml via YouTube.")
    p.add_argument("--library", "-l", type=Path, required=True, help="Path to Library.xml export")
    p.add_argument("--output",  "-o", type=Path, required=True, help="Destination folder for MP3s")
    p.add_argument("--workers", "-w", type=int, default=4, help="Parallel downloads (default 4)")
    p.add_argument("--tolerance", type=float, default=5.0, help="Absolute runtime tolerance seconds (default 5)")
    p.add_argument("--log-file", type=Path, help="Custom logfile path (default: script directory)")
    p.add_argument("--verbose-skips", action="store_true", help="Show SKIP messages in console")
    p.add_argument("--dry-run", action="store_true", help="Preview actions without downloading")
    args = p.parse_args()

    if not args.library.exists():
        sys.exit("Library file not found: " + str(args.library))

    args.output.mkdir(parents=True, exist_ok=True)

    default_log = Path(__file__).resolve().with_name("apple_music_dl.log")
    log_path = args.log_file or default_log
    setup_logging(log_path, args.verbose_skips)

    tracks = read_library(args.library)
    total  = len(tracks)
    logging.info("Discovered %d tracks", total)

    failed:  List[Dict] = []
    suspect: List[Dict] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fut_to_track = {pool.submit(download_track, t, args.output,
                                    args.tolerance, args.dry_run): t for t in tracks}

        with tqdm(total=total, unit="song", desc="Downloading", ncols=80) as bar:
            for fut in as_completed(fut_to_track):
                ok, valid = fut.result()
                tr = fut_to_track[fut]
                if not ok:
                    failed.append(tr)
                elif not valid:
                    suspect.append(tr)
                bar.update(1)
                bar.set_postfix({"ok": total - len(failed) - len(suspect),
                                 "fail": len(failed)})

    successes = total - len(failed)
    logging.info("Completed downloads: %d/%d", successes, total)

    if suspect:
        logging.warning("Potential mismatches (%d) – review manually:", len(suspect))
        for tr in suspect[:20]:
            logging.warning("SUSPECT  %s – %s", tr.get("Artist", "Unknown Artist"), tr.get("Name", "Unknown Title"))
        if len(suspect) > 20:
            logging.warning("… (%d more)", len(suspect) - 20)

    if failed:
        logging.error("Failed downloads (%d):", len(failed))
        for tr in failed[:20]:
            logging.error("FAILED   %s – %s", tr.get("Artist", "Unknown Artist"), tr.get("Name", "Unknown Title"))
        if len(failed) > 20:
            logging.error("… (%d more)", len(failed) - 20)

    logging.info("===== Run finished =====")


if __name__ == "__main__":
    main()
