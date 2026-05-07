# TeraFetch

Batch downloader and IDM link exporter for TeraBox. Scrapes file lists from TeraBox share URLs, validates download links, and exports for IDM or downloads directly.

## Features

- ✅ Auto-detect TeraBox share URLs (uses teraboxdownloader.xyz)
- ✅ Support cache URLs from teraboxdownloader.xyz/pro
- ✅ Parallel link validation with retry mechanism
- ✅ Separate output files for valid and failed links
- ✅ Batch download with concurrent workers
- ✅ Multiple quality options (360p, 480p, 720p, 1080p)
- ✅ Auto re-scrape on expired links

## Structure

```
terafetch/
├── main.py              # CLI + orchestration
├── scrapers.py          # Scraping logic (share URLs + cache URLs)
└── src/
    ├── downloader.py    # Download + validation
    └── utils.py         # Helper utilities
```

## Install

```bash
# Install dependencies
uv sync

# Install Playwright browsers (required for TeraBox share URL scraping)
uv run playwright install chromium
```

## Usage

### Export to IDM (Recommended)

```bash
# From TeraBox share URL with validation
uv run main.py -u "https://www.1024tera.com/sharing/link?surl=XXX" --idm --idm-check

# From cache URL with validation
uv run main.py -u "https://teradl.kingx.dev/cache?hash=XXX" --idm --idm-check

# Adjust validation workers (default: 3)
uv run main.py -u "URL" --idm --idm-check --idm-check-workers 5
```

**Output files:**

- `downloads/idm_links.txt` - Valid links ready for IDM import
- `downloads/idm_links_failed.txt` - Failed links (can be tried manually in IDM)
- `downloads/validation.log` - Detailed validation logs (auto-cleared each run)

### Direct Download

```bash
# From TeraBox share URL
uv run main.py -u "https://www.1024tera.com/sharing/link?surl=XXX" --workers 5

# From cache URL
uv run main.py -u "https://teradl.kingx.dev/cache?hash=XXX" --workers 5

# From saved JSON
uv run main.py --from-json downloads/file_list.json --limit 10
```

### Advanced Options

```bash
# Scrape only (save to JSON without downloading)
uv run main.py -u "URL" --scrape-only

# Download with quality selection (requires yt-dlp)
uv run main.py --from-json downloads/file_list.json --quality 720p

# Download specific range
uv run main.py --from-json downloads/file_list.json --start 11 --limit 10

# Custom output paths
uv run main.py -u "URL" --idm --idm-output custom/path.txt
```

## Options

```text
Input:
  --url, -u                 TeraBox share URL or cache URL
  --from-json, -f           Path to file_list.json from previous scrape

Download:
  --output, -o              Output folder (default: downloads)
  --workers, -w             Concurrent downloads (default: 3)
  --limit, -n               Max number of files to download/export
  --start, -s               Start from file number (default: 1)
  --quality, -q             Download m3u8 stream quality (best/1080p/720p/480p/360p)

IDM Export:
  --idm                     Export links to TXT and skip downloading
  --idm-output              TXT output path (default: downloads/idm_links.txt)
  --idm-check               Validate links before exporting
  --idm-check-workers       Parallel validation workers (default: 3)

Other:
  --scrape-only             Only scrape, save to JSON
  --verbose, -v             Debug logging
```

## Supported URLs

### TeraBox Share URLs (Auto-detect)

- `https://www.1024tera.com/sharing/link?surl=XXX`
- `https://1024terabox.com/s/XXX`
- `https://terabox.app/sharing/link?surl=XXX`

**Note:** Other TeraBox domains may work but haven't been tested yet.

### URL validation behavior

- `--url` accepts any syntactically valid `http`/`https` URL, but only supported TeraBox URLs are processed successfully.
- Non-TeraBox URLs may reach the scraper and fail with the upstream response from the service.

### Cache URLs

- `https://teradl.kingx.dev/cache?hash=XXX`

**Note:** Other cache URLs (teraboxdownloader.xyz, teraboxdownloader.pro) may work but haven't been tested yet.

## Notes

- **Playwright required**: TeraBox share URLs use Playwright to scrape teraboxdownloader.xyz
- **curl required**: Direct downloads use curl (must be in PATH)
- Links can expire or fail validation but still work in IDM (server-side issues)
- Use `--url` instead of `--from-json` to enable auto re-scrape on expired links
- Download speed depends on mirror/proxy server performance
- `--quality` requires yt-dlp installed: `pip install yt-dlp`
- Recommended validation workers: 1-3 (safe), 5-10 (fast but may trigger rate limits)

## Credit

This tool uses the proxy service from [teraboxdownloader.xyz](https://teraboxdownloader.xyz) to fetch download links.
