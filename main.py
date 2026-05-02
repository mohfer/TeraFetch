#!/usr/bin/env python3
"""
TeraFetch - Batch downloader and IDM link exporter for TeraBox.

Refactored with clean architecture:
- Handler layer (this file): CLI parsing and user interaction
- Service layer: Business logic
- Repository layer: I/O operations
"""

import argparse
import logging
import sys
from pathlib import Path

from src.repositories import (
    ApiRepository,
    FileListRepository,
    FileSystemRepository,
    HttpRepository,
    LinkExportRepository,
)
from src.services import DownloadService, ScraperService, ValidationService
from src.utils import setup_logging


class ConsoleLogger:
    """Simple console logger implementation."""

    def info(self, msg: str, **kwargs) -> None:
        print(msg)

    def error(self, msg: str, **kwargs) -> None:
        print(f"Error: {msg}", file=sys.stderr)

    def warning(self, msg: str, **kwargs) -> None:
        print(f"Warning: {msg}")

    def debug(self, msg: str, **kwargs) -> None:
        if logging.getLogger().level == logging.DEBUG:
            print(f"Debug: {msg}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="TeraFetch - batch downloader and IDM link exporter for TeraBox mirrors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--url", "-u", help="TeraBox share URL or cache URL")
    p.add_argument("--from-json", "-f", help="Download from a previously scraped JSON file")
    p.add_argument("--scrape-only", action="store_true", help="Only scrape, save to JSON")
    p.add_argument("--output", "-o", default="downloads", help="Output folder (default: downloads)")
    p.add_argument("--workers", "-w", type=int, default=3, help="Concurrent downloads (default: 3)")
    p.add_argument("--limit", "-n", type=int, help="Max number of files to download")
    p.add_argument("--start", "-s", type=int, default=1, help="Start from file number (default: 1)")
    p.add_argument(
        "--quality",
        "-q",
        choices=["best", "1080p", "720p", "480p", "360p"],
        help="Download from m3u8 stream at specified quality (uses yt-dlp)",
    )
    p.add_argument(
        "--idm", action="store_true", help="Export direct download links to TXT and skip downloading"
    )
    p.add_argument("--idm-output", default=None, help="IDM TXT output path (default: <output>/idm_links.txt)")
    p.add_argument("--idm-check", action="store_true", help="Validate links before exporting")
    p.add_argument(
        "--idm-check-workers", type=int, default=3, help="Number of parallel validation workers (default: 3)"
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def print_file_list(files: list[dict]) -> None:
    """Print formatted file list."""
    total_size = 0
    print(f"\n  {'#':>4}  {'Name':<45} {'Size':>10}")
    print(f"  {'':>4}  {'-'*45} {'-'*10}")
    for i, f in enumerate(files, 1):
        name = f.get("name", "?")
        if len(name) > 43:
            name = name[:40] + "..."
        size = f.get("size_formatted", "?")
        sb = f.get("size", 0)
        if isinstance(sb, (int, float)):
            total_size += sb
        print(f"  {i:>4}  {name:<45} {size:>10}")
    print(f"\n  Total: {total_size / (1024**3):.1f} GB")


def handle_scrape(args: argparse.Namespace, scraper_service: ScraperService, logger: ConsoleLogger) -> list[dict]:
    """Handle scraping operation."""
    json_path = str(Path(args.output) / "file_list.json")

    logger.info(f"Fetching: {args.url}")
    try:
        files = scraper_service.fetch_from_url(args.url, json_path)
        logger.info(f"Found {len(files)} files. Saved to {json_path}")
        return files
    except Exception as e:
        logger.error(f"Failed to fetch files: {e}")
        sys.exit(1)


def handle_idm_export(
    args: argparse.Namespace,
    files: list[dict],
    validation_service: ValidationService,
    logger: ConsoleLogger,
) -> None:
    """Handle IDM link export."""
    idm_path = args.idm_output or str(Path(args.output) / "idm_links.txt")
    idm_failed_path = str(Path(args.output) / "idm_links_failed.txt")

    start_idx = max(0, args.start - 1)
    end_idx = len(files)
    if args.limit:
        end_idx = min(start_idx + args.limit, len(files))
    selected = files[start_idx:end_idx]

    if not selected:
        logger.info("No files to export.")
        return

    logger.info(f"\nWill export {len(selected)} files (index {start_idx+1}-{start_idx+len(selected)})")

    valid_count, failed_count = validation_service.export_links(
        selected,
        idm_path,
        idm_failed_path,
        validate=args.idm_check,
        validation_workers=args.idm_check_workers,
    )

    logger.info(f"Exported {valid_count} valid links to {idm_path}")
    if failed_count > 0:
        logger.info(f"Exported {failed_count} failed links to {idm_failed_path}")
        logger.info("Failed links saved - you can try importing these manually in IDM.")

    logger.info("\nUse idm_links.txt as IDM import list.")


def handle_download(
    args: argparse.Namespace,
    files: list[dict],
    download_service: DownloadService,
    scraper_service: ScraperService,
    logger: ConsoleLogger,
) -> None:
    """Handle download operation."""
    start_idx = max(0, args.start - 1)
    end_idx = len(files)
    if args.limit:
        end_idx = min(start_idx + args.limit, len(files))
    selected = files[start_idx:end_idx]

    if not selected:
        logger.info("No files to download.")
        return

    logger.info(f"\nWill download {len(selected)} files (index {start_idx+1}-{start_idx+len(selected)})")
    print_file_list(selected)

    try:
        confirm = input(f"\nDownload {len(selected)} files? [Y/n] ").strip().lower()
        if confirm and confirm != "y":
            logger.info("Cancelled.")
            return
    except EOFError:
        pass

    json_path = str(Path(args.output) / "file_list.json")
    source_url = args.url if args.url else None

    results = download_service.download_with_retry(
        selected,
        args.output,
        args.workers,
        source_url,
        scraper_service,
        json_path,
        quality=args.quality,
    )

    elapsed = results.get("elapsed", 0)
    print(f"\n{'='*55}")
    print(f"DONE  ({elapsed:.0f}s)  Success: {results['success']}  Failed: {results['failed']}")
    if results["details"]:
        print(f"\nFailed ({len(results['details'])}):")
        for d in results["details"][:10]:
            print(f"  - {d['file']}: {d['error']}")


def main() -> None:
    """Main entry point - handles CLI and delegates to services."""
    args = parse_args()
    setup_logging(args.verbose)

    # Initialize dependencies (Dependency Injection)
    logger = ConsoleLogger()
    fs = FileSystemRepository()
    http = HttpRepository()
    api_repo = ApiRepository(http)
    file_list_repo = FileListRepository(fs)
    link_export_repo = LinkExportRepository(fs)

    # Initialize services
    scraper_service = ScraperService(api_repo, file_list_repo, logger)
    download_service = DownloadService(logger)
    validation_service = ValidationService(link_export_repo, logger)

    # Load or fetch files
    if args.url:
        files = handle_scrape(args, scraper_service, logger)
        if args.scrape_only:
            print_file_list(files)
            return
    elif args.from_json:
        try:
            files = scraper_service.load_from_json(args.from_json)
            logger.info(f"Loaded {len(files)} files from {args.from_json}")
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)
    else:
        logger.error("Error: Provide --url or --from-json")
        parse_args().print_help()
        sys.exit(1)

    # Execute operation
    if args.idm:
        handle_idm_export(args, files, validation_service, logger)
    else:
        handle_download(args, files, download_service, scraper_service, logger)


if __name__ == "__main__":
    main()
