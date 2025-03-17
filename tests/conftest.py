# tests/conftest.py
import httpx
import pytest
import pytest_asyncio

pytest_plugins = ["pytest_asyncio"]

pytest_asyncio_mode = "auto"


@pytest.fixture
def api_base_url():
    r"""Return the base URL of the API server."""
    return "http://localhost:8000"


# provide an async HTTP client - fix the usage of pytest_asyncio.fixture
@pytest_asyncio.fixture
async def async_client():
    r"""Provide an async HTTP client."""
    async with httpx.AsyncClient() as client:
        yield client  # directly yield the client object, not a generator
