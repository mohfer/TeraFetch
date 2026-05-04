"""Download files using curl with progress and concurrent support."""

import json
import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_print_lock = threading.Lock()

REFERER = "https://www.teraboxdownloader.xyz/"


def download_one(
    url: str,
    output_path: str | Path,
    file_num: int = 0,
    total: int = 0,
    referer: str = REFERER,
) -> tuple[str, bool, str, str]:
    """Download with curl. Returns (filename, success, message, error_type)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filename = output_path.name
    prefix = f"[{file_num}/{total}]"

    if output_path.exists() and output_path.stat().st_size > 1024:
        with open(output_path, "rb") as f:
            head = f.read(200)
        if b"<html" not in head.lower():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            _safe_print(f"{prefix} [SKIP] {filename} (already {size_mb:.1f} MB)")
            return filename, True, f"already exists ({size_mb:.1f} MB)", ""

    _safe_print(f"{prefix} Starting: {filename}")

    resume = output_path.exists() and output_path.stat().st_size > 0

    cmd = [
        "curl",
        "-L",
        "--progress-bar",
        "--retry", "5",
        "--retry-delay", "3",
        "--retry-max-time", "120",
        "--connect-timeout", "30",
        "--max-time", "7200",
        "-H", f"Referer: {referer}",
        "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "-H", "Accept: */*",
        "-o", str(output_path),
    ]

    if resume:
        cmd.extend(["-C", "-"])

    cmd.append(url)

    try:
        start_time = time.time()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        last_size = output_path.stat().st_size if output_path.exists() else 0
        last_check = start_time
        speed_str = "..."

        for line in proc.stdout:
            line = line.strip()
            now = time.time()
            if now - last_check >= 1.0:
                current_size = output_path.stat().st_size if output_path.exists() else 0
                bytes_delta = current_size - last_size
                if bytes_delta > 0:
                    speed_str = _format_speed(bytes_delta / (now - last_check))
                last_size = current_size
                last_check = now
            if line:
                _safe_print(f"  {prefix} {line} {speed_str}")

        proc.wait()

        if proc.returncode != 0:
            _safe_print(f"{prefix} [FAIL] {filename} - curl exit {proc.returncode}")
            return filename, False, f"curl exit {proc.returncode}", "other"

    except subprocess.TimeoutExpired:
        proc.kill()
        _safe_print(f"{prefix} [FAIL] {filename} - timeout")
        return filename, False, "timeout", "timeout"
    except Exception as e:
        _safe_print(f"{prefix} [FAIL] {filename} - {e}")
        return filename, False, str(e), "other"

    if not output_path.exists() or output_path.stat().st_size < 1024:
        if output_path.exists():
            with open(output_path, "rb") as f:
                head = f.read(500)
            try:
                import json as j
                err = j.loads(head)
                if "error" in err or "message" in err:
                    _safe_print(f"{prefix} [FAIL] {filename} - {err.get('error', err.get('message', 'API error'))}")
                    return filename, False, str(err.get("error", err.get("message"))), "other"
            except Exception:
                pass
        _safe_print(f"{prefix} [FAIL] {filename} - file too small ({output_path.stat().st_size if output_path.exists() else 0} bytes)")
        return filename, False, "file too small or missing", "other"

    with open(output_path, "rb") as f:
        head = f.read(500)
    head_lower = head.lower()

    if b'"error"' in head_lower and b"link expired" in head_lower:
        output_path.unlink()
        _safe_print(f"{prefix} [FAIL] {filename} - link expired")
        return filename, False, "link expired", "expired"

    if b"<html" in head_lower or b"<!doctype" in head_lower:
        output_path.unlink()
        _safe_print(f"{prefix} [FAIL] {filename} - got HTML instead of file")
        return filename, False, "got HTML instead of file", "html"

    elapsed = time.time() - start_time
    size_mb = output_path.stat().st_size / (1024 * 1024)
    avg_speed = size_mb / elapsed if elapsed > 0 else 0

    _safe_print(
        f"{prefix} [OK]   {filename} "
        f"({size_mb:.1f} MB, {avg_speed:.1f} MB/s, {elapsed:.0f}s)"
    )
    return filename, True, f"{size_mb:.1f} MB in {elapsed:.0f}s ({avg_speed:.1f} MB/s)", ""


def download_one_stream(
    url: str,
    output_path: str | Path,
    file_num: int = 0,
    total: int = 0,
    quality: str = "best",
) -> tuple[str, bool, str, str]:
    """Download m3u8 stream using yt-dlp."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filename = output_path.name
    prefix = f"[{file_num}/{total}]"

    if output_path.exists() and output_path.stat().st_size > 1024 * 1024:
        size_mb = output_path.stat().st_size / (1024 * 1024)
        _safe_print(f"{prefix} [SKIP] {filename} (already {size_mb:.1f} MB)")
        return filename, True, f"already exists ({size_mb:.1f} MB)", ""

    _safe_print(f"{prefix} Starting (stream {quality}): {filename}")

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--referer", REFERER,
        "-f", "best",
        "--no-live-from-start",
        "-o", str(output_path),
        url,
    ]

    start_time = time.time()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            line = line.strip()
            if line:
                _safe_print(f"  {prefix} {line}")

        proc.wait()

        if proc.returncode != 0:
            _safe_print(f"{prefix} [FAIL] {filename} - yt-dlp exit {proc.returncode}")
            return filename, False, f"yt-dlp exit {proc.returncode}", "other"

    except subprocess.TimeoutExpired:
        _safe_print(f"{prefix} [FAIL] {filename} - timeout")
        return filename, False, "timeout", "timeout"
    except FileNotFoundError:
        _safe_print(f"{prefix} [FAIL] {filename} - yt-dlp not found, install: pip install yt-dlp")
        return filename, False, "yt-dlp not installed", "other"

    actual = None
    for ext in [".mp4", ".mkv", ".webm", ".ts"]:
        candidate = output_path.with_suffix(ext)
        if candidate.exists() and candidate.stat().st_size > 1024:
            actual = candidate
            break
    if not actual and output_path.exists() and output_path.stat().st_size > 1024:
        actual = output_path

    if not actual:
        _safe_print(f"{prefix} [FAIL] {filename} - output file not found")
        return filename, False, "output file not found", "other"

    elapsed = time.time() - start_time
    size_mb = actual.stat().st_size / (1024 * 1024)
    avg_speed = size_mb / elapsed if elapsed > 0 else 0

    _safe_print(
        f"{prefix} [OK]   {actual.name} "
        f"({size_mb:.1f} MB, {avg_speed:.1f} MB/s, {elapsed:.0f}s)"
    )
    return filename, True, f"{size_mb:.1f} MB in {elapsed:.0f}s ({avg_speed:.1f} MB/s)", ""


