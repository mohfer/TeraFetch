# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TeraFetch is a batch downloader and IDM link exporter for TeraBox mirror links. It fetches file lists from TeraBox share URLs or cache URLs, validates links, and exports them for Internet Download Manager (IDM) or downloads directly with curl/yt-dlp.

The project follows **Clean Architecture** with clear layer separation for maintainability and testability.

## Development Commands

### Setup
```bash
uv sync
uv run playwright install chromium
```

### Run the application
```bash
# From TeraBox share URL with validation
uv run main.py -u "https://www.1024tera.com/sharing/link?surl=XXX" --idm --idm-check

# From cache URL
uv run main.py -u "https://teradl.kingx.dev/cache?hash=XXX" --workers 5

# From saved JSON
uv run main.py --from-json downloads/file_list.json --limit 10

# Adjust validation workers (default: 3)
uv run main.py -u "URL" --idm --idm-check --idm-check-workers 5
```

### Testing
```bash
# Syntax check
python -m py_compile main.py src/*.py

# Test specific module
python -m py_compile src/downloader.py
```

## Architecture

### Layer Structure

```
Handler Layer (main.py)
    ↓
Service Layer (src/services.py)
    ↓
Repository Layer (src/repositories.py)
    ↓
Protocol Layer (src/protocols.py)
```

**Handler Layer** (`main.py`)
- CLI argument parsing
- User interaction (prompts, output formatting)
- Delegates to services
- No business logic or I/O

**Service Layer** (`src/services.py`)
- `ScraperService` - Fetch and normalize file lists
- `DownloadService` - Download orchestration with retry logic
- `ValidationService` - Link validation and export
- Pure business logic, no I/O operations

**Repository Layer** (`src/repositories.py`)
- `FileSystemRepository` - File operations
- `HttpRepository` - HTTP client
- `ApiRepository` - TeraBox API calls
- `FileListRepository` - JSON storage
- `LinkExportRepository` - Export links to TXT
- All I/O operations isolated here

**Protocol Layer** (`src/protocols.py`)
- Interface definitions for dependency injection
- Enables testing with mocks/fakes
- Protocols: `HttpClient`, `FileSystem`, `Logger`, `Downloader`, `Validator`, `Scraper`

### Core Modules

**src/terabox_xyz.py** - Playwright-based scraper
- `fetch_terabox_xyz()` - Fetches files from TeraBox share URLs
- Uses async Playwright to intercept API responses from teradl.kingx.dev/gettask
- Returns normalized file list

**src/convert.py** - Data normalization
- `convert_teraboxdownloader()` - Converts cache API format to TeraFetch format
- Used for cache URLs (teradl.kingx.dev)
- Can be run standalone: `python src/convert.py response.json -o output.json`

**src/downloader.py** - Download implementation
- `download_batch()` - Concurrent downloads with ThreadPoolExecutor
- `collect_download_links()` - Parallel validation with configurable workers
- `_validate_download_url()` - URL validation with retry (5 attempts, exponential backoff)
- Performance optimizations: `@lru_cache`, connection pooling, metrics logging

**src/performance.py** - Performance monitoring
- `timing_decorator` - Automatic execution time tracking
- `PerformanceMonitor` - Context manager for code blocks
- `log_metric()` - Logs to `downloads/metrics.jsonl`

**src/utils.py** - Helper utilities
- `validate_url()` - Validates supported URLs (only tested URLs documented)
- `is_terabox_share_url()` - Distinguishes share URLs from cache URLs

### Data Flow

1. **URL Detection**: Check if TeraBox share URL or cache URL
2. **Fetching**:
   - Share URLs → `fetch_terabox_xyz()` (Playwright)
   - Cache URLs → `ApiRepository.fetch_cache_data()` → `convert_teraboxdownloader()`
3. **Normalization**: Both produce same file record format
4. **Storage**: Save to `downloads/file_list.json`
5. **Download/Export**:
   - Download: `download_batch()` with curl or yt-dlp
   - IDM: `collect_download_links()` + `save_links()` → TXT files

### File Record Format

```python
{
    "name": "filename.mp4",
    "size": 1234567,
    "size_formatted": "1.2 MB",
    "dlink": "https://...",  # Direct download URL
    "quality": {"360p": "...", "720p": "...", "1080p": "..."},
    "streaming_url": "https://...m3u8",
    "caption": "https://...srt",
    "fs_id": 123456,  # For deduplication and re-scraping
    "thumbnail": "https://...",
    "folder": "/path/to/folder",
    "category": 1,
    "_source": "teraboxdownloader"
}
```

## Performance Optimizations

- **Caching**: `@lru_cache` on `_get_download_url()` (2-5x speedup)
- **Connection Pooling**: `requests.Session` with HTTPAdapter (30-50% faster)
- **Parallel Validation**: ThreadPoolExecutor with configurable workers (default: 3)
- **Metrics Logging**: Auto-logged to `downloads/metrics.jsonl`

## Output Files

- `downloads/file_list.json` - Scraped file list
- `downloads/idm_links.txt` - Valid links for IDM import
- `downloads/idm_links_failed.txt` - Failed links (can be tried manually)
- `downloads/validation.log` - Detailed validation logs (auto-cleared each run)
- `downloads/metrics.jsonl` - Performance metrics

## Supported URLs (Tested)

**TeraBox Share URLs:**
- `https://www.1024tera.com/sharing/link?surl=XXX`
- `https://terabox.app/sharing/link?surl=XXX`

**Cache URLs:**
- `https://teradl.kingx.dev/cache?hash=XXX`

Other domains may work but haven't been verified.

## Link Expiration Handling

The downloader detects expired links by checking:
- JSON responses with "link expired" error
- HTML responses instead of file content
- Small file sizes (< 1KB)

When detected, `main.py` automatically re-scrapes fresh links and retries (up to 2 attempts).

## Validation Features

When using `--idm-check`:
- Parallel validation with configurable workers (default: 3)
- 5 retries with exponential backoff (1s, 2s, 4s, 8s, 16s)
- HTTP 5xx errors are retried, HTTP 4xx fail immediately
- Connection pooling for better performance
- Detailed logging of status codes, headers, response content

## Dependencies

- `requests` - HTTP client
- `playwright` - Browser automation (required for share URLs)
- `yt-dlp` - Video downloader (optional, for --quality flag)
- `curl` - External command for downloads (must be in PATH)

## Important Notes

- Use `--url` instead of `--from-json` to enable auto re-scrape on expired links
- Validation workers: 1-3 (safe), 5-10 (fast but may trigger rate limits)
- Links can fail validation but still work in IDM (server-side issues)
- Referer headers are automatically set based on URL domain
- Download speed depends on mirror/proxy server performance
