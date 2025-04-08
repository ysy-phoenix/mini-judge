import argparse
import ast
import asyncio
import json
import os
import time
from collections import Counter

from datasets import load_dataset
from rich.console import Console

from scripts.utils import (
    EMPTY_TEST_CASES,
    dump_failed_result,
    print_stress_test_summary,
    process_all_submissions,
)

KODCODE_TIME_LIMIT = 30
KODCODE_MEMORY_LIMIT = 4 * 1024


def format_unit_test(test: str) -> str:
    lines = test.split("\n")
    processed_lines = [line for line in lines if not line.startswith("from solution import ")]
    test_functions = []
    for line in lines:
        if line.startswith("def test_"):
            func_name = line.split("(")[0][4:]
            test_functions.append(func_name)
    new_content = "\n".join(processed_lines)
    if test_functions:
        new_content += '\n\nif __name__ == "__main__":\n'
        for func in test_functions:
            new_content += f"    {func}()\n"
    return new_content


def format_full_code(sample: dict) -> str:
    code = sample.get("solution")
    code += "\n\n"
    code += format_unit_test(sample.get("test"))
    code += "\n\n"
    return code


def format_test_cases(test: dict) -> str:
    inputs = test.get("stdin")
    outputs = test.get("stdout")
    if len(inputs) != len(outputs) or len(inputs) == 0:
        raise ValueError("Test cases are not valid")
    test_cases = [
        {"input": inp, "expected": out} for inp, out in zip(inputs, outputs, strict=False)
    ]
    return test_cases


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=512, help="max samples")
    parser.add_argument("--workers", type=int, default=128, help="max workers")
    parser.add_argument(
        "--subset",
        type=str,
        choices=[
            "Leetcode",
            "Apps",
            "Taco",
            "Codeforces",
            "Code_Contests",
            "Evol",
            "Package",
            "Algorithm",
            "Data_Structure",
            "Docs",
            "Filter",
            "Prefill",
        ],
        help="subset of kodcode",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()
    ds = load_dataset("KodCode/KodCode-V1", split="train", trust_remote_code=True)
    ds = ds.filter(lambda x: x.get("style") == "online_judge", num_proc=os.cpu_count())
    # ds = ds.filter(lambda x: x.get("subset") == args.subset, num_proc=os.cpu_count())
    if args.samples < 0:
        args.samples = float("inf")

    submissions = {}
    samples = {}
    for sample in ds:
        samples[sample.get("question_id")] = sample
        try:
            if sample.get("style") == "online_judge":
                code = sample.get("solution")
                mode = "acm"
                test_cases = format_test_cases(ast.literal_eval(sample.get("test")))
            else:
                code = format_full_code(sample)
                mode = "fullcode"
                test_cases = EMPTY_TEST_CASES
        except Exception as e:
            print(f"Error processing sample {sample.get('question_id')}: {e}")
            continue
        submission = {
            "code": code,
            "language": "python",
            "mode": mode,
            "test_cases": test_cases,
            "time_limit": KODCODE_TIME_LIMIT,
            "memory_limit": KODCODE_MEMORY_LIMIT,
        }
        submissions[sample.get("question_id")] = submission
        if len(submissions) >= args.samples:
            break

    benchmark_start = time.time()
    results = asyncio.run(process_all_submissions(submissions))
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    for _, result in results[:10]:
        if result.get("status") != "accepted":
            print(json.dumps(result, indent=4))

    print_stress_test_summary(results, total_time, len(submissions), console)
    os.makedirs("results", exist_ok=True)
    dump_failed_result(results, submissions, f"results/kodcode-{args.samples}.txt")


if __name__ == "__main__":
    main()
