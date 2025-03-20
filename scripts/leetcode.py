import ast
import json
import re
import time
from multiprocessing import Pool
from typing import Any

from datasets import load_dataset
from rich.console import Console

from scripts.utils import DEFAULT_MEMORY_LIMIT, DEFAULT_TIME_LIMIT, judge, print_stress_test_summary


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


def main():
    console = Console()
    ds = load_dataset("newfacade/LeetCodeDataset", split="train", trust_remote_code=True)
    max_samples = 128

    submissions = {}
    samples = {}
    for sample in ds:
        # code = format_full_code(sample)
        code = sample.get("prompt") + "\n\n" + sample.get("completion")
        test_cases = sample.get("input_output")

        if not code or not test_cases or "Node" in code:
            continue

        time_limit = DEFAULT_TIME_LIMIT
        memory_limit = DEFAULT_MEMORY_LIMIT
        samples[sample.get("task_id")] = sample
        submission = {
            "code": code,
            "language": "python",
            "mode": "leetcode",
            "test_cases": [
                {
                    "input": extract_input(test_case.get("input")),
                    "expected": extract_output(test_case.get("output")),
                }
                for test_case in test_cases
            ],
            "time_limit": time_limit,
            "memory_limit": memory_limit,
        }
        submissions[sample.get("task_id")] = submission
        if len(submissions) >= max_samples:
            break

    benchmark_start = time.time()
    with Pool(512) as pool:
        results = pool.map(judge, submissions.items())
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    for id, result in results:
        if result.get("status") != "accepted":
            print(json.dumps(result, indent=4))
            print(submissions[id].get("code"))

    print_stress_test_summary(results, total_time, max_samples, console)


if __name__ == "__main__":
    main()
