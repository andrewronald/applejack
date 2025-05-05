# 🍏 Apple‑Music → YouTube MP3 CLI

**applejack.py** converts an exported **Apple Music / iTunes** `Library.xml` into a folder of high‑quality, fully‑tagged MP3 files by fetching audio from YouTube via **yt‑dlp**. As far as I know there is no way to export your library on Windows so this will only work on macOS.

---

## ✨ Features

| Capability | Details |
|------------|---------|
| 🎯 **Duration validation** | Picks the first YouTube result whose runtime is within an adjustable tolerance (default ±5 s **or** ±5 % of track length). |
| 🎚️ **Configurable tolerance** | `--tolerance <seconds>` to tighten or relax the window. |
| ⚡ **Parallel downloads** | `--workers` downloads several tracks at once (default 4). |
| 🔄 **Auto‑resume** | Already‑downloaded MP3s are skipped, so re‑running retries only failures. |
| 📊 **Pinned progress bar** | Live `tqdm` bar sits at the bottom of the terminal—no scrolling—while log lines appear above it. |
| 🪵 **Unified logging** | Console status + logfile **next to the script** (`apple_music_dl.log` by default). |
| 🖼️ **Embedded metadata** | MP3 with thumbnail cover + ID3 tags. |
| 🏃 **Dry‑run mode** | `--dry-run` prints yt‑dlp commands without downloading. |

---

## 🛠️ Requirements

* **Python 3.9+**  
* **yt‑dlp** – `pip install yt-dlp`  
* **ffmpeg** – `brew install ffmpeg` (or equivalent)  
* **tqdm** *(optional but recommended)* – `pip install tqdm`

---

## 🚀 Installation (recommended: project‑local virtual‑env)

```bash
# In your project folder
python3 -m venv .venv
source .venv/bin/activate
pip install yt-dlp tqdm
brew install ffmpeg
chmod +x applejack.py