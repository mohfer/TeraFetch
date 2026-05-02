"""
performance.py - Performance monitoring and optimization utilities.
"""

import functools
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def timing_decorator(func: Callable) -> Callable:
    """Decorator to measure and log execution time of functions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        # Log to metrics file
        log_metric({
            "function": func.__name__,
            "execution_time": elapsed,
            "timestamp": datetime.now().isoformat()
        })

        return result
    return wrapper


def log_metric(metric: dict, log_file: str = "downloads/metrics.jsonl") -> None:
    """Log performance metrics to JSONL file."""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(metric) + "\n")


class PerformanceMonitor:
    """Context manager for monitoring performance of code blocks."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        elapsed = self.end_time - self.start_time

        log_metric({
            "operation": self.name,
            "execution_time": elapsed,
            "timestamp": datetime.now().isoformat(),
            "success": exc_type is None
        })

        return False


def batch_timer(operations: list[tuple[str, Callable]]) -> dict[str, float]:
    """Time multiple operations and return results."""
    results = {}

    for name, func in operations:
        start = time.time()
        func()
        elapsed = time.time() - start
        results[name] = elapsed

        log_metric({
            "batch_operation": name,
            "execution_time": elapsed,
            "timestamp": datetime.now().isoformat()
        })

    return results
