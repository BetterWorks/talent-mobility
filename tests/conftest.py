import asyncio
from typing import Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app as backend_app


@pytest.fixture(scope="session")
def event_loop(request) -> Generator:  # noqa: indirect usage
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        base_url='http://testserver',
        transport=ASGITransport(app=backend_app)
    ) as client:
        yield client
