"""
repositories.py - Repository layer for I/O operations.

Repositories handle all external I/O: file system, HTTP requests, database, etc.
They are injected into services for testability.
"""

import json
from pathlib import Path
from typing import Any

import requests

from .protocols import FileSystem, HttpClient


class FileSystemRepository:
    """Repository for file system operations."""

    def read_json(self, path: str) -> list[dict]:
        """Read JSON file and return parsed data."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: str, data: list[dict]) -> None:
        """Write data to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def write_text(self, path: str, content: str) -> None:
        """Write text content to file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def exists(self, path: str) -> bool:
        """Check if file exists."""
        return Path(path).exists()

    def mkdir(self, path: str, parents: bool = True, exist_ok: bool = True) -> None:
        """Create directory."""
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)


class HttpRepository:
    """Repository for HTTP operations."""

    def __init__(self, session: requests.Session | None = None):
        self._session = session or requests.Session()

    def get(self, url: str, timeout: int = 30, **kwargs) -> requests.Response:
        """Make GET request and return response."""
        return self._session.get(url, timeout=timeout, **kwargs)

    def close(self) -> None:
        """Close HTTP session."""
        self._session.close()


class ApiRepository:
    """Repository for TeraBox API operations."""

    def __init__(self, http_client: HttpClient):
        self._http = http_client

    def fetch_cache_data(self, url: str) -> dict:
        """Fetch data from TeraBox cache API."""
        response = self._http.get(url, timeout=30)
        response.raise_for_status()
        return response.json()


class FileListRepository:
    """Repository for file list storage."""

    def __init__(self, fs: FileSystem):
        self._fs = fs

    def save(self, path: str, files: list[dict]) -> None:
        """Save file list to JSON."""
        self._fs.write_json(path, files)

    def load(self, path: str) -> list[dict]:
        """Load file list from JSON."""
        return self._fs.read_json(path)

    def exists(self, path: str) -> bool:
        """Check if file list exists."""
        return self._fs.exists(path)


class LinkExportRepository:
    """Repository for exporting download links."""

    def __init__(self, fs: FileSystem):
        self._fs = fs

    def save_links(self, path: str, urls: list[str]) -> None:
        """Save URLs to text file, one per line."""
        content = "\n".join(urls)
        if urls:
            content += "\n"
        self._fs.write_text(path, content)
