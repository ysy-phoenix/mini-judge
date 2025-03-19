import ast
import json
import math
import re
import time
from collections import Counter
from multiprocessing import Pool
from statistics import mean, median
from typing import Any

import requests
from datasets import load_dataset
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

DEFAULT_TIME_LIMIT = 6
DEFAULT_MEMORY_LIMIT = 4 * 1024
MIN_MEMORY_LIMIT = 4 * 1024
API_BASE_URL = "http://localhost:8000/api/v1/judge"


def extract_time_limit(time_limit: str | None) -> int:
    if time_limit is None:
        return DEFAULT_TIME_LIMIT
    assert "second" in time_limit
    numbers = re.findall(r"\d+\.?\d*", time_limit)
    if numbers:
        return math.ceil(max(float(num) for num in numbers)) + 5
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


def judge(submission: dict) -> dict:
    id, submission = submission
    start_time = time.time()
    response = requests.post(API_BASE_URL, json=submission)
    end_time = time.time()
    result = response.json()
    # Add request latency to the result
    result["request_latency"] = (end_time - start_time) * 1000  # ms
    return id, result


def normalize_indentation(code: str) -> str:
    lines = code.splitlines()
    result = []

    has_tabs = any("\t" in line for line in lines)

    for line in lines:
        line = line.rstrip()
        leading_space = len(line) - len(line.lstrip())

        if has_tabs:
            line = line.replace("\t", "    ")
            leading_space = len(line) - len(line.lstrip())

        if leading_space > 0:
            indent_level = (leading_space + 2) // 4
            line = " " * (indent_level * 4) + line.lstrip()

        result.append(line)

    return "\n".join(result)


def handle_string(data: list[Any]) -> list[Any]:
    try:
        if isinstance(data, str):
            return ast.literal_eval(data)
        elif isinstance(data, list) or isinstance(data, tuple):
            return [handle_string(item) for item in data]
        else:
            return data
    except Exception:
        return data


def main():
    console = Console()

    ds = load_dataset("likaixin/TACO-verified", split="train", trust_remote_code=True)
    max_samples = 10

    submissions = {}
    for sample in ds:
        if sample.get("source") != "leetcode":
            continue
        code = normalize_indentation(sample.get("solutions")[0])
        input_output = json.loads(sample.get("input_output"))
        inputs = input_output.get("inputs")
        outputs = input_output.get("outputs")
        if not code or not inputs or not outputs:
            continue

        time_limit = extract_time_limit(sample.get("time_limit"))
        memory_limit = extract_memory_limit(sample.get("memory_limit"))
        inputs = handle_string(inputs)
        outputs = handle_string(outputs)
        submission = {
            "code": code,
            "language": "python",
            "mode": "leetcode",
            "test_cases": [
                {"input": inp, "expected": out} for inp, out in zip(inputs, outputs, strict=False)
            ],
            "time_limit": time_limit,
            "memory_limit": memory_limit,
        }
        submissions[sample.get("id")] = submission
        if len(submissions) >= max_samples:
            break

    benchmark_start = time.time()
    with Pool(512) as pool:
        results = pool.map(judge, submissions.items())
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    for id, result in results:
        if result.get("status") != "accepted":
            print(result.get("status"))
            print(result.get("test_case_results"))
            submission = submissions[id]
            input_data = submission.get("test_cases")[0].get("input")
            expected = submission.get("test_cases")[0].get("expected")
            print(submission.get("code"))
            print(input_data, input_data[0], type(input_data[0]))
            print(expected, type(expected))

    print_stress_test_summary(results, total_time, max_samples, console)


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
        summary_table.add_row("Avg Request Latency", f"{mean(latencies):.2f} ms")
        summary_table.add_row("Median Request Latency", f"{median(latencies):.2f} ms")
        summary_table.add_row(
            "Min/Max Request Latency", f"{min(latencies):.2f}/{max(latencies):.2f} ms"
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


if __name__ == "__main__":
    main()
