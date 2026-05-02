"""
convert.py - Normalize TeraBoxDownloader API responses to TeraFetch format.

This module converts API responses from TeraBoxDownloader mirrors (cache URLs)
into the standardized TeraFetch file record format. It's used internally by
main.py when fetching from cache URLs, and can also be run standalone to
convert manually captured API responses.

The teraboxdownloader.xyz integration (for TeraBox share URLs) uses a different
path via src/terabox_xyz.py and doesn't need this converter.

Usage:
  # Standalone conversion from saved API response
  python convert.py response.json -o downloads/file_list.json

  # Merge with existing file_list.json
  python convert.py response.json -o downloads/file_list.json --merge
"""

import argparse
import json
import sys
from pathlib import Path


def convert_teraboxdownloader(data: dict) -> list[dict]:
    """Convert a TeraBoxDownloader API response to TeraFetch records.

    Input format:
    {
        "files": [
            {
                "dlink": "https://teradl.kingx.dev/download?...",
                "fs_id": 123,
                "server_filename": "video.mp4",
                "size": 1234567,
                "human_size": "1.2 MB",
                "thumb": "https://...",
                "icon": "https://...",
                "path": "/folder/video.mp4",
                "category": 1,
                "quality": {"360": "https://...", "480": "https://...", "720": "https://..."},
                "streaming_url": "https://...",
                "caption": "https://..."
            }
        ]
    }

    Output format:
    [
        {
            "name": "video.mp4",
            "size": 1234567,
            "size_formatted": "1.2 MB",
            "dlink": "https://teradl.kingx.dev/download?...",
            "quality": {"360": "https://...", "480": "https://..."},
            "streaming_url": "https://...",
            "fs_id": 123,
            "thumbnail": "https://...",
            "folder": "/folder",
            "category": 1,
            "_source": "teraboxdownloader"
        }
    ]
    """
    files = []

    # Handle different input formats
    if "files" in data:
        raw_files = data["files"]
    elif isinstance(data, list):
        raw_files = data
    else:
        print("Error: Unrecognized JSON format. Expected 'files' array.")
        return []

    for f in raw_files:
        dlink = f.get("dlink", "")
        if not dlink:
            continue

        name = f.get("server_filename", f.get("name", "unknown"))
        size = f.get("size", 0)
        human_size = f.get("human_size", "")
        path = f.get("path", "")
        category = f.get("category", 0)

        # Determine folder from path
        folder = str(Path(path).parent) if path else "/"

        # Extract quality URLs for videos
        quality = f.get("quality", {})
        streaming_url = f.get("streaming_url", "")
        caption = f.get("caption", "")

        # Map to TeraFetch format
        files.append({
            "name": name,
            "size": size,
            "size_formatted": human_size,
            "type": _guess_type(name),
            "dlink": dlink,
            "quality": quality if quality else None,
            "streaming_url": streaming_url if streaming_url else None,
            "caption": caption if caption else None,
            "fs_id": f.get("fs_id", 0),
            "thumbnail": f.get("thumb", f.get("icon", "")),
            "folder": folder,
            "category": category,
            "_source": "teraboxdownloader",
        })

    return files


def _guess_type(filename: str) -> str:
    """Guess file type from extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    video_exts = {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "ts"}
    image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
    if ext in video_exts:
        return "video"
    if ext in image_exts:
        return "image"
    return "other"


def merge_with_existing(new_files: list[dict], existing_path: str) -> list[dict]:
    """Merge new files with existing file_list.json (avoid duplicates)."""
    existing = []
    if Path(existing_path).exists():
        with open(existing_path) as f:
            existing = json.load(f)

    # Build set of existing fs_ids
    existing_ids = {f.get("fs_id") for f in existing if f.get("fs_id")}

    # Add new files that aren't already in the list
    added = 0
    for f in new_files:
        fs_id = f.get("fs_id")
        if fs_id and fs_id not in existing_ids:
            existing.append(f)
            existing_ids.add(fs_id)
            added += 1

    print(f"Merged: {len(existing)} total ({added} new)")
    return existing


def main():
    parser = argparse.ArgumentParser(
        description="Convert TeraBoxDownloader API response to TeraFetch format",
        epilog="""
Example:
  # Convert API response to file_list.json
  python convert.py response.json -o downloads/file_list.json

  # Merge with existing file_list.json
  python convert.py response.json -o downloads/file_list.json --merge
        """,
    )
    parser.add_argument("input", help="Path to JSON file with API response")
    parser.add_argument("-o", "--output", default="downloads/file_list.json", help="Output path")
    parser.add_argument("--merge", action="store_true", help="Merge with existing file_list.json")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    with open(args.input) as f:
        data = json.load(f)

    files = convert_teraboxdownloader(data)
    if not files:
        print("Error: No files found in JSON.")
        sys.exit(1)

    print(f"Converted {len(files)} files")

    if args.merge:
        files = merge_with_existing(files, args.output)

    # Save
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(files, f, indent=2, ensure_ascii=False)

    print(f"Saved to {output}")

    # Print summary
    total_size = sum(f.get("size", 0) for f in files)
    print(f"\n  Files: {len(files)}")
    print(f"  Total: {total_size / (1024**3):.2f} GB")


if __name__ == "__main__":
    main()
