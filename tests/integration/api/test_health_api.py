"""Integration test ของ health endpoint."""


class TestHealthAPI:
    async def test_health_returns_ok(self, client):
        # Act
        response = await client.get("/api/v1/health")
        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["app"] == "streamora"

    async def test_unknown_route_returns_404(self, client):
        response = await client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
