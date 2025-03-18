import json
import math
import re
from collections import defaultdict
from multiprocessing import Pool

import requests
from datasets import load_dataset

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
        return math.ceil(max(float(num) for num in numbers))
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


ds = load_dataset("likaixin/TACO-verified", split="train", trust_remote_code=True)
max_samples = 20
req = defaultdict(dict)
problems = defaultdict(str)
for sample in ds:
    if sample.get("source") != "codeforces":
        continue
    code = sample.get("solutions")
    inputs = json.loads(sample.get("input_output")).get("inputs")
    outputs = json.loads(sample.get("input_output")).get("outputs")
    if len(code) == 0 or len(inputs) == 0 or len(outputs) == 0 or not isinstance(inputs[0], str):
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
    print(time_limit, memory_limit, len(inputs))
    req[len(req)] = request
    problems[len(req)] = sample.get("question")
    if len(req) >= max_samples:
        break


def judge(item: tuple) -> tuple:
    idx, request = item
    response = requests.post(API_BASE_URL, json=request)
    return idx, response.json()


# Pass tuples of (index, request) to maintain the association
with Pool(512) as p:
    results_with_idx = p.map(judge, req.items())

# Convert results back to a dictionary using the preserved indices
results_dict = dict(results_with_idx)

# Now you can access results by the original index
for idx, request in req.items():
    result = results_dict[idx]
    if result.get("status") != "accepted":
        print(f"Request {idx} failed:\n{result}")
        print(f"Problem {idx}:\n{problems[idx]}")
        print(f"Code {idx}:\n{request.get('code')}")
