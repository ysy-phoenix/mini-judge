import pytest

from app.models.schemas import JudgeMode, JudgeStatus, Language

EMPTY_TEST_CASES = [
    {"input": "", "expected": ""},
]


@pytest.mark.asyncio
async def test_execution_mode_accepted(async_client, api_base_url):
    r"""Test Execution mode with correct code - should pass all test cases."""
    test_code = """
def add(a, b):
    return a + b

a, b = map(int, input().split())
print(add(a, b))
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.EXECUTION.value,
        "test_cases": [{"input": "1 2", "expected": "3"}, {"input": "0 0", "expected": "0"}],
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.ACCEPTED
    assert data["test_case_results"][0]["actual_output"] == "3"
    assert data["test_case_results"][1]["actual_output"] == "0"


@pytest.mark.asyncio
async def test_acm_mode_accepted(async_client, api_base_url):
    r"""Test ACM mode with correct code - should pass all test cases."""
    test_code = """
def add(a, b):
    return a + b

a, b = map(int, input().split())
print(add(a, b))
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.ACM.value,
        "test_cases": [
            {"input": "1 2", "expected": "3"},
            {"input": "0 0", "expected": "0"},
            {"input": "-5 10", "expected": "5"},
        ],
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.ACCEPTED


@pytest.mark.asyncio
async def test_acm_mode_wrong_answer(async_client, api_base_url):
    r"""Test ACM mode with incorrect output - should get wrong answer."""
    test_code = """
def add(a, b):
    return a + b + 1  # Deliberately wrong

a, b = map(int, input().split())
print(add(a, b))
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.ACM.value,
        "test_cases": [{"input": "1 2", "expected": "3"}, {"input": "0 0", "expected": "0"}],
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.WRONG_ANSWER


@pytest.mark.asyncio
async def test_acm_mode_time_limit_exceeded(async_client, api_base_url):
    r"""Test ACM mode with code that exceeds time limit."""
    test_code = """
import time
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

n = int(input())
time.sleep(10)
print(fibonacci(n))
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.ACM.value,
        "test_cases": [
            {"input": "40", "expected": "102334155"}
        ],  # This will timeout with recursive fibonacci
        "time_limit": 1,  # 1 second
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.TIME_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_acm_mode_memory_limit_exceeded(async_client, api_base_url):
    r"""Test ACM mode with code that exceeds memory limit."""
    test_code = """
n = int(input())
# Create a large list that consumes lots of memory
large_list = [0] * (n * 10000000000)  # Will allocate a large amount of memory
print("Done")
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.ACM.value,
        "test_cases": [{"input": "100", "expected": "Done"}],  # This will consume ~800MB
        "time_limit": 5,
        "memory_limit": 1,  # 64MB limit
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.MEMORY_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_acm_mode_runtime_error(async_client, api_base_url):
    r"""Test ACM mode with code that causes runtime error."""
    test_code = """
a, b = map(int, input().split())
result = a / b  # Will cause division by zero
print(result)
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.ACM.value,
        "test_cases": [{"input": "5 0", "expected": "Error"}],  # Division by zero
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.RUNTIME_ERROR


@pytest.mark.asyncio
async def test_full_mode_accepted(async_client, api_base_url):
    r"""Test Full mode with correct code - complex algorithm."""
    test_code = """
def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

def nth_prime(n):
    count = 0
    num = 1
    while count < n:
        num += 1
        if is_prime(num):
            count += 1
    return num
def check(candidate):
    assert candidate(1) == 2
    assert candidate(5) == 11
    assert candidate(10) == 29
    assert candidate(100) == 541
    assert candidate(1000) == 7919
    assert candidate(10000) == 104729

check(nth_prime)
"""

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.FULLCODE.value,
        "test_cases": EMPTY_TEST_CASES,
        "time_limit": 5,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.ACCEPTED


@pytest.mark.asyncio
async def test_full_mode_wrong_answer(async_client, api_base_url):
    r"""Test Full mode with code that produces wrong answer."""
    test_code = """
class Solution:
    def twoSum(self, nums, target):
        # Deliberately wrong implementation
        return [0, 1]  # Always return the same answer

# Parse input and execute
def check(candidate):
    assert candidate([2,7,11,15], 9) == [0, 1]
    assert candidate([3,2,4], 6) == [1, 2]

check(Solution().twoSum)
"""

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.FULLCODE.value,
        "test_cases": EMPTY_TEST_CASES,
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.WRONG_ANSWER


@pytest.mark.asyncio
async def test_full_mode_time_limit_exceeded(async_client, api_base_url):
    r"""Test Full mode with code that times out (inefficient algorithm)."""
    test_code = """
import time
time.sleep(2)
"""

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.FULLCODE.value,
        "test_cases": EMPTY_TEST_CASES,
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.TIME_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_full_mode_memory_limit_exceeded(async_client, api_base_url):
    r"""Test Full mode with code that uses too much memory."""
    test_code = """
import sys

# Recursive function with no base case (causes stack overflow)
def large_memory_usage():
    # Create a large matrix filled with data
    size = int(input().strip())
    matrix = [[i*j for j in range(size)] for i in range(size)]
    # Force memory to stay around by adding to global list
    global all_matrices
    all_matrices.append(matrix)
    return sum(sum(row) for row in matrix)

all_matrices = []
assert large_memory_usage() == 0
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.FULLCODE.value,
        "test_cases": EMPTY_TEST_CASES,
        "time_limit": 5,
        "memory_limit": 1,  # 64MB limit
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.MEMORY_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_full_mode_runtime_error(async_client, api_base_url):
    r"""Test Full mode with code that causes runtime error."""
    test_code = """
def process_list(lst):
    # This will cause an index error
    return lst[len(lst)]

assert process_list([1, 2, 3]) == 3
    """

    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.FULLCODE.value,
        "test_cases": EMPTY_TEST_CASES,
        "time_limit": 1,
        "memory_limit": 256,
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.RUNTIME_ERROR


@pytest.mark.asyncio
async def test_full_code_multiple_test_cases(async_client, api_base_url):
    r"""Test Full mode with multiple test cases."""
    test_code = """
class Solution:
    def countSeniors(self, details: List[str]) -> int:
        count = 0
        for detail in details:
            age = int(detail[11:13])
            if age > 60:
                count += 1
        return count
"""
    inputs = [
        [["7868190130M7522", "5303914400F9211", "9273338290F4010"]],
        [["1313579440F2036", "2921522980M5644"]],
        [["3988132605O4995"]],
    ]
    outputs = [2, 0, 0]
    test_cases = [
        {"input": input, "expected": output} for input, output in zip(inputs, outputs, strict=False)
    ]
    submission = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.LEETCODE.value,
        "test_cases": test_cases,
        "entry_point": "countSeniors",
    }

    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=submission)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == JudgeStatus.ACCEPTED
