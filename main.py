#!/usr/bin/env python3
"""apple_music_yt_dl_cli.py

Download every track listed in an Apple Music/iTunes library XML export
using yt‑dlp, saving high‑quality **audio‑only** MP3s, embedding album art &
metadata, and validating that the chosen YouTube video is plausibly the
same song (duration check).

Validation strategy
-------------------
Apple Music library XMLs include the key ``Total Time`` (track length in
milliseconds).  For each song we:
1. Generate a YouTube search query.
2. Ask yt‑dlp to return JSON for the top 10 search results (``ytsearch10:``)
   **without downloading**.
3. Pick the first result whose ``duration`` is within an adaptive
tolerance of the track length (±max(5 s, 5 % of track length)).
4. If none match, fall back to the first result (but we still mark the
   track as *suspect* in the summary so the user can review).

Dependencies (macOS):
  brew install ffmpeg
  python3 -m pip install --upgrade yt-dlp

Usage:
  python apple_music_yt_dl_cli.py \
         --library  "/path/to/Music Library.xml" \
         --output   "/path/to/MP3s" \
         --workers 6
"""
from __future__ import annotations

import argparse
import json
import plistlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

# -------------------------- Helpers ----------------------------------------

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

# ------------- YouTube search / duration validation ------------------------

def pick_video(track: Dict, max_results: int = 10) -> Tuple[str, bool]:
    """Return (video_url, is_valid) where *is_valid* is True if duration is
    within tolerance, else False (fallback)."""
    query = build_search_query(track)
    search_cmd = [
        "yt-dlp",
        "--dump-json",
        "--skip-download",
        f"ytsearch{max_results}:{query}",
    ]
    try:
        proc = subprocess.run(search_cmd, capture_output=True, text=True, check=True)
        lines = proc.stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        return (f"ytsearch1:{query}", False)  # give up, still attempt

    # Target duration (seconds) ─ Apple stores ms.
    target_ms = track.get("Total Time") or 0
    if not target_ms:
        return (f"ytsearch1:{query}", False)
    target_s = target_ms / 1000.0
    tol = max(5, target_s * 0.05)  # 5 seconds or 5 %

    for ln in lines:
        try:
            meta = json.loads(ln)
            dur = meta.get("duration")
            if dur is None:
                continue
            if abs(dur - target_s) <= tol:
                return (meta.get("webpage_url") or f"https://www.youtube.com/watch?v={meta.get('id')}", True)
        except json.JSONDecodeError:
            continue
    # Nothing matched
    if lines:
        try:
            meta0 = json.loads(lines[0])
            return (meta0.get("webpage_url") or f"https://www.youtube.com/watch?v={meta0.get('id')}", False)
        except Exception:
            pass
    return (f"ytsearch1:{query}", False)

# ------------------------ Downloader ---------------------------------------

def download_track(track: Dict, out_dir: Path, dry_run: bool = False) -> Tuple[bool, bool]:
    """Return (success, validated)."""
    title = track.get("Name", "Unknown Title")
    artist = track.get("Artist", "Unknown Artist")
    filename = sanitize_filename(f"{artist} - {title}.mp3")
    out_path = out_dir / filename

    if out_path.exists():
        print(f"[SKIP] {filename} (already exists)")
        return (True, True)

    url, is_valid = pick_video(track)

    ytdlp_cmd = [
        "yt-dlp",
        "--no-playlist",
        "--format", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "--embed-metadata",
        "--add-metadata",
        "--metadata-from-title", "%\(artist\)s - %\(title\)s",
        "--output", str(out_path.with_suffix(".%(ext)s")),
        url,
    ]

    if dry_run:
        print("[DRY]", " ".join(ytdlp_cmd))
        return (True, is_valid)

    try:
        print(f"[DL] {artist} – {title} {'(validated)' if is_valid else '(fallback)'}")
        subprocess.run(ytdlp_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return (True, is_valid)
    except subprocess.CalledProcessError:
        print(f"[FAIL] {artist} – {title}")
        return (False, False)

# ------------------------------ CLI ----------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Download MP3s from an Apple Music library with YouTube validation.")
    p.add_argument("--library", "-l", type=Path, required=True, help="Path to Library.xml export")
    p.add_argument("--output", "-o", type=Path, required=True, help="Destination folder for MP3s")
    p.add_argument("--workers", "-w", type=int, default=4, help="Parallel downloads (default 4)")
    p.add_argument("--dry-run", action="store_true", help="Show what would happen but don't download")
    args = p.parse_args()

    if not args.library.exists():
        sys.exit("Library file not found: " + str(args.library))
    args.output.mkdir(parents=True, exist_ok=True)

    tracks = read_library(args.library)
    print(f"Found {len(tracks)} tracks\n")

    failed: List[Dict] = []
    suspect: List[Dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fut_to_track = {pool.submit(download_track, t, args.output, args.dry_run): t for t in tracks}
        for fut in as_completed(fut_to_track):
            ok, valid = fut.result()
            tr = fut_to_track[fut]
            if not ok:
                failed.append(tr)
            elif not valid:
                suspect.append(tr)

    print("\n-------------------------------------------")
    successes = len(tracks) - len(failed)
    print(f"Completed downloads: {successes}/{len(tracks)}")

    if suspect:
        print(f"\nPotential mismatches ({len(suspect)}): review manually:")
        for tr in suspect[:20]:
            print(f"  - {tr.get('Artist', 'Unknown Artist')} – {tr.get('Name', 'Unknown Title')}")
        if len(suspect) > 20:
            print("  …")

    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for tr in failed[:20]:
            print(f"  - {tr.get('Artist', 'Unknown Artist')} – {tr.get('Name', 'Unknown Title')}")
        if len(failed) > 20:
            print("  …")

    print("Done.")

if __name__ == "__main__":
    main()
