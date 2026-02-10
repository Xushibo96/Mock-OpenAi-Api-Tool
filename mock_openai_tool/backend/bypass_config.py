"""Bypass configuration manager for OpenAI API forwarding."""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bypass")


@dataclass
class BypassConfig:
    """Bypass configuration data class."""
    enabled: bool = False
    target_host: str = "api.openai.com"
    target_port: int = 443
    target_uri: str = "/v1/chat/completions"
    api_key: Optional[str] = None
    use_https: bool = False
    timeout: int = 60
    updated_at: float = 0.0


class ConfigValidationError(ValueError):
    """Configuration validation error."""
    pass


class BypassConfigManager:
    """Manages bypass configuration with validation and persistence."""

    def __init__(self, config_file: str = "bypass_config.json"):
        """Initialize configuration manager.

        Args:
            config_file: Path to configuration file
        """
        self._config_file = Path(config_file)
        self._config = BypassConfig()
        self._lock = asyncio.Lock()
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        if not self._config_file.exists():
            logger.info("Config file not found, using defaults")
            return

        try:
            with open(self._config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._config = BypassConfig(**data)
            logger.info("Loaded bypass config from file")
        except Exception as e:
            logger.error(f"Failed to load config: {e}", exc_info=True)

    async def get_config(self) -> BypassConfig:
        """Get current configuration.

        Returns:
            Current BypassConfig instance
        """
        async with self._lock:
            return BypassConfig(**asdict(self._config))

    async def update_config(self, **kwargs) -> BypassConfig:
        """Update configuration (partial or full).

        Args:
            **kwargs: Configuration fields to update

        Returns:
            Updated BypassConfig instance

        Raises:
            ConfigValidationError: If validation fails
        """
        async with self._lock:
            # Create updated config
            config_dict = asdict(self._config)
            config_dict.update(kwargs)
            config_dict['updated_at'] = asyncio.get_event_loop().time()

            new_config = BypassConfig(**config_dict)

            # Validate
            self._validate_config(new_config)

            # Apply and persist
            self._config = new_config
            await self._persist()

            logger.info(f"Config updated: {kwargs.keys()}")
            return BypassConfig(**asdict(self._config))

    async def enable(self) -> bool:
        """Enable bypass mode.

        Returns:
            True if enabled successfully

        Raises:
            ConfigValidationError: If config is incomplete
        """
        async with self._lock:
            # Validate required fields
            if not self._config.target_host:
                raise ConfigValidationError("target_host is required")
            if not self._config.target_port:
                raise ConfigValidationError("target_port is required")

            self._config.enabled = True
            self._config.updated_at = asyncio.get_event_loop().time()
            await self._persist()

            logger.info(
                f"Bypass enabled: {self._config.target_host}:"
                f"{self._config.target_port}"
            )
            return True

    async def disable(self) -> bool:
        """Disable bypass mode.

        Returns:
            True if disabled successfully
        """
        async with self._lock:
            self._config.enabled = False
            self._config.updated_at = asyncio.get_event_loop().time()
            await self._persist()

            logger.info("Bypass disabled")
            return True

    async def is_enabled(self) -> bool:
        """Check if bypass mode is enabled.

        Returns:
            True if enabled
        """
        async with self._lock:
            return self._config.enabled

    def _validate_config(self, config: BypassConfig) -> None:
        """Validate configuration.

        Args:
            config: Configuration to validate

        Raises:
            ConfigValidationError: If validation fails
        """
        # Validate target_host (domain or IP)
        if not config.target_host:
            raise ConfigValidationError("target_host cannot be empty")

        # Simple validation: allow domain names and IP addresses
        if not re.match(r'^[\w\.\-]+$', config.target_host):
            raise ConfigValidationError(
                f"Invalid target_host format: {config.target_host}"
            )

        # Validate target_port
        if not (1 <= config.target_port <= 65535):
            raise ConfigValidationError(
                f"target_port must be 1-65535, got {config.target_port}"
            )

        # Validate target_uri
        if not config.target_uri.startswith('/'):
            raise ConfigValidationError(
                "target_uri must start with '/'"
            )

        # Validate timeout
        if not (1 <= config.timeout <= 300):
            raise ConfigValidationError(
                f"timeout must be 1-300 seconds, got {config.timeout}"
            )

    async def _persist(self) -> None:
        """Persist configuration to file."""
        try:
            data = asdict(self._config)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Config persisted to file")
        except Exception as e:
            logger.error(f"Failed to persist config: {e}", exc_info=True)
