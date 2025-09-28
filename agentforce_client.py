"""
Client for interacting with the Salesforce Agentforce API.

This module provides a class to manage sessions and stream messages with the
Agentforce API, handling authentication and Server-Sent Events (SSE).
"""

import os
import httpx
import json
import logging
from typing import AsyncGenerator
from fastmcp import Context
from auth_manager import AuthManager
import dotenv

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

# --- 1. Configuration & Constants ---

SF_DOMAIN_URL = os.environ.get("SF_DOMAIN_URL")
AGENTFORCE_BASE_URL = "https://api.salesforce.com"
AGENT_ID = os.environ.get("AGENTFORCE_AGENT_ID")


class AgentforceClient:
    """Handles interaction with the Agentforce API."""

    def __init__(self, auth_manager: AuthManager):
        """
        Initializes the AgentforceClient.

        Args:
            auth_manager: An instance of AuthManager for handling authentication.
        """
        self.auth_manager = auth_manager
        self.client = httpx.AsyncClient(base_url=AGENTFORCE_BASE_URL, timeout=None)
        
    async def close(self):
        await self.client.aclose()


    async def _authenticated_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Makes an authenticated request to the Agentforce API.

        This method fetches a valid token, makes the request, and handles token
        expiration by refreshing the token and retrying the request if necessary.

        Args:
            method: The HTTP method for the request.
            url: The URL for the request.
            **kwargs: Additional arguments for the request.

        Returns:
            The HTTP response.

        Raises:
            RuntimeError: If the API request fails.
        """
        try:
            access_token = await self.auth_manager.get_valid_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                **kwargs.pop('headers', {})
            }
            logger.debug(f"headers = {headers}")
            async with httpx.AsyncClient(base_url=AGENTFORCE_BASE_URL, timeout=None) as client:
                response = await client.request(
                    method, url, headers=headers, **kwargs)

                if response.status_code == 401:
                    logger.warning(
                        "⚠️ Token expired (401). Attempting token refresh...")
                    await self.auth_manager._fetch_new_token()

                    access_token = await self.auth_manager.get_valid_token()
                    headers["Authorization"] = f"Bearer {access_token}"
                    response = await client.request(
                        method, url, headers=headers, **kwargs)

                response.raise_for_status()
                return response

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Agentforce API HTTP Error {e.response.status_code}: {e.response.text}") from e

    async def start_session(self, uuid: str) -> str:
        """
        Starts a new session with the Agentforce Agent.

        Args:
            uuid: A unique identifier for the session.

        Returns:
            The session ID.
        """
        url = f"/einstein/ai-agent/v1/agents/{AGENT_ID}/sessions"
        payload = {
            "externalSessionKey": uuid,
            "streamingCapabilities": {
                "chunkTypes": ["Text"]
            },
            "bypassUser": False,
            "instanceConfig": {
                "endpoint": SF_DOMAIN_URL
            }
        }
        response = await self._authenticated_request("POST", url, json=payload, headers={"Content-Type": "application/json"})
        return response.json().get("sessionId")

    async def stream_message(self, session_id: str, message: str, ctx: Context | None) -> AsyncGenerator[str, None]:
        """
        Streams a message to the Agentforce Agent and yields the response chunks.

        This method sends a message to the specified session and processes the
        Server-Sent Events (SSE) stream from the response, yielding the text
        chunks as they are received.

        Args:
            session_id: The ID of the session.
            message: The message to send to the agent.
            ctx: The FastMCP context for logging and interaction.

        Yields:
            Response chunks from the Agentforce Agent.
        """
        url = f"/einstein/ai-agent/v1/sessions/{session_id}/messages/stream"
        payload = {
            "message": {"sequenceId": 1, "type": "Text", "text": message}
        }
        access_token = await self.auth_manager.get_valid_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }

        logger.info(f"Sending message '{message}' on session '{session_id}")
        async with httpx.AsyncClient(base_url=AGENTFORCE_BASE_URL, timeout=None) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    logger.debug(f"RAW LINE: {line}")
                    if line.startswith("data:"):
                        try:
                            events = json.loads(line.lstrip("data:").strip())
                            for event in events:
                                if (event == "message"):
                                    if events[event].get("type") == "TextChunk":
                                        yield events[event]["message"]
                                    elif events[event].get("type") == "Inform":
                                        logger.debug(
                                            f"message =  {events[event]['result']}")
                                        yield "\n\n" + json.dumps(events[event]["result"], indent=2)
                                    elif events[event].get("type") == "ProgressIndicator":
                                        if ctx:
                                            await ctx.info(f"ProgressIndicator = {events[event]['message']}")
                                    elif events[event].get("type") == "Inquire":
                                        logger.info(
                                            f"INQUIRY: {events[event]['message']}")
                                        if ctx: 
                                            elicitation = await ctx.elicit(events[event]['message'], response_type=str)
                                            if elicitation.action == "accept":
                                                logger.info(f"elicitation accepted.  response = {elicitation.data}")
                                                yield f"\n\n{elicitation.data}\n\n"
                                                async for chunk in self.stream_message(session_id, elicitation.data, ctx):
                                                    yield chunk
                                            elif elicitation.action == "decline":
                                                logger.info("elicitation declined.")
                                                return
                                            else:
                                                return

                        except json.JSONDecodeError:
                            logger.warning(
                                "Encountered non JSON data processing SSE event starting with 'data:'.  That shouldn't happen. ")
                            continue

    async def end_session(self, session_id: str):
        """
        Ends the specified session.

        Args:
            session_id: The ID of the session to end.
        """
        url = f"/einstein/ai-agent/v1/sessions/{session_id}"
        await self._authenticated_request("DELETE", url, headers={"x-session-end-reason": "UserRequest"})
        
    async def __exit__(self, exc_type, exc_value, traceback):
        await self.client.aclose()