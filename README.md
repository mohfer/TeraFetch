# TeraFetch

Batch downloader and IDM link exporter for TeraBox mirror links.

Fetches file lists from TeraBox share URLs or cache URLs, validates links, and exports them for Internet Download Manager (IDM) or downloads directly with curl/yt-dlp.

## Features

- ✅ Auto-detect TeraBox share URLs (uses teraboxdownloader.xyz)
- ✅ Support cache URLs from teraboxdownloader.xyz/pro
- ✅ **Parallel link validation** with retry mechanism (5 retries, exponential backoff)
- ✅ **Separate output files** for valid and failed links
- ✅ **Performance optimizations**: caching, connection pooling, metrics logging
- ✅ Batch download with concurrent workers
- ✅ Multiple quality options (360p, 480p, 720p, 1080p)
- ✅ Auto re-scrape on expired links
- ✅ Detailed validation logging

## Architecture

TeraFetch follows **Clean Architecture** principles with clear layer separation:

- **Handler Layer** (`main.py`) - CLI parsing and user interaction
- **Service Layer** (`src/services.py`) - Business logic
- **Repository Layer** (`src/repositories.py`) - I/O operations
- **Protocol Layer** (`src/protocols.py`) - Interface definitions

### Design Patterns

- ✅ Separation of Concerns - Clear layer boundaries
- ✅ Dependency Injection - Constructor injection for testability
- ✅ Protocol-Based Design - Flexible implementations
- ✅ Single Responsibility - One reason to change per class
- ✅ Composition Over Inheritance - No complex hierarchies

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

**Validation features:**
- Parallel validation with configurable workers (default: 3)
- 5 retries with exponential backoff (1s, 2s, 4s, 8s, 16s)
- HTTP 5xx errors are retried, HTTP 4xx errors fail immediately
- Detailed logging of status codes, headers, and response content

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
- `https://terabox.app/sharing/link?surl=XXX`

**Note:** Other TeraBox domains may work but haven't been tested yet.

### Cache URLs
- `https://teradl.kingx.dev/cache?hash=XXX`

**Note:** Other cache URLs (teraboxdownloader.xyz, teraboxdownloader.pro) may work but haven't been tested yet.

## Validation Details

When using `--idm-check`, the script validates each link before exporting:

**Retry Logic:**
- HTTP 5xx errors (500, 502, 503): Retry up to 5 times with exponential backoff
- HTTP 4xx errors (400, 404, 403): Fail immediately (permanent errors)
- Network errors (timeout, connection): Retry up to 5 times

**Parallel Validation:**
- Default: 3 workers (balanced speed and safety)
- Increase workers for faster validation (risk: rate limiting)
- Decrease workers if getting too many HTTP 500 errors

**Output:**
- Valid links → `idm_links.txt`
- Failed links → `idm_links_failed.txt` (can be tried manually in IDM)
- Detailed logs → `validation.log` (cleared each run)

## Notes

- **Playwright required**: TeraBox share URLs use Playwright to scrape teraboxdownloader.xyz
- **curl required**: Direct downloads use curl (must be in PATH)
- Links can expire or fail validation but still work in IDM (server-side issues)
- Use `--url` instead of `--from-json` to enable auto re-scrape on expired links
- Download speed depends on mirror/proxy server performance
- `--quality` requires yt-dlp installed: `pip install yt-dlp`
- Recommended validation workers: 1-3 (safe), 5-10 (fast but may trigger rate limits)

## Performance

TeraFetch includes several performance optimizations:

- **Caching**: `@lru_cache` for repeated URL parsing (2-5x speedup)
- **Connection pooling**: Reuse HTTP connections for validation (30-50% faster)
- **Parallel processing**: Concurrent downloads and validation
- **Metrics logging**: Track validation/download performance in `downloads/metrics.jsonl`
