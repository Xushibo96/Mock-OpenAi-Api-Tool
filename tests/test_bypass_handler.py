"""Unit tests for bypass request handler."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from mock_openai_tool.backend.bypass_config import (
    BypassConfig,
    BypassConfigManager,
)
from mock_openai_tool.backend.bypass_handler import (
    BypassHandler,
    BypassError,
    HOP_BY_HOP_HEADERS,
)


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    manager = Mock(spec=BypassConfigManager)
    manager.get_config = AsyncMock(return_value=BypassConfig(
        enabled=True,
        target_host="api.example.com",
        target_port=443,
        target_uri="/v1/chat/completions",
        api_key=None,
        use_https=True,
        timeout=60,
    ))
    return manager


@pytest.fixture
def handler(mock_config_manager):
    """Create a BypassHandler instance."""
    return BypassHandler(config_manager=mock_config_manager)


def test_build_url_https_default_port(handler):
    """Test URL building with HTTPS and default port."""
    config = BypassConfig(
        target_host="api.example.com",
        target_port=443,
        target_uri="/v1/chat",
        use_https=True,
    )
    url = handler._build_url(config)
    assert url == "https://api.example.com/v1/chat"


def test_build_url_https_custom_port(handler):
    """Test URL building with HTTPS and custom port."""
    config = BypassConfig(
        target_host="api.example.com",
        target_port=8443,
        target_uri="/v1/chat",
        use_https=True,
    )
    url = handler._build_url(config)
    assert url == "https://api.example.com:8443/v1/chat"


def test_build_url_http_default_port(handler):
    """Test URL building with HTTP and default port."""
    config = BypassConfig(
        target_host="api.example.com",
        target_port=80,
        target_uri="/v1/chat",
        use_https=False,
    )
    url = handler._build_url(config)
    assert url == "http://api.example.com/v1/chat"


def test_build_url_http_custom_port(handler):
    """Test URL building with HTTP and custom port."""
    config = BypassConfig(
        target_host="api.example.com",
        target_port=8080,
        target_uri="/v1/chat",
        use_https=False,
    )
    url = handler._build_url(config)
    assert url == "http://api.example.com:8080/v1/chat"


def test_prepare_headers_without_api_key(handler):
    """Test headers preparation without API key."""
    original_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer original-token",
        "User-Agent": "test-client",
    }
    config = BypassConfig(api_key=None)

    headers = handler._prepare_headers(original_headers, config)

    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer original-token"
    assert headers["User-Agent"] == "test-client"


def test_prepare_headers_with_api_key(handler):
    """Test headers preparation with API key (overrides original)."""
    original_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer original-token",
    }
    config = BypassConfig(api_key="sk-configured-key")

    headers = handler._prepare_headers(original_headers, config)

    assert headers["Authorization"] == "Bearer sk-configured-key"


def test_prepare_headers_filters_hop_by_hop(handler):
    """Test hop-by-hop headers are filtered."""
    original_headers = {
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Host": "original-host.com",
        "Transfer-Encoding": "chunked",
        "Keep-Alive": "timeout=5",
        "User-Agent": "test-client",
    }
    config = BypassConfig()

    headers = handler._prepare_headers(original_headers, config)

    # Should be filtered
    assert "Connection" not in headers
    assert "Host" not in headers
    assert "Transfer-Encoding" not in headers
    assert "Keep-Alive" not in headers

    # Should be kept
    assert "Content-Type" in headers
    assert "User-Agent" in headers


def test_prepare_headers_adds_content_type_if_missing(handler):
    """Test Content-Type is added if missing."""
    original_headers = {}
    config = BypassConfig()

    headers = handler._prepare_headers(original_headers, config)

    assert headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_forward_request_success(handler, mock_config_manager):
    """Test successful request forwarding."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "test-response",
        "choices": [{"message": {"content": "Hello"}}]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    with patch.object(handler, '_get_client', return_value=mock_client):
        request_body = {"messages": [{"role": "user", "content": "Hi"}]}
        original_headers = {"Authorization": "Bearer test"}

        response_body, status_code, elapsed = await handler.forward_request(
            request_body=request_body,
            original_headers=original_headers,
            client_ip="192.168.1.1"
        )

        assert status_code == 200
        assert response_body["id"] == "test-response"
        assert elapsed >= 0


@pytest.mark.asyncio
async def test_forward_request_timeout(handler, mock_config_manager):
    """Test request timeout handling."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    mock_client.is_closed = False

    with patch.object(handler, '_get_client', return_value=mock_client):
        request_body = {"messages": []}
        original_headers = {}

        with pytest.raises(BypassError, match="timeout"):
            await handler.forward_request(
                request_body=request_body,
                original_headers=original_headers,
                client_ip="192.168.1.1"
            )


@pytest.mark.asyncio
async def test_forward_request_connection_error(handler, mock_config_manager):
    """Test connection error handling."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    mock_client.is_closed = False

    with patch.object(handler, '_get_client', return_value=mock_client):
        request_body = {"messages": []}
        original_headers = {}

        with pytest.raises(BypassError, match="Failed to connect"):
            await handler.forward_request(
                request_body=request_body,
                original_headers=original_headers,
                client_ip="192.168.1.1"
            )


@pytest.mark.asyncio
async def test_forward_request_non_json_response(handler, mock_config_manager):
    """Test handling of non-JSON response."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("Not JSON")
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    with patch.object(handler, '_get_client', return_value=mock_client):
        request_body = {"messages": []}
        original_headers = {}

        response_body, status_code, elapsed = await handler.forward_request(
            request_body=request_body,
            original_headers=original_headers,
            client_ip="192.168.1.1"
        )

        assert status_code == 500
        assert "error" in response_body
        assert response_body["error"]["message"] == "Internal Server Error"


@pytest.mark.asyncio
async def test_get_client_creates_new_client(handler, mock_config_manager):
    """Test client creation."""
    config = await mock_config_manager.get_config()
    client = await handler._get_client(config)

    assert client is not None
    assert isinstance(client, httpx.AsyncClient)


@pytest.mark.asyncio
async def test_get_client_reuses_existing_client(handler, mock_config_manager):
    """Test client reuse."""
    config = await mock_config_manager.get_config()

    client1 = await handler._get_client(config)
    client2 = await handler._get_client(config)

    assert client1 is client2


@pytest.mark.asyncio
async def test_close_client(handler, mock_config_manager):
    """Test client closing."""
    config = await mock_config_manager.get_config()
    await handler._get_client(config)

    await handler.close()

    assert handler._client is None


def test_bypass_error_with_cause():
    """Test BypassError stores cause."""
    original_error = ValueError("Original error")
    bypass_error = BypassError("Wrapped error", cause=original_error)

    assert bypass_error.message == "Wrapped error"
    assert bypass_error.cause is original_error
    assert str(bypass_error) == "Wrapped error"
