# TorrentLeech Freeleech Tracker

A terminal-based tool that polls TorrentLeech for new freeleech torrents and optionally auto-downloads the `.torrent` files.

## Features

- Live countdown display that updates in place — no terminal spam
- Rich-formatted table showing category, size, seeders/leechers, and tags for each new release
- Desktop notifications on macOS, Linux, and Windows
- Email notifications for new freeleech releases
- Auto-downloads `.torrent` files to a local folder
- Skips downloads if there is not enough disk space
- Optional min/max file size filter for downloads
- Persists seen torrents across restarts so you never get spammed with old entries

## Requirements

Install dependencies via:

```bash
pip install -r requirements.txt
```

Core packages: `requests`, `python-dotenv`, `rich`. On Windows, also install `win10toast` for desktop notifications.

## Setup

**1. Clone the repo and create a virtual environment**

```bash
git clone https://github.com/heybuddy1708/tl-freeleech-tracker.git
cd freeleech_tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Get your TorrentLeech session cookie**

- Log into TorrentLeech in your browser
- Open DevTools -> Network tab -> click any request to torrentleech.org
- Under Request Headers, copy the full value of the `Cookie` header

**3. Get your RSS key (required for auto-download)**

- Log into TorrentLeech -> My Account -> RSS (may have to enable it in settings)
- Copy the key from your profile

**4. Set up email notifications (optional)**

- Enable 2-Step Verification on your Google account at https://myaccount.google.com/signinoptions/two-step-verification
- Generate an app password at https://myaccount.google.com/apppasswords
- Copy the 16-character password (no spaces)

**5. Create a `.env` file**

Copy `.env.example` and fill in your values:

```bash
cp .env.example .env
```

```
COOKIE=tluid=xxx; tlpass=xxx; lastbrowse=xxx; ...
RSS_KEY=your_rss_key_here
EMAIL_FROM=your_gmail_here@gmail.com
EMAIL_TO=your_receiving_email_here@gmail.com
EMAIL_PASSWORD=abcdabcdabcdabcd
```

**6. Run**

```bash
python3 tracker.py
```

## Configuration

All options are at the top of the script:

| Variable | Default | Description |
|---|---|---|
| `POLL_INTERVAL` | `60` | Seconds between checks |
| `AUTO_DOWNLOAD` | `True` | Download `.torrent` files automatically |
| `DOWNLOAD_DIR` | `downloads` | Folder to save `.torrent` files |
| `MIN_SIZE` | `None` | Minimum file size in bytes, e.g. `1 * 1024**3` for 1 GB |
| `MAX_SIZE` | `None` | Maximum file size in bytes, e.g. `50 * 1024**3` for 50 GB |
| `MINIMUM_FREE_SPACE` | `10 * 1024**3` | Minimum disk space to keep free (default 10 GB) |
| `EMAIL_NOTIFICATIONS` | `False` | Send an email when a new freeleech is found |

## qBittorrent integration

Point qBittorrent's watched folder at the `downloads/` directory and it will automatically pick up and start any `.torrent` files that get saved there.