#!/usr/bin/env python3
"""
DeepCoder Evaluation Script

This script evaluates solutions from the DeepCoder dataset against test cases.
It supports multiple data sources and provides detailed statistics on solution performance.
"""

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from datasets import load_dataset
from rich.console import Console

from scripts.pbar import get_progress_bar
from scripts.utils import (
    Submission,
    dump_failed_result,
    extract_code,
    print_stress_test_summary,
    process_all_submissions,
)

# Configuration constants
DATASET_NAME = "agentica-org/DeepCoder-Preview-Dataset"
SPLITS = {
    "codeforces": "test",
    "lcbv5": "train",
    "primeintellect": "train",
    "taco": "train",
}
MAX_CODE_LENGTH = 65536
MAX_TEST_CASES = 64
MAX_SOLUTIONS = 1
RESULTS_DIR = "results"


@dataclass
class ProblemStats:
    r"""Track statistics for each problem."""

    passed: bool = False
    solution_count: int = 0
    passed_solutions: int = 0


def parse_str(input_value: Any) -> str:
    r"""Convert various input types to string representation."""
    if isinstance(input_value, list | tuple):
        return "\n".join(str(item) for item in input_value)
    return str(input_value)


def get_solutions(solutions: list[str]) -> list[str]:
    r"""Extract and filter valid solutions from raw solution text."""
    valid_solutions = []
    for solution in solutions:
        code = extract_code(solution)
        if code and len(code) <= MAX_CODE_LENGTH:
            valid_solutions.append(code)
    return valid_solutions[:MAX_SOLUTIONS]


def get_tests(tests: list[dict] | dict) -> list[dict]:
    r"""Sort tests by input length and limit to MAX_TEST_CASES."""
    sorted_tests = sorted(tests, key=lambda test: len(str(test["input"])), reverse=True)
    return sorted_tests[:MAX_TEST_CASES]


def prepare_taco_tests(tests: dict) -> tuple[str, list[dict], str | None]:
    r"""Prepare test cases from TACO dataset format."""
    if "fn_name" in tests:
        mode = "leetcode"
        entry_point = tests["fn_name"]
        test_cases = [
            {"input": input_val, "expected": output[0]}
            for input_val, output in zip(tests["inputs"], tests["outputs"], strict=False)
        ]
    else:
        mode = "acm"
        entry_point = None
        test_cases = [
            {"input": parse_str(input_val), "expected": parse_str(output)}
            for input_val, output in zip(tests["inputs"], tests["outputs"], strict=False)
        ]
    return mode, test_cases, entry_point


def prepare_primeintellect_tests(tests: list[dict]) -> tuple[str, list[dict], str | None]:
    r"""Prepare test cases from PrimeIntellect dataset format."""
    if tests[0]["type"] == "stdin_stdout":
        mode = "acm"
        entry_point = None
        test_cases = [
            {"input": parse_str(test["input"]), "expected": parse_str(test["output"])}
            for test in tests
        ]
    else:
        mode = "leetcode"
        entry_point = tests[0]["fn_name"]
        test_cases = [{"input": test["input"], "expected": test["output"][0]} for test in tests]
    return mode, test_cases, entry_point


def create_submissions(
    sample: dict, sample_idx: int, args: argparse.Namespace
) -> tuple[dict[str, Submission], dict[int, ProblemStats]]:
    r"""Create submissions from a dataset sample."""
    submissions = {}
    problem_stats = {}

    solutions = get_solutions(sample["solutions"])
    if not solutions:
        return submissions, problem_stats

    tests = json.loads(sample["tests"])

    if args.source == "taco":
        mode, test_cases, entry_point = prepare_taco_tests(tests)
    elif args.source == "primeintellect":
        mode, test_cases, entry_point = prepare_primeintellect_tests(tests)
    else:
        # Default assumption for other datasets
        mode = "acm"
        test_cases = tests
        entry_point = None

    test_cases = get_tests(test_cases)

    # Initialize problem stats
    problem_stats[sample_idx] = ProblemStats(
        solution_count=len(solutions),
    )

    # Create submissions for each solution
    for sol_idx, solution in enumerate(solutions):
        submission_id = f"{sample_idx}-{sol_idx}"
        submissions[submission_id] = Submission(
            code=solution,
            mode=mode,
            test_cases=test_cases,
            entry_point=entry_point,
        )

    return submissions, problem_stats


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate DeepCoder solutions")
    parser.add_argument(
        "--source",
        type=str,
        default="codeforces",
        choices=list(SPLITS.keys()),
        help="Dataset source to evaluate",
    )
    parser.add_argument("--samples", type=int, default=512, help="Maximum number of samples")
    parser.add_argument("--workers", type=int, default=128, help="Maximum number of workers")
    return parser.parse_args()


def update_stats(results: list[tuple[str, dict]], problem_stats: dict[int, ProblemStats]) -> None:
    r"""Update problem statistics based on evaluation results."""
    for submission_id, result in results:
        if result.get("status") == "accepted":
            problem_idx = int(submission_id.split("-")[0])
            problem_stats[problem_idx].passed = True
            problem_stats[problem_idx].passed_solutions += 1


def print_stats(
    problem_stats: dict[int, ProblemStats],
    total_time: float,
    results: list,
    submissions_count: int,
    console: Console,
) -> None:
    r"""Print evaluation statistics."""
    # Calculate pass rates
    total_problems = len(problem_stats)
    passed_problems = sum(1 for stats in problem_stats.values() if stats.passed)
    pass_rate = passed_problems / total_problems if total_problems > 0 else 0

    total_solutions = sum(stats.solution_count for stats in problem_stats.values())
    passed_solutions = sum(stats.passed_solutions for stats in problem_stats.values())
    solution_pass_rate = passed_solutions / total_solutions if total_solutions > 0 else 0

    # Print summary
    print_stress_test_summary(results, total_time, submissions_count, console)

    console.print(
        f"\n[bold]Problem Pass Rate:[/bold] {passed_problems}/{total_problems} ({pass_rate:.2%})"
    )
    console.print(
        f"[bold]Solution Pass Rate:[/bold] {passed_solutions}/{total_solutions} "
        f"({solution_pass_rate:.2%})"
    )


def main() -> None:
    r"""Main evaluation function."""
    console = Console()
    args = parse_args()

    # Load dataset
    ds = load_dataset(DATASET_NAME, args.source, split=SPLITS[args.source])

    # Adjust sample count
    args.samples = min(max(args.samples, -1), len(ds))
    if args.samples < 0:
        args.samples = len(ds)

    submissions = {}
    problem_stats = {}

    # Prepare submissions
    with get_progress_bar() as pbar:
        task = pbar.add_task("Preprocessing", total=args.samples)
        for idx, sample in enumerate(ds):
            if idx >= args.samples:
                break

            sample_submissions, sample_stats = create_submissions(sample, idx, args)
            submissions.update(sample_submissions)
            problem_stats.update(sample_stats)

            pbar.update(task, advance=1)

    # Run evaluation
    benchmark_start = time.time()
    submission_dicts = {
        k: {key: getattr(v, key) for key in v.__dataclass_fields__} for k, v in submissions.items()
    }
    results = asyncio.run(process_all_submissions(submission_dicts))
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    # Update and print statistics
    update_stats(results, problem_stats)
    print_stats(problem_stats, total_time, results, len(submissions), console)

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    result_file = f"{RESULTS_DIR}/deepcoder-{args.source}-{args.samples}.txt"
    dump_failed_result(results, submissions, result_file)


if __name__ == "__main__":
    main()
