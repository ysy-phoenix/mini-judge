import argparse
import json
import time
from multiprocessing import Pool

from datasets import load_dataset
from rich.console import Console

from scripts.utils import EMPTY_TEST_CASES, dump_failed_result, judge, print_stress_test_summary

LEETCODE_TIME_LIMIT = 30
LEETCODE_MEMORY_LIMIT = 4 * 1024


def format_full_code(sample: dict) -> str:
    code = sample.get("prompt")
    code += "\n\n"
    code += sample.get("completion")
    code += "\n\n"
    code += sample.get("test")
    code += "\n\n"
    code += f"check({sample.get('entry_point')})"
    return code


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=512, help="max samples")
    parser.add_argument("--workers", type=int, default=128, help="max workers")
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()
    ds = load_dataset("newfacade/LeetCodeDataset", split="train", trust_remote_code=True)

    submissions = {}
    samples = {}
    for sample in ds:
        samples[sample.get("task_id")] = sample
        code = format_full_code(sample)
        submission = {
            "code": code,
            "language": "python",
            "mode": "fullcode",
            "test_cases": EMPTY_TEST_CASES,
            "time_limit": LEETCODE_TIME_LIMIT,
            "memory_limit": LEETCODE_MEMORY_LIMIT,
        }
        submissions[sample.get("task_id")] = submission
        if len(submissions) >= args.samples:
            break

    benchmark_start = time.time()
    with Pool(args.workers) as pool:
        results = pool.map(judge, submissions.items())
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    for _, result in results:
        if result.get("status") != "accepted":
            print(json.dumps(result, indent=4))

    print_stress_test_summary(results, total_time, len(submissions), console)
    dump_failed_result(results, submissions, f"results/leetcode-{args.samples}.txt")


if __name__ == "__main__":
    main()
