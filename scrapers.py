"""Unified scraping module for TeraBox sources."""

import asyncio
import json
from pathlib import Path
from urllib.parse import quote

import requests
from playwright.async_api import async_playwright


class TeraBoxXYZDownloader:

    def __init__(self):
        self.base_url = "https://teradl.kingx.dev"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.teraboxdownloader.xyz/",
            "Origin": "https://www.teraboxdownloader.xyz"
        }

    async def fetch_files(self, terabox_url: str) -> dict:
        api_response = None
        error_message = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.headers["User-Agent"]
            )
            page = await context.new_page()

            async def handle_response(response):
                nonlocal api_response, error_message
                if 'teradl.kingx.dev/gettask' in response.url:
                    try:
                        payload = await response.json()
                        if 'result' in payload and payload['result']:
                            api_response = payload['result']
                            return
                        for key in ('message', 'msg', 'error', 'detail', 'reason'):
                            value = payload.get(key)
                            if isinstance(value, str) and value.strip():
                                error_message = value.strip()
                                return
                    except:
                        pass

            page.on("response", handle_response)

            encoded_url = quote(terabox_url, safe='')
            page_url = f"https://www.teraboxdownloader.xyz/p/fullscreen.html?q={encoded_url}"

            await page.goto(page_url, wait_until="networkidle", timeout=60000)

            for _ in range(15):
                if api_response:
                    break
                await asyncio.sleep(1)

            if not api_response and not error_message:
                try:
                    body_text = await page.locator("body").inner_text()
                except Exception:
                    body_text = ""

                for message in (
                    "Short URL not found in the provided link.",
                    "This link has been blocked according to the local laws, regulations, or policies",
                ):
                    if message in body_text:
                        error_message = message
                        break

            await browser.close()

        if error_message:
            return {"error": error_message}

        return api_response

    def get_files(self, terabox_url: str) -> dict:
        return asyncio.run(self.fetch_files(terabox_url))


def fetch_terabox_share(terabox_url: str) -> list[dict]:
    downloader = TeraBoxXYZDownloader()
    api_data = downloader.get_files(terabox_url)

    if isinstance(api_data, dict) and api_data.get("error"):
        raise ValueError(api_data["error"])

    if not api_data or 'files' not in api_data:
        return []

    normalized = []
    for file_info in api_data['files']:
        normalized.append({
            'name': file_info.get('server_filename', 'Unknown'),
            'fs_id': file_info.get('fs_id'),
            'size': file_info.get('size', 0),
            'size_formatted': file_info.get('human_size', 'Unknown'),
            'dlink': file_info.get('dlink', ''),
            'streaming_url': file_info.get('streaming_url', ''),
            'quality': file_info.get('quality', {}),
            'duration': file_info.get('duration_formated', ''),
            'thumb': file_info.get('thumb', ''),
            'path': file_info.get('path', ''),
            'category': file_info.get('category', 0)
        })

    return normalized


def fetch_from_cache(cache_url: str) -> list[dict]:
    resp = requests.get(cache_url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    return convert_teraboxdownloader(payload)


def convert_teraboxdownloader(payload: dict) -> list[dict]:
    files = []

    if "files" in payload:
        raw_files = payload["files"]
    elif isinstance(payload, list):
        raw_files = payload
    else:
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

        folder = str(Path(path).parent) if path else "/"

        quality = f.get("quality", {})
        streaming_url = f.get("streaming_url", "")
        caption = f.get("caption", "")

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
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    video_exts = {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "ts"}
    image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}
    if ext in video_exts:
        return "video"
    if ext in image_exts:
        return "image"
    return "other"


def fetch_files(url: str) -> list[dict]:
    from src.utils import validate_url, is_terabox_share_url

    if not validate_url(url):
        raise ValueError(f"Invalid URL: {url}")

    if is_terabox_share_url(url):
        files = fetch_terabox_share(url)
    else:
        files = fetch_from_cache(url)

    if not files:
        raise ValueError("No files found in response")

    return files


def save_file_list(files: list[dict], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(files, f, indent=2, ensure_ascii=False)


def load_file_list(path: str) -> list[dict]:
    if not Path(path).exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)