def download_batch(
    files: list[dict],
    output_dir: str | Path,
    workers: int = 3,
    quality: str | None = None,
) -> dict:
    """Download files concurrently. If quality is set, uses yt-dlp for m3u8 streams."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    use_stream = quality is not None

    tasks = []
    for f in files:
        file_json = json.dumps(f, sort_keys=True)

        if use_stream:
            url = _get_stream_url(f, quality)
            if not url:
                url, _ = _get_download_url(file_json)
                use_stream = False
        else:
            url, _ = _get_download_url(file_json)

        if not url:
            continue

        if "teradl.kingx.dev" in url or "teraboxdownloader" in url:
            ref = "https://www.teraboxdownloader.xyz/"
        else:
            ref = REFERER

        name = _clean_filename(f.get("name", "unknown"), is_zip=False)
        tasks.append((url, output_dir / name, f, use_stream, ref))

    if not tasks:
        return {"success": 0, "failed": 0, "expired_files": [], "details": []}

    total = len(tasks)
    results = {"success": 0, "failed": 0, "expired_files": [], "details": []}

    mode = f"stream {quality}" if use_stream else "direct"
    print(f"Downloading: {total} files | {workers} workers | Mode: {mode}")
    print(f"Output:      {output_dir.resolve()}\n")

    batch_start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for i, (url, path, info, is_stream, ref) in enumerate(tasks, 1):
            if is_stream:
                future = executor.submit(download_one_stream, url, path, i, total, quality)
            else:
                future = executor.submit(download_one, url, path, i, total, ref)
            futures[future] = info

        for future in as_completed(futures):
            file_info = futures[future]
            filename, ok, msg, err_type = future.result()
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["details"].append({"file": filename, "error": msg})
                if err_type == "expired":
                    results["expired_files"].append(file_info)

    batch_elapsed = time.time() - batch_start
    results["elapsed"] = batch_elapsed

    return results


def export_download_links(
    files: list[dict],
    path: str | Path,
    server: str = "zip",
) -> int:
    """Export direct download URLs to file."""
    urls = []
    for file_info in files:
        file_json = json.dumps(file_info, sort_keys=True)
        url, _ = _get_download_url(file_json, server)
        if url:
            urls.append(url)

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(urls))
        if urls:
            f.write("\n")

    return len(urls)


def collect_download_links(
    files: list[dict],
    validate: bool = False,
    log_file: str = "downloads/validation.log",
    validation_workers: int = 3,
) -> tuple[list[str], list[dict]]:
    urls = []
    errors = []
    total = len(files)

    if validate:
        log_path = Path(log_file)
        if log_path.exists():
            log_path.unlink()

        _safe_print(f"Validation log: {log_file}")
        _safe_print(f"Validating {total} links with {validation_workers} workers...\n")

    tasks = []
    for index, file_info in enumerate(files, 1):
        file_json = json.dumps(file_info, sort_keys=True)
        url, _ = _get_download_url(file_json)
        if not url:
            errors.append({"file": file_info.get("name", "unknown"), "error": "missing download URL"})
            continue
        tasks.append((index, url, file_info))

    if not validate:
        return [url for _, url, _ in tasks], errors

    validated_urls = []

    with ThreadPoolExecutor(max_workers=validation_workers) as executor:
        futures = {}
        for index, url, file_info in tasks:
            future = executor.submit(_validate_download_url, url, 5, log_file)
            futures[future] = (index, url, file_info)

        for future in as_completed(futures):
            index, url, file_info = futures[future]
            ok, message = future.result()
            status = "OK" if ok else "SKIP"
            _safe_print(f"[{index}/{total}] [{status}] {file_info.get('name', 'unknown')} - {message}")

            if ok:
                validated_urls.append((index, url))
            else:
                errors.append({"file": file_info.get("name", "unknown"), "error": message, "url": url})

    validated_urls.sort(key=lambda x: x[0])
    urls = [url for _, url in validated_urls]

    return urls, errors


def save_links(urls: list[str], path: str | Path) -> None:
    """Save URLs to TXT file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(urls))
        if urls:
            f.write("\n")


