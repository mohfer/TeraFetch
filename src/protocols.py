"""
protocols.py - Protocol definitions for dependency injection.

Protocols define interfaces that allow for flexible implementations
and easy testing with mocks/fakes.
"""

from typing import Protocol, Any


class HttpClient(Protocol):
    """Protocol for HTTP client operations."""

    def get(self, url: str, timeout: int = 30, **kwargs) -> Any:
        """Make GET request and return response."""
        ...

    def raise_for_status(self) -> None:
        """Raise exception for HTTP errors."""
        ...


class FileSystem(Protocol):
    """Protocol for file system operations."""

    def read_json(self, path: str) -> list[dict]:
        """Read JSON file and return parsed data."""
        ...

    def write_json(self, path: str, data: list[dict]) -> None:
        """Write data to JSON file."""
        ...

    def write_text(self, path: str, content: str) -> None:
        """Write text content to file."""
        ...

    def exists(self, path: str) -> bool:
        """Check if file exists."""
        ...

    def mkdir(self, path: str, parents: bool = True, exist_ok: bool = True) -> None:
        """Create directory."""
        ...


class Logger(Protocol):
    """Protocol for logging operations."""

    def info(self, msg: str, **kwargs) -> None:
        """Log info message."""
        ...

    def error(self, msg: str, **kwargs) -> None:
        """Log error message."""
        ...

    def warning(self, msg: str, **kwargs) -> None:
        """Log warning message."""
        ...

    def debug(self, msg: str, **kwargs) -> None:
        """Log debug message."""
        ...


class Downloader(Protocol):
    """Protocol for download operations."""

    def download(
        self,
        url: str,
        output_path: str,
        referer: str = "",
    ) -> tuple[bool, str]:
        """Download file from URL.

        Returns (success, message).
        """
        ...


class Validator(Protocol):
    """Protocol for URL validation operations."""

    def validate(self, url: str, max_retries: int = 5) -> tuple[bool, str]:
        """Validate URL accessibility.

        Returns (is_valid, message).
        """
        ...


class Scraper(Protocol):
    """Protocol for web scraping operations."""

    def fetch_files(self, url: str) -> list[dict]:
        """Fetch file list from URL.

        Returns list of file records.
        """
        ...


class MetricsCollector(Protocol):
    """Protocol for metrics collection."""

    def log_metric(self, metric: dict) -> None:
        """Log performance metric."""
        ...

    def log_operation(self, name: str, elapsed: float, **kwargs) -> None:
        """Log operation timing."""
        ...
