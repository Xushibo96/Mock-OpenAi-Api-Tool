"""Bypass request handler for forwarding requests to real OpenAI API."""

import logging
import time
from typing import Tuple, Optional

import httpx

from mock_openai_tool.backend.bypass_config import (
    BypassConfig,
    BypassConfigManager,
)

logger = logging.getLogger("bypass")

# Headers to filter out (hop-by-hop headers)
HOP_BY_HOP_HEADERS = {
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'transfer-encoding',
    'upgrade',
    'host',  # Will be set to target host
    'content-length',  # Will be auto-calculated by httpx
}


class BypassError(Exception):
    """Bypass forwarding error."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        self.message = message
        self.cause = cause
        super().__init__(message)


class BypassHandler:
    """Handles request forwarding to real OpenAI API."""

    def __init__(self, config_manager: BypassConfigManager):
        """Initialize bypass handler.

        Args:
            config_manager: Configuration manager instance
        """
        self._config_manager = config_manager
        self._client: Optional[httpx.AsyncClient] = None

    async def forward_request(
        self,
        request_body: dict,
        original_headers: dict,
        client_ip: str
    ) -> Tuple[dict, int, float]:
        """Forward request to real OpenAI API.

        Args:
            request_body: Request body to forward
            original_headers: Original request headers
            client_ip: Client IP address (for logging)

        Returns:
            Tuple of (response_body, status_code, elapsed_time)

        Raises:
            BypassError: If forwarding fails
        """
        config = await self._config_manager.get_config()
        target_url = self._build_url(config)
        headers = self._prepare_headers(original_headers, config)

        logger.info(
            f"Forwarding request from {client_ip} to {target_url}"
        )

        start_time = time.time()

        try:
            client = await self._get_client(config)
            response = await client.post(
                target_url,
                json=request_body,
                headers=headers,
                timeout=config.timeout,
            )

            elapsed = time.time() - start_time

            # Try to parse JSON response
            try:
                response_body = response.json()
            except Exception:
                # If not JSON, wrap in error format
                response_body = {
                    "error": {
                        "message": response.text,
                        "type": "api_error",
                        "code": response.status_code,
                    }
                }

            logger.info(
                f"Received response: status={response.status_code}, "
                f"elapsed={elapsed:.3f}s"
            )

            return response_body, response.status_code, elapsed

        except httpx.TimeoutException as e:
            elapsed = time.time() - start_time
            logger.error(f"Request timeout after {elapsed:.3f}s", exc_info=True)
            raise BypassError(
                f"Request timeout after {config.timeout}s",
                cause=e
            )

        except httpx.ConnectError as e:
            elapsed = time.time() - start_time
            logger.error(f"Connection failed: {e}", exc_info=True)
            raise BypassError(
                f"Failed to connect to {target_url}: {str(e)}",
                cause=e
            )

        except httpx.HTTPError as e:
            elapsed = time.time() - start_time
            logger.error(f"HTTP error: {e}", exc_info=True)
            raise BypassError(
                f"HTTP error: {str(e)}",
                cause=e
            )

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise BypassError(
                f"Unexpected error: {str(e)}",
                cause=e
            )

    def _build_url(self, config: BypassConfig) -> str:
        """Build target URL from config.

        Args:
            config: Bypass configuration

        Returns:
            Complete URL string
        """
        scheme = "https" if config.use_https else "http"

        # Handle default ports
        if (config.use_https and config.target_port == 443) or \
           (not config.use_https and config.target_port == 80):
            return f"{scheme}://{config.target_host}{config.target_uri}"
        else:
            return (
                f"{scheme}://{config.target_host}:"
                f"{config.target_port}{config.target_uri}"
            )

    def _prepare_headers(
        self,
        original_headers: dict,
        config: BypassConfig
    ) -> dict:
        """Prepare headers for forwarding.

        Args:
            original_headers: Original request headers
            config: Bypass configuration

        Returns:
            Filtered and updated headers dict
        """
        # Filter out hop-by-hop headers
        headers = {}
        for key, value in original_headers.items():
            if key.lower() not in HOP_BY_HOP_HEADERS:
                headers[key] = value

        # Override or add Authorization if API key configured
        if config.api_key:
            headers['Authorization'] = f'Bearer {config.api_key}'

        # Ensure Content-Type
        if 'content-type' not in {k.lower() for k in headers.keys()}:
            headers['Content-Type'] = 'application/json'

        return headers

    async def _get_client(self, config: BypassConfig) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Args:
            config: Bypass configuration

        Returns:
            AsyncClient instance
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=config.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
