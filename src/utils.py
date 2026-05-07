"""utils.py - Helper functions."""

import logging
import re
from urllib.parse import urlparse


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def validate_url(url: str) -> bool:
    """Check if the URL is syntactically valid."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_terabox_share_url(url: str) -> bool:
    """Check if URL is a TeraBox share link (not cache URL)."""
    patterns = [
        r"https?://(?:www\.)?1024tera\.com/sharing/link\?surl=",
        r"https?://(?:www\.)?1024terabox\.com/s/",
        r"https?://(?:www\.)?terabox\.app/sharing/link\?surl=",
        r"https?://(?:www\.)?terabox\.com/(?:s/|sharing/link\?surl=|wap/share/filelist\?surl=)",
        r"https?://(?:www\.)?teraboxapp\.com/(?:s/|sharing/link\?surl=)",
    ]
    return any(re.match(p, url) for p in patterns)
