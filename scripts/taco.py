import argparse
import asyncio
import json
import os
import time
from typing import Any

from datasets import load_dataset
from rich.console import Console

from scripts.utils import (
    EMPTY_TEST_CASES,
    check_code_with_ast,
    dump_failed_result,
    extract_memory_limit,
    extract_time_limit,
    print_stress_test_summary,
    process_all_submissions,
)

MAX_CODE_LENGTH = 32768
MODE_MAP = {
    "codeforces": "acm",
    "aizu": "acm",
    "codechef": "acm",
    "codewars": "fullcode",
    "atcoder": "acm",
    "hackerrank": "acm",
    "hackerearth": "acm",
}

# Adapted from https://github.com/ganler/code-r1/blob/main/examples/data_preprocess/coder1.py#L175
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


def get_solution(solutions: list[str]) -> str | None:
    for solution in solutions:
        if len(solution) > MAX_CODE_LENGTH:
            continue
        if check_code_with_ast(solution):
            return solution
    return None


def get_codewars_code(code: str, inputs: list[Any], outputs: list[Any], entry_point: str) -> str:
    code += f"\n{TEST_CODE.format(inputs=inputs, outputs=outputs)}"
    code += f"    assert _deep_eq({entry_point}(*i), o[0])\n"
    return code


def get_codechef_test_cases(inputs: list[Any], outputs: list[Any]) -> list[dict]:
    _inputs = []
    _outputs = []
    for inp in inputs:
        if isinstance(inp, list):
            _inputs.append("\n".join(map(str, inp)))
        else:
            _inputs.append(str(inp))
    for o in outputs:
        if isinstance(o, list):
            _outputs.append("\n".join(map(str, o)))
        else:
            _outputs.append(str(o))
    return _inputs, _outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=str,
        default="codeforces",
        choices=[
            "codeforces",
            "aizu",
            "codewars",
            "codechef",
            "atcoder",
            "hackerrank",
            "hackerearth",
        ],
    )
    parser.add_argument("--samples", type=int, default=512, help="max samples")
    parser.add_argument("--workers", type=int, default=128, help="max workers")
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()
    ds = load_dataset("likaixin/TACO-verified", split="train", trust_remote_code=True)

    submissions = {}
    for sample in ds:
        # step 1: filter by source
        if sample.get("source") != args.source:
            continue

        # step 2: get mode
        mode = MODE_MAP.get(args.source)

        # step 3: get solution
        code = get_solution(sample.get("solutions"))
        if not code:
            continue

        # step 4: get test cases
        input_output = json.loads(sample.get("input_output"))
        inputs, outputs = input_output.get("inputs"), input_output.get("outputs")
        if not inputs or not outputs:
            continue

        if args.source == "codewars":
            code = get_codewars_code(code, inputs, outputs, input_output.get("fn_name"))
        elif args.source == "codechef":
            inputs, outputs = get_codechef_test_cases(inputs, outputs)
        if mode == "acm":
            test_cases = [
                {"input": inp, "expected": out} for inp, out in zip(inputs, outputs, strict=False)
            ]
        else:
            test_cases = EMPTY_TEST_CASES

        # step 5: extract time limit and memory limit
        time_limit = extract_time_limit(sample.get("time_limit"))
        memory_limit = extract_memory_limit(sample.get("memory_limit"))

        submission = {
            "code": code,
            "language": "python",
            "mode": mode,
            "test_cases": test_cases,
            "time_limit": time_limit,
            "memory_limit": memory_limit,
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
    dump_failed_result(results, submissions, f"results/taco-{args.source}-{args.samples}.txt")


if __name__ == "__main__":
    main()
