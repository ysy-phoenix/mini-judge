import argparse
import asyncio
import json
import os
import time

from datasets import load_dataset
from rich.console import Console

from scripts.utils import (
    dump_failed_result,
    print_stress_test_summary,
    process_all_submissions,
)

CODE_CONTESTS_PLUS_TIME_LIMIT = 30
CODE_CONTESTS_PLUS_MEMORY_LIMIT = 4 * 1024


def get_code(submissions: list[dict]) -> str:
    for submission in submissions:
        if submission.get("language") == "py3":
            return submission.get("code")
    return None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=512, help="max samples")
    parser.add_argument("--workers", type=int, default=128, help="max workers")
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()
    ds = load_dataset("ByteDance-Seed/Code-Contests-Plus", "1x", split="train", num_proc=96)

    submissions = {}
    samples = {}
    for sample in ds:
        samples[sample.get("id")] = sample
        code = get_code(sample.get("correct_submissions"))
        if code is None:
            continue
        test_cases = sample.get("test_cases")
        if len(test_cases) == 0:
            continue
        test_cases = [
            {
                "input": test_case.get("input"),
                "expected": test_case.get("output"),
            }
            for test_case in test_cases
        ]
        submission = {
            "code": code,
            "language": "python",
            "mode": "acm",
            "test_cases": test_cases,
            "security_check": False,
            "time_limit": CODE_CONTESTS_PLUS_TIME_LIMIT,
            "memory_limit": CODE_CONTESTS_PLUS_MEMORY_LIMIT,
        }
        submissions[sample.get("id")] = submission
        if len(submissions) >= args.samples:
            break
    benchmark_start = time.time()
    results = asyncio.run(process_all_submissions(submissions))
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    for _, result in results:
        if result.get("status") != "accepted":
            print(json.dumps(result, indent=4))

    print_stress_test_summary(results, total_time, len(submissions), console)
    os.makedirs("results", exist_ok=True)
    dump_failed_result(results, submissions, f"results/code-contests-plus-{args.samples}.txt")


if __name__ == "__main__":
    main()
