import os
import argparse
import random
import string
import requests
import sys
import time
import concurrent.futures
import threading
import signal
from dataclasses import dataclass, field
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────

FIREFOX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
BASE_URL = "https://files.catbox.moe/{slug}.{ext}"
LOG_FILE = Path("log.txt")


@dataclass
class Config:
    extension: str = "png"
    workers: int = 4
    verbose: bool = False
    download: bool = False
    output_dir: Path = None
    show_count: bool = False
    timeout: float = 10.0
    delay: float = 0.002  # seconds between task submissions

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = Path(self.extension)


# ─────────────────────────────────────────────
#  Stats tracker
# ─────────────────────────────────────────────

class Stats:
    def __init__(self):
        self._lock = threading.Lock()
        self.checked = 0
        self.found = 0
        self.errors = 0
        self._start = time.monotonic()

    def inc_checked(self):
        with self._lock:
            self.checked += 1

    def inc_found(self):
        with self._lock:
            self.found += 1

    def inc_errors(self):
        with self._lock:
            self.errors += 1

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    @property
    def rps(self) -> float:
        elapsed = self.elapsed
        return self.checked / elapsed if elapsed > 0 else 0.0

    def summary(self) -> str:
        return (
            f"checked={self.checked}  found={self.found}  "
            f"errors={self.errors}  req/s={self.rps:.1f}  "
            f"elapsed={self.elapsed:.0f}s"
        )


# ─────────────────────────────────────────────
#  HTTP session (shared, thread-safe)
# ─────────────────────────────────────────────

def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": FIREFOX_UA})
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=32,
        pool_maxsize=64,
        max_retries=0,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ─────────────────────────────────────────────
#  Core logic
# ─────────────────────────────────────────────

def random_slug(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_url(ext: str) -> str:
    return BASE_URL.format(slug=random_slug(), ext=ext)


def log(path: Path, line: str, lock: threading.Lock) -> None:
    with lock:
        with path.open("a") as f:
            f.write(line + "\n")


def download_file(session: requests.Session, url: str, dest: Path, timeout: float) -> bool:
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            dest.write_bytes(resp.content)
            return True
    except Exception as e:
        print(Fore.RED + f"  download error: {e}")
    return False


def check_url(
    cfg: Config,
    session: requests.Session,
    stats: Stats,
    log_lock: threading.Lock,
    shutdown: threading.Event,
) -> None:
    if shutdown.is_set():
        return

    url = generate_url(cfg.extension)
    try:
        resp = session.get(url, timeout=cfg.timeout)
        stats.inc_checked()

        if resp.status_code == 200:
            stats.inc_found()
            print(Fore.GREEN + f"[HIT]  {url}")
            log(LOG_FILE, f"found: {url}", log_lock)

            if cfg.download:
                cfg.output_dir.mkdir(parents=True, exist_ok=True)
                dest = cfg.output_dir / Path(url).name
                if not dest.exists():  # skip duplicates
                    ok = download_file(session, url, dest, cfg.timeout)
                    if ok:
                        print(Fore.GREEN + f"  ✅ saved → {dest}")
                    else:
                        print(Fore.RED + f"  ✗ download failed")
        else:
            if cfg.verbose:
                print(Fore.WHITE + Style.DIM + f"[miss] {url}  ({resp.status_code})")
            log(LOG_FILE, f"miss: {url}", log_lock)

    except requests.exceptions.Timeout:
        stats.inc_errors()
        if cfg.verbose:
            print(Fore.YELLOW + f"[timeout] {url}")
    except requests.exceptions.RequestException as e:
        stats.inc_errors()
        if cfg.verbose:
            print(Fore.YELLOW + f"[error] {e}")


# ─────────────────────────────────────────────
#  Status printer
# ─────────────────────────────────────────────

def status_printer(stats: Stats, shutdown: threading.Event) -> None:
    while not shutdown.is_set():
        time.sleep(1)
        print(
            Fore.CYAN + f"\r  ↳ {stats.summary()}          ",
            end="",
            flush=True,
        )
    print()  # newline on exit


# ─────────────────────────────────────────────
#  Log reader
# ─────────────────────────────────────────────

def list_found() -> None:
    if not LOG_FILE.exists():
        print("log.txt not found.")
        return
    hits = [l.strip() for l in LOG_FILE.read_text().splitlines() if l.startswith("found:")]
    if not hits:
        print("No hits logged yet.")
    for h in hits:
        print(Fore.GREEN + h)


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="catbox.moe random URL scanner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("-f", "--file", default="png", metavar="EXT",
                   help="file extension to search for (e.g. png, mp4, gif)")
    p.add_argument("-w", "--workers", type=int, default=4,
                   help="number of concurrent threads")
    p.add_argument("-d", "--download", action="store_true",
                   help="download files as they are found")
    p.add_argument("-o", "--output", metavar="DIR",
                   help="directory to save downloads (default: <ext>/)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print misses and errors")
    p.add_argument("-l", "--list", action="store_true",
                   help="list all previously found URLs from log.txt and exit")
    p.add_argument("--delay", type=float, default=0.002,
                   help="seconds between task submissions (lower = faster)")
    p.add_argument("--timeout", type=float, default=10.0,
                   help="per-request timeout in seconds")
    return p.parse_args()


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.list:
        list_found()
        sys.exit(0)

    cfg = Config(
        extension=args.file,
        workers=args.workers,
        verbose=args.verbose,
        download=args.download,
        output_dir=Path(args.output) if args.output else Path(args.file),
        timeout=args.timeout,
        delay=args.delay,
    )

    print(Fore.CYAN + f"[catbox scanner]  ext=.{cfg.extension}  workers={cfg.workers}"
          + ("  download=on" if cfg.download else ""))
    print(Fore.WHITE + Style.DIM + "Press Ctrl+C to stop.\n")

    shutdown = threading.Event()
    log_lock = threading.Lock()
    stats = Stats()
    session = build_session()

    # Graceful Ctrl+C
    def _sigint(sig, frame):
        print(Fore.CYAN + "\n[!] stopping…")
        shutdown.set()

    signal.signal(signal.SIGINT, _sigint)

    # Live stats printer
    printer = threading.Thread(target=status_printer, args=(stats, shutdown), daemon=True)
    printer.start()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.workers) as executor:
            while not shutdown.is_set():
                executor.submit(check_url, cfg, session, stats, log_lock, shutdown)
                time.sleep(cfg.delay)
    finally:
        shutdown.set()
        session.close()
        printer.join(timeout=2)
        print(Fore.CYAN + f"\n[done] {stats.summary()}")
        sys.exit(0)


if __name__ == "__main__":
    main()
