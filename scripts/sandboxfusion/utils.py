import asyncio
import time
from collections import Counter
from statistics import mean, median

import aiohttp
from rich import box
from rich.panel import Panel
from rich.table import Table

from scripts.pbar import get_progress_bar

API_BASE_URL = "http://localhost:9000/submit"
DEFAULT_WORKERS = 56


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
    semaphore = asyncio.Semaphore(DEFAULT_WORKERS)

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


def print_stress_test_summary(results, total_time, total_samples, console):
    r"""Generate and print a comprehensive stress test summary."""
    # Status distribution
    results = [result for _, result in results]
    status_counts = Counter(result.get("accepted") for result in results)
    accepted_count = status_counts.get(True, 0)
    success_rate = (accepted_count / len(results)) * 100 if results else 0

    # Performance metrics
    latencies = [result.get("request_latency", 0) for result in results]
    execution_times = [
        max(
            x.get("exec_info", {}).get("run_result", {}).get("execution_time", 0)
            for x in result.get("tests", [])
        )
        for result in results
        if result.get("tests") is not None
    ]
    test_lengths = [len(result.get("tests", [])) for result in results]
    test_length_counts = Counter(test_lengths)
    test_length_counts = sorted(test_length_counts.items())

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
    if test_length_counts:
        summary_table.add_row("Avg Test Length", f"{mean(test_lengths):.2f}")
        summary_table.add_row("Median Test Length", f"{median(test_lengths):.2f}")
        summary_table.add_row(
            "Min/Max Test Length",
            f"{min(test_lengths)}/{max(test_lengths)}",
        )

    # Create status distribution table
    status_table = Table(title="Status Distribution", box=box.ROUNDED)
    status_table.add_column("Status", style="bright_cyan")
    status_table.add_column("Count", style="bright_white")
    status_table.add_column("Percentage", style="bright_white")

    for status, count in sorted(status_counts.items()):
        percentage = (count / len(results)) * 100 if results else 0
        status_style = "bright_green" if status else "bright_red"
        status_str = "Accepted" if status else "Failed"
        status_table.add_row(
            f"[{status_style}]{status_str}[/{status_style}]", str(count), f"{percentage:.2f}%"
        )

    # Create performance percentiles table
    if latencies:
        perf_table = Table(title="Performance Percentiles", box=box.ROUNDED)
        perf_table.add_column("Percentile", style="bright_cyan")
        perf_table.add_column("Request Latency (seconds)", style="bright_white")
        if execution_times:
            perf_table.add_column("Execution Time (seconds)", style="bright_white")
        if test_length_counts:
            perf_table.add_column("Test Length", style="bright_white")

        sorted_latencies = sorted(latencies)
        sorted_exec_times = sorted(execution_times) if execution_times else []
        sorted_test_lengths = sorted(test_lengths) if test_lengths else []
        for p in [50, 75, 90, 95, 99]:
            idx = int(len(sorted_latencies) * (p / 100))
            lat_p = sorted_latencies[idx] if idx < len(sorted_latencies) else 0

            row = [f"P{p}", f"{lat_p:.2f}"]

            if execution_times:
                idx = int(len(sorted_exec_times) * (p / 100))
                exec_p = sorted_exec_times[idx] if idx < len(sorted_exec_times) else 0
                row.append(f"{exec_p:.2f}")
            if test_length_counts:
                idx = int(len(sorted_test_lengths) * (p / 100))
                test_length_p = sorted_test_lengths[idx] if idx < len(sorted_test_lengths) else 0
                row.append(f"{test_length_p}")

            perf_table.add_row(*row)

    # Print all tables
    console.print("\n")
    console.print(Panel.fit("🚀 MINI-JUDGE BENCHMARK RESULTS 🚀", style="bright_green"))
    console.print(summary_table)
    console.print(status_table)
    if latencies:
        console.print(perf_table)
