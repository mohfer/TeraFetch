"""
services.py - Service layer for business logic.

Services contain pure business logic and orchestrate operations.
They depend on repositories for I/O operations.
"""

from typing import Protocol

from .convert import convert_teraboxdownloader
from .downloader import collect_download_links, download_batch
from .protocols import FileSystem, HttpClient, Logger
from .repositories import ApiRepository, FileListRepository, LinkExportRepository
from .terabox_xyz import fetch_terabox_xyz
from .utils import is_terabox_share_url, validate_url


class ScraperService:
    """Service for scraping file lists from URLs."""

    def __init__(
        self,
        api_repo: ApiRepository,
        file_list_repo: FileListRepository,
        logger: Logger | None = None,
    ):
        self._api_repo = api_repo
        self._file_list_repo = file_list_repo
        self._logger = logger

    def fetch_from_url(self, url: str, output_path: str) -> list[dict]:
        """Fetch file list from URL and save to JSON.

        Args:
            url: TeraBox share URL or cache URL
            output_path: Path to save file list JSON

        Returns:
            List of file records
        """
        if not validate_url(url):
            raise ValueError(f"Invalid URL: {url}")

        # Check if it's a TeraBox share URL
        if is_terabox_share_url(url):
            if self._logger:
                self._logger.info("Detected TeraBox share URL, using teraboxdownloader.xyz")
            files = fetch_terabox_xyz(url)
        else:
            # Cache URL
            if self._logger:
                self._logger.info("Fetching from cache API")
            data = self._api_repo.fetch_cache_data(url)
            files = convert_teraboxdownloader(data)

        if not files:
            raise ValueError("No files found in response")

        # Save to JSON
        self._file_list_repo.save(output_path, files)

        if self._logger:
            self._logger.info(f"Saved {len(files)} files to {output_path}")

        return files

    def load_from_json(self, path: str) -> list[dict]:
        """Load file list from JSON file."""
        if not self._file_list_repo.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        return self._file_list_repo.load(path)


class DownloadService:
    """Service for downloading files."""

    def __init__(self, logger: Logger | None = None):
        self._logger = logger

    def download_files(
        self,
        files: list[dict],
        output_dir: str,
        workers: int = 3,
        quality: str | None = None,
    ) -> dict:
        """Download multiple files concurrently.

        Args:
            files: List of file records
            output_dir: Output directory
            workers: Number of concurrent workers
            quality: Video quality (if downloading streams)

        Returns:
            Results dict with success/failed counts
        """
        if self._logger:
            self._logger.info(f"Starting download of {len(files)} files with {workers} workers")

        results = download_batch(files, output_dir, workers=workers, quality=quality)

        if self._logger:
            self._logger.info(
                f"Download complete: {results['success']} succeeded, {results['failed']} failed"
            )

        return results

    def download_with_retry(
        self,
        files: list[dict],
        output_dir: str,
        workers: int,
        source_url: str | None,
        scraper_service: "ScraperService",
        json_path: str,
        quality: str | None = None,
        max_retries: int = 2,
    ) -> dict:
        """Download files with auto re-scrape on link expiration.

        Args:
            files: List of file records
            output_dir: Output directory
            workers: Number of concurrent workers
            source_url: Source URL for re-scraping
            scraper_service: Scraper service for re-fetching
            json_path: Path to JSON file
            quality: Video quality
            max_retries: Maximum re-scrape attempts

        Returns:
            Results dict with success/failed counts
        """
        for attempt in range(max_retries + 1):
            results = self.download_files(files, output_dir, workers, quality)
            expired = results.get("expired_files", [])

            if not expired or attempt >= max_retries:
                if expired and self._logger:
                    self._logger.warning(f"{len(expired)} files still have expired links")
                return results

            if self._logger:
                self._logger.info(
                    f"{len(expired)} file(s) have expired links. "
                    f"Re-scraping (attempt {attempt+1}/{max_retries})..."
                )

            if not source_url:
                if self._logger:
                    self._logger.error("Cannot re-scrape - no source URL provided")
                return results

            # Re-scrape fresh links
            try:
                fresh = scraper_service.fetch_from_url(source_url, json_path)
                fresh_lookup = {f.get("fs_id"): f for f in fresh if f.get("fs_id")}

                updated = 0
                for i, f in enumerate(files):
                    fs_id = f.get("fs_id")
                    if fs_id and fs_id in fresh_lookup:
                        if f.get("dlink") != fresh_lookup[fs_id].get("dlink"):
                            files[i] = fresh_lookup[fs_id]
                            updated += 1

                if self._logger:
                    self._logger.info(f"Updated {updated} file(s) with fresh links")

            except Exception as e:
                if self._logger:
                    self._logger.error(f"Re-scrape failed: {e}")
                return results

        return results


class ValidationService:
    """Service for validating download links."""

    def __init__(
        self,
        link_export_repo: LinkExportRepository,
        logger: Logger | None = None,
    ):
        self._link_export_repo = link_export_repo
        self._logger = logger

    def export_links(
        self,
        files: list[dict],
        output_path: str,
        failed_output_path: str,
        validate: bool = False,
        validation_workers: int = 3,
    ) -> tuple[int, int]:
        """Export download links to text files.

        Args:
            files: List of file records
            output_path: Path for valid links
            failed_output_path: Path for failed links
            validate: Whether to validate links
            validation_workers: Number of validation workers

        Returns:
            Tuple of (valid_count, failed_count)
        """
        if self._logger:
            self._logger.info(f"Exporting {len(files)} links (validate={validate})")

        # Collect and optionally validate links
        valid_urls, errors = collect_download_links(
            files,
            validate=validate,
            validation_workers=validation_workers,
        )

        # Save valid links
        self._link_export_repo.save_links(output_path, valid_urls)

        # Save failed links if any
        failed_urls = [err.get("url") for err in errors if err.get("url")]
        if failed_urls:
            self._link_export_repo.save_links(failed_output_path, failed_urls)

        if self._logger:
            self._logger.info(
                f"Exported {len(valid_urls)} valid links, {len(failed_urls)} failed links"
            )

        return len(valid_urls), len(failed_urls)
