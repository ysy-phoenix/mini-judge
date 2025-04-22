import ast
import asyncio
import json
import math
import os
import re
import time
import warnings
from collections import Counter
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any

import aiohttp
from rich import box
from rich.panel import Panel
from rich.table import Table

from scripts.pbar import get_progress_bar

DEFAULT_TIME_LIMIT = 30  # seconds
DEFAULT_MEMORY_LIMIT = 4 * 1024  # MB
MIN_MEMORY_LIMIT = 128  # MB
API_BASE_URL = "http://localhost:8000/api/v1/judge"
EMPTY_TEST_CASES = [
    {"input": "", "expected": ""},
]
BLOCK_LIBS = [
    "fake-useragent",
    "keras",
    "socket",
    "torch",
    "scipy",
    "sklearn",
    "cv2",
    "scipy",
    "imageio",
    "sphinx-pyproject",
    "xgboost",
    "tweepy",
    "flask",
    "matplotlib",
    "pillow",
    "seaborn",
    "smtpd",
]

warnings.filterwarnings("ignore", category=SyntaxWarning)


@dataclass
class Submission:
    """Represents a code submission to be evaluated."""

    code: str
    language: str = "python"
    mode: str = "acm"
    test_cases: list[dict[str, Any]] = field(default_factory=list)
    time_limit: float = DEFAULT_TIME_LIMIT
    memory_limit: int = DEFAULT_MEMORY_LIMIT
    entry_point: str | None = None
    security_check: bool = False


def check_code_with_ast(code):
    try:
        ast.parse(code)
        compile(code, "<string>", "exec")
        if "eval(" in code or "exec(" in code:  # Filter out unsafe code
            return False
        for lib in BLOCK_LIBS:  # Filter out unsafe libraries
            if lib in code:
                return False
        return True
    except SyntaxError:
        return False


def extract_time_limit(time_limit: str | None) -> int:
    if time_limit is None:
        return DEFAULT_TIME_LIMIT
    assert "second" in time_limit
    numbers = re.findall(r"\d+\.?\d*", time_limit)
    if numbers:
        return math.ceil(max(float(num) for num in numbers)) + 10
    return DEFAULT_TIME_LIMIT


def extract_memory_limit(memory_limit: str | None) -> int:
    if memory_limit is None:
        return DEFAULT_MEMORY_LIMIT
    assert "bytes" in memory_limit or "megabytes" in memory_limit
    number = re.search(r"\d+\.?\d*", memory_limit)
    if number:
        value = float(number.group())
        if "bytes" in memory_limit:
            value /= 1024 * 1024
        return max(MIN_MEMORY_LIMIT, math.ceil(value))
    return DEFAULT_MEMORY_LIMIT


CODE_PATTERN = re.compile(r"```(?:\w+)?\n(.*?)\n```", re.DOTALL)


def extract_code(code: str) -> list[str]:
    if "```python" in code:
        code_blocks = CODE_PATTERN.findall(code)
        return "\n".join(code_blocks).strip()
    else:
        return code.strip()


async def judge(id: str, submission: dict) -> dict:
    start_time = time.time()
    async with aiohttp.ClientSession() as session:
        async with session.post(API_BASE_URL, json=submission) as response:
            result = await response.json()
    end_time = time.time()
    # Add request latency to the result
    result["request_latency"] = end_time - start_time  # seconds
    return id, result


async def process_all_submissions(submissions: dict):
    progress = get_progress_bar()
    tasks = []
    semaphore = asyncio.Semaphore(os.cpu_count())

    async def limited_judge(id, submission):
        async with semaphore:
            return await judge(id, submission)

    with progress:
        sub = progress.add_task("[cyan]Processing submissions...", total=len(submissions))
        for id, submission in submissions.items():
            task = asyncio.create_task(limited_judge(id, submission))
            tasks.append(task)
        results = []
        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)
            progress.update(sub, advance=1)
    return results


def dump_failed_result(results: dict, submissions: dict, file_path: str):
    with open(file_path, "w") as f:
        for id, result in results:
            if result.get("status") == "accepted":
                continue
            submission = submissions[id]
            if isinstance(submission, Submission):
                submission = submission.__dict__
            f.write(f"Submission for {id}:\n")
            f.write(f"{submission['code']}\n")
            f.write(f"time_limit: {submission['time_limit']}\n")
            f.write(f"memory_limit: {submission['memory_limit']}\n")
            f.write(f"Result for {id}:\n")
            f.write(json.dumps(result, indent=4))
            f.write("\n")


