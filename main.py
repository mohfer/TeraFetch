#!/usr/bin/env python3
"""TeraFetch - Batch downloader and IDM link exporter for TeraBox."""

import argparse
import sys
from pathlib import Path

from scrapers import fetch_files, load_file_list, save_file_list
from src.downloader import collect_download_links, download_batch, save_links
from src.utils import setup_logging


def parse_args() -> argparse.Namespace:
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


def scrape(url: str, json_path: str) -> list[dict]:
    print(f"Fetching: {url}")
    try:
        files = fetch_files(url)
        save_file_list(files, json_path)
        print(f"Found {len(files)} files. Saved to {json_path}")
        return files
    except Exception as e:
        print(f"Error: Failed to fetch files: {e}", file=sys.stderr)
        sys.exit(1)


def export_for_idm(
    files: list[dict],
    args: argparse.Namespace,
) -> None:
    idm_path = args.idm_output or str(Path(args.output) / "idm_links.txt")
    idm_failed_path = str(Path(args.output) / "idm_links_failed.txt")

    start_idx = max(0, args.start - 1)
    end_idx = len(files)
    if args.limit:
        end_idx = min(start_idx + args.limit, len(files))
    selected = files[start_idx:end_idx]

    if not selected:
        print("No files to export.")
        return

    print(f"\nWill export {len(selected)} files (index {start_idx+1}-{start_idx+len(selected)})")

    valid_urls, errors = collect_download_links(
        selected,
        validate=args.idm_check,
        validation_workers=args.idm_check_workers,
    )

    save_links(valid_urls, idm_path)

    failed_urls = [err.get("url") for err in errors if err.get("url")]
    if failed_urls:
        save_links(failed_urls, idm_failed_path)

    print(f"Exported {len(valid_urls)} valid links to {idm_path}")
    if failed_urls:
        print(f"Exported {len(failed_urls)} failed links to {idm_failed_path}")
        print("Failed links saved - you can try importing these manually in IDM.")

    print("\nUse idm_links.txt as IDM import list.")


def run_download(
    files: list[dict],
    args: argparse.Namespace,
    source_url: str | None,
    json_path: str,
) -> None:
    start_idx = max(0, args.start - 1)
    end_idx = len(files)
    if args.limit:
        end_idx = min(start_idx + args.limit, len(files))
    selected = files[start_idx:end_idx]

    if not selected:
        print("No files to download.")
        return

    print(f"\nWill download {len(selected)} files (index {start_idx+1}-{start_idx+len(selected)})")
    print_file_list(selected)

    try:
        confirm = input(f"\nDownload {len(selected)} files? [Y/n] ").strip().lower()
        if confirm and confirm != "y":
            print("Cancelled.")
            return
    except EOFError:
        pass

    max_retries = 2
    for attempt in range(max_retries + 1):
        results = download_batch(selected, args.output, args.workers, args.quality)
        expired = results.get("expired_files", [])

        if not expired or attempt >= max_retries:
            if expired:
                print(f"Warning: {len(expired)} files still have expired links")
            break

        print(f"{len(expired)} file(s) have expired links. Re-scraping (attempt {attempt+1}/{max_retries})...")

        if not source_url:
            print("Error: Cannot re-scrape - no source URL provided", file=sys.stderr)
            break

        try:
            fresh = fetch_files(source_url)
            save_file_list(fresh, json_path)
            fresh_lookup = {f.get("fs_id"): f for f in fresh if f.get("fs_id")}

            updated = 0
            for i, f in enumerate(files):
                fs_id = f.get("fs_id")
                if fs_id and fs_id in fresh_lookup:
                    if f.get("dlink") != fresh_lookup[fs_id].get("dlink"):
                        files[i] = fresh_lookup[fs_id]
                        updated += 1

            print(f"Updated {updated} file(s) with fresh links")

        except Exception as e:
            print(f"Error: Re-scrape failed: {e}", file=sys.stderr)
            break

    elapsed = results.get("elapsed", 0)
    print(f"\n{'='*55}")
    print(f"DONE  ({elapsed:.0f}s)  Success: {results['success']}  Failed: {results['failed']}")
    if results["details"]:
        print(f"\nFailed ({len(results['details'])}):")
        for d in results["details"][:10]:
            print(f"  - {d['file']}: {d['error']}")


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    if args.url:
        json_path = str(Path(args.output) / "file_list.json")
        files = scrape(args.url, json_path)
        if args.scrape_only:
            print_file_list(files)
            return
    elif args.from_json:
        try:
            files = load_file_list(args.from_json)
            print(f"Loaded {len(files)} files from {args.from_json}")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        json_path = args.from_json
    else:
        print("Error: Provide --url or --from-json", file=sys.stderr)
        parse_args().print_help()
        sys.exit(1)

    if args.idm:
        export_for_idm(files, args)
    else:
        source_url = args.url if args.url else None
        run_download(files, args, source_url, json_path)


if __name__ == "__main__":
    main()
