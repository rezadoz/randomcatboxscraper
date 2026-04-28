# AGENTS.md

## Project Overview

**catbox-scanner** is a multithreaded CLI tool that probes [catbox.moe](https://catbox.moe) for publicly accessible files by generating random 6-character slugs and checking whether the resulting URLs return HTTP 200. Hits are logged to `log.txt` and optionally downloaded.

---

## Repository Structure

```
.
├── catbox_scanner.py   # Single-file Python application (all logic lives here)
├── shell.nix           # Nix dev shell (Python 3 + requests + colorama)
└── log.txt             # Auto-created at runtime; stores hit/miss records
```

---

## Environment Setup

### Nix (recommended)

```bash
nix-shell        # drops you into a shell with all deps available
```

### pip (alternative)

```bash
pip install requests colorama
```

Python 3.8+ is required (uses `dataclasses`, `pathlib`, `concurrent.futures`).

---

## Running the Scanner

```bash
# Basic usage — scan for .png files with 4 threads
python catbox_scanner.py

# Scan for mp4 files with 16 threads, download hits
python catbox_scanner.py -f mp4 -w 16 -d

# Scan with verbose output (show misses), custom output dir, faster pace
python catbox_scanner.py -f gif -w 8 -v -o ./results --delay 0.001

# List all previously found URLs from log.txt
python catbox_scanner.py --list
```

### All CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-f`, `--file EXT` | `png` | File extension to search for |
| `-w`, `--workers N` | `4` | Number of concurrent threads |
| `-d`, `--download` | off | Download files as they are found |
| `-o`, `--output DIR` | `<ext>/` | Directory to save downloaded files |
| `-v`, `--verbose` | off | Print misses and errors |
| `-l`, `--list` | — | Print all hits from `log.txt` and exit |
| `--delay SECS` | `0.002` | Seconds between task submissions |
| `--timeout SECS` | `10.0` | Per-request timeout |

Press **Ctrl+C** for a graceful shutdown — the live stats line will print a final summary.

---

## Architecture

The codebase is intentionally single-file. Key components and their responsibilities:

### `Config` (dataclass)
Holds all runtime settings derived from CLI args. `output_dir` defaults to `./<ext>/` when not explicitly set.

### `Stats`
Thread-safe counters (`checked`, `found`, `errors`) plus elapsed time and requests-per-second derived properties. All mutations go through a `threading.Lock`.

### `build_session()`
Creates a shared `requests.Session` with a Firefox User-Agent and a tuned `HTTPAdapter` (`pool_maxsize=64`). One session is created per run and shared across all worker threads — `requests.Session` is thread-safe for concurrent GETs.

### `check_url()`
The unit of work submitted to the thread pool. Generates a random URL, fires a GET, increments stats, prints colored output, and optionally downloads the file. Respects the `shutdown` event to exit cleanly.

### `status_printer()`
Runs as a daemon thread. Prints an in-place stats line every second using `\r`.

### `main()`
Wires everything together: parses args → builds config/session/stats → installs a `SIGINT` handler → starts the printer thread → feeds tasks into a `ThreadPoolExecutor` in a tight loop throttled by `--delay`.

---

## Logging

All results are appended to `log.txt` in the working directory:

```
found: https://files.catbox.moe/abc123.png
miss:  https://files.catbox.moe/xyz789.png
```

`--list` filters and prints only `found:` lines from this file.

---

## Modifying the Scanner

**Change slug length** — edit `random_slug(length=6)` in `catbox_scanner.py`.

**Change the target domain / URL pattern** — edit `BASE_URL` at the top of the file.

**Add a new file extension** — no code change needed; pass `-f <ext>` at runtime.

**Persist stats across runs** — `Stats` is currently in-memory only; wire it to `log.txt` or a separate stats file if needed.

**Rate limiting / backoff** — `max_retries=0` is intentional. Add retry logic in `build_session()` via `urllib3.util.retry.Retry` if the target begins rate-limiting.

---

## Notes for Agents

- **No test suite exists.** When making changes, manually verify behavior with a small `--workers 1` run and `--verbose` to observe all request outcomes.
- **All state is in `catbox_scanner.py`.** There are no config files, databases, or additional modules to keep in sync.
- **`log.txt` grows unboundedly.** Truncate or rotate it manually between long runs.
- **The `shutdown` event is the only coordination mechanism** between threads. Any new long-running thread you add must accept and respect it.
- **Do not introduce global mutable state** outside of `Stats` — the existing design passes all shared objects explicitly to avoid hidden coupling.