def print_stress_test_summary(results, total_time, total_samples, console):
    r"""Generate and print a comprehensive stress test summary."""
    # Status distribution
    results = [result for _, result in results]
    status_counts = Counter(result.get("status") for result in results)
    accepted_count = status_counts.get("accepted", 0)
    success_rate = (accepted_count / len(results)) * 100 if results else 0

    # Performance metrics
    latencies = [result.get("request_latency", 0) for result in results]
    execution_times = [
        result.get("execution_time", 0)
        for result in results
        if result.get("execution_time") is not None
    ]
    memory_usages = [
        result.get("memory_usage", 0)
        for result in results
        if result.get("memory_usage") is not None
    ]

    # Calculate throughput
    throughput = len(results) / total_time if total_time > 0 else 0

    # Create summary table
    summary_table = Table(title="Stress Test Summary", box=box.ROUNDED)
    summary_table.add_column("Metric", style="bright_cyan")
    summary_table.add_column("Value", style="bright_white")

    summary_table.add_row("Total Samples", str(total_samples))
    summary_table.add_row("Processed Samples", str(len(results)))
    summary_table.add_row("Success Rate", f"{success_rate:.2f}%")
    summary_table.add_row("Total Time", f"{total_time:.2f} seconds")
    summary_table.add_row("Throughput", f"{throughput:.2f} requests/second")

    if latencies:
        summary_table.add_row("Avg Request Latency", f"{mean(latencies):.2f} seconds")
        summary_table.add_row("Median Request Latency", f"{median(latencies):.2f} seconds")
        summary_table.add_row(
            "Min/Max Request Latency", f"{min(latencies):.2f}/{max(latencies):.2f} seconds"
        )

    if execution_times:
        summary_table.add_row("Avg Execution Time", f"{mean(execution_times):.2f} seconds")
        summary_table.add_row("Median Execution Time", f"{median(execution_times):.2f} seconds")
        summary_table.add_row(
            "Min/Max Execution Time",
            f"{min(execution_times):.2f}/{max(execution_times):.2f} seconds",
        )

    if memory_usages:
        summary_table.add_row("Avg Memory Usage", f"{mean(memory_usages):.2f} MB")
        summary_table.add_row("Median Memory Usage", f"{median(memory_usages):.2f} MB")
        summary_table.add_row(
            "Min/Max Memory Usage", f"{min(memory_usages):.2f}/{max(memory_usages):.2f} MB"
        )

    # Create status distribution table
    status_table = Table(title="Status Distribution", box=box.ROUNDED)
    status_table.add_column("Status", style="bright_cyan")
    status_table.add_column("Count", style="bright_white")
    status_table.add_column("Percentage", style="bright_white")

    for status, count in sorted(status_counts.items()):
        percentage = (count / len(results)) * 100 if results else 0
        status_style = "bright_green" if status == "accepted" else "bright_red"
        status_table.add_row(
            f"[{status_style}]{status}[/{status_style}]", str(count), f"{percentage:.2f}%"
        )

    # Create performance percentiles table
    if latencies:
        perf_table = Table(title="Performance Percentiles", box=box.ROUNDED)
        perf_table.add_column("Percentile", style="bright_cyan")
        perf_table.add_column("Request Latency (seconds)", style="bright_white")
        if execution_times:
            perf_table.add_column("Execution Time (seconds)", style="bright_white")
        if memory_usages:
            perf_table.add_column("Memory Usage (MB)", style="bright_white")

        sorted_latencies = sorted(latencies)
        sorted_exec_times = sorted(execution_times) if execution_times else []
        sorted_memory = sorted(memory_usages) if memory_usages else []

        for p in [50, 75, 90, 95, 99]:
            idx = int(len(sorted_latencies) * (p / 100))
            lat_p = sorted_latencies[idx] if idx < len(sorted_latencies) else 0

            row = [f"P{p}", f"{lat_p:.2f}"]

            if execution_times:
                idx = int(len(sorted_exec_times) * (p / 100))
                exec_p = sorted_exec_times[idx] if idx < len(sorted_exec_times) else 0
                row.append(f"{exec_p:.2f}")

            if memory_usages:
                idx = int(len(sorted_memory) * (p / 100))
                mem_p = sorted_memory[idx] if idx < len(sorted_memory) else 0
                row.append(f"{mem_p:.2f}")

            perf_table.add_row(*row)

    # Print all tables
    console.print("\n")
    console.print(Panel.fit("🚀 MINI-JUDGE BENCHMARK RESULTS 🚀", style="bright_green"))
    console.print(summary_table)
    console.print(status_table)
    if latencies:
        console.print(perf_table)
