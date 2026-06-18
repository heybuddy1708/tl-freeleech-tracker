#!/usr/bin/env python3

import os
import sys
import time
import json
import shutil
import subprocess
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.live import Live
from rich.text import Text
from rich import box

load_dotenv()

COOKIE = os.getenv("COOKIE", "")
RSS_KEY = os.getenv("RSS_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
POLL_INTERVAL = 60
SEEN_FILE = ".tl_seen_torrents"
DOWNLOAD_DIR = "downloads"
API_URL = "https://www.torrentleech.org/torrents/browse/list/facets/tags%3AFREELEECH"

MIN_SIZE = None
MAX_SIZE = None
MIN_FREE_SPACE = 10 * 1024**3
AUTO_DOWNLOAD = False
EMAIL_NOTIFICATIONS = False

CATEGORY_MAP = {
    8: "Blu-ray", 9: "Blu-ray", 11: "Movies", 12: "Movies", 13: "Movies",
    14: "Movies HD", 15: "Movies", 16: "Movies", 17: "Games PC", 18: "Games",
    19: "Games", 20: "Games", 21: "Games", 22: "Games", 23: "Games",
    24: "Games", 25: "Games", 26: "Games", 27: "TV Series", 28: "TV Series",
    29: "TV Series", 30: "TV Series", 31: "TV Series", 32: "TV Series",
    33: "TV Series", 34: "TV Series", 36: "Foreign", 37: "Foreign",
    38: "Foreign", 39: "Anime", 40: "Anime", 42: "Anime", 43: "Anime",
    44: "Music", 45: "Music", 46: "Music", 47: "UHD", 48: "UHD", 49: "UHD",
}

console = Console()


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        console.print(f"[bold red]-  Email failed:[/bold red] {e}")


def has_enough_space(size_bytes):
    free = shutil.disk_usage(DOWNLOAD_DIR).free
    return free - size_bytes > MIN_FREE_SPACE


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        f.write("\n".join(seen))


def fetch_freeleech():
    headers = {
        "Cookie": COOKIE,
        "User-Agent": "Mozilla/5.0 (compatible; tl-freeleech-monitor/2.0)",
        "Accept": "application/json",
        "Referer": "https://www.torrentleech.org/",
    }
    try:
        r = requests.get(API_URL, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("torrentList", [])
    except requests.RequestException as e:
        console.print(f"[bold red]-  Fetch error:[/bold red] {e}")
        return []
    except json.JSONDecodeError as e:
        console.print(f"[bold red]-  JSON parse error:[/bold red] {e}")
        return []


def within_size_limits(size):
    if MIN_SIZE is not None and size < MIN_SIZE:
        return False
    if MAX_SIZE is not None and size > MAX_SIZE:
        return False
    return True


def download_torrent(t):
    if not RSS_KEY:
        console.print("[bold red]-  RSS_KEY not set — cannot download.[/bold red]")
        return False

    size = t.get("size", 0)
    if not has_enough_space(size):
        console.print(f"[bold red]-  Not enough disk space for {t['name']}[/bold red]")
        return False

    fid = t["fid"]
    filename = t["filename"]
    url = f"https://www.torrentleech.org/rss/download/{fid}/{RSS_KEY}/{filename}"

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    dest = os.path.join(DOWNLOAD_DIR, filename)

    if os.path.exists(dest):
        return True

    try:
        r = requests.get(url, headers={"Cookie": COOKIE}, timeout=15)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        return True
    except requests.RequestException as e:
        console.print(f"[bold red]-  Download failed for {filename}:[/bold red] {e}")
        return False


def fmt_size(size_bytes):
    try:
        b = int(size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
    except (ValueError, TypeError):
        return "?"


def fmt_tags(tags):
    filtered = [t for t in tags if t.upper() != "FREELEECH"
                and t.lower() != "rar"]
    return ", ".join(filtered[:4]) if filtered else "—"


def ts():
    return datetime.now().strftime("%H:%M:%S")


def notify(title, message):
    safe_message = message.replace('"', "'")
    safe_title = title.replace('"', "'")
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{safe_message}" with title "{safe_title}"'],
                check=False,
            )
        elif sys.platform == "win32":
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(safe_title, safe_message, duration=5)
        else:
            subprocess.run(["notify-send", safe_title, safe_message], check=False)
    except Exception:
        pass


def build_table(torrents):
    table = Table(
        box=box.ROUNDED,
        border_style="green",
        header_style="bold green",
        show_lines=True,
        expand=True,
    )
    table.add_column("Time", style="dim", no_wrap=True, width=10)
    table.add_column("Category", style="cyan", no_wrap=True, width=14)
    table.add_column("Size", style="yellow", no_wrap=True, width=10)
    table.add_column("S/L", style="green", no_wrap=True, width=8)
    table.add_column("Tags", style="magenta", width=24)
    table.add_column("DL", style="bold", no_wrap=True, width=4)
    table.add_column("Name", style="bold white", ratio=1)

    downloaded_torrents = []

    for t in torrents:
        cat = CATEGORY_MAP.get(t.get("categoryID", 0),
                               f"Cat {t.get('categoryID', '?')}")
        sl = f"{t.get('seeders', 0)}/{t.get('leechers', 0)}"
        size = t.get("size", 0)
        downloaded = False

        if AUTO_DOWNLOAD and within_size_limits(size):
            downloaded = download_torrent(t)
            if downloaded:
                downloaded_torrents.append(t)

        dl_icon = "[green]✓[/green]" if downloaded else "[dim]—[/dim]"

        table.add_row(
            ts(),
            cat,
            fmt_size(size),
            sl,
            fmt_tags(t.get("tags", [])),
            dl_icon,
            t.get("name", "Unknown"),
        )
    return table, downloaded_torrents


def countdown_panel(remaining, last_checked):
    mins, secs = divmod(remaining, 60)
    time_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
    return Panel(
        Text.from_markup(
            f"[dim]Last checked: [white]{last_checked}[/white]"
            f" — next check in [yellow]{time_str}[/yellow][/dim]"
        ),
        border_style="dim",
        padding=(0, 2),
    )


def print_header():
    console.print()
    console.print(Panel.fit(
        "[bold green] TorrentLeech Freeleech Monitor[/bold green]",
        subtitle=Text("Created by heybuddy1708", style="dim"),
        border_style="green",
        padding=(0, 2),
    ))
    console.print()


def main():
    if not COOKIE:
        console.print(Panel(
            "[bold red]No cookie configured.[/bold red]\n\n"
            "Add to your [cyan].env[/cyan] file:\n\n"
            "[bold yellow]COOKIE=tluid=xxx; tlpass=xxx; lastbrowse=xxx; ...[/bold yellow]\n\n"
            "Get it from DevTools -> any TorrentLeech request -> Request Headers -> Cookie",
            title="[red]Error[/red]",
            border_style="red",
        ))
        raise SystemExit(1)

    if AUTO_DOWNLOAD and not RSS_KEY:
        console.print(Panel(
            "[bold yellow]AUTO_DOWNLOAD is enabled but RSS_KEY is not set.[/bold yellow]\n\n"
            "Add to your [cyan].env[/cyan] file:\n\n"
            "[bold yellow]RSS_KEY=your_rss_key_here[/bold yellow]\n\n"
            "Get it from TorrentLeech -> My Account -> RSS",
            title="[yellow]Warning[/yellow]",
            border_style="yellow",
        ))

    if EMAIL_NOTIFICATIONS and not (EMAIL_FROM and EMAIL_TO and EMAIL_PASSWORD):
        console.print(Panel(
            "[bold yellow]EMAIL_NOTIFICATIONS is enabled but EMAIL values are not set.[/bold yellow]\n\n"
            "Add to your [cyan].env[/cyan] file:\n\n"
            "[bold yellow]EMAIL_FROM=your_sending_email_here[/bold yellow]\n\n"
            "[bold yellow]EMAIL_TO=your_receiving_email_here[/bold yellow]\n\n"
            "[bold yellow]EMAIL_PASSWORD=your_password_here (16 chars app password, not login)[/bold yellow]\n\n",
            title="[yellow]Warning[/yellow]",
            border_style="yellow",
        ))

    print_header()

    seen = load_seen()
    first_run = len(seen) == 0
    last_checked = "never"

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            live.update(Panel(
                Text("Checking for new freeleech...", style="dim"),
                border_style="dim",
                padding=(0, 2),
            ))
            torrents = fetch_freeleech()
            last_checked = ts()

            if torrents:
                new = [t for t in torrents if str(t["fid"]) not in seen]

                if first_run:
                    live.console.print(
                        f"[bold yellow][{ts()}] First run — seeding [cyan]{len(torrents)}[/cyan] "
                        "existing entries. New additions will appear here.[/bold yellow]"
                    )
                    for t in torrents:
                        seen.add(str(t["fid"]))
                    first_run = False
                else:
                    if new:
                        live.console.print(Rule("[bold green]New Freeleech[/bold green]", style="green"))
                        table, downloaded = build_table(new)
                        live.console.print(table)
                        for t in new:
                            seen.add(str(t["fid"]))
                            notify("TL Freeleech", t["name"])

                        if EMAIL_NOTIFICATIONS:
                            for t in downloaded:
                                send_email(
                                    f"Downloaded Freeleech: {t['name']}",
                                    f"Size: {fmt_size(t['size'])}\n"
                                    f"https://www.torrentleech.org/torrent/{t['fid']}"
                                )
                        print("\a")

                save_seen(seen)

            for remaining in range(POLL_INTERVAL, 0, -1):
                live.update(countdown_panel(remaining, last_checked))
                time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Stopped.[/bold red]")