## Submission Overview

Here is a simple example of the submission format.

```python
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
    "time_limit": 1, # seconds
    "memory_limit": 256, # MB
}
API_BASE_URL = "http://localhost:8000/api/v1/judge"
response = requests.post(f"{API_BASE_URL}", json=submission)
print(response.json())
'''
{
    'status': 'accepted',
    'execution_time': 0.028892040252685547,
    'memory_usage': 7,
    'error_message': None,
    'test_case_results': [],
    'task_id': 'd7035970-d601-4f90-8c04-1ad3ffff3232'
}
```

For more details, please refer to the [Schema](../app/models/schemas.py).

## Mode Overview

We support three modes:

- ACM Mode
- LeetCode Mode
- Full Mode

> [!Warning]
> LeetCode Mode is not recommended, try to use Full Mode instead.

### ACM Mode

ACM Mode is designed for traditional programming competitions where input is read from stdin and output is written to stdout.

**Example:**
```python
# Sample solution in ACM Mode
def solve(a, b):
    return a + b

# Read input from stdin
a, b = map(int, input().split())
# Write output to stdout
print(solve(a, b))
```

**Submission format:**
```json
{
  "code": "...",
  "language": "python",
  "mode": "acm",
  "test_cases": [
    {"input": "1 2", "expected": "3"},
    {"input": "5 7", "expected": "12"}
  ],
  "time_limit": 1,
  "memory_limit": 256
}
```

> [!Important]
> For the ACM mode, during evaluation, the granularity of our implemented evaluation is per individual test case(i.e. the time limit is per test case).

### LeetCode Mode

LeetCode Mode emulates the LeetCode platform's execution environment, where your code implements a solution class with specific methods.

**Key characteristics:**
- Requires a `Solution` class with a method that solves the problem
- Input parameters are passed directly to the method
- Result is returned rather than printed
- System handles class instantiation and method invocation

**Example:**
```python
# Sample solution in LeetCode Mode
from typing import List
class Solution:
    def countSeniors(self, details: List[str]) -> int:
        count = 0
        for detail in details:
            age = int(detail[11:13])
            if age > 60:
                count += 1
        return count
```

**Submission format:**
```python
inputs = [
    [["7868190130M7522", "5303914400F9211", "9273338290F4010"]],
    [["1313579440F2036", "2921522980M5644"]],
    [["3988132605O4995"]],
]
outputs = [2, 0, 0]
test_cases = [
    {"input": input, "expected": output} for input, output in zip(inputs, outputs, strict=False)
]
{
  "code": "...",
  "language": "python",
  "mode": "leetcode",
  "test_cases": test_cases,
  "time_limit": 1,
  "memory_limit": 256
}
```

- Note that each input is a list of arguments
- LeetCode mode also uses test-case wise evaluation like ACM mode

### FullCode Mode

FullCode Mode offers the most flexibility, allowing you to submit complete, self-contained solutions that handle both input parsing and output formatting.

**Key characteristics:**
- Entire code is executed as a standalone program
- You have complete **assertion-like** test cases in the code
- Best for complex problems requiring custom data structures

**Example:**
```python
import collections
import string
import math
import datetime

from typing import *
from functools import *
from collections import *
from itertools import *
from heapq import *
from bisect import *
from string import *
from operator import *
from math import *

inf = float('inf')

class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        ss = set()
        ans = i = 0
        for j, c in enumerate(s):
            while c in ss:
                ss.remove(s[i])
                i += 1
            ss.add(c)
            ans = max(ans, j - i + 1)
        return ans

def check(candidate):
    assert candidate(s = "abcabcbb") == 3
    assert candidate(s = "bbbbb") == 1
    assert candidate(s = "pwwkew") == 3
    assert candidate(s = "abcdabcabcabcd") == 4
    assert candidate(s = "abcdefgabcdefgabcdefgabcdefg") == 7
    assert candidate(s = "aabbccddeeff") == 2
    assert candidate(s = "sldfjldskfjdslkfjsdkljflkjsdfljfsdlkflskdjflsdjflskdjflsdkjflsdfjlsd") == 6
    # ...

check(Solution().lengthOfLongestSubstring)
```

**Submission format:**
```json
{
  "code": "...",
  "language": "python",
  "mode": "fullcode",
  "test_cases": [
    {"input": "", "expected": ""},
  ],
  "time_limit": 1,
  "memory_limit": 256
}
```

To match the API design, please make sure the test cases are in the format of `{"input": "", "expected": ""}`.
