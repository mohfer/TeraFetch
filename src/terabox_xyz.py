"""
TeraBox XYZ Downloader Module
Handles fetching download links from teraboxdownloader.xyz using Playwright
"""

import asyncio
from urllib.parse import quote
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
        """
        Fetch file information from TeraBox URL using Playwright

        Args:
            terabox_url: TeraBox share URL (e.g., https://www.1024tera.com/sharing/link?surl=XXX)

        Returns:
            dict: Result data containing files list
        """
        result_data = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.headers["User-Agent"]
            )
            page = await context.new_page()

            # Capture the gettask response
            async def handle_response(response):
                nonlocal result_data
                if 'teradl.kingx.dev/gettask' in response.url:
                    try:
                        data = await response.json()
                        if 'result' in data and data['result']:
                            result_data = data['result']
                    except:
                        pass

            page.on("response", handle_response)

            # Navigate to the page
            encoded_url = quote(terabox_url, safe='')
            page_url = f"https://www.teraboxdownloader.xyz/p/fullscreen.html?q={encoded_url}"

            await page.goto(page_url, wait_until="networkidle", timeout=60000)

            # Wait for result (max 15 seconds)
            for _ in range(15):
                if result_data:
                    break
                await asyncio.sleep(1)

            await browser.close()

        return result_data

    def get_files(self, terabox_url: str) -> dict:
        """
        Synchronous wrapper for fetch_files

        Args:
            terabox_url: TeraBox share URL

        Returns:
            dict: Result data containing files list
        """
        return asyncio.run(self.fetch_files(terabox_url))


def fetch_terabox_xyz(terabox_url: str) -> list[dict]:
    """
    Fetch and normalize files from teraboxdownloader.xyz

    Args:
        terabox_url: TeraBox share URL

    Returns:
        list[dict]: Normalized file list compatible with main.py format
    """
    downloader = TeraBoxXYZDownloader()
    result = downloader.get_files(terabox_url)

    if not result or 'files' not in result:
        return []

    # Normalize to match the expected format
    normalized = []
    for file_info in result['files']:
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
