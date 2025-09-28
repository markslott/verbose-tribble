"""
Manages OAuth 2.0 authentication for the Salesforce API.

This module provides a class to handle the acquisition and caching of access
tokens using the Client Credentials flow.
"""

import os
import time
import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages access token acquisition and caching using Client Credentials flow."""

    def __init__(self, client_id: str, client_secret: str, token_url: str):
        """
        Initializes the AuthManager.

        Args:
            client_id: The Salesforce connected app client ID.
            client_secret: The Salesforce connected app client secret.
            token_url: The Salesforce token endpoint URL.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    async def get_valid_token(self) -> str | None:
        """
        Returns a valid access token.

        This method returns the cached token if it's still valid, otherwise, it
        fetches a new one.

        Returns:
            A valid access token, or None if a token could not be obtained.
        """
        if self._access_token and self._expires_at > time.time() + 60:  # Refresh 60s before actual expiry
            return self._access_token

        await self._fetch_new_token()
        return self._access_token

    async def _fetch_new_token(self):
        """
        Executes the OAuth 2.0 Client Credentials flow to get a new token.

        This method makes a POST request to the Salesforce token endpoint to
        obtain a new access token, which is then cached.

        Raises:
            RuntimeError: If the token acquisition fails.
        """
        auth_payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,

        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data=auth_payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                token_data = response.json()

                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self._expires_at = time.time() + expires_in

                print(
                    f"✅ New Salesforce access token acquired. Expires in {expires_in}s.")

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"OAuth Token Error: HTTP {e.response.status_code}. Response: {e.response.text}") from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to acquire Salesforce access token: {e}") from e