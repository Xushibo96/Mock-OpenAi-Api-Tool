"""Unit tests for bypass API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
import tempfile
from pathlib import Path

from mock_openai_tool.backend.main import app
from mock_openai_tool.backend.bypass_config import BypassConfigManager


@pytest.fixture
def temp_bypass_file():
    """Create temporary bypass config file."""
    with tempfile.NamedTemporaryFile(
        mode='w', delete=False, suffix='_bypass.json'
    ) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def client_with_bypass(temp_bypass_file):
    """Create test client with bypass configured."""
    with patch('mock_openai_tool.backend.main.BypassConfigManager') as MockBypass, \
         patch('mock_openai_tool.backend.main.PresetQueueManager') as MockQueue:

        bypass_mgr = BypassConfigManager(config_file=temp_bypass_file)

        queue_mgr = Mock()
        queue_mgr.load = AsyncMock()
        queue_mgr.get_all_queues = AsyncMock(return_value={})

        MockBypass.return_value = bypass_mgr
        MockQueue.return_value = queue_mgr

        with TestClient(app) as test_client:
            import mock_openai_tool.backend.api_routes as api_routes
            api_routes.bypass_config_manager = bypass_mgr
            api_routes.websocket_broadcast = AsyncMock()

            yield test_client


def test_get_bypass_config_default(client_with_bypass):
    """Test getting default bypass configuration."""
    response = client_with_bypass.get("/api/bypass/config")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["target_host"] == "api.openai.com"
    assert data["target_port"] == 443
    assert data["target_uri"] == "/v1/chat/completions"
    assert data["use_https"] is False
    assert data["timeout"] == 60
    assert data["api_key_configured"] is False


def test_update_bypass_config(client_with_bypass):
    """Test updating bypass configuration."""
    response = client_with_bypass.put(
        "/api/bypass/config",
        json={
            "target_host": "custom.api.com",
            "target_port": 8443,
            "api_key": "sk-test123"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_host"] == "custom.api.com"
    assert data["target_port"] == 8443
    assert data["api_key_configured"] is True  # Should not return actual key


def test_update_bypass_config_partial(client_with_bypass):
    """Test partial bypass configuration update."""
    response = client_with_bypass.put(
        "/api/bypass/config",
        json={"target_port": 9000}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_port"] == 9000
    assert data["target_host"] == "api.openai.com"  # Unchanged


def test_update_bypass_config_invalid_port(client_with_bypass):
    """Test updating with invalid port."""
    response = client_with_bypass.put(
        "/api/bypass/config",
        json={"target_port": 70000}
    )

    assert response.status_code == 400
    assert "1-65535" in response.json()["detail"]


def test_update_bypass_config_invalid_uri(client_with_bypass):
    """Test updating with invalid URI."""
    response = client_with_bypass.put(
        "/api/bypass/config",
        json={"target_uri": "api/chat"}  # Missing leading slash
    )

    assert response.status_code == 400
    assert "must start with" in response.json()["detail"]


def test_enable_bypass(client_with_bypass):
    """Test enabling bypass mode."""
    response = client_with_bypass.post("/api/bypass/enable")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}

    # Verify it's enabled
    get_response = client_with_bypass.get("/api/bypass/config")
    assert get_response.json()["enabled"] is True


def test_disable_bypass(client_with_bypass):
    """Test disabling bypass mode."""
    # First enable
    client_with_bypass.post("/api/bypass/enable")

    # Then disable
    response = client_with_bypass.post("/api/bypass/disable")

    assert response.status_code == 200
    assert response.json() == {"enabled": False}

    # Verify it's disabled
    get_response = client_with_bypass.get("/api/bypass/config")
    assert get_response.json()["enabled"] is False


def test_api_key_not_returned_in_response(client_with_bypass):
    """Test that API key is not returned in response."""
    # Set API key
    client_with_bypass.put(
        "/api/bypass/config",
        json={"api_key": "sk-secret-key"}
    )

    # Get config
    response = client_with_bypass.get("/api/bypass/config")
    data = response.json()

    # Should not contain actual key
    assert "api_key" not in data
    assert data["api_key_configured"] is True


def test_clear_api_key(client_with_bypass):
    """Test clearing API key."""
    # Set API key
    client_with_bypass.put(
        "/api/bypass/config",
        json={"api_key": "sk-test"}
    )

    # Clear by setting to empty string
    client_with_bypass.put(
        "/api/bypass/config",
        json={"api_key": ""}
    )

    response = client_with_bypass.get("/api/bypass/config")
    assert response.json()["api_key_configured"] is False


def test_update_multiple_fields(client_with_bypass):
    """Test updating multiple configuration fields at once."""
    response = client_with_bypass.put(
        "/api/bypass/config",
        json={
            "target_host": "test.com",
            "target_port": 8080,
            "target_uri": "/api/v2/chat",
            "use_https": False,
            "timeout": 30
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["target_host"] == "test.com"
    assert data["target_port"] == 8080
    assert data["target_uri"] == "/api/v2/chat"
    assert data["use_https"] is False
    assert data["timeout"] == 30


def test_config_persists_across_requests(client_with_bypass):
    """Test that configuration persists across requests."""
    # Update config
    client_with_bypass.put(
        "/api/bypass/config",
        json={"target_host": "persistent.com"}
    )

    # Get config in a new request
    response = client_with_bypass.get("/api/bypass/config")
    assert response.json()["target_host"] == "persistent.com"


@pytest.mark.asyncio
async def test_websocket_broadcast_on_config_update(client_with_bypass):
    """Test that WebSocket broadcast is called on config update."""
    import mock_openai_tool.backend.api_routes as api_routes

    client_with_bypass.put(
        "/api/bypass/config",
        json={"target_host": "new.com"}
    )

    # Should broadcast config update
    api_routes.websocket_broadcast.assert_called_with("bypass_config_updated")


@pytest.mark.asyncio
async def test_websocket_broadcast_on_enable(client_with_bypass):
    """Test that WebSocket broadcast is called on enable."""
    import mock_openai_tool.backend.api_routes as api_routes

    client_with_bypass.post("/api/bypass/enable")

    api_routes.websocket_broadcast.assert_called_with("bypass_config_updated")


@pytest.mark.asyncio
async def test_websocket_broadcast_on_disable(client_with_bypass):
    """Test that WebSocket broadcast is called on disable."""
    import mock_openai_tool.backend.api_routes as api_routes

    client_with_bypass.post("/api/bypass/disable")

    api_routes.websocket_broadcast.assert_called_with("bypass_config_updated")
