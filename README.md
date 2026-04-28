# USE AT YOUR OWN RISK

**WARNING**: If you run this script you will likely download some NSFW/NSFL files. Some of them might be vile, some even illegal.

# catbox-scanner

A fast, multithreaded CLI tool that hunts for publicly accessible files on [catbox.moe](https://catbox.moe) by brute-forcing random 6-character slugs.

```
[catbox scanner]  ext=.png  workers=16  download=on
Press Ctrl+C to stop.

[HIT]  https://files.catbox.moe/a3kx9f.png
  ✅ saved → png/a3kx9f.png
[HIT]  https://files.catbox.moe/zq18mr.png
  ✅ saved → png/zq18mr.png
  ↳ checked=4821  found=2  errors=0  req/s=312.4  elapsed=15s
```

---

## Features

- **Concurrent scanning** — configurable thread pool, shared connection pool
- **Live stats** — real-time requests/sec, hit count, and elapsed time
- **Auto-download** — save hits to disk as they're found, skipping duplicates
- **Persistent log** — all hits written to `log.txt` for later review
- **Graceful shutdown** — Ctrl+C drains in-flight requests and prints a final summary

---

## Installation

### Nix

```bash
nix-shell
```

### pip

```bash
pip install requests colorama
```

Requires Python 3.8+.

---

## Usage

```bash
python catbox_scanner.py [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-f`, `--file EXT` | `png` | File extension to scan for |
| `-w`, `--workers N` | `4` | Number of concurrent threads |
| `-d`, `--download` | off | Download hits as they are found |
| `-o`, `--output DIR` | `<ext>/` | Directory to save downloads |
| `-v`, `--verbose` | off | Show misses and errors |
| `-l`, `--list` | — | Print all logged hits and exit |
| `--delay SECS` | `0.002` | Delay between task submissions |
| `--timeout SECS` | `10.0` | Per-request timeout |

### Examples

```bash
# Scan for PNGs, 4 threads (default)
python catbox_scanner.py

# Scan for MP4s, 16 threads, download everything
python catbox_scanner.py -f mp4 -w 16 -d

# Scan for GIFs, verbose, save to ./results
python catbox_scanner.py -f gif -w 8 -v -o ./results

# Crank up throughput
python catbox_scanner.py -w 32 --delay 0.0005

# Review previously found URLs
python catbox_scanner.py --list
```

---

## Output

Hits are printed in green and appended to `log.txt`:

```
found: https://files.catbox.moe/abc123.png
```

Downloaded files are saved to `./<ext>/` by default (or `--output DIR`). Files that already exist on disk are skipped.

---

## License

MIT
