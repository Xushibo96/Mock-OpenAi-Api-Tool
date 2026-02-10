"""Integration tests for bypass mode with main application flow."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
import tempfile
from pathlib import Path

from mock_openai_tool.backend.main import app
from mock_openai_tool.backend.bypass_config import BypassConfigManager
from mock_openai_tool.backend.bypass_handler import BypassHandler


@pytest.fixture
def temp_files():
    """Create temporary config files."""
    with tempfile.NamedTemporaryFile(
        mode='w', delete=False, suffix='_bypass.json'
    ) as bypass_file, \
         tempfile.NamedTemporaryFile(
        mode='w', delete=False, suffix='_queue.json'
    ) as queue_file:
        yield {
            'bypass': bypass_file.name,
            'queue': queue_file.name
        }
    Path(bypass_file.name).unlink(missing_ok=True)
    Path(queue_file.name).unlink(missing_ok=True)


@pytest.fixture
def client(temp_files):
    """Create test client with temporary config files."""
    # Override config file paths in app initialization
    with patch('mock_openai_tool.backend.main.BypassConfigManager') as MockBypass, \
         patch('mock_openai_tool.backend.main.PresetQueueManager') as MockQueue:

        # Create real instances with temp files
        bypass_mgr = BypassConfigManager(config_file=temp_files['bypass'])
        queue_mgr_instance = Mock()
        queue_mgr_instance.load = AsyncMock()
        queue_mgr_instance.get_all_queues = AsyncMock(return_value={})
        queue_mgr_instance.check_and_pop = AsyncMock(return_value=None)

        MockBypass.return_value = bypass_mgr
        MockQueue.return_value = queue_mgr_instance

        with TestClient(app) as test_client:
            # Manually inject for API routes since startup event may not fire
            import mock_openai_tool.backend.api_routes as api_routes
            api_routes.bypass_config_manager = bypass_mgr
            api_routes.queue_manager = queue_mgr_instance
            api_routes.bypass_handler = BypassHandler(bypass_mgr)

            yield test_client


def test_bypass_disabled_falls_back_to_preset_queue(client):
    """Test that when bypass is disabled, request falls back to preset queue."""
    # Bypass is disabled by default
    # Mock preset queue to return a response
    import mock_openai_tool.backend.api_routes as api_routes
    api_routes.queue_manager.check_and_pop = AsyncMock(return_value=(
        {"response": "from queue"}, 200
    ))

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]}
    )

    # Should get response from preset queue
    assert response.status_code == 200
    assert response.json() == {"response": "from queue"}


@pytest.mark.asyncio
async def test_bypass_enabled_skips_preset_queue(client):
    """Test that when bypass is enabled, preset queue is skipped."""
    import mock_openai_tool.backend.api_routes as api_routes
    import mock_openai_tool.backend.main as main_module

    # Enable bypass mode
    await api_routes.bypass_config_manager.enable()

    # Mock preset queue (should be skipped)
    api_routes.queue_manager.check_and_pop = AsyncMock(return_value=(
        {"response": "from queue"}, 200
    ))

    # Mock bypass handler in main module where it's used
    with patch.object(
        main_module.bypass_handler,
        'forward_request',
        AsyncMock(return_value=({"response": "from bypass"}, 200, 0.1))
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]}
        )

    # Should get response from bypass, not queue
    assert response.status_code == 200
    assert response.json() == {"response": "from bypass"}


@pytest.mark.asyncio
async def test_bypass_request_broadcasts_websocket_events(client):
    """Test that bypass request broadcasts WebSocket events."""
    import mock_openai_tool.backend.api_routes as api_routes
    import mock_openai_tool.backend.main as main_module

    # Enable bypass mode
    await api_routes.bypass_config_manager.enable()

    # Mock broadcast function to capture messages
    broadcast_messages = []

    async def mock_broadcast(message):
        broadcast_messages.append(message)

    # Mock bypass handler in main module
    with patch.object(
        main_module.bypass_handler,
        'forward_request',
        AsyncMock(return_value=({"response": "success"}, 200, 0.5))
    ), patch.object(
        main_module,
        'broadcast_websocket',
        side_effect=mock_broadcast
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]}
        )

    # Should broadcast two messages: request and response
    assert len(broadcast_messages) == 2

    # Check request event
    assert broadcast_messages[0]["type"] == "bypass_request"
    assert "data" in broadcast_messages[0]
    assert broadcast_messages[0]["data"]["client_ip"] == "testclient"

    # Check response event
    assert broadcast_messages[1]["type"] == "bypass_response"
    assert broadcast_messages[1]["data"]["success"] is True
    assert broadcast_messages[1]["data"]["status_code"] == 200


@pytest.mark.asyncio
async def test_bypass_error_broadcasts_failure_event(client):
    """Test that bypass error broadcasts failure event."""
    import mock_openai_tool.backend.api_routes as api_routes
    import mock_openai_tool.backend.main as main_module
    from mock_openai_tool.backend.bypass_handler import BypassError

    # Enable bypass mode
    await api_routes.bypass_config_manager.enable()

    # Mock broadcast function
    broadcast_messages = []

    async def mock_broadcast(message):
        broadcast_messages.append(message)

    # Mock bypass handler to raise error in main module
    with patch.object(
        main_module.bypass_handler,
        'forward_request',
        AsyncMock(side_effect=BypassError("Connection failed"))
    ), patch.object(
        main_module,
        'broadcast_websocket',
        side_effect=mock_broadcast
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]}
        )

    # Should return 502 error
    assert response.status_code == 502
    assert "error" in response.json()

    # Should broadcast request and error response
    assert len(broadcast_messages) == 2
    assert broadcast_messages[0]["type"] == "bypass_request"
    assert broadcast_messages[1]["type"] == "bypass_response"
    assert broadcast_messages[1]["data"]["success"] is False
    assert "Connection failed" in broadcast_messages[1]["data"]["error"]


@pytest.mark.asyncio
async def test_bypass_priority_over_queue(client):
    """Test that bypass has higher priority than preset queue."""
    import mock_openai_tool.backend.api_routes as api_routes
    import mock_openai_tool.backend.main as main_module

    # Setup both bypass and preset queue
    await api_routes.bypass_config_manager.enable()
    api_routes.queue_manager.check_and_pop = AsyncMock(return_value=(
        {"response": "from queue"}, 200
    ))

    # Mock bypass handler in main module
    with patch.object(
        main_module.bypass_handler,
        'forward_request',
        AsyncMock(return_value=({"response": "from bypass"}, 200, 0.1))
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]}
        )

    # Bypass should win
    assert response.json() == {"response": "from bypass"}

    # Preset queue check should not be called
    api_routes.queue_manager.check_and_pop.assert_not_called()


@pytest.mark.asyncio
async def test_disable_bypass_restores_normal_flow(client):
    """Test that disabling bypass restores normal flow."""
    import mock_openai_tool.backend.api_routes as api_routes

    # First enable, then disable bypass
    await api_routes.bypass_config_manager.enable()
    await api_routes.bypass_config_manager.disable()

    # Mock preset queue
    api_routes.queue_manager.check_and_pop = AsyncMock(return_value=(
        {"response": "from queue"}, 200
    ))

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "test"}]}
    )

    # Should use preset queue, not bypass
    assert response.json() == {"response": "from queue"}
