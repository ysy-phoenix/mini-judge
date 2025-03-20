import argparse
import ast
import json
import re
import time
from multiprocessing import Pool
from typing import Any

from datasets import load_dataset
from rich.console import Console

from scripts.utils import judge, print_stress_test_summary

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


def extract_input(input_str: str) -> list[Any]:
    pattern = r"(\w+)\s*=\s*(.*?)(?=\s*,\s*\w+\s*=|\s*$)"
    matches = re.findall(pattern, input_str, re.DOTALL)

    result = []
    for _, value_str in matches:
        value_str = value_str.strip()
        try:
            value = ast.literal_eval(value_str)
            result.append(value)
        except (SyntaxError, ValueError) as e:
            if value_str.isalpha():
                result.append(value_str)
            else:
                raise ValueError(f"Cannot parse value: {value_str}, error: {str(e)}") from e

    return result


def extract_output(output_str: str) -> Any:
    try:
        output = ast.literal_eval(output_str)
        return output
    except (SyntaxError, ValueError):
        return output_str


EMPTY_TESTCASES = [
    {
        "input": "",
        "expected": "",
    },
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="fullcode", choices=["leetcode", "fullcode"])
    parser.add_argument("--samples", type=int, default=512, help="max samples")
    parser.add_argument("--workers", type=int, default=128, help="max workers")
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()
    ds = load_dataset("newfacade/LeetCodeDataset", split="train", trust_remote_code=True)

    submissions = {}
    samples = {}
    max_code_length = 0
    for sample in ds:
        code = (
            format_full_code(sample)
            if args.mode == "fullcode"
            else sample.get("prompt") + "\n\n" + sample.get("completion")
        )

        if args.mode == "leetcode" and "Node" in code:
            continue

        if args.mode == "fullcode":
            testcases = EMPTY_TESTCASES
        else:
            testcases = [
                {
                    "input": extract_input(test_case.get("input")),
                    "expected": extract_output(test_case.get("output")),
                }
                for test_case in sample.get("input_output")
            ]

        samples[sample.get("task_id")] = sample
        max_code_length = max(max_code_length, len(code))
        submission = {
            "code": code,
            "language": "python",
            "mode": args.mode,
            "test_cases": testcases,
            "time_limit": LEETCODE_TIME_LIMIT,
            "memory_limit": LEETCODE_MEMORY_LIMIT,
        }
        submissions[sample.get("task_id")] = submission
        if len(submissions) >= args.samples:
            break

    print(f"Max code length: {max_code_length}")
    benchmark_start = time.time()

    with Pool(args.workers) as pool:
        results = pool.map(judge, submissions.items())

    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    for id, result in results:
        if result.get("status") != "accepted":
            print(json.dumps(result, indent=4))
            print(submissions[id].get("code"))

    print_stress_test_summary(results, total_time, len(submissions), console)


if __name__ == "__main__":
    main()