def _validate_download_url(url: str, max_retries: int = 5, log_file: str = "validation.log") -> tuple[bool, str]:
    """Probe URL and reject JSON/HTML responses. Retries on 5xx errors."""
    import requests
    from datetime import datetime

    referer = "https://www.teraboxdownloader.xyz/" if "teradl.kingx.dev" in url or "teraboxdownloader" in url else REFERER
    headers = {
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")

    log(f"\n{'='*80}")
    log(f"Validating: {url}")

    session = requests.Session()
    session.trust_env = False

    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    last_error = None
    validation_start = time.time()

    try:
        for attempt in range(max_retries):
            try:
                log(f"Attempt {attempt + 1}/{max_retries}")
                response = session.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)

                log(f"Status: {response.status_code}")
                log(f"Headers: {dict(response.headers)}")

                chunk = next(response.iter_content(chunk_size=512), b"")
                content_type = response.headers.get("content-type", "").lower()
                text = chunk.decode("utf-8", errors="ignore").strip()

                log(f"Content-Type: {content_type}")
                log(f"First 200 chars: {text[:200]}")

                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    log(f"Server error: {last_error}")
                    response.close()
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt
                        log(f"Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        log(f"FAIL: {last_error} (after {max_retries} retries)")
                        return False, last_error

                if response.status_code >= 400:
                    log(f"FAIL: HTTP {response.status_code}")
                    response.close()
                    return False, f"HTTP {response.status_code}"

                if "application/json" in content_type or text.startswith("{"):
                    try:
                        data = json.loads(text)
                        error_msg = data.get("error") or data.get("message") or "JSON error response"
                        log(f"FAIL: JSON error - {error_msg}")
                        response.close()
                        return False, error_msg
                    except json.JSONDecodeError:
                        log(f"FAIL: Invalid JSON response")
                        response.close()
                        return False, "JSON error response"

                if "text/html" in content_type or "<html" in text.lower() or "<!doctype" in text.lower():
                    log(f"FAIL: HTML response")
                    response.close()
                    return False, "HTML response"

                validation_time = time.time() - validation_start
                log(f"SUCCESS: Valid download link (validated in {validation_time:.2f}s)")
                response.close()
                return True, "valid"

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as exc:
                last_error = str(exc)
                log(f"ERROR (attempt {attempt + 1}): {last_error}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    log(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
            except Exception as exc:
                log(f"UNEXPECTED ERROR: {exc}")
                return False, str(exc)

        log(f"FAIL: Failed after {max_retries} retries - {last_error}")
        return False, f"failed after {max_retries} retries: {last_error}"
    finally:
        session.close()


def save_json(files: list[dict], path: str) -> None:
    """Save file list to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(files, f, indent=2, ensure_ascii=False)


def _safe_print(msg: str):
    with _print_lock:
        print(msg, flush=True)


def _format_speed(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / (1024*1024):.1f} MB/s"
    elif bps >= 1024:
        return f"{bps / 1024:.0f} KB/s"
    return f"{bps:.0f} B/s"


@lru_cache(maxsize=1024)
def _get_download_url(file_info_json: str, server: str = "zip") -> tuple[str | None, bool]:
    """Extract dlink from file_info. Returns (url, is_zip)."""
    file_info = json.loads(file_info_json)
    url = file_info.get("dlink")
    return url, False


def _get_stream_url(file_info: dict, quality: str = "best") -> str | None:
    """Get m3u8 URL for specified quality."""
    streams = file_info.get("quality")
    if not streams or not isinstance(streams, dict):
        return None

    if quality == "best":
        priority = ["1080p", "720p", "480p", "360p"]
        for q in priority:
            if q in streams:
                return streams[q]
        return next(iter(streams.values()), None)

    return streams.get(quality)


def _clean_filename(name: str, is_zip: bool = False) -> str:
    name = name.strip()
    if not name or name.startswith("⚠️"):
        name = "unknown_file"
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '_')
    if is_zip:
        base = name.rsplit(".", 1)[0] if "." in name else name
        name = base + ".zip"
    return name
