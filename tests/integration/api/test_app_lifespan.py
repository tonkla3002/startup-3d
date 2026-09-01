"""ตรวจว่า lifespan สร้าง httpx client ตัวเดียวไว้ใช้ตลอด lifetime ของแอป."""

import httpx
from fastapi.testclient import TestClient

from app.main import create_app


class TestLifespan:
    def test_lifespan_creates_shared_http_client(self):
        # Arrange
        application = create_app()
        # Act — TestClient ใน context manager จะรัน lifespan จริง
        with TestClient(application) as test_client:
            shared = application.state.http_client
            # Assert
            assert isinstance(shared, httpx.AsyncClient)
            assert test_client.get("/api/v1/health").status_code == 200

    def test_docs_enabled_outside_production(self):
        application = create_app()
        assert application.docs_url == "/docs"
