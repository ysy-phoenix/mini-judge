import argparse
import ast
import json
import time
from multiprocessing import Pool
from typing import Any

from datasets import load_dataset
from rich.console import Console

from scripts.utils import (
    extract_memory_limit,
    extract_time_limit,
    judge,
    print_stress_test_summary,
)


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="acm", choices=["acm", "leetcode"])
    args = parser.parse_args()
    console = Console()
    source_map = {"acm": "codeforces", "leetcode": "leetcode"}

    ds = load_dataset("likaixin/TACO-verified", split="train", trust_remote_code=True)
    max_samples = 512

    submissions = {}
    for sample in ds:
        if sample.get("source") != source_map[args.mode]:
            continue
        code = normalize_indentation(sample.get("solutions")[0])
        input_output = json.loads(sample.get("input_output"))
        inputs = input_output.get("inputs")
        outputs = input_output.get("outputs")
        if not code or not inputs or not outputs:
            continue

        time_limit = extract_time_limit(sample.get("time_limit"))
        memory_limit = extract_memory_limit(sample.get("memory_limit"))
        inputs = handle_string(inputs) if args.mode == "leetcode" else inputs
        outputs = handle_string(outputs) if args.mode == "leetcode" else outputs
        submission = {
            "code": code,
            "language": "python",
            "mode": args.mode,
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

    for _, result in results:
        if result.get("status") != "accepted":
            print(json.dumps(result, indent=4))

    print_stress_test_summary(results, total_time, max_samples, console)


if __name__ == "__main__":
    main()
