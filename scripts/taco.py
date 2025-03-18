import json
import math
import re
from multiprocessing import Pool

import requests
from datasets import load_dataset
from tqdm import tqdm

DEFAULT_TIME_LIMIT = 6
DEFAULT_MEMORY_LIMIT = 1024
MIN_MEMORY_LIMIT = 256
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


def judge(request: dict) -> dict:
    response = requests.post(API_BASE_URL, json=request)
    return response.json()


def main():
    ds = load_dataset("likaixin/TACO-verified", split="train", trust_remote_code=True)
    max_samples = 512

    requests_data = []
    problems_data = []
    for sample in ds:
        if sample.get("source") != "codeforces":
            continue
        code = sample.get("solutions")
        input_output = json.loads(sample.get("input_output"))
        inputs = input_output.get("inputs")
        outputs = input_output.get("outputs")
        if not code or not inputs or not outputs or not isinstance(inputs[0], str):
            continue

        time_limit = extract_time_limit(sample.get("time_limit"))
        memory_limit = extract_memory_limit(sample.get("memory_limit"))
        request = {
            "code": code[0],
            "language": "python",
            "mode": "acm",
            "test_cases": [
                {"input": inp, "expected": out} for inp, out in zip(inputs, outputs, strict=False)
            ],
            "time_limit": time_limit,
            "memory_limit": memory_limit,
        }
        requests_data.append(request)
        problems_data.append(sample.get("question"))

        if len(requests_data) >= max_samples:
            break

    with Pool(512) as pool:
        results = list(
            tqdm(pool.imap(judge, requests_data), total=len(requests_data), desc="Processing")
        )

    for idx, (result, _problem, req) in enumerate(
        zip(results, problems_data, requests_data, strict=False)
    ):
        if result.get("status") != "accepted":
            print(f"Request {idx} failed:\n{result}")
            # print(f"Problem {idx}:\n{problem}")
            print(f"Code {idx}:\n{req.get('code')}")
        # else:
        #     print(f"Request {idx} passed\n{result}")


if __name__ == "__main__":
    main()
