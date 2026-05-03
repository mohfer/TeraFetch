# TeraFetch

Batch downloader and IDM link exporter for TeraBox mirror links.

TeraFetch allows you to:

- Fetch file lists from TeraBox share URLs or cache URLs
- Validate download links in parallel
- Export links for Internet Download Manager (IDM)
- Download files directly using `curl` / `yt-dlp`

---

## ✨ Features

- Auto-detect TeraBox share URLs (via `teraboxdownloader.xyz`)
- Support cache URLs (`teraboxdownloader.xyz/pro`)
- Parallel link validation with retry mechanism (5 retries, exponential backoff)
- Separate output files for valid and failed links
- Batch download with concurrent workers
- Multiple quality options: `360p`, `480p`, `720p`, `1080p`
- Auto re-scrape on expired links

---

## 📦 Requirements

| Dependency | Required For |
|------------|--------------|
| `uv` | Package & environment management |
| `playwright` (Chromium) | Scraping TeraBox share URLs |
| `curl` | Direct file downloads |
| `yt-dlp` | Quality-based downloads (`--quality`) |

---

## ⚙️ Installation

```bash
# Install dependencies
uv sync

# Install Playwright browsers (required for scraping)
uv run playwright install chromium
```

---

## 🚀 Usage

### 1. Export to IDM (Recommended)

```bash
# From TeraBox share URL
uv run main.py -u "https://www.1024tera.com/sharing/link?surl=XXX" --idm --idm-check

# From cache URL
uv run main.py -u "https://teradl.kingx.dev/cache?hash=XXX" --idm --idm-check

# Adjust validation workers
uv run main.py -u "URL" --idm --idm-check --idm-check-workers 5
```

**Output files:**

| File | Description |
|------|-------------|
| `downloads/idm_links.txt` | Valid links (ready for IDM import) |
| `downloads/idm_links_failed.txt` | Failed links |
| `downloads/validation.log` | Validation logs (auto-cleared each run) |

---

### 2. Direct Download

```bash
# From TeraBox share URL
uv run main.py -u "URL" --workers 5

# From cache URL
uv run main.py -u "URL" --workers 5

# From saved JSON
uv run main.py --from-json downloads/file_list.json --limit 10
```

---

### 3. Advanced Usage

```bash
# Scrape only (save to JSON, no download)
uv run main.py -u "URL" --scrape-only

# Download with quality selection (requires yt-dlp)
uv run main.py --from-json downloads/file_list.json --quality 720p

# Download a specific range
uv run main.py --from-json downloads/file_list.json --start 11 --limit 10

# Custom IDM output path
uv run main.py -u "URL" --idm --idm-output custom/path.txt
```

---

## 🧩 Options

### Input

| Flag | Description |
|------|-------------|
| `--url`, `-u` | TeraBox share URL or cache URL |
| `--from-json`, `-f` | Path to saved `file_list.json` |

### Download

| Flag | Default | Description |
|------|---------|-------------|
| `--output`, `-o` | `downloads` | Output folder |
| `--workers`, `-w` | `3` | Concurrent download workers |
| `--limit`, `-n` | — | Max number of files to download |
| `--start`, `-s` | `1` | Start from file number |
| `--quality`, `-q` | — | Quality: `best` / `1080p` / `720p` / `480p` / `360p` |

### IDM Export

| Flag | Default | Description |
|------|---------|-------------|
| `--idm` | — | Export links to TXT (skip download) |
| `--idm-output` | — | Custom TXT output path |
| `--idm-check` | — | Validate links before exporting |
| `--idm-check-workers` | `3` | Validation worker count |

### Other

| Flag | Description |
|------|-------------|
| `--scrape-only` | Scrape and save JSON only, no download |
| `--verbose`, `-v` | Enable debug logging |

---

## 🔗 Supported URLs

### TeraBox Share URLs

- `https://www.1024tera.com/sharing/link?surl=XXX`
- `https://terabox.app/sharing/link?surl=XXX`

> Other domains may work but are not fully tested.

### Cache URLs

- `https://teradl.kingx.dev/cache?hash=XXX`

> Other cache providers (`teraboxdownloader.xyz` / `.pro`) may work but are not fully tested.

---

## 🔍 Link Validation (IDM Mode)

When `--idm-check` is used, each link is validated before export.

> ⚠️ Some links may fail validation but still work in IDM due to server-side behavior.

---

## 📝 Notes

- Use `--url` instead of `--from-json` to enable auto re-scraping on expired links.
- Download speed depends on the mirror/proxy server.
- Install `yt-dlp` for quality-based downloads:
  ```bash
  pip install yt-dlp
  ```

### Recommended Worker Count

| Workers | Risk Level |
|---------|------------|
| 1–3 | Safe (low risk of rate limiting) |
| 5–10 | Faster (higher risk of rate limiting) |
