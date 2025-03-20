import requests

from scripts.utils import API_BASE_URL


def main():
    test_code = """
def add(a, b):
    return a + b

a, b = map(int, input().split())
print(add(a, b))
"""
    submission = {
        "code": test_code,
        "language": "python",
        "mode": "acm",
        "test_cases": [{"input": "1 2", "expected": "3"}, {"input": "1 3", "expected": "4"}],
        "time_limit": 1,
        "memory_limit": 256,
    }
    for _ in range(10):
        response = requests.post(f"{API_BASE_URL}", json=submission)
        print(response.json())


if __name__ == "__main__":
    main()
