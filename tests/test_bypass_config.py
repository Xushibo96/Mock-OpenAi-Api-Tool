"""Unit tests for bypass configuration manager."""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from mock_openai_tool.backend.bypass_config import (
    BypassConfig,
    BypassConfigManager,
    ConfigValidationError,
)


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def manager(temp_config_file):
    """Create a BypassConfigManager instance."""
    return BypassConfigManager(config_file=temp_config_file)


@pytest.mark.asyncio
async def test_default_config(manager):
    """Test default configuration values."""
    config = await manager.get_config()
    assert config.enabled is False
    assert config.target_host == "api.openai.com"
    assert config.target_port == 443
    assert config.target_uri == "/v1/chat/completions"
    assert config.api_key is None
    assert config.use_https is False
    assert config.timeout == 60


@pytest.mark.asyncio
async def test_update_config_partial(manager):
    """Test partial configuration update."""
    config = await manager.update_config(target_host="example.com")
    assert config.target_host == "example.com"
    assert config.target_port == 443  # Unchanged


@pytest.mark.asyncio
async def test_update_config_full(manager):
    """Test full configuration update."""
    config = await manager.update_config(
        target_host="custom.api.com",
        target_port=8080,
        target_uri="/api/chat",
        api_key="sk-test123",
        use_https=False,
        timeout=30
    )
    assert config.target_host == "custom.api.com"
    assert config.target_port == 8080
    assert config.target_uri == "/api/chat"
    assert config.api_key == "sk-test123"
    assert config.use_https is False
    assert config.timeout == 30


@pytest.mark.asyncio
async def test_enable_disable(manager):
    """Test enable and disable operations."""
    # Initially disabled
    assert await manager.is_enabled() is False

    # Enable
    result = await manager.enable()
    assert result is True
    assert await manager.is_enabled() is True

    # Disable
    result = await manager.disable()
    assert result is True
    assert await manager.is_enabled() is False


@pytest.mark.asyncio
async def test_enable_with_valid_config(manager):
    """Test enable succeeds with valid default config."""
    # Default config has valid host and port
    result = await manager.enable()
    assert result is True
    assert await manager.is_enabled() is True


@pytest.mark.asyncio
async def test_config_persistence(temp_config_file):
    """Test configuration persists to file."""
    manager1 = BypassConfigManager(config_file=temp_config_file)

    # Update config
    await manager1.update_config(
        target_host="test.com",
        target_port=9000,
        api_key="sk-test"
    )
    await manager1.enable()

    # Create new manager with same file
    manager2 = BypassConfigManager(config_file=temp_config_file)
    config = await manager2.get_config()

    assert config.enabled is True
    assert config.target_host == "test.com"
    assert config.target_port == 9000
    assert config.api_key == "sk-test"


@pytest.mark.asyncio
async def test_validate_invalid_host(manager):
    """Test validation of invalid host."""
    with pytest.raises(ConfigValidationError, match="target_host"):
        await manager.update_config(target_host="invalid host with spaces")


@pytest.mark.asyncio
async def test_validate_empty_host(manager):
    """Test validation of empty host."""
    with pytest.raises(ConfigValidationError, match="cannot be empty"):
        await manager.update_config(target_host="")


@pytest.mark.asyncio
async def test_validate_port_range(manager):
    """Test validation of port range."""
    # Port too low
    with pytest.raises(ConfigValidationError, match="1-65535"):
        await manager.update_config(target_port=0)

    # Port too high
    with pytest.raises(ConfigValidationError, match="1-65535"):
        await manager.update_config(target_port=65536)

    # Valid ports
    await manager.update_config(target_port=1)
    await manager.update_config(target_port=65535)


@pytest.mark.asyncio
async def test_validate_uri_format(manager):
    """Test validation of URI format."""
    # Invalid URI (no leading slash)
    with pytest.raises(ConfigValidationError, match="must start with"):
        await manager.update_config(target_uri="api/chat")

    # Valid URI
    await manager.update_config(target_uri="/api/v1/chat")


@pytest.mark.asyncio
async def test_validate_timeout_range(manager):
    """Test validation of timeout range."""
    # Timeout too low
    with pytest.raises(ConfigValidationError, match="1-300"):
        await manager.update_config(timeout=0)

    # Timeout too high
    with pytest.raises(ConfigValidationError, match="1-300"):
        await manager.update_config(timeout=301)

    # Valid timeouts
    await manager.update_config(timeout=1)
    await manager.update_config(timeout=300)


@pytest.mark.asyncio
async def test_concurrent_access(manager):
    """Test concurrent configuration access is safe."""
    async def update_host(host):
        await manager.update_config(target_host=host)

    # Run concurrent updates
    await asyncio.gather(
        update_host("host1.com"),
        update_host("host2.com"),
        update_host("host3.com"),
    )

    # Should have one of the hosts
    config = await manager.get_config()
    assert config.target_host in ["host1.com", "host2.com", "host3.com"]


@pytest.mark.asyncio
async def test_get_config_returns_copy(manager):
    """Test get_config returns a copy, not reference."""
    config1 = await manager.get_config()
    config1.target_host = "modified.com"

    config2 = await manager.get_config()
    assert config2.target_host != "modified.com"
    assert config2.target_host == "api.openai.com"


@pytest.mark.asyncio
async def test_valid_ip_address_as_host(manager):
    """Test IP address is valid as host."""
    await manager.update_config(target_host="192.168.1.1")
    config = await manager.get_config()
    assert config.target_host == "192.168.1.1"


@pytest.mark.asyncio
async def test_valid_domain_name_as_host(manager):
    """Test domain name is valid as host."""
    await manager.update_config(target_host="api.example.com")
    config = await manager.get_config()
    assert config.target_host == "api.example.com"


@pytest.mark.asyncio
async def test_updated_at_timestamp(manager):
    """Test updated_at timestamp is set."""
    config1 = await manager.get_config()
    initial_time = config1.updated_at

    await asyncio.sleep(0.01)
    await manager.update_config(target_host="new.com")

    config2 = await manager.get_config()
    assert config2.updated_at > initial_time
