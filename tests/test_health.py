import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == "ok"


@pytest.mark.asyncio
async def test_ready_check(async_client: AsyncClient):
    response = await async_client.get("/api/ready/")
    assert response.status_code == 200
    assert response.json() == "ok"


@pytest.mark.asyncio
async def test_health_returns_no_business_data(async_client: AsyncClient):
    response = await async_client.get("/api/health/")
    assert response.status_code == 200
    data = response.json()
    assert data == "ok"
    assert not isinstance(data, dict)


@pytest.mark.asyncio
async def test_ready_returns_no_business_data(async_client: AsyncClient):
    response = await async_client.get("/api/ready/")
    assert response.status_code == 200
    data = response.json()
    assert data == "ok"
    assert not isinstance(data, dict)
