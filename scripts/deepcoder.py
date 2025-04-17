import argparse
import asyncio
import json
import os
import time

from datasets import load_dataset
from rich.console import Console

from scripts.pbar import get_progress_bar
from scripts.utils import (
    DEFAULT_MEMORY_LIMIT,
    DEFAULT_TIME_LIMIT,
    dump_failed_result,
    extract_code,
    print_stress_test_summary,
    process_all_submissions,
)

SPLITS = {
    "codeforces": "test",
    "lcbv5": "train",
    "primeintellect": "train",
    "taco": "train",
}

MAX_CODE_LENGTH = 65536

TEST_CODE = """
_inputs = {inputs}
_outputs = {outputs}
import math
def _deep_eq(a, b, tol=1e-5):
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(a, b, rel_tol=tol, abs_tol=tol)
    if isinstance(a, (list, tuple)):
        if len(a) != len(b): return False
        return all(_deep_eq(x, y, tol) for x, y in zip(a, b))
    return a == b

for i, o in zip(_inputs, _outputs):
"""


def format_full_code(code: str, fn_name: str, tests: list[dict]) -> str:
    inputs = [test["input"] for test in tests]
    outputs = [test["expected"] for test in tests]
    code += f"\n{TEST_CODE.format(inputs=inputs, outputs=outputs)}"
    code += f"    assert _deep_eq({fn_name}(*i), o[0])\n"
    return code


def get_solutions(solutions: list[str]) -> list[str]:
    valid_solutions = []
    for solution in solutions:
        solution = extract_code(solution)
        if len(solution) > MAX_CODE_LENGTH:
            continue
        if solution:
            valid_solutions.append(solution)
    return valid_solutions


MAX_TEST_CASES = 64


def get_tests(tests: list[dict]) -> list[dict]:
    # Sort tests by the length of their input (longest first)
    sorted_tests = sorted(tests, key=lambda test: len(str(test["input"])), reverse=True)
    # Return at most MAX_TEST_CASES tests
    return sorted_tests[:MAX_TEST_CASES]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=str,
        default="codeforces",
        choices=[
            "codeforces",
            "lcbv5",
            "primeintellect",
            "taco",
        ],
    )
    parser.add_argument("--samples", type=int, default=512, help="max samples")
    parser.add_argument("--workers", type=int, default=128, help="max workers")
    return parser.parse_args()


def main():
    console = Console()
    args = parse_args()
    ds = load_dataset(
        "agentica-org/DeepCoder-Preview-Dataset", args.source, split=SPLITS[args.source]
    )
    if args.samples < 0:
        args.samples = len(ds)
    args.samples = min(args.samples, len(ds))
    submissions = {}
    problem_stats = {}  # Track problem pass/fail status

    with get_progress_bar() as pbar:
        task = pbar.add_task("Preprocessing", total=args.samples)
        for idx, sample in enumerate(ds):
            if idx >= args.samples:
                break

            solutions = get_solutions(sample["solutions"])
            if not solutions:
                continue

            tests = get_tests(json.loads(sample["tests"]))
            entry_point = None
            if tests[0]["type"] == "stdin_stdout":
                mode = "acm"
                tests = [{"input": test["input"], "expected": test["output"]} for test in tests]
            else:
                mode = "leetcode"
                entry_point = tests[0]["fn_name"]
                tests = [{"input": test["input"], "expected": test["output"][0]} for test in tests]

            # Initialize problem stats
            problem_stats[idx] = {
                "passed": False,
                "solution_count": len(solutions),
                "passed_solutions": 0,
            }

            # Add all valid solutions
            for sol_idx, solution in enumerate(solutions):
                submission_id = f"{idx}-{sol_idx}"
                submission = {
                    "code": solution,
                    "language": "python",
                    "mode": mode,
                    "test_cases": tests,
                    "time_limit": DEFAULT_TIME_LIMIT,
                    "memory_limit": DEFAULT_MEMORY_LIMIT,
                    "entry_point": entry_point,
                }
                submissions[submission_id] = submission

            pbar.update(task, advance=1)

    benchmark_start = time.time()
    results = asyncio.run(process_all_submissions(submissions))
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start

    # Update problem stats based on results
    for submission_id, result in results:
        if result.get("status") == "accepted":
            problem_idx = int(submission_id.split("-")[0])
            problem_stats[problem_idx]["passed"] = True
            problem_stats[problem_idx]["passed_solutions"] += 1

    # Calculate pass rate
    total_problems = len(problem_stats)
    passed_problems = sum(1 for stats in problem_stats.values() if stats["passed"])
    pass_rate = passed_problems / total_problems if total_problems > 0 else 0

    # Print statistics
    print_stress_test_summary(results, total_time, len(submissions), console)
    console.print(
        f"\n[bold]Problem Pass Rate:[/bold] {passed_problems}/{total_problems} ({pass_rate:.2%})"
    )

    # Additional detailed statistics
    total_solutions = sum(stats["solution_count"] for stats in problem_stats.values())
    passed_solutions = sum(stats["passed_solutions"] for stats in problem_stats.values())
    solution_pass_rate = passed_solutions / total_solutions if total_solutions > 0 else 0
    console.print(
        f"[bold]Solution Pass Rate:[/bold] {passed_solutions}/{total_solutions} "
        f"({solution_pass_rate:.2%})"
    )

    os.makedirs("results", exist_ok=True)
    dump_failed_result(results, submissions, f"results/deepcoder-{args.source}-{args.samples}.txt")


if __name__ == "__main__":
    main()
