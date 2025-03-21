import pytest

from app.models.schemas import JudgeMode, Language


@pytest.mark.asyncio
async def test_judge_submission_basic(async_client, api_base_url):
    r"""Test the basic code submission functionality - send a request to the local API."""
    # 1. prepare test data
    test_code = """
def add(a, b):
    return a + b

a, b = map(int, input().split())
print(add(a, b))
"""
    test_request = {
        "code": test_code,
        "language": Language.PYTHON.value,
        "mode": JudgeMode.ACM.value,
        "test_cases": [{"input": "1 2", "expected": "3"}, {"input": "1 3", "expected": "4"}],
        "time_limit": 1,
        "memory_limit": 256,
    }

    # 2. send a request to the local server
    response = await async_client.post(f"{api_base_url}/api/v1/judge", json=test_request)

    # 3. validate the response
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert data["status"] == "accepted"
