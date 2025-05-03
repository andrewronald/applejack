# 🍏 Apple‑Music → YouTube MP3 CLI

**apple_music_yt_dl_cli.py** converts an exported **Apple Music / iTunes** `Library.xml` into a folder of high‑quality, fully‑tagged MP3 files by fetching audio from YouTube via **yt‑dlp**.

---

## ✨ Features

| Capability | Details |
|------------|---------|
| 🎯 **Duration validation** | Chooses the first YouTube result whose runtime is within ±5 seconds **or** ±5 % of the track length in `Library.xml`.  Falls back gracefully if nothing matches and flags the download as *suspect*. |
| ⚡ **Parallel downloads** | `--workers` flag lets you pick how many tracks to grab at once (default 4). |
| 🔄 **Auto‑resume** | Already‑downloaded MP3s are skipped, so re‑running retries only failures. |
| 📊 **Pinned progress bar** | Live `tqdm` bar stays at the bottom of the terminal—no scrolling—while log messages appear above it. |
| 🪵 **Dual logging** | Prints friendly status lines to the console **and** writes a detailed, timestamped logfile (`apple_music_dl.log` in the output folder by default). |
| 🖼️ **Embedded metadata** | mp3 + thumbnail cover, ID3 title/artist/album. |
| 🏃 **Dry‑run mode** | `--dry-run` prints the yt‑dlp commands without downloading anything. |

---

## 🛠️ Requirements

* **Python 3.9+**  
* **yt‑dlp** – `pip install --upgrade yt-dlp`  
* **ffmpeg** – `brew install ffmpeg` (or your OS’s package manager)  
* **tqdm** *(optional but recommended for the progress bar)* – `pip install tqdm`

> The script will still run without `tqdm`; you’ll just see a simple numeric counter instead of the fancy bar.

---

## 🚀 Installation

```bash
# Clone the repo or copy the script somewhere in your PATH
chmod +x apple_music_yt_dl_cli.py

# Install Python dependencies (add --user if you prefer local installs)
pip install --upgrade yt-dlp tqdm

# macOS example – install ffmpeg via Homebrew
brew install ffmpeg
```

---

## 📦 Usage

1. **Export** your Apple Music library:  
   *Music app → File → Library → Export Library… → `Music Library.xml`*
2. Run the script:

```bash
python apple_music_yt_dl_cli.py \
  --library "/Users/andrew/Music/Music Library.xml" \
  --output  "/Users/andrew/Downloads/MP3s" \
  --workers 6
```

You’ll see something like:

```
Downloading  42%|███████▏        | 123/293 [02:18<03:11]  ok=120  fail=3
```

When finished, check `apple_music_dl.log` inside the output folder for a full report of successes, mismatches, and any errors.

---

## 🔧 Options

| Flag | Default | Description |
|------|---------|-------------|
| `--library, -l` | *(required)* | Path to your exported `Library.xml`. |
| `--output, -o` | *(required)* | Folder where MP3s will be saved. Will be created if it doesn’t exist. |
| `--workers, -w` | `4` | Parallel download threads. Increase on fast connections; lower if you hit YouTube rate‑limits. |
| `--log-file` | `<output>/apple_music_dl.log` | Custom logfile path. |
| `--dry-run` | *(off)* | Print yt‑dlp commands but don’t download anything. |

---

## 🤔 FAQ

### Can I rerun the script to finish failed downloads?

Yes! The script skips any MP3 file that already exists, so re‑executing with the same `--library` and `--output` paths will automatically attempt only the tracks that failed previously.

### How accurate is the duration filter?

A tolerance of ±5 seconds **or** ±5 % of track length (whichever is greater) is used. You can tweak this in `pick_video()` if you need a stricter match.

### What if a song has no matching duration result?

The script downloads the first search result anyway, flags it as *suspect*, and lists it at the end (and in the logfile) so you can review or replace it manually.

---

## 📝 License

MIT. Do what you like, but downloading copyrighted material may violate YouTube’s TOS or local laws use responsibly.
